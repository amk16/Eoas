from fastapi import HTTPException, Depends, Header
from typing import Optional
import jwt
import os


async def authenticate_token(authorization: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency to authenticate JWT tokens.
    Extracts userId (Firebase UID) from token and returns it for use in route handlers.
    
    Returns:
        Firebase UID as string (was previously integer user_id)
    """
    if not authorization:
        raise HTTPException(status_code=401, detail='Access token required')
    
    # Extract token from "Bearer TOKEN" format
    parts = authorization.split(' ')
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Access token required')
    
    token = parts[1]
    
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret:
        raise HTTPException(status_code=500, detail='JWT secret not configured')
    
    try:
        decoded = jwt.decode(token, jwt_secret, algorithms=['HS256'])
        user_id = decoded.get('userId')
        if not user_id:
            raise HTTPException(status_code=403, detail='Invalid or expired token')
        # user_id is now a Firebase UID (string) instead of integer
        return str(user_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail='Invalid or expired token')
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail='Invalid or expired token')

