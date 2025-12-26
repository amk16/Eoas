from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
from src.routes import auth, characters, sessions, campaigns, audio, scribe_token, analyze, conversational_ai, images

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

# Configure CORS
# When allow_credentials=True, we cannot use allow_origins=["*"]
# We need to specify exact origins
allowed_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://localhost:8080,https://eoas-529682581088.europe-west1.run.app"
).split(",")
# Strip whitespace from each origin
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]

logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    logger.info("Starting D&D Tracker Server...")
    init_database()
    
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

