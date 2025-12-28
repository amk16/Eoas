from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from ..middleware.auth import authenticate_token
from ..db.database import get_database
from ..db.firebase import get_firestore
from firebase_admin import firestore
from ..services.event_types import get_event_type_by_name, get_registered_events

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionCreate(BaseModel):
    name: str
    campaign_id: Optional[str] = None


class SessionUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    ended_at: Optional[str] = None


class AddCharactersRequest(BaseModel):
    character_ids: List[str]


# ============================================================================
# BACKWARD COMPATIBILITY - DEPRECATED MODELS
# These models are only used by deprecated endpoints above.
# TODO: Remove when deprecated endpoints are removed
# ============================================================================

class DamageEventCreate(BaseModel):
    """[DEPRECATED] Model for damage/healing events. Use EventCreate instead."""
    character_id: int
    amount: int
    type: str  # 'damage' or 'healing'
    transcript_segment: Optional[str] = None


class TranscriptSegmentCreate(BaseModel):
    client_chunk_id: str
    client_timestamp_ms: Optional[int] = None
    text: str
    speaker: Optional[str] = None


class TranscriptSegmentUpdate(BaseModel):
    text: Optional[str] = None
    speaker: Optional[str] = None


# Phase 1: Combat event models
class CombatEventCreate(BaseModel):
    """[DEPRECATED] Model for combat events. Use EventCreate instead."""
    event_type: str  # 'initiative_roll', 'turn_advance', 'round_start'
    character_id: Optional[int] = None  # Required for initiative_roll
    initiative_value: Optional[int] = None  # Required for initiative_roll
    round_number: Optional[int] = None  # Optional for round_start
    transcript_segment: Optional[str] = None


class InitiativeAdvanceRequest(BaseModel):
    pass  # No parameters needed, just advances to next turn


class InitiativeReorderRequest(BaseModel):
    character_orders: List[Dict[str, int]]  # [{"character_id": 1, "turn_order": 1}, ...]


# Phase 2: Status condition models
class StatusConditionRemoveRequest(BaseModel):
    character_id: int
    condition_name: str


# Phase 3: Buff/debuff models
class BuffDebuffRemoveRequest(BaseModel):
    character_id: int
    effect_name: str


# Generic event model - accepts any event type
class EventCreate(BaseModel):
    """Generic event model that accepts any fields needed for any event type.
    
    The event type registry will validate which fields are actually required
    for each specific event type.
    """
    type: str  # Required: the event type name (e.g., 'damage', 'initiative_roll', 'status_condition_applied')
    character_id: Optional[int] = None
    character_name: Optional[str] = None
    amount: Optional[int] = None
    initiative_value: Optional[int] = None
    round_number: Optional[int] = None
    condition_name: Optional[str] = None
    duration_minutes: Optional[int] = None
    # Phase 3: Buff/debuff fields
    effect_name: Optional[str] = None
    effect_type: Optional[str] = None  # 'buff' or 'debuff'
    stat_modifications: Optional[Dict[str, Any]] = None  # e.g., {"ac": 2, "attack_rolls": 1}
    stacking_rule: Optional[str] = None  # 'none', 'stack', 'replace', 'highest'
    source: Optional[str] = None  # Optional: spell name, item name, etc.
    # Phase 4: Spell cast fields
    spell_name: Optional[str] = None
    spell_level: Optional[int] = None  # 0-9, where 0 is cantrip
    transcript_segment: Optional[str] = None


