import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


DB_DEFAULT_PATH = "llm_character_cards.db"


def _now_iso() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="milliseconds")


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
    interaction_count: int = 0 # unused for now

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
    interaction_count: int = 0 # unused for now
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


def _persona_from_row(row: tuple) -> Persona:
    return Persona(
        uid=row[0],
        persona=row[1],
        content=row[2],
        owner_uid=row[3],
        visibility=PersonaVisibility(row[4]),
        created_at=row[5],
        updated_at=row[6],
        last_interaction_recv_at=row[7],
        interaction_count=row[8],
    )


def _discord_user_from_row(row: tuple) -> DiscordUser:
    return DiscordUser(
        user_uid=row[0],
        selected_persona_uid=row[1],
        last_interaction_send_at=row[2],
        interaction_count=row[3],
        last_payout_at=row[4],
        balance=row[5],
    )


class SQLiteRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def connection(self):
        with sqlite3.connect(self.db_path) as conn:
            yield conn


class PersonaRepository(SQLiteRepository):
    allowed_update_fields = {"persona", "content", "visibility", "last_interaction_recv_at", "interaction_count"}

    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                uid INTEGER PRIMARY KEY AUTOINCREMENT,
                persona TEXT NOT NULL,
                content TEXT NOT NULL,
                owner_uid INTEGER NOT NULL,
                visibility INTEGER NOT NULL CHECK(visibility IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_interaction_recv_at TEXT NOT NULL,
                interaction_count INTEGER DEFAULT 0,
                FOREIGN KEY (owner_uid) REFERENCES discord_users (user_uid)
            )
            """
        )

    def count_by_owner(self, owner_uid: int) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*)
                FROM personas
                WHERE owner_uid = ?
                """,
                (owner_uid,),
            )
            row = cursor.fetchone()
            return row[0] if row else 0

    def create(self, persona: str, content: str, owner_uid: int, visibility: PersonaVisibility) -> int:
        now = _now_iso()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO personas (persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (persona, content, owner_uid, visibility.value, now, now, now),
            )
            persona_uid = cursor.lastrowid
            if not persona_uid:
                raise ValueError("Failed to retrieve the persona uid after insertion.")
            return persona_uid

    def fetch_by_uid(self, persona_uid: int) -> Optional[Persona]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT uid, persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas
                WHERE uid = ?
                """,
                (persona_uid,),
            )
            row = cursor.fetchone()
            return _persona_from_row(row) if row else None

    def list_visible_for_user(self, user_uid: int) -> List[Persona]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT uid, persona, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas
                WHERE visibility = 1 OR owner_uid = ?
                ORDER BY updated_at DESC
                """,
                (user_uid,),
            )
            return [_persona_from_row(row) for row in cursor.fetchall()]

    def update(self, persona_uid: int, owner_uid: int, **updates) -> bool:
        if not updates:
            return False

        invalid_fields = set(updates) - self.allowed_update_fields
        if invalid_fields:
            raise ValueError(f"Unsupported persona update fields: {sorted(invalid_fields)}")

        normalized_updates = {
            key: value.value if isinstance(value, Enum) else value
            for key, value in updates.items()
        }
        normalized_updates["updated_at"] = _now_iso()

        set_clause = ", ".join([f"{key} = ?" for key in normalized_updates.keys()])
        query = f"""
            UPDATE personas
            SET {set_clause}
            WHERE uid = ? AND owner_uid = ?
        """

        with self.connection() as conn:
            cursor = conn.execute(query, list(normalized_updates.values()) + [persona_uid, owner_uid])
            return cursor.rowcount > 0

    def delete(self, persona_uid: int, owner_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM personas
                WHERE uid = ? AND owner_uid = ?
                """,
                (persona_uid, owner_uid),
            )
            return cursor.rowcount > 0


class DiscordUserRepository(SQLiteRepository):
    allowed_update_fields = {
        "selected_persona_uid",
        "last_interaction_send_at",
        "interaction_count",
        "last_payout_at",
        "balance",
        "preferred_name",
    }

    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discord_users (
                user_uid INTEGER PRIMARY KEY,
                selected_persona_uid INTEGER NOT NULL DEFAULT -1,
                last_interaction_send_at TEXT DEFAULT NULL,
                interaction_count INTEGER DEFAULT 0,
                last_payout_at TEXT DEFAULT NULL,
                balance INTEGER DEFAULT 0,
                preferred_name TEXT DEFAULT NULL,
                FOREIGN KEY (selected_persona_uid) REFERENCES personas (uid)
            )
            """
        )

    def create_if_missing(self, user_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO discord_users (user_uid, balance, interaction_count)
                VALUES (?, 0, 0)
                """,
                (user_uid,),
            )

    def fetch_by_uid(self, user_uid: int) -> Optional[DiscordUser]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT user_uid, selected_persona_uid, last_interaction_send_at, interaction_count, last_payout_at, balance
                FROM discord_users
                WHERE user_uid = ?
                """,
                (user_uid,),
            )
            row = cursor.fetchone()
            return _discord_user_from_row(row) if row else None

    def update(self, user_uid: int, **updates) -> bool:
        if not updates:
            return False

        invalid_fields = set(updates) - self.allowed_update_fields
        if invalid_fields:
            raise ValueError(f"Unsupported discord user update fields: {sorted(invalid_fields)}")

        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        query = f"""
            UPDATE discord_users
            SET {set_clause}
            WHERE user_uid = ?
        """
        with self.connection() as conn:
            cursor = conn.execute(query, list(updates.values()) + [user_uid])
            return cursor.rowcount > 0

    def upsert_selected_persona(self, user_uid: int, persona_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO discord_users (user_uid, selected_persona_uid)
                VALUES (?, ?)
                ON CONFLICT(user_uid) DO UPDATE SET
                    selected_persona_uid = excluded.selected_persona_uid
                """,
                (user_uid, persona_uid),
            )

    def get_selected_persona_uid(self, user_uid: int) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT selected_persona_uid
                FROM discord_users
                WHERE user_uid = ?
                """,
                (user_uid,),
            )
            row = cursor.fetchone()
            return row[0] if row else -1

    def clear_selected_persona(self, user_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE discord_users
                SET selected_persona_uid = -1
                WHERE user_uid = ?
                """,
                (user_uid,),
            )

    def clear_persona_selection(self, persona_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE discord_users
                SET selected_persona_uid = -1
                WHERE selected_persona_uid = ?
                """,
                (persona_uid,),
            )


