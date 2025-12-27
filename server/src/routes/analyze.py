from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List
import logging
from ..middleware.auth import authenticate_token
from ..db.database import get_database
from ..services.gemini_service import analyze_transcript
from ..services.transcript_correction_service import correct_transcript
from ..services.event_types import get_event_type_by_name

# Set up logger
logger = logging.getLogger(__name__)


router = APIRouter()


class AnalyzeRequest(BaseModel):
    transcript: str
    session_id: int


def _get_combat_context(db: Any, session_id: int) -> Dict[str, Any]:
    """
    Fetch combat context for a session.
    
    Returns:
        Dictionary with combat context:
        {
            "current_turn_character_id": int | None,
            "current_turn_character_name": str | None,
            "active_characters": [
                {"id": int, "name": str, "turn_order": int}
            ],
            "is_combat_active": bool
        }
    """
    # Get combat state
    combat_state = db.execute(
        'SELECT * FROM combat_state WHERE session_id = ?',
        (session_id,)
    ).fetchone()
    
    is_combat_active = False
    current_turn_character_id = None
    current_turn_character_name = None
    
    if combat_state and combat_state['is_active']:
        is_combat_active = True
        current_turn_character_id = combat_state['current_turn_character_id']
        
        # Get current turn character name if available
        if current_turn_character_id:
            character = db.execute(
                'SELECT name FROM characters WHERE id = ?',
                (current_turn_character_id,)
            ).fetchone()
            if character:
                current_turn_character_name = character['name']
    
    # Get active characters in initiative order
    active_characters = []
    if is_combat_active:
        initiative_rows = db.execute('''
            SELECT 
                io.character_id,
                io.turn_order,
                c.name
            FROM initiative_order io
            JOIN characters c ON io.character_id = c.id
            WHERE io.session_id = ?
            ORDER BY io.turn_order ASC
        ''', (session_id,)).fetchall()
        
        active_characters = [
            {
                "id": row['character_id'],
                "name": row['name'],
                "turn_order": row['turn_order']
            }
            for row in initiative_rows
        ]
    
    return {
        "current_turn_character_id": current_turn_character_id,
        "current_turn_character_name": current_turn_character_name,
        "active_characters": active_characters,
        "is_combat_active": is_combat_active
    }


