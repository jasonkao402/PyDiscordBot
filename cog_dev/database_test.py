import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class NoteVisibility(Enum):
    PUBLIC = "public"
    PRIVATE = "private"

@dataclass
class Note:
    id: Optional[int]
    title: str
    content: str
    owner_id: str
    visibility: NoteVisibility
    created_at: str
    updated_at: str

class NoteDatabase:
    def __init__(self, db_path: str = "llm_character_cards.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    owner_id TEXT NOT NULL,  -- Store Discord UID directly
                    visibility TEXT NOT NULL CHECK(visibility IN ('public', 'private')),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_selections (
                    user_id TEXT PRIMARY KEY,
                    selected_note_id INTEGER,
                    FOREIGN KEY (selected_note_id) REFERENCES notes (id)
                )
            """)
    
    def create_note(self, title: str, content: str, owner_id: str, visibility: NoteVisibility) -> Note:
        """Create a new note"""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO notes (title, content, owner_id, visibility, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (title, content, owner_id, visibility.value, now, now))
            
            note_id = cursor.lastrowid
            return Note(note_id, title, content, owner_id, visibility, now, now)
    
    def get_note(self, note_id: int, user_id: str) -> Optional[Note]:
        """Get a note if user has permission to view it"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, title, content, owner_id, visibility, created_at, updated_at
                FROM notes 
                WHERE id = ? AND (visibility = 'public' OR owner_id = ?)
            """, (note_id, user_id))
            
            row = cursor.fetchone()
            if row:
                return Note(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=NoteVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6]
                )
            return None
    
    def update_note(self, note_id: int, user_id: str, **updates) -> bool:
        """Update a note - only owner can update"""
        if not updates:
            return False
        
        # Build dynamic update query
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        updates['updated_at'] = datetime.now().isoformat()
        
        query = f"""
            UPDATE notes 
            SET {set_clause}, updated_at = ?
            WHERE id = ? AND owner_id = ?
        """
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                query, 
                list(updates.values()) + [note_id, user_id]
            )
            return cursor.rowcount > 0
    
    def delete_note(self, note_id: int, user_id: str) -> bool:
        """Delete a note - only owner can delete"""
        with sqlite3.connect(self.db_path) as conn:
            # First, clear any user selections pointing to this note
            conn.execute("""
                DELETE FROM user_selections 
                WHERE selected_note_id = ?
            """, (note_id,))
            
            # Then delete the note
            cursor = conn.execute("""
                DELETE FROM notes 
                WHERE id = ? AND owner_id = ?
            """, (note_id, user_id))
            
            return cursor.rowcount > 0
    
    def list_notes(self, user_id: str) -> List[Note]:
        """List all notes visible to user (their own + public notes)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, title, content, owner_id, visibility, created_at, updated_at
                FROM notes 
                WHERE visibility = 'public' OR owner_id = ?
                ORDER BY updated_at DESC
            """, (user_id,))
            
            return [
                Note(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=NoteVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6]
                ) for row in cursor.fetchall()
            ]
    
    def set_selected_note(self, user_id: str, note_id: int) -> bool:
        """Set user's selected note"""
        # Verify note exists and user has permission
        note = self.get_note(note_id, user_id)
        if not note:
            return False
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_selections (user_id, selected_note_id)
                VALUES (?, ?)
            """, (user_id, note_id))
            
        return True
    
    def get_selected_note(self, user_id: str) -> Optional[Note]:
        """Get user's currently selected note"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT n.id, n.title, n.content, n.owner_id, n.visibility, n.created_at, n.updated_at
                FROM notes n
                JOIN user_selections us ON n.id = us.selected_note_id
                WHERE us.user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return Note(
                    id=row[0],
                    title=row[1],
                    content=row[2],
                    owner_id=row[3],
                    visibility=NoteVisibility(row[4]),
                    created_at=row[5],
                    updated_at=row[6]
                )
            return None
    
    def clear_selected_note(self, user_id: str):
        """Clear user's selected note"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                DELETE FROM user_selections 
                WHERE user_id = ?
            """, (user_id,))
    
    def _get_or_create_user_serial(self, user_id: str) -> int:
        """Get or create a serial number for a user."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT rowid FROM users WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            if row:
                return row[0]

            cursor = conn.execute("""
                INSERT INTO users (user_id) VALUES (?)
            """, (user_id,))
            return cursor.lastrowid

    def _get_user_id_by_serial(self, serial: int) -> Optional[str]:
        """Retrieve user ID by serial number."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id FROM users WHERE rowid = ?
            """, (serial,))
            row = cursor.fetchone()
            return row[0] if row else None

    def import_notes_from_file(self, file_path: str, user_id: str):
        """Import notes from a text file."""
        user_serial = self._get_or_create_user_serial(user_id)
        now = datetime.now().isoformat()

        with open(file_path, 'r', encoding='utf-8') as file, sqlite3.connect(self.db_path) as conn:
            for line in file:
                try:
                    title, content, visibility = line.strip().split('|')
                    visibility_enum = NoteVisibility(visibility.strip().lower())
                    conn.execute("""
                        INSERT INTO notes (title, content, owner_id, visibility, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (title.strip(), content.strip(), user_serial, visibility_enum.value, now, now))
                except ValueError:
                    print(f"Skipping invalid line: {line.strip()}")

