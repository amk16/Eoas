# D&D Tracker Server (Python)

Backend server for the D&D Audio Damage & Healing Tracker - Python FastAPI implementation.

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure you have a `.env` file with the required environment variables:
- `JWT_SECRET`: A random secret string for JWT token signing
- `GROQ_API_KEY`: Your Groq Cloud API key (needed for audio transcription)
- `ELEVENLABS_API_KEY`: Your ElevenLabs API key (needed for realtime scribe transcription)
- `PORT`: Server port (default: 3001)
- `DATABASE_PATH`: Optional path to SQLite database (default: `data/dnd_tracker.db`)
- `SCRIBE_RATE_LIMIT`: Optional rate limit for scribe token endpoint (default: 20 requests per 60 seconds)

## Running

Development mode (with auto-reload):
```bash
cd server
uvicorn src.main:app --reload --port 3001
```

Production mode:
```bash
cd server
uvicorn src.main:app --host 0.0.0.0 --port 3001
```

Or run as a module:
```bash
cd server
python -m src.main
```

**Note:** Make sure you run these commands from the `server` directory so Python can find the `src` package.

The server will run on `http://localhost:3001` by default.

## API Endpoints

All endpoints match the original Node.js server:

### Health Check
- `GET /api/health` - Health check endpoint

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user

### Characters
- `GET /api/characters` - Get user's characters
- `POST /api/characters` - Create new character
- `PUT /api/characters/:id` - Update character
- `DELETE /api/characters/:id` - Delete character

### Sessions
- `GET /api/sessions` - Get user's sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/:id` - Get session details
- `PUT /api/sessions/:id` - Update session
- `POST /api/sessions/:id/characters` - Add characters to session
- `GET /api/sessions/:id/events` - Get session events

### Audio
- `POST /api/audio/transcribe` - Transcribe audio using Groq Cloud

### ElevenLabs Scribe
- `GET /api/scribe-token` - Generate single-use token for ElevenLabs Realtime Scribe streaming
  - Rate limited: 20 requests per 60 seconds per IP (configurable via `SCRIBE_RATE_LIMIT`)
  - Returns a token that can be used to connect to ElevenLabs Realtime API
  - Never exposes the permanent `ELEVENLABS_API_KEY` to clients

## Database

The server uses the same SQLite database as the Node.js version. The database file is located at `data/dnd_tracker.db` by default. All existing data will be preserved.

## Notes

- The Python server maintains 100% API compatibility with the original Node.js server
- All environment variables and database schemas remain the same
- The server uses FastAPI which provides automatic OpenAPI documentation at `/docs`

