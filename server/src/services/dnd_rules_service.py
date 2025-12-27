# dnd_rules_service.py
"""
D&D 5th Edition Rules Knowledge Base
Provides structured knowledge about D&D rules for the voice assistant.
"""


def get_dnd_rules_knowledge() -> str:
    """
    Get comprehensive D&D 5th Edition rules knowledge.
    This is used to inform the voice assistant about general D&D rules.
    
    Returns:
        String containing D&D rules knowledge
    """
    return """
DUNGEONS & DRAGONS 5TH EDITION RULES KNOWLEDGE

=== COMBAT ===
- Combat is turn-based, with each participant taking a turn in initiative order
- Initiative is determined by a d20 roll + Dexterity modifier
- On your turn, you can move and take one action (Attack, Cast a Spell, Dash, Disengage, Dodge, Help, Hide, Ready, Search, Use an Object)
- You can also take one bonus action if you have an ability that grants one
- Opportunity attacks occur when a creature leaves another creature's reach
- Critical hits occur on a natural 20 on an attack roll, doubling all damage dice

=== DAMAGE & HEALING ===
- When a creature takes damage, subtract it from current hit points (HP)
- When HP reaches 0, the creature falls unconscious and begins making death saving throws
- Healing restores HP but cannot exceed maximum HP
- Temporary HP is added on top of current HP and is lost first
- Damage types: Acid, Cold, Fire, Force, Lightning, Necrotic, Poison, Psychic, Radiant, Thunder

=== ABILITY SCORES ===
- Six ability scores: Strength (STR), Dexterity (DEX), Constitution (CON), Intelligence (INT), Wisdom (WIS), Charisma (CHA)
- Ability modifiers range from -5 to +5 based on score (10-11 = +0, 12-13 = +1, 14-15 = +2, etc.)
- Ability checks: d20 + ability modifier + proficiency (if proficient)
- Saving throws: d20 + ability modifier + proficiency (if proficient in that save)

=== SKILLS ===
- Skills are tied to ability scores (e.g., Stealth uses Dexterity, Perception uses Wisdom)
- Proficiency bonus starts at +2 at level 1, increases to +6 at level 20
- If proficient in a skill, add proficiency bonus to ability checks for that skill

=== CHARACTER CLASSES ===
- Barbarian: Rage, Unarmored Defense, martial prowess
- Bard: Spellcasting, Bardic Inspiration, Jack of All Trades
- Cleric: Spellcasting, Divine Domain, Channel Divinity
- Druid: Spellcasting, Wild Shape, Nature magic
- Fighter: Fighting Style, Action Surge, Extra Attack
- Monk: Martial Arts, Ki, Unarmored Movement
- Paladin: Spellcasting, Divine Smite, Aura abilities
- Ranger: Spellcasting, Favored Enemy, Natural Explorer
- Rogue: Sneak Attack, Expertise, Cunning Action
- Sorcerer: Spellcasting, Sorcerous Origin, Metamagic
- Warlock: Spellcasting, Pact Magic, Eldritch Invocations
- Wizard: Spellcasting, Arcane Recovery, Spellbook

=== RACES ===
- Common races: Human, Elf, Dwarf, Halfling, Dragonborn, Gnome, Half-Elf, Half-Orc, Tiefling
- Each race provides ability score increases, racial traits, and sometimes subrace options

=== SPELLS ===
- Spell levels range from 0 (cantrips) to 9
- Spell slots are used to cast spells of that level or higher
- Cantrips can be cast at will without using spell slots
- Spell save DC = 8 + proficiency bonus + spellcasting ability modifier
- Spell attack modifier = proficiency bonus + spellcasting ability modifier

=== ARMOR CLASS (AC) ===
- AC determines how hard a creature is to hit
- Unarmored: 10 + Dexterity modifier
- Light armor: Base AC + Dexterity modifier
- Medium armor: Base AC + Dexterity modifier (max +2)
- Heavy armor: Base AC (no Dexterity modifier)
- Shield adds +2 to AC

=== CONDITIONS ===
- Blinded: Can't see, automatically fails sight-based checks
- Charmed: Can't attack charmer, charmer has advantage on social checks
- Frightened: Disadvantage on ability checks/attacks while source is in line of sight
- Grappled: Speed becomes 0, can't benefit from bonus to speed
- Paralyzed: Can't move or speak, automatically fails STR/DEX saves, attacks have advantage
- Petrified: Transformed to stone, resistant to all damage
- Poisoned: Disadvantage on attack rolls and ability checks
- Prone: Must use half movement to stand, melee attacks have advantage, ranged attacks have disadvantage
- Restrained: Speed is 0, disadvantage on DEX saves, attacks have advantage
- Stunned: Can't take actions/reactions, automatically fails STR/DEX saves, attacks have advantage
- Unconscious: Can't move or speak, drops held items, attacks have advantage, automatically fails saves

=== RESTING ===
- Short Rest: 1 hour, spend Hit Dice to recover HP
- Long Rest: 8 hours (6 hours sleep, 2 hours light activity), recover all HP and half Hit Dice
- Long rest also restores spell slots and class features

=== DEATH SAVING THROWS ===
- When at 0 HP, make death saving throws at start of each turn
- Roll d20: 10+ = success, 9 or lower = failure
- 3 successes = stable, 3 failures = death
- Natural 20 = regain 1 HP, natural 1 = 2 failures

=== ADVANTAGE & DISADVANTAGE ===
- Advantage: Roll 2d20, take the higher result
- Disadvantage: Roll 2d20, take the lower result
- Advantage and disadvantage cancel each other out (even if multiple sources)

=== MULTICLASSING ===
- Requires minimum ability scores in both classes
- Proficiency bonus is based on total character level
- Spell slots are calculated separately for each spellcasting class

=== MAGIC ITEMS ===
- Common items: +1 weapons, potions, scrolls
- Uncommon: +1 armor, wands, rings
- Rare: +2 weapons/armor, powerful wands
- Very Rare: +3 weapons/armor, legendary items
- Legendary: Artifacts, extremely powerful items

=== ENCOUNTER BUILDING ===
- Challenge Rating (CR) indicates encounter difficulty
- Easy: CR below party level
- Medium: CR equal to party level
- Hard: CR 1-2 above party level
- Deadly: CR 3+ above party level

This knowledge base provides general D&D 5th Edition rules. For specific class features, spells, or rules, refer to the official Player's Handbook or consult with the Dungeon Master.
"""


def get_dnd_rules_summary() -> str:
    """
    Get a shorter summary of D&D rules for when token limits are a concern.
    
    Returns:
        Condensed D&D rules knowledge
    """
    return """
D&D 5E QUICK REFERENCE:
- Combat: Turn-based, d20 + modifiers for attacks/saves
- HP: Damage reduces HP, 0 HP = unconscious, death saves
- Ability Scores: STR, DEX, CON, INT, WIS, CHA (modifiers: -5 to +5)
- Skills: d20 + ability mod + proficiency (if proficient)
- AC: 10 + DEX (unarmored) or armor base + modifiers
- Spells: Levels 0-9, use spell slots, save DC = 8 + prof + ability mod
- Conditions: Blinded, Charmed, Frightened, Grappled, Paralyzed, Poisoned, Prone, Restrained, Stunned, Unconscious
- Advantage/Disadvantage: Roll 2d20, take higher/lower
- Rest: Short (1hr, spend Hit Dice) or Long (8hr, full recovery)
"""







