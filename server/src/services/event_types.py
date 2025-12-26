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

logger = logging.getLogger(__name__)

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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Processes the event (e.g., save to database, update character state).
        
        Args:
            event_data: The validated event data
            session_id: The session ID
            user_id: The user ID (for authorization)
            db: Database connection
            
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
            elif field == 'amount' and event_data[field] <= 0:
                logger.warning(f"Amount must be positive: {event_data[field]}")
                return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle damage event: save to database and update character HP."""
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Verify character belongs to user
        character = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (event_data['character_id'], user_id)
        ).fetchone()
        
        if not character:
            raise HTTPException(
                status_code=404,
                detail='Character not found'
            )
        
        # Use transaction to ensure both operations succeed
        try:
            # Calculate new HP (damage reduces HP, minimum 0)
            current_hp = session_character['current_hp']
            new_hp = max(0, current_hp - event_data['amount'])
            
            # Insert damage event
            cursor = db.execute(
                '''INSERT INTO damage_events 
                   (session_id, character_id, amount, type, transcript_segment)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['amount'],
                    'damage',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Update character's current HP
            db.execute(
                'UPDATE session_characters SET current_hp = ? WHERE session_id = ? AND character_id = ?',
                (new_hp, session_id, event_data['character_id'])
            )
            
            # Commit both operations together
            db.commit()
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    de.*,
                    c.name as character_name
                FROM damage_events de
                JOIN characters c ON de.character_id = c.id
                WHERE de.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
            elif field == 'amount' and event_data[field] <= 0:
                logger.warning(f"Amount must be positive: {event_data[field]}")
                return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle healing event: save to database and update character HP."""
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        # Verify character belongs to user
        character = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (event_data['character_id'], user_id)
        ).fetchone()
        
        if not character:
            raise HTTPException(
                status_code=404,
                detail='Character not found'
            )
        
        # Use transaction to ensure both operations succeed
        try:
            # Calculate new HP (healing increases HP, maximum max_hp)
            current_hp = session_character['current_hp']
            max_hp = character['max_hp']
            new_hp = min(max_hp, current_hp + event_data['amount'])
            
            # Insert healing event
            cursor = db.execute(
                '''INSERT INTO damage_events 
                   (session_id, character_id, amount, type, transcript_segment)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['amount'],
                    'healing',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Update character's current HP
            db.execute(
                'UPDATE session_characters SET current_hp = ? WHERE session_id = ? AND character_id = ?',
                (new_hp, session_id, event_data['character_id'])
            )
            
            # Commit both operations together
            db.commit()
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    de.*,
                    c.name as character_name
                FROM damage_events de
                JOIN characters c ON de.character_id = c.id
                WHERE de.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle initiative roll: save event and update initiative order."""
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        try:
            # Insert combat event
            cursor = db.execute(
                '''INSERT INTO combat_events 
                   (session_id, character_id, event_type, initiative_value, transcript_segment)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    'initiative_roll',
                    event_data['initiative_value'],
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Get or create combat state
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if not combat_state:
                # Initialize combat state
                db.execute(
                    '''INSERT INTO combat_state (session_id, current_round, is_active)
                       VALUES (?, 1, 1)''',
                    (session_id,)
                )
            else:
                # If combat state exists but is inactive, reactivate it
                # This handles the case where combat ended and a new initiative roll starts combat again
                if not combat_state['is_active']:
                    # Clear old initiative order when starting a new combat
                    db.execute(
                        'DELETE FROM initiative_order WHERE session_id = ?',
                        (session_id,)
                    )
                    db.execute(
                        '''UPDATE combat_state 
                           SET is_active = 1, current_round = 1, current_turn_character_id = NULL
                           WHERE session_id = ?''',
                        (session_id,)
                    )
                    logger.info(f"Reactivating combat for session {session_id} after new initiative roll.")
            
            # Update or insert initiative order
            db.execute(
                '''INSERT OR REPLACE INTO initiative_order 
                   (session_id, character_id, initiative_value, turn_order)
                   VALUES (?, ?, ?, 
                       COALESCE((SELECT MAX(turn_order) FROM initiative_order WHERE session_id = ?), 0) + 1)''',
                (session_id, event_data['character_id'], event_data['initiative_value'], session_id)
            )
            
            # Reorder initiative by initiative_value (descending)
            # Get all initiative entries for this session
            initiative_rows = db.execute(
                '''SELECT character_id, initiative_value 
                   FROM initiative_order 
                   WHERE session_id = ? 
                   ORDER BY initiative_value DESC, character_id ASC''',
                (session_id,)
            ).fetchall()
            
            # Update turn_order based on sorted initiative
            for idx, row in enumerate(initiative_rows, start=1):
                db.execute(
                    'UPDATE initiative_order SET turn_order = ? WHERE session_id = ? AND character_id = ?',
                    (idx, session_id, row['character_id'])
                )
            
            # If no current turn is set, set it to the first character
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if combat_state and not combat_state['current_turn_character_id']:
                first_char = db.execute(
                    '''SELECT character_id FROM initiative_order 
                       WHERE session_id = ? 
                       ORDER BY turn_order ASC LIMIT 1''',
                    (session_id,)
                ).fetchone()
                
                if first_char:
                    db.execute(
                        'UPDATE combat_state SET current_turn_character_id = ? WHERE session_id = ?',
                        (first_char['character_id'], session_id)
                    )
            
            db.commit()
            
            # Get the created event
            event_row = db.execute('''
                SELECT 
                    ce.*,
                    c.name as character_name
                FROM combat_events ce
                JOIN characters c ON ce.character_id = c.id
                WHERE ce.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle turn advance: move to next character in initiative order.
        
        Includes deduplication: if a turn advance occurred recently (within 5 seconds),
        skip processing to avoid duplicate advances from phrases like "I end my turn"
        followed by "beginning the next turn".
        """
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        try:
            # Deduplication: Check for recent turn advance events (within 5 seconds)
            # This prevents duplicate turn advances from phrases like "I end my turn" 
            # followed by "beginning the next turn" which Gemini might detect as two events
            import datetime
            time_window_seconds = 5
            cutoff_time = datetime.datetime.now() - datetime.timedelta(seconds=time_window_seconds)
            
            # SQLite stores timestamps as strings, so we need to compare as strings
            # Format: 'YYYY-MM-DD HH:MM:SS'
            cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
            
            recent_turn_advance = db.execute(
                '''SELECT id, timestamp FROM combat_events 
                   WHERE session_id = ? 
                   AND event_type = 'turn_advance'
                   AND datetime(timestamp) > datetime(?)
                   ORDER BY timestamp DESC
                   LIMIT 1''',
                (session_id, cutoff_str)
            ).fetchone()
            
            if recent_turn_advance:
                logger.info(
                    f"Turn advance deduplication: Skipping duplicate turn advance. "
                    f"Last turn advance was {recent_turn_advance['timestamp']} "
                    f"(within {time_window_seconds} second window)"
                )
                # Return the recent event instead of creating a new one
                # This prevents the turn from advancing twice
                event_row = db.execute(
                    'SELECT * FROM combat_events WHERE id = ?',
                    (recent_turn_advance['id'],)
                ).fetchone()
                return dict(event_row)
            
            # Insert combat event
            cursor = db.execute(
                '''INSERT INTO combat_events 
                   (session_id, event_type, transcript_segment)
                   VALUES (?, ?, ?)''',
                (
                    session_id,
                    'turn_advance',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Get combat state
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if not combat_state:
                raise HTTPException(
                    status_code=400,
                    detail='Combat not started. Roll initiative first.'
                )
            
            # Get current turn character
            current_char_id = combat_state['current_turn_character_id']
            if not current_char_id:
                raise HTTPException(
                    status_code=400,
                    detail='No current turn set. Roll initiative first.'
                )
            
            # Get current turn order
            current_turn = db.execute(
                'SELECT turn_order FROM initiative_order WHERE session_id = ? AND character_id = ?',
                (session_id, current_char_id)
            ).fetchone()
            
            if not current_turn:
                raise HTTPException(
                    status_code=400,
                    detail='Current character not in initiative order'
                )
            
            # Get next character in order
            next_char = db.execute(
                '''SELECT character_id FROM initiative_order 
                   WHERE session_id = ? AND turn_order > ?
                   ORDER BY turn_order ASC LIMIT 1''',
                (session_id, current_turn['turn_order'])
            ).fetchone()
            
            if next_char:
                # Move to next character
                db.execute(
                    'UPDATE combat_state SET current_turn_character_id = ? WHERE session_id = ?',
                    (next_char['character_id'], session_id)
                )
            else:
                # Wrap around to first character and increment round
                first_char = db.execute(
                    '''SELECT character_id FROM initiative_order 
                       WHERE session_id = ? 
                       ORDER BY turn_order ASC LIMIT 1''',
                    (session_id,)
                ).fetchone()
                
                if first_char:
                    db.execute(
                        '''UPDATE combat_state 
                           SET current_turn_character_id = ?, current_round = current_round + 1 
                           WHERE session_id = ?''',
                        (first_char['character_id'], session_id)
                    )
            
            db.commit()
            
            # Get the created event
            event_row = db.execute(
                'SELECT * FROM combat_events WHERE id = ?',
                (event_id,)
            ).fetchone()
            
            return dict(event_row)
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle round start: increment round and set to first character."""
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        try:
            # Get or create combat state
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if not combat_state:
                # Initialize combat state
                db.execute(
                    'INSERT INTO combat_state (session_id, current_round, is_active) VALUES (?, 1, 1)',
                    (session_id,)
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
                (session_id,)
            ).fetchone()
            
            # Insert combat event
            cursor = db.execute(
                '''INSERT INTO combat_events 
                   (session_id, event_type, round_number, transcript_segment)
                   VALUES (?, ?, ?, ?)''',
                (
                    session_id,
                    'round_start',
                    new_round,
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Update combat state
            if first_char:
                db.execute(
                    '''UPDATE combat_state 
                       SET current_round = ?, current_turn_character_id = ? 
                       WHERE session_id = ?''',
                    (new_round, first_char['character_id'], session_id)
                )
            else:
                db.execute(
                    'UPDATE combat_state SET current_round = ? WHERE session_id = ?',
                    (new_round, session_id)
                )
            
            db.commit()
            
            # Get the created event
            event_row = db.execute(
                'SELECT * FROM combat_events WHERE id = ?',
                (event_id,)
            ).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle status condition applied: save event and add to active conditions."""
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        try:
            # Calculate expiration time if duration is provided
            expires_at = None
            duration_minutes = event_data.get('duration_minutes')
            if duration_minutes and duration_minutes > 0:
                import datetime
                expires_at = datetime.datetime.now() + datetime.timedelta(minutes=duration_minutes)
            
            # Insert status condition event
            cursor = db.execute(
                '''INSERT INTO status_condition_events 
                   (session_id, character_id, condition_name, action, duration_minutes, transcript_segment)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['condition_name'],
                    'applied',
                    duration_minutes,
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Add to active status conditions (replace if already exists)
            db.execute(
                '''INSERT OR REPLACE INTO active_status_conditions 
                   (session_id, character_id, condition_name, applied_at, expires_at, duration_minutes)
                   VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['condition_name'],
                    expires_at.strftime('%Y-%m-%d %H:%M:%S') if expires_at else None,
                    duration_minutes
                )
            )
            
            db.commit()
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    sce.*,
                    c.name as character_name
                FROM status_condition_events sce
                JOIN characters c ON sce.character_id = c.id
                WHERE sce.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle status condition removed: save event and remove from active conditions."""
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        try:
            # Insert status condition event
            cursor = db.execute(
                '''INSERT INTO status_condition_events 
                   (session_id, character_id, condition_name, action, transcript_segment)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['condition_name'],
                    'removed',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Remove from active status conditions
            db.execute(
                '''DELETE FROM active_status_conditions 
                   WHERE session_id = ? AND character_id = ? AND condition_name = ?''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['condition_name']
                )
            )
            
            db.commit()
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    sce.*,
                    c.name as character_name
                FROM status_condition_events sce
                JOIN characters c ON sce.character_id = c.id
                WHERE sce.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle combat end: deactivate combat state and clear current turn."""
        # Verify session belongs to user
        session = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')
        
        try:
            # Insert combat event
            cursor = db.execute(
                '''INSERT INTO combat_events 
                   (session_id, event_type, transcript_segment)
                   VALUES (?, ?, ?)''',
                (
                    session_id,
                    'combat_end',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Get or create combat state
            combat_state = db.execute(
                'SELECT * FROM combat_state WHERE session_id = ?',
                (session_id,)
            ).fetchone()
            
            if combat_state:
                # Deactivate combat: set is_active to 0 and clear current turn
                db.execute(
                    '''UPDATE combat_state 
                       SET is_active = 0, current_turn_character_id = NULL 
                       WHERE session_id = ?''',
                    (session_id,)
                )
                # Clear initiative order when combat ends
                db.execute(
                    'DELETE FROM initiative_order WHERE session_id = ?',
                    (session_id,)
                )
                logger.info(f"Combat ended for session {session_id}. Combat state deactivated and initiative order cleared.")
            else:
                # No combat state exists, that's fine - combat wasn't active
                # But still clear any leftover initiative order
                db.execute(
                    'DELETE FROM initiative_order WHERE session_id = ?',
                    (session_id,)
                )
                logger.info(f"Combat end event for session {session_id}, but no active combat state found. Initiative order cleared.")
            
            db.commit()
            
            # Get the created event
            event_row = db.execute(
                'SELECT * FROM combat_events WHERE id = ?',
                (event_id,)
            ).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle buff/debuff applied: save event and add to active effects with stacking logic."""
        import json
        import datetime
        
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        try:
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
                (session_id, event_data['character_id'], event_data['effect_name'])
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
                            session_id,
                            event_data['character_id'],
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
                    return dict(db.execute('SELECT * FROM buff_debuff_events WHERE id = ?', (cursor.lastrowid,)).fetchone())
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
                                session_id,
                                event_data['character_id'],
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
                        return dict(db.execute('SELECT * FROM buff_debuff_events WHERE id = ?', (cursor.lastrowid,)).fetchone())
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
                    session_id,
                    event_data['character_id'],
                    event_data['effect_name'],
                    event_data['effect_type'],
                    'applied',
                    json.dumps(event_data['stat_modifications']),
                    stacking_rule,
                    duration_minutes,
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Add or update active buff/debuff
            db.execute(
                '''INSERT OR REPLACE INTO active_buff_debuffs 
                   (session_id, character_id, effect_name, effect_type, stat_modifications, stacking_rule, applied_at, expires_at, duration_minutes, source)
                   VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
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
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    bde.*,
                    c.name as character_name
                FROM buff_debuff_events bde
                JOIN characters c ON bde.character_id = c.id
                WHERE bde.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
            elif field == 'character_id' and not isinstance(event_data[field], int):
                try:
                    event_data[field] = int(event_data[field])
                except (ValueError, TypeError):
                    logger.warning(f"Invalid character_id type: {event_data[field]}")
                    return False
        
        return True
    
    async def handle_event(
        self,
        event_data: Dict[str, Any],
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Handle buff/debuff removed: save event and remove from active effects."""
        import json
        
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
            (session_id, event_data['character_id'])
        ).fetchone()
        
        if not session_character:
            raise HTTPException(
                status_code=400,
                detail='Character is not in this session'
            )
        
        try:
            # Insert buff/debuff event
            cursor = db.execute(
                '''INSERT INTO buff_debuff_events 
                   (session_id, character_id, effect_name, effect_type, action, transcript_segment)
                   VALUES (?, ?, ?, 
                       (SELECT effect_type FROM active_buff_debuffs 
                        WHERE session_id = ? AND character_id = ? AND effect_name = ? LIMIT 1),
                       ?, ?)''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['effect_name'],
                    session_id,
                    event_data['character_id'],
                    event_data['effect_name'],
                    'removed',
                    event_data.get('transcript_segment')
                )
            )
            event_id = cursor.lastrowid
            
            # Remove from active buffs/debuffs
            db.execute(
                '''DELETE FROM active_buff_debuffs 
                   WHERE session_id = ? AND character_id = ? AND effect_name = ?''',
                (
                    session_id,
                    event_data['character_id'],
                    event_data['effect_name']
                )
            )
            
            db.commit()
            
            # Get the created event with character name
            event_row = db.execute('''
                SELECT 
                    bde.*,
                    c.name as character_name
                FROM buff_debuff_events bde
                JOIN characters c ON bde.character_id = c.id
                WHERE bde.id = ?
            ''', (event_id,)).fetchone()
            
            return dict(event_row)
            
        except Exception as e:
            db.rollback()
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
        
        if not isinstance(event_data['character_id'], int):
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
        session_id: int,
        user_id: int,
        db: Any
    ) -> Dict[str, Any]:
        """Process spell cast event: save event and update spell slot usage."""
        logger.info(f"SpellCastEventType.handle_event called - session_id: {session_id}, user_id: {user_id}")
        logger.debug(f"Event data: {event_data}")
        
        try:
            character_id = event_data.get('character_id')
            spell_level = event_data.get('spell_level')
            spell_name = event_data.get('spell_name')
            
            logger.info(f"Processing spell cast: {spell_name} (level {spell_level}) for character {character_id}")
            
            # Verify character belongs to user's session
            character_check = db.execute('''
                SELECT sc.character_id
                FROM session_characters sc
                JOIN sessions s ON sc.session_id = s.id
                WHERE sc.session_id = ? AND sc.character_id = ? AND s.user_id = ?
            ''', (session_id, character_id, user_id)).fetchone()
            
            if not character_check:
                logger.warning(f"Character {character_id} not found in session {session_id} for user {user_id}")
                raise HTTPException(status_code=404, detail='Character not found in session')
            
            logger.debug(f"Character {character_id} verified in session {session_id}")
            
            # Save spell event - use 'cast' to match CHECK constraint
            logger.debug(f"Inserting spell event into database: spell_name={spell_name}, spell_level={spell_level}, event_type='cast'")
            event_id = db.execute('''
                INSERT INTO spell_events (
                    session_id, character_id, spell_name, spell_level, event_type, transcript_segment
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                character_id,
                spell_name,
                spell_level,
                'cast',
                event_data.get('transcript_segment', '')
            )).lastrowid
            logger.debug(f"Spell event inserted with ID: {event_id}")
            
            # Update spell slot usage (only for level 1-9, cantrips don't use slots)
            if spell_level > 0:
                logger.debug(f"Updating spell slot usage for character {character_id}, spell level {spell_level}")
                # Insert or update spell slot usage
                db.execute('''
                    INSERT INTO character_spell_slots (
                        session_id, character_id, spell_level, slots_used
                    ) VALUES (?, ?, ?, 1)
                    ON CONFLICT(session_id, character_id, spell_level) 
                    DO UPDATE SET slots_used = slots_used + 1
                ''', (session_id, character_id, spell_level))
            else:
                logger.debug(f"Spell level is {spell_level} (cantrip), skipping spell slot usage update")
            
            logger.debug(f"Committing transaction for spell event {event_id}")
            db.commit()
            
            # Get the created event with character name
            logger.debug(f"Fetching created spell event with ID {event_id}")
            event_row = db.execute('''
                SELECT 
                    se.*,
                    c.name as character_name
                FROM spell_events se
                JOIN characters c ON se.character_id = c.id
                WHERE se.id = ?
            ''', (event_id,)).fetchone()
            
            logger.info(
                f"✓ Spell cast event processed successfully: {spell_name} (level {spell_level}) by character {character_id} "
                f"in session {session_id}"
            )
            
            return dict(event_row)
            
        except HTTPException:
            logger.debug("HTTPException raised, re-raising")
            raise
        except Exception as e:
            logger.error(f"❌ Error handling spell cast event: {e}")
            logger.error(f"   Event data: {event_data}")
            logger.error(f"   Session ID: {session_id}, User ID: {user_id}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            db.rollback()
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

