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
    id: Optional[int]
    persona: str
    content: str
    owner_id: int
    visibility: PersonaVisibility
    created_at: str
    updated_at: str
    last_interaction_recv_at: Optional[str] = None
    interaction_count: int = 0
    
    def permission_check(self, user_id: int) -> bool:
        """Check if the given user_id has permission to access this persona."""
        if self.visibility == PersonaVisibility.PUBLIC:
            return True
        return self.owner_id == user_id
    
class PersonaDatabase:
    def __init__(self, db_path: str = "llm_character_cards.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    persona TEXT NOT NULL,
                    content TEXT NOT NULL,
                    owner_id INTEGER NOT NULL,  -- Store Discord UID directly
                    visibility INTEGER NOT NULL CHECK(visibility IN (0, 1)),  -- 0: private, 1: public
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_interaction_recv_at TEXT NOT NULL,
                    interaction_count INTEGER DEFAULT 0
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS discord_user (
                    user_id INTEGER PRIMARY KEY,
                    selected_persona_id INTEGER,
                    last_interaction_send_at TEXT DEFAULT NULL,
                    interaction_count INTEGER DEFAULT 0,
                    FOREIGN KEY (selected_persona_id) REFERENCES personas (id)
                )
            """)

    def create_persona(self, persona: str, content: str, owner_id: int, visibility: PersonaVisibility) -> Persona:
        """Create a new persona"""
        now = datetime.now().isoformat(timespec='milliseconds')
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO personas (persona, content, owner_id, visibility, created_at, updated_at, last_interaction_recv_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (persona, content, owner_id, visibility.value, now, now, now))
            
            persona_id = cursor.lastrowid
            return Persona(persona_id, persona, content, owner_id, visibility, now, now, now, 0)
    
    def get_persona(self, persona_id: int, user_id: int) -> Optional[Persona]:
        """Get a persona if user has permission to view it"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, persona, content, owner_id, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE id = ? AND (visibility = 1 OR owner_id = ?)
            """, (persona_id, user_id))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    id=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None
    def get_persona_no_check(self, persona_id: int) -> Optional[Persona]:
        """Get a persona without permission check, only for cache use"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, persona, content, owner_id, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE id = ?
            """, (persona_id,))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    id=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None

    def update_persona(self, persona_id: int, user_id: int, **updates) -> bool:
        """Update a persona - only owner can update"""
        if not updates:
            return False
        
        # Build dynamic update query
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        updates['updated_at'] = datetime.now().isoformat(timespec='milliseconds')
        
        query = f"""
            UPDATE personas 
            SET {set_clause}, updated_at = ?
            WHERE id = ? AND owner_id = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                query, 
                list(updates.values()) + [persona_id, user_id]
            )
            return cursor.rowcount > 0
    
    def delete_persona(self, persona_id: int, user_id: int) -> bool:
        """Delete a persona - only owner can delete"""
        
        with sqlite3.connect(self.db_path) as conn:
            # First, clear any user selections pointing to this persona
            conn.execute("""
                DELETE FROM discord_user 
                WHERE selected_persona_id = ?
            """, (persona_id,))
            
            # Then delete the persona
            cursor = conn.execute("""
                DELETE FROM personas 
                WHERE id = ? AND owner_id = ?
            """, (persona_id, user_id))
            
            return cursor.rowcount > 0
    
    def list_personas(self, user_id: int) -> List[Persona]:
        """List all personas visible to user (their own + public personas)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, persona, content, owner_id, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas 
                WHERE visibility = 1 OR owner_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            
            return [
                Persona(
                    id=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                ) for row in cursor.fetchall()
            ]
    
    def set_selected_persona(self, user_id: int, persona_id: int) -> bool:
        """Set user's selected persona"""
        # Verify persona exists and user has permission
        persona = self.get_persona(persona_id, user_id)
        if not persona:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO discord_user (user_id, selected_persona_id)
                VALUES (?, ?)
            """, (user_id, persona_id))
            
        return True
    
    def get_selected_persona(self, user_id: int) -> Optional[Persona]:
        """Get user's currently selected persona"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT p.id, p.persona, p.content, p.owner_id, p.visibility, p.created_at, p.updated_at, p.last_interaction_recv_at, p.interaction_count
                FROM personas p
                JOIN discord_user us ON p.id = us.selected_persona_id
                WHERE us.user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return Persona(
                    id=row[0],
                    persona=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=PersonaVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6],
                    last_interaction_recv_at=row[7],
                    interaction_count=row[8]
                )
            return None
        
    def get_selected_persona_id(self, user_id: int) -> int:
        """Get user's currently selected persona ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT us.selected_persona_id
                FROM discord_user us
                WHERE us.user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return row[0]
            return -1
        
    def clear_selected_persona(self, user_id: int):
        """Clear user's selected persona"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM discord_user 
                WHERE user_id = ?
            """, (user_id,))
    
    def increment_interaction_count(self, persona_id: int, user_id: int):
        """Increment the interaction count for a user and persona."""
        now = datetime.now().isoformat(timespec='milliseconds')
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE personas
                SET interaction_count = interaction_count + 1,
                    last_interaction_recv_at = ?
                WHERE id = ?
            """, (now, persona_id))
            conn.execute("""
                UPDATE discord_user
                SET interaction_count = interaction_count + 1,
                    last_interaction_send_at = ?
                WHERE user_id = ?
            """, (now, user_id))

