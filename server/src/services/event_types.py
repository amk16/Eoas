"""
Event Types Module

This module defines all event types that can be detected and processed in D&D sessions.
Each event type includes:
- Schema definition
- Prompt instructions for Gemini AI
- Validation logic
- Handler function to process the event

To add a new event type:
1. Create a class inheriting from EventType
2. Implement all abstract methods
3. Register it using register_event_type()
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from firebase_admin import firestore

logger = logging.getLogger(__name__)


def save_event_to_firestore(
    session_ref: Any,
    event_type: str,
    event_data: Dict[str, Any],
    character_id: Optional[str] = None,
    character_name: Optional[str] = None
) -> Dict[str, Any]:
    """Helper function to save an event to Firestore events subcollection.
    
    Args:
        session_ref: Firestore session document reference
        event_type: Type of event (e.g., 'damage', 'healing', 'initiative_roll')
        event_data: Event data dictionary
        character_id: Character ID (optional, extracted from event_data if not provided)
        character_name: Character name (optional, extracted from event_data if not provided)
    
    Returns:
        Dictionary containing the saved event data with id and timestamp
    """
    events_ref = session_ref.collection('events')
    event_doc_ref = events_ref.document()
    
    # Extract character info if not provided
    if not character_id:
        character_id = str(event_data.get('character_id', ''))
    if not character_name:
        character_name = event_data.get('character_name', 'Unknown')
    
    # Build event document data
    event_doc_data = {
        'type': event_type,
        'character_id': character_id,
        'character_name': character_name,
        'timestamp': firestore.SERVER_TIMESTAMP,
    }
    
    # Add type-specific fields
    if 'amount' in event_data:
        event_doc_data['amount'] = event_data['amount']
    if 'initiative_value' in event_data:
        event_doc_data['initiative_value'] = event_data['initiative_value']
    if 'transcript_segment' in event_data:
        event_doc_data['transcript_segment'] = event_data.get('transcript_segment')
    if 'spell_name' in event_data:
        event_doc_data['spell_name'] = event_data.get('spell_name')
    if 'spell_level' in event_data:
        event_doc_data['spell_level'] = event_data.get('spell_level')
    if 'round_number' in event_data:
        event_doc_data['round_number'] = event_data.get('round_number')
    if 'condition_name' in event_data:
        event_doc_data['condition_name'] = event_data.get('condition_name')
    if 'effect_name' in event_data:
        event_doc_data['effect_name'] = event_data.get('effect_name')
    if 'effect_type' in event_data:
        event_doc_data['effect_type'] = event_data.get('effect_type')
    
    # Save to Firestore
    event_doc_ref.set(event_doc_data)
    event_id = event_doc_ref.id
    
    # Get the created event
    event_doc = event_doc_ref.get()
    result = event_doc.to_dict()
    result['id'] = event_id
    
    # Convert Firestore timestamp to string
    if 'timestamp' in result and hasattr(result['timestamp'], 'isoformat'):
        result['timestamp'] = result['timestamp'].isoformat()
    
    return result

# Registry to hold all registered event types
_event_registry: Dict[str, 'EventType'] = {}


class EventType(ABC):
    """Base abstract class for all event types."""
    
    @abstractmethod
    def get_name(self) -> str:
        """Returns the event type name (e.g., 'damage', 'healing')."""
        pass
    
    @abstractmethod
    def get_prompt_instructions(self) -> str:
        """Returns instructions for Gemini on how to detect this event type."""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Returns the expected JSON schema for this event type.
        
        Returns a dictionary describing required fields and their types.
        Example: {
            'character_id': int,
            'amount': int,
            'type': str,
            'transcript_segment': str
        }
        """
        pass
    
    @abstractmethod
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validates that event_data matches the expected schema.
        
        Args:
            event_data: The event data to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
    
    @abstractmethod
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Processes the event (e.g., save to database, update character state).
        
        Args:
            event_data: The validated event data
            session_id: The session ID (string from Firestore)
            user_id: The user ID (for authorization)
            db_firestore: Firestore database client
            session_ref: Firestore session document reference
            
        Returns:
            Dictionary containing the created/processed event data
            
        Raises:
            HTTPException: If processing fails
        """
        pass


class DamageEventType(EventType):
    """Event type for damage dealt to characters."""
    
    def get_name(self) -> str:
        return "damage"
    
    def get_prompt_instructions(self) -> str:
        return """DAMAGE EVENTS:
