import sqlite3
from persona_db.DatabaseModels import Persona, DiscordUser, ChatInteraction, PersonaMemories
from persona_db.PersonaRepository import PersonaRepository
from persona_db.DiscordUserRepository import DiscordUserRepository
from persona_db.InteractionRepository import InteractionRepository
from persona_db.PersonaMemoriesRepository import PersonaMemoriesRepository
from persona_db.ChatInteractionRepository import ChatInteractionRepository
from typing import Any, Dict, List, Optional, Set
from contextlib import contextmanager

DB_DEFAULT_PATH = "llm_character_cards.db"

class PersonaDatabase:
    # class variables to define allowed update fields for different permission levels
    allowed_fields_basic = frozenset({"last_interaction_recv_at"})
    allowed_fields_owner = frozenset({"persona_name", "content", "visibility", "is_public", "allowed_role_ids"})
    allowed_fields_teammember = frozenset({"persona_name", "content"})
    
    def __init__(self, db_path: str = DB_DEFAULT_PATH):
        self.db_path = db_path
        self._conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False, 
            isolation_level=None
        )
        
        self.personas = PersonaRepository(self._conn)
        self.users = DiscordUserRepository(self._conn)
        self.interactions = InteractionRepository(self._conn)
        self.chat_interactions = ChatInteractionRepository(self._conn)
        self.persona_memories = PersonaMemoriesRepository(self._conn)

        self._init_db()
        
    @contextmanager
    def _transaction(self):
        """Context manager for write/update/delete operations to ensure proper commit/rollback."""
        self._conn.execute("BEGIN IMMEDIATE;")  # acquire a write lock to ensure all changes are flushed
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        
    def _init_db(self):
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = FULL")
        # self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        
        with self._transaction():
            self.personas.create_tables(self._conn)
            # self.personas.rename_legacy_persona_column(self._conn)
            self.users.create_tables(self._conn)
            # self.users.migrate(self._conn)  # run migrations for users table
            self.interactions.create_tables(self._conn)
            self.chat_interactions.create_tables(self._conn)
            self.persona_memories.create_tables(self._conn)

    def write_to_disk(self):
        """
        Manually forces a WAL checkpoint. 
        Note: This is usually not required for data safety, as commit() already writes to the WAL file.
        """
        try:
            cursor = self._conn.cursor()
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            busy, log_pages, checkpoint_pages = cursor.fetchone()
            
            if busy:
                print(f"Checkpoint was busy (active readers/writers). {log_pages} log pages and {checkpoint_pages} checkpoint pages remain.")
            return not busy
        except Exception as e:
            print(f"Failed to checkpoint WAL: {e}")
            raise
            
    def count_personas_by_owner(self, owner_uid: int) -> int:
        """Count the number of personas owned by a specific user."""
        return self.personas.count_by_owner(owner_uid)
    
    def create_persona(self, persona_name: str, content: str, owner_uid: int, is_public: bool, allowed_role_ids: Set[int] = set()) -> int:
        """Create a new persona"""
        with self._transaction():
            return self.personas.create(persona_name, content, owner_uid, is_public, allowed_role_ids)

    def get_persona(self, persona_uid: int, user_uid: int, role_ids: Set[int]) -> Optional[Persona]:
        """Get a persona if user has permission to basic_read it"""
        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_basic(user_uid, role_ids):
            return persona
        return None

    def get_persona_no_check(self, persona_uid: int) -> Optional[Persona]:
        """Get a persona without permission check, only for cache use"""
        return self.personas.fetch_by_uid(persona_uid)
    
    def _get_allowed_fields_for_user(self, persona_uid: int, user_uid: int, user_role_ids: Set[int]) -> Set[str]:
        _persona = self.personas.fetch_by_uid(persona_uid)
        if not _persona:
            raise ValueError(f"Persona with uid {persona_uid} not found.")
        
        _allowed_fields = set(self.allowed_fields_basic)
        if _persona.owner_uid == user_uid:
            _allowed_fields |= self.allowed_fields_owner
        # any intersection between persona's allowed_role_ids and user's role_ids:
        elif (_persona.allowed_role_ids & user_role_ids):
            _allowed_fields |= self.allowed_fields_teammember
            
        return _allowed_fields
    
    def update_persona(self, persona_uid: int, user_uid: int, user_roles: Set[int], **updates) -> bool:
        """Update a persona - branching logic based on whether the user is owner or has role-based permission"""
        if not updates:
            return False
        
        allowed_fields = self._get_allowed_fields_for_user(persona_uid, user_uid, user_roles)
        invalid_fields = set(updates) - allowed_fields
        if invalid_fields:
            # raise ValueError(f"Unsupported persona update fields: {sorted(invalid_fields)}")
            print(f"User {user_uid} attempted to update fields {sorted(invalid_fields)} which are not allowed based on their permissions.")
            return False
        
        with self._transaction():
            return self.personas.update(persona_uid, **updates)

    def delete_persona(self, persona_uid: int, user_uid: int) -> bool:
        """Delete a persona - only owner can delete"""
        with self._transaction():
            self.users._unbind_selected_user_for_persona(persona_uid)
            return self.personas.delete(persona_uid, user_uid)

    def list_personas(self, user_uid: int, role_ids: Set[int] = set()) -> List[Persona]:
        """List all personas visible to user (their own + public personas)"""
        return self.personas.list_visible_for_user(user_uid, role_ids)

    def set_selected_persona(self, persona_uid: int, user_uid: int, role_ids: Set[int] = set()) -> bool:
        """Set user's selected persona"""
        persona = self.get_persona(persona_uid, user_uid, role_ids)
        if not persona:
            return False
        
        with self._transaction():
            self.users.upsert_selected_persona(user_uid, persona_uid)
        return True

    def get_selected_persona(self, user_uid: int, role_ids: Set[int] = set()) -> Optional[Persona]:
        """Get user's currently selected persona"""
        persona_uid = self.users.get_selected_persona_uid(user_uid)
        if persona_uid is None:
            return None

        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_basic(user_uid, role_ids):
            return persona
        return None

    def get_selected_persona_uid(self, user_uid: int) -> Optional[int]:
        """Get user's currently selected persona uid"""
        return self.users.get_selected_persona_uid(user_uid)

    def deselect_persona(self, user_uid: int):
        """Clear user's selected persona"""
        with self._transaction():
            self.users.deselect_persona(user_uid)

    def increment_interaction_count(self, persona_uid: int, user_uid: int):
        """Increment the interaction count for a user and persona."""
        with self._transaction():
            self.interactions.increment_interaction_count(persona_uid, user_uid)

    def get_user_interaction_stats(self, user_uid: int) -> Optional[Dict[str, Any]]:
        """Get interaction statistics for a specific user."""
        return self.interactions.get_user_interaction_stats(user_uid)

    def get_top_users(self, limit: int = 5) -> List[tuple]:
        """Get top users by total interaction count."""
        return self.interactions.get_top_users(limit)

    def create_chat_interaction(
        self,
        msg_uid: int,
        user_uid: int,
        persona_uid: int,
        main_content: str,
        summary: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> bool:
        """Create a chat interaction record. returns the msg_uid if successful."""
        with self._transaction():
            return self.chat_interactions.create(
                msg_uid=msg_uid,
                user_uid=user_uid,
                persona_uid=persona_uid,
                main_content=main_content,
                summary=summary,
                user_prompt=user_prompt,
            )

    def get_chat_interaction(self, msg_uid: int) -> Optional[ChatInteraction]:
        """Get a chat interaction by message uid."""
        return self.chat_interactions.fetch_by_msg_uid(msg_uid)

    def list_chat_interactions_for_persona(self, persona_uid: int, limit: Optional[int] = None) -> List[ChatInteraction]:
        """List chat interactions for a persona."""
        return self.chat_interactions.list_by_persona_uid(persona_uid, limit=limit)

    def list_chat_interactions_for_user(self, user_uid: int, limit: Optional[int] = None) -> List[ChatInteraction]:
        """List chat interactions for a user."""
        return self.chat_interactions.list_by_user_uid(user_uid, limit=limit)

    def update_chat_interaction(self, msg_uid: int, **updates) -> bool:
        """Update a chat interaction record."""
        with self._transaction():
            return self.chat_interactions.update(msg_uid, **updates)

    def mark_chat_interaction_memorized(self, msg_uid: int, summary: Optional[str] = None) -> bool:
        """Mark a chat interaction as memorized."""
        with self._transaction():
            return self.chat_interactions.mark_memorized(msg_uid, summary=summary)

    def delete_chat_interaction(self, msg_uid: int) -> bool:
        """Delete a chat interaction record."""
        with self._transaction():
            return self.chat_interactions.delete(msg_uid)

    def create_persona_memory(
        self,
        memory_content: str,
        persona_uid: int,
        source_msg_uids: List[int],
    ) -> int:
        """Create a persona memory record."""
        with self._transaction():
            return self.persona_memories.create(
                memory_content=memory_content,
                persona_uid=persona_uid,
                source_msg_uids=source_msg_uids,
            )

    def get_persona_memory(self, memory_uid: int) -> Optional[PersonaMemories]:
        """Get a persona memory by uid."""
        return self.persona_memories.fetch_by_uid(memory_uid)

    def list_persona_memories(self, persona_uid: int) -> List[PersonaMemories]:
        """List persona memories for a persona."""
        return self.persona_memories.list_by_persona_uid(persona_uid)

    def update_persona_memory(self, memory_uid: int, **updates) -> bool:
        """Update a persona memory record."""
        with self._transaction():
            return self.persona_memories.update(memory_uid, **updates)

    def delete_persona_memory(self, memory_uid: int) -> bool:
        """Delete a persona memory record."""
        with self._transaction():
            return self.persona_memories.delete(memory_uid)

    def create_discord_user(self, user_uid: int) -> None:
        """Create a new Discord user if they don't already exist."""
        with self._transaction():
            self.users.create_if_missing(user_uid)

    def get_discord_user(self, user_uid: int) -> Optional[DiscordUser]:
        """Retrieve a Discord user by their UID."""
        return self.users.fetch_by_uid(user_uid)

    def update_discord_user(self, user_uid: int, **updates) -> bool:
        """Update a Discord user's attributes."""
        with self._transaction():
            return self.users.update(user_uid, **updates)
    
    def get_discord_user_preferred_name(self, user_uid: int) -> Optional[str]:
        """Get a Discord user's preferred name."""
        user = self.get_discord_user(user_uid)
        return user.preferred_name if user else None


def main_test():
    manager = PersonaDatabase(":memory:")
    user1_uid = 1000
    user2_uid = 2000
    user3_uid = 3000
    manager.create_discord_user(user1_uid)
    manager.create_discord_user(user2_uid)
    manager.create_discord_user(user3_uid)
    p1_uid = manager.create_persona("Test 1", "Content 1", user1_uid, True)
    p2_uid = manager.create_persona("Test 2", "Content 2", user1_uid, False)
    p3_uid = manager.create_persona("Test 3", "Content 3", user1_uid, False, allowed_role_ids={123})
    p4_uid = manager.create_persona("Test 4", "Content 4", user2_uid, True)
    result = manager.set_selected_persona(user1_uid, p1_uid)
    print(f"Select persona result: {result}")
    selected = manager.get_selected_persona(user1_uid)
    if selected:
        print(f"Selected persona: {selected.persona_name}\n---\n{selected.content[:20]}...")
    else:
        print("No persona selected.")

    personas = manager.list_personas(user1_uid)
    print("User1 can see: ")
    for persona in personas:
        print(persona)

    user2_personas = manager.list_personas(user2_uid, role_ids={123})
    print("User2 can see: ")
    for persona in user2_personas:
        print(persona)

    user = manager.get_discord_user(user1_uid)
    if user:
        print(f"Retrieved user: {user}")

    manager.update_discord_user(user1_uid, balance=100)
    updated_user = manager.get_discord_user(user1_uid)
    if updated_user:
        print(f"Updated user balance: {updated_user.balance}")

def message_test():
    db = PersonaDatabase(":memory:")
    user_uid = 1000
    persona_uid = db.create_persona("Test Persona", "Test Content", user_uid, True)
    db.create_discord_user(user_uid)

    log_msg = []
    for i in range(3):
        msg_uid = 1000 + i
        content = f"Message content {i}"
        db.create_chat_interaction(
            msg_uid=msg_uid,
            user_uid=user_uid,
            persona_uid=persona_uid,
            main_content=content,
        )
        log_msg.append(str(msg_uid))
    mem_id = db.create_persona_memory(
        memory_content="This is a memory.", 
        persona_uid=persona_uid,
        source_msg_uids=log_msg
    )
    memory = db.get_persona_memory(mem_id)
    print(f"Created memory: {memory}")
    # print(f"Created persona memory with uid: {mem_id}")
    interactions = db.list_chat_interactions_for_persona(persona_uid)
    print(f"Chat interactions for persona {persona_uid}:")
    for interaction in interactions:
        print(interaction)

if __name__ == "__main__":
    main_test()
    message_test()