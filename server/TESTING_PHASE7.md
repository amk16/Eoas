# Testing Guide - Phase 7: Analyze Transcript

This guide explains how to test the `/api/analyze` endpoint that uses Google Gemini to extract damage/healing events from D&D transcripts.

## Prerequisites

1. **Install Python dependencies:**
   ```bash
   cd server
   pip install -r requirements.txt
   ```
   This will install `google-generativeai` and other required packages.

2. **Set up Google Gemini API Key:**
   - Get your API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Add it to your `server/.env` file:
     ```
     GEMINI_API_KEY=your-api-key-here
     ```

3. **Start the server:**
   ```bash
   cd server
   uvicorn src.main:app --reload --port 3001
   ```
   Or use:
   ```bash
   npm run dev
   ```

## Testing Methods

### Method 1: Automated Python Test Script (Recommended)

The easiest way to test is using the provided test script:

```bash
cd server
python test_phase7.py
```

This script will:
1. Register/login a test user
2. Create a test character
3. Create a test session
4. Add the character to the session
5. Analyze a sample D&D transcript
6. Display the extracted events

**Expected output:**
```
============================================================
Phase 7 Test Suite - Analyze Transcript Endpoint
============================================================

🔐 Step 1: Authenticating...
✅ Registered and logged in as test@example.com

👤 Step 2: Creating character 'Gandalf'...
✅ Created character: Gandalf (ID: 1, Max HP: 100)

🎲 Step 3: Creating session 'Test Session'...
✅ Created session: Test Session (ID: 1)

➕ Step 4: Adding character to session...
✅ Added character to session

🔍 Step 5: Analyzing transcript...
   Transcript: The goblin swings its rusty sword at Gandalf, dealing 15 points of damage...
✅ Analysis successful!
   Found 3 event(s)

   Events:
   1. DAMAGE: 15 to Gandalf
      Character ID: 1
      Segment: The goblin swings its rusty sword at Gandalf, dealing 15 points of damage...
   2. HEALING: 20 to Gandalf
      Character ID: 1
      Segment: The cleric quickly casts a healing spell, restoring 20 hit points...
   3. DAMAGE: 8 to Gandalf
      Character ID: 1
      Segment: Another goblin attacks and hits Gandalf for 8 damage...
```

### Method 2: Using cURL

First, you need to get an authentication token:

```bash
# 1. Register/Login to get a token
TOKEN=$(curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}' \
  | jq -r '.token')

# If registration is needed:
# TOKEN=$(curl -s -X POST http://localhost:3001/api/auth/register \
#   -H "Content-Type: application/json" \
#   -d '{"email":"test@example.com","password":"testpass123"}' \
#   | jq -r '.token')

# 2. Create a character
CHARACTER_ID=$(curl -s -X POST http://localhost:3001/api/characters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Gandalf","max_hp":100}' \
  | jq -r '.id')

# 3. Create a session
SESSION_ID=$(curl -s -X POST http://localhost:3001/api/sessions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"Test Session"}' \
  | jq -r '.id')

# 4. Add character to session
curl -X POST http://localhost:3001/api/sessions/$SESSION_ID/characters \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"character_ids\":[$CHARACTER_ID]}"

# 5. Analyze a transcript
curl -X POST http://localhost:3001/api/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"transcript\": \"The goblin swings its rusty sword at Gandalf, dealing 15 points of damage. The cleric quickly casts a healing spell, restoring 20 hit points to Gandalf.\",
    \"session_id\": $SESSION_ID
  }" | jq
```

### Method 3: Using Postman or Insomnia

1. **Set up authentication:**
   - Create a POST request to `http://localhost:3001/api/auth/login`
   - Body (JSON):
     ```json
     {
       "email": "test@example.com",
       "password": "testpass123"
     }
     ```
   - Copy the `token` from the response

2. **Create a character:**
   - POST `http://localhost:3001/api/characters`
   - Headers: `Authorization: Bearer <your-token>`
   - Body:
     ```json
     {
       "name": "Gandalf",
       "max_hp": 100
     }
     ```
   - Note the `id` from the response

