# ioun.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import asyncio
from ..middleware.auth import authenticate_token
from ..services.ioun_service import (
    chat_with_gemini,
    generate_narrative_from_transcript,
    generate_tts_audio,
    get_conversation_history,
    add_to_history
)
from ..services.conversational_ai_service import build_system_prompt
from ..services.context_service import get_user_context
from ..services.dnd_rules_service import get_dnd_rules_knowledge

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
        
        # Run narrative and response generation in parallel
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
        
        # Create tasks for narrative and response generation
        narrative_task = asyncio.create_task(generate_narrative())
        response_task = asyncio.create_task(generate_response())
        
        # Wait for either task to complete, then start TTS if narrative is ready
        # This allows TTS to start as soon as narrative completes, even if response is still generating
        done, pending = await asyncio.wait(
            [narrative_task, response_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Determine which task completed first
        narrative_response = None
        response_text = None
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
        try:
            logger.info("Waiting for TTS audio generation to complete")
            audio_base64 = await tts_task
        except Exception as e:
            logger.error(f"Error generating TTS audio: {e}")
            # TTS failure is not critical - we can still return the text responses
            audio_base64 = None
        
        logger.info("Chat request completed successfully")
        
        return ChatResponse(
            response=response_text,
            narrative_response=narrative_response,
            audio_base64=audio_base64
        )
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error in chat request: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}"
        )

