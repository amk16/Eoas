import os
import logging
import uuid
from typing import Dict, Any
from dotenv import load_dotenv
from google import genai
from google.genai import types
from .gcs_service import upload_image_and_get_url

# Ensure .env is loaded
load_dotenv()

logger = logging.getLogger(__name__)

# Note: New images are now stored in Google Cloud Storage

import json
from typing import Dict, Any

def get_level_visual_logic(level: int) -> Dict[str, str]:
    """
    Returns specific visual attributes tied to character power tiers.
    Controls materials, lighting complexity, and magical effects.
    """
    if level <= 4:
        return {
            "tier": "Apprentice (Tier 1)",
            "materials": "weathered leather, rough-spun linen, basic iron, wooden staff",
            "lighting": "natural soft daylight, realistic shadows",
            "vfx": "minimal, subtle dust particles, no glow",
            "presence": "grounded, humble adventurer"
        }
    elif level <= 10:
        return {
            "tier": "Experienced (Tier 2)",
            "materials": "polished steel, reinforced leather, silk accents, etched bronze",
            "lighting": "dramatic rim lighting, focused spotlight",
            "vfx": "faint magical hum, glowing weapon runes",
            "presence": "confident hero, heroic posture"
        }
    elif level <= 16:
        return {
            "tier": "Master (Tier 3)",
            "materials": "engraved silver, gold-inlay armor, iridescent fabrics, mithril",
            "lighting": "cinematic high-contrast, dual-tone lighting",
            "vfx": "floating magical embers, swirling mana, ethereal aura",
            "presence": "commanding master, legendary stance"
        }
    else:
        return {
            "tier": "Legendary (Tier 4)",
            "materials": "cosmic obsidian, glowing crystal, divine artifacts, flowing liquid gold",
            "lighting": "god-rays, internal character luminescence, ethereal glow",
            "vfx": "reality-bending energy, spatial distortions, crackling divine power",
            "presence": "god-like entity, awe-inspiring presence"
        }



def get_class_visuals(class_name: str) -> Dict[str, str]:
    """Maps D&D classes to specific magic colors, materials, and visual vibes."""
    class_map = {
        "Artificer": {"mana": "Electric blue sparks and amber glow", "material": "Etched brass, oiled leather, clockwork gears", "vibe": "Industrial, inventor"},
        "Barbarian": {"aura": "Crimson heat-haze and primal steam", "material": "Hammered bronze, rough furs, animal bone", "vibe": "Brutal, raw, weathered"},
        "Bard": {"mana": "Prismatic musical notes and golden swirls", "material": "Embroidered velvet, polished wood, silver strings", "vibe": "Elegant, flamboyant"},
        "Cleric": {"mana": "Radiant white light and holy golden halos", "material": "Polished silver plate, heavy linen tabards", "vibe": "Divine, sanctified"},
        "Druid": {"mana": "Emerald vine particles and floating leaves", "material": "Treated ironwood, cured hide, living moss", "vibe": "Organic, ancient, wild"},
        "Fighter": {"aura": "Faint white stamina vapor", "material": "Reinforced steel, heavy gambeson, practical belts", "vibe": "Martial, disciplined, sturdy"},
        "Monk": {"aura": "Soft azure ki-aura and flowing energy", "material": "Simple saffron silk, hempen wraps, wooden beads", "vibe": "Zen, agile, spiritual"},
        "Paladin": {"mana": "Burning sunlight and brilliant white fire", "material": "Gilded plate armor, heavy velvet capes", "vibe": "Heroic, regal, armored"},
        "Ranger": {"aura": "Hunter-green mist and earthy brown dust", "material": "Weathered green leather, camouflaged cloaks", "vibe": "Swift, survivalist, keen"},
        "Rogue": {"aura": "Inky black smoke and subtle silver glimmers", "material": "Midnight-dyed suede, matte-black steel blades", "vibe": "Stealthy, sharp, dangerous"},
        "Sorcerer": {"mana": "Raw chaotic violet and neon arcane arcs", "material": "Thin iridescent silks, crystal jewelry", "vibe": "Volatile, innate power"},
        "Warlock": {"mana": "Deep iris purple and eldritch green shadows", "material": "Cracked obsidian, dark leather, occult symbols", "vibe": "Mysterious, cursed, edgy"},
        "Wizard": {"mana": "Indigo star-mists and geometric runes", "material": "Heavy layered robes, leather-bound tomes", "vibe": "Scholarly, complex, arcane"}
    }
    return class_map.get(class_name, {"aura": "faint energy", "material": "sturdy travel gear", "vibe": "adventuring"})

