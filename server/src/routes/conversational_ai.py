from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
import logging
import time
from ..middleware.auth import authenticate_token
from ..db.database import get_database
from ..services.conversational_ai_service import (
    create_conversation_token,
    build_system_prompt,
    build_tools_config,
    handle_tool_call
)
from ..services.context_service import get_user_context
from ..services.dnd_rules_service import get_dnd_rules_knowledge

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for pending actions (in production, use Redis or database)
_pending_actions: Dict[str, Dict[str, Any]] = {}


class ActionRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]


class ConfirmActionRequest(BaseModel):
    action_id: str
    confirmed: bool


@router.get("/conversational-ai/token")
async def get_conversation_token(
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Generate a single-use token for ElevenLabs Conversational AI.
    Includes user context and D&D rules knowledge in the system prompt.
    
    Returns:
        Dictionary containing token and conversation configuration
    """
    logger.info(f"Generating conversation token for user {user_id}")
    
    try:
        # Gather user context
        user_context = await get_user_context(user_id)
        logger.info(f"Gathered context: {len(user_context['campaigns'])} campaigns, "
                   f"{len(user_context['sessions'])} sessions, "
                   f"{len(user_context['characters'])} characters")
        
        # Get D&D rules knowledge
        dnd_rules = get_dnd_rules_knowledge()
        
        # Build system prompt with context
        system_prompt = build_system_prompt(user_context, dnd_rules)
        logger.info(f"Built system prompt ({len(system_prompt)} characters)")
        
        # Build tools configuration
        tools = build_tools_config()
        logger.info(f"Configured {len(tools)} tools")
        
        # Create conversation token from ElevenLabs
        result = await create_conversation_token(
            user_id=user_id,
            system_prompt=system_prompt,
            tools=tools
        )
        
        logger.info("Conversation token generated successfully")
        return result
        
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating conversation token: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate conversation token: {str(e)}"
        )


@router.post("/conversational-ai/action")
async def handle_assistant_action(
    request: ActionRequest,
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Handle an action proposed by the assistant.
    Creates a pending action that requires user confirmation.
    
    Args:
        request: Action request with tool name and parameters
        user_id: Authenticated user ID
    
    Returns:
        Action details with confirmation ID
    """
    logger.info(f"Handling action request from user {user_id}: {request.tool_name}")
    
    try:
        # Handle the tool call and create pending action
        action = await handle_tool_call(
            tool_name=request.tool_name,
            parameters=request.parameters,
            user_id=user_id
        )
        
        # Generate unique action ID
        action_id = f"{user_id}_{int(time.time() * 1000)}"
        action["action_id"] = action_id
        
        # Store pending action
        _pending_actions[action_id] = action
        
        logger.info(f"Created pending action {action_id}: {action['description']}")
        
        return {
            "action_id": action_id,
            "status": "pending_confirmation",
            "description": action["description"],
            "tool_name": action["tool_name"],
            "parameters": action["parameters"]
        }
        
    except Exception as e:
        logger.error(f"Error handling action: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to handle action: {str(e)}"
        )


@router.post("/conversational-ai/confirm")
async def confirm_action(
    request: ConfirmActionRequest,
    user_id: int = Depends(authenticate_token)
) -> Dict[str, Any]:
    """
    Confirm and execute a pending action, or reject it.
    
    Args:
        request: Confirmation request with action ID and confirmation status
        user_id: Authenticated user ID
    
    Returns:
        Result of the action execution
    """
    logger.info(f"Confirming action {request.action_id} for user {user_id}: {request.confirmed}")
    
    try:
        # Get pending action
        action = _pending_actions.get(request.action_id)
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")
        
        # Verify action belongs to user
        if action["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Action does not belong to user")
        
        # If not confirmed, just remove the pending action
        if not request.confirmed:
            del _pending_actions[request.action_id]
            logger.info(f"Action {request.action_id} rejected by user")
            return {
                "action_id": request.action_id,
                "status": "rejected",
                "message": "Action was rejected"
            }
        
        # Execute the action
        db = get_database()
        tool_name = action["tool_name"]
        params = action["parameters"]
        
        result = None
        
        if tool_name == "update_character_hp":
            # Verify character belongs to user
            char_row = db.execute(
                'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                (params["character_id"], user_id)
            ).fetchone()
            
            if not char_row:
                raise HTTPException(status_code=404, detail="Character not found")
            
            # Update character HP in active sessions
            db.execute('''
                UPDATE session_characters
                SET current_hp = ?
                WHERE character_id = ? AND session_id IN (
                    SELECT id FROM sessions WHERE user_id = ? AND status = 'active'
                )
            ''', (params["new_hp"], params["character_id"], user_id))
            
            # Also update max_hp if new_hp exceeds current max_hp
            if params["new_hp"] > char_row["max_hp"]:
                db.execute(
                    'UPDATE characters SET max_hp = ? WHERE id = ?',
                    (params["new_hp"], params["character_id"])
                )
            
            db.commit()
            result = {
                "character_id": params["character_id"],
                "character_name": params["character_name"],
                "new_hp": params["new_hp"],
                "reason": params.get("reason")
            }
            logger.info(f"Updated character {params['character_name']} HP to {params['new_hp']}")
            
        elif tool_name == "create_session":
            # Create new session
            session_id = db.execute(
                'INSERT INTO sessions (user_id, name, campaign_id, status, started_at) VALUES (?, ?, ?, ?, datetime("now"))',
                (user_id, params["name"], params.get("campaign_id"), "active")
            ).lastrowid
            
            # Add characters to session
            for char_id in params["character_ids"]:
                # Verify character belongs to user
                char_row = db.execute(
                    'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                    (char_id, user_id)
                ).fetchone()
                
                if char_row:
                    db.execute('''
                        INSERT INTO session_characters (session_id, character_id, starting_hp, current_hp, max_hp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (session_id, char_id, char_row["max_hp"], char_row["max_hp"], char_row["max_hp"]))
            
            db.commit()
            result = {
                "session_id": session_id,
                "name": params["name"],
                "character_ids": params["character_ids"]
            }
            logger.info(f"Created session {params['name']} with {len(params['character_ids'])} characters")
            
        elif tool_name == "update_character_stat":
            # Verify character belongs to user
            char_row = db.execute(
                'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                (params["character_id"], user_id)
            ).fetchone()
            
            if not char_row:
                raise HTTPException(status_code=404, detail="Character not found")
            
            # Map stat names to database columns
            stat_map = {
                "ac": "ac",
                "level": "level",
                "max_hp": "max_hp",
                "temp_hp": "temp_hp",
                "initiative_bonus": "initiative_bonus"
            }
            
            stat_column = stat_map.get(params["stat_name"])
            if not stat_column:
                raise HTTPException(status_code=400, detail=f"Invalid stat name: {params['stat_name']}")
            
            db.execute(
                f'UPDATE characters SET {stat_column} = ? WHERE id = ?',
                (params["new_value"], params["character_id"])
            )
            
            db.commit()
            result = {
                "character_id": params["character_id"],
                "character_name": params["character_name"],
                "stat_name": params["stat_name"],
                "new_value": params["new_value"]
            }
            logger.info(f"Updated character {params['character_name']} {params['stat_name']} to {params['new_value']}")
            
        elif tool_name == "create_character":
            # Create new character
            character_id = db.execute('''
                INSERT INTO characters (
                    user_id, name, max_hp, race, class_name, level,
                    campaign_id, ac, initiative_bonus, temp_hp, background, alignment, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))
            ''', (
                user_id,
                params["name"],
                params["max_hp"],
                params.get("race"),
                params.get("class_name"),
                params.get("level"),
                params.get("campaign_id"),
                params.get("ac"),
                params.get("initiative_bonus"),
                params.get("temp_hp"),
                params.get("background"),
                params.get("alignment"),
                params.get("notes")
            )).lastrowid
            
            db.commit()
            result = {
                "character_id": character_id,
                "name": params["name"],
                "max_hp": params["max_hp"]
            }
            logger.info(f"Created character {params['name']}")
            
        elif tool_name == "update_character":
            # Verify character belongs to user
            char_row = db.execute(
                'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                (params["character_id"], user_id)
            ).fetchone()
            
            if not char_row:
                raise HTTPException(status_code=404, detail="Character not found")
            
            # Build update query dynamically
            updates = []
            values = []
            
            if params.get("name") is not None:
                updates.append("name = ?")
                values.append(params["name"])
            if params.get("max_hp") is not None:
                updates.append("max_hp = ?")
                values.append(params["max_hp"])
            if params.get("race") is not None:
                updates.append("race = ?")
                values.append(params["race"])
            if params.get("class_name") is not None:
                updates.append("class_name = ?")
                values.append(params["class_name"])
            if params.get("level") is not None:
                updates.append("level = ?")
                values.append(params["level"])
            if params.get("ac") is not None:
                updates.append("ac = ?")
                values.append(params["ac"])
            if params.get("alignment") is not None:
                updates.append("alignment = ?")
                values.append(params["alignment"])
            if params.get("background") is not None:
                updates.append("background = ?")
                values.append(params["background"])
            if params.get("notes") is not None:
                updates.append("notes = ?")
                values.append(params["notes"])
            if params.get("campaign_id") is not None:
                # Verify campaign belongs to user if provided
                if params["campaign_id"]:
                    campaign = db.execute(
                        'SELECT id FROM campaigns WHERE id = ? AND user_id = ?',
                        (params["campaign_id"], user_id)
                    ).fetchone()
                    if not campaign:
                        raise HTTPException(status_code=400, detail="Campaign not found or does not belong to you")
                updates.append("campaign_id = ?")
                values.append(params["campaign_id"])
            
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            updates.append("updated_at = datetime('now')")
            values.extend([params["character_id"], user_id])
            
            query = f'UPDATE characters SET {", ".join(updates)} WHERE id = ? AND user_id = ?'
            db.execute(query, values)
            db.commit()
            
            result = {
                "character_id": params["character_id"],
                "character_name": params["character_name"],
                "updated_fields": [u.split(" = ")[0] for u in updates if "updated_at" not in u]
            }
            logger.info(f"Updated character {params['character_name']}")
            
        elif tool_name == "update_character_notes":
            # Verify character belongs to user
            char_row = db.execute(
                'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                (params["character_id"], user_id)
            ).fetchone()
            
            if not char_row:
                raise HTTPException(status_code=404, detail="Character not found")
            
            # Get existing notes
            existing_notes = char_row.get("notes") or ""
            append_mode = params.get("append_mode", True)
            
            if append_mode:
                # Append new notes
                new_notes = existing_notes + "\n\n" + params["notes"] if existing_notes else params["notes"]
            else:
                # Replace notes
                new_notes = params["notes"]
            
            db.execute(
                'UPDATE characters SET notes = ?, updated_at = datetime("now") WHERE id = ? AND user_id = ?',
                (new_notes, params["character_id"], user_id)
            )
            db.commit()
            
            result = {
                "character_id": params["character_id"],
                "character_name": params["character_name"],
                "notes_updated": True
            }
            logger.info(f"Updated notes for character {params['character_name']}")
            
        elif tool_name == "update_session":
            # Verify session belongs to user
            session_row = db.execute(
                'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
                (params["session_id"], user_id)
            ).fetchone()
            
            if not session_row:
                raise HTTPException(status_code=404, detail="Session not found")
            
            # Build update query dynamically
            updates = []
            values = []
            
            if params.get("name") is not None:
                updates.append("name = ?")
                values.append(params["name"])
            if params.get("status") is not None:
                updates.append("status = ?")
                values.append(params["status"])
            if params.get("ended_at") is not None:
                updates.append("ended_at = ?")
                values.append(params["ended_at"] if params["ended_at"] else None)
            
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.extend([params["session_id"], user_id])
            query = f'UPDATE sessions SET {", ".join(updates)} WHERE id = ? AND user_id = ?'
            db.execute(query, values)
            db.commit()
            
            result = {
                "session_id": params["session_id"],
                "session_name": params["session_name"],
                "updated_fields": [u.split(" = ")[0] for u in updates]
            }
            logger.info(f"Updated session {params['session_name']}")
            
        elif tool_name == "add_characters_to_session":
            # Verify session belongs to user
            session_row = db.execute(
                'SELECT * FROM sessions WHERE id = ? AND user_id = ?',
                (params["session_id"], user_id)
            ).fetchone()
            
            if not session_row:
                raise HTTPException(status_code=404, detail="Session not found")
            
            added_count = 0
            for char_id in params["character_ids"]:
                # Verify character belongs to user
                char_row = db.execute(
                    'SELECT * FROM characters WHERE id = ? AND user_id = ?',
                    (char_id, user_id)
                ).fetchone()
                
                if not char_row:
                    continue
                
                # Check if character is already in session
                existing = db.execute(
                    'SELECT * FROM session_characters WHERE session_id = ? AND character_id = ?',
                    (params["session_id"], char_id)
                ).fetchone()
                
                if not existing:
                    db.execute('''
                        INSERT INTO session_characters (session_id, character_id, starting_hp, current_hp, max_hp)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (params["session_id"], char_id, char_row["max_hp"], char_row["max_hp"], char_row["max_hp"]))
                    added_count += 1
            
            db.commit()
            result = {
                "session_id": params["session_id"],
                "session_name": params["session_name"],
                "characters_added": added_count
            }
            logger.info(f"Added {added_count} character(s) to session {params['session_name']}")
            
        elif tool_name == "create_campaign":
            # Create new campaign
            campaign_id = db.execute(
                'INSERT INTO campaigns (user_id, name, description, created_at, updated_at) VALUES (?, ?, ?, datetime("now"), datetime("now"))',
                (user_id, params["name"], params.get("description"))
            ).lastrowid
            
            db.commit()
            result = {
                "campaign_id": campaign_id,
                "name": params["name"],
                "description": params.get("description")
            }
            logger.info(f"Created campaign {params['name']}")
            
        elif tool_name == "update_campaign":
            # Verify campaign belongs to user
            campaign_row = db.execute(
                'SELECT * FROM campaigns WHERE id = ? AND user_id = ?',
                (params["campaign_id"], user_id)
            ).fetchone()
            
            if not campaign_row:
                raise HTTPException(status_code=404, detail="Campaign not found")
            
            # Build update query dynamically
            updates = []
            values = []
            
            if params.get("name") is not None:
                updates.append("name = ?")
                values.append(params["name"])
            if params.get("description") is not None:
                updates.append("description = ?")
                values.append(params["description"])
            
            if not updates:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            updates.append("updated_at = datetime('now')")
            values.extend([params["campaign_id"], user_id])
            
            query = f'UPDATE campaigns SET {", ".join(updates)} WHERE id = ? AND user_id = ?'
            db.execute(query, values)
            db.commit()
            
            result = {
                "campaign_id": params["campaign_id"],
                "campaign_name": params["campaign_name"],
                "updated_fields": [u.split(" = ")[0] for u in updates if "updated_at" not in u]
            }
            logger.info(f"Updated campaign {params['campaign_name']}")
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {tool_name}")
        
        # Remove pending action
        del _pending_actions[request.action_id]
        
        return {
            "action_id": request.action_id,
            "status": "executed",
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming action: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute action: {str(e)}"
        )


@router.get("/conversational-ai/pending-actions")
async def get_pending_actions(
    user_id: int = Depends(authenticate_token)
) -> List[Dict[str, Any]]:
    """
    Get all pending actions for the authenticated user.
    
    Returns:
        List of pending actions
    """
    user_actions = [
        {k: v for k, v in action.items() if k != "user_id"}
        for action in _pending_actions.values()
        if action["user_id"] == user_id
    ]
    return user_actions



