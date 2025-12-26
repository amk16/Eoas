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
    email = request.email
    password = request.password
    
    db = get_database()
    
    # Find user by email
    user = db.execute(
        'SELECT id, email, password_hash FROM users WHERE email = ?',
        (email,)
    ).fetchone()
    
    if not user:
        raise HTTPException(status_code=401, detail='Invalid email or password')
    
    # Verify password
    password_match = bcrypt.checkpw(
        password.encode('utf-8'),
        user['password_hash'].encode('utf-8')
    )
    if not password_match:
        raise HTTPException(status_code=401, detail='Invalid email or password')
    
    # Generate JWT token
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret:
        raise HTTPException(status_code=500, detail='JWT secret not configured')
    
    token = jwt.encode(
        {'userId': user['id'], 'exp': datetime.utcnow() + timedelta(days=7)},
        jwt_secret,
        algorithm='HS256'
    )
    
    return {
        'message': 'Login successful',
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email']
        }
    }

