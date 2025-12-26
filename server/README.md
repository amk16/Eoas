# D&D Tracker Server

Backend server for the D&D Audio Damage & Healing Tracker.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

3. Update `.env` with your API keys:
- `JWT_SECRET`: A random secret string for JWT token signing
- `GROQ_API_KEY`: Your Groq Cloud API key (needed for Phase 6)
- `GEMINI_API_KEY`: Your Google Gemini API key (needed for Phase 7)

## Running

Development mode (with auto-reload):
```bash
npm run dev
```

Build for production:
```bash
npm run build
npm start
```

The server will run on `http://localhost:3001` by default.

## API Endpoints

### Phase 1
- `GET /api/health` - Health check endpoint

### Phase 2
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user

### Phase 3
- `GET /api/characters` - Get user's characters
- `POST /api/characters` - Create new character
- `PUT /api/characters/:id` - Update character
- `DELETE /api/characters/:id` - Delete character

### Phase 4
- `GET /api/sessions` - Get user's sessions
- `POST /api/sessions` - Create new session
- `GET /api/sessions/:id` - Get session details
- `PUT /api/sessions/:id` - Update session
- `POST /api/sessions/:id/characters` - Add characters to session

### Phase 6
- `POST /api/transcribe` - Transcribe audio using Groq Cloud

### Phase 7
- `POST /api/analyze` - Analyze transcript for damage/healing events

### Phase 8
- `POST /api/sessions/:id/damage-event` - Record damage/healing event
- `GET /api/sessions/:id/events` - Get session events