class InteractionRepository(SQLiteRepository):
    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_persona_interactions (
                user_uid INTEGER NOT NULL,
                persona_uid INTEGER NOT NULL,
                interaction_count INTEGER DEFAULT 1,
                last_interaction_at TEXT NOT NULL,
                PRIMARY KEY (user_uid, persona_uid),
                FOREIGN KEY (user_uid) REFERENCES discord_users (user_uid),
                FOREIGN KEY (persona_uid) REFERENCES personas (uid)
            )
            """
        )

    def increment_interaction_count(self, persona_uid: int, user_uid: int) -> None:
        now = _now_iso()
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE personas
                SET interaction_count = interaction_count + 1,
                    last_interaction_recv_at = ?
                WHERE uid = ?
                """,
                (now, persona_uid),
            )

            conn.execute(
                """
                INSERT INTO discord_users (user_uid, interaction_count, last_interaction_send_at)
                VALUES (?, 1, ?)
                ON CONFLICT(user_uid) DO UPDATE SET
                    interaction_count = interaction_count + 1,
                    last_interaction_send_at = excluded.last_interaction_send_at
                """,
                (user_uid, now),
            )

            conn.execute(
                """
                INSERT INTO user_persona_interactions (user_uid, persona_uid, interaction_count, last_interaction_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(user_uid, persona_uid) DO UPDATE SET
                    interaction_count = interaction_count + 1,
                    last_interaction_at = excluded.last_interaction_at
                """,
                (user_uid, persona_uid, now),
            )

    def get_user_interaction_stats(self, user_uid: int) -> Optional[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT SUM(interaction_count)
                FROM user_persona_interactions
                WHERE user_uid = ?
                """,
                (user_uid,),
            )
            row = cursor.fetchone()

            if not row or row[0] is None:
                return None

            total_interactions = row[0]

            cursor = conn.execute(
                """
                SELECT p.uid, p.persona, upi.interaction_count
                FROM user_persona_interactions upi
                JOIN personas p ON upi.persona_uid = p.uid
                WHERE upi.user_uid = ?
                ORDER BY upi.interaction_count DESC
                LIMIT 1
                """,
                (user_uid,),
            )
            most_interacted = cursor.fetchone()

            if most_interacted:
                return {
                    "total_interactions": total_interactions,
                    "most_interacted_persona_uid": most_interacted[0],
                    "most_interacted_persona_name": most_interacted[1],
                    "most_interacted_count": most_interacted[2],
                }

            return {
                "total_interactions": total_interactions,
                "most_interacted_persona_uid": None,
                "most_interacted_persona_name": None,
                "most_interacted_count": 0,
            }

    def get_top_users(self, limit: int = 5) -> List[tuple]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT user_uid, SUM(interaction_count) as total_interactions
                FROM user_persona_interactions
                GROUP BY user_uid
                ORDER BY total_interactions DESC
                LIMIT ?
                """,
                (limit,),
            )
            return cursor.fetchall()


