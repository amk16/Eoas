# conversational_ai_service.py
import os
import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Callable, Awaitable
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY_CONVAI")

# Model configuration
CONVERSATIONAL_AI_MODEL = "eleven_multilingual_v2"


async def create_conversation_token(
    user_id: int,
    system_prompt: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Create a conversational AI agent using ElevenLabs SDK.
    
    Args:
        user_id: User ID for context
        system_prompt: Optional custom system prompt
        tools: Optional list of tools/functions the assistant can call
    
    Returns:
        Dictionary containing agent ID and conversation configuration
    """
    if not ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not configured")
    
    logger.info(f"Creating conversational AI agent for user {user_id}")
    
    try:
        # Build conversation configuration
        conversation_config = {
            "agent": {
                "prompt": {
                    "prompt": system_prompt or "You are a helpful D&D assistant.",
                }
            }
        }
        
        # Add tools if provided
        if tools:
            conversation_config["agent"]["tools"] = tools
        
        # Run synchronous SDK call in thread pool to avoid blocking
        def create_agent_sync():
            # Initialize ElevenLabs client
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            
            # Create the conversational AI agent
            response = client.conversational_ai.agents.create(
                name=f"D&D Assistant - User {user_id}",
                conversation_config=conversation_config
            )
            return response
        
        # Execute in thread pool
        loop = asyncio.get_event_loop()
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor() as executor:
            agent_response = await loop.run_in_executor(executor, create_agent_sync)
        
        agent_id = getattr(agent_response, 'agent_id', None) or getattr(agent_response, 'id', None)
        logger.info(f"Successfully created conversational AI agent: {agent_id}")
        
        # Get a signed URL for WebSocket connection using the agent
        def get_signed_url_sync():
            client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
            # Get signed URL for WebSocket connection
            # This should return a WebSocket URL we can use to connect
            signed_url_response = client.conversational_ai.conversations.get_signed_url(
                agent_id=agent_id
            )
            return signed_url_response
        
        # Get WebSocket signed URL
        try:
            with ThreadPoolExecutor() as executor:
                signed_url_response = await loop.run_in_executor(executor, get_signed_url_sync)
            
            # Extract WebSocket URL from response
            # The response is a ConversationSignedUrlResponseModel
            websocket_url = None
            conversation_id = None
            
            # Try different ways to extract the signed URL
            if hasattr(signed_url_response, 'signed_url'):
                websocket_url = signed_url_response.signed_url
            if hasattr(signed_url_response, 'conversation_id'):
                conversation_id = signed_url_response.conversation_id
            
            # If not found, try model_dump or dict methods
            if not websocket_url:
                if hasattr(signed_url_response, 'model_dump'):
                    data = signed_url_response.model_dump()
                    websocket_url = data.get('signed_url') or data.get('url')
                    conversation_id = conversation_id or data.get('conversation_id')
                elif hasattr(signed_url_response, 'dict'):
                    data = signed_url_response.dict()
                    websocket_url = data.get('signed_url') or data.get('url')
                    conversation_id = conversation_id or data.get('conversation_id')
                elif isinstance(signed_url_response, dict):
                    websocket_url = signed_url_response.get('signed_url') or signed_url_response.get('url')
                    conversation_id = conversation_id or signed_url_response.get('conversation_id')
            
            logger.info(f"Got signed URL for agent {agent_id}: {websocket_url or 'N/A'}")
            
            result = {
                "agent_id": agent_id,
                "conversation_config": conversation_config,
            }
            
            if conversation_id:
                result["conversation_id"] = conversation_id
            
            # SDK expects 'signedUrl' for WebSocket connections
            if websocket_url:
                result["signedUrl"] = websocket_url
                # Keep websocket_url for backward compatibility
                result["websocket_url"] = websocket_url
            else:
                # Fallback: construct WebSocket URL using agent_id
                fallback_url = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={agent_id}"
                if conversation_id:
                    fallback_url += f"&conversation_id={conversation_id}"
                result["signedUrl"] = fallback_url
                result["websocket_url"] = fallback_url
            
            return result
        except Exception as conv_error:
            logger.warning(f"Failed to get signed URL, using agent only: {conv_error}")
            import traceback
            logger.warning(traceback.format_exc())
            # Fallback: return agent info and construct WebSocket URL
            fallback_url = f"wss://api.elevenlabs.io/v1/convai/conversation?agent_id={agent_id}"
            return {
                "agent_id": agent_id,
                "signedUrl": fallback_url,
                "websocket_url": fallback_url,  # Keep for backward compatibility
                "conversation_config": conversation_config,
            }
        
    except Exception as e:
        logger.error(f"Error creating conversational AI agent: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"Failed to create conversational AI agent: {str(e)}")


def build_system_prompt(
    user_context: Dict[str, Any],
    dnd_rules: Optional[str] = None
) -> str:
    """
    Build a comprehensive system prompt for the voice assistant.
    
    Args:
        user_context: Dictionary containing user's campaigns, sessions, characters
        dnd_rules: Optional D&D rules knowledge base text
    
    Returns:
        Formatted system prompt string
    """
    prompt_parts = [
        "You are a helpful D&D (Dungeons & Dragons) voice assistant. You can discuss:",
        "- The user's campaigns, sessions, and characters",
        "- General D&D rules and mechanics",
        "- Game strategies and character builds",
        "",
        "IMPORTANT: When the user asks you to modify data (update HP, create sessions, etc.),",
        "you must request confirmation before proceeding. Use the appropriate tool/function",
        "to propose the action, and wait for user confirmation before executing.",
        "",
        "=== STRUCTURED DATA FORMATTING ===",
        "When displaying character, session, or campaign information, format it as JSON in markdown code blocks.",
        "Use the following format:",
        "",
        "For a single character:",
        "```json:character",
        "{",
        '  "id": 1,',
        '  "name": "Character Name",',
        '  "race": "Human",',
        '  "class_name": "Fighter",',
        '  "level": 5,',
        '  "max_hp": 50,',
        '  "ac": 18,',
        '  "alignment": "Lawful Good",',
        '  "background": "Optional background text",',
        '  "notes": "Optional notes"',
        "}",
        "```",
        "",
        "For multiple characters:",
        "```json:characters",
        "[",
        "  { \"id\": 1, \"name\": \"Character 1\", ... },",
        "  { \"id\": 2, \"name\": \"Character 2\", ... }",
        "]",
        "```",
        "",
        "For a session:",
        "```json:session",
        "{",
        '  "id": 1,',
        '  "name": "Session Name",',
        '  "status": "active",',
        '  "started_at": "2024-01-15T10:00:00Z",',
        '  "ended_at": null,',
        '  "campaign_id": 1',
        "}",
        "```",
        "",
        "For multiple sessions:",
        "```json:sessions",
        "[",
        "  { \"id\": 1, \"name\": \"Session 1\", ... },",
        "  { \"id\": 2, \"name\": \"Session 2\", ... }",
        "]",
        "```",
        "",
        "For a campaign:",
        "```json:campaign",
        "{",
        '  "id": 1,',
        '  "name": "Campaign Name",',
        '  "description": "Campaign description",',
        '  "created_at": "2024-01-01T00:00:00Z"',
        "}",
        "```",
        "",
        "Always use the exact code block format with the type prefix (json:character, json:characters, json:session, json:sessions, json:campaign).",
        "Include all available fields from the data. You can provide context before or after the code block.",
        "",
        "=== MARKDOWN FORMATTING RULES ===",
        "You have access to extensive markdown formatting capabilities. Use these formats to create rich, well-structured responses.",
        "",
        "## Lists",
        "Use lists to organize information clearly:",
        "",
        "**Unordered Lists:**",
        "- Use for items without specific order",
        "- Can be nested for sub-items",
        "  - Like this nested item",
        "  - Another nested item",
        "",
        "**Ordered Lists:**",
        "1. Use for sequential information",
        "2. Great for step-by-step instructions",
        "3. Can also be nested",
        "   1. Nested numbered items",
        "   2. Work the same way",
        "",
        "**Definition Lists (for stats/attributes):**",
        "Use a combination of bold text and regular text:",
        "**HP:** 50/50",
        "**AC:** 18",
        "**Level:** 5",
        "",
        "## Tables",
        "Use tables to display structured data, comparisons, or multiple related items:",
        "",
        "Example - Character Stats Table:",
        "| Character | HP | AC | Level | Class |",
        "|-----------|----|----|-------|-------|",
        "| Aragorn   | 50 | 18 | 5     | Fighter |",
        "| Gandalf   | 40 | 15 | 7     | Wizard |",
        "",
        "Example - Session Summary Table:",
        "| Session | Status | Started | Characters |",
        "|---------|--------|---------|------------|",
        "| Session 1 | Active | 2024-01-15 | 3 |",
        "| Session 2 | Ended | 2024-01-10 | 4 |",
        "",
        "Always include a header row and align columns properly. Use tables when comparing multiple items or showing structured data.",
        "",
        "## Special Detail Views",
        "For in-depth explanations of a single character, session, or campaign, use special markdown code blocks.",
        "CRITICAL: You MUST use the exact format shown below with the language identifier in the code fence.",
        "",
        "**Character Detail View:**",
        "When providing a comprehensive explanation of a single character, use this EXACT format:",
        "```markdown:character-detail",
        "# Character Name",
        "## Stats",
        "- **HP:** 50/50",
        "- **AC:** 18",
        "- **Level:** 5",
        "- **Race:** Human",
        "- **Class:** Fighter",
        "## Background",
        "Detailed background story and character development...",
        "## Recent Events",
        "What has happened to this character recently...",
        "```",
        "",
        "**Session Detail View:**",
        "When providing a comprehensive explanation of a single session, use this EXACT format:",
        "```markdown:session-detail",
        "# Session Name",
        "## Overview",
        "Summary of the session...",
        "## Key Events",
        "1. Event one",
        "2. Event two",
        "## Characters Involved",
        "- Character 1",
        "- Character 2",
        "```",
        "",
        "**Campaign Detail View:**",
        "When providing a comprehensive explanation of a single campaign, use this EXACT format:",
        "```markdown:campaign-detail",
        "# Campaign Name",
        "## Description",
        "Campaign overview and setting...",
        "## Sessions",
        "List of sessions in this campaign...",
        "## Characters",
        "Characters involved in this campaign...",
        "```",
        "",
        "IMPORTANT FORMATTING RULES:",
        "- The code fence MUST start with three backticks followed immediately by the language identifier",
        "- For character details: use ```markdown:character-detail (no space after the colon)",
        "- For session details: use ```markdown:session-detail (no space after the colon)",
        "- For campaign details: use ```markdown:campaign-detail (no space after the colon)",
        "- The language identifier is case-sensitive and must match exactly",
        "- Do NOT use spaces in the language identifier",
        "- The closing fence is just three backticks: ```",
        "",
        "These detail views allow for rich formatting with headers, lists, and narrative text. Use them when the user asks for detailed information about a single item.",
        "",
        "## Change Logs and Operation Summaries",
        "When displaying information about edits, additions, or other operations, use special markdown formats:",
        "",
        "**Change Log Format:**",
        "Use this when showing what was changed (before/after comparisons):",
        "```markdown:change-log",
        "**Updated Character: Aragorn**",
        "- **HP:** 45 → 50 (healed 5 HP)",
        "- **Level:** 4 → 5 (leveled up)",
        "- **AC:** 17 → 18 (armor upgrade)",
        "```",
        "",
        "**Operation Summary Format:**",
        "Use this when summarizing create/update operations:",
        "```markdown:operation-summary",
        "**Created Session: \"The Dragon's Lair\"**",
        "- **Campaign:** Lost Mines of Phandelver",
        "- **Characters:** Aragorn, Gandalf, Legolas",
        "- **Status:** Active",
        "- **Started:** 2024-01-15",
        "```",
        "",
        "Or for character creation:",
        "```markdown:operation-summary",
        "**Created Character: Legolas**",
        "- **Race:** Elf",
        "- **Class:** Ranger",
        "- **Level:** 3",
        "- **HP:** 30",
        "- **AC:** 16",
        "```",
        "",
        "**Confirmation Messages:**",
        "When confirming an operation, format the confirmation clearly:",
        "```markdown:operation-summary",
        "**Operation Confirmed**",
        "Successfully updated Aragorn:",
        "- HP changed from 45 to 50",
        "- Reason: Healed by potion",
        "```",
        "",
        "## General Markdown Guidelines",
        "- Use **bold** for emphasis on important terms or labels",
        "- Use *italic* for narrative text or descriptions",
        "- Use headers (# ## ###) to organize sections",
        "- Combine formats: Use tables for comparisons, lists for items, detail views for deep dives",
        "- Always format data clearly - don't just list raw information",
        "- When in doubt, use the most structured format (tables for data, lists for items, detail views for explanations)",
        "",
    ]
    
    # Add user context
    if user_context:
        prompt_parts.append("=== USER'S DATA ===")
        
        if user_context.get("campaigns"):
            prompt_parts.append(f"\nCampaigns ({len(user_context['campaigns'])}):")
            for campaign in user_context["campaigns"][:10]:  # Limit to first 10
                desc = f" - {campaign.get('name', 'Unnamed')}"
                if campaign.get('description'):
                    desc += f": {campaign['description'][:100]}"
                prompt_parts.append(desc)
        
        if user_context.get("sessions"):
            prompt_parts.append(f"\nSessions ({len(user_context['sessions'])}):")
            for session in user_context["sessions"][:10]:
                status = session.get('status', 'unknown')
                desc = f" - {session.get('name', 'Unnamed')} ({status})"
                if session.get('started_at'):
                    desc += f" - Started: {session['started_at']}"
                prompt_parts.append(desc)
        
        if user_context.get("characters"):
            prompt_parts.append(f"\nCharacters ({len(user_context['characters'])}):")
            for char in user_context["characters"][:20]:  # Show more characters
                desc = f" - {char.get('name', 'Unnamed')}"
                if char.get('class_name'):
                    desc += f" ({char['class_name']}"
                    if char.get('level'):
                        desc += f" {char['level']}"
                    desc += ")"
                if char.get('current_hp') is not None and char.get('max_hp'):
                    desc += f" - HP: {char['current_hp']}/{char['max_hp']}"
                prompt_parts.append(desc)
        
        prompt_parts.append("")
    
    # Add D&D rules knowledge
    if dnd_rules:
        prompt_parts.append("=== D&D RULES KNOWLEDGE ===")
        prompt_parts.append(dnd_rules[:2000])  # Limit rules text to avoid token limits
        prompt_parts.append("")
    
    prompt_parts.append(
        "Remember: Always be helpful, accurate, and request confirmation before modifying any data."
    )
    
    return "\n".join(prompt_parts)


def build_tools_config() -> List[Dict[str, Any]]:
    """
    Build the tools/functions configuration for the assistant.
    These tools allow the assistant to propose actions that require confirmation.
    
    Returns:
        List of tool definitions
    """
    tools = [
        {
            "type": "function",
            "function": {
                "name": "update_character_hp",
                "description": "Propose updating a character's HP (hit points). Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "integer",
                            "description": "The ID of the character to update"
                        },
                        "character_name": {
                            "type": "string",
                            "description": "The name of the character (for confirmation)"
                        },
                        "new_hp": {
                            "type": "integer",
                            "description": "The new HP value"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the HP change (e.g., 'took 5 damage', 'healed 10 HP')"
                        }
                    },
                    "required": ["character_id", "character_name", "new_hp", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_session",
                "description": "Propose creating a new D&D session. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of the session"
                        },
                        "campaign_id": {
                            "type": "integer",
                            "description": "Optional campaign ID to associate with the session",
                            "nullable": True
                        },
                        "character_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of character IDs to include in the session"
                        }
                    },
                    "required": ["name", "character_ids"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_character_stat",
                "description": "Propose updating a character's stat (AC, level, etc.). Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "integer",
                            "description": "The ID of the character to update"
                        },
                        "character_name": {
                            "type": "string",
                            "description": "The name of the character"
                        },
                        "stat_name": {
                            "type": "string",
                            "enum": ["ac", "level", "max_hp", "temp_hp", "initiative_bonus"],
                            "description": "The stat to update"
                        },
                        "new_value": {
                            "type": "integer",
                            "description": "The new value for the stat"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the change"
                        }
                    },
                    "required": ["character_id", "character_name", "stat_name", "new_value", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_character",
                "description": "Propose creating a new character. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Character name"
                        },
                        "max_hp": {
                            "type": "integer",
                            "description": "Maximum hit points"
                        },
                        "class_name": {
                            "type": "string",
                            "description": "Character class (e.g., 'Fighter', 'Wizard')",
                            "nullable": True
                        },
                        "race": {
                            "type": "string",
                            "description": "Character race (e.g., 'Human', 'Elf')",
                            "nullable": True
                        },
                        "level": {
                            "type": "integer",
                            "description": "Character level",
                            "nullable": True
                        },
                        "campaign_id": {
                            "type": "integer",
                            "description": "Optional campaign ID",
                            "nullable": True
                        }
                    },
                    "required": ["name", "max_hp"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_character",
                "description": "Propose updating a character's fields (name, race, class, level, AC, alignment, background, notes, etc.). Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "integer",
                            "description": "The ID of the character to update"
                        },
                        "character_name": {
                            "type": "string",
                            "description": "The name of the character (for confirmation)"
                        },
                        "name": {
                            "type": "string",
                            "description": "New character name",
                            "nullable": True
                        },
                        "max_hp": {
                            "type": "integer",
                            "description": "New maximum hit points",
                            "nullable": True
                        },
                        "race": {
                            "type": "string",
                            "description": "Character race (e.g., 'Human', 'Elf')",
                            "nullable": True
                        },
                        "class_name": {
                            "type": "string",
                            "description": "Character class (e.g., 'Fighter', 'Wizard')",
                            "nullable": True
                        },
                        "level": {
                            "type": "integer",
                            "description": "Character level",
                            "nullable": True
                        },
                        "ac": {
                            "type": "integer",
                            "description": "Armor Class",
                            "nullable": True
                        },
                        "alignment": {
                            "type": "string",
                            "description": "Character alignment (e.g., 'Lawful Good', 'Chaotic Neutral')",
                            "nullable": True
                        },
                        "background": {
                            "type": "string",
                            "description": "Character background story",
                            "nullable": True
                        },
                        "notes": {
                            "type": "string",
                            "description": "Character notes",
                            "nullable": True
                        },
                        "campaign_id": {
                            "type": "integer",
                            "description": "Campaign ID to associate with character",
                            "nullable": True
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the update"
                        }
                    },
                    "required": ["character_id", "character_name", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_character_notes",
                "description": "Propose appending or updating a character's notes field. Useful for adding session notes or character development. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "character_id": {
                            "type": "integer",
                            "description": "The ID of the character to update"
                        },
                        "character_name": {
                            "type": "string",
                            "description": "The name of the character (for confirmation)"
                        },
                        "notes": {
                            "type": "string",
                            "description": "Notes to add or replace. If append_mode is true, this will be appended to existing notes."
                        },
                        "append_mode": {
                            "type": "boolean",
                            "description": "If true, append to existing notes. If false, replace notes entirely.",
                            "default": True
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for updating notes"
                        }
                    },
                    "required": ["character_id", "character_name", "notes", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_session",
                "description": "Propose updating a session's fields (name, status, ended_at). Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "integer",
                            "description": "The ID of the session to update"
                        },
                        "session_name": {
                            "type": "string",
                            "description": "The name of the session (for confirmation)"
                        },
                        "name": {
                            "type": "string",
                            "description": "New session name",
                            "nullable": True
                        },
                        "status": {
                            "type": "string",
                            "enum": ["active", "ended"],
                            "description": "Session status",
                            "nullable": True
                        },
                        "ended_at": {
                            "type": "string",
                            "description": "End date/time in ISO format (e.g., '2024-01-15T10:00:00Z'). Use null to clear.",
                            "nullable": True
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the update"
                        }
                    },
                    "required": ["session_id", "session_name", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_characters_to_session",
                "description": "Propose adding characters to an existing session. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "integer",
                            "description": "The ID of the session"
                        },
                        "session_name": {
                            "type": "string",
                            "description": "The name of the session (for confirmation)"
                        },
                        "character_ids": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of character IDs to add to the session"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for adding characters"
                        }
                    },
                    "required": ["session_id", "session_name", "character_ids", "reason"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_campaign",
                "description": "Propose creating a new campaign. Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Campaign name"
                        },
                        "description": {
                            "type": "string",
                            "description": "Campaign description",
                            "nullable": True
                        }
                    },
                    "required": ["name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_campaign",
                "description": "Propose updating a campaign's fields (name, description). Requires user confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "campaign_id": {
                            "type": "integer",
                            "description": "The ID of the campaign to update"
                        },
                        "campaign_name": {
                            "type": "string",
                            "description": "The name of the campaign (for confirmation)"
                        },
                        "name": {
                            "type": "string",
                            "description": "New campaign name",
                            "nullable": True
                        },
                        "description": {
                            "type": "string",
                            "description": "New campaign description",
                            "nullable": True
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for the update"
                        }
                    },
                    "required": ["campaign_id", "campaign_name", "reason"]
                }
            }
        }
    ]
    
    return tools


async def handle_tool_call(
    tool_name: str,
    parameters: Dict[str, Any],
    user_id: int
) -> Dict[str, Any]:
    """
    Handle a tool call from the assistant.
    This creates a pending action that requires user confirmation.
    
    Args:
        tool_name: Name of the tool/function called
        parameters: Parameters passed to the tool
        user_id: User ID for authorization
    
    Returns:
        Dictionary with action details for confirmation
    """
    logger.info(f"Tool call received: {tool_name} with parameters: {parameters}")
    
    # Create a pending action object
    action = {
        "tool_name": tool_name,
        "parameters": parameters,
        "user_id": user_id,
        "status": "pending_confirmation",
        "created_at": asyncio.get_event_loop().time()
    }
    
    # Format a user-friendly description with markdown formatting
    description_parts = []
    
    # Handle different tool types
    if tool_name == "update_character_hp":
        char_name = parameters.get("character_name", "character")
        new_hp = parameters.get("new_hp")
        reason = parameters.get("reason", "")
        description_parts.append(f"Update **{char_name}**'s HP to **{new_hp}**")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "update_character_stat":
        char_name = parameters.get("character_name", "character")
        stat_name = parameters.get("stat_name", "").upper()
        new_value = parameters.get("new_value")
        reason = parameters.get("reason", "")
        description_parts.append(f"Update **{char_name}**'s {stat_name} to **{new_value}**")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "update_character":
        char_name = parameters.get("character_name", "character")
        updates = []
        if parameters.get("name"):
            updates.append(f"name to '{parameters['name']}'")
        if parameters.get("max_hp") is not None:
            updates.append(f"max HP to {parameters['max_hp']}")
        if parameters.get("race"):
            updates.append(f"race to {parameters['race']}")
        if parameters.get("class_name"):
            updates.append(f"class to {parameters['class_name']}")
        if parameters.get("level") is not None:
            updates.append(f"level to {parameters['level']}")
        if parameters.get("ac") is not None:
            updates.append(f"AC to {parameters['ac']}")
        if parameters.get("alignment"):
            updates.append(f"alignment to {parameters['alignment']}")
        if parameters.get("background"):
            updates.append("background")
        if parameters.get("notes"):
            updates.append("notes")
        if parameters.get("campaign_id") is not None:
            updates.append("campaign association")
        
        if updates:
            description_parts.append(f"Update **{char_name}**: {', '.join(updates)}")
        else:
            description_parts.append(f"Update **{char_name}**")
        
        reason = parameters.get("reason", "")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "update_character_notes":
        char_name = parameters.get("character_name", "character")
        append_mode = parameters.get("append_mode", True)
        mode_text = "append to" if append_mode else "update"
        reason = parameters.get("reason", "")
        description_parts.append(f"{mode_text.capitalize()} **{char_name}**'s notes")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "create_character":
        char_name = parameters.get("name", "character")
        class_name = parameters.get("class_name")
        level = parameters.get("level")
        description_parts.append(f"Create character **{char_name}**")
        if class_name:
            description_parts.append(f"({class_name}")
            if level:
                description_parts.append(f" Level {level}")
            description_parts.append(")")
    
    elif tool_name == "create_session":
        session_name = parameters.get("name", "session")
        char_count = len(parameters.get("character_ids", []))
        description_parts.append(f"Create session **{session_name}**")
        if char_count > 0:
            description_parts.append(f"with {char_count} character(s)")
    
    elif tool_name == "update_session":
        session_name = parameters.get("session_name", "session")
        updates = []
        if parameters.get("name"):
            updates.append(f"name to '{parameters['name']}'")
        if parameters.get("status"):
            updates.append(f"status to {parameters['status']}")
        if parameters.get("ended_at") is not None:
            updates.append("end date")
        
        if updates:
            description_parts.append(f"Update session **{session_name}**: {', '.join(updates)}")
        else:
            description_parts.append(f"Update session **{session_name}**")
        
        reason = parameters.get("reason", "")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "add_characters_to_session":
        session_name = parameters.get("session_name", "session")
        char_count = len(parameters.get("character_ids", []))
        reason = parameters.get("reason", "")
        description_parts.append(f"Add {char_count} character(s) to session **{session_name}**")
        if reason:
            description_parts.append(f"({reason})")
    
    elif tool_name == "create_campaign":
        campaign_name = parameters.get("name", "campaign")
        description_parts.append(f"Create campaign **{campaign_name}**")
    
    elif tool_name == "update_campaign":
        campaign_name = parameters.get("campaign_name", "campaign")
        updates = []
        if parameters.get("name"):
            updates.append(f"name to '{parameters['name']}'")
        if parameters.get("description") is not None:
            updates.append("description")
        
        if updates:
            description_parts.append(f"Update campaign **{campaign_name}**: {', '.join(updates)}")
        else:
            description_parts.append(f"Update campaign **{campaign_name}**")
        
        reason = parameters.get("reason", "")
        if reason:
            description_parts.append(f"({reason})")
    
    else:
        # Fallback for unknown tools
        description_parts.append(f"Assistant wants to {tool_name.replace('_', ' ')}")
        if parameters.get("name"):
            description_parts.append(f"named '{parameters['name']}'")
        if parameters.get("reason"):
            description_parts.append(f"({parameters['reason']})")
    
    action["description"] = " ".join(description_parts)
    
    return action