class PersonaManager:
    def __init__(self, db_path: str = "llm_character_cards.db"):
        self.db = PersonaDatabase(db_path)
        self.current_user: Optional[int] = None
    
    def login(self, user_id: int):
        """Set current user"""
        self.current_user = user_id
        print(f"User {user_id} logged in")
    
    def create_persona(self, persona: str, content: str, visibility: PersonaVisibility) -> Optional[Persona]:
        """Create a new persona for current user"""
        if not self.current_user:
            print("Please login first")
            return None
        
        persona = self.db.create_persona(persona, content, self.current_user, visibility)
        print(f"Persona created with ID: {persona.id}")
        return persona
    
    def select_persona(self, persona_id: int) -> bool:
        """Select a persona for current user"""
        if not self.current_user:
            print("Please login first")
            return False
        
        success = self.db.set_selected_persona(self.current_user, persona_id)
        if success:
            print(f"Persona {persona_id} selected")
        else:
            print(f"Failed to select persona {persona_id} - persona not found or no permission")
        return success
    
    def get_selected_persona(self) -> Optional[Persona]:
        """Get current user's selected persona"""
        if not self.current_user:
            print("Please login first")
            return None
        
        return self.db.get_selected_persona(self.current_user)
    
    def update_selected_persona(self, persona: Optional[str] = None, content: Optional[str] = None, 
                           visibility: Optional[PersonaVisibility] = None) -> bool:
        """Update current user's selected persona"""
        if not self.current_user:
            print("Please login first")
            return False
        
        selected_persona = self.get_selected_persona()
        if not selected_persona:
            print("No persona selected")
            return False
        
        updates = {}
        if persona is not None:
            updates['persona'] = persona
        if content is not None:
            updates['content'] = content
        if visibility is not None:
            updates['visibility'] = visibility.value
        
        success = self.db.update_persona(selected_persona.id, self.current_user, **updates)
        if success:
            print("Persona updated successfully")
        else:
            print("Failed to update persona - you may not own this persona")
        return success
    
    def delete_selected_persona(self) -> bool:
        """Delete current user's selected persona"""
        if not self.current_user:
            print("Please login first")
            return False
        
        selected_persona = self.get_selected_persona()
        if not selected_persona:
            print("No persona selected")
            return False
        
        success = self.db.delete_persona(selected_persona.id, self.current_user)
        if success:
            print("Persona deleted successfully")
            self.db.clear_selected_persona(self.current_user)
        else:
            print("Failed to delete persona - not owner of this persona")
        return success
    
    def list_personas(self) -> List[Persona]:
        """List all personas visible to current user"""
        if not self.current_user:
            print("Please login first")
            return []
        
        return self.db.list_personas(self.current_user)

# Example usage
if __name__ == "__main__":
    manager = PersonaManager()
    
    # User operations
    manager.login("225833749156331520")
    
    # Create personas
    persona1 = manager.create_persona("My Private Persona", "This is private", PersonaVisibility.PRIVATE)
    persona2 = manager.create_persona("Public Persona", "This is first public", PersonaVisibility.PUBLIC)
    persona3 = manager.create_persona("Public Persona 2", "This is second public", PersonaVisibility.PUBLIC)
    # Select and work with a persona
    manager.select_persona(persona1.id)
    selected = manager.get_selected_persona()
    print(f"Selected persona: {selected.persona}\n---\n{selected.content}")
    
    # Update selected persona
    manager.update_selected_persona(persona="Updated Private Persona")
    
    # List all visible personas
    personas = manager.list_personas()
    for persona in personas:
        print(f"- {persona.persona} ({persona.visibility.value})")
    
    # Switch user
    manager.login("511412168386674691")
    user2_personas = manager.list_personas()
    print(f"User2 can see {len(user2_personas)} personas")  # Should only see public personas