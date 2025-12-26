# Testing Guide - Phases 1-3

## Prerequisites

1. Make sure you have Node.js installed (v18+ recommended)
2. Both frontend and backend dependencies are installed

## Setup

### 1. Backend Setup

Navigate to the server directory:
```bash
cd server
```

Create a `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
```
PORT=3001
JWT_SECRET=your-random-secret-key-here-change-this
DATABASE_PATH=./data/dnd_tracker.db
```

**Note**: For Phases 1-3, you don't need `GEMINI_API_KEY` yet (that's for later phases).

Start the backend server:
```bash
npm run dev
```

You should see:
```
Database tables created successfully
Database initialized at: ...
Server is running on http://localhost:3001
```

### 2. Frontend Setup

In a **new terminal**, navigate to the project root:
```bash
cd /Users/ehabriaz/Desktop/google_hack
```

Create a `.env` file in the root directory:
```bash
echo "VITE_API_URL=http://localhost:3001" > .env
```

Start the frontend:
```bash
npm run dev
```

The frontend should open at `http://localhost:5173` (or similar port).

## Testing Checklist

### Phase 1: Backend Foundation
- [ ] Backend server starts without errors
- [ ] Database file is created in `server/data/dnd_tracker.db`
- [ ] Health check works: Visit `http://localhost:3001/api/health` in browser
  - Should return: `{"status":"ok","message":"Server is running"}`

### Phase 2: Authentication
- [ ] Can access `/register` page
- [ ] Can create a new account with email and password
- [ ] After registration, automatically logged in and redirected to home
- [ ] Can logout
- [ ] Can access `/login` page
- [ ] Can login with created credentials
- [ ] After login, redirected to home
- [ ] Cannot access `/` (home) without being logged in (redirects to login)
- [ ] Token persists after page refresh (stays logged in)

### Phase 3: Character Management
- [ ] Can navigate to `/characters` from home page
- [ ] See empty state when no characters exist
- [ ] Can click "Create Character" button
- [ ] Can create a new character with name and max HP
- [ ] After creation, redirected to character list
- [ ] Character appears in the list
- [ ] Can click "Edit" on a character
- [ ] Can modify character name and max HP
- [ ] Changes are saved and reflected in the list
- [ ] Can click "Delete" on a character
- [ ] Confirmation dialog appears
- [ ] Character is deleted after confirmation
- [ ] Character disappears from list

## Common Issues

### Backend won't start
- Check that `.env` file exists in `server/` directory
- Verify `JWT_SECRET` is set in `.env`
- Check if port 3001 is already in use

### Frontend can't connect to backend
- Verify backend is running on port 3001
- Check that `VITE_API_URL=http://localhost:3001` is in root `.env` file
- Check browser console for CORS errors

### Database errors
- Delete `server/data/dnd_tracker.db` and restart server (will recreate)
- Check file permissions on `server/data/` directory

### Authentication issues
- Clear browser localStorage: `localStorage.clear()` in browser console
- Check that JWT_SECRET is set in backend `.env`
- Verify token is being stored: Check browser DevTools > Application > Local Storage

## Next Steps After Testing

Once you've verified Phases 1-3 work correctly, we can proceed to:
- **Phase 4**: Session Management
- **Phase 5**: Audio Capture (Frontend)
- **Phase 6**: ElevenLabs Scribe Transcription
- And so on...

Let me know if you encounter any issues during testing!

