import os
import asyncio
import logging
import time
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import google.generativeai as genai

# Ensure .env is loaded
load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)


async def correct_transcript(
    transcript: str,
    characters: List[Dict[str, Any]],
    combat_context: Dict[str, Any] = None
) -> str:
    """
    Correct transcription errors in a transcript using combat context and D&D knowledge.
    
    Uses Gemini API to fix common transcription errors including:
    - Character name disambiguation
    - Turn context awareness
    - D&D spell name corrections
    - Ability name corrections
    - Game term corrections
    - Filtering off-topic content
    
    Args:
        transcript: The original transcript text to correct
        characters: List of characters in the session with their names and IDs
        combat_context: Optional combat context with current turn and active characters
    
    Returns:
        Corrected transcript string
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("🔧 TRANSCRIPT CORRECTION - Starting")
    logger.info(f"   Original transcript length: {len(transcript)} characters")
    logger.info(f"   Original transcript word count: {len(transcript.split())} words")
    logger.debug(f"   Original transcript (full): {transcript}")
    
    if not transcript or not transcript.strip():
        logger.warning("   ⚠️  Empty transcript received, returning as-is")
        return transcript
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        logger.error("   ❌ GEMINI_API_KEY is not configured")
        raise ValueError('GEMINI_API_KEY is not configured')
    
    # Configure Gemini
    logger.info("   ⚙️  Configuring Gemini API...")
    genai.configure(api_key=gemini_api_key)
    logger.info("   ✓ Gemini API configured successfully")
    
    # Build character context for the prompt
    logger.info("   📋 Building character context...")
    character_names = [char['name'] for char in characters]
    character_list = "\n".join([
        f"- {char['name']} (ID: {char['id']})"
        for char in characters
    ])
    logger.info(f"   ✓ Found {len(characters)} character(s) in session:")
    for char in characters:
        logger.info(f"      - {char['name']} (ID: {char['id']})")
    
    # Build combat context section for prompt
    logger.info("   ⚔️  Building combat context...")
    combat_context_section = ""
    if combat_context and combat_context.get('is_combat_active'):
        current_turn_name = combat_context.get('current_turn_character_name')
        current_turn_id = combat_context.get('current_turn_character_id')
        active_chars = combat_context.get('active_characters', [])
        
        combat_context_section = f"""
COMBAT CONTEXT:
- Combat is currently active
- Current turn: {current_turn_name or 'None'}
- Active characters in turn order:
"""
        for char in active_chars:
            combat_context_section += f"  - {char['name']} (turn order: {char['turn_order']})\n"
        
        logger.info(f"   ✓ Combat is ACTIVE")
        logger.info(f"      Current turn: {current_turn_name or 'None'} (ID: {current_turn_id or 'None'})")
        logger.info(f"      Active characters in initiative order ({len(active_chars)} total):")
        for char in active_chars:
            marker = " ← CURRENT" if char['id'] == current_turn_id else ""
            logger.info(f"         {char['turn_order']}. {char['name']} (ID: {char['id']}){marker}")
    else:
        combat_context_section = "\nCOMBAT CONTEXT:\n- Combat is not currently active\n"
        logger.info("   ✓ Combat is NOT active (no combat context available)")
    
    # Build prompt for transcript correction
    logger.info("   📝 Building correction prompt...")
    prompt = f"""You are correcting a D&D (Dungeons & Dragons) game transcript that was generated from speech-to-text transcription. 
The transcript may contain errors due to:
- Misheard character names
- Misheard spell names
- Misheard ability names
- Misheard game terminology
- Off-topic conversational content

Your task is to correct the transcript while preserving the original meaning and game-relevant content.

AVAILABLE CHARACTERS IN THIS SESSION:
{character_list}
{combat_context_section}

CORRECTION GUIDELINES:

