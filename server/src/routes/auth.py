from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from ..db.database import get_database


router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post('/register')
async def register(request: RegisterRequest):
    """Register a new user."""
    email = request.email
    password = request.password
    
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail='Password must be at least 6 characters')
    
    db = get_database()
    
    # Check if user already exists
    existing_user = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
    if existing_user:
        raise HTTPException(status_code=400, detail='User with this email already exists')
    
    # Hash password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    # Insert new user
    cursor = db.execute('INSERT INTO users (email, password_hash) VALUES (?, ?)', (email, password_hash))
    db.commit()
    user_id = cursor.lastrowid
    
    # Generate JWT token
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret:
        raise HTTPException(status_code=500, detail='JWT secret not configured')
    
    token = jwt.encode(
        {'userId': user_id, 'exp': datetime.utcnow() + timedelta(days=7)},
        jwt_secret,
        algorithm='HS256'
    )
    
    return {
        'message': 'User created successfully',
        'token': token,
        'user': {
            'id': user_id,
            'email': email
        }
    }


@router.post('/login')
async def login(request: LoginRequest):
    """Login user."""
    import logging
    logger = logging.getLogger(__name__)
    
    email = request.email
    password = request.password
    
    logger.info(f"Login attempt for email: {email}")
    
    db = get_database()
    
    # Find user by email
    user = db.execute(
        'SELECT id, email, password_hash FROM users WHERE email = ?',
        (email,)
    ).fetchone()
    
    if not user:
        logger.warning(f"Login failed: User not found for email: {email}")
        raise HTTPException(status_code=401, detail='Invalid email or password')
    
    logger.info(f"User found: id={user['id']}, email={user['email']}")
    
    # Verify password
    try:
        password_match = bcrypt.checkpw(
            password.encode('utf-8'),
            user['password_hash'].encode('utf-8')
        )
        if not password_match:
            logger.warning(f"Login failed: Invalid password for email: {email}")
            raise HTTPException(status_code=401, detail='Invalid email or password')
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        raise HTTPException(status_code=401, detail='Invalid email or password')
    
    # Generate JWT token
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret:
        logger.error("JWT_SECRET not configured")
        raise HTTPException(status_code=500, detail='JWT secret not configured')
    
    token = jwt.encode(
        {'userId': user['id'], 'exp': datetime.utcnow() + timedelta(days=7)},
        jwt_secret,
        algorithm='HS256'
    )
    
    logger.info(f"Login successful for user: {email}")
    
    return {
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email']
        }
    }

