# mode_analysis_service.py
import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai

# Ensure .env is loaded
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

# API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Model configuration
GEMINI_MODEL = "models/gemini-2.5-flash"

# Event type order: campaign -> character -> session
EVENT_TYPE_ORDER = ["campaign", "character", "session"]


async def detect_creation_intent(
    transcript: str,
    user_context: Dict[str, Any]
) -> List[str]:
    """
    Detect which event types (campaign/character/session) are requested in the transcript.
    Returns ordered list of event types (campaign -> character -> session).
    
    Args:
        transcript: The transcript text to analyze
        user_context: Dictionary containing user's existing campaigns, sessions, and characters
    
    Returns:
        Ordered list of event type strings (e.g., ["campaign", "character"])
    """
    logger.info("=" * 60)
    logger.info("Starting creation intent detection")
    logger.info(f"Transcript length: {len(transcript)} characters")
    
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
            for camp in user_context["campaigns"][:20]
        ])
    
    sessions_list = ""
    if user_context.get("sessions"):
        sessions_list = "\n".join([
            f"- {session['name']} (ID: {session['id']})"
            for session in user_context["sessions"][:20]
        ])
    
    characters_list = ""
    if user_context.get("characters"):
        characters_list = "\n".join([
            f"- {char['name']} (ID: {char['id']})"
            for char in user_context["characters"][:30]
        ])
    
    # Build the prompt for intent detection
    prompt = f"""You are analyzing a D&D (Dungeons & Dragons) voice assistant transcript to detect requests to CREATE campaigns, sessions, or characters.

EXISTING USER DATA (for reference - do not create duplicates):
{f"Campaigns:{chr(10)}{campaigns_list}" if campaigns_list else "Campaigns: None"}
{f"Sessions:{chr(10)}{sessions_list}" if sessions_list else "Sessions: None"}
{f"Characters:{chr(10)}{characters_list}" if characters_list else "Characters: None"}

Analyze the following transcript and identify which types of objects the user wants to CREATE.

CREATION REQUEST TYPES:

1. CREATE CAMPAIGN:
   - Example phrases: "create a campaign called X", "new campaign named X", "make a campaign X"

2. CREATE SESSION:
   - Example phrases: "create a session", "new session called X", "start a session for campaign Y"

3. CREATE CHARACTER:
   - Example phrases: "create a character named X", "new character called X", "make a character"

IMPORTANT RULES:
- Only detect creation requests where the user is explicitly asking to CREATE something
- Do NOT detect informational queries like "tell me about my campaigns" or "show me characters"
- Return ONLY the event types detected, in priority order: campaign -> character -> session
- If multiple types are detected, return them in that order

Transcript:
{transcript}

Return a JSON array of event type strings. Valid values are: "campaign", "character", "session".
Return them in priority order: campaign first, then character, then session.

Example responses:
- ["campaign"] - User wants to create a campaign
- ["character", "session"] - User wants to create a character and a session (character first)
- [] - No creation intent detected

Return ONLY valid JSON array, no additional text or explanation."""

    try:
        # Use Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info("Initialized Gemini model for intent detection")
        logger.info(f"Sending prompt to Gemini (prompt length: {len(prompt)} characters)")
        
        # Run synchronous Gemini API call in thread pool to avoid blocking
        def generate_sync():
            logger.info("Calling Gemini API for intent detection...")
            return model.generate_content(prompt)
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, generate_sync)
        
        logger.info("Received response from Gemini API ")
        
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
        detected_types = json.loads(response_text)
        
        if not isinstance(detected_types, list):
            logger.warning(f"Gemini returned non-list response, converting to list: {type(detected_types)}")
            detected_types = [detected_types] if detected_types else []
        
        # Validate and filter event types
        valid_types = []
        for event_type in detected_types:
            if event_type in EVENT_TYPE_ORDER:
                valid_types.append(event_type)
            else:
                logger.warning(f"Invalid event type detected: {event_type}, skipping")
        
        # Order by priority: campaign -> character -> session
        ordered_types = []
        for priority_type in EVENT_TYPE_ORDER:
            if priority_type in valid_types:
                ordered_types.append(priority_type)
        
        logger.info(f"Intent detection complete: {len(ordered_types)} event type(s) detected: {ordered_types}")
        logger.info("=" * 60)
        return ordered_types
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response text (first 500 chars): {response_text[:500]}")
        logger.warning("Returning empty list due to JSON parsing error")
        return []
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        logger.error(f"Intent detection failed: {error_detail}")
        logger.warning("Returning empty list due to analysis error")
        return []


