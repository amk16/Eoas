from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from ..middleware.auth import authenticate_token
from ..db.firebase import get_firestore
from firebase_admin import firestore
from ..services.nano_banana_service import generate_character_image

logger = logging.getLogger(__name__)


router = APIRouter()


class CharacterCreate(BaseModel):
    name: str
    max_hp: int
    campaign_id: Optional[str] = None
    race: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[int] = None
    ac: Optional[int] = None
    initiative_bonus: Optional[int] = None
    temp_hp: Optional[int] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    notes: Optional[str] = None
    display_art_url: Optional[str] = None
    art_prompt: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: str
    max_hp: int
    campaign_id: Optional[str] = None
    race: Optional[str] = None
    class_name: Optional[str] = None
    level: Optional[int] = None
    ac: Optional[int] = None
    initiative_bonus: Optional[int] = None
    temp_hp: Optional[int] = None
    background: Optional[str] = None
    alignment: Optional[str] = None
    notes: Optional[str] = None
    display_art_url: Optional[str] = None
    art_prompt: Optional[str] = None


@router.get('/')
async def get_characters(
    campaign_id: Optional[str] = Query(None),
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all characters for the authenticated user, optionally filtered by campaign."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CHARACTERS] Fetching characters from Firestore for user_id={user_id}, campaign_id={campaign_id}')
        
        # Query nested collection: users/{user_id}/characters
        query = db.collection('users').document(user_id).collection('characters')
        if campaign_id:
            query = query.where('campaign_id', '==', campaign_id)
        
        docs = query.stream()
        characters = []
        for doc in docs:
            char_data = doc.to_dict()
            char_data['id'] = doc.id  # Add document ID
            
            # Convert Firestore timestamps to strings
            if 'created_at' in char_data and hasattr(char_data['created_at'], 'isoformat'):
                char_data['created_at'] = char_data['created_at'].isoformat()
            if 'updated_at' in char_data and hasattr(char_data['updated_at'], 'isoformat'):
                char_data['updated_at'] = char_data['updated_at'].isoformat()
            
            characters.append(char_data)
        
        # Sort by created_at descending
        characters.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        logger.info(f'[CHARACTERS] Returning {len(characters)} characters from Firestore')
        return characters
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error fetching characters: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{character_id}')
async def get_character(character_id: str, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Get a single character by ID."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CHARACTERS] Fetching character from Firestore: id={character_id}, user_id={user_id}')
        
        # Access nested collection: users/{user_id}/characters/{character_id}
        character_ref = db.collection('users').document(user_id).collection('characters').document(str(character_id))
        doc = character_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail='Character not found')
        
        char_data = doc.to_dict()
        char_data['id'] = doc.id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in char_data and hasattr(char_data['created_at'], 'isoformat'):
            char_data['created_at'] = char_data['created_at'].isoformat()
        if 'updated_at' in char_data and hasattr(char_data['updated_at'], 'isoformat'):
            char_data['updated_at'] = char_data['updated_at'].isoformat()
        
        logger.info(f'[CHARACTERS] Returning character from Firestore')
        return char_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error fetching character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/')
async def create_character(character: CharacterCreate, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Create a new character."""
    try:
        logger.info(f'[CHARACTERS] Creating character for user_id={user_id}, name={character.name}')
        logger.info(f'[CHARACTERS] Character data: {character.dict()}')
        logger.info(f'[CHARACTERS] Storage: Firestore')
        
        if not character.name or not character.max_hp:
            raise HTTPException(status_code=400, detail='Name and max_hp are required')
        
        if not isinstance(character.max_hp, int) or character.max_hp <= 0:
            raise HTTPException(status_code=400, detail='max_hp must be a positive number')

        if character.level is not None and (not isinstance(character.level, int) or character.level <= 0):
            raise HTTPException(status_code=400, detail='level must be a positive number')

        if character.ac is not None and (not isinstance(character.ac, int) or character.ac <= 0):
            raise HTTPException(status_code=400, detail='ac must be a positive number')

        if character.temp_hp is not None and (not isinstance(character.temp_hp, int) or character.temp_hp < 0):
            raise HTTPException(status_code=400, detail='temp_hp must be 0 or a positive number')

        if character.initiative_bonus is not None and (not isinstance(character.initiative_bonus, int)):
            raise HTTPException(status_code=400, detail='initiative_bonus must be a number')
        
        # Get Firestore client
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CHARACTERS] Got Firestore client')
        
        # Verify campaign belongs to user if provided
        if character.campaign_id:
            campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(character.campaign_id))
            campaign_doc = campaign_ref.get()
            if not campaign_doc.exists:
                raise HTTPException(status_code=400, detail='Campaign not found')
        
        # Prepare character data for Firestore (no user_id needed - it's in the path)
        character_data = {
            'name': character.name,
            'max_hp': character.max_hp,
            'campaign_id': character.campaign_id,
            'race': character.race,
            'class_name': character.class_name,
            'level': character.level,
            'ac': character.ac,
            'initiative_bonus': character.initiative_bonus,
            'temp_hp': character.temp_hp,
            'background': character.background,
            'alignment': character.alignment,
            'notes': character.notes,
            'display_art_url': character.display_art_url,
            'art_prompt': character.art_prompt,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Remove None values
        character_data = {k: v for k, v in character_data.items() if v is not None}
        
        logger.info(f'[CHARACTERS] Saving to Firestore collection: users/{user_id}/characters')
        # Create document in nested collection: users/{user_id}/characters
        character_ref = db.collection('users').document(user_id).collection('characters').document()
        character_ref.set(character_data)
        character_id = character_ref.id
        
        logger.info(f'[CHARACTERS] Character saved to Firestore with id={character_id}')
        
        # Fetch the created document to return
        created_doc = character_ref.get()
        result = created_doc.to_dict()
        result['id'] = character_id  # Add document ID to result
        
        # Convert Firestore timestamps to strings for JSON serialization
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        logger.info(f'[CHARACTERS] Returning created character: {result}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{character_id}')
async def update_character(
    character_id: str,
    character: CharacterUpdate,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a character."""
    try:
        logger.info(f'[CHARACTERS] Updating character id={character_id} for user_id={user_id}')
        logger.info(f'[CHARACTERS] Update data: {character.dict()}')
        logger.info(f'[CHARACTERS] Storage: Firestore')
        
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CHARACTERS] Got Firestore client')
        
        # Access nested collection: users/{user_id}/characters/{character_id}
        character_ref = db.collection('users').document(user_id).collection('characters').document(str(character_id))
        existing_doc = character_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Character not found')
        
        if not character.name or not character.max_hp:
            raise HTTPException(status_code=400, detail='Name and max_hp are required')
        
        if not isinstance(character.max_hp, int) or character.max_hp <= 0:
            raise HTTPException(status_code=400, detail='max_hp must be a positive number')

        if character.level is not None and (not isinstance(character.level, int) or character.level <= 0):
            raise HTTPException(status_code=400, detail='level must be a positive number')

        if character.ac is not None and (not isinstance(character.ac, int) or character.ac <= 0):
            raise HTTPException(status_code=400, detail='ac must be a positive number')

        if character.temp_hp is not None and (not isinstance(character.temp_hp, int) or character.temp_hp < 0):
            raise HTTPException(status_code=400, detail='temp_hp must be 0 or a positive number')

        if character.initiative_bonus is not None and (not isinstance(character.initiative_bonus, int)):
            raise HTTPException(status_code=400, detail='initiative_bonus must be a number')
        
        # Verify campaign belongs to user if provided
        if character.campaign_id:
            campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(character.campaign_id))
            campaign_doc = campaign_ref.get()
            if not campaign_doc.exists:
                raise HTTPException(status_code=400, detail='Campaign not found')
        
        # Prepare update data
        update_data = {
            'name': character.name,
            'max_hp': character.max_hp,
            'campaign_id': character.campaign_id,
            'race': character.race,
            'class_name': character.class_name,
            'level': character.level,
            'ac': character.ac,
            'initiative_bonus': character.initiative_bonus,
            'temp_hp': character.temp_hp,
            'background': character.background,
            'alignment': character.alignment,
            'notes': character.notes,
            'display_art_url': character.display_art_url,
            'art_prompt': character.art_prompt,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Remove None values
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        logger.info(f'[CHARACTERS] Updating Firestore document: characters/{character_id}')
        character_ref.update(update_data)
        logger.info(f'[CHARACTERS] Character updated in Firestore')
        
        # Fetch updated document
        updated_doc = character_ref.get()
        result = updated_doc.to_dict()
        result['id'] = character_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        logger.info(f'[CHARACTERS] Returning updated character: {result}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error updating character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{character_id}')
async def delete_character(character_id: str, user_id: str = Depends(authenticate_token)) -> Dict[str, str]:
    """Delete a character."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CHARACTERS] Deleting character id={character_id} for user_id={user_id}')
        
        # Access nested collection: users/{user_id}/characters/{character_id}
        character_ref = db.collection('users').document(user_id).collection('characters').document(str(character_id))
        existing_doc = character_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Character not found')
        
        logger.info(f'[CHARACTERS] Deleting from Firestore: users/{user_id}/characters/{character_id}')
        character_ref.delete()
        logger.info(f'[CHARACTERS] Character deleted from Firestore')
        
        return {'message': 'Character deleted successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{character_id}/generate-art')
async def generate_character_art(
    character_id: str,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Generate character art for a character using nano banana.
    Updates the character with the generated art URL and prompt.
    """
    try:
        db = get_firestore()
        if not db:
            logger.error('[CHARACTERS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/characters/{character_id}
        character_ref = db.collection('users').document(user_id).collection('characters').document(str(character_id))
        doc = character_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail='Character not found')
        
        character_data = doc.to_dict()
        character_data['id'] = doc.id
        
        # Generate art using nano banana service
        try:
            art_result = await generate_character_image(character_data)
            
            # Update character with generated art URL and prompt
            character_ref.update({
                'display_art_url': art_result['image_url'],
                'art_prompt': art_result['prompt'],
                'updated_at': firestore.SERVER_TIMESTAMP,
            })
            
            # Fetch updated character
            updated_doc = character_ref.get()
            result = updated_doc.to_dict()
            result['id'] = character_id
            
            # Convert Firestore timestamps to strings
            if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
                result['created_at'] = result['created_at'].isoformat()
            if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
                result['updated_at'] = result['updated_at'].isoformat()
            
            return result
        except Exception as e:
            print(f'Error generating character art: {e}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to generate character art: {str(e)}'
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error in generate_character_art endpoint: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')

