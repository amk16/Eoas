# ioun.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import asyncio
from ..middleware.auth import authenticate_token
from ..services.ioun_service import (
    chat_with_gemini,
    generate_narrative_from_transcript,
    generate_tts_audio,
    get_conversation_history,
    add_to_history,
    get_conversation_mode_state,
    update_conversation_mode_state
)
from ..services.prompt_service import build_system_prompt
from ..services.context_service import get_user_context
from ..services.dnd_rules_service import get_dnd_rules_knowledge
from ..services.creation_analysis_service import analyze_for_creations
from ..services.mode_analysis_service import (
    detect_creation_intent,
    analyze_in_mode,
    check_exit_skip,
    is_creation_complete,
    generate_mode_response,
    generate_completion_confirmation
)
from ..services.creation_execution_service import (
    execute_campaign_creation,
    execute_session_creation,
    execute_character_creation
)

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    transcript: str
    voice_id: Optional[str] = None
    conversation_id: Optional[str] = None  # Optional conversation ID to continue existing conversation


class ChatResponse(BaseModel):
    response: str
    narrative_response: str
    audio_base64: Optional[str] = None
    creation_requests: Optional[List[Dict[str, Any]]] = None
    mode: Optional[str] = None  # Current MODE or null
    pending_events: Optional[List[str]] = None  # Remaining events to process
    current_event_data: Optional[Dict[str, Any]] = None  # Accumulated data


