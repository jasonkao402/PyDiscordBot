from calendar import c
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

tz = timezone(timedelta(hours = 8))
tempTime = datetime.now(timezone.utc) + timedelta(seconds=-10)
tempTime = tempTime.time()

class PersonaVisibility(Enum):
    PRIVATE = 0
    PUBLIC = 1

@dataclass
class Persona:
    uid: int
    persona: str
    content: str
    owner_uid: int
    visibility: PersonaVisibility
    created_at: str
    updated_at: str
    last_interaction_recv_at: Optional[str] = None
    interaction_count: int = 0
    
    def permission_check(self, user_uid: int) -> bool:
        """Check if the given user_uid has permission to access this persona."""
        return self.visibility == PersonaVisibility.PUBLIC or self.owner_uid == user_uid
    
    def __str__(self):
        return f"Persona(uid={self.uid:3d}, persona={self.persona}, owner_uid={self.owner_uid}, visibility={self.visibility.name})"
@dataclass
class DiscordUser:
    user_uid: int
    selected_persona_uid: int
    last_interaction_send_at: Optional[str] = None
    interaction_count: int = 0
    last_payout_at: Optional[str] = None
    balance: int = 0
    
    def __str__(self):
        return f"DiscordUser(user_uid={self.user_uid}, selected_persona_uid={self.selected_persona_uid}, balance={self.balance})"
    
    def set_balance(self, amount: int):
        self.balance = amount
    
    def adjust_balance(self, delta: int):
        if self.balance + delta < 0:
            raise ValueError("Insufficient balance")
        self.balance += delta
    
    
    