def get_race_visuals(race: str) -> Dict[str, str]:
    """Maps races to cultural design languages (motifs and craftsmanship)."""
    race_map = {
        "Aasimar": {"style": "Angelic gold filigree, feathered motifs, celestial pearlescence", "anatomy": "Glowing eyes, flawless skin"},
        "Dragonborn": {"style": "Draconic scale patterns, heavy ridge-like armor plates", "anatomy": "Thick scales, powerful snout, intimidating horns"},
        "Dwarf": {"style": "Thick geometric engravings, heavy stone-hewn textures", "anatomy": "Stout frame, intricate braided beard"},
        "Elf": {"style": "Flowing organic curves, leaf-shaped filigree, lightweight elegance", "anatomy": "Slender, pointed ears, ethereal features"},
        "Gnome": {"style": "Intricate miniature tinkering, whimsical gem-inlays", "anatomy": "Small stature, inquisitive bright eyes"},
        "Goliath": {"style": "Lithic skin markings, rugged mountain-climbing gear", "anatomy": "Massive towering height, stone-like skin patterns"},
        "Halfling": {"style": "Cozy rustic stitching, practical pockets, earthy comfort", "anatomy": "Small, hairy feet, cheerful expression"},
        "Human": {"style": "Versatile functionalism, balanced cultural motifs", "anatomy": "Diverse features, determined gaze"},
        "Orc": {"style": "Jagged iron spikes, heavy tusks, battle-scarred leather", "anatomy": "Grey skin, prominent lower tusks, muscular build"},
        "Tiefling": {"style": "Infernal sigils, sharp horn-jewelry, jagged silk edges", "anatomy": "Large horns, spade-tipped tail, vibrant skin tones"},
        "Tabaxi": {"style": "Feline agility-focused gear, sleek leather, tribal jewelry", "anatomy": "Leopard-like fur, predatory cat eyes"},
        "Warforged": {"style": "Industrial rivets, integrated plating, wooden 'muscle' fibers", "anatomy": "Constructed body, glowing ocular sensors"}
    }
    return race_map.get(race, {"style": "classic fantasy", "anatomy": "humanoid adventurer"})

