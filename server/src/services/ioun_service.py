# ioun_service.py
import os
import json
import re
import asyncio
import logging
import base64
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
from ..db.firebase import get_firestore
from firebase_admin import firestore

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY') or os.getenv('ELEVENLABS_API_KEY_CONVAI')

# Model configuration
GEMINI_MODEL = "models/gemini-2.5-flash"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Default Eleven Labs voice (Rachel)

# Maximum number of messages to load from history (to avoid token limits)
MAX_HISTORY_MESSAGES = 50


def get_conversation_history(user_id: str, conversation_id: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get conversation history for a user from Firestore.
    
    Args:
        user_id: User ID
        conversation_id: Optional conversation ID. If provided, loads from that conversation.
                        If None, returns empty list (new conversation).
    
    Returns:
        List of message dicts with 'role' and 'content' keys
    """
    if not conversation_id:
        logger.info(f"No conversation_id provided for user {user_id}, returning empty history")
        return []
    
    try:
        db = get_firestore()
        if not db:
            logger.warning("Firestore not initialized, returning empty history")
            return []
        
        # Get messages from Firestore subcollection
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
        messages_ref = conv_ref.collection('messages')
        
        # Order by timestamp ascending and limit to last N messages
        messages_docs = messages_ref.order_by('timestamp', direction=firestore.Query.ASCENDING).stream()
        
        messages = []
        for doc in messages_docs:
            msg_data = doc.to_dict()
            messages.append({
                'role': msg_data.get('role', 'user'),
                'content': msg_data.get('content', '')
            })
        
        # Keep only last MAX_HISTORY_MESSAGES to avoid token limits
        if len(messages) > MAX_HISTORY_MESSAGES:
            messages = messages[-MAX_HISTORY_MESSAGES:]
            logger.info(f"Limited conversation history to last {MAX_HISTORY_MESSAGES} messages")
        
        logger.info(f"Loaded {len(messages)} messages from conversation {conversation_id} for user {user_id}")
        return messages
    except Exception as e:
        logger.error(f"Error loading conversation history: {e}")
        return []


def add_to_history(user_id: str, conversation_id: str, role: str, content: str) -> None:
    """
    Add a message to conversation history in Firestore.
    
    Args:
        user_id: User ID
        conversation_id: Conversation ID
        role: Message role ('user' or 'assistant')
        content: Message content
    """
    if not conversation_id:
        logger.warning(f"No conversation_id provided, cannot save message to history")
        return
    
    try:
        db = get_firestore()
        if not db:
            logger.warning("Firestore not initialized, cannot save message to history")
            return
        
        # Verify conversation exists
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(conversation_id)
        conv_doc = conv_ref.get()
        
        if not conv_doc.exists:
            logger.warning(f"Conversation {conversation_id} does not exist, cannot save message")
            return
        
        # Prepare message data
        message_data = {
            'role': role,
            'content': content,
            'timestamp': firestore.SERVER_TIMESTAMP,
        }
        
        # Add message to subcollection
        messages_ref = conv_ref.collection('messages')
        messages_ref.add(message_data)
        
        # Update conversation's last_message_at and updated_at
        conv_ref.update({
            'last_message_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        })
        
        # Auto-generate title from first user message if title is still default
        if role == 'user':
            conv_data = conv_doc.to_dict()
            if conv_data and conv_data.get('title') == 'New Conversation':
                # Generate title from first 50 characters of first user message
                title = content[:50].strip()
                if len(content) > 50:
                    title += '...'
                conv_ref.update({'title': title})
        
        logger.info(f"Added {role} message to conversation {conversation_id} for user {user_id}")
    except Exception as e:
        logger.error(f"Error saving message to history: {e}")
        # Don't raise - this is not critical for the chat to work


def clear_history(user_id: str, conversation_id: Optional[str] = None) -> None:
    """
    Clear conversation history for a user.
    
    Note: This function is kept for backward compatibility but doesn't do anything
    since we're using Firestore. To clear history, delete the conversation.
    """
    logger.info(f"clear_history called for user {user_id}, conversation {conversation_id} (no-op with Firestore)")


async def chat_with_gemini(
    transcript: str,
    system_prompt: str,
    conversation_history: List[Dict[str, str]],
    user_id: str
) -> str:
    """
    Send transcript to Gemini and get response.
    
    Args:
        transcript: User's transcript text
        system_prompt: System prompt for Gemini
        conversation_history: Previous conversation messages
        user_id: User ID for logging
    
    Returns:
        Gemini's response text
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured")
    
    logger.info(f"Chatting with Gemini for user {user_id}")
    logger.info(f"Transcript length: {len(transcript)} characters")
    logger.info(f"History length: {len(conversation_history)} messages")
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Initialize model with system instruction
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt
    )
    
    # Build chat history for Gemini
    # Convert conversation history to Gemini format
    history = []
    for msg in conversation_history:
        # Gemini expects 'user' or 'model' as role
        role = "user" if msg["role"] == "user" else "model"
        history.append({
            "role": role,
            "parts": [msg["content"]]
        })
    
    # Run synchronous Gemini API call in thread pool
    def generate_sync():
        logger.info("Calling Gemini API...")
        # Start chat with history
        chat = model.start_chat(history=history)
        # Send current message
        response = chat.send_message(transcript)
        return response.text
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        response_text = await loop.run_in_executor(executor, generate_sync)
    
    logger.info(f"Received response from Gemini ({len(response_text)} characters)")
    return response_text


