import os
import json
import asyncio
import logging
import re
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai
from .event_types import get_registered_events, get_event_type_by_name

# Ensure .env is loaded
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


def _clean_json_response(json_text: str) -> str:
    """
    Remove trailing commas from JSON string to make it valid JSON.
    
    Gemini API sometimes returns JSON with trailing commas (e.g., {"key": "value",}),
    which Python's json.loads() cannot parse. This function removes such trailing commas.
    
    Args:
        json_text: JSON string that may contain trailing commas
        
    Returns:
        Cleaned JSON string without trailing commas
    """
    # Remove trailing commas before closing braces: ,} -> }
    json_text = re.sub(r',(\s*})', r'\1', json_text)
    # Remove trailing commas before closing brackets: ,] -> ]
    json_text = re.sub(r',(\s*])', r'\1', json_text)
    return json_text


async def analyze_transcript(
    transcript: str,
    characters: List[Dict[str, Any]],
    combat_context: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Analyze transcript for events using Google Gemini API.
    Uses registered event types to dynamically build the prompt and validate results.
    
    Args:
        transcript: The transcript text to analyze (should be corrected transcript)
        characters: List of characters in the session with their names and IDs
        combat_context: Optional combat context with current turn and active characters.
                       When provided, includes combat context in the prompt to help disambiguate
                       character references and improve analysis accuracy.
    
    Returns:
        List of events with character_id, amount, type, and transcript_segment
    """
    logger.info("=" * 60)
    logger.info("Starting transcript analysis with Gemini")
    logger.info(f"Transcript length: {len(transcript)} characters")
    logger.info(f"Number of characters in session: {len(characters)}")
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        logger.error("GEMINI_API_KEY is not configured")
        raise ValueError('GEMINI_API_KEY is not configured')
    
    # Configure Gemini
    genai.configure(api_key=gemini_api_key)
    logger.info("Gemini API configured successfully")
    
    # Get registered event types
    registered_events = get_registered_events()
    logger.info(f"Found {len(registered_events)} registered event type(s): {', '.join(registered_events.keys())}")
    
    # Build character context for the prompt
    character_list = "\n".join([
        f"- {char['name']} (ID: {char['id']})"
        for char in characters
    ])
    logger.info(f"Characters to analyze for: {', '.join([char['name'] for char in characters])}")
    
    # Build combat context section for prompt
    combat_context_section = ""
    if combat_context and combat_context.get('is_combat_active'):
        current_turn_name = combat_context.get('current_turn_character_name')
        active_chars = combat_context.get('active_characters', [])
        
        combat_context_section = f"""

COMBAT CONTEXT:
- Combat is currently active
- Current turn: {current_turn_name or 'None'}
- Active characters in turn order:
"""
        for char in active_chars:
            combat_context_section += f"  - {char['name']} (ID: {char['id']}, turn order: {char['turn_order']})\n"
        
        combat_context_section += """
NOTE: When analyzing the transcript, use this combat context to help disambiguate character references:
- References like "I", "my", "me" likely refer to the current turn character
- Character names mentioned in the context of turn order are more likely to be accurate
- Consider the turn order when determining which character is acting
"""
        logger.info(f"Combat context included - Current turn: {current_turn_name or 'None'}, Active characters: {len(active_chars)}")
    else:
        combat_context_section = "\nCOMBAT CONTEXT:\n- Combat is not currently active\n"
        logger.info("Combat context: not active")
    
    # Phase 3: Safety check for [ALREADY_ANALYZED] marker
    MARKER = '[ALREADY_ANALYZED]'
    marker_instruction = ""
    if MARKER in transcript:
        logger.warning(f"⚠️  Safety check: Found {MARKER} marker in transcript (should have been removed in analyze.py)")
        marker_instruction = f"""
IMPORTANT: The transcript below contains a {MARKER} marker. 
- Ignore any events found in text BEFORE the {MARKER} marker
- Only extract events from text AFTER the {MARKER} marker
- The marker indicates that text before it has already been analyzed and should not be processed again

"""
    
    # Build prompt instructions from all registered event types
    event_instructions = []
    event_schemas = []
    
    for event_name, event_type in registered_events.items():
        event_instructions.append(event_type.get_prompt_instructions())
        schema = event_type.get_schema()
        # Build schema description for prompt
        schema_desc = f"{event_name.upper()} event schema: " + ", ".join([
            f"{k}: {v.__name__ if hasattr(v, '__name__') else str(v)}"
            for k, v in schema.items()
        ])
        event_schemas.append(schema_desc)
    
    # Create a detailed prompt for Gemini using registered event types
    prompt = f"""You are analyzing a D&D (Dungeons & Dragons) game transcript to identify game events.

Available characters in this session:
{character_list}
{combat_context_section}
{marker_instruction}{chr(10).join(event_instructions)}

Analyze the following transcript and extract all relevant events. For each event, identify:
1. Which character was affected (match the character name from the list above)
2. The event type (must match one of the registered types)
3. All required fields for that event type
4. The specific segment of text that describes the event

Event schemas:
{chr(10).join(event_schemas)}

Transcript:
{transcript}

Return a JSON array of events. Each event must include:
- "type": The event type name in lowercase (one of: {', '.join(registered_events.keys())}) - MUST be lowercase, e.g., "turn_advance", "spell_cast", "initiative_roll"
- "character_id": <integer ID from the character list>
- "character_name": "<exact name from character list>"
- All other required fields for that event type
- "transcript_segment": "<the exact text segment that describes this event>"

Only include events where you can clearly identify:
- A character name that matches one from the list
- A valid event type from the registered types
- All required fields for that event type

If no events are found, return an empty array: []

Return ONLY valid JSON, no additional text or explanation."""

    try:
        # Use Gemini Pro model
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        logger.info("Initialized Gemini Pro model")
        logger.info(f"Sending prompt to Gemini (prompt length: {len(prompt)} characters)")
        
        # Run synchronous Gemini API call in thread pool to avoid blocking
        def generate_sync():
            logger.info("Calling Gemini API...")
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
        
        # Clean JSON response (remove trailing commas that Gemini sometimes includes)
        original_length = len(response_text)
        response_text = _clean_json_response(response_text)
        if len(response_text) != original_length:
            logger.debug("Cleaned trailing commas from JSON response")
        
        # Parse JSON response
        logger.info("Parsing JSON response from Gemini")
        events = json.loads(response_text)
        logger.info(f"Parsed {len(events)} raw events from Gemini response")
        
        # Validate and clean up events using registered event types
        validated_events = []
        for i, event in enumerate(events):
            if not isinstance(event, dict):
                logger.warning(f"Event {i+1}: Not a dictionary, skipping")
                continue
            
            # Get event type
            event_type_name = event.get('type')
            if not event_type_name:
                logger.warning(f"Event {i+1}: Missing 'type' field, skipping")
                continue
            
            # Get the event type handler
            event_type = get_event_type_by_name(event_type_name)
            if not event_type:
                logger.warning(f"Event {i+1}: Unknown event type '{event_type_name}', skipping")
                continue
            
            # Validate using the event type's validate method
            if not event_type.validate(event):
                logger.warning(f"Event {i+1}: Validation failed for type '{event_type_name}', skipping")
                continue
            
            validated_events.append(event)
            logger.info(f"✓ Validated event {len(validated_events)}: {event_type_name} {event.get('amount', 'N/A')} to character {event.get('character_id', 'N/A')}")
        
        logger.info(f"Analysis complete: {len(validated_events)} valid events extracted from {len(events)} raw events")
        logger.info("=" * 60)
        return validated_events
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response text (first 500 chars): {response_text[:500]}")
        raise Exception(f'Failed to parse analysis response: {str(e)}')
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        logger.error(f"Analysis failed: {error_detail}")
        raise Exception(f'Analysis failed: {error_detail}')

