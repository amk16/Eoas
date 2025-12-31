from fastapi import APIRouter, HTTPException, Depends
from starlette.requests import Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
from ..middleware.auth import authenticate_token
from ..db.firebase import get_firestore
from firebase_admin import firestore

logger = logging.getLogger(__name__)

router = APIRouter()


class ConversationCreate(BaseModel):
    title: Optional[str] = None  # Auto-generated from first message if not provided


class ConversationUpdate(BaseModel):
    title: Optional[str] = None


class MessageCreate(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


@router.get('/')
async def get_conversations(
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """Get all conversations for the authenticated user."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Query nested collection: users/{user_id}/conversations
        docs = db.collection('users').document(user_id).collection('conversations').stream()
        
        conversations = []
        for doc in docs:
            conv_data = doc.to_dict()
            conv_data['id'] = doc.id  # Add document ID
            
            # Convert Firestore timestamps to strings
            if 'created_at' in conv_data and hasattr(conv_data['created_at'], 'isoformat'):
                conv_data['created_at'] = conv_data['created_at'].isoformat()
            if 'updated_at' in conv_data and hasattr(conv_data['updated_at'], 'isoformat'):
                conv_data['updated_at'] = conv_data['updated_at'].isoformat()
            if 'last_message_at' in conv_data and hasattr(conv_data['last_message_at'], 'isoformat'):
                conv_data['last_message_at'] = conv_data['last_message_at'].isoformat()
            
            conversations.append(conv_data)
        
        # Sort by last_message_at descending (most recent first)
        conversations.sort(key=lambda x: x.get('last_message_at', ''), reverse=True)
        
        logger.info(f'[CONVERSATIONS] Returning {len(conversations)} conversations for user {user_id}')
        return conversations
    except Exception as e:
        logger.error(f'Error fetching conversations: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.get('/{conversation_id}')
async def get_conversation(
    conversation_id: str,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Get a single conversation by ID with messages."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Get conversation from Firestore nested collection
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(str(conversation_id))
        conv_doc = conv_ref.get()
        
        if not conv_doc.exists:
            raise HTTPException(status_code=404, detail='Conversation not found')
        
        conversation = conv_doc.to_dict()
        conversation['id'] = conversation_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in conversation and hasattr(conversation['created_at'], 'isoformat'):
            conversation['created_at'] = conversation['created_at'].isoformat()
        if 'updated_at' in conversation and hasattr(conversation['updated_at'], 'isoformat'):
            conversation['updated_at'] = conversation['updated_at'].isoformat()
        if 'last_message_at' in conversation and hasattr(conversation['last_message_at'], 'isoformat'):
            conversation['last_message_at'] = conversation['last_message_at'].isoformat()
        
        # Get messages from Firestore subcollection
        messages_ref = conv_ref.collection('messages')
        messages_docs = messages_ref.order_by('timestamp', direction=firestore.Query.ASCENDING).stream()
        
        messages = []
        for doc in messages_docs:
            msg_data = doc.to_dict()
            msg_data['id'] = doc.id
            
            # Convert Firestore timestamp to string
            if 'timestamp' in msg_data and hasattr(msg_data['timestamp'], 'isoformat'):
                msg_data['timestamp'] = msg_data['timestamp'].isoformat()
            
            messages.append(msg_data)
        
        result = {
            **conversation,
            'messages': messages
        }
        
        logger.info(f'[CONVERSATIONS] Returning conversation {conversation_id} with {len(messages)} messages')
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error fetching conversation: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/')
async def create_conversation(
    conversation: ConversationCreate,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Create a new conversation."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Prepare conversation data for Firestore
        conversation_data = {
            'title': conversation.title or 'New Conversation',
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
            'last_message_at': firestore.SERVER_TIMESTAMP,
        }
        
        # Create document in nested collection: users/{user_id}/conversations
        conv_ref = db.collection('users').document(user_id).collection('conversations').document()
        conv_ref.set(conversation_data)
        conversation_id = conv_ref.id
        
        logger.info(f'[CONVERSATIONS] Created conversation {conversation_id} for user {user_id}')
        
        # Fetch the created document to return
        created_doc = conv_ref.get()
        result = created_doc.to_dict()
        result['id'] = conversation_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        if 'last_message_at' in result and hasattr(result['last_message_at'], 'isoformat'):
            result['last_message_at'] = result['last_message_at'].isoformat()
        
        return result
    except Exception as e:
        logger.error(f'Error creating conversation: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.put('/{conversation_id}')
async def update_conversation(
    conversation_id: str,
    conversation_update: ConversationUpdate,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Update a conversation."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/conversations/{conversation_id}
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(str(conversation_id))
        existing_doc = conv_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Conversation not found')
        
        # Build update data
        update_data = {
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        if conversation_update.title is not None:
            update_data['title'] = conversation_update.title
        
        if len(update_data) == 1:  # Only updated_at
            raise HTTPException(status_code=400, detail='No fields to update')
        
        logger.info(f'[CONVERSATIONS] Updating conversation {conversation_id}')
        conv_ref.update(update_data)
        
        # Fetch updated document
        updated_doc = conv_ref.get()
        result = updated_doc.to_dict()
        result['id'] = conversation_id
        
        # Convert Firestore timestamps to strings
        if 'created_at' in result and hasattr(result['created_at'], 'isoformat'):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and hasattr(result['updated_at'], 'isoformat'):
            result['updated_at'] = result['updated_at'].isoformat()
        if 'last_message_at' in result and hasattr(result['last_message_at'], 'isoformat'):
            result['last_message_at'] = result['last_message_at'].isoformat()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating conversation: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.delete('/{conversation_id}')
async def delete_conversation(
    conversation_id: str,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, str]:
    """Delete a conversation and all its messages."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Access nested collection: users/{user_id}/conversations/{conversation_id}
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(str(conversation_id))
        existing_doc = conv_ref.get()
        
        if not existing_doc.exists:
            raise HTTPException(status_code=404, detail='Conversation not found')
        
        # Delete all messages in the subcollection first
        messages_ref = conv_ref.collection('messages')
        messages_docs = messages_ref.stream()
        batch = db.batch()
        message_count = 0
        for doc in messages_docs:
            batch.delete(doc.reference)
            message_count += 1
            # Firestore batch limit is 500 operations
            if message_count >= 500:
                batch.commit()
                batch = db.batch()
                message_count = 0
        
        if message_count > 0:
            batch.commit()
        
        # Delete the conversation document
        logger.info(f'[CONVERSATIONS] Deleting conversation {conversation_id} and {message_count} messages')
        conv_ref.delete()
        
        return {'message': 'Conversation deleted successfully'}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting conversation: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')


@router.post('/{conversation_id}/messages')
async def add_message(
    conversation_id: str,
    message: MessageCreate,
    request: Request,
    user_id: str = Depends(authenticate_token)
) -> Dict[str, Any]:
    """Add a message to a conversation."""
    try:
        db = get_firestore()
        if not db:
            logger.error('[CONVERSATIONS] Firestore not initialized')
            raise HTTPException(status_code=500, detail='Firestore not available')
        
        # Verify conversation exists
        conv_ref = db.collection('users').document(user_id).collection('conversations').document(str(conversation_id))
        conv_doc = conv_ref.get()
        
        if not conv_doc.exists:
            raise HTTPException(status_code=404, detail='Conversation not found')
        
        # Validate role
        if message.role not in ['user', 'assistant']:
            raise HTTPException(status_code=400, detail="Role must be 'user' or 'assistant'")
        
        # Prepare message data
        message_data = {
            'role': message.role,
            'content': message.content,
            'timestamp': firestore.SERVER_TIMESTAMP,
        }
        
        # Add message to subcollection
        messages_ref = conv_ref.collection('messages')
        msg_ref = messages_ref.document()
        msg_ref.set(message_data)
        message_id = msg_ref.id
        
        # Update conversation's last_message_at and updated_at
        conv_ref.update({
            'last_message_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        })
        
        # Auto-generate title from first user message if title is still default
        if message.role == 'user':
            conv_data = conv_doc.to_dict()
            if conv_data and conv_data.get('title') == 'New Conversation':
                # Generate title from first 50 characters of first user message
                title = message.content[:50].strip()
                if len(message.content) > 50:
                    title += '...'
                conv_ref.update({'title': title})
        
        logger.info(f'[CONVERSATIONS] Added message {message_id} to conversation {conversation_id}')
        
        # Fetch the created message to return
        created_doc = msg_ref.get()
        result = created_doc.to_dict()
        result['id'] = message_id
        
        # Convert Firestore timestamp to string
        if 'timestamp' in result and hasattr(result['timestamp'], 'isoformat'):
            result['timestamp'] = result['timestamp'].isoformat()
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error adding message: {e}')
        raise HTTPException(status_code=500, detail='Internal server error')



