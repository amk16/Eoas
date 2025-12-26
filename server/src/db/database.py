import sqlite3
import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_db: Optional[sqlite3.Connection] = None
_db_path: Optional[str] = None


def init_database() -> None:
    """Initialize the database connection and create tables if they don't exist."""
    global _db, _db_path
    
    # Get database path from environment or use default
    db_path = os.getenv('DATABASE_PATH')
    if not db_path:
        # Default to data/dnd_tracker.db relative to server directory
        server_dir = Path(__file__).parent.parent.parent
        db_path = str(server_dir / 'data' / 'dnd_tracker.db')
    
    _db_path = db_path
    
    # Ensure data directory exists
    db_dir = Path(db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    _db = sqlite3.connect(db_path, check_same_thread=False)
    _db.row_factory = sqlite3.Row  # Enable column access by name
    
    # Enable WAL mode
    _db.execute('PRAGMA journal_mode = WAL')
    
    create_tables()
    print(f'Database initialized at: {db_path}')


def create_tables() -> None:
    """Create database tables if they don't exist."""
    if not _db:
        raise RuntimeError('Database not initialized')
    
    # Users table
    _db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Campaigns table
    _db.execute('''
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Characters table
    _db.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            campaign_id INTEGER,
            name TEXT NOT NULL,
            max_hp INTEGER NOT NULL,
            race TEXT,
            class_name TEXT,
            level INTEGER,
            ac INTEGER,
            initiative_bonus INTEGER,
            temp_hp INTEGER,
            background TEXT,
            alignment TEXT,
            notes TEXT,
            display_art_url TEXT,
            art_prompt TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL
        )
    ''')
    
    # Sessions table
    _db.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            campaign_id INTEGER,
            name TEXT NOT NULL,
            started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ended_at DATETIME,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(id) ON DELETE SET NULL
        )
    ''')
    
    # Session characters table (junction table)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS session_characters (
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            starting_hp INTEGER NOT NULL,
            current_hp INTEGER NOT NULL,
            PRIMARY KEY (session_id, character_id),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Damage events table
    _db.execute('''
        CREATE TABLE IF NOT EXISTS damage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('damage', 'healing')),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            transcript_segment TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')

    # Session transcript segments (persisted transcription stream)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS session_transcripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            client_chunk_id TEXT NOT NULL,
            client_timestamp_ms INTEGER,
            text TEXT NOT NULL,
            speaker TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            UNIQUE(session_id, client_chunk_id)
        )
    ''')

    # Helpful index for paginating / streaming segments
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_session_transcripts_session_id_id
        ON session_transcripts (session_id, id)
    ''')
    
    # Phase 1: Combat events table (initiative rolls, turn advances, round starts, combat end)
    # Note: We don't use CHECK constraint because SQLite doesn't support altering them
    # Validation is handled in application layer via event type registry
    
    # First, check if table exists with old CHECK constraint and migrate if needed
    try:
        table_info = _db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='combat_events'"
        ).fetchone()
        
        if table_info and table_info[0] and 'CHECK(event_type IN' in table_info[0]:
            # Table exists with old CHECK constraint - need to migrate
            logger.info("Migrating combat_events table: removing CHECK constraint to support new event types...")
            
            # Create new table without CHECK constraint
            _db.execute('''
                CREATE TABLE combat_events_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    character_id INTEGER,
                    event_type TEXT NOT NULL,
                    initiative_value INTEGER,
                    round_number INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    transcript_segment TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL
                )
            ''')
            
            # Copy data from old table
            _db.execute('''
                INSERT INTO combat_events_new 
                SELECT * FROM combat_events
            ''')
            
            # Drop old table
            _db.execute('DROP TABLE combat_events')
            
            # Rename new table
            _db.execute('ALTER TABLE combat_events_new RENAME TO combat_events')
            
            _db.commit()
            logger.info("Migration complete: combat_events table updated successfully")
    except Exception as e:
        # If migration fails, rollback and continue
        _db.rollback()
        # Check if error is because table doesn't exist yet (which is fine)
        if 'no such table' not in str(e).lower() and 'no such column' not in str(e).lower():
            logger.warning(f"Combat events migration check: {e}")
    
    # Now create table if it doesn't exist (or was just migrated)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS combat_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            character_id INTEGER,
            event_type TEXT NOT NULL,
            initiative_value INTEGER,
            round_number INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            transcript_segment TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE SET NULL
        )
    ''')
    
    # Phase 1: Initiative order table (current turn order state)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS initiative_order (
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            initiative_value INTEGER NOT NULL,
            turn_order INTEGER NOT NULL,
            PRIMARY KEY (session_id, character_id),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Phase 1: Combat state table (current round, current turn, active status)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS combat_state (
            session_id INTEGER PRIMARY KEY,
            current_round INTEGER DEFAULT 1,
            current_turn_character_id INTEGER,
            is_active INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (current_turn_character_id) REFERENCES characters(id) ON DELETE SET NULL
        )
    ''')
    
    # Indexes for combat queries
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_combat_events_session_id
        ON combat_events (session_id, timestamp)
    ''')
    
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_initiative_order_session_turn
        ON initiative_order (session_id, turn_order)
    ''')
    
    # Phase 2: Status condition events table (history of condition applications/removals)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS status_condition_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            condition_name TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('applied', 'removed')),
            duration_minutes INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            transcript_segment TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Phase 2: Active status conditions table (current active conditions)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS active_status_conditions (
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            condition_name TEXT NOT NULL,
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            duration_minutes INTEGER,
            PRIMARY KEY (session_id, character_id, condition_name),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Indexes for status condition queries
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_status_condition_events_session_id
        ON status_condition_events (session_id, timestamp)
    ''')
    
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_active_status_conditions_session_character
        ON active_status_conditions (session_id, character_id)
    ''')
    
    # Phase 3: Buff/Debuff events table (history of effect applications/removals)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS buff_debuff_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            effect_name TEXT NOT NULL,
            effect_type TEXT NOT NULL CHECK(effect_type IN ('buff', 'debuff')),
            action TEXT NOT NULL CHECK(action IN ('applied', 'removed')),
            stat_modifications TEXT,  -- JSON string: {"ac": 2, "attack_rolls": 1, "saving_throws": -1, etc.}
            stacking_rule TEXT,  -- 'none', 'stack', 'replace', 'highest'
            duration_minutes INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            transcript_segment TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Phase 3: Active buffs/debuffs table (current active effects with stat modifications)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS active_buff_debuffs (
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            effect_name TEXT NOT NULL,
            effect_type TEXT NOT NULL CHECK(effect_type IN ('buff', 'debuff')),
            stat_modifications TEXT NOT NULL,  -- JSON string: {"ac": 2, "attack_rolls": 1, "saving_throws": -1, etc.}
            stacking_rule TEXT NOT NULL,  -- 'none', 'stack', 'replace', 'highest'
            applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            duration_minutes INTEGER,
            source TEXT,  -- Optional: spell name, item name, etc.
            PRIMARY KEY (session_id, character_id, effect_name),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Indexes for buff/debuff queries
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_buff_debuff_events_session_id
        ON buff_debuff_events (session_id, timestamp)
    ''')
    
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_active_buff_debuffs_session_character
        ON active_buff_debuffs (session_id, character_id)
    ''')
    
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_active_buff_debuffs_expires_at
        ON active_buff_debuffs (expires_at)
    ''')
    
    # Phase 4: Spell events table (history of spell casts)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS spell_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            spell_name TEXT NOT NULL,
            spell_level INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            transcript_segment TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Phase 4: Character spell slot usage table (current spell slot usage per character per session)
    _db.execute('''
        CREATE TABLE IF NOT EXISTS character_spell_slots (
            session_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            spell_level INTEGER NOT NULL,
            slots_used INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (session_id, character_id, spell_level),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (character_id) REFERENCES characters(id) ON DELETE CASCADE
        )
    ''')
    
    # Indexes for spell queries
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_spell_events_session_id
        ON spell_events (session_id, timestamp)
    ''')
    
    _db.execute('''
        CREATE INDEX IF NOT EXISTS idx_character_spell_slots_session_character
        ON character_spell_slots (session_id, character_id)
    ''')
    
    # Add campaign_id columns to existing tables if they don't exist (migration)
    try:
        # Check if campaign_id column exists in characters table
        cursor = _db.execute("PRAGMA table_info(characters)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'campaign_id' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL')

        # Character expansion columns (safe additive migrations)
        if 'race' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN race TEXT')
        if 'class_name' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN class_name TEXT')
        if 'level' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN level INTEGER')
        if 'ac' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN ac INTEGER')
        if 'initiative_bonus' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN initiative_bonus INTEGER')
        if 'temp_hp' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN temp_hp INTEGER')
        if 'background' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN background TEXT')
        if 'alignment' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN alignment TEXT')
        if 'notes' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN notes TEXT')
        if 'display_art_url' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN display_art_url TEXT')
        if 'art_prompt' not in columns:
            _db.execute('ALTER TABLE characters ADD COLUMN art_prompt TEXT')
        
        # Check if campaign_id column exists in sessions table
        cursor = _db.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'campaign_id' not in columns:
            _db.execute('ALTER TABLE sessions ADD COLUMN campaign_id INTEGER REFERENCES campaigns(id) ON DELETE SET NULL')
        
        _db.commit()
    except Exception as e:
        print(f'Warning: Migration may have failed (this is OK if columns already exist): {e}')
        _db.rollback()
    
    _db.commit()
    print('Database tables created successfully')


def get_database() -> sqlite3.Connection:
    """Get the database connection."""
    if not _db:
        raise RuntimeError('Database not initialized. Call init_database() first.')
    return _db

