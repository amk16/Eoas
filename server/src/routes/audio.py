from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Dict, Any
from ..middleware.auth import authenticate_token
from ..services.scribe_service import transcribe_audio


router = APIRouter()


@router.post('/transcribe')
async def transcribe(
    audio: UploadFile = File(...),
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Transcribe audio endpoint."""
    try:
        # Read audio file content
        audio_buffer = await audio.read()
        filename = audio.filename or 'audio.webm'
        content_type = audio.content_type or ''
        
        # Transcribe using Scribe (pass both filename and content_type for format detection)
        result = await transcribe_audio(audio_buffer, filename, content_type)
        
        # Scribe returns {"text": ..., "raw": ...} format
        # Extract language from raw event if available, otherwise return None
        language = None
        if 'raw' in result and isinstance(result['raw'], dict):
            raw_event = result['raw']
            # Check if language is available in the raw event
            language = raw_event.get('language') or raw_event.get('language_code')
        
        return {
            'transcript': result['text'],
            'language': language
        }
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f'Transcription error: {e}')
        print(f'Traceback: {error_trace}')
        raise HTTPException(
            status_code=500,
            detail=f'Failed to transcribe audio: {str(e)}'
        )

