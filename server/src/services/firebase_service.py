"""
Firebase service layer for authentication and user management.

This module provides functions for:
- User registration and authentication via Firebase Auth
- User profile management in Firestore
- JWT token generation for frontend compatibility
"""
import logging
from typing import Optional, Dict, Any
from firebase_admin import auth as firebase_auth
from firebase_admin.exceptions import FirebaseError
from firebase_admin import firestore
import jwt
import os
import httpx
from datetime import datetime, timedelta

from ..db.firebase import get_firestore, get_auth

logger = logging.getLogger(__name__)


def create_user(email: str, password: str) -> Dict[str, Any]:
    """
    Register a new user in Firebase Authentication.
    
    Args:
        email: User email address
        password: User password
        
    Returns:
        Dictionary with user data including uid and email
        
    Raises:
        ValueError: If user already exists or validation fails
        RuntimeError: If Firebase is not initialized
    """
    logger.info(f"create_user called for email: {email}")
    
    try:
        # get_auth() will raise RuntimeError if Firebase is not initialized
        logger.debug("Getting Firebase Auth client")
        auth_client = get_auth()
        logger.debug("Firebase Auth client obtained successfully")
        
        # Check if user already exists
        logger.debug(f"Checking if user with email {email} already exists")
        try:
            existing_user = auth_client.get_user_by_email(email)
            # User exists, raise error
            logger.warning(f"User with email {email} already exists (UID: {existing_user.uid})")
            raise ValueError(f"User with email {email} already exists")
        except firebase_auth.UserNotFoundError:
            # User doesn't exist, proceed with creation - this is expected
            logger.debug(f"User with email {email} does not exist, proceeding with creation")
            pass
        except ValueError:
            # Re-raise ValueError (user exists)
            logger.debug("Re-raising ValueError (user exists)")
            raise
        except Exception as e:
            # For other exceptions when checking, log but continue
            # Firebase create_user will handle duplicate email errors properly
            logger.warning(f"Error checking for existing user (will attempt creation anyway): {type(e).__name__}: {e}")
        
        # Create user in Firebase Auth
        logger.info(f"Creating new Firebase user for email: {email}")
        user_record = auth_client.create_user(
            email=email,
            password=password,
            email_verified=False
        )
        logger.info(f"Firebase user created successfully: UID={user_record.uid}, email={user_record.email}")
        
        # Create user profile in Firestore (optional - don't fail if Firestore is not available)
        logger.debug(f"Attempting to create Firestore profile for user: {user_record.uid}")
        try:
            create_user_profile(user_record.uid, email)
            logger.debug(f"Firestore profile created for user: {user_record.uid}")
        except Exception as e:
            # Firestore is optional - log warning but don't fail user creation
            logger.warning(f"Could not create Firestore profile for user {user_record.uid} (Firestore may not be available): {type(e).__name__}: {e}")
            logger.info("User created successfully in Firebase Auth, but Firestore profile creation was skipped")
        
        logger.info(f"User registration completed successfully: {user_record.uid} ({email})")
        
        return {
            'uid': user_record.uid,
            'email': user_record.email
        }
        
    except ValueError as e:
        logger.warning(f"ValueError in create_user for {email}: {e}")
        raise
    except FirebaseError as e:
        logger.error(f"Firebase error creating user for {email}: {type(e).__name__}: {e}")
        logger.error(f"Firebase error code: {getattr(e, 'code', 'N/A')}, message: {getattr(e, 'message', 'N/A')}")
        raise ValueError(f"Failed to create user: {str(e)}")
    except RuntimeError as e:
        logger.error(f"RuntimeError in create_user for {email}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating user for {email}: {type(e).__name__}: {e}", exc_info=True)
        raise RuntimeError(f"Failed to create user: {str(e)}")