async def analyze_in_mode(
    mode: str,
    transcript: str,
    user_context: Dict[str, Any],
    current_event_data: Optional[Dict[str, Any]] = None,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Dict[str, Any]:
    """
    Analyze transcript in a specific MODE to extract information for object creation.
    
    Args:
        mode: Current MODE ("campaign_creation", "character_creation", or "session_creation")
        transcript: Current user message
        user_context: Dictionary containing user's existing campaigns, sessions, and characters
        current_event_data: Previously accumulated data for this MODE
        conversation_history: List of conversation messages with 'role' and 'content' keys (for context)
    
    Returns:
        Dictionary with extracted data for the current MODE
    """
    logger.info("=" * 60)
    logger.info(f"Starting MODE-specific analysis for mode: {mode}")
    logger.info(f"Transcript length: {len(transcript)} characters")
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured")
        raise ValueError('GEMINI_API_KEY is not configured')
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured successfully")
    
    # Build context sections
    campaigns_list = ""
    if user_context.get("campaigns"):
        campaigns_list = "\n".join([
            f"- {camp['name']} (ID: {camp['id']})"
            for camp in user_context["campaigns"][:20]
        ])
    
    sessions_list = ""
    if user_context.get("sessions"):
        sessions_list = "\n".join([
            f"- {session['name']} (ID: {session['id']})"
            for session in user_context["sessions"][:20]
        ])
    
    characters_list = ""
    if user_context.get("characters"):
        characters_list = "\n".join([
            f"- {char['name']} (ID: {char['id']})"
            for char in user_context["characters"][:30]
        ])
    
    # Build MODE-specific prompt
    if mode == "campaign_creation":
        mode_prompt = build_campaign_creation_prompt(campaigns_list, current_event_data, conversation_history)
    elif mode == "character_creation":
        mode_prompt = build_character_creation_prompt(characters_list, campaigns_list, current_event_data, conversation_history)
    elif mode == "session_creation":
        mode_prompt = build_session_creation_prompt(sessions_list, campaigns_list, characters_list, current_event_data, conversation_history)
    else:
        logger.error(f"Unknown mode: {mode}")
        raise ValueError(f"Unknown mode: {mode}")
    
    # Combine with current transcript
    full_prompt = f"""{mode_prompt}

CURRENT USER MESSAGE:
{transcript}

Return ONLY valid JSON, no additional text or explanation."""
    
    try:
        # Use Gemini model
        model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info("Initialized Gemini model for MODE analysis")
        logger.info(f"Sending prompt to Gemini (prompt length: {len(full_prompt)} characters)")
        
        # Run synchronous Gemini API call in thread pool
        def generate_sync():
            logger.info("Calling Gemini API for MODE analysis...")
            return model.generate_content(full_prompt)
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, generate_sync)
        
        logger.info("Received response from Gemini API {response.text}")
        
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
        logger.info("Parsing JSON response from Gemini ")
        extracted_data = json.loads(response_text)
        
        if not isinstance(extracted_data, dict):
            logger.warning(f"Gemini returned non-dict response, using empty dict: {type(extracted_data)}")
            extracted_data = {}
        
        # Merge with current_event_data if provided
        if current_event_data:
            merged_data = {**current_event_data, **extracted_data}
            logger.info(f"Merged with existing data: {len(merged_data)} fields")
        else:
            merged_data = extracted_data
        
        logger.info(f"MODE analysis complete: extracted {len(merged_data)} field(s)")
        logger.info("=" * 60)
        return merged_data
    
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response text (first 500 chars): {response_text[:500]}")
        # Return current_event_data on error
        return current_event_data or {}
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        logger.error(f"MODE analysis failed: {error_detail}")
        # Return current_event_data on error
        return current_event_data or {}


