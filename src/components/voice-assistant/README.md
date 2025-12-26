# Voice Assistant Structured Data Components

## Usage

The Voice Assistant can render structured data (characters, sessions, campaigns) using special markdown code blocks.

### Character Display

**Single Character by ID:**
```json:character
123
```

**Multiple Characters by IDs:**
```json:character
[123, 456, 789]
```

**Full Character Object:**
```json:character
{
  "id": 123,
  "name": "Gandalf",
  "race": "Wizard",
  "class_name": "Wizard",
  "level": 20,
  "max_hp": 100,
  "ac": 15,
  "alignment": "Lawful Good"
}
```

### Session Display

**Session by ID:**
```json:session
456
```

**Full Session Object:**
```json:session
{
  "id": 456,
  "name": "The Mines of Moria",
  "status": "active",
  "started_at": "2024-01-15T10:00:00Z"
}
```

### Campaign Display

**Campaign by ID:**
```json:campaign
789
```

**Full Campaign Object:**
```json:campaign
{
  "id": 789,
  "name": "The Lord of the Rings",
  "description": "An epic journey through Middle-earth"
}
```

## How It Works

1. The AI response includes markdown with special code blocks using `json:character`, `json:session`, or `json:campaign` as the language
2. `EnhancedResponse` detects these special code blocks
3. `StructuredDataRenderer` parses the JSON and:
   - If it's an ID (number), fetches the data from the API
   - If it's a full object, uses it directly
4. The appropriate component (CharacterCard, SessionCard, CampaignCard) is rendered

## Components

- `EnhancedResponse`: Wraps Streamdown with custom code block rendering
- `StructuredDataRenderer`: Handles data fetching and component selection
- `CharacterCard` / `CharacterGrid`: Display character information
- `SessionCard`: Display session information
- `CampaignCard`: Display campaign information

