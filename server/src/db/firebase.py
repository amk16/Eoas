import os
import json
import logging
from pathlib import Path
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore, auth

logger = logging.getLogger(__name__)

_firebase_app: Optional[firebase_admin.App] = None
_firestore_db: Optional[firestore.Client] = None


def init_firebase() -> None:
    """Initialize Firebase Admin SDK."""
    global _firebase_app, _firestore_db
    
    if _firebase_app is not None:
        logger.info("Firebase already initialized")
        return
    
    try:
        # Get Firebase project ID from environment
        project_id = os.getenv('FIREBASE_PROJECT_ID')
        if not project_id:
            error_msg = "FIREBASE_PROJECT_ID not set. Firebase will not be initialized."
            logger.error(error_msg)
            raise RuntimeError(error_msg)
        
        cred = None
        
        # Priority 1: Check for JSON string in environment variable
        credentials_json = os.getenv('FIREBASE_CREDENTIALS_JSON')
        if credentials_json:
            try:
                # Try to parse the JSON
                cred_dict = json.loads(credentials_json)
                # Validate that it has required fields
                if not isinstance(cred_dict, dict):
                    raise ValueError("FIREBASE_CREDENTIALS_JSON must be a JSON object")
                if 'type' not in cred_dict or cred_dict.get('type') != 'service_account':
                    logger.warning("FIREBASE_CREDENTIALS_JSON may not be a valid service account JSON")
                cred = credentials.Certificate(cred_dict)
                logger.info("Using Firebase credentials from FIREBASE_CREDENTIALS_JSON environment variable")
            except json.JSONDecodeError as e:
                # Show a preview of the malformed JSON to help debug
                preview = credentials_json[:100] if len(credentials_json) > 100 else credentials_json
                logger.error(f"Failed to parse FIREBASE_CREDENTIALS_JSON: {e}")
                logger.error(f"JSON preview (first 100 chars): {preview}")
                logger.error("Tip: If the JSON contains special characters, make sure it's properly escaped.")
                logger.error("Alternative: Use FIREBASE_CREDENTIALS_PATH to point to a JSON file instead.")
                raise RuntimeError(f"Invalid JSON in FIREBASE_CREDENTIALS_JSON: {e}. Use FIREBASE_CREDENTIALS_PATH as an alternative.") from e
            except ValueError as e:
                logger.error(f"Invalid Firebase credentials format: {e}")
                raise RuntimeError(f"Invalid Firebase credentials format: {e}") from e
        else:
            # Priority 2: Check for file path
            credentials_path = os.getenv('FIREBASE_CREDENTIALS_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if credentials_path:
                cred_path = Path(credentials_path)
                if not cred_path.exists():
                    logger.warning(f"Firebase credentials file not found at {credentials_path}. Trying default credentials.")
                else:
                    cred = credentials.Certificate(str(cred_path))
                    logger.info(f"Using Firebase credentials from file: {credentials_path}")
        
        # Initialize Firebase app
        if cred:
            _firebase_app = firebase_admin.initialize_app(cred, {
                'projectId': project_id,
            })
        else:
            # Priority 3: Try to use default credentials (e.g., from GCP environment)
            try:
                _firebase_app = firebase_admin.initialize_app()
                logger.info("Using Firebase default credentials")
            except Exception as e:
                error_msg = f"Could not initialize Firebase with default credentials: {e}. Please provide FIREBASE_CREDENTIALS_JSON or FIREBASE_CREDENTIALS_PATH."
                logger.error(error_msg)
                raise RuntimeError(error_msg)
        
        # Initialize Firestore
        # Allow specifying a database ID (defaults to "(default)")
        database_id = os.getenv('FIREBASE_DATABASE_ID', '(default)')
        try:
            if database_id == '(default)':
                # For default database, don't specify database parameter
                _firestore_db = firestore.client()
            else:
                # For named databases, specify the database ID
                _firestore_db = firestore.client(database_id=database_id)
            logger.info(f"Firestore initialized with database: {database_id}")
        except Exception as e:
            error_msg = f"Failed to initialize Firestore with database '{database_id}': {e}"
            logger.error(error_msg)
            if "does not exist" in str(e) or "404" in str(e):
                logger.error(f"Database '{database_id}' does not exist in project '{project_id}'.")
                logger.error("Please ensure:")
                logger.error("1. The database is created in Firebase Console")
                logger.error("2. The database is created in Native mode (not Datastore mode)")
                logger.error("3. If using a named database, set FIREBASE_DATABASE_ID environment variable")
                logger.error(f"4. Check your databases at: https://console.cloud.google.com/firestore/databases?project={project_id}")
            raise RuntimeError(error_msg) from e
        
        logger.info(f"Firebase initialized successfully for project: {project_id}")
        
    except RuntimeError:
        # Re-raise RuntimeError as-is
        raise
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        raise RuntimeError(f"Failed to initialize Firebase: {e}") from e


def get_firebase_app() -> Optional[firebase_admin.App]:
    """Get the Firebase app instance."""
    if _firebase_app is None:
        logger.warning("Firebase not initialized. Call init_firebase() first.")
    return _firebase_app


def get_firestore() -> Optional[firestore.Client]:
    """Get the Firestore database client."""
    if _firestore_db is None:
        logger.warning("Firestore not initialized. Call init_firebase() first.")
    return _firestore_db


def get_auth() -> auth.Client:
    """Get the Firebase Auth client."""
    if _firebase_app is None:
        raise RuntimeError("Firebase not initialized. Call init_firebase() first.")
    return auth.Client(app=_firebase_app)

