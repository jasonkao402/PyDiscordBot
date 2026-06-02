import sqlite3
from persona_db.DatabaseModels import Persona, DiscordUser, ChatInteraction, PersonaVisibility, PersonaMemories
from persona_db.PersonaRepository import PersonaRepository
from persona_db.DiscordUserRepository import DiscordUserRepository
from persona_db.InteractionRepository import InteractionRepository
from persona_db.PersonaMemoriesRepository import PersonaMemoriesRepository
from persona_db.ChatInteractionRepository import ChatInteractionRepository
from typing import Any, Dict, List, Optional, Set

DB_DEFAULT_PATH = "llm_character_cards.db"

class PersonaDatabase:
    def __init__(self, db_path: str = DB_DEFAULT_PATH):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        # self._conn.execute("PRAGMA foreign_keys = ON;")

        self.personas = PersonaRepository(self._conn)
        self.users = DiscordUserRepository(self._conn)
        self.interactions = InteractionRepository(self._conn)
        self.chat_interactions = ChatInteractionRepository(self._conn)
        self.persona_memories = PersonaMemoriesRepository(self._conn)

        self._init_db()

    def _init_db(self):
        self.personas.create_tables(self._conn)
        self.personas.rename_legacy_persona_column(self._conn)
        self.personas.add_is_public_column(self._conn)
        self.users.create_tables(self._conn)
        self.interactions.create_tables(self._conn)
        self.chat_interactions.create_tables(self._conn)
        self.persona_memories.create_tables(self._conn)

    def create_persona(self, persona: str, content: str, owner_uid: int, is_public: bool | PersonaVisibility) -> int:
        """Create a new persona, ensuring the user does not exceed the limit."""
        persona_count = self.personas.count_by_owner(owner_uid)
        if persona_count >= 5:
            print(f"User {owner_uid} has reached the persona limit.")
            return -1
        is_public_value = bool(is_public.value) if isinstance(is_public, PersonaVisibility) else is_public
        return self.personas.create(persona, content, owner_uid, is_public_value)

    def get_persona(self, persona_uid: int, user_uid: int, role_ids: Set[int]) -> Optional[Persona]:
        """Get a persona if user has permission to view it"""
        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_basic(user_uid, role_ids):
            return persona
        return None

    def get_persona_no_check(self, persona_uid: int) -> Optional[Persona]:
        """Get a persona without permission check, only for cache use"""
        return self.personas.fetch_by_uid(persona_uid)

    def update_persona(self, persona_uid: int, user_uid: int, user_roles: Set[int], **updates) -> bool:
        """Update a persona - branching logic based on whether the user is owner or has role-based permission"""
        if not updates:
            return False
        
        _persona = self.personas.fetch_by_uid(persona_uid)
        if not _persona: # check if persona exists
            return False
        
        if _persona.permission_full(user_uid, user_roles):
            allowed_fields = self.personas.allowed_owner_update_fields
            return self.personas.update(persona_uid, allowed_fields, **updates)
        
        elif _persona.permission_basic(user_uid, user_roles):
            allowed_fields = self.personas.allowed_teammember_update_fields
            return self.personas.update(persona_uid, allowed_fields, **updates)
        
        else:
            return False

    def delete_persona(self, persona_uid: int, user_uid: int) -> bool:
        """Delete a persona - only owner can delete"""
        self.users.clear_persona_selection(persona_uid)
        return self.personas.delete(persona_uid, user_uid)

    def list_personas(self, user_uid: int) -> List[Persona]:
        """List all personas visible to user (their own + public personas)"""
        return self.personas.list_visible_for_user(user_uid, [])

    def set_selected_persona(self, user_uid: int, persona_uid: int, role_ids: Set[int] = set()) -> bool:
        """Set user's selected persona"""
        persona = self.get_persona(persona_uid, user_uid, role_ids)
        if not persona:
            return False

        self.users.upsert_selected_persona(user_uid, persona_uid)
        return True

    def get_selected_persona(self, user_uid: int, role_ids: Set[int] = set()) -> Optional[Persona]:
        """Get user's currently selected persona"""
        persona_uid = self.users.get_selected_persona_uid(user_uid)
        if persona_uid < 0:
            return None

        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_basic(user_uid, role_ids):
            return persona
        return None

    def get_selected_persona_uid(self, user_uid: int) -> int:
        """Get user's currently selected persona uid"""
        return self.users.get_selected_persona_uid(user_uid)

    def clear_selected_persona(self, user_uid: int):
        """Clear user's selected persona"""
        self.users.clear_selected_persona(user_uid)

    def increment_interaction_count(self, persona_uid: int, user_uid: int):
        """Increment the interaction count for a user and persona."""
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
        created_at: Optional[str] = None,
        is_memorized: bool = False,
        summary: Optional[str] = None,
    ) -> bool:
        """Create a chat interaction record."""
        return self.chat_interactions.create(
            msg_uid=msg_uid,
            user_uid=user_uid,
            persona_uid=persona_uid,
            main_content=main_content,
            created_at=created_at,
            is_memorized=is_memorized,
            summary=summary,
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
        return self.chat_interactions.update(msg_uid, **updates)

    def mark_chat_interaction_memorized(self, msg_uid: int, summary: Optional[str] = None) -> bool:
        """Mark a chat interaction as memorized."""
        return self.chat_interactions.mark_memorized(msg_uid, summary=summary)

    def delete_chat_interaction(self, msg_uid: int) -> bool:
        """Delete a chat interaction record."""
        return self.chat_interactions.delete(msg_uid)

    def create_persona_memory(
        self,
        memory_content: str,
        persona_uid: int,
        source_msg_uids: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> int:
        """Create a persona memory record."""
        return self.persona_memories.create(
            memory_content=memory_content,
            persona_uid=persona_uid,
            source_msg_uids=source_msg_uids,
            created_at=created_at,
            updated_at=updated_at,
        )

    def get_persona_memory(self, memory_uid: int) -> Optional[PersonaMemories]:
        """Get a persona memory by uid."""
        return self.persona_memories.fetch_by_uid(memory_uid)

    def list_persona_memories(self, persona_uid: int) -> List[PersonaMemories]:
        """List persona memories for a persona."""
        return self.persona_memories.list_by_persona_uid(persona_uid)

    def update_persona_memory(self, memory_uid: int, **updates) -> bool:
        """Update a persona memory record."""
        return self.persona_memories.update(memory_uid, **updates)

    def delete_persona_memory(self, memory_uid: int) -> bool:
        """Delete a persona memory record."""
        return self.persona_memories.delete(memory_uid)

    def create_discord_user(self, user_uid: int) -> None:
        """Create a new Discord user if they don't already exist."""
        self.users.create_if_missing(user_uid)

    def get_discord_user(self, user_uid: int) -> Optional[DiscordUser]:
        """Retrieve a Discord user by their UID."""
        return self.users.fetch_by_uid(user_uid)

    def update_discord_user(self, user_uid: int, **updates) -> bool:
        """Update a Discord user's attributes."""
        return self.users.update(user_uid, **updates)


def main_test():
    manager = PersonaDatabase(":memory:")
    user1_uid = 1000
    user2_uid = 2000
    user3_uid = 3000
    manager.create_discord_user(user1_uid)
    manager.create_discord_user(user2_uid)
    manager.create_discord_user(user3_uid)
    manager.create_persona("Test1", "Content for Test1", user1_uid, PersonaVisibility.PUBLIC)
    manager.create_persona("Test2", "Content for Test2", user1_uid, PersonaVisibility.PRIVATE)
    manager.create_persona("Test3", "Content for Test3", user2_uid, PersonaVisibility.PUBLIC)
    result = manager.set_selected_persona(user1_uid, 1)
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

    user2_personas = manager.list_personas(user2_uid)
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

if __name__ == "__main__":
    main_test()