def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """
    Authenticate a user with email and password using Firebase Auth REST API.
    
    Args:
        email: User email address
        password: User password
        
    Returns:
        Dictionary with user data including uid and email
        
    Raises:
        ValueError: If authentication fails
        RuntimeError: If Firebase is not initialized or API key not configured
    """
    logger.info(f"authenticate_user called for email: {email}")
    
    # Get Firebase Web API key from environment
    logger.debug("Checking FIREBASE_WEB_API_KEY configuration")
    web_api_key = os.getenv('FIREBASE_WEB_API_KEY')
    if not web_api_key:
        logger.error("FIREBASE_WEB_API_KEY not configured")
        raise RuntimeError("FIREBASE_WEB_API_KEY not configured. Required for password authentication.")
    logger.debug("FIREBASE_WEB_API_KEY found (length: %d)", len(web_api_key))
    
    logger.debug("Checking FIREBASE_PROJECT_ID configuration")
    project_id = os.getenv('FIREBASE_PROJECT_ID')
    if not project_id:
        logger.error("FIREBASE_PROJECT_ID not configured")
        raise RuntimeError("FIREBASE_PROJECT_ID not configured.")
    logger.debug(f"FIREBASE_PROJECT_ID: {project_id}")
    
    # Use Firebase Auth REST API to sign in with email/password
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={web_api_key}"
    logger.debug(f"Making authentication request to Firebase Auth API for email: {email}")
    
    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    
    try:
        logger.debug("Sending POST request to Firebase Auth API")
        response = httpx.post(url, json=payload, timeout=10.0)
        logger.debug(f"Firebase Auth API response status: {response.status_code}")
        
        response.raise_for_status()
        data = response.json()
        logger.debug("Firebase Auth API response received and parsed")
        
        if "error" in data:
            error_message = data["error"].get("message", "Authentication failed")
            error_code = data["error"].get("code", "N/A")
            logger.warning(f"Firebase auth error response: code={error_code}, message={error_message}")
            raise ValueError("Invalid email or password")
        
        # Extract user information
        uid = data.get("localId")
        email_verified = data.get("emailVerified", False)
        id_token = data.get("idToken")
        logger.debug(f"Authentication successful: uid={uid}, email_verified={email_verified}")
        
        if not uid:
            logger.error("Authentication response missing user ID (localId)")
            raise ValueError("Authentication failed: no user ID returned")
        
        # Get user details from Firebase Auth
        logger.debug(f"Fetching user details from Firebase Admin SDK for UID: {uid}")
        try:
            auth_client = get_auth()
            user_record = auth_client.get_user(uid)
            logger.debug(f"User record retrieved: uid={user_record.uid}, email={user_record.email}")
            
            # Update user profile in Firestore if needed (optional - don't fail if Firestore is not available)
            logger.debug(f"Attempting to check Firestore profile for user: {uid}")
            try:
                user_profile = get_user_by_id(uid)
                if not user_profile:
                    logger.info(f"Firestore profile not found for user {uid}, attempting to create new profile")
                    try:
                        create_user_profile(uid, email)
                        logger.debug(f"Firestore profile created for user: {uid}")
                    except Exception as e:
                        # Firestore is optional - log warning but don't fail authentication
                        logger.warning(f"Could not create Firestore profile for user {uid} (Firestore may not be available): {type(e).__name__}: {e}")
                else:
                    logger.debug(f"Firestore profile exists for user: {uid}")
            except Exception as e:
                # Firestore is optional - log warning but don't fail authentication
                logger.warning(f"Firestore operations failed for user {uid} (Firestore may not be available): {type(e).__name__}: {e}")
                logger.info("Authentication successful, but Firestore operations were skipped")
            
            logger.info(f"User authentication completed successfully: {uid} ({email})")
            
            return {
                'uid': uid,
                'email': user_record.email or email,
                'id_token': id_token  # Can be used for verification later
            }
        except RuntimeError as e:
            # Re-raise RuntimeError (e.g., Firebase Auth not initialized)
            logger.error(f"RuntimeError getting user details for {uid}: {e}")
            raise
        except Exception as e:
            # Only fail if we can't get user details from Firebase Auth
            # Firestore errors are handled above and don't cause authentication to fail
            logger.error(f"Error getting user details from Firebase Auth for {uid}: {type(e).__name__}: {e}", exc_info=True)
            raise ValueError("Authentication failed: could not retrieve user details from Firebase Auth")
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from Firebase Auth API: status={e.response.status_code}")
        if e.response.status_code == 400:
            try:
                error_data = e.response.json()
                error_message = error_data.get("error", {}).get("message", "Invalid email or password")
                error_code = error_data.get("error", {}).get("code", "N/A")
                logger.warning(f"Firebase auth HTTP 400 error: code={error_code}, message={error_message}")
            except Exception:
                logger.warning(f"Firebase auth HTTP 400 error: {e.response.text[:200]}")
            raise ValueError("Invalid email or password")
        logger.error(f"Firebase authentication request failed with status {e.response.status_code}: {e}")
        raise RuntimeError(f"Firebase authentication request failed: {e}")
    except httpx.RequestError as e:
        logger.error(f"Request error connecting to Firebase Auth API: {type(e).__name__}: {e}")
        raise RuntimeError(f"Failed to connect to Firebase: {e}")
    except ValueError as e:
        logger.warning(f"ValueError in authenticate_user for {email}: {e}")
        raise
    except RuntimeError as e:
        logger.error(f"RuntimeError in authenticate_user for {email}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error authenticating user {email}: {type(e).__name__}: {e}", exc_info=True)
        raise ValueError(f"Authentication failed: {str(e)}")


