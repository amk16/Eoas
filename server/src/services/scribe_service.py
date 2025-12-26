# scribe_service.py
import os
import io
import json
import base64
import asyncio
import tempfile
import subprocess
from typing import Dict, Any, AsyncIterator, Optional, Tuple

import numpy as np
import resampy
import websockets
from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.utils import which
import shutil

load_dotenv()

ELEVENLABS_REALTIME_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Configure pydub to use ffmpeg explicitly
_FFMPEG_PATH = which("ffmpeg") or shutil.which("ffmpeg")
if _FFMPEG_PATH:
    AudioSegment.converter = _FFMPEG_PATH
    AudioSegment.ffmpeg = _FFMPEG_PATH
    AudioSegment.ffprobe = which("ffprobe") or shutil.which("ffprobe") or _FFMPEG_PATH.replace("ffmpeg", "ffprobe")

# Config: tweak if you want auto commit, different chunk size, etc.
MODEL_ID = "scribe_v2_realtime"
AUDIO_FORMAT = "pcm_16000"
COMMIT_STRATEGY = "manual"  # we send commit at the end
INCLUDE_TIMESTAMPS = True
# chunk size in bytes. 3200 bytes ~ 0.1s at 16kHz 16-bit mono (16000 samples/sec * 2 bytes/sample * 0.1s = 3200)
PCM_CHUNK_BYTES = 3200


def build_realtime_url(
    model_id: str = MODEL_ID,
    audio_format: str = AUDIO_FORMAT,
    commit_strategy: str = COMMIT_STRATEGY,
    include_timestamps: bool = INCLUDE_TIMESTAMPS,
    language_code: Optional[str] = None,
) -> str:
    from urllib.parse import urlencode

    params = {
        "model_id": model_id,
        "audio_format": audio_format,
        "commit_strategy": commit_strategy,
        "include_timestamps": "true" if include_timestamps else "false",
    }
    if language_code:
        params["language_code"] = language_code

    return f"{ELEVENLABS_REALTIME_URL}?{urlencode(params)}"


