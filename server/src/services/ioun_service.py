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

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# API Keys
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY') or os.getenv('ELEVENLABS_API_KEY_CONVAI')

# Model configuration
GEMINI_MODEL = "models/gemini-2.5-flash"
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Default Eleven Labs voice (Rachel)

# In-memory conversation history storage (keyed by user_id)
_conversation_histories: Dict[str, List[Dict[str, str]]] = {}


def get_conversation_history(user_id: str) -> List[Dict[str, str]]:
    """Get conversation history for a user."""
    return _conversation_histories.get(user_id, [])


def add_to_history(user_id: str, role: str, content: str) -> None:
    """Add a message to conversation history."""
    if user_id not in _conversation_histories:
        _conversation_histories[user_id] = []
    _conversation_histories[user_id].append({"role": role, "content": content})
    # Keep only last 20 messages to avoid token limits
    if len(_conversation_histories[user_id]) > 20:
        _conversation_histories[user_id] = _conversation_histories[user_id][-20:]


def clear_history(user_id: str) -> None:
    """Clear conversation history for a user."""
    if user_id in _conversation_histories:
        del _conversation_histories[user_id]


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


async def generate_narrative_dialogue(response: str) -> str:
    """
    Generate narrative dialogue version of the response using Gemini.
    
    Converts the written response into natural spoken dialogue optimized for TTS.
    
    Args:
        response: The original response text
    
    Returns:
        Narrative version optimized for speech
    """
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured, returning original response")
        return response
    
    logger.info("Generating narrative dialogue with Gemini")
    logger.info(f"Response length: {len(response)} characters")
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    
    # System instruction for narrative conversion
    narrative_system_instruction = """You are converting written responses into natural spoken dialogue. 
Make it conversational, easy to listen to, and suitable for text-to-speech. 
Remove any markdown formatting, code blocks, or complex structures. 
Keep the meaning and key information, but make it flow naturally when spoken aloud.
Use natural pauses and conversational phrasing. Avoid reading lists or tables verbatim - instead, 
describe them in a natural way."""
    
    # Initialize model with narrative system instruction
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=narrative_system_instruction
    )
    
    # Create prompt for conversion
    prompt = f"""Convert the following response into natural spoken dialogue. Make it conversational and easy to listen to.

Response to convert:
{response}"""
    
    # Run synchronous Gemini API call in thread pool
    def generate_sync():
        logger.info("Calling Gemini API for narrative generation...")
        response_obj = model.generate_content(prompt)
        return response_obj.text
    
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        narrative_text = await loop.run_in_executor(executor, generate_sync)
    
    logger.info(f"Narrative generation complete ({len(narrative_text)} characters)")
    return narrative_text


async def post_process_for_narrative(response: str) -> str:
    """
    Post-process the display response to create a narrative version optimized for speech.
    
    Uses Gemini to generate natural spoken dialogue from the written response.
    
    Args:
        response: The original response text
    
    Returns:
        Narrative version optimized for TTS
    """
    logger.info("Post-processing response for narrative")
    return await generate_narrative_dialogue(response)


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