@router.post('/analyze')
async def analyze(
    request: AnalyzeRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Analyze transcript for damage/healing events."""
    logger.info("=" * 60)
    logger.info(f"📥 Received analyze request from user {user_id}")
    logger.info(f"   Session ID: {request.session_id}")
    logger.info(f"   Transcript length: {len(request.transcript)} characters")
    logger.info(f"   Transcript preview: {request.transcript[:100]}...")
    
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (request.session_id, user_id)
        ).fetchone()
        
        if not session:
            logger.warning(f"Session {request.session_id} not found for user {user_id}")
            raise HTTPException(status_code=404, detail='Session not found')
        
        logger.info(f"✓ Session {request.session_id} verified for user {user_id}")
        
        # Get characters in the session
        characters_rows = db.execute('''
            SELECT 
                c.id,
                c.name,
                sc.starting_hp,
                sc.current_hp
            FROM session_characters sc
            JOIN characters c ON sc.character_id = c.id
            WHERE sc.session_id = ?
        ''', (request.session_id,)).fetchall()
        
        characters = [dict(row) for row in characters_rows]
        
        if not characters:
            logger.warning(f"No characters found in session {request.session_id}")
            raise HTTPException(
                status_code=400,
                detail='No characters found in session. Add characters to the session first.'
            )
        
        logger.info(f"✓ Found {len(characters)} character(s) in session: {', '.join([c['name'] for c in characters])}")
        
        # Phase 1: Check for [ALREADY_ANALYZED] marker and extract portion after marker
        MARKER = '[ALREADY_ANALYZED]'
        transcript_before_marker = ''
        transcript_to_analyze = request.transcript
        
        if MARKER in request.transcript:
            logger.info(f"🔍 Found {MARKER} marker in transcript")
            marker_index = request.transcript.find(MARKER)
            transcript_before_marker = request.transcript[:marker_index].strip()
            transcript_after_marker = request.transcript[marker_index + len(MARKER):].strip()
            transcript_to_analyze = transcript_after_marker
            logger.info(f"   Portion before marker: {len(transcript_before_marker)} chars")
            logger.info(f"   Portion after marker (to analyze): {len(transcript_after_marker)} chars")
        else:
            logger.info("🔍 No marker found in transcript, analyzing full transcript")
        
        # Get combat context for transcript correction and analysis
        combat_context = _get_combat_context(db, request.session_id)
        if combat_context['is_combat_active']:
            logger.info(f"⚔️  Combat is active - Current turn: {combat_context['current_turn_character_name'] or 'None'}, Active characters: {len(combat_context['active_characters'])}")
        else:
            logger.info("⚔️  Combat is not active")
        
        # Correct transcript using combat context and D&D knowledge
        original_transcript = transcript_to_analyze
        logger.info("🔧 Starting transcript correction...")
        logger.info(f"   Input: {len(original_transcript)} chars, {len(original_transcript.split())} words")
        corrected_transcript = await correct_transcript(original_transcript, characters, combat_context)
        
        # Log both transcripts for debugging (full text at debug level)
        logger.debug(f"   Original transcript (full): {original_transcript}")
        logger.debug(f"   Corrected transcript (full): {corrected_transcript}")
        
        # Summary of correction results
        if original_transcript != corrected_transcript:
            char_diff = len(corrected_transcript) - len(original_transcript)
            word_diff = len(corrected_transcript.split()) - len(original_transcript.split())
            logger.info(f"   ✓ Correction complete: {char_diff:+d} chars, {word_diff:+d} words changed")
        else:
            logger.info("   ✓ Correction complete: No changes needed")
        
        # Analyze corrected transcript using Gemini
        logger.info("🚀 Starting Gemini analysis...")
        events = await analyze_transcript(corrected_transcript, characters, combat_context)
        
        # Store transcript_before_marker for Phase 2 (marker insertion)
        # This will be used when constructing the previous_chunk_for_next_analysis
        
        logger.info(f"✅ Analysis complete: {len(events)} event(s) found")
        
        # Phase 2: Cut off at last word of last event's transcript_segment
        previous_chunk_for_next_analysis = ''
        if events:
            # Find the last event by position in the corrected transcript (not array order)
            last_event = None
            last_event_end_pos = -1
            last_event_segment_pos = -1
            
            for event in events:
                transcript_segment = event.get('transcript_segment', '')
                if not transcript_segment:
                    continue
                
                # Find where this segment appears in the corrected transcript
                segment_pos = corrected_transcript.find(transcript_segment)
                if segment_pos == -1:
                    # Segment not found, log warning
                    logger.warning(f"Event transcript_segment not found in corrected transcript: {transcript_segment[:50]}...")
                    continue
                
                # Calculate end position of this segment
                segment_end_pos = segment_pos + len(transcript_segment)
                
                # Track the event that appears latest in the text
                if segment_end_pos > last_event_end_pos:
                    last_event_end_pos = segment_end_pos
                    last_event_segment_pos = segment_pos
                    last_event = event
            
            if last_event and last_event_end_pos >= 0:
                # Get the segment text
                segment_text = corrected_transcript[last_event_segment_pos:last_event_end_pos]
                
                # Find the last word boundary in the segment
                # Work backwards from the end to find where the last word ends
                last_word_end_in_segment = len(segment_text)
                # Skip trailing whitespace
                while last_word_end_in_segment > 0 and segment_text[last_word_end_in_segment - 1].isspace():
                    last_word_end_in_segment -= 1
                
                # Calculate absolute position of the end of the last word
                cutoff_pos = last_event_segment_pos + last_word_end_in_segment
                
                # Previous chunk should contain ONLY text AFTER the cutoff point
                # This is the text that wasn't analyzed yet (comes after the last processed event)
                text_after_cutoff = corrected_transcript[cutoff_pos:].strip()
                
                # If there's no text after cutoff (last event is at the end), return empty string
                # This means the next analysis should only analyze new chunks without old context
                if not text_after_cutoff or len(text_after_cutoff) < 3:
                    # Last event is at the end, no text after it
                    previous_chunk_for_next_analysis = ''
                    logger.info(f"✂️  Last event is at end of transcript, returning empty previous chunk")
                    logger.info(f"   Last event: {last_event.get('type', 'unknown')} - {last_event.get('transcript_segment', '')[:50]}...")
                    logger.info(f"   Cutoff position: {cutoff_pos} (end of transcript: {len(corrected_transcript)})")
                else:
                    # Combine: portion before marker (if exists) + text after cutoff
                    if transcript_before_marker:
                        previous_chunk_for_next_analysis = f"{transcript_before_marker} {text_after_cutoff}".strip()
                    else:
                        previous_chunk_for_next_analysis = text_after_cutoff
                    
                    logger.info(f"✂️  Cut off transcript at last word of last event (position {cutoff_pos})")
                    logger.info(f"   Last event: {last_event.get('type', 'unknown')} - {last_event.get('transcript_segment', '')[:50]}...")
                    logger.info(f"   Text before cutoff: {len(corrected_transcript[:cutoff_pos])} chars (analyzed)")
                    logger.info(f"   Text after cutoff: {len(text_after_cutoff)} chars (will be in previous chunk)")
                    logger.info(f"   Previous chunk length: {len(previous_chunk_for_next_analysis)} chars")
            else:
                logger.warning("⚠️  Could not find last event position, using full analyzed portion")
                # Fallback: return analyzed portion
                if transcript_before_marker:
                    previous_chunk_for_next_analysis = f"{transcript_before_marker} {corrected_transcript}".strip()
                else:
                    previous_chunk_for_next_analysis = corrected_transcript
        else:
            # No events found, return analyzed portion
            logger.info("ℹ️  No events found, returning analyzed portion")
            if transcript_before_marker:
                previous_chunk_for_next_analysis = f"{transcript_before_marker} {corrected_transcript}".strip()
            else:
                previous_chunk_for_next_analysis = corrected_transcript
        
        # Save events directly to database instead of returning them to frontend
        saved_events = []
        for i, event in enumerate(events, 1):
            try:
                # Get the event type handler
                event_type = get_event_type_by_name(event.get('type'))
                if not event_type:
                    logger.warning(f"Event {i}: Unknown event type '{event.get('type')}', skipping")
                    continue
                
                # Validate event
                if not event_type.validate(event):
                    logger.warning(f"Event {i}: Validation failed for type '{event.get('type')}', skipping")
                    logger.debug(f"Event data: {event}")
                    continue
                
                # Save event using the event type's handler
                saved_event = await event_type.handle_event(
                    event,
                    request.session_id,
                    user_id,
                    db
                )
                saved_events.append(saved_event)
                
                # Log event description
                event_type_name = event.get('type', 'unknown').upper()
                if event_type_name in ('DAMAGE', 'HEALING'):
                    event_desc = f"{event_type_name} {event.get('amount', 'N/A')} to {event.get('character_name', 'Unknown')} (ID: {event.get('character_id', 'N/A')})"
                elif event_type_name == 'INITIATIVE_ROLL':
                    event_desc = f"{event_type_name} {event.get('initiative_value', 'N/A')} for {event.get('character_name', 'Unknown')} (ID: {event.get('character_id', 'N/A')})"
                elif event_type_name == 'TURN_ADVANCE':
                    event_desc = f"{event_type_name} - advancing to next turn"
                elif event_type_name == 'ROUND_START':
                    round_num = event.get('round_number', 'N/A')
                    event_desc = f"{event_type_name} - Round {round_num}"
                elif event_type_name == 'COMBAT_END':
                    event_desc = f"{event_type_name} - combat ended"
                elif event_type_name == 'SPELL_CAST':
                    spell_name = event.get('spell_name', 'Unknown')
                    spell_level = event.get('spell_level', 'N/A')
                    char_name = event.get('character_name', 'Unknown')
                    event_desc = f"{event_type_name} - {spell_name} (level {spell_level}) by {char_name}"
                else:
                    char_name = event.get('character_name', 'Unknown')
                    char_id = event.get('character_id', 'N/A')
                    event_desc = f"{event_type_name} for {char_name} (ID: {char_id})"
                
                logger.info(f"   ✓ Saved event {i}: {event_desc}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to save event {i}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                # Continue processing other events even if one fails
        
        logger.info(f"💾 Saved {len(saved_events)} event(s) to database")
        logger.info("=" * 60)
        
        response = {
            'events': saved_events,
            'count': len(saved_events)
        }
        
        # Add previous_chunk_for_next_analysis if we have it
        if previous_chunk_for_next_analysis:
            response['previous_chunk_for_next_analysis'] = previous_chunk_for_next_analysis
            logger.info(f"📦 Returning previous_chunk_for_next_analysis ({len(previous_chunk_for_next_analysis)} chars)")
        
        return response
    
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"ValueError in analyze endpoint: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"❌ Analysis error: {e}")
        logger.error(f"Traceback: {error_trace}")
        raise HTTPException(
            status_code=500,
            detail=f'Failed to analyze transcript: {str(e)}'
        )