@router.get('/')
async def get_sessions(
    campaign_id: Optional[str] = Query(None),
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all sessions for the authenticated user, optionally filtered by campaign."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Query nested collection: users/{user_id}/sessions
        query = db.collection('users').document(user_id).collection('sessions')
        if campaign_id:
            query = query.where('campaign_id', '==', campaign_id)
        
        docs = query.stream()
        sessions = []
        for doc in docs:
            session_data = doc.to_dict()
            session_data['id'] = doc.id  # Add document ID
            
            # Convert Firestore timestamps to strings
            if 'started_at' in session_data and hasattr(session_data['started_at'], 'isoformat'):
                session_data['started_at'] = session_data['started_at'].isoformat()
            if 'ended_at' in session_data and hasattr(session_data['ended_at'], 'isoformat'):
                session_data['ended_at'] = session_data['ended_at'].isoformat()
            
            sessions.append(session_data)
        
        # Sort by started_at descending
        sessions.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        return sessions
    except Exception as e:
        print(f'Error fetching sessions: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{session_id}')
async def get_session(session_id: str, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Get a single session by ID with characters and events."""
    try:
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Get session from Firestore nested collection
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        session = session_doc.to_dict()
        session['id'] = session_id
        
        # Convert Firestore timestamps to strings
        if 'started_at' in session and hasattr(session['started_at'], 'isoformat'):
            session['started_at'] = session['started_at'].isoformat()
        if 'ended_at' in session and hasattr(session['ended_at'], 'isoformat'):
            session['ended_at'] = session['ended_at'].isoformat()
        
        # Get session characters from Firestore subcollection
        session_characters_ref = session_ref.collection('session_characters')
        session_characters_docs = session_characters_ref.stream()
        
        session_characters = []
        for doc in session_characters_docs:
            char_data = doc.to_dict()
            character_id = char_data.get('character_id')
            
            if character_id:
                # Get full character details from Firestore
                char_ref = db_firestore.collection('users').document(user_id).collection('characters').document(str(character_id))
                char_doc = char_ref.get()
                
                if char_doc.exists:
                    char_details = char_doc.to_dict()
                    session_characters.append({
                        'id': doc.id,
                        'character_id': character_id,
                        'character_name': char_data.get('character_name') or char_details.get('name', 'Unknown'),
                        'starting_hp': char_data.get('starting_hp', char_details.get('max_hp', 100)),
                        'current_hp': char_data.get('current_hp', char_details.get('max_hp', 100)),
                        'max_hp': char_details.get('max_hp', 100),
                        # Include additional character details if needed
                        'race': char_details.get('race'),
                        'class_name': char_details.get('class_name'),
                        'level': char_details.get('level'),
                        'ac': char_details.get('ac'),
                    })
        
        # Get events from Firestore subcollection
        events_ref = session_ref.collection('events')
        events_docs = events_ref.stream()
        
        all_events = []
        for doc in events_docs:
            event_data = doc.to_dict()
            event_data['id'] = doc.id
            
            # Convert Firestore timestamp to string
            if 'timestamp' in event_data and hasattr(event_data['timestamp'], 'isoformat'):
                event_data['timestamp'] = event_data['timestamp'].isoformat()
            
            # Map event type to frontend-compatible format
            event_type = event_data.get('type', 'unknown')
            
            # Build event in format expected by frontend
            formatted_event = {
                'id': event_data['id'],
                'session_id': session_id,
                'character_id': event_data.get('character_id'),
                'character_name': event_data.get('character_name', 'Unknown'),
                'type': event_type,  # 'damage', 'healing', 'spell_cast', etc.
                'event_type': event_type,  # For compatibility
                'timestamp': event_data.get('timestamp', ''),
                'transcript_segment': event_data.get('transcript_segment'),
            }
            
            # Add type-specific fields
            if event_type in ('damage', 'healing'):
                formatted_event['amount'] = event_data.get('amount')
            elif event_type == 'spell_cast':
                formatted_event['spell_name'] = event_data.get('spell_name')
                formatted_event['spell_level'] = event_data.get('spell_level')
            elif event_type == 'initiative_roll':
                formatted_event['initiative_value'] = event_data.get('initiative_value')
            elif event_type == 'round_start':
                formatted_event['round_number'] = event_data.get('round_number')
            elif event_type in ('status_condition_applied', 'status_condition_removed'):
                formatted_event['condition_name'] = event_data.get('condition_name')
            elif event_type in ('buff_debuff_applied', 'buff_debuff_removed'):
                formatted_event['effect_name'] = event_data.get('effect_name')
                formatted_event['effect_type'] = event_data.get('effect_type')
            
            all_events.append(formatted_event)
        
        # Sort all events by timestamp descending
        all_events.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return {
            **session,
            'characters': session_characters,
            'events': all_events
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching session: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/')
async def create_session(session: SessionCreate, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Create a new session."""
    try:
        logger.info(f'[SESSIONS] Creating session for user_id={user_id}, name={session.name}')
        logger.info(f'[SESSIONS] Session data: {session.dict()}')
        logger.info(f'[SESSIONS] Storage: Firestore')
        
        if not session.name:
            raise HTTPException(status_code=400, detail='Session name is required')
        
        db = get_firestore()
        if not db:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[SESSIONS] Got Firestore client')
        
        # Verify campaign belongs to user if provided (campaigns are now in Firestore)
        if session.campaign_id:
            campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(session.campaign_id))
            campaign_doc = campaign_ref.get()
            if not campaign_doc.exists:
                raise HTTPException(status_code=400, detail='Campaign not found or does not belong to you')
        
        # Prepare session data for Firestore (no user_id needed - it's in the path)
        session_data = {
            'name': session.name,
            'status': 'active',
            'campaign_id': session.campaign_id,
            'started_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Remove None values
        session_data = {k: v for k, v in session_data.items() if v is not None}
        
        logger.info(f'[SESSIONS] Saving to Firestore collection: users/{user_id}/sessions')
        # Create document in nested collection: users/{user_id}/sessions
        session_ref = db.collection('users').document(user_id).collection('sessions').document()
        session_ref.set(session_data)
        session_id = session_ref.id
        logger.info(f'[SESSIONS] Session saved to Firestore with id={session_id}')
        
        # Fetch the created document to return
        created_doc = session_ref.get()
        result = created_doc.to_dict()
        result['id'] = session_id  # Add document ID to result
        
        # Convert Firestore timestamps to strings for JSON serialization
        if 'started_at' in result and hasattr(result['started_at'], 'isoformat'):
            result['started_at'] = result['started_at'].isoformat()
        if 'ended_at' in result and hasattr(result['ended_at'], 'isoformat'):
            result['ended_at'] = result['ended_at'].isoformat()
        
        logger.info(f'[SESSIONS] Returning created session: {result}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating session: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{session_id}')
async def update_session(
    session_id: str,
    session_update: SessionUpdate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a session (e.g., end session, change name)."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/sessions/{session_id}
        session_ref = db.collection('users').document(user_id).collection('sessions').document(str(session_id))
        existing_doc = session_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Build update data
        update_data = {}
        
        if session_update.name is not None:
            update_data['name'] = session_update.name
        if session_update.status is not None:
            update_data['status'] = session_update.status
        if session_update.ended_at is not None:
            update_data['ended_at'] = session_update.ended_at
        
        if not update_data:
            raise HTTPException(status_code=400, detail='No fields to update')
        
        logger.info(f'[SESSIONS] Updating Firestore document: users/{user_id}/sessions/{session_id}')
        session_ref.update(update_data)
        logger.info(f'[SESSIONS] Session updated in Firestore')
        
        # Fetch updated document
        updated_doc = session_ref.get()
        result = updated_doc.to_dict()
        result['id'] = session_id
        
        # Convert Firestore timestamps to strings
        if 'started_at' in result and hasattr(result['started_at'], 'isoformat'):
            result['started_at'] = result['started_at'].isoformat()
        if 'ended_at' in result and hasattr(result['ended_at'], 'isoformat'):
            result['ended_at'] = result['ended_at'].isoformat()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error updating session: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{session_id}/characters')
async def add_characters_to_session(
    session_id: str,
    request: AddCharactersRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Add characters to a session."""
    try:
        if not isinstance(request.character_ids, list) or len(request.character_ids) == 0:
            raise HTTPException(status_code=400, detail='character_ids must be a non-empty array')
        
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Verify session belongs to user
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify all characters belong to user and get their max_hp
        characters = []
        for character_id in request.character_ids:
            char_ref = db_firestore.collection('users').document(user_id).collection('characters').document(str(character_id))
            char_doc = char_ref.get()
            
            if not char_doc.exists:
                raise HTTPException(
                    status_code=400,
                    detail=f'Character {character_id} not found or does not belong to you'
                )
            
            char_data = char_doc.to_dict()
            characters.append({
                'id': character_id,
                'max_hp': char_data.get('max_hp', 100),
                'name': char_data.get('name', 'Unknown')
            })
        
        # Store session characters in Firestore subcollection
        session_characters_ref = session_ref.collection('session_characters')
        
        for character in characters:
            # Check if session_character already exists
            char_doc_ref = session_characters_ref.document(character['id'])
            char_doc = char_doc_ref.get()
            
            if char_doc.exists:
                # Update existing
                char_doc_ref.update({
                    'starting_hp': character['max_hp'],
                    'current_hp': character['max_hp'],
                })
            else:
                # Create new
                char_doc_ref.set({
                    'character_id': character['id'],
                    'character_name': character['name'],
                    'starting_hp': character['max_hp'],
                    'current_hp': character['max_hp'],
                })
        
        # Return updated session with characters
        session_characters_docs = session_characters_ref.stream()
        session_characters = []
        for doc in session_characters_docs:
            char_data = doc.to_dict()
            char_data['id'] = doc.id
            session_characters.append(char_data)
        
        return {
            'message': 'Characters added to session',
            'characters': session_characters
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error adding characters to session: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{session_id}/events')
async def get_session_events(session_id: int, user_id: str = Depends(authenticate_token)) -> List[Dict[str, Any]]:
    """Get events for a session."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        events_rows = db.execute('''
            SELECT 
                de.*,
                c.name as character_name
            FROM damage_events de
            JOIN characters c ON de.character_id = c.id
            WHERE de.session_id = ?
            ORDER BY de.timestamp DESC
        ''', (session_id,)).fetchall()
        
        events = [dict(row) for row in events_rows]
        return events
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching session events: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# ============================================================================
# BACKWARD COMPATIBILITY - DEPRECATED ENDPOINTS
# These endpoints exist only for backward compatibility.
# TODO: Remove these endpoints once all clients are migrated to /event endpoint
# ============================================================================

@router.post('/{session_id}/damage-event')
async def create_damage_event(
    session_id: int,
    event: DamageEventCreate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """[DEPRECATED] Record a damage or healing event for a character in a session.
    
    DEPRECATED: Use POST /sessions/{id}/event instead.
    This endpoint exists only for backward compatibility.
    
    Uses the event type registry to handle the event processing.
    """
    try:
        # Get the event type handler
        event_type = get_event_type_by_name(event.type)
        if not event_type:
            valid_types = ', '.join(get_registered_events().keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown event type: {event.type}. Valid types: {valid_types}"
            )
        
        # Convert Pydantic model to dict for validation and processing
        event_data = {
            'character_id': event.character_id,
            'amount': event.amount,
            'type': event.type,
            'transcript_segment': event.transcript_segment
        }
        
        # Validate using event type's validate method
        if not event_type.validate(event_data):
            raise HTTPException(
                status_code=400,
                detail='Event data validation failed'
            )
        
        # Get database connection
        db = get_database()
        
        # Delegate to event type's handler
        result = await event_type.handle_event(event_data, session_id, user_id, db)
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating damage event: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Combat event endpoint
@router.post('/{session_id}/combat-event')
async def create_combat_event(
    session_id: int,
    event: CombatEventCreate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """[DEPRECATED] Record a combat event (initiative roll, turn advance, round start).
    
    DEPRECATED: Use POST /sessions/{id}/event instead.
    This endpoint exists only for backward compatibility.
    """
    try:
        # Get the event type handler
        event_type = get_event_type_by_name(event.event_type)
        if not event_type:
            valid_types = ', '.join(get_registered_events().keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown event type: {event.event_type}. Valid types: {valid_types}"
            )
        
        # Convert Pydantic model to dict for validation and processing
        event_data = {
            'type': event.event_type,
            'transcript_segment': event.transcript_segment
        }
        
        # Add type-specific fields
        if event.character_id is not None:
            event_data['character_id'] = event.character_id
        if event.initiative_value is not None:
            event_data['initiative_value'] = event.initiative_value
        if event.round_number is not None:
            event_data['round_number'] = event.round_number
        
        # Validate using event type's validate method
        if not event_type.validate(event_data):
            raise HTTPException(
                status_code=400,
                detail='Event data validation failed'
            )
        
        # Get database connection
        db = get_database()
        
        # Delegate to event type's handler
        result = await event_type.handle_event(event_data, session_id, user_id, db)
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating combat event: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Generic event endpoint - handles all event types through the registry
@router.post('/{session_id}/event')
async def create_event(
    session_id: int,
    event: EventCreate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Generic endpoint for creating any type of event.
    
    Uses the event type registry to automatically:
    - Validate the event data based on event type
    - Process the event (save to DB, update state tables)
    
    This is the unified endpoint that replaces type-specific endpoints.
    The frontend should use this for all events.
    """
    try:
        # Get the event type handler from registry
        event_type = get_event_type_by_name(event.type)
        if not event_type:
            valid_types = ', '.join(get_registered_events().keys())
            raise HTTPException(
                status_code=400,
                detail=f"Unknown event type: '{event.type}'. Valid types: {valid_types}"
            )
        
        # Convert Pydantic model to dict, excluding None values
        event_data = {
            'type': event.type,
        }
        
        # Add all non-None fields to event_data
        if event.character_id is not None:
            event_data['character_id'] = event.character_id
        if event.character_name is not None:
            event_data['character_name'] = event.character_name
        if event.amount is not None:
            event_data['amount'] = event.amount
        if event.initiative_value is not None:
            event_data['initiative_value'] = event.initiative_value
        if event.round_number is not None:
            event_data['round_number'] = event.round_number
        if event.condition_name is not None:
            event_data['condition_name'] = event.condition_name
        if event.duration_minutes is not None:
            event_data['duration_minutes'] = event.duration_minutes
        # Phase 3: Buff/debuff fields
        if event.effect_name is not None:
            event_data['effect_name'] = event.effect_name
        if event.effect_type is not None:
            event_data['effect_type'] = event.effect_type
        if event.stat_modifications is not None:
            event_data['stat_modifications'] = event.stat_modifications
        if event.stacking_rule is not None:
            event_data['stacking_rule'] = event.stacking_rule
        if event.source is not None:
            event_data['source'] = event.source
        # Phase 4: Spell cast fields
        if event.spell_name is not None:
            event_data['spell_name'] = event.spell_name
        if event.spell_level is not None:
            event_data['spell_level'] = event.spell_level
        if event.transcript_segment is not None:
            event_data['transcript_segment'] = event.transcript_segment
        
        # Validate using event type's validate method
        if not event_type.validate(event_data):
            raise HTTPException(
                status_code=400,
                detail='Event data validation failed'
            )
        
        # Get database connection
        db = get_database()
        
        # Delegate to event type's handler (this does all the work)
        result = await event_type.handle_event(event_data, session_id, user_id, db)
        
        return result
            
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating event: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Get initiative order
@router.get('/{session_id}/initiative')
async def get_initiative_order(
    session_id: int,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Get current initiative order for a session."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get combat state
        combat_state = db.execute(
            'SELECT * FROM combat_state WHERE session_id = ?',
            (session_id,)
        ).fetchone()
        
        # Get initiative order
        initiative_rows = db.execute('''
            SELECT 
                io.character_id,
                io.initiative_value,
                io.turn_order,
                c.name as character_name
            FROM initiative_order io
            JOIN characters c ON io.character_id = c.id
            WHERE io.session_id = ?
            ORDER BY io.turn_order ASC
        ''', (session_id,)).fetchall()
        
        initiative_list = [dict(row) for row in initiative_rows]
        
        result = {
            'initiative_order': initiative_list,
            'combat_state': dict(combat_state) if combat_state else None
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching initiative order: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Get full combat state
@router.get('/{session_id}/combat-state')
async def get_combat_state(
    session_id: str,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Get full combat state including round, current turn, and initiative order."""
    try:
        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Combat state is still in SQLite, so we need to convert session_id to int
        # If conversion fails, return empty combat state (combat not active)
        # This is expected for Firestore sessions until combat state is migrated
        try:
            session_id_int = int(session_id)
            # Legacy SQLite path (only reached if session_id_int was successfully converted)
            db = get_database()
            
            # Get combat state from SQLite
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id_int,)
            ).fetchone()
            
            if combat_state:
                # Get initiative order with character names from SQLite
                initiative_rows = db.execute('''
                    SELECT 
                        io.character_id,
                        io.initiative_value,
                        io.turn_order,
                        c.name as character_name
                    FROM initiative_order io
                    JOIN characters c ON io.character_id = c.id
                    WHERE io.session_id = ?
                    ORDER BY io.turn_order ASC
                ''', (session_id_int,)).fetchall()
                
                initiative_list = [dict(row) for row in initiative_rows]
                
                # Get current turn character name
                current_turn_char_name = None
                if combat_state['current_turn_character_id']:
                    char = db.execute(
                        'SELECT name FROM characters WHERE id = ?',
                        (combat_state['current_turn_character_id'],)
                    ).fetchone()
                    if char:
                        current_turn_char_name = char['name']
                
                return {
                    'is_active': bool(combat_state['is_active']),
                    'current_round': combat_state['current_round'],
                    'current_turn_character_id': combat_state['current_turn_character_id'],
                    'current_turn_character_name': current_turn_char_name,
                    'initiative_order': initiative_list
                }
        except (ValueError, TypeError):
            # Session ID is a Firestore string - read combat state from Firestore
            combat_state_ref = session_ref.collection('combat_state').document('current')
            combat_state_doc = combat_state_ref.get()
            
            if not combat_state_doc.exists:
                # No combat state exists
                return {
                    'is_active': False,
                    'current_round': 1,
                    'current_turn_character_id': None,
                    'current_turn_character_name': None,
                    'initiative_order': []
                }
            
            combat_state_data = combat_state_doc.to_dict()
            
            # Get initiative order from Firestore
            initiative_order_ref = session_ref.collection('initiative_order')
            all_orders = list(initiative_order_ref.stream())
            
            initiative_list = []
            for doc in all_orders:
                data = doc.to_dict()
                initiative_list.append({
                    'character_id': data.get('character_id'),
                    'character_name': data.get('character_name', 'Unknown'),
                    'initiative_value': data.get('initiative_value', 0),
                    'turn_order': data.get('turn_order', 0)
                })
            
            # Sort by turn_order
            initiative_list.sort(key=lambda x: x.get('turn_order', 0))
            
            # Get current turn character name
            current_turn_char_name = None
            current_turn_char_id = combat_state_data.get('current_turn_character_id')
            if current_turn_char_id:
                for char in initiative_list:
                    if str(char.get('character_id')) == str(current_turn_char_id):
                        current_turn_char_name = char.get('character_name')
                        break
                
                # If not found in initiative list, try to fetch from characters collection
                if not current_turn_char_name:
                    char_ref = db_firestore.collection('users').document(user_id).collection('characters').document(str(current_turn_char_id))
                    char_doc = char_ref.get()
                    if char_doc.exists:
                        char_data = char_doc.to_dict()
                        current_turn_char_name = char_data.get('name', 'Unknown')
            
            return {
                'is_active': combat_state_data.get('is_active', False),
                'current_round': combat_state_data.get('current_round', 1),
                'current_turn_character_id': current_turn_char_id,
                'current_turn_character_name': current_turn_char_name,
                'initiative_order': initiative_list
            }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching combat state: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Manually advance turn
@router.post('/{session_id}/initiative/advance')
async def advance_turn(
    session_id: str,
    request: InitiativeAdvanceRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Manually advance to the next turn in initiative order."""
    try:
        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Combat state is still in SQLite, so we need to convert session_id to int
        # Update combat state in Firestore
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(session_id)
        combat_state_ref = session_ref.collection('combat_state').document('current')
        combat_state_doc = combat_state_ref.get()
        
        if not combat_state_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Combat not started. Roll initiative first.'
            )
        
        combat_state_data = combat_state_doc.to_dict()
        if not combat_state_data.get('is_active', False):
            raise HTTPException(
                status_code=400,
                detail='Combat not active. Roll initiative first.'
            )
        
        current_char_id = combat_state_data.get('current_turn_character_id')
        if not current_char_id:
            raise HTTPException(
                status_code=400,
                detail='No current turn set. Roll initiative first.'
            )
        
        # Get initiative order from Firestore
        initiative_order_ref = session_ref.collection('initiative_order')
        all_orders = list(initiative_order_ref.stream())
        
        # Find current character's turn order
        current_turn_order = None
        for doc in all_orders:
            data = doc.to_dict()
            if str(data.get('character_id')) == str(current_char_id):
                current_turn_order = data.get('turn_order')
                break
        
        if current_turn_order is None:
            raise HTTPException(
                status_code=400,
                detail='Current character not in initiative order'
            )
        
        # Find next character in order
        next_char_id = None
        next_char_turn_order = None
        for doc in all_orders:
            data = doc.to_dict()
            turn_order = data.get('turn_order', 0)
            if turn_order > current_turn_order:
                if next_char_turn_order is None or turn_order < next_char_turn_order:
                    next_char_id = data.get('character_id')
                    next_char_turn_order = turn_order
        
        if next_char_id:
            # Move to next character
            combat_state_ref.update({
                'current_turn_character_id': next_char_id,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
        else:
            # Wrap around to first character and increment round
            first_char_id = None
            first_turn_order = None
            for doc in all_orders:
                data = doc.to_dict()
                turn_order = data.get('turn_order', 0)
                if first_turn_order is None or turn_order < first_turn_order:
                    first_char_id = data.get('character_id')
                    first_turn_order = turn_order
            
            if first_char_id:
                current_round = combat_state_data.get('current_round', 1)
                combat_state_ref.update({
                    'current_turn_character_id': first_char_id,
                    'current_round': current_round + 1,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
        
        # Also try to update SQLite for legacy compatibility (if session_id can be converted)
        try:
            session_id_int = int(session_id)
            db = get_database()
            
            # Get combat state from SQLite
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id_int,)
            ).fetchone()
            
            if not combat_state or not combat_state['is_active']:
                # Return updated combat state from Firestore
                return await get_combat_state(session_id, user_id)
            
            # Get current turn character
            current_char_id_int = combat_state['current_turn_character_id']
            if not current_char_id_int:
                return await get_combat_state(session_id, user_id)
            
            # Get current turn order
            current_turn = db.execute(
                'SELECT turn_order FROM initiative_order WHERE session_id = ? AND character_id = ?',
                (session_id_int, current_char_id_int)
            ).fetchone()
            
            if not current_turn:
                return await get_combat_state(session_id, user_id)
            
            # Get next character in order
            next_char = db.execute(
                '''SELECT character_id FROM initiative_order 
                   WHERE session_id = ? AND turn_order > ?
                   ORDER BY turn_order ASC LIMIT 1''',
                (session_id_int, current_turn['turn_order'])
            ).fetchone()
            
            if next_char:
                db.execute(
                    'UPDATE combat_state SET current_turn_character_id = ? WHERE session_id = ?',
                    (next_char['character_id'], session_id_int)
                )
            else:
                first_char = db.execute(
                    '''SELECT character_id FROM initiative_order 
                       WHERE session_id = ? 
                       ORDER BY turn_order ASC LIMIT 1''',
                    (session_id_int,)
                ).fetchone()
                
                if first_char:
                    db.execute(
                        '''UPDATE combat_state 
                           SET current_turn_character_id = ?, current_round = current_round + 1 
                           WHERE session_id = ?''',
                        (first_char['character_id'], session_id_int)
                    )
            
            db.commit()
        except (ValueError, TypeError):
            # Can't convert to int, skip SQLite update (Firestore is the source of truth)
            pass
        
        # Return updated combat state
        return await get_combat_state(session_id, user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        db = get_database()
        db.rollback()
        print(f'Error advancing turn: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Manually reorder initiative
@router.post('/{session_id}/initiative/reorder')
async def reorder_initiative(
    session_id: int,
    request: InitiativeReorderRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Manually reorder initiative for a session."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Update turn orders
        for char_order in request.character_orders:
            char_id = char_order.get('character_id')
            turn_order = char_order.get('turn_order')
            
            if char_id is None or turn_order is None:
                continue
            
            # Verify character is in session
            session_char = db.execute(
                'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
                (session_id, char_id)
            ).fetchone()
            
            if not session_char:
                continue
            
            # Update turn order
            db.execute(
                'UPDATE initiative_order SET turn_order = ? WHERE session_id = ? AND character_id = ?',
                (turn_order, session_id, char_id)
            )
        
        db.commit()
        
        # Return updated initiative order
        return await get_initiative_order(session_id, user_id)
        
    except HTTPException:
        raise
    except Exception as e:
        db = get_database()
        db.rollback()
        print(f'Error reordering initiative: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 2: Get status conditions
@router.get('/{session_id}/status-conditions')
async def get_status_conditions(
    session_id: int,
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all active status conditions for a session."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get active status conditions with character names
        condition_rows = db.execute('''
            SELECT 
                asc.*,
                c.name as character_name
            FROM active_status_conditions asc
            JOIN characters c ON asc.character_id = c.id
            WHERE asc.session_id = ?
            ORDER BY asc.character_id, asc.condition_name
        ''', (session_id,)).fetchall()
        
        conditions = []
        for row in condition_rows:
            condition_dict = dict(row)
            # Check if condition has expired
            if condition_dict.get('expires_at'):
                import datetime
                expires_at = datetime.datetime.fromisoformat(condition_dict['expires_at'])
                if datetime.datetime.now() > expires_at:
                    # Condition has expired, remove it
                    db.execute(
                        '''DELETE FROM active_status_conditions 
                           WHERE session_id = ? AND character_id = ? AND condition_name = ?''',
                        (session_id, condition_dict['character_id'], condition_dict['condition_name'])
                    )
                    continue
            conditions.append(condition_dict)
        
        db.commit()
        return conditions
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching status conditions: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 2: Remove status condition
@router.post('/{session_id}/status-conditions/remove')
async def remove_status_condition(
    session_id: int,
    request: StatusConditionRemoveRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Manually remove a status condition from a character."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify character is in the session
        session_character = db.execute(
            'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
            (session_id, request.character_id)
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Check if condition exists
        condition = db.execute(
            '''SELECT * FROM active_status_conditions 
               WHERE session_id = ? AND character_id = ? AND condition_name = ?''',
            (session_id, request.character_id, request.condition_name)
        ).fetchone()
        
        if not condition:
            raise HTTPException(
                status_code=404,
                detail='Status condition not found'
            )
        
        # Insert removal event
        db.execute(
            '''INSERT INTO status_condition_events 
               (session_id, character_id, condition_name, action, transcript_segment)
               VALUES (?, ?, ?, ?, ?)''',
            (
                session_id,
                request.character_id,
                request.condition_name,
                'removed',
                f'Manually removed by user'
            )
        )
        
        # Remove from active status conditions
        db.execute(
            '''DELETE FROM active_status_conditions 
               WHERE session_id = ? AND character_id = ? AND condition_name = ?''',
            (session_id, request.character_id, request.condition_name)
        )
        
        db.commit()
        
        return {
            'message': 'Status condition removed successfully',
            'character_id': request.character_id,
            'condition_name': request.condition_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db = get_database()
        db.rollback()
        print(f'Error removing status condition: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 3: Get active buffs/debuffs for a session
@router.get('/{session_id}/buffs-debuffs')
async def get_buffs_debuffs(
    session_id: int,
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all active buffs/debuffs for a session."""
    import json
    import datetime
    
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get active buffs/debuffs with character names
        effect_rows = db.execute('''
            SELECT 
                abd.*,
                c.name as character_name
            FROM active_buff_debuffs abd
            JOIN characters c ON abd.character_id = c.id
            WHERE abd.session_id = ?
            ORDER BY abd.character_id, abd.effect_name
        ''', (session_id,)).fetchall()
        
        effects = []
        for row in effect_rows:
            effect_dict = dict(row)
            # Parse stat_modifications JSON
            if effect_dict.get('stat_modifications'):
                effect_dict['stat_modifications'] = json.loads(effect_dict['stat_modifications'])
            else:
                effect_dict['stat_modifications'] = {}
            
            # Check if effect has expired
            if effect_dict.get('expires_at'):
                expires_at_str = effect_dict['expires_at']
                if isinstance(expires_at_str, str):
                    expires_at = datetime.datetime.fromisoformat(expires_at_str.replace(' ', 'T'))
                else:
                    expires_at = expires_at_str
                if datetime.datetime.now() > expires_at:
                    # Effect has expired, remove it
                    db.execute(
                        '''DELETE FROM active_buff_debuffs 
                           WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
                        (session_id, effect_dict['character_id'], effect_dict['effect_name'])
                    )
                    continue
            effects.append(effect_dict)
        
        db.commit()
        return effects
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching buffs/debuffs: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 3: Get active buffs/debuffs for a specific character
@router.get('/{session_id}/characters/{character_id}/buffs-debuffs')
async def get_character_buffs_debuffs(
    session_id: int,
    character_id: int,
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all active buffs/debuffs for a specific character in a session."""
    import json
    import datetime
    
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify character is in the session
        session_character = db.execute(
            'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
            (session_id, character_id)
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get active buffs/debuffs for this character
        effect_rows = db.execute('''
            SELECT 
                abd.*,
                c.name as character_name
            FROM active_buff_debuffs abd
            JOIN characters c ON abd.character_id = c.id
            WHERE abd.session_id = ? AND abd.character_id = ?
            ORDER BY abd.effect_name
        ''', (session_id, character_id)).fetchall()
        
        effects = []
        for row in effect_rows:
            effect_dict = dict(row)
            # Parse stat_modifications JSON
            if effect_dict.get('stat_modifications'):
                effect_dict['stat_modifications'] = json.loads(effect_dict['stat_modifications'])
            else:
                effect_dict['stat_modifications'] = {}
            
            # Check if effect has expired
            if effect_dict.get('expires_at'):
                expires_at_str = effect_dict['expires_at']
                if isinstance(expires_at_str, str):
                    expires_at = datetime.datetime.fromisoformat(expires_at_str.replace(' ', 'T'))
                else:
                    expires_at = expires_at_str
                if datetime.datetime.now() > expires_at:
                    # Effect has expired, remove it
                    db.execute(
                        '''DELETE FROM active_buff_debuffs 
                           WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
                        (session_id, character_id, effect_dict['effect_name'])
                    )
                    continue
            effects.append(effect_dict)
        
        db.commit()
        return effects
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching character buffs/debuffs: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 3: Remove buff/debuff
@router.post('/{session_id}/buffs-debuffs/remove')
async def remove_buff_debuff(
    session_id: int,
    request: BuffDebuffRemoveRequest,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Manually remove a buff/debuff from a character."""
    import json
    
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify character is in the session
        session_character = db.execute(
            'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
            (session_id, request.character_id)
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Check if effect exists
        effect = db.execute(
            '''SELECT * FROM active_buff_debuffs 
               WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
            (session_id, request.character_id, request.effect_name)
        ).fetchone()
        
        if not effect:
            raise HTTPException(
                status_code=404,
                detail='Buff/debuff not found'
            )
        
        # Insert removal event
        db.execute(
            '''INSERT INTO buff_debuff_events 
               (session_id, character_id, effect_name, effect_type, action, stat_modifications, stacking_rule, transcript_segment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                session_id,
                request.character_id,
                request.effect_name,
                effect['effect_type'],
                'removed',
                effect['stat_modifications'],
                effect['stacking_rule'],
                'Manually removed by user'
            )
        )
        
        # Remove from active buffs/debuffs
        db.execute(
            '''DELETE FROM active_buff_debuffs 
               WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
            (session_id, request.character_id, request.effect_name)
        )
        
        db.commit()
        
        return {
            'message': 'Buff/debuff removed successfully',
            'character_id': request.character_id,
            'effect_name': request.effect_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db = get_database()
        db.rollback()
        print(f'Error removing buff/debuff: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 4: Get spell slot usage for a session
@router.get('/{session_id}/spell-slots')
async def get_spell_slots(
    session_id: int,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Get spell slot usage for all characters in a session.
    
    Returns a dictionary mapping character_id to their spell slot usage:
    {
        "1": {
            "character_id": 1,
            "character_name": "Wizard",
            "slots_by_level": {
                "1": 3,  // 3 first-level slots used
                "2": 1,  // 1 second-level slot used
                "3": 0   // 0 third-level slots used
            }
        },
        ...
    }
    """
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get spell slot usage with character names
        slot_rows = db.execute('''
            SELECT 
                css.*,
                c.name as character_name
            FROM character_spell_slots css
            JOIN characters c ON css.character_id = c.id
            WHERE css.session_id = ?
            ORDER BY css.character_id, css.spell_level
        ''', (session_id,)).fetchall()
        
        # Group by character
        spell_slots_by_character = {}
        for row in slot_rows:
            char_id = row['character_id']
            if char_id not in spell_slots_by_character:
                spell_slots_by_character[char_id] = {
                    'character_id': char_id,
                    'character_name': row['character_name'],
                    'slots_by_level': {}
                }
            spell_slots_by_character[char_id]['slots_by_level'][str(row['spell_level'])] = row['slots_used']
        
        return spell_slots_by_character
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching spell slots: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 4: Get spell slot usage for a specific character
@router.get('/{session_id}/characters/{character_id}/spell-slots')
async def get_character_spell_slots(
    session_id: int,
    character_id: int,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Get spell slot usage for a specific character in a session."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify character is in the session
        session_character = db.execute(
            'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
            (session_id, character_id)
        ).fetchone()
        
        if not session_character:
            raise HTTPException(status_code=404, detail='Character not found in session')
        
        # Get character name
        character = db.execute(
            'SELECT name FROM characters WHERE id = ?',
            (character_id,)
        ).fetchone()
        
        if not character:
            raise HTTPException(status_code=404, detail='Character not found')
        
        # Get spell slot usage
        slot_rows = db.execute('''
            SELECT spell_level, slots_used
            FROM character_spell_slots
            WHERE session_id = ? AND character_id = ?
            ORDER BY spell_level
        ''', (session_id, character_id)).fetchall()
        
        slots_by_level = {}
        for row in slot_rows:
            slots_by_level[str(row['spell_level'])] = row['slots_used']
        
        return {
            'character_id': character_id,
            'character_name': character['name'],
            'slots_by_level': slots_by_level
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching character spell slots: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


# Phase 4: Reset spell slots for a character (optional utility)
@router.post('/{session_id}/characters/{character_id}/spell-slots/reset')
async def reset_character_spell_slots(
    session_id: int,
    character_id: int,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Reset spell slot usage for a character (set all to 0)."""
    try:
        db = get_database()
        
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Verify character is in the session
        session_character = db.execute(
            'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
            (session_id, character_id)
        ).fetchone()
        
        if not session_character:
            raise HTTPException(status_code=404, detail='Character not found in session')
        
        # Delete all spell slot records for this character
        db.execute('''
            DELETE FROM character_spell_slots
            WHERE session_id = ? AND character_id = ?
        ''', (session_id, character_id))
        
        db.commit()
        
        return {
            'message': 'Spell slots reset successfully',
            'character_id': character_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db = get_database()
        db.rollback()
        print(f'Error resetting spell slots: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{session_id}/transcripts')
async def get_session_transcripts(
    session_id: str,
    limit: int = Query(200, ge=1, le=1000),
    after_id: Optional[int] = Query(None, ge=0),
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get persisted transcript segments for a session from Firestore."""
    try:
        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get transcripts from Firestore subcollection
        transcripts_ref = session_ref.collection('transcripts')
        
        # Query transcripts - try to order by created_at, but if index doesn't exist, order by document ID
        # Firestore requires an index for order_by on timestamp fields
        try:
            query = transcripts_ref.order_by('created_at', direction=firestore.Query.ASCENDING).limit(limit)
            docs = query.stream()
        except Exception as e:
            # If index doesn't exist, fall back to ordering by document ID
            logger.warning(f"Could not order by created_at (index may not exist): {e}. Ordering by document ID instead.")
            query = transcripts_ref.limit(limit)
            docs = query.stream()
        
        transcripts = []
        for doc in docs:
            transcript_data = doc.to_dict()
            transcript_data['id'] = doc.id
            
            # Convert Firestore timestamp to string
            if 'created_at' in transcript_data and hasattr(transcript_data['created_at'], 'isoformat'):
                transcript_data['created_at'] = transcript_data['created_at'].isoformat()
            
            transcripts.append(transcript_data)
        
        # Sort by created_at if available (client-side fallback)
        transcripts.sort(key=lambda x: x.get('created_at', ''))
        
        return transcripts
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error fetching session transcripts: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{session_id}/transcripts')
async def create_session_transcript_segment(
    session_id: str,
    segment: TranscriptSegmentCreate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Create (or de-dupe) a persisted transcript segment for a session in Firestore."""
    try:
        if not segment.client_chunk_id or not segment.text:
            raise HTTPException(status_code=400, detail='client_chunk_id and text are required')

        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Store transcripts in Firestore subcollection
        transcripts_ref = session_ref.collection('transcripts')
        
        # Check if transcript with this client_chunk_id already exists (de-dupe)
        existing_docs = transcripts_ref.where('client_chunk_id', '==', segment.client_chunk_id).limit(1).stream()
        existing_doc = None
        for doc in existing_docs:
            existing_doc = doc
            break
        
        if existing_doc:
            # Return existing transcript
            result = existing_doc.to_dict()
            result['id'] = existing_doc.id
            # Convert Firestore timestamp to string if present
            if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
                result['created_at'] = result['created_at'].isoformat()
            return result
        
        # Create new transcript document
        from firebase_admin import firestore
        transcript_data = {
            'client_chunk_id': segment.client_chunk_id,
            'client_timestamp_ms': segment.client_timestamp_ms,
            'text': segment.text,
            'speaker': segment.speaker,
            'created_at': firestore.SERVER_TIMESTAMP,
        }
        
        doc_ref = transcripts_ref.document()
        doc_ref.set(transcript_data)
        
        # Get the created document
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=500, detail='Failed to create transcript segment')
        
        result = doc.to_dict()
        result['id'] = doc.id
        
        # Convert Firestore timestamp to string
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error creating session transcript segment: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{session_id}/transcripts/{transcript_id}')
async def update_session_transcript_segment(
    session_id: str,
    transcript_id: str,
    update: TranscriptSegmentUpdate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a transcript segment (speaker and/or text) for a session in Firestore."""
    try:
        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Get transcript from Firestore subcollection
        transcript_ref = session_ref.collection('transcripts').document(str(transcript_id))
        transcript_doc = transcript_ref.get()
        
        if not transcript_doc.exists:
            raise HTTPException(status_code=404, detail='Transcript segment not found')

        # Build update data
        update_data = {}
        if update.text is not None:
            update_data['text'] = update.text
        if update.speaker is not None:
            update_data['speaker'] = update.speaker

        if not update_data:
            raise HTTPException(status_code=400, detail='No fields to update')

        # Update the document
        transcript_ref.update(update_data)
        
        # Get the updated document
        updated_doc = transcript_ref.get()
        result = updated_doc.to_dict()
        result['id'] = updated_doc.id
        
        # Convert Firestore timestamp to string
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating session transcript segment: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{session_id}/transcripts')
async def clear_session_transcripts(
    session_id: str,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Delete all persisted transcript segments for a session."""
    try:
        # Verify session belongs to user in Firestore
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[SESSIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        session_ref = db_firestore.collection('users').document(user_id).collection('sessions').document(str(session_id))
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail='Session not found')
        
        # Transcripts are still in SQLite, so convert session_id to int
        try:
            session_id_int = int(session_id)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=400,
                detail=f'Session ID {session_id} cannot be used with transcript system (must be numeric)'
            )
        
        db = get_database()

        db.execute('DELETE FROM session_transcripts WHERE session_id = ?', (session_id_int,))
        db.commit()
        return {'message': 'Transcripts cleared'}
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error clearing session transcripts: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')

