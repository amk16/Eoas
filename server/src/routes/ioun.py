# ioun.py
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from ..middleware.auth import authenticate_token
from ..services.ioun_service import (
    chat_with_gemini,
    post_process_for_narrative,
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
    
    Accepts a transcript, sends it to Gemini with conversation history,
    post-processes the response for narrative TTS, and generates audio.
    
    Args:
        request: Chat request with transcript and optional voice_id
        user_id: Authenticated user ID
    
    Returns:
        Chat response with display response, narrative response, and audio
    """
    logger.info(f"Chat request from user {user_id}")
    logger.info(f"Transcript length: {len(request.transcript)} characters")
    
    try:
        # Get user context and D&D rules
        user_context = await get_user_context(user_id)
        dnd_rules = get_dnd_rules_knowledge()
        
        # Build system prompt
        system_prompt = build_system_prompt(user_context, dnd_rules)
        logger.info(f"Built system prompt ({len(system_prompt)} characters)")
        
        # Get conversation history
        conversation_history = get_conversation_history(user_id)
        
        # Add user message to history
        add_to_history(user_id, "user", request.transcript)
        
        # Send to Gemini
        response_text = await chat_with_gemini(
            transcript=request.transcript,
            system_prompt=system_prompt,
            conversation_history=conversation_history,
            user_id=user_id
        )
        
        # Add assistant response to history
        add_to_history(user_id, "assistant", response_text)
        
        # Post-process for narrative
        narrative_response = await post_process_for_narrative(response_text)
        
        # Generate TTS audio
        audio_base64 = await generate_tts_audio(
            text=narrative_response,
            voice_id=request.voice_id
        )
        
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

