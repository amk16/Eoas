<!-- 3db81e14-a258-439f-a589-99dc3acf05c2 b69e00eb-f4e3-48c3-86e3-71d868b22b75 -->
# Transcript Correction and Turn End Detection Fix

## Overview

Add a transcript correction layer that uses combat context (current turn character, active characters, D&D terminology) to fix transcription errors before analysis. Also restrict turn end event detection to only detect actual turn endings, not mentions of whose turn it is.

## Phase 1: Fix Turn End Event Detection

**Goal**: Restrict turn end detection to only explicit turn endings, avoiding false positives from turn announcements.

**Files to Modify**:

- `server/src/services/event_types.py`

**Changes**:

- Update `TurnAdvanceEventType.get_prompt_instructions()` method (lines ~582-587)
- Remove ambiguous examples like "[character]'s turn", "turn passes to [character]", "next turn"
- Add explicit DO NOT DETECT examples: "it's your turn", "I'll start my turn", "your turn is next"
- Focus on explicit ending phrases: "I end my turn", "that ends my turn", "I'm done with my turn", "turn ends here", "my turn is over"

**Success Criteria**: Turn advance events only trigger on explicit turn endings, not on turn announcements.

---

## Phase 2: Add Combat Context Fetching

**Goal**: Extract combat state information (current turn, active characters) for use in transcript correction.

**Files to Modify**:

- `server/src/routes/analyze.py`

**Changes**:

- Add function `_get_combat_context()` to fetch combat state from database
- Query `combat_state` table for current turn character and combat status
- Query `initiative_order` and `characters` tables for active characters in turn order
- Create combat context structure:
  ```python
  {
      "current_turn_character_id": int | None,
      "current_turn_character_name": str | None,
      "active_characters": [
          {"id": int, "name": str, "turn_order": int}
      ],
      "is_combat_active": bool
  }
  ```

- Call this function in the `/analyze` endpoint before analysis
- Pass combat context to analysis service (initially just pass through, will be used in Phase 3)

**Success Criteria**: Combat context is successfully fetched and available for use in analysis pipeline.

---

## Phase 3: Create Transcript Correction Service

**Goal**: Build a service that uses combat context and D&D knowledge to correct transcription errors.

**Files to Create**:

- `server/src/services/transcript_correction_service.py`

**Functionality**:

- Create `correct_transcript()` async function that:
  - Takes parameters: transcript text, characters list, combat context
  - Uses Gemini API (same model as analysis) to analyze and correct transcript
  - Prompt strategy:
    - Character name disambiguation using active character names from combat context
    - Turn context awareness (knowing whose turn it is helps correct related references)
    - D&D spell name corrections (common D&D spells like Fireball, Cure Wounds, etc.)
    - Ability name corrections (common class abilities)
    - Game term corrections (AC, HP, saving throws, damage types, etc.)
    - Filter out off-topic conversational content unrelated to the game
  - Returns corrected transcript string
- Add error handling and logging
- Handle cases where combat is not active (no combat context available)

**Success Criteria**: Service can successfully correct transcripts using combat context and D&D knowledge, with improved accuracy for character names and game terms.

---

## Phase 4: Integrate Correction into Analysis Flow

**Goal**: Use corrected transcripts for event analysis while preserving original for debugging.

**Files to Modify**:

- `server/src/routes/analyze.py`
- `server/src/services/gemini_service.py`

**Changes**:

- In `analyze.py` `/analyze` endpoint:
  - Call `correct_transcript()` before `analyze_transcript()`
  - Log both original and corrected transcripts for debugging (use logger.debug for full text)
  - Pass corrected transcript and combat context to `analyze_transcript()`
- Update `gemini_service.py` `analyze_transcript()` function:
  - Add `combat_context` parameter (optional, for backwards compatibility)
  - Include combat context in prompt when available:
    - Current turn character information
    - Active character list with turn order
    - Use this context to help disambiguate character references in analysis

**Success Criteria**: Analysis uses corrected transcripts, resulting in improved event detection accuracy, with original transcripts logged for debugging.

---

## Technical Details

### Combat Context Structure

```python
{
    "current_turn_character_id": int | None,
    "current_turn_character_name": str | None,
    "active_characters": [
        {"id": int, "name": str, "turn_order": int}
    ],
    "is_combat_active": bool
}
```

### Turn End Detection Examples

**DO Detect:**

- "I end my turn"
- "That ends my turn"
- "I'm done with my turn"
- "Turn ends here"
- "My turn is over"

**DON'T Detect:**

- "It's your turn"
- "I'll start my turn"
- "Your turn is next"
- "Next up is [character]"
- "[Character]'s turn now"

### Database Queries for Combat Context

- `SELECT * FROM combat_state WHERE session_id = ?` - Get current turn and combat status
- `SELECT io.character_id, io.turn_order, c.name FROM initiative_order io JOIN characters c ON io.character_id = c.id WHERE io.session_id = ? ORDER BY io.turn_order` - Get active characters





