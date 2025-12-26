from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from ..middleware.auth import authenticate_token
from ..db.database import get_database

logger = logging.getLogger(__name__)


router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get('/')
async def get_campaigns(request: Request, user_id: int = Depends(authenticate_token)) -> List[Dict[str, Any]]:
    """Get all campaigns for the authenticated user."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        forwarded_for = request.headers.get('X-Forwarded-For', 'not-set')
        host = request.headers.get('Host', 'not-set')
        logger.info(f'[Campaigns API] GET /campaigns - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}, X-Forwarded-For={forwarded_for}, Host={host}')
        
        db = get_database()
        rows = db.execute(
            'SELECT * FROM campaigns WHERE user_id = ? ORDER BY created_at DESC',
            (user_id,)
        ).fetchall()
        
        campaigns = [dict(row) for row in rows]
        
        # Log response being sent
        logger.info(f'[Campaigns API] GET /campaigns - Sending response with {len(campaigns)} campaign(s), protocol={scheme}, forwarded_proto={forwarded_proto}')
        return campaigns
    except Exception as e:
        print(f'Error fetching campaigns: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{campaign_id}')
async def get_campaign(campaign_id: int, request: Request, user_id: int = Depends(authenticate_token)) -> Dict[str, Any]:
    """Get a single campaign by ID with characters and sessions."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] GET /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_database()
        
        # Get campaign
        campaign_row = db.execute(
            'SELECT * FROM campaigns WHERE id = ? AND user_id = ?',
            (campaign_id, user_id)
        ).fetchone()
        
        if not campaign_row:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        campaign = dict(campaign_row)
        
        # Get characters for this campaign
        characters_rows = db.execute(
            'SELECT * FROM characters WHERE campaign_id = ? AND user_id = ? ORDER BY created_at DESC',
            (campaign_id, user_id)
        ).fetchall()
        
        characters = [dict(row) for row in characters_rows]
        
        # Get sessions for this campaign
        sessions_rows = db.execute(
            'SELECT * FROM sessions WHERE campaign_id = ? AND user_id = ? ORDER BY started_at DESC',
            (campaign_id, user_id)
        ).fetchall()
        
        sessions = [dict(row) for row in sessions_rows]
        
        result = {
            **campaign,
            'characters': characters,
            'sessions': sessions
        }
        
        # Log response being sent
        logger.info(f'[Campaigns API] GET /campaigns/{campaign_id} - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error fetching campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/')
async def create_campaign(campaign: CampaignCreate, request: Request, user_id: int = Depends(authenticate_token)) -> Dict[str, Any]:
    """Create a new campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] POST /campaigns - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        if not campaign.name:
            raise HTTPException(status_code=400, detail='Campaign name is required')
        
        db = get_database()
        cursor = db.execute(
            'INSERT INTO campaigns (user_id, name, description) VALUES (?, ?, ?)',
            (user_id, campaign.name, campaign.description)
        )
        db.commit()
        campaign_id = cursor.lastrowid
        
        row = db.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
        result = dict(row)
        
        # Log response being sent
        logger.info(f'[Campaigns API] POST /campaigns - Sending response with campaign_id={campaign_id}, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{campaign_id}')
async def update_campaign(
    campaign_id: int,
    campaign_update: CampaignUpdate,
    request: Request,
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] PUT /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_database()
        
        # Verify campaign belongs to user
        existing = db.execute(
            'SELECT * FROM campaigns WHERE id = ? AND user_id = ?',
            (campaign_id, user_id)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        # Build update query dynamically
        updates = []
        values = []
        
        if campaign_update.name is not None:
            updates.append('name = ?')
            values.append(campaign_update.name)
        if campaign_update.description is not None:
            updates.append('description = ?')
            values.append(campaign_update.description)
        
        if not updates:
            raise HTTPException(status_code=400, detail='No fields to update')
        
        updates.append('updated_at = CURRENT_TIMESTAMP')
        values.extend([campaign_id, user_id])
        query = f'UPDATE campaigns SET {", ".join(updates)} WHERE id = ? AND user_id = ?'
        
        db.execute(query, values)
        db.commit()
        
        row = db.execute('SELECT * FROM campaigns WHERE id = ?', (campaign_id,)).fetchone()
        result = dict(row)
        
        # Log response being sent
        logger.info(f'[Campaigns API] PUT /campaigns/{campaign_id} - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error updating campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{campaign_id}')
async def delete_campaign(campaign_id: int, request: Request, user_id: int = Depends(authenticate_token)) -> Dict[str, str]:
    """Delete a campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] DELETE /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_database()
        
        # Verify campaign belongs to user
        existing = db.execute(
            'SELECT * FROM campaigns WHERE id = ? AND user_id = ?',
            (campaign_id, user_id)
        ).fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        db.execute('DELETE FROM campaigns WHERE id = ? AND user_id = ?', (campaign_id, user_id))
        db.commit()
        
        result = {'message': 'Campaign deleted successfully'}
        
        # Log response being sent
        logger.info(f'[Campaigns API] DELETE /campaigns/{campaign_id} - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error deleting campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')