class PersonaDatabase:
    def __init__(self, db_path: str = DB_DEFAULT_PATH):
        self.db_path = db_path
        self.personas = PersonaRepository(db_path)
        self.users = DiscordUserRepository(db_path)
        self.interactions = InteractionRepository(db_path)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            self.personas.create_tables(conn)
            self.users.create_tables(conn)
            self.interactions.create_tables(conn)

    def create_persona(self, persona: str, content: str, owner_uid: int, visibility: PersonaVisibility) -> int:
        """Create a new persona, ensuring the user does not exceed the limit."""
        persona_count = self.personas.count_by_owner(owner_uid)
        if persona_count >= 5:
            print(f"User {owner_uid} has reached the persona limit.")
            return -1

        return self.personas.create(persona, content, owner_uid, visibility)

    def get_persona(self, persona_uid: int, user_uid: int) -> Optional[Persona]:
        """Get a persona if user has permission to view it"""
        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_check(user_uid):
            return persona
        return None

    def get_persona_no_check(self, persona_uid: int) -> Optional[Persona]:
        """Get a persona without permission check, only for cache use"""
        return self.personas.fetch_by_uid(persona_uid)

    def update_persona(self, persona_uid: int, user_uid: int, **updates) -> bool:
        """Update a persona - only owner can update"""
        return self.personas.update(persona_uid, user_uid, **updates)

    def delete_persona(self, persona_uid: int, user_uid: int) -> bool:
        """Delete a persona - only owner can delete"""
        self.users.clear_persona_selection(persona_uid)
        return self.personas.delete(persona_uid, user_uid)

    def list_personas(self, user_uid: int) -> List[Persona]:
        """List all personas visible to user (their own + public personas)"""
        return self.personas.list_visible_for_user(user_uid)

    def set_selected_persona(self, user_uid: int, persona_uid: int) -> bool:
        """Set user's selected persona"""
        persona = self.get_persona(persona_uid, user_uid)
        if not persona:
            return False

        self.users.upsert_selected_persona(user_uid, persona_uid)
        return True

    def get_selected_persona(self, user_uid: int) -> Optional[Persona]:
        """Get user's currently selected persona"""
        persona_uid = self.users.get_selected_persona_uid(user_uid)
        if persona_uid < 0:
            return None

        persona = self.personas.fetch_by_uid(persona_uid)
        if persona and persona.permission_check(user_uid):
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

    def create_discord_user(self, user_uid: int) -> None:
        """Create a new Discord user if they don't already exist."""
        self.users.create_if_missing(user_uid)

    def get_discord_user(self, user_uid: int) -> Optional[DiscordUser]:
        """Retrieve a Discord user by their UID."""
        return self.users.fetch_by_uid(user_uid)

    def update_discord_user(self, user_uid: int, **updates) -> bool:
        """Update a Discord user's attributes."""
        return self.users.update(user_uid, **updates)


if __name__ == "__main__":
    manager = PersonaDatabase()

    user1_uid = 225833749156331520
    result = manager.set_selected_persona(user1_uid, 3)
    print(f"Select persona result: {result}")
    selected = manager.get_selected_persona(user1_uid)
    if selected:
        print(f"Selected persona: {selected.persona}\n---\n{selected.content[:50]}...")
    else:
        print("No persona selected.")

    personas = manager.list_personas(user1_uid)
    print("User1 can see: ")
    for persona in personas:
        print(persona)

    user2_uid = 511412168386674691
    user2_personas = manager.list_personas(user2_uid)
    print("User2 can see: ")
    for persona in user2_personas:
        print(persona)

    user_uid = 123456789
    manager.create_discord_user(user_uid)

    user = manager.get_discord_user(user_uid)
    if user:
        print(f"Retrieved user: {user}")

    manager.update_discord_user(user_uid, balance=100)
    updated_user = manager.get_discord_user(user_uid)
    if updated_user:
        print(f"Updated user balance: {updated_user.balance}")