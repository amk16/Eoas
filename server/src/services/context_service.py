# context_service.py
import logging
from typing import Dict, Any, List, Optional
from ..db.database import get_database

logger = logging.getLogger(__name__)


async def get_user_context(user_id: int) -> Dict[str, Any]:
    """
    Gather all relevant context about a user's campaigns, sessions, and characters.
    This context is used to inform the voice assistant about the user's data.
    
    Args:
        user_id: The user ID to fetch context for
    
    Returns:
        Dictionary containing campaigns, sessions, and characters
    """
    logger.info(f"Gathering context for user {user_id}")
    
    try:
        db = get_database()
        context = {
            "campaigns": [],
            "sessions": [],
            "characters": []
        }
        
        # Fetch campaigns
        campaign_rows = db.execute(
            'SELECT id, name, description, created_at FROM campaigns WHERE user_id = ? ORDER BY created_at DESC LIMIT 50',
            (user_id,)
        ).fetchall()
        
        context["campaigns"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "description": dict(row).get("description"),
                "created_at": dict(row).get("created_at")
            }
            for row in campaign_rows
        ]
        
        logger.info(f"Found {len(context['campaigns'])} campaigns")
        
        # Fetch sessions
        session_rows = db.execute(
            '''SELECT id, name, campaign_id, started_at, ended_at, status 
               FROM sessions 
               WHERE user_id = ? 
               ORDER BY started_at DESC 
               LIMIT 50''',
            (user_id,)
        ).fetchall()
        
        context["sessions"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "campaign_id": dict(row).get("campaign_id"),
                "started_at": dict(row).get("started_at"),
                "ended_at": dict(row).get("ended_at"),
                "status": dict(row).get("status", "active")
            }
            for row in session_rows
        ]
        
        logger.info(f"Found {len(context['sessions'])} sessions")
        
        # Fetch characters with their current HP from active sessions
        character_rows = db.execute(
            '''SELECT 
                   c.id, 
                   c.name, 
                   c.max_hp, 
                   c.race, 
                   c.class_name, 
                   c.level, 
                   c.ac,
                   c.campaign_id,
                   COALESCE(sc.current_hp, c.max_hp) as current_hp
               FROM characters c
               LEFT JOIN session_characters sc ON c.id = sc.character_id 
                   AND sc.session_id IN (
                       SELECT id FROM sessions WHERE user_id = ? AND status = 'active'
                   )
               WHERE c.user_id = ?
               ORDER BY c.created_at DESC
               LIMIT 100''',
            (user_id, user_id)
        ).fetchall()
        
        context["characters"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "max_hp": row["max_hp"],
                "current_hp": dict(row).get("current_hp") or row["max_hp"],
                "race": dict(row).get("race"),
                "class_name": dict(row).get("class_name"),
                "level": dict(row).get("level"),
                "ac": dict(row).get("ac"),
                "campaign_id": dict(row).get("campaign_id")
            }
            for row in character_rows
        ]
        
        logger.info(f"Found {len(context['characters'])} characters")
        
        return context
        
    except Exception as e:
        logger.error(f"Error gathering user context: {e}")
        # Return empty context on error rather than failing
        return {
            "campaigns": [],
            "sessions": [],
            "characters": []
        }


async def get_session_context(session_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed context for a specific session, including characters and recent events.
    
    Args:
        session_id: The session ID
        user_id: The user ID for authorization
    
    Returns:
        Dictionary with session details, characters, and events, or None if not found
    """
    logger.info(f"Gathering context for session {session_id}")
    
    try:
        db = get_database()
        
        # Get session
        session_row = db.execute(
            'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
            (session_id, user_id)
        ).fetchone()
        
        if not session_row:
            logger.warning(f"Session {session_id} not found for user {user_id}")
            return None
        
        session = dict(session_row)
        
        # Get session characters
        character_rows = db.execute(
            '''SELECT 
                   sc.*,
                   c.name as character_name,
                   c.max_hp
               FROM session_characters sc
               JOIN characters c ON sc.character_id = c.id
               WHERE sc.session_id = ?''',
            (session_id,)
        ).fetchall()
        
        characters = [
            {
                "character_id": row["character_id"],
                "character_name": row["character_name"],
                "current_hp": dict(row).get("current_hp"),
                "max_hp": row["max_hp"],
                "starting_hp": dict(row).get("starting_hp")
            }
            for row in character_rows
        ]
        
        # Get recent events (last 20)
        event_rows = db.execute(
            '''SELECT * FROM damage_events 
               WHERE session_id = ? 
               ORDER BY timestamp DESC 
               LIMIT 20''',
            (session_id,)
        ).fetchall()
        
        events = [dict(row) for row in event_rows]
        
        return {
            "session": session,
            "characters": characters,
            "events": events
        }
        
    except Exception as e:
        logger.error(f"Error gathering session context: {e}")
        return None