@router.post("/ioun/chat", response_model=ChatResponse)
async def chat_with_ioun(
    request: ChatRequest,
    user_id: str = Depends(authenticate_token)
) -> ChatResponse:
    """
    Chat with Ioun voice assistant.
    
    Accepts a transcript, generates narrative and response in parallel,
    generates TTS audio from narrative, and returns all results.
    
    Args:
        request: Chat request with transcript and optional voice_id
        user_id: Authenticated user ID
    
    Returns:
        Chat response with display response, narrative response, and audio
    """
    logger.info(f"Chat request from user {user_id}")
    logger.info(f"Transcript length: {len(request.transcript)} characters")
    logger.info(f"Conversation ID: {request.conversation_id or 'None (new conversation)'}")
    
    try:
        # Get user context and D&D rules
        user_context = await get_user_context(user_id)
        dnd_rules = get_dnd_rules_knowledge()
        
        # Load conversation MODE state
        mode_state = get_conversation_mode_state(user_id, request.conversation_id)
        current_mode = mode_state.get("mode")
        pending_events = mode_state.get("pending_events", [])
        current_event_data = mode_state.get("current_event_data", {})
        intent_detection_message = mode_state.get("intent_detection_message")
        
        logger.info(f"MODE state: mode={current_mode}, pending_events={pending_events}, has_data={bool(current_event_data)}")
        
        # Build system prompt
        system_prompt = build_system_prompt(user_context, dnd_rules)
        logger.info(f"Built system prompt ({len(system_prompt)} characters)")
        
        # Get conversation history (from Firestore if conversation_id provided)
        conversation_history = get_conversation_history(user_id, request.conversation_id)
        
        # Add user message to history (will create conversation if needed)
        if request.conversation_id:
            add_to_history(user_id, request.conversation_id, "user", request.transcript)
        else:
            logger.info("No conversation_id provided, message will not be saved to history")
        
        # Check for EXIT/SKIP commands if in MODE
        if current_mode:
            found_command, command_type = check_exit_skip(request.transcript)
            if found_command:
                if command_type == "exit":
                    # Exit MODE completely, clear state
                    logger.info("EXIT command detected - exiting MODE")
                    if request.conversation_id:
                        update_conversation_mode_state(
                            user_id, request.conversation_id,
                            mode="",  # Sentinel value to clear mode
                            pending_events=[],
                            current_event_data={},
                            intent_detection_message=""  # Clear it
                        )
                    current_mode = None
                    pending_events = []
                    current_event_data = {}
                elif command_type == "skip":
                    # Skip current MODE, move to next pending event
                    logger.info("SKIP command detected - skipping current MODE")
                    if pending_events:
                        pending_events.pop(0)  # Remove current event
                        if pending_events:
                            # Enter next MODE (keep intent_detection_message)
                            next_event_type = pending_events[0]
                            current_mode = f"{next_event_type}_creation"
                            current_event_data = {}
                            # Keep intent_detection_message for next MODE
                            if request.conversation_id:
                                update_conversation_mode_state(
                                    user_id, request.conversation_id,
                                    mode=current_mode,
                                    pending_events=pending_events,
                                    current_event_data={}
                                    # intent_detection_message=None - keep existing
                                )
                        else:
                            # No more pending events, exit MODE
                            current_mode = None
                            current_event_data = {}
                            if request.conversation_id:
                                update_conversation_mode_state(
                                    user_id, request.conversation_id,
                                    mode="",  # Sentinel value to clear mode
                                    pending_events=[],
                                    current_event_data={},
                                    intent_detection_message=""  # Clear it
                                )
                    else:
                        # No pending events to begin with, just exit MODE
                        current_mode = None
                        current_event_data = {}
                        if request.conversation_id:
                            update_conversation_mode_state(
                                user_id, request.conversation_id,
                                mode="",  # Sentinel value to clear mode
                                pending_events=[],
                                current_event_data={},
                                intent_detection_message=""  # Clear it
                            )
        
        # MODE-specific analysis task
        mode_analysis_data = None
        creation_complete = False
        created_item = None
        mode_just_completed = False
        completed_mode_type = None  # Store the mode type that just completed
        
        if current_mode:
            # In MODE: Run MODE-specific analysis
            logger.info(f"In MODE: {current_mode} - running MODE-specific analysis")
            try:
                mode_analysis_data = await analyze_in_mode(
                    mode=current_mode,
                    transcript=request.transcript,
                    user_context=user_context,
                    current_event_data=current_event_data,
                    conversation_history=conversation_history
                )
                
                # Merge with current_event_data
                current_event_data = mode_analysis_data
                
                # Check if creation is complete
                creation_complete = is_creation_complete(current_mode, current_event_data)
                
                if creation_complete:
                    logger.info(f"Creation complete for {current_mode}")
                    # Execute creation
                    try:
                        if current_mode == "campaign_creation":
                            created_item = await execute_campaign_creation(current_event_data, user_id)
                            logger.info(f"✓ Created campaign: {created_item.get('name')} (ID: {created_item.get('id')})")
                        elif current_mode == "character_creation":
                            created_item = await execute_character_creation(current_event_data, user_id)
                            logger.info(f"✓ Created character: {created_item.get('name')} (ID: {created_item.get('id')})")
                        elif current_mode == "session_creation":
                            created_item = await execute_session_creation(current_event_data, user_id)
                            logger.info(f"✓ Created session: {created_item.get('name')} (ID: {created_item.get('id')})")
                        
                        # Move to next pending event or exit MODE
                        if pending_events:
                            pending_events.pop(0)  # Remove completed event
                            if pending_events:
                                # Enter next MODE (keep intent_detection_message if it was the original trigger)
                                next_event_type = pending_events[0]
                                current_mode = f"{next_event_type}_creation"
                                current_event_data = {}
                                # Keep intent_detection_message for next MODE (it was the original trigger)
                                logger.info(f"Moving to next MODE: {current_mode}")
                            else:
                                # No more pending events, exit MODE
                                mode_just_completed = True
                                completed_mode_type = current_mode
                                current_mode = None
                                current_event_data = {}
                                intent_detection_message = ""  # Clear it
                                logger.info("All events complete - exiting MODE")
                        else:
                            # No pending events, exit MODE
                            mode_just_completed = True
                            completed_mode_type = current_mode
                            current_mode = None
                            current_event_data = {}
                            intent_detection_message = ""  # Clear it
                            logger.info("Creation complete - exiting MODE")
                        
                        # Update conversation state
                        if request.conversation_id:
                            update_conversation_mode_state(
                                user_id, request.conversation_id,
                                mode="" if current_mode is None else current_mode,  # Use sentinel to clear if None
                                pending_events=pending_events,
                                current_event_data=current_event_data,
                                intent_detection_message=intent_detection_message
                            )
                    except Exception as e:
                        logger.error(f"Error executing creation: {e}")
                        # Don't exit MODE on error - let user retry
                        creation_complete = False
                else:
                    # Update conversation state with new data
                    if request.conversation_id:
                        update_conversation_mode_state(
                            user_id, request.conversation_id,
                            current_event_data=current_event_data
                        )
            except Exception as e:
                logger.error(f"Error in MODE analysis (non-blocking): {e}")
                # Keep current state on error
        else:
            # Not in MODE: Detect creation intent
            logger.info("Not in MODE - detecting creation intent")
            try:
                detected_types = await detect_creation_intent(request.transcript, user_context)
                if detected_types:
                    logger.info(f"Creation intent detected: {detected_types}")
                    # Enter MODE with first event type
                    first_event_type = detected_types[0]
                    current_mode = f"{first_event_type}_creation"
                    pending_events = detected_types
                    current_event_data = {}
                    intent_detection_message = request.transcript
                    
                    # Update conversation state
                    if request.conversation_id:
                        update_conversation_mode_state(
                            user_id, request.conversation_id,
                            mode=current_mode,
                            pending_events=pending_events,
                            current_event_data={},
                            intent_detection_message=intent_detection_message if intent_detection_message else None
                        )
                    
                    logger.info(f"Entered MODE: {current_mode}, pending events: {pending_events}")
            except Exception as e:
                logger.error(f"Error in intent detection (non-blocking): {e}")
        
        # Generate response based on MODE state
        response_text = None
        narrative_response = None
        audio_base64 = None
        
        if current_mode is not None:
            # In MODE: Generate MODE-specific response
            logger.info(f"In MODE ({current_mode}) - generating MODE-specific response")
            try:
                mode_response = await generate_mode_response(
                    mode=current_mode,
                    current_event_data=current_event_data,
                    system_prompt=system_prompt,
                    conversation_history=conversation_history,
                    user_id=user_id
                )
                response_text = mode_response
                narrative_response = mode_response  # Use same text for both
                
                # Add to history if conversation_id provided
                if request.conversation_id:
                    add_to_history(user_id, request.conversation_id, "assistant", response_text)
                
                # Generate TTS audio
                if narrative_response:
                    try:
                        audio_base64 = await generate_tts_audio(text=narrative_response, voice_id=request.voice_id)
                    except Exception as e:
                        logger.error(f"Error generating TTS audio for MODE response: {e}")
                        audio_base64 = None
            except Exception as e:
                logger.error(f"Error generating MODE response: {e}")
                # Fallback to simple message
                response_text = "Please provide the required information."
                narrative_response = response_text
        
        elif mode_just_completed and created_item and completed_mode_type:
            # MODE just completed: Generate completion confirmation
            logger.info(f"MODE just completed ({completed_mode_type}) - generating completion confirmation")
            try:
                confirmation = generate_completion_confirmation(
                    mode=completed_mode_type,
                    created_item=created_item
                )
                response_text = confirmation
                narrative_response = confirmation  # Use same text for both
                
                # Add to history if conversation_id provided
                if request.conversation_id:
                    add_to_history(user_id, request.conversation_id, "assistant", response_text)
                
                # Generate TTS audio
                if narrative_response:
                    try:
                        audio_base64 = await generate_tts_audio(text=narrative_response, voice_id=request.voice_id)
                    except Exception as e:
                        logger.error(f"Error generating TTS audio for completion confirmation: {e}")
                        audio_base64 = None
            except Exception as e:
                logger.error(f"Error generating completion confirmation: {e}")
                # Fallback to simple message
                response_text = "Creation completed successfully."
                narrative_response = response_text
        
        else:
            # Normal flow: Generate narrative and response in parallel
            logger.info("Starting parallel generation of narrative and response")
            
            async def generate_response():
                """Generate the main response from Gemini."""
                try:
                    response_text = await chat_with_gemini(
                        transcript=request.transcript,
                        system_prompt=system_prompt,
                        conversation_history=conversation_history,
                        user_id=user_id
                    )
                    # Add assistant response to history (if conversation_id provided)
                    if request.conversation_id:
                        add_to_history(user_id, request.conversation_id, "assistant", response_text)
                    logger.info(f"Response generation complete ({len(response_text)} chars)")
                    return response_text
                except Exception as e:
                    logger.error(f"Error generating response: {e}")
                    raise
            
            async def generate_narrative():
                """Generate narrative response from transcript."""
                try:
                    narrative_text = await generate_narrative_from_transcript(
                        transcript=request.transcript,
                        system_prompt=system_prompt,
                        conversation_history=conversation_history,
                        user_id=user_id
                    )
                    logger.info(f"Narrative generation complete ({len(narrative_text)} chars)")
                    return narrative_text
                except Exception as e:
                    logger.error(f"Error generating narrative: {e}")
                    raise
            
            # Create tasks for narrative and response generation (parallel)
            narrative_task = asyncio.create_task(generate_narrative())
            response_task = asyncio.create_task(generate_response())
            
            # Wait for either task to complete, then start TTS if narrative is ready
            # This allows TTS to start as soon as narrative completes, even if response is still generating
            done, pending = await asyncio.wait(
                [narrative_task, response_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Determine which task completed first
            tts_task = None
            
            for task in done:
                try:
                    if task == narrative_task:
                        narrative_response = await task
                        logger.info("Narrative completed first - starting TTS generation immediately")
                        # Start TTS generation immediately since narrative is ready
                        tts_task = asyncio.create_task(
                            generate_tts_audio(text=narrative_response, voice_id=request.voice_id)
                        )
                    elif task == response_task:
                        response_text = await task
                        logger.info("Response completed first - waiting for narrative to start TTS")
                except Exception as e:
                    logger.error(f"Error processing completed task: {e}")
                    raise
            
            # Wait for the remaining task(s) to complete
            if narrative_response is None:
                try:
                    # Narrative is still pending, wait for it
                    narrative_response = await narrative_task
                    logger.info("Narrative completed - starting TTS generation")
                    # Start TTS now that narrative is ready
                    tts_task = asyncio.create_task(
                        generate_tts_audio(text=narrative_response, voice_id=request.voice_id)
                    )
                except Exception as e:
                    logger.error(f"Error waiting for narrative: {e}")
                    # Cancel response task if narrative failed
                    response_task.cancel()
                    raise
            
            if response_text is None:
                try:
                    # Response is still pending, wait for it
                    response_text = await response_task
                except Exception as e:
                    logger.error(f"Error waiting for response: {e}")
                    # Cancel TTS task if response failed
                    if tts_task:
                        tts_task.cancel()
                    raise
            
            # Wait for TTS to complete (it should have started by now)
            if tts_task:
                try:
                    logger.info("Waiting for TTS audio generation to complete")
                    audio_base64 = await tts_task
                except Exception as e:
                    logger.error(f"Error generating TTS audio: {e}")
                    # TTS failure is not critical - we can still return the text responses
                    audio_base64 = None
        
        logger.info("Chat request completed successfully")
        
        # Build response with MODE information
        return ChatResponse(
            response=response_text,
            narrative_response=narrative_response,
            audio_base64=audio_base64,
            creation_requests=None,  # Legacy field, kept for compatibility
            mode=current_mode,
            pending_events=pending_events if pending_events else None,
            current_event_data=current_event_data if current_event_data else None
        )
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception(f"Error in chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )


class ExecuteCreationsRequest(BaseModel):
    creation_requests: List[Dict[str, Any]]


class CreatedItem(BaseModel):
    action_type: str
    item: Dict[str, Any]
    status: str  # 'success' or 'error'
    error: Optional[str] = None


class ExecuteCreationsResponse(BaseModel):
    created_items: List[CreatedItem]
    success_count: int
    error_count: int


@router.post("/ioun/execute-creations", response_model=ExecuteCreationsResponse)
async def execute_creations(
    request: ExecuteCreationsRequest,
    user_id: str = Depends(authenticate_token)
) -> ExecuteCreationsResponse:
    """
    Execute creation requests detected from transcript analysis.
    
    This endpoint is called after user confirms creation requests detected in the chat.
    
    Args:
        request: ExecuteCreationsRequest with list of creation requests
        user_id: Authenticated user ID
    
    Returns:
        ExecuteCreationsResponse with created items and status for each
    """
    logger.info(f"Execute creations request from user {user_id}")
    logger.info(f"Number of creation requests: {len(request.creation_requests)}")
    
    created_items = []
    success_count = 0
    error_count = 0
    
    for i, creation_request in enumerate(request.creation_requests):
        action_type = creation_request.get('action_type')
        data = creation_request.get('data', {})
        
        if not action_type:
            logger.warning(f"Creation request {i+1}: Missing action_type, skipping")
            error_count += 1
            created_items.append(CreatedItem(
                action_type='unknown',
                item={},
                status='error',
                error='Missing action_type'
            ))
            continue
        
        try:
            if action_type == 'create_campaign':
                created_item = await execute_campaign_creation(data, user_id)
                created_items.append(CreatedItem(
                    action_type='create_campaign',
                    item=created_item,
                    status='success'
                ))
                success_count += 1
                logger.info(f"✓ Successfully created campaign: {created_item.get('name')} (ID: {created_item.get('id')})")
            
            elif action_type == 'create_session':
                created_item = await execute_session_creation(data, user_id)
                created_items.append(CreatedItem(
                    action_type='create_session',
                    item=created_item,
                    status='success'
                ))
                success_count += 1
                logger.info(f"✓ Successfully created session: {created_item.get('name')} (ID: {created_item.get('id')})")
            
            elif action_type == 'create_character':
                created_item = await execute_character_creation(data, user_id)
                created_items.append(CreatedItem(
                    action_type='create_character',
                    item=created_item,
                    status='success'
                ))
                success_count += 1
                logger.info(f"✓ Successfully created character: {created_item.get('name')} (ID: {created_item.get('id')})")
            
            else:
                error_msg = f"Unknown action_type: {action_type}"
                logger.warning(f"Creation request {i+1}: {error_msg}")
                error_count += 1
                created_items.append(CreatedItem(
                    action_type=action_type,
                    item={},
                    status='error',
                    error=error_msg
                ))
        
        except ValueError as e:
            # Validation errors
            error_msg = str(e)
            logger.error(f"Creation request {i+1} validation error: {error_msg}")
            error_count += 1
            created_items.append(CreatedItem(
                action_type=action_type,
                item={},
                status='error',
                error=error_msg
            ))
        
        except HTTPException as e:
            # HTTP errors (like Firestore not available)
            error_msg = e.detail
            logger.error(f"Creation request {i+1} HTTP error: {error_msg}")
            error_count += 1
            created_items.append(CreatedItem(
                action_type=action_type,
                item={},
                status='error',
                error=error_msg
            ))
        
        except Exception as e:
            # Unexpected errors
            error_msg = f"Unexpected error: {str(e)}"
            logger.exception(f"Creation request {i+1} unexpected error: {error_msg}")
            error_count += 1
            created_items.append(CreatedItem(
                action_type=action_type,
                item={},
                status='error',
                error=error_msg
            ))
    
    logger.info(f"Execute creations complete: {success_count} success(es), {error_count} error(s)")
    
    return ExecuteCreationsResponse(
        created_items=created_items,
        success_count=success_count,
        error_count=error_count
    )