def validate_audio_data(audio_bytes: bytes, filename: Optional[str] = None, content_type: str = "") -> Tuple[bool, str]:
    """
    Validate basic audio data properties before attempting to decode.
    Note: We don't validate magic bytes strictly, as ffmpeg can often decode
    files even if format headers don't match exactly (e.g., variations in encoding).
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not audio_bytes:
        return False, "Audio data is empty"
    
    # Check minimum file size (files should be at least a few bytes to be valid)
    if len(audio_bytes) < 4:
        return False, f"Audio file too small ({len(audio_bytes)} bytes). Minimum size is 4 bytes."
    
    # Note: We intentionally don't validate magic bytes here because:
    # 1. FFmpeg can decode many format variations
    # 2. Some audio formats have different header structures
    # 3. Files might be in a different format than the extension suggests
    # 4. We want to let ffmpeg attempt decoding and provide detailed error messages
    
    return True, ""


def get_ffmpeg_error_details(input_file: str, format_hint: Optional[str] = None) -> str:
    """
    Call ffmpeg directly to get detailed error output when decoding fails.
    
    Returns:
        String containing ffmpeg stderr output
    """
    if not _FFMPEG_PATH:
        return "ffmpeg not found"
    
    try:
        # Build ffmpeg command to probe the file
        cmd = [_FFMPEG_PATH, '-v', 'error', '-i', input_file, '-f', 'null', '-']
        
        # Add format hint if provided
        if format_hint:
            cmd = [_FFMPEG_PATH, '-v', 'error', '-f', format_hint, '-i', input_file, '-f', 'null', '-']
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        
        error_output = result.stderr.strip()
        if not error_output and result.returncode != 0:
            error_output = f"ffmpeg returned error code: {result.returncode}"
        
        return error_output
    except subprocess.TimeoutExpired:
        return "ffmpeg command timed out"
    except Exception as e:
        return f"Failed to run ffmpeg: {str(e)}"


def decode_to_pcm16_mono_16k(audio_bytes: bytes, filename: Optional[str] = None, content_type: str = "") -> bytes:
    """
    Decode arbitrary audio bytes (wav, webm, mp3, etc.) using pydub (ffmpeg)
    then convert to mono, resample to 16000 Hz, and return little-endian int16 bytes.
    Supports WebM/Opus and other formats that ffmpeg can handle.
    
    Args:
        audio_bytes: Raw audio data bytes
        filename: Optional filename to help determine format (e.g., 'audio.webm', 'audio.ogg')
        content_type: Optional MIME type (e.g., 'audio/webm', 'audio/ogg') for better format detection
    """
    # Validate audio data
    is_valid, validation_error = validate_audio_data(audio_bytes, filename, content_type)
    if not is_valid:
        raise ValueError(f"Audio data validation failed: {validation_error}")
    
    # Check if ffmpeg is available
    if not _FFMPEG_PATH:
        raise RuntimeError(
            "ffmpeg is required for audio decoding but was not found. "
            "Please install ffmpeg: https://ffmpeg.org/download.html\n"
            "On macOS: brew install ffmpeg"
        )
    
    # Determine format from content_type first (more accurate), then filename, then default
    format_hint = None
    ext = '.webm'  # Default extension
    
    # Map MIME types to format hints
    mime_format_map = {
        'audio/webm': 'webm',
        'audio/webm;codecs=opus': 'webm',
        'audio/ogg': 'ogg',
        'audio/opus': 'opus',
        'audio/mpeg': 'mp3',
        'audio/mp3': 'mp3',
        'audio/wav': 'wav',
        'audio/x-wav': 'wav',
        'audio/mp4': 'm4a',
        'audio/m4a': 'm4a',
        'audio/aac': 'aac',
        'audio/flac': 'flac',
    }
    
    if content_type:
        format_hint = mime_format_map.get(content_type.lower().split(';')[0])  # Remove codec info
        # Also determine extension from content type
        if 'webm' in content_type.lower():
            ext = '.webm'
        elif 'ogg' in content_type.lower():
            ext = '.ogg'
        elif 'opus' in content_type.lower():
            ext = '.opus'
        elif 'mp3' in content_type.lower() or 'mpeg' in content_type.lower():
            ext = '.mp3'
        elif 'wav' in content_type.lower():
            ext = '.wav'
        elif 'm4a' in content_type.lower() or 'mp4' in content_type.lower():
            ext = '.m4a'
        elif 'aac' in content_type.lower():
            ext = '.aac'
        elif 'flac' in content_type.lower():
            ext = '.flac'
    
    # Fall back to filename if content_type didn't provide format
    if not format_hint and filename:
        # Extract extension from filename
        ext = os.path.splitext(filename)[1].lower()
        if not ext:
            ext = '.webm'  # Default if no extension found
    
    # Map extensions to format hints if we still don't have one
    if not format_hint:
        format_map = {
            '.webm': 'webm',
            '.ogg': 'ogg',
            '.opus': 'opus',
            '.mp3': 'mp3',
            '.wav': 'wav',
            '.m4a': 'm4a',
            '.aac': 'aac',
            '.flac': 'flac',
        }
        format_hint = format_map.get(ext)
    
    # Create a temporary file to store the audio bytes
    # Using a temporary file instead of BytesIO ensures ffmpeg can properly read the data
    temp_file = None
    temp_file_path = None
    
    try:
        # Create temporary file with appropriate suffix
        temp_file = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        temp_file_path = temp_file.name
        temp_file.write(audio_bytes)
        temp_file.close()
        temp_file = None  # Mark as closed so we don't try to close it again
        
        # Load audio from file using pydub (supports WebM, MP3, WAV, etc.)
        # pydub uses ffmpeg under the hood for format conversion
        # Try with format hint first, then without if it fails
        audio = None
        pydub_error = None
        try:
            if format_hint:
                audio = AudioSegment.from_file(temp_file_path, format=format_hint)
            else:
                audio = AudioSegment.from_file(temp_file_path)
        except Exception as e:
            pydub_error = e
            # If format hint fails, try without format hint (let ffmpeg auto-detect)
            try:
                audio = AudioSegment.from_file(temp_file_path)
            except Exception as e2:
                # Both attempts failed, get detailed ffmpeg error
                ffmpeg_error = get_ffmpeg_error_details(temp_file_path, format_hint)
                file_size = len(audio_bytes)
                error_details = (
                    f"Failed to decode audio file.\n"
                    f"File size: {file_size} bytes\n"
                    f"Filename: {filename or 'unknown'}\n"
                    f"Content-Type: {content_type or 'unknown'}\n"
                    f"Format hint: {format_hint or 'auto-detect'}\n"
                    f"Extension: {ext}\n"
                    f"Pydub error: {str(pydub_error)}\n"
                    f"Second attempt error: {str(e2)}\n"
                    f"\nFFmpeg error details:\n{ffmpeg_error}"
                )
                raise ValueError(f"Unsupported audio format or corrupted audio data: {error_details}") from e2
        
        # Convert to mono if stereo/multi-channel
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Resample to 16kHz if needed
        if audio.frame_rate != 16000:
            audio = audio.set_frame_rate(16000)
        
        # Convert to PCM 16-bit (signed 16-bit little-endian)
        # raw_audio_data returns bytes in the format: signed 16-bit PCM, little-endian
        pcm_bytes = audio.raw_data
        
        return pcm_bytes
        
    except FileNotFoundError as e:
        error_msg = str(e)
        if "ffmpeg" in error_msg.lower() or "ffprobe" in error_msg.lower():
            raise RuntimeError(
                f"ffmpeg executable not found: {error_msg}\n"
                "Please install ffmpeg: https://ffmpeg.org/download.html\n"
                "On macOS: brew install ffmpeg"
            ) from e
        raise
    except ValueError:
        # Re-raise ValueError as-is (already has detailed error message)
        raise
    except Exception as e:
        error_msg = str(e)
        file_size = len(audio_bytes) if audio_bytes else 0
        
        # Try to get ffmpeg error details if we have a temp file path
        ffmpeg_details = ""
        if temp_file_path is not None:
            try:
                ffmpeg_details = f"\n\nFFmpeg error details:\n{get_ffmpeg_error_details(temp_file_path, format_hint)}"
            except Exception:
                pass
        
        error_details = (
            f"Failed to decode audio.\n"
            f"File size: {file_size} bytes\n"
            f"Filename: {filename or 'unknown'}\n"
            f"Content-Type: {content_type or 'unknown'}\n"
            f"Format hint: {format_hint or 'auto-detect'}\n"
            f"Extension: {ext}\n"
            f"Error: {error_msg}{ffmpeg_details}"
        )
        
        if "format" in error_msg.lower() or "codec" in error_msg.lower() or "invalid" in error_msg.lower():
            raise ValueError(f"Unsupported audio format or corrupted audio data: {error_details}") from e
        else:
            raise RuntimeError(f"Failed to decode audio: {error_details}") from e
    finally:
        # Clean up temporary file
        if temp_file is not None:
            try:
                temp_file.close()
            except Exception:
                pass
        if temp_file_path is not None:
            try:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
            except Exception as cleanup_error:
                # Log but don't fail on cleanup errors
                print(f"Warning: Failed to delete temporary file {temp_file_path}: {cleanup_error}")


async def _pcm_chunker(pcm_bytes: bytes, chunk_size: int = PCM_CHUNK_BYTES) -> AsyncIterator[bytes]:
    """
    Yield PCM bytes in small chunks suitable for streaming to ElevenLabs.
    """
    for i in range(0, len(pcm_bytes), chunk_size):
        yield pcm_bytes[i : i + chunk_size]
        # don't sleep by default — we stream as fast as we have data
        await asyncio.sleep(0)


class ScribeError(RuntimeError):
    pass


async def transcribe_audio(audio_buffer: bytes, filename: str = "audio.webm", content_type: str = "", language_code: Optional[str] = None) -> Dict[str, Any]:
    """
    High-level function to replace your Groq transcribe_audio:
    - Accepts raw audio bytes (uploaded file content).
    - Decodes/resamples to 16kHz mono PCM.
    - Streams to ElevenLabs Realtime WebSocket.
    - Sends "commit" and waits for a committed transcript event.
    Returns a dict: {"text": "...", "raw": <committed_event>}
    """
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY not set in environment")

    # decode + resample to PCM16 16kHz mono
    pcm = decode_to_pcm16_mono_16k(audio_buffer, filename, content_type)

    ws_url = build_realtime_url(language_code=language_code)

    headers = [("xi-api-key", ELEVENLABS_API_KEY)]

    # collect final committed transcript event
    final_event: Optional[Dict[str, Any]] = None

    try:
        async with websockets.connect(ws_url, extra_headers=headers, write_limit=2**20, max_size=None) as ws:
            # Wait for session_started:
            first_raw = await ws.recv()
            try:
                first_msg = json.loads(first_raw)
            except Exception:
                first_msg = {"raw": first_raw}

            # check for session_started - if not present, just continue but log
            # (docs show a session_started handshake event)
            # Stream audio chunks
            async for chunk in _pcm_chunker(pcm):
                b64 = base64.b64encode(chunk).decode("ascii")
                msg = {
                    "message_type": "input_audio_chunk",
                    "audio_base_64": b64,
                    "sample_rate": 16000,
                }
                await ws.send(json.dumps(msg))

            # after all audio is sent, tell the server to commit the transcript
            await ws.send(json.dumps({"message_type": "commit"}))

            # read messages until we get a committed transcript
            while True:
                try:
                    raw = await ws.recv()
                except websockets.ConnectionClosedOK:
                    break
                except websockets.ConnectionClosedError as e:
                    raise ScribeError(f"Websocket closed with error: {e}")

                try:
                    msg = json.loads(raw)
                except Exception:
                    # unexpected non-json message
                    continue

                mtype = msg.get("message_type", "")

                if mtype in ("partial_transcript", "partial_transcript_with_timestamps"):
                    # optional: you could log or stream partials back to caller
                    continue

                if mtype in ("committed_transcript", "committed_transcript_with_timestamps"):
                    final_event = msg
                    # we can break early; if you expect multiple committed events, collect instead
                    break

                # error messages
                if mtype.endswith("Error") or "error" in msg:
                    raise ScribeError(f"Scribe API error: {msg}")

            if not final_event:
                raise ScribeError("No committed_transcript received from Scribe.")

            # Build a convenient response similar to the Groq/Whisper wrapper:
            text = final_event.get("text") or final_event.get("transcript") or ""
            return {"text": text, "raw": final_event}

    except Exception as exc:
        raise ScribeError(f"Transcription failed: {exc}")

