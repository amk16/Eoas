from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from ..services.firebase_service import (
    create_user as firebase_create_user,
    authenticate_user as firebase_authenticate_user,
    create_custom_jwt
)

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post('/register')
async def register(request: RegisterRequest):
    """Register a new user with Firebase."""
    email = request.email
    password = request.password
    
    # Validate email format (Pydantic EmailStr should handle this, but double-check)
    if not email or '@' not in email:
        raise HTTPException(status_code=400, detail='Invalid email format')
    
    # Validate password
    if not password:
        raise HTTPException(status_code=400, detail='Password is required')
    if len(password) < 6:
        raise HTTPException(status_code=400, detail='Password must be at least 6 characters')
    
    try:
        # Create user in Firebase
        user_data = firebase_create_user(email, password)
        uid = user_data['uid']
        
        # Generate custom JWT token for frontend compatibility
        token = create_custom_jwt(uid, email)
        
        return {
            'message': 'User created successfully',
            'token': token,
            'user': {
                'id': uid,
                'email': email
            }
        }
    except RuntimeError as e:
        # Firebase not initialized or configuration error
        error_msg = str(e)
        if 'not initialized' in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail='Authentication service is not available. Please check server configuration.'
            )
        raise HTTPException(status_code=500, detail=f'Configuration error: {str(e)}')
    except ValueError as e:
        # User already exists or validation error
        error_msg = str(e)
        if 'already exists' in error_msg.lower():
            raise HTTPException(status_code=400, detail='User with this email already exists')
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to create user: {str(e)}')


@router.post('/login')
async def login(request: LoginRequest):
    """Login user with Firebase."""
    email = request.email
    password = request.password
    
    try:
        # Authenticate user with Firebase
        user_data = firebase_authenticate_user(email, password)
        uid = user_data['uid']
        user_email = user_data['email']
        
        # Generate custom JWT token for frontend compatibility
        token = create_custom_jwt(uid, user_email)
        
        return {
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': uid,
                'email': user_email
            }
        }
    except RuntimeError as e:
        # Firebase not initialized or configuration error
        error_msg = str(e)
        if 'not initialized' in error_msg.lower():
            raise HTTPException(
                status_code=503,
                detail='Authentication service is not available. Please check server configuration.'
            )
        raise HTTPException(status_code=500, detail=f'Configuration error: {str(e)}')
    except ValueError as e:
        # Invalid credentials
        raise HTTPException(status_code=401, detail='Invalid email or password')
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Login failed: {str(e)}')