def generate_character_art_prompt(data: Dict[str, Any]) -> str:
    level = data.get('level', 1)
    cls = get_class_visuals(data.get('class_name', ''))
    race = get_race_visuals(data.get('race', ''))
    
    # Tiered Material Progression
    if level <= 4:
        # Tier 1: Grounded, worn, realistic
        grade, metal, aura = "Weathered and basic", "Dull Iron", "Zero visible aura"
        lighting = "Natural overcast daylight, realistic shadows"
    elif level <= 10:
        # Tier 2: Refined, professional
        grade, metal, aura = "Polished and reinforced", "Forged Steel", "Faint shimmer on gear"
        lighting = "Dramatic cinematic rim-lighting"
    elif level <= 16:
        # Tier 3: Masterwork, ornate
        grade, metal, aura = "Ornate masterwork", "Mithril and Silver", "Constant swirling mana"
        lighting = "High-contrast, dual-tone accent lighting"
    else:
        # Tier 4: Divine, world-shaking
        grade, metal, aura = "Divine artifact-level", "Glowing Adamantine", "Reality-bending radiant aura"
        lighting = "Heavenly god-rays, internal luminescence"

    prompt_object = {
        "subject": {
            "title": f"Level {level} {data.get('race')} {data.get('class_name')}",
            "visual_identity": f"{race['anatomy']}. Wearing {grade} {race['style']} equipment.",
            "pose": "Heroic dynamic stance, ready for battle, full body focus"
        },
        "details": {
            "armor_weapons": f"Armor made of {metal} with {cls['material']} accents. {data.get('notes', '')}",
            "class_vfx": f"Power: {aura}. {cls.get('aura') or cls.get('mana', 'faint energy')} emanating from hands and eyes.",
            "cultural_vibe": f"Reflects {race['style']} and {cls['vibe']} aesthetic."
        },
        "artistic_direction": {
            "style": "Modern Pokemon-style Holo-Rare Full Art Illustration",
            "vibrancy": "Professional medium-vibrancy, harmonious color palette, cinematic grading",
            "lighting": lighting,
            "framing": "BORDERLESS, edge-to-edge, intricate professional digital painting",
            "Text": "NO TEXT AT ALL"
        }
    }
    return json.dumps(prompt_object, indent=2)