class PersonaDatabase:
    def __init__(self, db_path: str = "llm_character_cards.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            # Table to store personas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personas (
                    uid INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    content TEXT NOT NULL,
                    owner_uid INTEGER NOT NULL,  -- Store Discord UID directly
                    visibility INTEGER NOT NULL CHECK(visibility IN (0, 1)),  -- 0: private, 1: public
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_interaction_recv_at TEXT NOT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    FOREIGN KEY (owner_uid) REFERENCES discord_users (user_uid)
                )
            """)
            
            # Table to track Discord users and their selected personas
            conn.execute("""
                CREATE TABLE IF NOT EXISTS discord_users (
                    user_uid INTEGER PRIMARY KEY,
                    selected_persona_uid INTEGER NOT NULL DEFAULT -1,
                    last_interaction_send_at TEXT DEFAULT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    last_payout_at TEXT DEFAULT NULL,
                    balance INTEGER DEFAULT 0,
                    FOREIGN KEY (selected_persona_uid) REFERENCES personas (uid)
                    )
                """)
            
            # Table to track user-persona interactions
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_persona_interactions (
                    user_uid INTEGER NOT NULL,
                    persona_uid INTEGER NOT NULL,
                    interaction_count INTEGER DEFAULT 1,
                    last_interaction_at TEXT NOT NULL,
                    PRIMARY KEY (user_uid, persona_uid),
                    FOREIGN KEY (user_uid) REFERENCES discord_users (user_uid),
                    FOREIGN KEY (persona_uid) REFERENCES personas (uid)
                )
            """)

    def create_persona(self, persona: str, content: str, owner_uid: int, visibility: PersonaVisibility) -> None:
        """Create a new persona, ensuring the user does not exceed the limit."""
        # Check if the user already has 5 personas
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM personas
                WHERE owner_uid = ?
            """, (owner_uid,))
            persona_count = cursor.fetchone()[0]

        if persona_count >= 5:
            print(f"User {owner_uid} has reached the persona limit.")
            return

        now = datetime.now().isoformat(timespec='milliseconds')
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO personas (persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (persona, content, owner_uid, visibility.value, now, now, now))

            persona_uid = cursor.lastrowid
            if not persona_uid:
                raise ValueError("Failed to retrieve the persona uid after insertion.")
    
    def get_persona(self, persona_uid: int, user_uid: int) -> Optional[Persona]:
        """Get a persona if user has permission to view it"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT uid, persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE uid = ? AND (visibility = 1 OR owner_uid = ?)
            """, (persona_uid, user_uid))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    uid=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_uid=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None
    def get_persona_no_check(self, persona_uid: int) -> Optional[Persona]:
        """Get a persona without permission check, only for cache use"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT uid, persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE uid = ?
            """, (persona_uid,))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    uid=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_uid=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None

    def update_persona(self, persona_uid: int, user_uid: int, **updates) -> bool:
        """Update a persona - only owner can update"""
        if not updates:
            return False
        
        # Build dynamic update query
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        updates['updated_at'] = datetime.now().isoformat(timespec='milliseconds')
        
        query = f"""
            UPDATE personas 
            SET {set_clause}, updated_at = ?
            WHERE uid = ? AND owner_uid = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                query, 
                list(updates.values()) + [persona_uid, user_uid]
            )
            return cursor.rowcount > 0
    
    def delete_persona(self, persona_uid: int, user_uid: int) -> bool:
        """Delete a persona - only owner can delete"""
        
        with sqlite3.connect(self.db_path) as conn:
            # First, clear any user selections pointing to this persona
            conn.execute("""
                DELETE FROM discord_users 
                WHERE selected_persona_uid = ?
            """, (persona_uid,))
            
            # Then delete the persona
            cursor = conn.execute("""
                DELETE FROM personas 
                WHERE uid = ? AND owner_uid = ?
            """, (persona_uid, user_uid))
            
            return cursor.rowcount > 0
    
    def list_personas(self, user_uid: int) -> List[Persona]:
        """List all personas visible to user (their own + public personas)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT uid, persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE visibility = 1 OR owner_uid = ?
                ORDER BY updated_at DESC
            """, (user_uid,))
            
            return [
                Persona(
                    uid=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_uid=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                ) for row in cursor.fetchall()
            ]
    
    def set_selected_persona(self, user_uid: int, persona_uid: int) -> bool:
        """Set user's selected persona"""
        # Verify persona exists and user has permission
        persona = self.get_persona(persona_uid, user_uid)
        if not persona:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO discord_users (user_uid, selected_persona_uid)
                VALUES (?, ?)
            """, (user_uid, persona_uid))
            
        return True
    
    def get_selected_persona(self, user_uid: int) -> Optional[Persona]:
        """Get user's currently selected persona"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT p.uid, p.persona, p.content, p.owner_uid, p.visibility, p.created_at, p.updated_at, p.last_interaction_recv_at, p.interaction_count
                FROM personas p
                JOIN discord_users us ON p.uid = us.selected_persona_uid
                WHERE us.user_uid = ?
            """, (user_uid,))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    uid=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_uid=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None
        
    def get_selected_persona_uid(self, user_uid: int) -> int:
        """Get user's currently selected persona uid"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT us.selected_persona_uid
                FROM discord_users us
                WHERE us.user_uid = ?
            """, (user_uid,))
            
            row = cursor.fetchone()
            if row:
                return row[0]
            return -1
        
    def clear_selected_persona(self, user_uid: int):
        """Clear user's selected persona"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM discord_users 
                WHERE user_uid = ?
            """, (user_uid,))
    
    def increment_interaction_count(self, persona_uid: int, user_uid: int):
        """Increment the interaction count for a user and persona."""
        now = datetime.now().isoformat(timespec='milliseconds')
        with sqlite3.connect(self.db_path) as conn:
            # 1. Update the Persona's global counts
            conn.execute("""
                UPDATE personas
                SET interaction_count = interaction_count + 1,
                    last_interaction_recv_at = ?
                WHERE uid = ?
            """, (now, persona_uid))
            
            # 2. Update the User's global counts (already in your code)
            conn.execute("""
                INSERT INTO discord_users (user_uid, interaction_count, last_interaction_send_at)
                VALUES (?, 1, ?)
                ON CONFLICT(user_uid) DO UPDATE SET
                    interaction_count = interaction_count + 1,
                    last_interaction_send_at = excluded.last_interaction_send_at
            """, (user_uid, now))

            # 3. Track the specific User-Persona interaction (The new logic)
            # Use INSERT OR REPLACE or ON CONFLICT for UPSERT logic
            # This logic will either insert a new record or update the existing one
            conn.execute("""
                INSERT INTO user_persona_interactions (user_uid, persona_uid, interaction_count, last_interaction_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_uid, persona_uid) DO UPDATE SET
                    interaction_count = interaction_count + 1,
                    last_interaction_at = excluded.last_interaction_at
            """, (user_uid, persona_uid, now))
    
    def get_user_interaction_stats(self, user_uid: int) -> Optional[Dict[str, Any]]:
        """Get interaction statistics for a specific user."""
        with sqlite3.connect(self.db_path) as conn:
            # Get user's total interaction count by summing up all interactions with personas
            cursor = conn.execute("""
                SELECT SUM(interaction_count)
                FROM user_persona_interactions
                WHERE user_uid = ?
            """, (user_uid,))
            row = cursor.fetchone()
            
            if not row or row[0] is None:
                return None
            
            total_interactions = row[0]
            
            # Get user's most interacted persona
            cursor = conn.execute("""
                SELECT p.uid, p.persona, upi.interaction_count
                FROM user_persona_interactions upi
                JOIN personas p ON upi.persona_uid = p.uid
                WHERE upi.user_uid = ?
                ORDER BY upi.interaction_count DESC
                LIMIT 1
            """, (user_uid,))
            
            most_interacted = cursor.fetchone()
            
            if most_interacted:
                return {
                    'total_interactions': total_interactions,
                    'most_interacted_persona_uid': most_interacted[0],
                    'most_interacted_persona_name': most_interacted[1],
                    'most_interacted_count': most_interacted[2]
                }
            else:
                return {
                    'total_interactions': total_interactions,
                    'most_interacted_persona_uid': None,
                    'most_interacted_persona_name': None,
                    'most_interacted_count': 0
                }
    
    def get_top_users(self, limit: int = 5) -> List[tuple]:
        """Get top users by total interaction count."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_uid, interaction_count
                FROM discord_users
                ORDER BY interaction_count DESC
                LIMIT ?
            """, (limit,))
            
            return cursor.fetchall()
        
    def create_discord_user(self, user_uid: int) -> None:
        """Create a new Discord user if they don't already exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO discord_users (user_uid, balance, interaction_count)
                VALUES (?, 0, 0)
            """, (user_uid,))

    def get_discord_user(self, user_uid: int) -> Optional[DiscordUser]:
        """Retrieve a Discord user by their UID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_uid, selected_persona_uid, last_interaction_send_at, interaction_count, last_payout_at, balance
                FROM discord_users
                WHERE user_uid = ?
            """, (user_uid,))
            row = cursor.fetchone()
            if row:
                return DiscordUser(
                    user_uid=row[0],
                    selected_persona_uid=row[1],
                    last_interaction_send_at=row[2],
                    interaction_count=row[3],
                    last_payout_at=row[4],
                    balance=row[5]
                )
            return None

    def update_discord_user(self, user_uid: int, **updates) -> bool:
        """Update a Discord user's attributes."""
        if not updates:
            return False

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        query = f"""
            UPDATE discord_users
            SET {set_clause}
            WHERE user_uid = ?
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, list(updates.values()) + [user_uid])
            return cursor.rowcount > 0

# Example usage
if __name__ == "__main__":
    manager = PersonaDatabase()
    
    # Create personas
    user1_uid = 225833749156331520
    # manager.create_persona("My Private Persona", "This is private", user1_uid, PersonaVisibility.PRIVATE)
    # manager.create_persona("Public Persona", "This is first public", user1_uid, PersonaVisibility.PUBLIC)
    # manager.create_persona("Public Persona 2", "This is second public", user1_uid, PersonaVisibility.PUBLIC)
    # Select and work with a persona
    result = manager.set_selected_persona(user1_uid, 3)
    print(f"Select persona result: {result}")
    selected = manager.get_selected_persona(user1_uid)
    if selected:
        print(f"Selected persona: {selected.persona}\n---\n{selected.content[:50]}...")
    else:
        print("No persona selected.")
    
    # List all visible personas
    personas = manager.list_personas(user1_uid)
    print("User1 can see: ")
    for persona in personas:
        print(persona)
    
    # Switch user
    user2_uid = 511412168386674691
    user2_personas = manager.list_personas(user2_uid)
    print("User2 can see: ")
    for persona in user2_personas:
        print(persona)

    # Create a new Discord user
    user_uid = 123456789
    manager.create_discord_user(user_uid)

    # Retrieve the Discord user
    user = manager.get_discord_user(user_uid)
    if user:
        print(f"Retrieved user: {user}")

    # Update the Discord user's balance
    manager.update_discord_user(user_uid, balance=100)
    updated_user = manager.get_discord_user(user_uid)
    if updated_user:
        print(f"Updated user balance: {updated_user.balance}")