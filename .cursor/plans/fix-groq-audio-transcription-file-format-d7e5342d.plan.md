<!-- d7e5342d-d091-4709-b1a6-17b494d65e8c 138ecbab-02c6-4813-94fc-8c865b3ef931 -->
# Migrate from groq_service to scribe_service

The codebase is switching from Groq API to ElevenLabs Scribe API. All references to `groq_service` need to be updated to use `scribe_service` instead.

## Changes Required

### 1. Update Python route import (`server/src/routes/audio.py`)

- **Line 4**: Change import from `groq_service` to `scribe_service`
- **Line 22**: The function call remains the same (`transcribe_audio`)
- **Line 26**: Update to handle new return format - `scribe_service` returns `{"text": ..., "raw": ...}` instead of `{"text": ..., "language": ..., "segments": ...}`
- Remove or adjust `language` field access since Scribe doesn't return it in the same format

### 2. Check TypeScript route (`server/src/routes/audio.ts`)

- **Line 4**: If this file is still in use, update import from `groqService` to `scribeService` (or remove if Python route is the only one used)

### 3. Verify return format compatibility

- `scribe_service.transcribe_audio()` returns: `{"text": str, "raw": dict}`
- Current route expects: `result['text']` and `result.get('language')`
- **Action**: Update route to only use `result['text']` or extract language from `result['raw']` if available

### 4. Environment variable check

- Ensure `ELEVENLABS_API_KEY` is set in environment (replaces `GROQ_API_KEY`)
- Verify dependencies: `numpy`, `soundfile`, `resampy`, `websockets` are installed

## Implementation Details

**File: `server/src/routes/audio.py`**

- Change: `from ..services.groq_service import transcribe_audio` → `from ..services.scribe_service import transcribe_audio`
- Update response to handle missing `language` field gracefully (return `None` or extract from `raw` if needed)

**File: `server/src/routes/audio.ts` (if still in use)**

- Update import path if TypeScript route is active
- Otherwise, this file can be ignored if Python route is the primary one