async def generate_narrative_dialogue(transcript: str, system_prompt: str, conversation_history: List[Dict[str, str]], user_id: str) -> str:
    """
    Generate narrative dialogue response from user transcript using Gemini.
    
    Generates a natural spoken dialogue response optimized for TTS, directly from the user's transcript.
    
    Args:
        transcript: User's transcript text
        system_prompt: System prompt for context (same as main response)
        conversation_history: Previous conversation messages
        user_id: User ID for logging
    
    Returns:
        Narrative version optimized for speech
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured, returning empty narrative")
        return ""
    
    logger.info(f"Generating narrative dialogue from transcript for user {user_id}")
    logger.info(f"Transcript length: {len(transcript)} characters")
    logger.info(f"History length: {len(conversation_history)} messages")
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    
    # System instruction for narrative generation - focused on concise spoken responses
    narrative_system_instruction = f"""{system_prompt}

IMPORTANT: Generate a concise, conversational spoken response optimized for text-to-speech.
- Keep it under 1000 characters
- Use natural, conversational phrasing
- Avoid reading lists or tables verbatim - describe them naturally
- Make it flow smoothly when spoken aloud
- Be friendly and engaging"""
    
    # Initialize model with narrative system instruction
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=narrative_system_instruction
    )
    
    # Build chat history for Gemini
    history = []
    for msg in conversation_history:
        # Gemini expects 'user' or 'model' as role
        role = "user" if msg["role"] == "user" else "model"
        history.append({
            "role": role,
            "parts": [msg["content"]]
        })
    
    # Run synchronous Gemini API call in thread pool
    def generate_sync():
        logger.info("Calling Gemini API for narrative generation...")
        # Start chat with history
        chat = model.start_chat(history=history)
        # Send current message
        response = chat.send_message(transcript)
        return response.text
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        narrative_text = await loop.run_in_executor(executor, generate_sync)
    
    logger.info(f"Narrative generation complete ({len(narrative_text)} characters)")
    return narrative_text


async def generate_narrative_from_transcript(
    transcript: str,
    system_prompt: str,
    conversation_history: List[Dict[str, str]],
    user_id: str
) -> str:
    """
    Generate narrative dialogue response from user transcript.
    
    This is a convenience wrapper around generate_narrative_dialogue().
    
    Args:
        transcript: User's transcript text
        system_prompt: System prompt for context
        conversation_history: Previous conversation messages
        user_id: User ID for logging
    
    Returns:
        Narrative version optimized for TTS
    """
    return await generate_narrative_dialogue(transcript, system_prompt, conversation_history, user_id)


async def post_process_for_narrative(response: str) -> str:
    """
    DEPRECATED: This function is kept for backward compatibility but will be replaced.
    The narrative should now be generated from transcript, not from response.
    
    This function will be removed in Phase 2 when the route is updated.
    """
    logger.warning("post_process_for_narrative() is deprecated. Narrative should be generated from transcript.")
    # For now, return empty string - this will be fixed in Phase 2
    return ""


async def generate_tts_audio(
    text: str,
    voice_id: Optional[str] = None
) -> Optional[str]:
    """
    Generate TTS audio using Eleven Labs API.
    
    Args:
        text: Text to convert to speech
        voice_id: Optional voice ID (defaults to DEFAULT_VOICE_ID)
    
    Returns:
        Base64-encoded audio data, or None if generation fails
    """
    if not ELEVENLABS_API_KEY:
        logger.warning("ELEVENLABS_API_KEY not configured, skipping TTS generation")
        return None
    
    if not text or not text.strip():
        logger.warning("Empty text provided for TTS")
        return None
    
    voice = voice_id or DEFAULT_VOICE_ID
    logger.info(f"Generating TTS audio with voice {voice} ({len(text)} characters)")
    
    try:
        # Initialize ElevenLabs client
        client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
        
        # Generate audio
        def generate_sync():
            audio_generator = client.text_to_speech.convert(
                voice_id=voice,
                text=text,
                model_id="eleven_turbo_v2_5"
            )
            # Collect all audio chunks
            audio_data = b""
            for chunk in audio_generator:
                audio_data += chunk
            return audio_data
        
        # Run in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            audio_data = await loop.run_in_executor(executor, generate_sync)
        
        # Convert to base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        logger.info(f"Generated TTS audio ({len(audio_data)} bytes)")
        return audio_base64
        
    except Exception as e:
        logger.error(f"Failed to generate TTS audio: {e}")
        return None