def build_campaign_creation_prompt(
    campaigns_list: str,
    current_event_data: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]]
) -> str:
    """Build prompt for campaign creation MODE."""
    existing_data_section = ""
    if current_event_data:
        existing_data_section = f"""
EXISTING DATA (already collected):
{json.dumps(current_event_data, indent=2)}

Merge new information with existing data. Do not overwrite existing fields unless the user explicitly changes them."""
    
    conversation_history_section = ""
    if conversation_history:
        # Format conversation history as readable transcript
        history_lines = []
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            # Capitalize role for display
            role_display = role.capitalize() if role == 'user' else 'Assistant'
            history_lines.append(f"{role_display}: {content}")
        
        if history_lines:
            conversation_history_section = f"""
CONVERSATION HISTORY:
{chr(10).join(history_lines)}
"""
    
    return f"""You are in CAMPAIGN CREATION MODE. The user is creating a new D&D campaign.

EXISTING CAMPAIGNS (for reference - do not create duplicates):
{campaigns_list if campaigns_list else "None"}
{conversation_history_section}
{existing_data_section}

Extract information from the user's message about the campaign they want to create.

CAMPAIGN FIELDS:
- name (string, REQUIRED): Campaign name
- description (string, OPTIONAL): Campaign description

Analyze the user's message and extract any campaign information. Return a JSON object with the fields you can extract.

Example response:
{{
  "name": "Lost Mines of Phandelver",
  "description": "A classic D&D adventure"
}}

If a field is not mentioned in the current message, omit it from the response (it will be merged with existing data)."""


def build_character_creation_prompt(
    characters_list: str,
    campaigns_list: str,
    current_event_data: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]]
) -> str:
    """Build prompt for character creation MODE."""
    existing_data_section = ""
    if current_event_data:
        existing_data_section = f"""
EXISTING DATA (already collected):
{json.dumps(current_event_data, indent=2)}

Merge new information with existing data. Do not overwrite existing fields unless the user explicitly changes them."""
    
    conversation_history_section = ""
    if conversation_history:
        # Format conversation history as readable transcript
        history_lines = []
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            # Capitalize role for display
            role_display = role.capitalize() if role == 'user' else 'Assistant'
            history_lines.append(f"{role_display}: {content}")
        
        if history_lines:
            conversation_history_section = f"""
CONVERSATION HISTORY:
{chr(10).join(history_lines)}
"""
    
    return f"""You are in CHARACTER CREATION MODE. The user is creating a new D&D character.

EXISTING CHARACTERS (for reference - do not create duplicates):
{characters_list if characters_list else "None"}

EXISTING CAMPAIGNS (for reference - campaign_id must match existing campaign):
{campaigns_list if campaigns_list else "None"}
{conversation_history_section}
{existing_data_section}

Extract information from the user's message about the character they want to create.

CHARACTER FIELDS:
- name (string, REQUIRED): Character name
- max_hp (integer, REQUIRED): Maximum hit points
- campaign_id (string, OPTIONAL): ID of existing campaign (must match from list above)
- race (string, OPTIONAL): Character race
- class_name (string, OPTIONAL): Character class
- level (integer, OPTIONAL): Character level
- ac (integer, OPTIONAL): Armor class
- initiative_bonus (integer, OPTIONAL): Initiative bonus
- background (string, OPTIONAL): Character background
- alignment (string, OPTIONAL): Character alignment
- notes (string, OPTIONAL): Additional notes
- strength_base, dexterity_base, constitution_base, intelligence_base, wisdom_base, charisma_base (integer, OPTIONAL): Base ability scores
- strength_bonus, dexterity_bonus, constitution_bonus, intelligence_bonus, wisdom_bonus, charisma_bonus (integer, OPTIONAL): Ability score bonuses

Analyze the user's message and extract any character information. Return a JSON object with the fields you can extract.

Example response:
{{
  "name": "Aragorn",
  "max_hp": 50,
  "race": "Human",
  "class_name": "Ranger",
  "level": 5
}}

If a field is not mentioned in the current message, omit it from the response (it will be merged with existing data)."""


