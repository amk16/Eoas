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
- `GEMINI_API_KEY`: Your Google Gemini API key (needed for Phase 7)
- `FIREBASE_PROJECT_ID`: Your Firebase project ID (for Firebase Authentication)
- `FIREBASE_CREDENTIALS_JSON`: Firebase service account JSON as a string (recommended for deployment)
  - OR `FIREBASE_CREDENTIALS_PATH`: Path to Firebase service account JSON file
  - OR `GOOGLE_APPLICATION_CREDENTIALS`: Path to credentials file (GCP standard)
- `FIREBASE_WEB_API_KEY`: Firebase Web API Key (found in Firebase Console > Project Settings > General > Web API Key)
  - Required for password authentication via REST API

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
- `POST /api/transcribe` - Transcribe audio using ElevenLabs Scribe

### Phase 7
- `POST /api/analyze` - Analyze transcript for damage/healing events

### Phase 8
- `POST /api/sessions/:id/damage-event` - Record damage/healing event
- `GET /api/sessions/:id/events` - Get session events

