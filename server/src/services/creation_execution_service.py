# creation_execution_service.py
import logging
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
from ..db.firebase import get_firestore
from firebase_admin import firestore

logger = logging.getLogger(__name__)


async def execute_campaign_creation(
    data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    Execute campaign creation.
    
    Args:
        data: Campaign data dictionary with name (required) and description (optional)
        user_id: User ID
    
    Returns:
        Created campaign dictionary with id
    """
    logger.info(f"[CREATION] Creating campaign for user_id={user_id}")
    logger.info(f"[CREATION] Campaign data: {data}")
    
    name = data.get('name', 'New Campaign')
    
    db = get_firestore()
    if not db:
        logger.error('[CREATION] Firestore not initialized')
        raise HTTPException(status_code=500, detail='Firestore not available')
    
    # Prepare campaign data
    campaign_data = {
        'name': name,
        'description': data.get('description'),
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    }
    
    # Remove None values
    campaign_data = {k: v for k, v in campaign_data.items() if v is not None}
    
    # Create document in nested collection
    campaign_ref = db.collection('users').document(user_id).collection('campaigns').document()
    campaign_ref.set(campaign_data)
    campaign_id = campaign_ref.id
    logger.info(f'[CREATION] Campaign saved to Firestore with id={campaign_id}')
    
    # Fetch and return created document
    created_doc = campaign_ref.get()
    result = created_doc.to_dict()
    result['id'] = campaign_id
    
    # Convert Firestore timestamps to strings
    if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
        result['created_at'] = result['created_at'].isoformat()
    if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
        result['updated_at'] = result['updated_at'].isoformat()
    
    return result


async def execute_session_creation(
    data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    Execute session creation.
    
    Args:
        data: Session data dictionary with name (required), campaign_id (optional), character_ids (optional)
        user_id: User ID
    
    Returns:
        Created session dictionary with id
    """
    logger.info(f"[CREATION] Creating session for user_id={user_id}")
    logger.info(f"[CREATION] Session data: {data}")
    
    name = data.get('name', 'New Session')
    
    db = get_firestore()
    if not db:
        logger.error('[CREATION] Firestore not initialized')
        raise HTTPException(status_code=500, detail='Firestore not available')
    
    campaign_id = data.get('campaign_id')
    
    # Verify campaign belongs to user if provided
    if campaign_id:
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        campaign_doc = campaign_ref.get()
        if not campaign_doc.exists:
            raise ValueError(f"Campaign {campaign_id} not found or does not belong to user")
    
    # Prepare session data
    session_data = {
        'name': name,
        'status': 'active',
        'campaign_id': campaign_id,
        'started_at': firestore.SERVER_TIMESTAMP,
    }
    
    # Remove None values
    session_data = {k: v for k, v in session_data.items() if v is not None}
    
    # Create document in nested collection
    session_ref = db.collection('users').document(user_id).collection('sessions').document()
    session_ref.set(session_data)
    session_id = session_ref.id
    logger.info(f'[CREATION] Session saved to Firestore with id={session_id}')
    
    # Add characters to session if provided
    character_ids = data.get('character_ids', [])
    if character_ids:
        session_characters_ref = session_ref.collection('session_characters')
        for char_id in character_ids:
            # Verify character belongs to user
            char_ref = db.collection('users').document(user_id).collection('characters').document(str(char_id))
            char_doc = char_ref.get()
            if char_doc.exists:
                char_data = char_doc.to_dict()
                max_hp = char_data.get('max_hp', 100)
                session_characters_ref.add({
                    'character_id': str(char_id),
                    'character_name': char_data.get('name', 'Unknown'),
                    'starting_hp': max_hp,
                    'current_hp': max_hp,
                })
                logger.info(f'[CREATION] Added character {char_id} to session {session_id}')
    
    # Fetch and return created document
    created_doc = session_ref.get()
    result = created_doc.to_dict()
    result['id'] = session_id
    
    # Convert Firestore timestamps to strings
    if 'started_at' in result and hasattr(result['started_at'], 'isoformat'):
        result['started_at'] = result['started_at'].isoformat()
    if 'ended_at' in result and hasattr(result['ended_at'], 'isoformat'):
        result['ended_at'] = result['ended_at'].isoformat()
    
    return result


async def execute_character_creation(
    data: Dict[str, Any],
    user_id: str
) -> Dict[str, Any]:
    """
    Execute character creation.
    
    Args:
        data: Character data dictionary with name and max_hp (required), plus optional fields
        user_id: User ID
    
    Returns:
        Created character dictionary with id
    """
    logger.info(f"[CREATION] Creating character for user_id={user_id}")
    logger.info(f"[CREATION] Character data: {data}")
    
    name = data.get('name', 'New Character')
    max_hp = data.get('max_hp', 100)
    
    # Ensure max_hp is valid integer (default to 100 if invalid)
    try:
        max_hp = int(max_hp)
        if max_hp <= 0:
            logger.warning(f"[CREATION] Invalid max_hp value {max_hp}, using default 100")
            max_hp = 100
    except (ValueError, TypeError):
        logger.warning(f"[CREATION] Invalid max_hp value, using default 100")
        max_hp = 100
    
    db = get_firestore()
    if not db:
        logger.error('[CREATION] Firestore not initialized')
        raise HTTPException(status_code=500, detail='Firestore not available')
    
    campaign_id = data.get('campaign_id')
    
    # Verify campaign belongs to user if provided
    if campaign_id:
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        campaign_doc = campaign_ref.get()
        if not campaign_doc.exists:
            raise ValueError(f"Campaign {campaign_id} not found or does not belong to user")
    
    # Prepare character data - include all optional fields
    character_data = {
        'name': name,
        'max_hp': max_hp,
        'campaign_id': campaign_id,
        'race': data.get('race'),
        'class_name': data.get('class_name'),
        'level': data.get('level'),
        'ac': data.get('ac'),
        'initiative_bonus': data.get('initiative_bonus'),
        'temp_hp': data.get('temp_hp'),
        'background': data.get('background'),
        'alignment': data.get('alignment'),
        'notes': data.get('notes'),
        'display_art_url': data.get('display_art_url'),
        'art_prompt': data.get('art_prompt'),
        'strength_base': data.get('strength_base'),
        'strength_bonus': data.get('strength_bonus'),
        'dexterity_base': data.get('dexterity_base'),
        'dexterity_bonus': data.get('dexterity_bonus'),
        'wisdom_base': data.get('wisdom_base'),
        'wisdom_bonus': data.get('wisdom_bonus'),
        'intelligence_base': data.get('intelligence_base'),
        'intelligence_bonus': data.get('intelligence_bonus'),
        'constitution_base': data.get('constitution_base'),
        'constitution_bonus': data.get('constitution_bonus'),
        'charisma_base': data.get('charisma_base'),
        'charisma_bonus': data.get('charisma_bonus'),
        'style': data.get('style'),
        'clothing': data.get('clothing'),
        'expression': data.get('expression'),
        'created_at': firestore.SERVER_TIMESTAMP,
        'updated_at': firestore.SERVER_TIMESTAMP,
    }
    
    # Remove None values
    character_data = {k: v for k, v in character_data.items() if v is not None}
    
    # Create document in nested collection
    character_ref = db.collection('users').document(user_id).collection('characters').document()
    character_ref.set(character_data)
    character_id = character_ref.id
    logger.info(f'[CREATION] Character saved to Firestore with id={character_id}')
    
    # Fetch and return created document
    created_doc = character_ref.get()
    result = created_doc.to_dict()
    result['id'] = character_id
    
    # Convert Firestore timestamps to strings
    if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
        result['created_at'] = result['created_at'].isoformat()
    if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
        result['updated_at'] = result['updated_at'].isoformat()
    
    return result