3. **Create a session:**
   - POST `http://localhost:3001/api/sessions`
   - Headers: `Authorization: Bearer <your-token>`
   - Body:
     ```json
     {
       "name": "Test Session"
     }
     ```
   - Note the `id` from the response

4. **Add character to session:**
   - POST `http://localhost:3001/api/sessions/<session-id>/characters`
   - Headers: `Authorization: Bearer <your-token>`
   - Body:
     ```json
     {
       "character_ids": [<character-id>]
     }
     ```

5. **Analyze transcript:**
   - POST `http://localhost:3001/api/analyze`
   - Headers: `Authorization: Bearer <your-token>`
   - Body:
     ```json
     {
       "transcript": "The goblin swings its rusty sword at Gandalf, dealing 15 points of damage. The cleric quickly casts a healing spell, restoring 20 hit points to Gandalf.",
       "session_id": <session-id>
     }
     ```

**Expected Response:**
```json
{
  "events": [
    {
      "character_id": 1,
      "character_name": "Gandalf",
      "amount": 15,
      "type": "damage",
      "transcript_segment": "The goblin swings its rusty sword at Gandalf, dealing 15 points of damage."
    },
    {
      "character_id": 1,
      "character_name": "Gandalf",
      "amount": 20,
      "type": "healing",
      "transcript_segment": "The cleric quickly casts a healing spell, restoring 20 hit points to Gandalf."
    }
  ],
  "count": 2
}
```

## Sample Transcripts for Testing

### Simple Damage Event
```
The orc attacks Gandalf and deals 12 damage.
```

### Simple Healing Event
```
The cleric heals Gandalf for 25 hit points.
```

### Multiple Events
```
The goblin swings its rusty sword at Gandalf, dealing 15 points of damage. 
Gandalf staggers back, his robes torn. The cleric quickly casts a healing spell, 
restoring 20 hit points to Gandalf. The wizard then casts a fireball, 
dealing 30 damage to the goblin. Another goblin attacks and hits Gandalf for 8 damage.
```

### Complex Scenario
```
The dragon breathes fire, and Gandalf takes 45 fire damage. The paladin rushes 
forward and heals Gandalf with Lay on Hands, restoring 30 hit points. The rogue 
stabs the dragon for 18 damage. The dragon retaliates, hitting Gandalf for 22 damage.
```

## Common Issues

### Error: "GEMINI_API_KEY is not configured"
- **Solution:** Make sure you've added `GEMINI_API_KEY=your-key` to your `server/.env` file
- Restart the server after adding the key

### Error: "No characters found in session"
- **Solution:** Make sure you've added at least one character to the session using the `/api/sessions/:id/characters` endpoint

### Error: "Session not found"
- **Solution:** Verify the session_id exists and belongs to your user account

### Error: "Failed to parse analysis response"
- **Solution:** This can happen if Gemini returns malformed JSON. Try a simpler transcript or check your API key is valid

### Error: "Analysis failed: ..."
- **Solution:** 
  - Check your Gemini API key is valid and has quota remaining
  - Verify the transcript contains recognizable character names and damage/healing amounts
  - Check server logs for detailed error messages

### No events found in response
- **Possible reasons:**
  - The transcript doesn't contain clear damage/healing events
  - Character names in the transcript don't match characters in the session
  - The amounts aren't clearly stated as numbers
- **Solution:** Try a more explicit transcript like "Gandalf takes 15 damage" or "Gandalf is healed for 20 hit points"

## Testing Checklist

- [ ] Server starts without errors
- [ ] `GEMINI_API_KEY` is set in `.env`
- [ ] Can authenticate and get a token
- [ ] Can create a character
- [ ] Can create a session
- [ ] Can add character to session
- [ ] Can analyze a simple transcript with damage event
- [ ] Can analyze a simple transcript with healing event
- [ ] Can analyze a transcript with multiple events
- [ ] Response includes correct character_id
- [ ] Response includes correct amount
- [ ] Response includes correct type (damage/healing)
- [ ] Response includes transcript_segment

## Next Steps

Once Phase 7 is working, you can proceed to:
- **Phase 8**: Record damage/healing events to the database
- Integrate the analyze endpoint with the frontend LiveScribe component

