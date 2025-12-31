# PickAxe - Dungeon Console

A comprehensive D&D campaign management tool with AI-powered voice assistant capabilities. PickAxe helps you organize campaigns, manage characters, track game sessions, and interact with an intelligent voice assistant for D&D discussions.

## Overview

PickAxe (Dungeon Console) is a full-stack application for managing Dungeons & Dragons campaigns. It features four main components that work together to provide a complete campaign management experience:

1. **Campaigns** - Organize and manage your D&D campaigns
2. **Characters** - Create and track your D&D characters
3. **Sessions** - Run game sessions with real-time transcription and event tracking
4. **Ioun** - AI-powered voice assistant for D&D discussions as well as creation 

## Installation & Setup

### Prerequisites

- **Node.js** (v18+ recommended)
- **Python** (3.8+)
- **Git**
- API Keys:
  - Google Cloud Platform account with Firebase and Gemini API enabled
  - ElevenLabs API key

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd Eoas
```

### Step 2: Backend Setup

1. Navigate to the server directory:
```bash
cd server
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the `server` directory:
```bash
# Copy from example if available, or create new
touch .env
```

4. Configure environment variables (see [Environment Variables](#environment-variables) section below)

### Step 3: Frontend Setup

1. Navigate back to the root directory:
```bash
cd ..
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Create a `.env` file in the root directory:
```bash
touch .env
```

4. Add the frontend environment variable:
```bash
echo "VITE_API_URL=http://localhost:3001" > .env
```

### Step 4: Running the Application

**Terminal 1 - Backend Server:**
```bash
cd server
uvicorn src.main:app --reload --port 3001
```

The backend will run on `http://localhost:3001`

**Terminal 2 - Frontend Development Server:**
```bash
# From root directory
npm run dev
```

The frontend will typically run on `http://localhost:5173` (or similar port)

### Step 5: Access the Application

1. Open your browser and navigate to the frontend URL (e.g., `http://localhost:5173`)
2. Register a new account or login
3. Start using PickAxe!

## Environment Variables

### Backend Environment Variables (`server/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | Yes | Random secret string for JWT token signing. Generate a secure random string. |
| `GEMINI_API_KEY` | Yes | Your Google Gemini API key. Get it from [Google AI Studio](https://makersuite.google.com/app/apikey) |
| `ELEVENLABS_API_KEY` | Yes | Your ElevenLabs API key. Get it from [ElevenLabs Dashboard](https://elevenlabs.io/app/settings/api-keys) |
| `FIREBASE_PROJECT_ID` | Yes | Your Firebase project ID. Found in Firebase Console > Project Settings |
| `FIREBASE_CREDENTIALS_JSON` | Yes* | Firebase service account JSON as a string (recommended for deployment). Get from Firebase Console > Project Settings > Service Accounts |
| `FIREBASE_CREDENTIALS_PATH` | Alternative | Path to Firebase service account JSON file (alternative to `FIREBASE_CREDENTIALS_JSON`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Alternative | Path to credentials file (GCP standard, alternative to above) |
| `FIREBASE_WEB_API_KEY` | Yes | Firebase Web API Key. Found in Firebase Console > Project Settings > General > Web API Key |
| `PORT` | No | Server port (default: 3001) |
| `DATABASE_PATH` | No | Path to SQLite database file (default: `data/dnd_tracker.db`) |
| `SCRIBE_RATE_LIMIT` | No | Rate limit for scribe token endpoint (default: 20 requests per 60 seconds) |

*Note: You need at least one of `FIREBASE_CREDENTIALS_JSON`, `FIREBASE_CREDENTIALS_PATH`, or `GOOGLE_APPLICATION_CREDENTIALS`

### Frontend Environment Variables (root `.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | Yes | Backend API URL (default: `http://localhost:3001` for development) |

## Four Main Components

### 1. Campaigns (`/campaigns`)

**Purpose**: Create and manage D&D campaigns that serve as containers for characters and sessions.

**Basic Actions**:
- Create new campaigns with name and description
- View campaign details and associated characters/sessions
- Edit campaign information
- Delete campaigns
- Generate campaign banner art using AI

**Information Flow**:
```
Create Campaign → Set Name/Description → Save → View Campaign
                                                      ↓
                                    Generate Art (optional) → AI generates banner image
                                                      ↓
                                    Link Characters/Sessions → View associated content
```

**Key Features**:
- Campaign banner art generation using Google Gemini image generation
- Link characters and sessions to campaigns
- View campaign overview with associated content

### 2. Characters (`/characters`)

**Purpose**: Create and manage D&D characters with full stat tracking and visual representation.

**Basic Actions**:
- Create new characters with stats (HP, AC, level, race, class, etc.)
- View character details in sidebar
- Edit character information
- Delete characters
- Generate character portrait art using AI
- Link characters to campaigns

**Information Flow**:
```
Create Character → Fill Stats/Details → Save → View Character List
                                                      ↓
                                    Generate Art (optional) → AI generates portrait
                                                      ↓
                                    Link to Campaign → Associate with campaign
                                                      ↓
                                    Use in Sessions → Add to game sessions
```

**Key Features**:
- Comprehensive character stat tracking (HP, AC, initiative, level, race, class)
- Character portrait generation using Google Gemini image generation
- Campaign association
- Session participation tracking

### 3. Sessions (`/sessions`)

**Purpose**: Create and manage game sessions with real-time transcription and automatic damage/healing event tracking.

**Basic Actions**:
- Create new sessions with name and optional campaign link
- Select characters to participate in the session
- Start/end sessions
- Real-time audio transcription using ElevenLabs Scribe
- Automatic detection of damage/healing events from transcript
- Manual event creation and editing
- View session history and events

**Information Flow**:
```
Create Session → Select Campaign (optional) → Select Characters → Start Session
                                                      ↓
                                    Real-time Transcription (ElevenLabs) → Audio to Text
                                                      ↓
                                    Transcript Analysis (Gemini) → Detect Events
                                                      ↓
                                    Event Tracking → Events Applied 
                                                      ↓
                                    End Session → Save Session Data
```

**Key Features**:
- Real-time speech-to-text transcription via ElevenLabs Scribe Realtime API
- AI-powered transcript analysis using Google Gemini to detect damage/healing events
- Automatic character health updates
- Initiative tracking
- Session history and event logs

### 4. Ioun (`/ioun-silence`)

**Purpose**: AI-powered voice assistant for D&D discussions, capable of understanding context and creating campaigns, characters, and sessions through natural conversation.

**Basic Actions**:
- Start voice conversation with Ioun
- Speak naturally about D&D topics
- Request creation of campaigns, characters, or sessions
- Receive AI-generated responses with text-to-speech audio
- View conversation history
- Manage multiple conversations

**Information Flow**:
```
User Speaks → ElevenLabs Scribe Transcription → Text Transcript
                                                      ↓
                                    Gemini Intent Detection → Identify Creation Requests
                                                      ↓
                                    MODE Analysis (Gemini) → Extract Required Fields
                                                      ↓
                                    Gemini Chat Response → Generate Contextual Response
                                                      ↓
                                    ElevenLabs TTS → Convert Response to Audio
                                                      ↓
                                    Execute Creations → Create Campaigns/Characters/Sessions
                                                      ↓
                                    Display Response + Audio → User Hears Response
```

**Key Features**:
- Real-time speech-to-text using ElevenLabs Scribe Realtime API
- Context-aware AI responses using Google Gemini
- Natural language creation of campaigns, characters, and sessions
- Text-to-speech audio responses using ElevenLabs TTS
- Conversation history stored in Firestore
- Intelligent field extraction and validation

## Google Cloud Platform Services

PickAxe uses several Google Cloud Platform services for authentication, data storage, and AI capabilities.

### Firebase Authentication

**What it is**: Google's authentication service that provides secure user management.

**How it's used**:
- User registration: Creates new user accounts with email and password
- User login: Authenticates users and issues JWT tokens
- Token verification: Validates JWT tokens on protected API endpoints
- User management: Stores user metadata and authentication state

**Configuration**:
- Requires `FIREBASE_PROJECT_ID` and `FIREBASE_WEB_API_KEY` environment variables
- Requires Firebase service account credentials for admin operations
- Users are stored in Firebase Authentication
- Authentication tokens are used for API authorization

### Firestore

**What it is**: Google's NoSQL document database, part of Firebase.

**How it's used**:
- **Campaigns Storage**: Stores campaign data (name, description, art URLs, user associations)
- **Characters Storage**: Stores character data (stats, art URLs, campaign associations)
- **Sessions Storage**: Stores session data (name, status, start/end times, campaign associations)
- **Conversations Storage**: Stores Ioun voice assistant conversation history
- **User Data**: Stores user profiles and preferences
- **Events**: Stores damage/healing events associated with sessions

**Data Structure**:
- Collections organized by user ID for data isolation
- Documents contain full entity data (campaigns, characters, sessions)
- Real-time updates supported through Firestore listeners

**Configuration**:
- Automatically initialized with Firebase setup
- Uses the same Firebase project as Authentication
- No additional configuration needed beyond Firebase setup

### Gemini API

**What it is**: Google's generative AI API that provides advanced language understanding and generation capabilities.

**How it's used in PickAxe**:

1. **Ioun Voice Assistant Chat** (`server/src/services/ioun_service.py`)
   - Generates contextual responses to user queries about D&D
   - Maintains conversation history and context
   - Uses `gemini-2.5-flash` model
   - Provides narrative-style responses for immersive experience

2. **Transcript Analysis** (`server/src/services/gemini_service.py`)
   - Analyzes transcribed speech to detect events
   - Extracts character names, damage amounts, and event types
   - Uses structured JSON output for event detection
   - Processes session transcripts in real-time

3. **Intent Detection** (`server/src/services/mode_analysis_service.py`)
   - Detects when users want to create campaigns, characters, or sessions
   - Analyzes natural language to identify creation requests
   - Returns ordered list of creation intents (campaign → character → session)

4. **MODE Analysis** (`server/src/services/mode_analysis_service.py`)
   - Extracts required fields for creating entities (campaigns, characters, sessions)
   - Validates completeness of creation requests
   - Generates follow-up questions for missing information
   - Uses structured extraction to populate entity data

5. **Image Generation** (`server/src/services/nano_banana_service.py`)
   - **Character Portraits**: Generates square (1:1) character art using `gemini-3-pro-image-preview`
   - **Campaign Banners**: Generates wide (21:9) campaign banner art
   - Creates D&D-themed artwork based on character/campaign descriptions
   - Stores generated images and returns URLs

6. **Transcript Correction** (`server/src/services/transcript_correction_service.py`)
   - Fixes common transcription errors before analysis
   - Improves accuracy of damage/healing event detection
   - Corrects D&D-specific terminology and character names
   - Uses `gemini-2.5-flash` model for corrections



**API Usage Patterns**:
- All Gemini calls are made server-side (never exposed to client)
- Responses are processed and validated before returning to client
- Error handling for API rate limits and failures
- Thread pool execution for non-blocking API calls

## ElevenLabs Services

PickAxe uses ElevenLabs for real-time speech processing and audio generation.

### ElevenLabs Scribe Realtime API

**What it is**: ElevenLabs' real-time speech-to-text API that provides low-latency transcription of spoken audio.

**How it's used**:

1. **Real-time Transcription** (`src/components/LiveScribeSilence.tsx`, `src/components/LiveScribe.tsx`)
   - WebSocket connection to ElevenLabs Realtime API
   - Streams audio chunks from browser microphone
   - Receives real-time transcript updates
   - Configures Voice Activity Detection (VAD) for silence detection
   - Used in Sessions for live transcription during gameplay
   - Used in Ioun voice assistant for speech input

2. **Backend Transcription** (`server/src/services/scribe_service.py`)
   - Server-side audio file transcription
   - Processes uploaded audio files
   - Returns transcript text and language detection
   - Used for batch transcription of recorded audio

3. **Token Generation** (`server/src/routes/scribe_token.py`)
   - Generates single-use tokens for client connections
   - Protects permanent API key from client exposure
   - Rate-limited endpoint (20 requests per 60 seconds by default)
   - Returns temporary token for WebSocket connection

**Configuration**:
- Requires `ELEVENLABS_API_KEY` environment variable
- Uses `scribe_v2_realtime` model
- Audio format: PCM 16kHz, 16-bit mono
- WebSocket URL: `wss://api.elevenlabs.io/v1/speech-to-text/realtime`

**Security**:
- Permanent API key stored only on backend
- Clients receive temporary single-use tokens
- Tokens expire after use
- Rate limiting prevents abuse

### ElevenLabs Text-to-Speech (TTS)

**What it is**: ElevenLabs' text-to-speech API that converts text into natural-sounding speech.

**How it's used**:

1. **Ioun Voice Assistant Responses** (`server/src/services/ioun_service.py`)
   - Converts Gemini-generated responses to speech
   - Provides audio playback of assistant responses
   - Supports multiple voice options
   - Returns base64-encoded audio for browser playback

**Configuration**:
- Uses same `ELEVENLABS_API_KEY` as Scribe
- Voice selection configurable per user/conversation
- Audio format optimized for web playback

**Usage Flow**:
```
Gemini generates text response → ElevenLabs TTS converts to audio → Base64 encoded → Sent to frontend → Audio playback
```

## Project Structure

```
google_hack/
├── src/                    # Frontend React application
│   ├── components/         # React components
│   │   ├── campaigns/     # Campaign management components
│   │   ├── characters/     # Character management components
│   │   ├── sessions/      # Session management components
│   │   ├── voice-assistant/# Ioun voice assistant components
│   │   └── layout/         # Layout components (SectionShell)
│   ├── services/           # API service layer
│   └── types/              # TypeScript type definitions
├── server/                 # Backend Python FastAPI application
│   ├── src/
│   │   ├── routes/         # API route handlers
│   │   ├── services/       # Business logic services
│   │   ├── db/             # Database and Firebase setup
│   │   └── middleware/     # Authentication middleware
│   └── requirements.txt    # Python dependencies
├── package.json            # Frontend dependencies
└── README.md              # This file
```

## Development

### Backend Development

```bash
cd server
uvicorn src.main:app --reload --port 3001
```

### Frontend Development

```bash
npm run dev
```