- Detect when a character takes damage (loses hit points)
- Look for phrases like "takes X damage", "hits for X", "deals X damage", "X damage to [character]"
- Identify the character name and the numeric damage amount
- Extract the exact text segment that describes the damage event"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'amount': int,
            'type': str,  # Should be "damage"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate damage event data."""
        schema = self.get_schema()
        
        # character_name is optional for API calls (comes from DB), required for Gemini responses
        optional_fields = {'character_name', 'transcript_segment'}
        
        # Check required fields
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            # Type validation
            if field == 'type' and event_data[field] != 'damage':
                logger.warning(f"Invalid type for damage event: {event_data[field]}")
                return False
            elif field == 'amount' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount type: {event_data[field]}")
                    return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
            elif field == 'amount' and event_data[field] <= 0:
                logger.warning(f"Amount must be positive: {event_data[field]}")
                return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle damage event: save to Firestore and update character HP."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        session_character_data = session_character_doc.to_dict()
        current_hp = session_character_data.get('current_hp', session_character_data.get('starting_hp', 100))
        
        # Verify character belongs to user
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        
        if not character_doc.exists:
            raise HTTPException(
                status_code=404,
                detail='Character not found'
            )
        
        character_data = character_doc.to_dict()
        character_name = character_data.get('name', 'Unknown')
        
        try:
            # Calculate new HP (damage reduces HP, minimum 0)
            new_hp = max(0, current_hp - event_data['amount'])
            
            # Save event to Firestore subcollection
            events_ref = session_ref.collection('events')
            event_doc_ref = events_ref.document()
            
            from firebase_admin import firestore
            event_data_firestore = {
                'type': 'damage',
                'character_id': character_id,
                'character_name': character_name,
                'amount': event_data['amount'],
                'transcript_segment': event_data.get('transcript_segment'),
                'timestamp': firestore.SERVER_TIMESTAMP,
            }
            
            event_doc_ref.set(event_data_firestore)
            event_id = event_doc_ref.id
            
            # Update character's current HP in session_characters
            session_character_ref.update({
                'current_hp': new_hp
            })
            
            # Get the created event
            event_doc = event_doc_ref.get()
            event_data_result = event_doc.to_dict()
            event_data_result['id'] = event_id
            
            # Convert Firestore timestamp to string
            if 'timestamp' in event_data_result and hasattr(event_data_result['timestamp'], 'isoformat'):
                event_data_result['timestamp'] = event_data_result['timestamp'].isoformat()
            
            return event_data_result
            
        except Exception as e:
            logger.error(f"Error handling damage event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class HealingEventType(EventType):
    """Event type for healing received by characters."""
    
    def get_name(self) -> str:
        return "healing"
    
    def get_prompt_instructions(self) -> str:
        return """HEALING EVENTS:
- Detect when a character receives healing (gains hit points)
- Look for phrases like "heals for X", "restores X HP", "gains X hit points", "X healing to [character]"
- Identify the character name and the numeric healing amount
- Extract the exact text segment that describes the healing event"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'amount': int,
            'type': str,  # Should be "healing"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate healing event data."""
        schema = self.get_schema()
        
        # character_name is optional for API calls (comes from DB), required for Gemini responses
        optional_fields = {'character_name', 'transcript_segment'}
        
        # Check required fields
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            # Type validation
            if field == 'type' and event_data[field] != 'healing':
                logger.warning(f"Invalid type for healing event: {event_data[field]}")
                return False
            elif field == 'amount' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount type: {event_data[field]}")
                    return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
            elif field == 'amount' and event_data[field] <= 0:
                logger.warning(f"Amount must be positive: {event_data[field]}")
                return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle healing event: save to Firestore and update character HP."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        session_character_data = session_character_doc.to_dict()
        current_hp = session_character_data.get('current_hp', session_character_data.get('starting_hp', 100))
        
        # Verify character belongs to user and get max_hp
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        
        if not character_doc.exists:
            raise HTTPException(
                status_code=404,
                detail='Character not found'
            )
        
        character_data = character_doc.to_dict()
        character_name = character_data.get('name', 'Unknown')
        max_hp = character_data.get('max_hp', 100)
        
        try:
            # Calculate new HP (healing increases HP, maximum max_hp)
            new_hp = min(max_hp, current_hp + event_data['amount'])
            
            # Save event to Firestore using helper function
            saved_event = save_event_to_firestore(
                session_ref,
                'healing',
                event_data,
                character_id,
                character_name
            )
            
            # Update character's current HP in session_characters
            session_character_ref.update({
                'current_hp': new_hp
            })
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling healing event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class InitiativeRollEventType(EventType):
    """Event type for initiative rolls."""
    
    def get_name(self) -> str:
        return "initiative_roll"
    
    def get_prompt_instructions(self) -> str:
        return """INITIATIVE ROLL EVENTS:
- Detect when a character rolls for initiative
- Look for phrases like "rolls initiative", "initiative of X", "[character] rolls X for initiative", "initiative roll: X"
- Identify the character name and the initiative value (d20 roll + modifier)
- Extract the exact text segment that describes the initiative roll"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'initiative_value': int,
            'type': str,  # Should be "initiative_roll"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate initiative roll event data."""
        schema = self.get_schema()
        optional_fields = {'character_name', 'transcript_segment'}
        
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            if field == 'type' and event_data[field] != 'initiative_roll':
                logger.warning(f"Invalid type for initiative roll event: {event_data[field]}")
                return False
            elif field == 'initiative_value' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid initiative_value type: {event_data[field]}")
                    return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle initiative roll: save event to Firestore and update initiative order in SQLite."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'initiative_roll',
                event_data,
                character_id,
                character_name
            )
            
            # Save combat state to Firestore
            combat_state_ref = session_ref.collection('combat_state').document('current')
            combat_state_doc = combat_state_ref.get()
            
            if not combat_state_doc.exists:
                # Initialize combat state
                combat_state_ref.set({
                    'is_active': True,
                    'current_round': 1,
                    'current_turn_character_id': None,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            else:
                combat_state_data = combat_state_doc.to_dict()
                if not combat_state_data.get('is_active', False):
                    # Clear old initiative order when starting a new combat
                    initiative_order_ref = session_ref.collection('initiative_order')
                    for doc in initiative_order_ref.stream():
                        doc.reference.delete()
                    
                    # Reactivate combat
                    combat_state_ref.update({
                        'is_active': True,
                        'current_round': 1,
                        'current_turn_character_id': None,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                    logger.info(f"Reactivating combat for session {session_id} after new initiative roll.")
            
            # Save or update initiative order in Firestore
            initiative_order_ref = session_ref.collection('initiative_order').document(character_id)
            initiative_order_ref.set({
                'character_id': character_id,
                'character_name': character_name,
                'initiative_value': event_data['initiative_value'],
                'turn_order': 0,  # Will be recalculated
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            
            # Get all initiative orders and recalculate turn_order
            all_initiative_orders = session_ref.collection('initiative_order').stream()
            initiative_list = []
            for doc in all_initiative_orders:
                data = doc.to_dict()
                initiative_list.append({
                    'character_id': data['character_id'],
                    'initiative_value': data['initiative_value'],
                    'timestamp': data.get('updated_at')
                })
            
            # Sort by initiative value (descending), then by character_id for consistency
            initiative_list.sort(key=lambda x: (x['initiative_value'], str(x['character_id'])), reverse=True)
            
            # Update turn_order for each
            for idx, item in enumerate(initiative_list, start=1):
                order_ref = session_ref.collection('initiative_order').document(str(item['character_id']))
                order_ref.update({
                    'turn_order': idx,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # Set first character as current turn if not set
            combat_state_data = combat_state_ref.get().to_dict()
            if not combat_state_data.get('current_turn_character_id'):
                if initiative_list:
                    first_char_id = initiative_list[0]['character_id']
                    combat_state_ref.update({
                        'current_turn_character_id': first_char_id,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
            
            # Also try to update SQLite for legacy compatibility (if session_id can be converted)
            try:
                session_id_int = int(session_id)
                character_id_int = int(character_id)
                from ..db.database import get_database
                db = get_database()
                
                # Get or create combat state in SQLite
                combat_state = db.execute(
                    'SELECT * FROM combat_state WHERE session_id = ?',
                    (session_id_int,)
                ).fetchone()
                
                if not combat_state:
                    db.execute(
                        '''INSERT INTO combat_state (session_id, current_round, is_active)
                           VALUES (?, 1, 1)''',
                        (session_id_int,)
                    )
                else:
                    if not combat_state['is_active']:
                        db.execute(
                            'DELETE FROM initiative_order WHERE session_id = ?',
                            (session_id_int,)
                        )
                        db.execute(
                            '''UPDATE combat_state 
                               SET is_active = 1, current_round = 1, current_turn_character_id = NULL
                               WHERE session_id = ?''',
                            (session_id_int,)
                        )
                
                # Update initiative order in SQLite
                db.execute(
                    '''INSERT OR REPLACE INTO initiative_order 
                       (session_id, character_id, initiative_value, turn_order)
                       VALUES (?, ?, ?, 
                           COALESCE((SELECT MAX(turn_order) FROM initiative_order WHERE session_id = ?), 0) + 1)''',
                    (session_id_int, character_id_int, event_data['initiative_value'], session_id_int)
                )
                
                # Reorder initiative by initiative_value (descending)
                initiative_rows = db.execute(
                    '''SELECT character_id, initiative_value 
                       FROM initiative_order 
                       WHERE session_id = ? 
                       ORDER BY initiative_value DESC, character_id ASC''',
                    (session_id_int,)
                ).fetchall()
                
                # Update turn_order based on sorted initiative
                for idx, row in enumerate(initiative_rows, start=1):
                    db.execute(
                        'UPDATE initiative_order SET turn_order = ? WHERE session_id = ? AND character_id = ?',
                        (idx, session_id_int, row['character_id'])
                    )
                
                # Set first character as current turn if not set
                combat_state = db.execute(
                    'SELECT * FROM combat_state WHERE session_id = ?',
                    (session_id_int,)
                ).fetchone()
                
                if combat_state and not combat_state['current_turn_character_id']:
                    first_char = db.execute(
                        '''SELECT character_id FROM initiative_order 
                           WHERE session_id = ? 
                           ORDER BY turn_order ASC LIMIT 1''',
                        (session_id_int,)
                    ).fetchone()
                    
                    if first_char:
                        db.execute(
                            'UPDATE combat_state SET current_turn_character_id = ? WHERE session_id = ?',
                            (first_char['character_id'], session_id_int)
                        )
                
                db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (Firestore is the source of truth)
                pass
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling initiative roll event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class TurnAdvanceEventType(EventType):
    """Event type for turn advancement."""
    
    def get_name(self) -> str:
        return "turn_advance"
    
    def get_prompt_instructions(self) -> str:
        return """TURN ADVANCE EVENTS:
- Detect ONLY when a character explicitly ENDS their turn (not when a turn is announced or mentioned)
- This event advances to the next character in initiative order
- Extract the exact text segment that describes the turn ending

DO DETECT phrases like:
- "I end my turn"
- "That ends my turn"
- "I'm done with my turn"
- "Turn ends here"
- "My turn is over"
- "That's the end of my turn"
- "I finish my turn"

DO NOT DETECT phrases like:
- "it's your turn"
- "I'll start my turn"
- "your turn is next"
- "next up is [character]"
- "[character]'s turn now"
- "[character]'s turn"
- "turn passes to [character]"
- "next turn"
- Any phrase that announces or mentions whose turn it is (these are NOT turn endings)"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'type': str,  # Should be "turn_advance"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate turn advance event data."""
        if event_data.get('type') != 'turn_advance':
            logger.warning(f"Invalid type for turn advance event: {event_data.get('type')}")
            return False
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle turn advance: move to next character in initiative order.
        
        Includes deduplication: if a turn advance occurred recently (within 5 seconds),
        skip processing to avoid duplicate advances from phrases like "I end my turn"
        followed by "beginning the next turn".
        """
        try:
            # Deduplication: Check for recent turn advance events in Firestore (within 5 seconds)
            import datetime
            from firebase_admin import firestore as firestore_module
            time_window_seconds = 5
            cutoff_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=time_window_seconds)
            
            # Check Firestore for recent turn_advance events
            # Note: We order by timestamp only (single-field index) and filter by type in memory
            # to avoid requiring a composite index
            events_ref = session_ref.collection('events')
            # Fetch recent events ordered by timestamp, then filter by type in memory
            recent_events = events_ref.order_by('timestamp', direction=firestore_module.Query.DESCENDING).limit(10).stream()
            
            recent_turn_advance = None
            for doc in recent_events:
                event_data_check = doc.to_dict()
                # Filter for turn_advance events in memory
                if event_data_check.get('type') != 'turn_advance':
                    continue
                    
                if 'timestamp' in event_data_check:
                    event_time = event_data_check['timestamp']
                    if hasattr(event_time, 'timestamp'):
                        # Firestore timestamp
                        if event_time.timestamp() > cutoff_time.timestamp():
                            recent_turn_advance = {'id': doc.id, 'data': event_data_check}
                            break  # Found the most recent one within window
                    elif isinstance(event_time, datetime.datetime):
                        if event_time > cutoff_time:
                            recent_turn_advance = {'id': doc.id, 'data': event_data_check}
                            break  # Found the most recent one within window
            
            if recent_turn_advance:
                logger.info(
                    f"Turn advance deduplication: Skipping duplicate turn advance. "
                    f"Last turn advance was within {time_window_seconds} second window"
                )
                result = recent_turn_advance['data'].copy()
                result['id'] = recent_turn_advance['id']
                if 'timestamp' in result and hasattr(result['timestamp'], 'isoformat'):
                    result['timestamp'] = result['timestamp'].isoformat()
                return result
            
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'turn_advance',
                event_data
            )
            
            # Update combat state in Firestore
            combat_state_ref = session_ref.collection('combat_state').document('current')
            combat_state_doc = combat_state_ref.get()
            
            if not combat_state_doc.exists:
                raise HTTPException(
                    status_code=400,
                    detail='Combat not started. Roll initiative first.'
                )
            
            combat_state_data = combat_state_doc.to_dict()
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
                from ..db.database import get_database
                db = get_database()
                
                # Get combat state
                combat_state = db.execute(
                    'SELECT * FROM combat_state WHERE session_id = ?',
                    (session_id_int,)
                ).fetchone()
                
                if not combat_state:
                    return saved_event
                
                # Get current turn character
                current_char_id_int = combat_state['current_turn_character_id']
                if not current_char_id_int:
                    return saved_event
                
                # Get current turn order
                current_turn = db.execute(
                    'SELECT turn_order FROM initiative_order WHERE session_id = ? AND character_id = ?',
                    (session_id_int, current_char_id_int)
                ).fetchone()
                
                if not current_turn:
                    return saved_event
                
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
            
            return saved_event
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling turn advance event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class RoundStartEventType(EventType):
    """Event type for round start."""
    
    def get_name(self) -> str:
        return "round_start"
    
    def get_prompt_instructions(self) -> str:
        return """ROUND START EVENTS:
- Detect when a new round of combat begins
- Look for phrases like "round X begins", "start of round X", "new round", "round X starts"
- This event increments the round counter and optionally resets to first character
- Extract the exact text segment that describes the round start"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'round_number': int,  # Optional, will use current + 1 if not provided
            'type': str,  # Should be "round_start"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate round start event data."""
        if event_data.get('type') != 'round_start':
            logger.warning(f"Invalid type for round start event: {event_data.get('type')}")
            return False
        
        if 'round_number' in event_data and not isinstance(event_data['round_number'], int):
            try:
                event_data['round_number'] = int(event_data['round_number'])
            except (ValueError, TypeError):
                logger.warning(f"Invalid round_number type: {event_data['round_number']}")
                return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle round start: save to Firestore and update round counter in Firestore."""
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'round_start',
                event_data
            )
            
            # Update combat state in Firestore
            combat_state_ref = session_ref.collection('combat_state').document('current')
            combat_state_doc = combat_state_ref.get()
            
            if not combat_state_doc.exists:
                # Initialize combat state
                combat_state_ref.set({
                    'is_active': True,
                    'current_round': 1,
                    'current_turn_character_id': None,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                current_round = 1
            else:
                combat_state_data = combat_state_doc.to_dict()
                current_round = combat_state_data.get('current_round', 1)
            
            # Determine new round number
            new_round = event_data.get('round_number')
            if not new_round:
                new_round = current_round + 1
            
            # Get first character in initiative order
            initiative_order_ref = session_ref.collection('initiative_order')
            all_orders = list(initiative_order_ref.stream())
            
            first_char_id = None
            first_turn_order = None
            for doc in all_orders:
                data = doc.to_dict()
                turn_order = data.get('turn_order', 0)
                if first_turn_order is None or turn_order < first_turn_order:
                    first_char_id = data.get('character_id')
                    first_turn_order = turn_order
            
            # Update combat state
            if first_char_id:
                combat_state_ref.update({
                    'current_round': new_round,
                    'current_turn_character_id': first_char_id,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            else:
                combat_state_ref.update({
                    'current_round': new_round,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # Also try to update SQLite for legacy compatibility (if session_id can be converted)
            try:
                session_id_int = int(session_id)
                from ..db.database import get_database
                db = get_database()
                
                # Get or create combat state
                combat_state = db.execute(
                    'SELECT * FROM combat_state WHERE session_id = ?',
                    (session_id_int,)
                ).fetchone()
                
                if not combat_state:
                    db.execute(
                        'INSERT INTO combat_state (session_id, current_round, is_active) VALUES (?, 1, 1)',
                        (session_id_int,)
                    )
                    current_round = 1
                else:
                    current_round = combat_state['current_round']
                
                # Determine new round number
                new_round = event_data.get('round_number')
                if not new_round:
                    new_round = current_round + 1
                
                # Get first character in initiative order
                first_char = db.execute(
                    '''SELECT character_id FROM initiative_order 
                       WHERE session_id = ? 
                       ORDER BY turn_order ASC LIMIT 1''',
                    (session_id_int,)
                ).fetchone()
                
                # Update combat state
                if first_char:
                    db.execute(
                        '''UPDATE combat_state 
                           SET current_round = ?, current_turn_character_id = ? 
                           WHERE session_id = ?''',
                        (new_round, first_char['character_id'], session_id_int)
                    )
                else:
                    db.execute(
                        'UPDATE combat_state SET current_round = ? WHERE session_id = ?',
                        (new_round, session_id_int)
                    )
                
                db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (Firestore is the source of truth)
                pass
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling round start event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


# Registry functions

def register_event_type(event_type: EventType) -> None:
    """Register an event type in the registry.
    
    Args:
        event_type: An instance of an EventType subclass
    """
    name = event_type.get_name()
    if name in _event_registry:
        logger.warning(f"Event type '{name}' is already registered. Overwriting.")
    _event_registry[name] = event_type
    logger.info(f"Registered event type: {name}")


def get_registered_events() -> Dict[str, EventType]:
    """Get all registered event types.
    
    Returns:
        Dictionary mapping event type names to EventType instances
    """
    return _event_registry.copy()


def get_event_type_by_name(name: str) -> Optional[EventType]:
    """Get an event type by name (case-insensitive lookup).
    
    Args:
        name: The event type name (case-insensitive)
        
    Returns:
        EventType instance if found, None otherwise
    """
    if not name:
        return None
    
    # First try exact match (most common case)
    if name in _event_registry:
        return _event_registry[name]
    
    # Then try case-insensitive lookup
    name_lower = name.lower()
    for registered_name, event_type in _event_registry.items():
        if registered_name.lower() == name_lower:
            return event_type
    
    return None


# Register default event types
register_event_type(DamageEventType())
register_event_type(HealingEventType())

class StatusConditionAppliedEventType(EventType):
    """Event type for status conditions being applied to characters."""
    
    def get_name(self) -> str:
        return "status_condition_applied"
    
    def get_prompt_instructions(self) -> str:
        return """STATUS CONDITION APPLIED EVENTS:
- Detect when a character gains a status condition (ailment, buff, debuff, etc.)
- Look for phrases like "becomes poisoned", "is stunned", "gains advantage", "is blinded", "[character] is [condition]"
- Common conditions: poisoned, stunned, paralyzed, blinded, deafened, charmed, frightened, grappled, prone, restrained, unconscious
- Identify the character name and the condition name
- If a duration is mentioned (e.g., "for 10 minutes", "until end of turn"), include it
- Extract the exact text segment that describes the condition application"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'condition_name': str,
            'type': str,  # Should be "status_condition_applied"
            'duration_minutes': int,  # Optional
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate status condition applied event data."""
        schema = self.get_schema()
        optional_fields = {'character_name', 'transcript_segment', 'duration_minutes'}
        
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            if field == 'type' and event_data[field] != 'status_condition_applied':
                logger.warning(f"Invalid type for status condition applied event: {event_data[field]}")
                return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
            elif field == 'duration_minutes' and field in event_data:
                if not isinstance(event_data[field], int):
                    try:
                        event_data[field] = int(event_data[field])
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid duration_minutes type: {event_data[field]}")
                        return False
                if event_data[field] < 0:
                    logger.warning(f"Duration must be non-negative: {event_data[field]}")
                    return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle status condition applied: save to Firestore and add to active conditions in SQLite."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'status_condition_applied',
                event_data,
                character_id,
                character_name
            )
            
            # Status conditions are still in SQLite, so convert session_id to int if possible
            from ..db.database import get_database
            db = get_database()
            
            try:
                session_id_int = int(session_id)
                character_id_int = int(character_id)
            except (ValueError, TypeError):
                logger.warning(f"Cannot convert session_id {session_id} or character_id {character_id} to int for status condition management")
                return saved_event
            
            # Calculate expiration time if duration is provided
            expires_at = None
            duration_minutes = event_data.get('duration_minutes')
            if duration_minutes and duration_minutes > 0:
                import datetime
                expires_at = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
            
            # Add to active status conditions in SQLite (replace if already exists)
            db.execute(
                '''INSERT OR REPLACE INTO active_status_conditions 
                   (session_id, character_id, condition_name, applied_at, expires_at, duration_minutes)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)''',
                (
                    session_id_int,
                    character_id_int,
                    event_data['condition_name'],
                    expires_at.strftime('%Y-%m-%d %H:%M:%S') if expires_at else None,
                    duration_minutes
                )
            )
            
            db.commit()
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling status condition applied event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class StatusConditionRemovedEventType(EventType):
    """Event type for status conditions being removed from characters."""
    
    def get_name(self) -> str:
        return "status_condition_removed"
    
    def get_prompt_instructions(self) -> str:
        return """STATUS CONDITION REMOVED EVENTS:
- Detect when a character loses a status condition (ailment, buff, debuff, etc.)
- Look for phrases like "no longer poisoned", "shakes off the stun", "condition ends", "[character] is no longer [condition]"
- Identify the character name and the condition name that was removed
- Extract the exact text segment that describes the condition removal"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'condition_name': str,
            'type': str,  # Should be "status_condition_removed"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate status condition removed event data."""
        schema = self.get_schema()
        optional_fields = {'character_name', 'transcript_segment'}
        
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            if field == 'type' and event_data[field] != 'status_condition_removed':
                logger.warning(f"Invalid type for status condition removed event: {event_data[field]}")
                return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle status condition removed: save to Firestore and remove from active conditions in SQLite."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'status_condition_removed',
                event_data,
                character_id,
                character_name
            )
            
            # Status conditions are still in SQLite, so convert session_id to int if possible
            from ..db.database import get_database
            db = get_database()
            
            try:
                session_id_int = int(session_id)
                character_id_int = int(character_id)
            except (ValueError, TypeError):
                logger.warning(f"Cannot convert session_id {session_id} or character_id {character_id} to int for status condition management")
                return saved_event
            
            # Remove from active status conditions in SQLite
            db.execute(
                '''DELETE FROM active_status_conditions 
                   WHERE session_id = ? AND character_id = ? AND condition_name = ?''',
                (
                    session_id_int,
                    character_id_int,
                    event_data['condition_name']
                )
            )
            
            db.commit()
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling status condition removed event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class CombatEndEventType(EventType):
    """Event type for ending combat/initiative tracking."""
    
    def get_name(self) -> str:
        return "combat_end"
    
    def get_prompt_instructions(self) -> str:
        return """COMBAT END EVENTS:
- Detect when combat ends and initiative order is no longer being tracked
- Look for phrases like "combat is over", "you are out of initiative", "no more enemies in sight", 
  "combat ends", "initiative ends", "the battle is over", "all enemies defeated"
- This event deactivates combat tracking and clears the current turn
- Extract the exact text segment that describes the combat ending"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'type': str,  # Should be "combat_end"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate combat end event data."""
        if event_data.get('type') != 'combat_end':
            logger.warning(f"Invalid type for combat end event: {event_data.get('type')}")
            return False
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle combat end: save to Firestore and deactivate combat state in Firestore."""
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'combat_end',
                event_data
            )
            
            # Update combat state in Firestore
            combat_state_ref = session_ref.collection('combat_state').document('current')
            combat_state_doc = combat_state_ref.get()
            
            if combat_state_doc.exists:
                # Deactivate combat: set is_active to False and clear current turn
                combat_state_ref.update({
                    'is_active': False,
                    'current_turn_character_id': None,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
                # Clear initiative order when combat ends
                initiative_order_ref = session_ref.collection('initiative_order')
                for doc in initiative_order_ref.stream():
                    doc.reference.delete()
                logger.info(f"Combat ended for session {session_id}. Combat state deactivated and initiative order cleared.")
            else:
                # No combat state exists, that's fine - combat wasn't active
                # But still clear any leftover initiative order
                initiative_order_ref = session_ref.collection('initiative_order')
                for doc in initiative_order_ref.stream():
                    doc.reference.delete()
                logger.info(f"Combat end event for session {session_id}, but no active combat state found. Initiative order cleared.")
            
            # Also try to update SQLite for legacy compatibility (if session_id can be converted)
            try:
                session_id_int = int(session_id)
                from ..db.database import get_database
                db = get_database()
                
                # Get or create combat state
                combat_state = db.execute(
                    'SELECT * FROM combat_state WHERE session_id = ?',
                    (session_id_int,)
                ).fetchone()
                
                if combat_state:
                    # Deactivate combat: set is_active to 0 and clear current turn
                    db.execute(
                        '''UPDATE combat_state 
                           SET is_active = 0, current_turn_character_id = NULL 
                           WHERE session_id = ?''',
                        (session_id_int,)
                    )
                    # Clear initiative order when combat ends
                    db.execute(
                        'DELETE FROM initiative_order WHERE session_id = ?',
                        (session_id_int,)
                    )
                else:
                    # No combat state exists, but still clear any leftover initiative order
                    db.execute(
                        'DELETE FROM initiative_order WHERE session_id = ?',
                        (session_id_int,)
                    )
                
                db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (Firestore is the source of truth)
                pass
            
            return saved_event
            
        except Exception as e:
            logger.error(f"Error handling combat end event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class BuffDebuffAppliedEventType(EventType):
    """Event type for buffs/debuffs being applied to characters."""
    
    def get_name(self) -> str:
        return "buff_debuff_applied"
    
    def get_prompt_instructions(self) -> str:
        return """BUFF/DEBUFF APPLIED EVENTS:
- Detect when a character gains a temporary buff or debuff that modifies stats
- Look for phrases like "gains +2 AC", "has advantage on attack rolls", "gets +1 to saving throws", 
  "AC increases by 2", "attack bonus of +3", "saving throw penalty of -2", "speed reduced by 10 feet"
- Identify stat modifications: AC, attack_rolls, damage_rolls, saving_throws, skill_checks, speed, etc.
- Determine if it's a buff (positive effect) or debuff (negative effect)
- If a duration is mentioned (e.g., "for 1 minute", "until end of turn", "for 10 rounds"), include it
- Extract the exact text segment that describes the effect application
- Common examples: "Bless" (+1d4 to attack rolls and saving throws), "Shield of Faith" (+2 AC), 
  "Haste" (+2 AC, double speed), "Bane" (-1d4 to attack rolls and saving throws)"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'effect_name': str,  # e.g., "Bless", "Shield of Faith", "Haste"
            'effect_type': str,  # 'buff' or 'debuff'
            'stat_modifications': dict,  # e.g., {"ac": 2, "attack_rolls": 1, "saving_throws": -1}
            'stacking_rule': str,  # 'none', 'stack', 'replace', 'highest' (default: 'replace')
            'type': str,  # Should be "buff_debuff_applied"
            'duration_minutes': int,  # Optional
            'source': str,  # Optional: spell name, item name, etc.
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate buff/debuff applied event data."""
        schema = self.get_schema()
        optional_fields = {'character_name', 'transcript_segment', 'duration_minutes', 'source', 'stacking_rule'}
        
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            if field == 'type' and event_data[field] != 'buff_debuff_applied':
                logger.warning(f"Invalid type for buff/debuff applied event: {event_data[field]}")
                return False
            elif field == 'effect_type' and event_data.get(field) not in ['buff', 'debuff']:
                logger.warning(f"Invalid effect_type: {event_data.get(field)}. Must be 'buff' or 'debuff'")
                return False
            elif field == 'stat_modifications':
                if not isinstance(event_data.get(field), dict):
                    logger.warning(f"stat_modifications must be a dictionary")
                    return False
            elif field == 'stacking_rule' and field in event_data:
                if event_data[field] not in ['none', 'stack', 'replace', 'highest']:
                    logger.warning(f"Invalid stacking_rule: {event_data[field]}")
                    return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
            elif field == 'duration_minutes' and field in event_data:
                if not isinstance(event_data[field], int):
                    try:
                        event_data[field] = int(event_data[field])
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid duration_minutes type: {event_data[field]}")
                        return False
                if event_data[field] < 0:
                    logger.warning(f"Duration must be non-negative: {event_data[field]}")
                    return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle buff/debuff applied: save event to Firestore and add to active effects in SQLite."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'buff_debuff_applied',
                event_data,
                character_id,
                character_name
            )
            
            # Also try to update SQLite for active effects tracking (if session_id can be converted)
            try:
                import json
                import datetime
                session_id_int = int(session_id)
                character_id_int = int(character_id)
                from ..db.database import get_database
                db = get_database()
                
                # Calculate expiration time if duration is provided
                expires_at = None
                duration_minutes = event_data.get('duration_minutes')
                if duration_minutes and duration_minutes > 0:
                    expires_at = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
                
                # Get stacking rule (default: 'replace')
                stacking_rule = event_data.get('stacking_rule', 'replace')
                
                # Check if effect already exists
                existing_effect = db.execute(
                    '''SELECT * FROM active_buff_debuffs 
                       WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
                    (session_id_int, character_id_int, event_data['effect_name'])
                ).fetchone()
                
                # Apply stacking rules
                if existing_effect:
                    if stacking_rule == 'none':
                        # Don't apply if already exists
                        logger.info(f"Effect {event_data['effect_name']} already exists with stacking_rule='none', skipping")
                        # Still create event for history
                        cursor = db.execute(
                            '''INSERT INTO buff_debuff_events 
                               (session_id, character_id, effect_name, effect_type, action, stat_modifications, stacking_rule, duration_minutes, transcript_segment)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                session_id_int,
                                character_id_int,
                                event_data['effect_name'],
                                event_data['effect_type'],
                                'applied',
                                json.dumps(event_data['stat_modifications']),
                                stacking_rule,
                                duration_minutes,
                                event_data.get('transcript_segment')
                            )
                        )
                        db.commit()
                    elif stacking_rule == 'replace':
                        # Replace existing effect
                        pass  # Will update below
                    elif stacking_rule == 'highest':
                        # Only replace if new effect has higher values
                        existing_mods = json.loads(existing_effect['stat_modifications'])
                        new_mods = event_data['stat_modifications']
                        should_replace = False
                        for stat, value in new_mods.items():
                            if stat in existing_mods:
                                # Compare absolute values for highest
                                if abs(value) > abs(existing_mods[stat]):
                                    should_replace = True
                                    break
                            else:
                                should_replace = True
                                break
                        if not should_replace:
                            logger.info(f"Existing effect {event_data['effect_name']} has higher values, keeping existing")
                            cursor = db.execute(
                                '''INSERT INTO buff_debuff_events 
                                   (session_id, character_id, effect_name, effect_type, action, stat_modifications, stacking_rule, duration_minutes, transcript_segment)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (
                                    session_id_int,
                                    character_id_int,
                                    event_data['effect_name'],
                                    event_data['effect_type'],
                                    'applied',
                                    json.dumps(event_data['stat_modifications']),
                                    stacking_rule,
                                    duration_minutes,
                                    event_data.get('transcript_segment')
                                )
                            )
                            db.commit()
                    elif stacking_rule == 'stack':
                        # Stack effects - combine stat modifications
                        existing_mods = json.loads(existing_effect['stat_modifications'])
                        new_mods = event_data['stat_modifications']
                        combined_mods = existing_mods.copy()
                        for stat, value in new_mods.items():
                            if stat in combined_mods:
                                combined_mods[stat] = combined_mods[stat] + value
                            else:
                                combined_mods[stat] = value
                        event_data['stat_modifications'] = combined_mods
                        # Update expiration to the later of the two
                        existing_expires = existing_effect['expires_at']
                        if existing_expires and expires_at:
                            expires_at_str = existing_expires if isinstance(existing_expires, str) else existing_expires.strftime('%Y-%m-%d %H:%M:%S')
                            new_expires_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
                            if existing_expires > expires_at:
                                expires_at = datetime.datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S') if isinstance(existing_expires, str) else existing_expires
                
                # Insert buff/debuff event
                cursor = db.execute(
                    '''INSERT INTO buff_debuff_events 
                       (session_id, character_id, effect_name, effect_type, action, stat_modifications, stacking_rule, duration_minutes, transcript_segment)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        session_id_int,
                        character_id_int,
                        event_data['effect_name'],
                        event_data['effect_type'],
                        'applied',
                        json.dumps(event_data['stat_modifications']),
                        stacking_rule,
                        duration_minutes,
                        event_data.get('transcript_segment')
                    )
                )
                
                # Add or update active buff/debuff
                db.execute(
                    '''INSERT OR REPLACE INTO active_buff_debuffs 
                       (session_id, character_id, effect_name, effect_type, stat_modifications, stacking_rule, applied_at, expires_at, duration_minutes, source)
                       VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)''',
                    (
                        session_id_int,
                        character_id_int,
                        event_data['effect_name'],
                        event_data['effect_type'],
                        json.dumps(event_data['stat_modifications']),
                        stacking_rule,
                        expires_at.strftime('%Y-%m-%d %H:%M:%S') if expires_at else None,
                        duration_minutes,
                        event_data.get('source')
                    )
                )
                
                db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (active effects tracking unavailable)
                pass
            
            return saved_event
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling buff/debuff applied event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class BuffDebuffRemovedEventType(EventType):
    """Event type for buffs/debuffs being removed from characters."""
    
    def get_name(self) -> str:
        return "buff_debuff_removed"
    
    def get_prompt_instructions(self) -> str:
        return """BUFF/DEBUFF REMOVED EVENTS:
- Detect when a character loses a temporary buff or debuff
- Look for phrases like "Bless ends", "no longer has +2 AC", "effect wears off", 
  "[character] loses [effect]"
- Identify the character name and the effect name that was removed
- Extract the exact text segment that describes the effect removal"""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'character_name': str,
            'effect_name': str,
            'type': str,  # Should be "buff_debuff_removed"
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        """Validate buff/debuff removed event data."""
        schema = self.get_schema()
        optional_fields = {'character_name', 'transcript_segment'}
        
        for field, field_type in schema.items():
            if field not in event_data and field not in optional_fields:
                logger.warning(f"Missing required field: {field}")
                return False
            
            if field == 'type' and event_data[field] != 'buff_debuff_removed':
                logger.warning(f"Invalid type for buff/debuff removed event: {event_data[field]}")
                return False
            elif field == 'character_id':
                # Accept both int and str (Firestore uses strings, SQLite uses ints)
                if not isinstance(event_data[field], (int, str)):
                    logger.warning(f"Invalid character_id type: {type(event_data[field])}, value: {event_data[field]}")
                    return False
                # Keep as-is (string for Firestore, int for SQLite compatibility)
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Handle buff/debuff removed: save event to Firestore and remove from active effects in SQLite."""
        character_id = str(event_data['character_id'])
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'buff_debuff_removed',
                event_data,
                character_id,
                character_name
            )
            
            # Also try to update SQLite for active effects tracking (if session_id can be converted)
            try:
                session_id_int = int(session_id)
                character_id_int = int(character_id)
                from ..db.database import get_database
                db = get_database()
                
                # Insert buff/debuff event
                cursor = db.execute(
                    '''INSERT INTO buff_debuff_events 
                       (session_id, character_id, effect_name, effect_type, action, transcript_segment)
                       VALUES (?, ?, ?, 
                           (SELECT effect_type FROM active_buff_debuffs 
                            WHERE session_id = ? AND character_id = ? AND effect_name = ? LIMIT 1),
                           ?, ?)''',
                    (
                        session_id_int,
                        character_id_int,
                        event_data['effect_name'],
                        session_id_int,
                        character_id_int,
                        event_data['effect_name'],
                        'removed',
                        event_data.get('transcript_segment')
                    )
                )
                
                # Remove from active buffs/debuffs
                db.execute(
                    '''DELETE FROM active_buff_debuffs 
                       WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
                    (
                        session_id_int,
                        character_id_int,
                        event_data['effect_name']
                    )
                )
                
                db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (active effects tracking unavailable)
                pass
            
            return saved_event
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling buff/debuff removed event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


class SpellCastEventType(EventType):
    """Event type for spell casting - tracks spell slot usage."""
    
    def get_name(self) -> str:
        return "spell_cast"
    
    def get_prompt_instructions(self) -> str:
        return """SPELL CAST EVENTS:
- Detect when a character casts a spell
- Look for phrases like "casts [spell name]", "I cast [spell name]", "[character] casts [spell name]",
  "uses [spell name]", "casts a level [X] spell", "casts [spell name] at [X]th level"
- Extract the spell name (e.g., "Fireball", "Cure Wounds", "Bless", "Shield")
- Extract the spell level (0-9, where 0 is a cantrip and doesn't use spell slots)
- If spell level is not explicitly mentioned, infer from context:
  * Cantrips: "Eldritch Blast", "Guidance", "Mage Hand", "Fire Bolt" (level 0)
  * Common 1st level: "Cure Wounds", "Shield", "Magic Missile", "Burning Hands"
  * Common 2nd level: "Scorching Ray", "Misty Step", "Hold Person"
  * Common 3rd level: "Fireball", "Counterspell", "Revivify"
  * If uncertain, default to level 1
- If a spell is cast "at a higher level" (e.g., "Cure Wounds at 3rd level"), use that level
- Extract the exact text segment that describes the spell cast
- Note: Only track spell slot usage (level 1-9). Cantrips (level 0) don't use spell slots."""
    
    def get_schema(self) -> Dict[str, Any]:
        return {
            'character_id': int,
            'spell_name': str,
            'spell_level': int,  # 0-9, where 0 is cantrip
            'transcript_segment': str
        }
    
    def validate(self, event_data: Dict[str, Any]) -> bool:
        required_fields = ['character_id', 'spell_name', 'spell_level']
        if not all(field in event_data for field in required_fields):
            return False
        
        # Accept both int and str (Firestore uses strings, SQLite uses ints)
        if not isinstance(event_data['character_id'], (int, str)):
            return False
        
        if not isinstance(event_data['spell_name'], str) or not event_data['spell_name'].strip():
            return False
        
        spell_level = event_data['spell_level']
        if not isinstance(spell_level, int) or spell_level < 0 or spell_level > 9:
            return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: str,
        user_id: str,
        db_firestore: Any,
        session_ref: Any
    ) -> Dict[str, Any]:
        """Process spell cast event: save event to Firestore and update spell slot usage in SQLite."""
        character_id = str(event_data.get('character_id'))
        spell_level = event_data.get('spell_level')
        spell_name = event_data.get('spell_name')
        
        # Verify character is in the session (from Firestore)
        session_character_ref = session_ref.collection('session_characters').document(character_id)
        session_character_doc = session_character_ref.get()
        
        if not session_character_doc.exists:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Get character name
        character_ref = db_firestore.collection('users').document(user_id).collection('characters').document(character_id)
        character_doc = character_ref.get()
        character_name = event_data.get('character_name', 'Unknown')
        if character_doc.exists:
            char_data = character_doc.to_dict()
            character_name = char_data.get('name', character_name)
        
        try:
            # Save event to Firestore
            saved_event = save_event_to_firestore(
                session_ref,
                'spell_cast',
                event_data,
                character_id,
                character_name
            )
            
            # Also try to update SQLite for spell slot tracking (if session_id can be converted)
            try:
                session_id_int = int(session_id)
                character_id_int = int(character_id)
                from ..db.database import get_database
                db = get_database()
                
                # Update spell slot usage (only for level 1-9, cantrips don't use slots)
                if spell_level > 0:
                    # Insert or update spell slot usage
                    db.execute('''
                        INSERT INTO character_spell_slots (
                            session_id, character_id, spell_level, slots_used
                        ) VALUES (?, ?, ?, 1)
                        ON CONFLICT(session_id, character_id, spell_level) 
                        DO UPDATE SET slots_used = slots_used + 1
                    ''', (session_id_int, character_id_int, spell_level))
                    db.commit()
            except (ValueError, TypeError):
                # Can't convert to int, skip SQLite update (spell slots tracking unavailable)
                pass
            
            return saved_event
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error handling spell cast event: {e}")
            raise HTTPException(status_code=500, detail='Internal server error')


# Phase 1: Register initiative event types
register_event_type(InitiativeRollEventType())
register_event_type(TurnAdvanceEventType())
register_event_type(RoundStartEventType())
register_event_type(CombatEndEventType())

# Phase 2: Register status condition event types
register_event_type(StatusConditionAppliedEventType())
register_event_type(StatusConditionRemovedEventType())

# Phase 3: Register buff/debuff event types
register_event_type(BuffDebuffAppliedEventType())
register_event_type(BuffDebuffRemovedEventType())

# Phase 4: Register spell cast event type
register_event_type(SpellCastEventType())

