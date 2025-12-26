import os
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from groq import Groq

# Ensure .env is loaded
load_dotenv()


async def transcribe_audio(audio_buffer: bytes, filename: str = 'audio.webm') -> Dict[str, Any]:
    """
    Transcribe audio using Groq Cloud Whisper API.
    
    Args:
        audio_buffer: Audio file bytes (WebM, MP3, WAV, etc.)
        filename: Original filename for the audio
    
    Returns:
        Dictionary with 'text', 'language', and 'segments' keys
    """
    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        raise ValueError('GROQ_API_KEY is not configured')
    
    # Create a temporary file to store the audio
    server_dir = Path(__file__).parent.parent.parent
    temp_dir = server_dir / 'temp'
    temp_dir.mkdir(exist_ok=True)
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(
        dir=temp_dir,
        suffix='.webm',
        delete=False
    ) as temp_file:
        temp_file.write(audio_buffer)
        temp_file_path = temp_file.name
    
    try:
        # Initialize Groq client (reads GROQ_API_KEY from environment)
        client = Groq(api_key=groq_api_key)
        
        # Run synchronous Groq client call in thread pool to avoid blocking
        def transcribe_sync():
            with open(temp_file_path, 'rb') as audio_file:
                return client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    response_format="verbose_json"
                )
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, transcribe_sync)
        
        # Extract results
        result = {
            'text': response.text if hasattr(response, 'text') else '',
            'language': getattr(response, 'language', None),
            'segments': getattr(response, 'segments', None)
        }
        
        return result
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'response') and hasattr(e.response, 'json'):
            try:
                error_body = e.response.json()
                error_detail = error_body.get('error', {}).get('message', str(e))
            except:
                pass
        raise Exception(f'Transcription failed: {error_detail}')
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception as e:
            print(f'Error deleting temp file: {e}')

