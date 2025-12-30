# Voice Assistant Creation Actions - Architecture Explanation

## Current Gemini Usage Patterns

### Pattern 1: Conversational Chat (`chat_with_gemini` in `ioun_service.py`)
**Purpose:** Generate natural language responses  
**Input:** Transcript + system prompt + conversation history  
**Output:** Natural language text response  
**Used in:** `/ioun/chat` endpoint  
**Example:** User says "Tell me about my characters" → Returns conversational explanation

### Pattern 2: Structured Data Extraction (`analyze_transcript` in `gemini_service.py`)
**Purpose:** Extract structured JSON data from transcripts  
**Input:** Transcript + context (characters, combat state)  
**Output:** JSON array of structured events  
**Used in:** `/analyze` endpoint (SessionView)  
**Example:** "Aragorn takes 10 damage" → Returns `[{"type": "damage", "character_id": 1, "amount": 10, ...}]`

### Pattern 3: Narrative Generation (`generate_narrative_from_transcript` in `ioun_service.py`)
**Purpose:** Generate TTS-optimized spoken response  
**Input:** Transcript + system prompt + conversation history  
**Output:** Natural language text optimized for speech  
**Used in:** `/ioun/chat` endpoint (parallel with Pattern 1)  
**Example:** Same input as Pattern 1, but returns concise version for voice

## Proposed: Creation Analysis Pattern

### Pattern 4: Creation Request Extraction (NEW - `creation_analysis_service.py`)
**Purpose:** Extract structured JSON for creation requests  
**Input:** Transcript + user context (existing campaigns/sessions/characters)  
**Output:** JSON array of creation requests  
**Used in:** `/ioun/chat` endpoint (parallel with Patterns 1 & 3)  
**Example:** "Create a campaign called Lost Mines" → Returns `[{"action_type": "create_campaign", "data": {"name": "Lost Mines", ...}}]`

## Integration Architecture

### Current `/ioun/chat` Flow (2 Parallel Tasks):

```
User Transcript
    ↓
/ioun/chat endpoint
    ↓
Get user context + build system prompt
    ↓
┌─────────────────────────────────────┐
│   Parallel Gemini Calls             │
├─────────────────────────────────────┤
│ Task 1: chat_with_gemini            │ → Conversational response
│ Task 2: generate_narrative          │ → TTS response
└─────────────────────────────────────┘
    ↓
Wait for both to complete
    ↓
Generate TTS audio from narrative
    ↓
Return: {response, narrative_response, audio_base64}
```

### Proposed `/ioun/chat` Flow (3 Parallel Tasks):

```
User Transcript
    ↓
/ioun/chat endpoint
    ↓
Get user context + build system prompt
    ↓
┌─────────────────────────────────────┐
│   Parallel Gemini Calls             │
├─────────────────────────────────────┤
│ Task 1: chat_with_gemini            │ → Conversational response
│ Task 2: generate_narrative          │ → TTS response  
│ Task 3: analyze_for_creations       │ → JSON array of creation requests
└─────────────────────────────────────┘
    ↓
Wait for all 3 to complete
    ↓
If Task 3 found creations:
    Execute creations via service functions
    ↓
Generate TTS audio from narrative (Task 2)
    ↓
Return: {response, narrative_response, audio_base64, created_items}
```

## Key Design Decisions

### Decision 1: Parallel vs Sequential

**Parallel (Recommended):**
- All 3 Gemini calls happen simultaneously
- Faster overall response (limited by slowest call, not sum)
- Creation analysis failures don't block chat response
- Matches existing pattern (narrative already runs in parallel)

**Sequential:**
- Chat response first, then analyze for creations
- Simpler flow but slower
- Could be separate endpoint for explicit control

### Decision 2: Execution Timing

**Option A: Auto-execute (Recommended)**
- Execute creations immediately when detected
- Return created items in response
- Frontend shows confirmation
- Matches event creation pattern (auto-execute)

**Option B: Request Confirmation**
- Return creation requests in response
- Wait for user confirmation
- Then execute
- Safer but adds interaction step

### Decision 3: Error Handling Strategy

**Creation Analysis Failures:**
- Non-blocking (chat response still returns)
- Log error, return empty created_items array
- User still gets conversational response

**Creation Execution Failures:**
- Individual creation failures don't block others
- Return partial success with error details
- Include in created_items with status field

**Missing Required Fields:**
- Skip creation, log warning
- Optionally: include in response asking for clarification
- Don't block other creations

## Code Structure Comparison

### Event Analysis (Existing Pattern):

```python
# gemini_service.py
async def analyze_transcript(transcript, characters, combat_context):
    # Build prompt for event extraction
    prompt = "Extract events from transcript..."
    # Call Gemini
    response = model.generate_content(prompt)
    # Parse JSON
    events = json.loads(response.text)
    # Validate using event types
    validated_events = [validate_and_filter(e) for e in events]
    return validated_events

# routes/analyze.py
events = await analyze_transcript(transcript, characters, combat_context)
for event in events:
    event_type = get_event_type_by_name(event['type'])
    await event_type.handle_event(event, session_id, user_id, db, session_ref)
```

### Creation Analysis (Proposed Pattern):

```python
# creation_analysis_service.py
async def analyze_for_creations(transcript, user_context):
    # Build prompt for creation extraction
    prompt = "Extract creation requests from transcript..."
    # Call Gemini  
    response = model.generate_content(prompt)
    # Parse JSON
    creation_requests = json.loads(response.text)
    # Validate required fields
    validated_requests = [validate_creation_request(r) for r in creation_requests]
    return validated_requests

# routes/ioun.py (in parallel with chat tasks)
creation_requests = await analyze_for_creations(transcript, user_context)
created_items = []
for req in creation_requests:
    if req['action_type'] == 'create_campaign':
        created = await create_campaign_service(req['data'], user_id)
        created_items.append(created)
    # ... handle other types
```

## Summary

- **Creation analysis follows the same pattern as event analysis**: Structured JSON extraction via separate Gemini call
- **Integration method**: Add as 3rd parallel task in `/ioun/chat` (matches existing narrative pattern)
- **Execution**: Auto-execute creations immediately (matches event creation pattern)
- **Error handling**: Non-blocking, partial success support
- **Response**: Add `created_items` array to ChatResponse model

