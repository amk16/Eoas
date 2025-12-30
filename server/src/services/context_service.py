# context_service.py
import logging
from typing import Dict, Any, List, Optional
from ..db.firebase import get_firestore

logger = logging.getLogger(__name__)


async def get_user_context(user_id: str) -> Dict[str, Any]:
    """
    Gather all relevant context about a user's campaigns, sessions, and characters from Firestore.
    This context is used to inform the voice assistant about the user's data.
    
    Args:
        user_id: The user ID to fetch context for
    
    Returns:
        Dictionary containing campaigns, sessions, and characters
    """
    logger.info(f"Gathering context for user {user_id}")
    
    try:
        db = get_firestore()
        if not db:
            logger.warning("Firestore not initialized, returning empty context")
            return {
                "campaigns": [],
                "sessions": [],
                "characters": []
            }
        
        context = {
            "campaigns": [],
            "sessions": [],
            "characters": []
        }
        
        # Fetch campaigns from Firestore
        campaigns_docs = db.collection('users').document(user_id).collection('campaigns').stream()
        for doc in campaigns_docs:
            camp_data = doc.to_dict()
            context["campaigns"].append({
                "id": doc.id,
                "name": camp_data.get('name', ''),
                "description": camp_data.get('description'),
                "created_at": camp_data.get('created_at').isoformat() if camp_data.get('created_at') and hasattr(camp_data.get('created_at'), 'isoformat') else None
            })
        # Sort by created_at descending (limit to 50 most recent)
        context["campaigns"].sort(key=lambda x: x.get('created_at') or '', reverse=True)
        context["campaigns"] = context["campaigns"][:50]
        
        logger.info(f"Found {len(context['campaigns'])} campaigns")
        
        # Fetch sessions from Firestore
        sessions_docs = db.collection('users').document(user_id).collection('sessions').stream()
        for doc in sessions_docs:
            session_data = doc.to_dict()
            context["sessions"].append({
                "id": doc.id,
                "name": session_data.get('name', ''),
                "campaign_id": session_data.get('campaign_id'),
                "started_at": session_data.get('started_at').isoformat() if session_data.get('started_at') and hasattr(session_data.get('started_at'), 'isoformat') else None,
                "ended_at": session_data.get('ended_at').isoformat() if session_data.get('ended_at') and hasattr(session_data.get('ended_at'), 'isoformat') else None,
                "status": session_data.get('status', 'active')
            })
        # Sort by started_at descending (limit to 50 most recent)
        context["sessions"].sort(key=lambda x: x.get('started_at') or '', reverse=True)
        context["sessions"] = context["sessions"][:50]
        
        logger.info(f"Found {len(context['sessions'])} sessions")
        
        # Fetch characters from Firestore
        characters_docs = db.collection('users').document(user_id).collection('characters').stream()
        
        # Get active sessions to check for current_hp
        active_session_ids = [
            sess["id"] for sess in context["sessions"] 
            if sess.get("status") == "active"
        ]
        
        # Create a map of character_id -> current_hp from active sessions
        character_hp_map = {}
        for session_id in active_session_ids:
            session_characters_ref = db.collection('users').document(user_id).collection('sessions').document(session_id).collection('session_characters')
            session_characters_docs = session_characters_ref.stream()
            for doc in session_characters_docs:
                char_data = doc.to_dict()
                char_id = char_data.get('character_id')
                if char_id:
                    current_hp = char_data.get('current_hp')
                    if current_hp is not None:
                        character_hp_map[str(char_id)] = current_hp
        
        for doc in characters_docs:
            char_data = doc.to_dict()
            char_id = doc.id
            max_hp = char_data.get('max_hp', 0)
            current_hp = character_hp_map.get(char_id, max_hp)
            
            created_at = char_data.get('created_at')
            created_at_str = created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else None
            
            context["characters"].append({
                "id": char_id,
                "name": char_data.get('name', ''),
                "max_hp": max_hp,
                "current_hp": current_hp,
                "race": char_data.get('race'),
                "class_name": char_data.get('class_name'),
                "level": char_data.get('level'),
                "ac": char_data.get('ac'),
                "campaign_id": char_data.get('campaign_id'),
                "created_at": created_at_str
            })
        # Sort by created_at descending (limit to 100 most recent)
        context["characters"].sort(key=lambda x: x.get('created_at') or '', reverse=True)
        context["characters"] = context["characters"][:100]
        
        logger.info(f"Found {len(context['characters'])} characters")
        
        return context
        
    except Exception as e:
        logger.error(f"Error gathering user context: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Return empty context on error rather than failing
        return {
            "campaigns": [],
            "sessions": [],
            "characters": []
        }


async def get_session_context(session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed context for a specific session, including characters and recent events.
    
    NOTE: This function is deprecated - sessions/characters/events are stored in Firestore.
    The session route handlers in routes/sessions.py handle Firestore queries directly.
    
    Args:
        session_id: The session ID
        user_id: The user ID for authorization
    
    Returns:
        None (deprecated function - use session routes directly)
    """
    logger.warning(f"get_session_context called but deprecated (session_id={session_id})")
    # This function is no longer used - session data is queried directly from Firestore in routes
    return None