class NoteManager:
    def __init__(self, db_path: str = "llm_character_cards.db"):
        self.db = NoteDatabase(db_path)
        self.current_user: Optional[str] = None
    
    def login(self, user_id: str):
        """Set current user"""
        self.current_user = user_id
        print(f"User {user_id} logged in")
    
    def create_note(self, title: str, content: str, visibility: NoteVisibility) -> Optional[Note]:
        """Create a new note for current user"""
        if not self.current_user:
            print("Please login first")
            return None
        
        note = self.db.create_note(title, content, self.current_user, visibility)
        print(f"Note created with ID: {note.id}")
        return note
    
    def select_note(self, note_id: int) -> bool:
        """Select a note for current user"""
        if not self.current_user:
            print("Please login first")
            return False
        
        success = self.db.set_selected_note(self.current_user, note_id)
        if success:
            print(f"Note {note_id} selected")
        else:
            print(f"Failed to select note {note_id} - note not found or no permission")
        return success
    
    def get_selected_note(self) -> Optional[Note]:
        """Get current user's selected note"""
        if not self.current_user:
            print("Please login first")
            return None
        
        return self.db.get_selected_note(self.current_user)
    
    def update_selected_note(self, title: Optional[str] = None, content: Optional[str] = None, 
                           visibility: Optional[NoteVisibility] = None) -> bool:
        """Update current user's selected note"""
        if not self.current_user:
            print("Please login first")
            return False
        
        selected_note = self.get_selected_note()
        if not selected_note:
            print("No note selected")
            return False
        
        updates = {}
        if title is not None:
            updates['title'] = title
        if content is not None:
            updates['content'] = content
        if visibility is not None:
            updates['visibility'] = visibility.value
        
        success = self.db.update_note(selected_note.id, self.current_user, **updates)
        if success:
            print("Note updated successfully")
        else:
            print("Failed to update note - you may not own this note")
        return success
    
    def delete_selected_note(self) -> bool:
        """Delete current user's selected note"""
        if not self.current_user:
            print("Please login first")
            return False
        
        selected_note = self.get_selected_note()
        if not selected_note:
            print("No note selected")
            return False
        
        success = self.db.delete_note(selected_note.id, self.current_user)
        if success:
            print("Note deleted successfully")
            self.db.clear_selected_note(self.current_user)
        else:
            print("Failed to delete note - you may not own this note")
        return success
    
    def list_notes(self) -> List[Note]:
        """List all notes visible to current user"""
        if not self.current_user:
            print("Please login first")
            return []
        
        return self.db.list_notes(self.current_user)

# Example usage
if __name__ == "__main__":
    manager = NoteManager()
    
    # User operations
    manager.login("225833749156331520")
    
    # Create notes
    note1 = manager.create_note("My Private Note", "This is private", NoteVisibility.PRIVATE)
    note2 = manager.create_note("Public Note", "This is first public", NoteVisibility.PUBLIC)
    note3 = manager.create_note("Public Note 2", "This is second public", NoteVisibility.PUBLIC)
    # Select and work with a note
    manager.select_note(note1.id)
    selected = manager.get_selected_note()
    print(f"Selected note: {selected.title}\n---\n{selected.content}")
    
    # Update selected note
    manager.update_selected_note(title="Updated Private Note")
    
    # List all visible notes
    notes = manager.list_notes()
    for note in notes:
        print(f"- {note.title} ({note.visibility.value})")
    
    # Switch user
    manager.login("511412168386674691")
    user2_notes = manager.list_notes()
    print(f"User2 can see {len(user2_notes)} notes")  # Should only see public notes