def get_user_by_id(uid: str) -> Optional[Dict[str, Any]]:
    """
    Get user data from Firestore by Firebase UID.
    
    Note: Firestore is optional. This function returns None if Firestore is not available.
    
    Args:
        uid: Firebase user UID
        
    Returns:
        Dictionary with user data or None if not found or Firestore is not available
    """
    logger.debug(f"get_user_by_id called for UID: {uid}")
    
    try:
        db = get_firestore()
        if not db:
            logger.debug("Firestore not initialized in get_user_by_id (this is OK if Firestore is not being used)")
            return None
        
        logger.debug(f"Querying Firestore for user document: users/{uid}")
        user_ref = db.collection('users').document(uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            logger.debug(f"User document not found in Firestore for UID: {uid}")
            return None
        
        user_data = user_doc.to_dict()
        user_data['uid'] = uid
        logger.debug(f"User data retrieved from Firestore for UID: {uid}")
        return user_data
        
    except Exception as e:
        # Firestore is optional - log as debug/warning, not error
        logger.debug(f"Firestore not available for get_user_by_id {uid}: {type(e).__name__}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get user data from Firestore by email.
    
    Args:
        email: User email address
        
    Returns:
        Dictionary with user data or None if not found
    """
    logger.debug(f"get_user_by_email called for email: {email}")
    
    try:
        db = get_firestore()
        if not db:
            logger.warning("Firestore not initialized in get_user_by_email")
            return None
        
        # Query Firestore for user with matching email
        logger.debug(f"Querying Firestore for user with email: {email}")
        users_ref = db.collection('users')
        query = users_ref.where('email', '==', email).limit(1)
        docs = query.stream()
        
        for doc in docs:
            user_data = doc.to_dict()
            user_data['uid'] = doc.id
            logger.debug(f"User found in Firestore: UID={doc.id}, email={email}")
            return user_data
        
        logger.debug(f"No user found in Firestore with email: {email}")
        return None
        
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {type(e).__name__}: {e}", exc_info=True)
        return None


def verify_firebase_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Firebase ID token and return decoded token data.
    
    Args:
        token: Firebase ID token string
        
    Returns:
        Dictionary with decoded token data or None if invalid
    """
    logger.debug("verify_firebase_token called")
    
    try:
        auth_client = get_auth()
        logger.debug("Verifying Firebase ID token")
        decoded_token = auth_client.verify_id_token(token)
        logger.debug(f"Firebase ID token verified successfully: uid={decoded_token.get('uid', 'N/A')}")
        return decoded_token
    except firebase_auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase ID token: {e}")
        return None
    except firebase_auth.ExpiredIdTokenError as e:
        logger.warning(f"Expired Firebase ID token: {e}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Firebase token: {type(e).__name__}: {e}", exc_info=True)
        return None


def create_custom_jwt(uid: str, email: str) -> str:
    """
    Generate a custom JWT token for frontend compatibility.
    
    This maintains the same JWT format as the current SQLite-based system
    so the frontend doesn't need to change.
    
    Note: For backward compatibility, we use the Firebase UID as userId.
    In Phase 3-5, we may add integer ID mapping if needed.
    
    Args:
        uid: Firebase user UID (will be used as userId in JWT)
        email: User email address
        
    Returns:
        JWT token string
    """
    logger.debug(f"create_custom_jwt called for UID: {uid}, email: {email}")
    
    jwt_secret = os.getenv('JWT_SECRET')
    if not jwt_secret:
        logger.error("JWT_SECRET not configured")
        raise RuntimeError("JWT_SECRET not configured")
    logger.debug("JWT_SECRET found")
    
    # Create JWT with same format as current system
    # Using UID as userId (string) - will need to handle in middleware/routes
    exp_time = datetime.utcnow() + timedelta(days=7)
    payload = {
        'userId': uid,  # Using Firebase UID as userId
        'email': email,
        'exp': exp_time
    }
    logger.debug(f"Creating JWT with payload: userId={uid}, email={email}, exp={exp_time}")
    
    token = jwt.encode(payload, jwt_secret, algorithm='HS256')
    logger.debug("JWT token created successfully")
    return token


def create_user_profile(uid: str, email: str, legacy_id: Optional[int] = None) -> None:
    """
    Create or update a user profile document in Firestore.
    
    Note: Firestore is optional. This function will raise an exception if Firestore is not available,
    but callers should catch and handle this gracefully.
    
    Args:
        uid: Firebase user UID
        email: User email address
        legacy_id: Optional legacy integer ID for migration purposes
        
    Raises:
        RuntimeError: If Firestore is not initialized
        Exception: If Firestore operations fail
    """
    logger.debug(f"create_user_profile called for UID: {uid}, email: {email}, legacy_id: {legacy_id}")
    
    try:
        db = get_firestore()
        if not db:
            logger.warning("Firestore not initialized in create_user_profile")
            raise RuntimeError("Firestore not initialized")
        
        user_ref = db.collection('users').document(uid)
        logger.debug(f"Accessing Firestore document: users/{uid}")
        
        # Get existing data if it exists
        existing_doc = user_ref.get()
        existing_data = existing_doc.to_dict() if existing_doc.exists else {}
        logger.debug(f"Existing document exists: {existing_doc.exists}")
        
        # Prepare user data
        user_data = {
            'email': email,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        
        # Add legacy_id if provided
        if legacy_id is not None:
            user_data['legacy_id'] = legacy_id
            logger.debug(f"Adding legacy_id to user data: {legacy_id}")
        
        # Set or update the document
        if existing_doc.exists:
            # Update existing document (preserve created_at)
            logger.debug(f"Updating existing Firestore profile for user: {uid}")
            user_ref.update(user_data)
            logger.info(f"Updated Firestore profile for user: {uid}")
        else:
            # Create new document with created_at
            logger.debug(f"Creating new Firestore profile for user: {uid}")
            user_data['created_at'] = firestore.SERVER_TIMESTAMP
            user_ref.set(user_data)
            logger.info(f"Created Firestore profile for user: {uid}")
            
    except RuntimeError as e:
        logger.warning(f"RuntimeError creating/updating user profile for {uid}: {e}")
        raise
    except Exception as e:
        logger.warning(f"Error creating/updating user profile for {uid}: {type(e).__name__}: {e}")
        raise

