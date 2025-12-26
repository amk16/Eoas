from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from ..middleware.auth import authenticate_token
from ..db.database import get_database
from ..services.nano_banana_service import generate_character_image


router = APIRouter()


class CharacterCreate(BaseModel):
    name: str
    max_hp: int
    campaign_id: Optional[int] = None
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
    campaign_id: Optional[int] = None
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
    campaign_id: Optional[int] = Query(None),
    user_id: int = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all characters for the authenticated user, optionally filtered by campaign."""
    try:
        db = get_database()
        if campaign_id:
            rows = db.execute(
                'SELECT * FROM characters WHERE user_id = ? AND campaign_id = ? ORDER BY created_at DESC',
                (user_id, campaign_id)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM characters WHERE user_id = ? ORDER BY created_at DESC',
                (user_id,)
            ).fetchall()
        
        # Convert Row objects to dictionaries
        characters = [dict(row) for row in rows]
        return characters
    except Exception as e:
        print(f'Error fetching characters: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{character_id}')
async def get_character(character_id: int, user_id: int = Depends(authenticate_token)) -> Dict[str, Any]:
    """Get a single character by ID."""
    try:
        db = get_database()
        row = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (character_id, user_id)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail='Character not found')
        
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/')
async def create_character(character: CharacterCreate, user_id: int = Depends(authenticate_token)) -> Dict[str, Any]:
    """Create a new character."""
    try:
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
        
        db = get_database()
        
        # Verify campaign belongs to user if provided
        if character.campaign_id:
            campaign = db.execute(
                'SELECT id FROM campaigns WHERE id = ? AND user_id = ?',
                (character.campaign_id, user_id)
            ).fetchone()
            if not campaign:
                raise HTTPException(status_code=400, detail='Campaign not found or does not belong to you')
        
        cursor = db.execute(
            '''
                INSERT INTO characters (
                    user_id, name, max_hp, campaign_id,
                    race, class_name, level, ac, initiative_bonus, temp_hp,
                    background, alignment, notes, display_art_url, art_prompt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                user_id,
                character.name,
                character.max_hp,
                character.campaign_id,
                character.race,
                character.class_name,
                character.level,
                character.ac,
                character.initiative_bonus,
                character.temp_hp,
                character.background,
                character.alignment,
                character.notes,
                character.display_art_url,
                character.art_prompt,
            )
        )
        db.commit()
        character_id = cursor.lastrowid
        
        row = db.execute('SELECT * FROM characters WHERE id = ?', (character_id,)).fetchone()
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{character_id}')
async def update_character(
    character_id: int,
    character: CharacterUpdate,
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a character."""
    try:
        db = get_database()
        
        # Verify character belongs to user
        existing = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (character_id, user_id)
        ).fetchone()
        
        if not existing:
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
            campaign = db.execute(
                'SELECT id FROM campaigns WHERE id = ? AND user_id = ?',
                (character.campaign_id, user_id)
            ).fetchone()
            if not campaign:
                raise HTTPException(status_code=400, detail='Campaign not found or does not belong to you')
        
        db.execute(
            '''
                UPDATE characters SET
                    name = ?,
                    max_hp = ?,
                    campaign_id = ?,
                    race = ?,
                    class_name = ?,
                    level = ?,
                    ac = ?,
                    initiative_bonus = ?,
                    temp_hp = ?,
                    background = ?,
                    alignment = ?,
                    notes = ?,
                    display_art_url = ?,
                    art_prompt = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            ''',
            (
                character.name,
                character.max_hp,
                character.campaign_id,
                character.race,
                character.class_name,
                character.level,
                character.ac,
                character.initiative_bonus,
                character.temp_hp,
                character.background,
                character.alignment,
                character.notes,
                character.display_art_url,
                character.art_prompt,
                character_id,
                user_id,
            )
        )
        db.commit()
        
        row = db.execute('SELECT * FROM characters WHERE id = ?', (character_id,)).fetchone()
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error updating character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{character_id}')
async def delete_character(character_id: int, user_id: int = Depends(authenticate_token)) -> Dict[str, str]:
    """Delete a character."""
    try:
        db = get_database()
        
        # Verify character belongs to user
        existing = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (character_id, user_id)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail='Character not found')
        
        db.execute('DELETE FROM characters WHERE id = ? AND user_id = ?', (character_id, user_id))
        db.commit()
        
        return {'message': 'Character deleted successfully'}
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error deleting character: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{character_id}/generate-art')
async def generate_character_art(
    character_id: int,
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Generate character art for a character using nano banana.
    Updates the character with the generated art URL and prompt.
    """
    try:
        db = get_database()
        
        # Verify character belongs to user
        row = db.execute(
            'SELECT * FROM characters WHERE id = ? AND user_id = ?',
            (character_id, user_id)
        ).fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail='Character not found')
        
        character_data = dict(row)
        
        # Generate art using nano banana service
        try:
            art_result = await generate_character_image(character_data)
            
            # Update character with generated art URL and prompt
            db.execute(
                '''
                    UPDATE characters SET
                        display_art_url = ?,
                        art_prompt = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                ''',
                (
                    art_result['image_url'],
                    art_result['prompt'],
                    character_id,
                    user_id,
                )
            )
            db.commit()
            
            # Fetch updated character
            updated_row = db.execute('SELECT * FROM characters WHERE id = ?', (character_id,)).fetchone()
            return dict(updated_row)
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

