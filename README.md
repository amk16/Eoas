# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

## ElevenLabs Scribe Realtime Integration

This project includes ElevenLabs Scribe Realtime streaming for live transcription.

### Local Testing

#### Prerequisites
1. Set up the backend server (see `server/README_PYTHON.md`)
2. Install frontend dependencies: `npm install` (no additional packages needed - uses native WebSocket)
3. Set environment variable `ELEVENLABS_API_KEY` in your backend `.env` file

#### Running Locally

**Backend:**
```bash
cd server
# Set ELEVENLABS_API_KEY in .env file
uvicorn src.main:app --reload --port 3001
```

**Frontend:**
```bash
# From project root
npm run dev
```

#### Testing the Live Scribe Feature

1. Start both backend and frontend servers
2. Navigate to `http://localhost:5173/scribe` (or your Vite dev server URL)
3. Click "Start Transcription"
4. Grant microphone permissions when prompted
5. Speak into your microphone
6. Observe:
   - Partial transcripts appear in real-time (shown in gray/italic)
   - Committed transcripts appear as you speak (shown in bold)
   - Connection status indicator
7. Click "Stop Transcription" to end the session

#### Rate Limiting

The backend enforces rate limiting: **20 requests per 60 seconds per IP** by default. This can be configured via the `SCRIBE_RATE_LIMIT` environment variable.

### Vercel Deployment

**Important:** The frontend is hosted on Vercel, but the backend must be deployed separately (Vercel is frontend-only for this setup).

#### Environment Variables in Vercel

1. Navigate to your Vercel project settings
2. Go to **Settings** > **Environment Variables**
3. Add `ELEVENLABS_API_KEY`:
   - **Key:** `ELEVENLABS_API_KEY`
   - **Value:** Your ElevenLabs API key
   - **Environment:** Production (and Preview if needed)
   - **Important:** Do NOT use `NEXT_PUBLIC_*` prefix - this keeps the key server-side only

#### Backend Deployment

The FastAPI backend must be deployed separately (e.g., Railway, Render, Fly.io, or your own server). Ensure:
- `ELEVENLABS_API_KEY` is set as an environment variable
- CORS is configured to allow requests from your Vercel frontend domain
- The backend URL matches `VITE_API_URL` in your frontend environment

### Troubleshooting

- **Token fetch fails:** Check that `ELEVENLABS_API_KEY` is set correctly in backend environment
- **Microphone permission denied:** Grant microphone access in browser settings
- **No transcripts appearing:** Check browser console for WebSocket errors; token may have expired (tokens expire after ~15 minutes)
- **Rate limit exceeded:** Wait 60 seconds before trying again, or increase `SCRIBE_RATE_LIMIT` in backend
- **Connection errors:** Verify backend is running and accessible from frontend

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