async def generate_character_image(character_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate character art using Google Gemini image generation service.
    
    Args:
        character_data: Dictionary containing character information
    
    Returns:
        Dictionary with 'image_url' and 'prompt' keys
    """
    character_name = character_data.get('name', 'Character')
    logger.info(f"[nano_banana_service] generate_character_image called for character: {character_name}")
    
    prompt = generate_character_art_prompt(character_data)
    logger.info(f"[nano_banana_service] Generated prompt: {prompt}")
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        error_msg = "GEMINI_API_KEY not configured in environment variables"
        logger.error(f"[nano_banana_service] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=gemini_api_key)
        
        logger.info(f"[nano_banana_service] Calling Gemini API for image generation")
        
        # Generate image using Gemini
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=types.ImageConfig(
                    aspect_ratio="1:1",  # Square aspect ratio for character portraits
                    image_size="2K"
                ),
            )
        )
        
        # Extract image from response
        image = None
        for part in response.parts:
            if image := part.as_image():
                break
        
        if not image:
            logger.error("[nano_banana_service] No image found in API response")
            raise ValueError("API response does not contain an image")
        
        # Generate a unique filename for the image
        character_id = character_data.get('id', 'unknown')
        image_filename = f"character_{character_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Get image bytes directly from the Image object
        if not hasattr(image, 'image_bytes') or image.image_bytes is None:
            raise ValueError("Image object does not have image_bytes attribute")
        image_bytes = image.image_bytes
        
        logger.info(f"[nano_banana_service] Uploading image to GCS: {image_filename}")
        
        # Upload to Google Cloud Storage and get signed URL
        image_url = await upload_image_and_get_url(
            image_bytes,
            image_filename,
            content_type='image/png'
        )
        
        logger.info(f"[nano_banana_service] Successfully uploaded image to GCS: {image_filename}")
        
        result = {
            'image_url': image_url,
            'prompt': prompt,
        }
        logger.info(f"[nano_banana_service] Image generation completed for: {character_name}")
        return result
                
    except Exception as e:
        logger.error(f"[nano_banana_service] Error generating image: {str(e)}")
        raise Exception(f"Failed to generate character image: {str(e)}")


def generate_campaign_art_prompt(campaign_data: Dict[str, Any]) -> str:
    """
    Generate an art prompt for a campaign banner image.
    
    Args:
        campaign_data: Dictionary containing campaign information
            - name: Campaign name
            - description: Campaign description
            - created_at: Creation timestamp (optional, for theme context)
            - characters: List of characters (optional, for context)
            - sessions: List of sessions (optional, for context)
    
    Returns:
        JSON string containing the structured prompt
    """
    campaign_name = campaign_data.get('name', 'Campaign')
    description = campaign_data.get('description', '')
    created_at = campaign_data.get('created_at', '')
    characters = campaign_data.get('characters', [])
    sessions = campaign_data.get('sessions', [])
    
    # Extract theme and mood from description
    description_lower = description.lower() if description else ''
    
    # Determine campaign theme based on description keywords
    theme_keywords = {
        'dark': ['dark', 'shadow', 'evil', 'corruption', 'necromancy', 'undead', 'vampire', 'demon'],
        'epic': ['epic', 'legendary', 'ancient', 'dragon', 'god', 'divine', 'cosmic'],
        'mystical': ['magic', 'arcane', 'mystical', 'enchantment', 'spell', 'wizard', 'sorcerer'],
        'nature': ['forest', 'wild', 'druid', 'nature', 'animal', 'beast', 'plant'],
        'urban': ['city', 'town', 'tavern', 'guild', 'merchant', 'noble', 'court'],
        'adventure': ['quest', 'journey', 'travel', 'explore', 'treasure', 'dungeon'],
        'war': ['war', 'battle', 'army', 'soldier', 'siege', 'conflict', 'military']
    }
    
    detected_themes = []
    for theme, keywords in theme_keywords.items():
        if any(keyword in description_lower for keyword in keywords):
            detected_themes.append(theme)
    
    # Default to adventure if no themes detected
    primary_theme = detected_themes[0] if detected_themes else 'adventure'
    
    # Map themes to visual elements
    theme_visuals = {
        'dark': {
            'palette': 'deep purples, blacks, dark blues, crimson accents',
            'mood': 'ominous shadows, dramatic contrast, mysterious atmosphere',
            'elements': 'twisted architecture, shadowy figures, dark magic, moonlit scenes'
        },
        'epic': {
            'palette': 'gold, bronze, deep blues, radiant whites, celestial colors',
            'mood': 'grandiose, awe-inspiring, legendary scale',
            'elements': 'towering structures, divine light, ancient artifacts, cosmic phenomena'
        },
        'mystical': {
            'palette': 'vibrant purples, blues, silvers, ethereal glows',
            'mood': 'enchanting, otherworldly, magical',
            'elements': 'floating runes, magical portals, arcane symbols, shimmering energy'
        },
        'nature': {
            'palette': 'greens, browns, earth tones, natural sunlight',
            'mood': 'wild, untamed, organic',
            'elements': 'ancient trees, wildlife, natural formations, druidic circles'
        },
        'urban': {
            'palette': 'warm browns, stone grays, warm torchlight, rich fabrics',
            'mood': 'bustling, civilized, social',
            'elements': 'architecture, marketplaces, guild halls, cityscapes'
        },
        'adventure': {
            'palette': 'warm earth tones, sky blues, golden hour lighting',
            'mood': 'heroic, exploratory, journey-focused',
            'elements': 'maps, compasses, distant horizons, paths through varied terrain'
        },
        'war': {
            'palette': 'steel grays, reds, blacks, smoke and fire',
            'mood': 'intense, conflict-driven, martial',
            'elements': 'battlefields, banners, weapons, fortifications'
        }
    }
    
    visuals = theme_visuals.get(primary_theme, theme_visuals['adventure'])
    
    # Build campaign context from metadata
    context_parts = []
    if characters:
        context_parts.append(f"featuring {len(characters)} adventurer{'s' if len(characters) > 1 else ''}")
    if sessions:
        active_sessions = [s for s in sessions if s.get('status') == 'active']
        if active_sessions:
            context_parts.append(f"with {len(active_sessions)} active session{'s' if len(active_sessions) > 1 else ''}")
    
    context_text = ', '.join(context_parts) if context_parts else "an epic D&D campaign"
    
    # Create the prompt object
    prompt_object = {
        "subject": {
            "title": f"{campaign_name} - Campaign Banner",
            "campaign_identity": f"A fantasy D&D campaign banner for '{campaign_name}'. {description if description else 'An epic adventure awaits.'}",
            "context": context_text
        },
        "visual_design": {
            "theme": primary_theme,
            "color_palette": visuals['palette'],
            "atmospheric_mood": visuals['mood'],
            "visual_elements": visuals['elements'],
            "composition": "Wide horizontal banner format, cinematic landscape orientation, epic scope"
        },
        "artistic_direction": {
            "style": "Epic fantasy campaign banner, cinematic digital painting, professional game art",
            "vibrancy": "Rich, saturated colors with dramatic lighting, high production value",
            "lighting": "Cinematic lighting with depth, dramatic shadows and highlights",
            "framing": "BORDERLESS wide rectangular banner, edge-to-edge composition, landscape format optimized for 21:9 ultrawide aspect ratio",
            "text": "NO TEXT AT ALL, NO WORDS, NO LETTERS, PURE VISUAL ART",
            "focus": "Epic fantasy scene that captures the essence and atmosphere of the campaign"
        }
    }
    
    return json.dumps(prompt_object, indent=2)


async def generate_campaign_image(campaign_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate campaign banner art using Google Gemini image generation service.
    
    Args:
        campaign_data: Dictionary containing campaign information
            - id: Campaign ID
            - name: Campaign name
            - description: Campaign description
            - created_at: Creation timestamp (optional)
            - characters: List of characters (optional)
            - sessions: List of sessions (optional)
    
    Returns:
        Dictionary with 'image_url' and 'prompt' keys
    """
    campaign_name = campaign_data.get('name', 'Campaign')
    logger.info(f"[nano_banana_service] generate_campaign_image called for campaign: {campaign_name}")
    
    prompt = generate_campaign_art_prompt(campaign_data)
    logger.info(f"[nano_banana_service] Generated campaign prompt: {prompt}")
    
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        error_msg = "GEMINI_API_KEY not configured in environment variables"
        logger.error(f"[nano_banana_service] {error_msg}")
        raise ValueError(error_msg)
    
    try:
        # Initialize Gemini client
        client = genai.Client(api_key=gemini_api_key)
        
        logger.info(f"[nano_banana_service] Calling Gemini API for campaign banner generation")
        
        # Generate image using Gemini with 21:9 aspect ratio for wide rectangular banner
        # Note: 21:9 is the widest available aspect ratio (ultrawide format)
        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=['IMAGE'],
                image_config=types.ImageConfig(
                    aspect_ratio="21:9",  # Wide rectangular banner aspect ratio (ultrawide)
                    image_size="2K"
                ),
            )
        )
        
        # Extract image from response
        image = None
        for part in response.parts:
            if image := part.as_image():
                break
        
        if not image:
            logger.error("[nano_banana_service] No image found in API response")
            raise ValueError("API response does not contain an image")
        
        # Generate a unique filename for the image
        campaign_id = campaign_data.get('id', 'unknown')
        image_filename = f"campaign_{campaign_id}_{uuid.uuid4().hex[:8]}.png"
        
        # Get image bytes directly from the Image object
        if not hasattr(image, 'image_bytes') or image.image_bytes is None:
            raise ValueError("Image object does not have image_bytes attribute")
        image_bytes = image.image_bytes
        
        logger.info(f"[nano_banana_service] Uploading campaign banner to GCS: {image_filename}")
        
        # Upload to Google Cloud Storage and get signed URL
        image_url = await upload_image_and_get_url(
            image_bytes,
            image_filename,
            content_type='image/png'
        )
        
        logger.info(f"[nano_banana_service] Successfully uploaded campaign banner to GCS: {image_filename}")
        
        result = {
            'image_url': image_url,
            'prompt': prompt,
        }
        logger.info(f"[nano_banana_service] Campaign banner generation completed for: {campaign_name}")
        return result
                
    except Exception as e:
        logger.error(f"[nano_banana_service] Error generating campaign banner: {str(e)}")
        raise Exception(f"Failed to generate campaign banner: {str(e)}")