def build_session_creation_prompt(
    sessions_list: str,
    campaigns_list: str,
    characters_list: str,
    current_event_data: Optional[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]]
) -> str:
    """Build prompt for session creation MODE."""
    existing_data_section = ""
    if current_event_data:
        existing_data_section = f"""
EXISTING DATA (already collected):
{json.dumps(current_event_data, indent=2)}

Merge new information with existing data. Do not overwrite existing fields unless the user explicitly changes them."""
    
    conversation_history_section = ""
    if conversation_history:
        # Format conversation history as readable transcript
        history_lines = []
        for msg in conversation_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            # Capitalize role for display
            role_display = role.capitalize() if role == 'user' else 'Assistant'
            history_lines.append(f"{role_display}: {content}")
        
        if history_lines:
            conversation_history_section = f"""
CONVERSATION HISTORY:
{chr(10).join(history_lines)}
"""
    
    return f"""You are in SESSION CREATION MODE. The user is creating a new D&D session.

EXISTING SESSIONS (for reference - do not create duplicates):
{sessions_list if sessions_list else "None"}

EXISTING CAMPAIGNS (for reference - campaign_id must match existing campaign):
{campaigns_list if campaigns_list else "None"}

EXISTING CHARACTERS (for reference - character_ids must match existing characters):
{characters_list if characters_list else "None"}
{conversation_history_section}
{existing_data_section}

Extract information from the user's message about the session they want to create.

SESSION FIELDS:
- name (string, REQUIRED): Session name
- campaign_id (string, OPTIONAL): ID of existing campaign (must match from list above)
- character_ids (array of strings, OPTIONAL): IDs of existing characters to include (must match from list above)

Analyze the user's message and extract any session information. Return a JSON object with the fields you can extract.

Example response:
{{
  "name": "Session 1: The Adventure Begins",
  "campaign_id": "abc123",
  "character_ids": ["char1", "char2"]
}}

If a field is not mentioned in the current message, omit it from the response (it will be merged with existing data)."""


def check_exit_skip(transcript: str) -> Tuple[bool, Optional[str]]:
    """
    Check if user message contains EXIT or SKIP command.
    
    Args:
        transcript: User message text
    
    Returns:
        Tuple of (found_command, command_type) where command_type is "exit" or "skip" or None
    """
    transcript_lower = transcript.lower().strip()
    
    # Check for EXIT commands
    exit_patterns = ["exit", "go back", "back to general", "cancel", "abort"]
    for pattern in exit_patterns:
        if pattern in transcript_lower:
            logger.info(f"EXIT command detected: '{pattern}' in transcript")
            return True, "exit"
    
    # Check for SKIP commands
    skip_patterns = ["skip", "next", "move on", "skip this"]
    for pattern in skip_patterns:
        if pattern in transcript_lower:
            logger.info(f"SKIP command detected: '{pattern}' in transcript")
            return True, "skip"
    
    return False, None


def is_creation_complete(mode: str, event_data: Dict[str, Any]) -> bool:
    """
    Check if creation is complete based on MODE and collected data.
    
    Args:
        mode: Current MODE ("campaign_creation", "character_creation", or "session_creation")
        event_data: Collected data for the current MODE
    
    Returns:
        True if creation is complete (all required fields present), False otherwise
    """
    if mode == "campaign_creation":
        return "name" in event_data and event_data.get("name")
    elif mode == "character_creation":
        return "name" in event_data and event_data.get("name") and "max_hp" in event_data and event_data.get("max_hp")
    elif mode == "session_creation":
        return "name" in event_data and event_data.get("name")
    else:
        return False


