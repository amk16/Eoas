from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from ..middleware.auth import authenticate_token
from ..db.database import get_database
from ..db.firebase import get_firestore
from firebase_admin import firestore
from ..services.nano_banana_service import generate_campaign_image

logger = logging.getLogger(__name__)


router = APIRouter()


class CampaignCreate(BaseModel):
    name: str
    description: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


@router.get('/')
async def get_campaigns(request: Request, user_id: str = Depends(authenticate_token)) -> List[Dict[str, Any]]:
    """Get all campaigns for the authenticated user."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        forwarded_for = request.headers.get('X-Forwarded-For', 'not-set')
        host = request.headers.get('Host', 'not-set')
        logger.info(f'[Campaigns API] GET /campaigns - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}, X-Forwarded-For={forwarded_for}, Host={host}')
        
        db = get_firestore()
        if not db:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Query nested collection: users/{user_id}/campaigns
        docs = db.collection('users').document(user_id).collection('campaigns').stream()
        
        campaigns = []
        for doc in docs:
            campaign_data = doc.to_dict()
            campaign_data['id'] = doc.id  # Add document ID
            
            # Convert Firestore timestamps to strings
            if 'created_at' in campaign_data and hasattr(campaign_data['created_at'], 'isoformat'):
                campaign_data['created_at'] = campaign_data['created_at'].isoformat()
            if 'updated_at' in campaign_data and hasattr(campaign_data['updated_at'], 'isoformat'):
                campaign_data['updated_at'] = campaign_data['updated_at'].isoformat()
            
            campaigns.append(campaign_data)
        
        # Sort by created_at descending
        campaigns.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Log response being sent
        logger.info(f'[Campaigns API] GET /campaigns - Sending response with {len(campaigns)} campaign(s), protocol={scheme}, forwarded_proto={forwarded_proto}')
        return campaigns
    except Exception as e:
        print(f'Error fetching campaigns: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{campaign_id}')
async def get_campaign(campaign_id: str, request: Request, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Get a single campaign by ID with characters and sessions."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] GET /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db_firestore = get_firestore()
        if not db_firestore:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Get campaign from Firestore nested collection
        campaign_ref = db_firestore.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        campaign_doc = campaign_ref.get()
        
        if not campaign_doc.exists:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        campaign = campaign_doc.to_dict()
        campaign['id'] = campaign_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in campaign and hasattr(campaign['created_at'], 'isoformat'):
            campaign['created_at'] = campaign['created_at'].isoformat()
        if 'updated_at' in campaign and hasattr(campaign['updated_at'], 'isoformat'):
            campaign['updated_at'] = campaign['updated_at'].isoformat()
        
        # Get characters for this campaign from Firestore subcollection
        characters_docs = db_firestore.collection('users').document(user_id).collection('characters').where('campaign_id', '==', campaign_id).stream()
        characters = []
        for doc in characters_docs:
            char_data = doc.to_dict()
            char_data['id'] = doc.id
            # Convert Firestore timestamps to strings
            if 'created_at' in char_data and hasattr(char_data['created_at'], 'isoformat'):
                char_data['created_at'] = char_data['created_at'].isoformat()
            if 'updated_at' in char_data and hasattr(char_data['updated_at'], 'isoformat'):
                char_data['updated_at'] = char_data['updated_at'].isoformat()
            characters.append(char_data)
        
        # Sort characters by created_at descending
        characters.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        # Get sessions for this campaign from Firestore subcollection
        sessions_docs = db_firestore.collection('users').document(user_id).collection('sessions').where('campaign_id', '==', campaign_id).stream()
        sessions = []
        for doc in sessions_docs:
            session_data = doc.to_dict()
            session_data['id'] = doc.id
            # Convert Firestore timestamps to strings
            if 'started_at' in session_data and hasattr(session_data['started_at'], 'isoformat'):
                session_data['started_at'] = session_data['started_at'].isoformat()
            if 'ended_at' in session_data and hasattr(session_data['ended_at'], 'isoformat'):
                session_data['ended_at'] = session_data['ended_at'].isoformat()
            sessions.append(session_data)
        
        # Sort sessions by started_at descending
        sessions.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        
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
async def create_campaign(campaign: CampaignCreate, request: Request, user_id: str = Depends(authenticate_token)) -> Dict[str, Any]:
    """Create a new campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[CAMPAIGNS] Creating campaign for user_id={user_id}, name={campaign.name}')
        logger.info(f'[CAMPAIGNS] Campaign data: {campaign.dict()}')
        logger.info(f'[CAMPAIGNS] Storage: Firestore')
        logger.info(f'[Campaigns API] POST /campaigns - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        if not campaign.name:
            raise HTTPException(status_code=400, detail='Campaign name is required')
        
        db = get_firestore()
        if not db:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        logger.info(f'[CAMPAIGNS] Got Firestore client')
        
        # Prepare campaign data for Firestore (no user_id needed - it's in the path)
        campaign_data = {
            'name': campaign.name,
            'description': campaign.description,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Remove None values
        campaign_data = {k: v for k, v in campaign_data.items() if v is not None}
        
        logger.info(f'[CAMPAIGNS] Saving to Firestore collection: users/{user_id}/campaigns')
        # Create document in nested collection: users/{user_id}/campaigns
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document()
        campaign_ref.set(campaign_data)
        campaign_id = campaign_ref.id
        logger.info(f'[CAMPAIGNS] Campaign saved to Firestore with id={campaign_id}')
        
        # Fetch the created document to return
        created_doc = campaign_ref.get()
        result = created_doc.to_dict()
        result['id'] = campaign_id  # Add document ID to result
        
        # Convert Firestore timestamps to strings for JSON serialization
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        # Log response being sent
        logger.info(f'[Campaigns API] POST /campaigns - Sending response with campaign_id={campaign_id}, protocol={scheme}, forwarded_proto={forwarded_proto}')
        logger.info(f'[CAMPAIGNS] Returning created campaign: {result}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error creating campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{campaign_id}')
async def update_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] PUT /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_firestore()
        if not db:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/campaigns/{campaign_id}
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        existing_doc = campaign_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        # Build update data
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        if campaign_update.name is not None:
            update_data['name'] = campaign_update.name
        if campaign_update.description is not None:
            update_data['description'] = campaign_update.description
        
        if len(update_data) == 1:  # Only updated_at
            raise HTTPException(status_code=400, detail='No fields to update')
        
        logger.info(f'[CAMPAIGNS] Updating Firestore document: users/{user_id}/campaigns/{campaign_id}')
        campaign_ref.update(update_data)
        logger.info(f'[CAMPAIGNS] Campaign updated in Firestore')
        
        # Fetch updated document
        updated_doc = campaign_ref.get()
        result = updated_doc.to_dict()
        result['id'] = campaign_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        
        # Log response being sent
        logger.info(f'[Campaigns API] PUT /campaigns/{campaign_id} - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error updating campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{campaign_id}')
async def delete_campaign(campaign_id: str, request: Request, user_id: str = Depends(authenticate_token)) -> Dict[str, str]:
    """Delete a campaign."""
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] DELETE /campaigns/{campaign_id} - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_firestore()
        if not db:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/campaigns/{campaign_id}
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        existing_doc = campaign_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        logger.info(f'[CAMPAIGNS] Deleting from Firestore: users/{user_id}/campaigns/{campaign_id}')
        campaign_ref.delete()
        logger.info(f'[CAMPAIGNS] Campaign deleted from Firestore')
        
        result = {'message': 'Campaign deleted successfully'}
        
        # Log response being sent
        logger.info(f'[Campaigns API] DELETE /campaigns/{campaign_id} - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
        return result
    except HTTPException:
        raise
    except Exception as e:
        print(f'Error deleting campaign: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{campaign_id}/generate-art')
async def generate_campaign_art(
    campaign_id: str,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Generate campaign banner art for a campaign using nano banana.
    Updates the campaign with the generated art URL and prompt.
    """
    try:
        # Log request protocol information
        scheme = request.url.scheme
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'not-set')
        logger.info(f'[Campaigns API] POST /campaigns/{campaign_id}/generate-art - Request protocol info: scheme={scheme}, X-Forwarded-Proto={forwarded_proto}')
        
        db = get_firestore()
        if not db:
            logger.error('[CAMPAIGNS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/campaigns/{campaign_id}
        campaign_ref = db.collection('users').document(user_id).collection('campaigns').document(str(campaign_id))
        campaign_doc = campaign_ref.get()
        
        if not campaign_doc.exists:
            raise HTTPException(status_code=404, detail='Campaign not found')
        
        campaign_data = campaign_doc.to_dict()
        campaign_data['id'] = campaign_id
        
        # Get characters for this campaign for context in prompt generation
        characters_docs = db.collection('users').document(user_id).collection('characters').where('campaign_id', '==', campaign_id).stream()
        characters = []
        for doc in characters_docs:
            char_data = doc.to_dict()
            char_data['id'] = doc.id
            # Convert Firestore timestamps to strings
            if 'created_at' in char_data and hasattr(char_data['created_at'], 'isoformat'):
                char_data['created_at'] = char_data['created_at'].isoformat()
            if 'updated_at' in char_data and hasattr(char_data['updated_at'], 'isoformat'):
                char_data['updated_at'] = char_data['updated_at'].isoformat()
            characters.append(char_data)
        
        # Get sessions for this campaign for context in prompt generation
        sessions_docs = db.collection('users').document(user_id).collection('sessions').where('campaign_id', '==', campaign_id).stream()
        sessions = []
        for doc in sessions_docs:
            session_data = doc.to_dict()
            session_data['id'] = doc.id
            # Convert Firestore timestamps to strings
            if 'started_at' in session_data and hasattr(session_data['started_at'], 'isoformat'):
                session_data['started_at'] = session_data['started_at'].isoformat()
            if 'ended_at' in session_data and hasattr(session_data['ended_at'], 'isoformat'):
                session_data['ended_at'] = session_data['ended_at'].isoformat()
            sessions.append(session_data)
        
        # Add characters and sessions to campaign data for prompt generation
        campaign_data['characters'] = characters
        campaign_data['sessions'] = sessions
        
        # Convert Firestore timestamps to strings for prompt generation
        if 'created_at' in campaign_data and hasattr(campaign_data['created_at'], 'isoformat'):
            campaign_data['created_at'] = campaign_data['created_at'].isoformat()
        if 'updated_at' in campaign_data and hasattr(campaign_data['updated_at'], 'isoformat'):
            campaign_data['updated_at'] = campaign_data['updated_at'].isoformat()
        
        # Generate art using nano banana service
        try:
            logger.info(f'[CAMPAIGNS] Generating banner art for campaign: {campaign_data.get("name", "Unknown")}')
            art_result = await generate_campaign_image(campaign_data)
            
            # Update campaign with generated art URL and prompt
            campaign_ref.update({
                'display_art_url': art_result['image_url'],
                'art_prompt': art_result['prompt'],
                'updated_at': firestore.SERVER_TIMESTAMP,
            })
            
            logger.info(f'[CAMPAIGNS] Successfully generated and saved banner art for campaign: {campaign_data.get("name", "Unknown")}')
            
            # Fetch updated campaign
            updated_doc = campaign_ref.get()
            result = updated_doc.to_dict()
            result['id'] = campaign_id
            
            # Convert Firestore timestamps to strings
            if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
                result['created_at'] = result['created_at'].isoformat()
            if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
                result['updated_at'] = result['updated_at'].isoformat()
            
            # Log response being sent
            logger.info(f'[Campaigns API] POST /campaigns/{campaign_id}/generate-art - Sending response, protocol={scheme}, forwarded_proto={forwarded_proto}')
            return result
        except Exception as e:
            logger.error(f'[CAMPAIGNS] Error generating campaign banner art: {e}')
            print(f'Error generating campaign art: {e}')
            raise HTTPException(
                status_code=500,
                detail=f'Failed to generate campaign banner art: {str(e)}'
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'[CAMPAIGNS] Error in generate_campaign_art endpoint: {e}')
        print(f'Error in generate_campaign_art endpoint: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')

