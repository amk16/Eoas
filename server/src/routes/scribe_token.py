import os
import time
from collections import defaultdict
from fastapi import APIRouter, Request, HTTPException
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

router = APIRouter()

# Read ElevenLabs API key from environment
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Rate limiting configuration
# Default: 20 requests per 60 seconds per IP
# Can be overridden via SCRIBE_RATE_LIMIT environment variable
RATE_LIMIT = int(os.getenv("SCRIBE_RATE_LIMIT", "20"))
RATE_LIMIT_WINDOW = 60  # seconds

# In-memory rate limiter: IP -> list of timestamps
# Automatically cleans up old entries to prevent memory growth
_last_calls: dict[str, list[float]] = defaultdict(list)


def _cleanup_old_entries(ip: str, now: float) -> None:
    """Remove timestamps older than the rate limit window."""
    _last_calls[ip] = [t for t in _last_calls[ip] if now - t < RATE_LIMIT_WINDOW]


def _check_rate_limit(ip: str, now: float) -> bool:
    """
    Check if IP has exceeded rate limit.
    Returns True if allowed, False if rate limited.
    """
    _cleanup_old_entries(ip, now)
    return len(_last_calls[ip]) < RATE_LIMIT


def _record_request(ip: str, now: float) -> None:
    """Record a request timestamp for the given IP."""
    _last_calls[ip].append(now)


@router.get("/api/scribe-token")
async def get_scribe_token(request: Request):
    """
    Generate a single-use token for ElevenLabs Realtime Scribe.
    
    This endpoint:
    - Calls ElevenLabs API to create a single-use token
    - Enforces rate limiting (20 requests per 60 seconds per IP by default)
    - Optionally tracks usage by X-USER-ID header if present
    - Never exposes the permanent ELEVENLABS_API_KEY to the client
    
    Returns:
        JSON response from ElevenLabs containing the token
    """
    # Check if API key is configured
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: ELEVENLABS_API_KEY not set"
        )
    
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Check rate limit
    if not _check_rate_limit(client_ip, current_time):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Maximum {RATE_LIMIT} requests per {RATE_LIMIT_WINDOW} seconds."
        )
    
    # Record this request
    _record_request(client_ip, current_time)
    
    # Optional: Track user ID if header is present (for analytics/logging)
    user_id = request.headers.get("X-USER-ID")
    # Note: We don't use user_id for rate limiting, just for potential logging
    
    # Call ElevenLabs API to create single-use token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.elevenlabs.io/v1/single-use-token/realtime_scribe",
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )
            
            # Handle non-200 responses
            if response.status_code >= 400:
                # Log error details without exposing API key
                error_text = response.text
                logger.error(f"ElevenLabs API error (status {response.status_code}): {error_text}")
                
                # Return appropriate error to client
                if response.status_code == 401:
                    raise HTTPException(
                        status_code=502,
                        detail="Authentication failed with ElevenLabs API. Please check server configuration."
                    )
                elif response.status_code == 429:
                    raise HTTPException(
                        status_code=502,
                        detail="ElevenLabs API rate limit exceeded. Please try again later."
                    )
                else:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Failed to obtain token from ElevenLabs API (status {response.status_code})"
                    )
            
            # Return the JSON response from ElevenLabs
            # Response format may vary: could be {"token": "..."}, {"signed_url": "..."}, or direct object
            return response.json()
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Request to ElevenLabs API timed out. Please try again."
        )
    except httpx.RequestError as e:
        # Network or connection errors
        logger.error(f"Network error calling ElevenLabs API: {e}")
        raise HTTPException(
            status_code=502,
            detail="Failed to connect to ElevenLabs API. Please try again later."
        )
    except HTTPException:
        # Re-raise HTTP exceptions (rate limit, etc.)
        raise
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected error in scribe token endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while generating the token."
        )

