# creation_analysis_service.py
import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai
from .mode_analysis_service import detect_creation_intent

# Ensure .env is loaded
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Model configuration
GEMINI_MODEL = "models/gemini-2.5-flash"


async def analyze_for_creations(
    transcript: str,
    user_context: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Analyze transcript for creation requests (campaigns, sessions, characters) using Google Gemini API.
    
    NOTE: This function is kept for backward compatibility. For new code, use detect_creation_intent()
    from mode_analysis_service for intent detection, which returns ordered event types.
    
    Args:
        transcript: The transcript text to analyze
        user_context: Dictionary containing user's existing campaigns, sessions, and characters
                      (from context_service.get_user_context)
    
    Returns:
        List of creation request dictionaries with action_type, data, and transcript_segment
    """
    logger.info("=" * 60)
    logger.info("Starting creation request analysis with Gemini (legacy function)")
    logger.info(f"Transcript length: {len(transcript)} characters")
    
    # First detect intent using new service
    detected_types = await detect_creation_intent(transcript, user_context)
    
    # If no intent detected, return empty list
    if not detected_types:
        logger.info("No creation intent detected, returning empty list")
        return []
    
    # For backward compatibility, convert to old format
    # This maintains the old API but uses new intent detection
    creation_requests = []
    for event_type in detected_types:
        creation_requests.append({
            'action_type': f'create_{event_type}',
            'data': {},  # Data will be collected in MODE
            'transcript_segment': transcript
        })
    
    logger.info(f"Converted {len(detected_types)} intent(s) to legacy format")
    return creation_requests
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured")
        raise ValueError('GEMINI_API_KEY is not configured')
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
    
    # Build context sections for the prompt
    campaigns_list = ""
    if user_context.get("campaigns"):
        campaigns_list = "\n".join([
            f"- {camp['name']} (ID: {camp['id']})"
            for camp in user_context["campaigns"][:20]  # Limit to first 20
        ])
        logger.info(f"Found {len(user_context['campaigns'])} existing campaigns in context")
    
    sessions_list = ""
    if user_context.get("sessions"):
        sessions_list = "\n".join([
            f"- {session['name']} (ID: {session['id']})"
            for session in user_context["sessions"][:20]  # Limit to first 20
        ])
        logger.info(f"Found {len(user_context['sessions'])} existing sessions in context")
    
    characters_list = ""
    if user_context.get("characters"):
        characters_list = "\n".join([
            f"- {char['name']} (ID: {char['id']})"
            for char in user_context["characters"][:30]  # Limit to first 30
        ])
        logger.info(f"Found {len(user_context['characters'])} existing characters in context")
    
    # Build the prompt for Gemini
    prompt = f"""You are analyzing a D&D (Dungeons & Dragons) voice assistant transcript to detect requests to CREATE campaigns, sessions, or characters.

EXISTING USER DATA (for reference - do not create duplicates):
{f"Campaigns:{chr(10)}{campaigns_list}" if campaigns_list else "Campaigns: None"}
{f"Sessions:{chr(10)}{sessions_list}" if sessions_list else "Sessions: None"}
{f"Characters:{chr(10)}{characters_list}" if characters_list else "Characters: None"}

Analyze the following transcript and extract any requests to CREATE campaigns, sessions, or characters.

CREATION REQUEST TYPES:

1. CREATE CAMPAIGN:
   - Required: name (string)
   - Optional: description (string)
   - Example phrases: "create a campaign called X", "new campaign named X", "make a campaign X"

2. CREATE SESSION:
   - Required: name (string)
   - Optional: campaign_id (string - must match existing campaign ID from list above if mentioned)
   - Optional: character_ids (array of strings - must match existing character IDs if mentioned)
   - Example phrases: "create a session", "new session called X", "start a session for campaign Y"

3. CREATE CHARACTER:
   - Required: name (string), max_hp (integer)
   - Optional: campaign_id (string - must match existing campaign ID if mentioned)
   - Optional: race (string), class_name (string), level (integer), ac (integer), 
              initiative_bonus (integer), background (string), alignment (string), 
              notes (string), and other D&D character fields
   - Example phrases: "create a character named X", "new character called X", "make a character"

IMPORTANT RULES:
- Only extract creation requests where the user is explicitly asking to CREATE something
- Do NOT extract informational queries like "tell me about my campaigns" or "show me characters"
- If a campaign/character name is mentioned but already exists in the context, do NOT create a duplicate
- For sessions, character_ids should only include characters that exist in the context (match by name or ID)
- Extract ALL available information from the transcript for each creation request
- If required fields (name, max_hp for characters) are missing, still include the request but mark missing fields

Transcript:
{transcript}

Return a JSON array of creation requests. Each request must include:
- "action_type": One of "create_campaign", "create_session", or "create_character"
- "data": Object with all extracted fields for that creation type
- "transcript_segment": The exact text segment that describes this creation request

Example response format:
[
  {{
    "action_type": "create_campaign",
    "data": {{
      "name": "Lost Mines of Phandelver",
      "description": "A classic D&D adventure"
    }},
    "transcript_segment": "create a campaign called Lost Mines of Phandelver, it's a classic D&D adventure"
  }},
  {{
    "action_type": "create_character",
    "data": {{
      "name": "Aragorn",
      "max_hp": 50,
      "race": "Human",
      "class_name": "Ranger",
      "level": 5
    }},
    "transcript_segment": "create a character named Aragorn, he's a level 5 Human Ranger with 50 hit points"
  }}
]

If no creation requests are found, return an empty array: []

Return ONLY valid JSON, no additional text or explanation."""

    try:
        # Use Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info("Initialized Gemini model")
        logger.info(f"Sending prompt to Gemini (prompt length: {len(prompt)} characters)")
        
        # Run synchronous Gemini API call in thread pool to avoid blocking
        def generate_sync():
            logger.info("Calling Gemini API for creation analysis...")
            return model.generate_content(prompt)
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, generate_sync)
        
        logger.info("Received response from Gemini API")
        
        # Extract JSON from response
        response_text = response.text.strip()
        logger.debug(f"Raw Gemini response (first 200 chars): {response_text[:200]}...")
        
        # Remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
        if response_text.startswith('```json'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
        
        # Parse JSON response
        logger.info("Parsing JSON response from Gemini")
        creation_requests = json.loads(response_text)
        
        if not isinstance(creation_requests, list):
            logger.warning(f"Gemini returned non-list response, converting to list: {type(creation_requests)}")
            creation_requests = [creation_requests] if creation_requests else []
        
        logger.info(f"Parsed {len(creation_requests)} raw creation request(s) from Gemini response")
        
        # Validate and clean up creation requests
        validated_requests = []
        for i, request in enumerate(creation_requests):
            if not isinstance(request, dict):
                logger.warning(f"Request {i+1}: Not a dictionary, skipping")
                continue
            
            action_type = request.get('action_type')
            if not action_type:
                logger.warning(f"Request {i+1}: Missing 'action_type' field, skipping")
                continue
            
            if action_type not in ('create_campaign', 'create_session', 'create_character'):
                logger.warning(f"Request {i+1}: Invalid action_type '{action_type}', skipping")
                continue
            
            data = request.get('data')
            if not data or not isinstance(data, dict):
                logger.warning(f"Request {i+1}: Missing or invalid 'data' field, skipping")
                continue
            
            # Apply defaults for missing required fields (instead of skipping)
            if action_type == 'create_campaign':
                if not data.get('name'):
                    logger.info(f"Request {i+1}: Campaign creation missing 'name' field, using default 'New Campaign'")
                    data['name'] = 'New Campaign'
            elif action_type == 'create_session':
                if not data.get('name'):
                    logger.info(f"Request {i+1}: Session creation missing 'name' field, using default 'New Session'")
                    data['name'] = 'New Session'
            elif action_type == 'create_character':
                if not data.get('name'):
                    logger.info(f"Request {i+1}: Character creation missing 'name' field, using default 'New Character'")
                    data['name'] = 'New Character'
                # Ensure max_hp exists and is valid integer (default to 100 if missing)
                if 'max_hp' not in data:
                    logger.info(f"Request {i+1}: Character creation missing 'max_hp' field, using default 100")
                    data['max_hp'] = 100
                else:
                    try:
                        data['max_hp'] = int(data['max_hp'])
                        if data['max_hp'] <= 0:
                            logger.info(f"Request {i+1}: Character creation has invalid 'max_hp' value ({data['max_hp']}), using default 100")
                            data['max_hp'] = 100
                    except (ValueError, TypeError):
                        logger.info(f"Request {i+1}: Character creation has invalid 'max_hp' value, using default 100")
                        data['max_hp'] = 100
            
            validated_requests.append({
                'action_type': action_type,
                'data': data,
                'transcript_segment': request.get('transcript_segment', '')
            })
            logger.info(f"✓ Validated request {len(validated_requests)}: {action_type} - {data.get('name', 'Unknown')}")
        
        logger.info(f"Analysis complete: {len(validated_requests)} valid creation request(s) extracted from {len(creation_requests)} raw requests")
        logger.info("=" * 60)
        return validated_requests
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response text (first 500 chars): {response_text[:500]}")
        # Return empty list on JSON parse error (non-blocking)
        logger.warning("Returning empty list due to JSON parsing error")
        return []
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        logger.error(f"Analysis failed: {error_detail}")
        # Return empty list on error (non-blocking for chat response)
        logger.warning("Returning empty list due to analysis error")
        return []