1. CHARACTER NAME DISAMBIGUATION:
   - Use the exact character names from the list above
   - If a name sounds similar to a character name, correct it to the matching character
   - Examples: "Gandalf" → "Gandalf", "Aragorn" → "Aragorn" (if they're in the list)
   - If combat is active, prioritize names from the active characters list

2. TURN CONTEXT AWARENESS:
   - If combat is active and a character name is mentioned, consider the current turn character
   - References like "I", "my", "me" likely refer to the current turn character
   - Use this context to help disambiguate character references

3. D&D SPELL NAME CORRECTIONS:
   - Correct common D&D spell names to their proper forms
   - Examples: "fireball" → "Fireball", "cure wounds" → "Cure Wounds", "magic missile" → "Magic Missile"
   - Common spells: Fireball, Cure Wounds, Magic Missile, Shield, Counterspell, Healing Word, 
     Bless, Bane, Haste, Slow, Dispel Magic, Counterspell, Revivify, Raise Dead, etc.

4. ABILITY NAME CORRECTIONS:
   - Correct common class abilities to their proper forms
   - Examples: "second wind" → "Second Wind", "action surge" → "Action Surge", "sneak attack" → "Sneak Attack"
   - Common abilities: Second Wind, Action Surge, Sneak Attack, Rage, Wild Shape, Lay on Hands, etc.

5. GAME TERM CORRECTIONS:
   - AC (Armor Class)
   - HP (Hit Points)
   - Saving throws (Dexterity, Constitution, Wisdom, etc.)
   - Damage types (fire, cold, lightning, poison, necrotic, radiant, etc.)
   - Conditions (prone, stunned, paralyzed, etc.)
   - Dice notation (d20, d6, etc.)

6. FILTER OFF-TOPIC CONTENT:
   - Remove conversational content that is clearly not about the game
   - Examples: "um", "uh", excessive filler words, unrelated side conversations
   - Keep game-relevant content even if it's casual
   - Preserve the flow and meaning of game actions

7. PRESERVE ORIGINAL STRUCTURE:
   - Keep the original sentence structure and flow
   - Only correct errors, don't rewrite or paraphrase
   - Maintain the natural speaking style
   - Keep numbers and quantities as spoken (e.g., "five damage" stays as "five damage")

ORIGINAL TRANSCRIPT:
{transcript}

Return ONLY the corrected transcript text. Do not include any explanations, comments, or additional text. 
Return the corrected transcript exactly as it should be used for game event analysis."""

    try:
        # Use Gemini Pro model (same as analysis)
        logger.info("   🤖 Initializing Gemini model...")
        model = genai.GenerativeModel('models/gemini-2.5-flash')
        logger.info("   ✓ Model initialized: gemini-2.5-flash")
        
        # Log prompt statistics
        prompt_words = len(prompt.split())
        prompt_lines = len(prompt.split('\n'))
        logger.info(f"   📊 Prompt statistics:")
        logger.info(f"      - Total length: {len(prompt)} characters")
        logger.info(f"      - Word count: {prompt_words} words")
        logger.info(f"      - Line count: {prompt_lines} lines")
        logger.info(f"      - Transcript portion: {len(transcript)} characters")
        logger.debug(f"   📄 Full prompt (first 500 chars): {prompt[:500]}...")
        
        # Run synchronous Gemini API call in thread pool to avoid blocking
        api_start_time = time.time()
        logger.info("   🚀 Sending correction request to Gemini API...")
        
        def generate_sync():
            logger.debug("      [Thread] Executing Gemini API call...")
            return model.generate_content(prompt)
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            response = await loop.run_in_executor(executor, generate_sync)
        
        api_duration = time.time() - api_start_time
        logger.info(f"   ✓ Received response from Gemini API (took {api_duration:.2f}s)")
        
        # Extract corrected transcript from response
        logger.info("   🔍 Processing Gemini response...")
        corrected_transcript = response.text.strip()
        
        # Log response metadata if available
        if hasattr(response, 'usage_metadata'):
            usage = response.usage_metadata
            logger.info(f"   📈 API usage metadata:")
            if hasattr(usage, 'prompt_token_count'):
                logger.info(f"      - Prompt tokens: {usage.prompt_token_count}")
            if hasattr(usage, 'candidates_token_count'):
                logger.info(f"      - Response tokens: {usage.candidates_token_count}")
            if hasattr(usage, 'total_token_count'):
                logger.info(f"      - Total tokens: {usage.total_token_count}")
        
        logger.info(f"   ✓ Corrected transcript length: {len(corrected_transcript)} characters")
        logger.info(f"   ✓ Corrected transcript word count: {len(corrected_transcript.split())} words")
        logger.debug(f"   📄 Corrected transcript (full): {corrected_transcript}")
        
        # Detailed comparison between original and corrected
        logger.info("   🔬 Comparing original vs corrected transcript...")
        if corrected_transcript != transcript:
            logger.info("   ✓ Transcript WAS CORRECTED (differences detected)")
            
            # Calculate differences
            orig_words = transcript.split()
            corr_words = corrected_transcript.split()
            word_diff = len(corr_words) - len(orig_words)
            char_diff = len(corrected_transcript) - len(transcript)
            
            logger.info(f"   📊 Difference statistics:")
            logger.info(f"      - Character difference: {char_diff:+d} ({len(transcript)} → {len(corrected_transcript)})")
            logger.info(f"      - Word difference: {word_diff:+d} ({len(orig_words)} → {len(corr_words)})")
            
            # Show a sample of differences if they're significant
            if abs(char_diff) > 10 or abs(word_diff) > 3:
                logger.info("   🔍 Sample comparison (first 200 chars):")
                logger.info(f"      Original:  {transcript[:200]}...")
                logger.info(f"      Corrected: {corrected_transcript[:200]}...")
            
            # Check for specific types of corrections
            if any(spell in corrected_transcript.lower() for spell in ['fireball', 'cure wounds', 'magic missile', 'shield']):
                logger.info("   ✨ Detected spell name corrections")
            if any(char['name'].lower() in corrected_transcript.lower() for char in characters):
                logger.info("   ✨ Detected character name references")
        else:
            logger.info("   ✓ Transcript UNCHANGED (no corrections needed)")
        
        total_duration = time.time() - start_time
        logger.info(f"   ⏱️  Total correction time: {total_duration:.2f}s")
        logger.info("=" * 60)
        return corrected_transcript
    
    except Exception as e:
        error_duration = time.time() - start_time
        error_detail = str(e)
        if hasattr(e, 'message'):
            error_detail = e.message
        
        logger.error("   ❌ TRANSCRIPT CORRECTION FAILED")
        logger.error(f"      Error: {error_detail}")
        logger.error(f"      Error type: {type(e).__name__}")
        
        # Log additional error details if available
        if hasattr(e, 'response'):
            logger.error(f"      Response status: {getattr(e.response, 'status_code', 'N/A')}")
        
        import traceback
        logger.debug(f"      Full traceback:\n{traceback.format_exc()}")
        
        # If correction fails, return original transcript to avoid breaking the pipeline
        logger.warning(f"   ⚠️  Returning original transcript due to correction failure (took {error_duration:.2f}s)")
        logger.info("=" * 60)
        return transcript