def get_required_fields(mode: str) -> List[str]:
    """
    Get list of required fields for a MODE.
    
    Args:
        mode: Current MODE ("campaign_creation", "character_creation", or "session_creation")
    
    Returns:
        List of required field names
    """
    if mode == "campaign_creation":
        return ["name"]
    elif mode == "character_creation":
        return ["name", "max_hp"]
    elif mode == "session_creation":
        return ["name"]
    else:
        return []


async def generate_mode_response(
    mode: str,
    current_event_data: Dict[str, Any],
    system_prompt: str,
    conversation_history: Optional[List[Dict[str, str]]],
    user_id: str
) -> str:
    """
    Generate a MODE-specific response using Gemini to ask for missing required fields.
    
    Args:
        mode: Current MODE ("campaign_creation", "character_creation", or "session_creation")
        current_event_data: Currently collected data for this MODE
        system_prompt: Base system prompt for context
        conversation_history: Previous conversation messages
        user_id: User ID for logging
    
    Returns:
        Generated response text asking for missing fields
    """
    logger.info(f"Generating MODE-specific response for mode: {mode}")
    
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not configured")
        raise ValueError('GEMINI_API_KEY is not configured')
    
    # Configure Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    
    # Get required fields and determine what's missing
    required_fields = get_required_fields(mode)
    missing_fields = [field for field in required_fields if field not in current_event_data or not current_event_data.get(field)]
    
    # Build context about what we have and what we need
    collected_data = json.dumps(current_event_data, indent=2) if current_event_data else "None"
    
    # Build conversation history section
    conversation_history_section = ""
    if conversation_history:
        history_lines = []
        for msg in conversation_history[-5:]:  # Last 5 messages for context
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            role_display = "User" if role == "user" else "Assistant"
            history_lines.append(f"{role_display}: {content}")
        
        if history_lines:
            conversation_history_section = f"""
CONVERSATION HISTORY:
{chr(10).join(history_lines)}
"""
    
    # Build mode-specific prompt
    mode_name = mode.replace("_creation", "").replace("_", " ").title()
    
    prompt = f"""You are helping the user create a {mode_name} in a D&D (Dungeons & Dragons) game.

CURRENTLY COLLECTED DATA:
{collected_data}

REQUIRED FIELDS: {', '.join(required_fields)}
MISSING REQUIRED FIELDS: {', '.join(missing_fields) if missing_fields else 'None - all required fields collected'}

{conversation_history_section}

Generate a friendly, conversational response to help the user provide the missing information. 
- Ask naturally about what's missing (e.g., "What's the character's name?", "What should we call this campaign?")
- Be concise and helpful
- If we have some data already, acknowledge it naturally
- Keep it under 200 characters
- Use natural spoken language (this will be converted to speech)

Generate ONLY the response text, no additional explanation or formatting."""

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info("Initialized Gemini model for MODE response generation")
        
        # Run synchronous Gemini API call in thread pool
        def generate_sync():
            logger.info("Calling Gemini API for MODE response generation...")
            return model.generate_content(prompt)
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, generate_sync)
        
        response_text = response.text.strip()
        logger.info(f"MODE response generation complete ({len(response_text)} characters)")
        return response_text
    
    except Exception as e:
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        logger.error(f"MODE response generation failed: {error_detail}")
        # Fallback response
        if missing_fields:
            field_name = missing_fields[0].replace("_", " ")
            return f"What's the {field_name}?"
        return "What information would you like to provide?"


def generate_completion_confirmation(
    mode: str,
    created_item: Dict[str, Any]
) -> str:
    """
    Generate a completion confirmation message when a MODE creation finishes.
    
    Args:
        mode: The MODE that just completed ("campaign_creation", "character_creation", or "session_creation")
        created_item: The created item dictionary with 'name' and other fields
    
    Returns:
        Confirmation message string
    """
    item_type = mode.replace("_creation", "")
    item_name = created_item.get('name', 'item')
    
    if mode == "campaign_creation":
        return f"Campaign created successfully: {item_name}"
    elif mode == "character_creation":
        return f"Character created successfully: {item_name}"
    elif mode == "session_creation":
        return f"Session created successfully: {item_name}"
    else:
        return f"{item_type.title()} created successfully: {item_name}"

