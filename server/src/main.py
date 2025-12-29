from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import sys
import logging
from pathlib import Path



# Add parent directory to path to allow imports
server_dir = Path(__file__).parent.parent
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

from src.db.database import init_database
from src.db.firebase import init_firebase
from src.routes import auth, characters, sessions, campaigns, audio, scribe_token, analyze, conversational_ai, images, ioun

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Add exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Provide detailed validation error messages."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        message = error["msg"]
        errors.append(f"{field}: {message}")
    
    error_message = "Validation error: " + "; ".join(errors)
    logger.warning(f"Validation error on {request.url.path}: {error_message}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": error_message, "errors": exc.errors()}
    )

# Configure CORS
# When allow_credentials=True, we cannot use allow_origins=["*"]
# We need to specify exact origins
default_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8080",
    "https://eoasdev-529682581088.europe-west1.run.app",
    "https://eoas-529682581088.europe-west1.run.app"
]

cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    # Parse environment variable (comma-separated)
    allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    allowed_origins = default_origins

# Ensure production origin is always included
production_origin = "https://eoas-529682581088.europe-west1.run.app"
if production_origin not in allowed_origins:
    allowed_origins.append(production_origin)

logger.info(f"CORS allowed origins: {allowed_origins}")




app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting D&D Tracker Server...")
    
    # Initialize SQLite database (for campaigns, characters, sessions)
    init_database()
    
    # Initialize Firebase (for authentication and user data)
    try:
        init_firebase()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        logger.error("Authentication endpoints will not work without Firebase.")
        # Log what's missing
        if not os.getenv('FIREBASE_PROJECT_ID'):
            logger.error("  - FIREBASE_PROJECT_ID is not set")
        if not os.getenv('FIREBASE_CREDENTIALS_JSON') and not os.getenv('FIREBASE_CREDENTIALS_PATH') and not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
            logger.error("  - Firebase credentials not found. Set one of: FIREBASE_CREDENTIALS_JSON, FIREBASE_CREDENTIALS_PATH, or GOOGLE_APPLICATION_CREDENTIALS")
    
    # Ensure uploads directory exists for character images
    server_dir = Path(__file__).parent.parent
    uploads_dir = server_dir / "uploads" / "character_images"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Character images directory: {uploads_dir}")
    
    logger.info("Database initialized")
    logger.info("Server ready to accept requests")

# Health check endpoint
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Server is running"}

# Register routes
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])
app.include_router(characters.router, prefix="/api/characters", tags=["characters"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(scribe_token.router, tags=["scribe"])
app.include_router(conversational_ai.router, prefix="/api", tags=["conversational-ai"])
app.include_router(ioun.router, prefix="/api", tags=["ioun"])
app.include_router(images.router, prefix="/api/images", tags=["images"])

# Serve static images
server_dir = Path(__file__).parent.parent
uploads_dir = server_dir / "uploads"
if uploads_dir.exists():
    app.mount("/api/images", StaticFiles(directory=str(uploads_dir)), name="images")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3001))
    uvicorn.run(app, host="0.0.0.0", port=port)

