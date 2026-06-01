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

    def __str__(self):
        return self.name

@dataclass
class Persona:
    uid: int
    persona_name: str
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
        return f"Persona(uid={self.uid:3d}, persona={self.persona_name}, owner_uid={self.owner_uid}, visibility={self.visibility.name})"


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

@dataclass
class ChatInteraction:
    msg_uid: int #PK
    user_uid: int #FK
    persona_uid: int #FK
    created_at: str
    is_memorized: bool = False
    main_content: str = ""
    summary: Optional[str] = None
    
@dataclass
class PersonaMemories:
    memory_uid: int #PK
    memory_content: str
    persona_uid: int #FK
    source_msg_uids: str # comma-separated list of msg_uids that contributed to this memory
    created_at: str
    updated_at: str

@dataclass
class UserGroups:
    group_uid: int #PK
    group_name: str
    member_uids: str # comma-separated list of user_uids in this group

@dataclass
class PersonaGroupAccess:
    group_uid: int #PK
    persona_uid: int #FK


def _split_uid_list(value: str) -> List[int]:
    if not value:
        return []
    return [int(item) for item in value.split(",") if item.strip()]


def _join_uid_list(values: List[int]) -> str:
    return ",".join(str(value) for value in values)

def _chat_interaction_from_row(row: tuple) -> ChatInteraction:
    return ChatInteraction(
        msg_uid=row[0],
        user_uid=row[1],
        persona_uid=row[2],
        created_at=row[3],
        is_memorized=bool(row[4]),
        main_content=row[5],
        summary=row[6],
    )


def _persona_memory_from_row(row: tuple) -> PersonaMemories:
    return PersonaMemories(
        memory_uid=row[0],
        memory_content=row[1],
        persona_uid=row[2],
        source_msg_uids=row[3],
        created_at=row[4],
        updated_at=row[5],
    )


def _user_group_from_row(row: tuple) -> UserGroups:
    return UserGroups(
        group_uid=row[0],
        group_name=row[1],
        member_uids=row[2],
    )


def _persona_group_access_from_row(row: tuple) -> PersonaGroupAccess:
    return PersonaGroupAccess(
        group_uid=row[0],
        persona_uid=row[1],
    )

def _persona_from_row(row: tuple) -> Persona:
    return Persona(
        uid=row[0],
        persona_name=row[1],
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
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    @contextmanager
    def connection(self):
        yield self._conn

class PersonaRepository(SQLiteRepository):
    allowed_update_fields = {"persona_name", "content", "visibility", "last_interaction_recv_at", "interaction_count"}

    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS personas (
                uid INTEGER PRIMARY KEY AUTOINCREMENT,
                persona_name TEXT NOT NULL,
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

    def rename_legacy_persona_column(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(personas)")
        columns = {row[1] for row in cursor.fetchall()}

        if "persona" in columns and "persona_name" not in columns:
            conn.execute("ALTER TABLE personas RENAME COLUMN persona TO persona_name")

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
                INSERT INTO personas (persona_name, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at)
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
                SELECT uid, persona_name, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
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
                SELECT uid, persona_name, content, owner_uid, visibility, created_at, updated_at, last_interaction_recv_at, interaction_count
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
                SELECT p.uid, p.persona_name, upi.interaction_count
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


class ChatInteractionRepository(SQLiteRepository):
    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_interactions (
                msg_uid INTEGER PRIMARY KEY,
                user_uid INTEGER NOT NULL,
                persona_uid INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                is_memorized INTEGER NOT NULL DEFAULT 0 CHECK(is_memorized IN (0, 1)),
                main_content TEXT NOT NULL DEFAULT '',
                summary TEXT DEFAULT NULL,
                FOREIGN KEY (user_uid) REFERENCES discord_users (user_uid),
                FOREIGN KEY (persona_uid) REFERENCES personas (uid)
            )
            """
        )

    def create(
        self,
        msg_uid: int,
        user_uid: int,
        persona_uid: int,
        main_content: str,
        created_at: Optional[str] = None,
        is_memorized: bool = False,
        summary: Optional[str] = None,
    ) -> bool:
        created_at = created_at or _now_iso()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_interactions (
                    msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg_uid,
                    user_uid,
                    persona_uid,
                    created_at,
                    int(is_memorized),
                    main_content,
                    summary,
                ),
            )
            return cursor.rowcount > 0

    def fetch_by_msg_uid(self, msg_uid: int) -> Optional[ChatInteraction]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary
                FROM chat_interactions
                WHERE msg_uid = ?
                """,
                (msg_uid,),
            )
            row = cursor.fetchone()
            return _chat_interaction_from_row(row) if row else None

    def list_by_persona_uid(self, persona_uid: int, limit: Optional[int] = None) -> List[ChatInteraction]:
        query = """
            SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary
            FROM chat_interactions
            WHERE persona_uid = ?
            ORDER BY created_at DESC
        """
        params: List[Any] = [persona_uid]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return [_chat_interaction_from_row(row) for row in cursor.fetchall()]

    def list_by_user_uid(self, user_uid: int, limit: Optional[int] = None) -> List[ChatInteraction]:
        query = """
            SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary
            FROM chat_interactions
            WHERE user_uid = ?
            ORDER BY created_at DESC
        """
        params: List[Any] = [user_uid]
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return [_chat_interaction_from_row(row) for row in cursor.fetchall()]

    def update(self, msg_uid: int, **updates) -> bool:
        if not updates:
            return False

        allowed_fields = {"user_uid", "persona_uid", "created_at", "is_memorized", "main_content", "summary"}
        invalid_fields = set(updates) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Unsupported chat interaction update fields: {sorted(invalid_fields)}")

        normalized_updates = {
            key: int(value) if key == "is_memorized" and isinstance(value, bool) else value
            for key, value in updates.items()
        }
        set_clause = ", ".join([f"{key} = ?" for key in normalized_updates.keys()])
        query = f"""
            UPDATE chat_interactions
            SET {set_clause}
            WHERE msg_uid = ?
        """

        with self.connection() as conn:
            cursor = conn.execute(query, list(normalized_updates.values()) + [msg_uid])
            return cursor.rowcount > 0

    def mark_memorized(self, msg_uid: int, summary: Optional[str] = None) -> bool:
        updates: Dict[str, Any] = {"is_memorized": 1}
        if summary is not None:
            updates["summary"] = summary
        return self.update(msg_uid, **updates)

    def delete(self, msg_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM chat_interactions
                WHERE msg_uid = ?
                """,
                (msg_uid,),
            )
            return cursor.rowcount > 0


class PersonaMemoriesRepository(SQLiteRepository):
    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS persona_memories (
                memory_uid INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_content TEXT NOT NULL,
                persona_uid INTEGER NOT NULL,
                source_msg_uids TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (persona_uid) REFERENCES personas (uid)
            )
            """
        )

    def create(
        self,
        memory_content: str,
        persona_uid: int,
        source_msg_uids: str,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> int:
        now = _now_iso()
        created_at = created_at or now
        updated_at = updated_at or now
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO persona_memories (
                    memory_content, persona_uid, source_msg_uids, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_content, persona_uid, source_msg_uids, created_at, updated_at),
            )
            memory_uid = cursor.lastrowid
            if not memory_uid:
                raise ValueError("Failed to retrieve the memory uid after insertion.")
            return memory_uid

    def fetch_by_uid(self, memory_uid: int) -> Optional[PersonaMemories]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT memory_uid, memory_content, persona_uid, source_msg_uids, created_at, updated_at
                FROM persona_memories
                WHERE memory_uid = ?
                """,
                (memory_uid,),
            )
            row = cursor.fetchone()
            return _persona_memory_from_row(row) if row else None

    def list_by_persona_uid(self, persona_uid: int) -> List[PersonaMemories]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT memory_uid, memory_content, persona_uid, source_msg_uids, created_at, updated_at
                FROM persona_memories
                WHERE persona_uid = ?
                ORDER BY updated_at DESC
                """,
                (persona_uid,),
            )
            return [_persona_memory_from_row(row) for row in cursor.fetchall()]

    def update(self, memory_uid: int, **updates) -> bool:
        if not updates:
            return False

        allowed_fields = {"memory_content", "persona_uid", "source_msg_uids"}
        invalid_fields = set(updates) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Unsupported persona memory update fields: {sorted(invalid_fields)}")

        normalized_updates = dict(updates)
        normalized_updates["updated_at"] = _now_iso()

        set_clause = ", ".join([f"{key} = ?" for key in normalized_updates.keys()])
        query = f"""
            UPDATE persona_memories
            SET {set_clause}
            WHERE memory_uid = ?
        """

        with self.connection() as conn:
            cursor = conn.execute(query, list(normalized_updates.values()) + [memory_uid])
            return cursor.rowcount > 0

    def delete(self, memory_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM persona_memories
                WHERE memory_uid = ?
                """,
                (memory_uid,),
            )
            return cursor.rowcount > 0


class UserGroupsRepository(SQLiteRepository):
    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_groups (
                group_uid INTEGER PRIMARY KEY AUTOINCREMENT,
                group_name TEXT NOT NULL,
                member_uids TEXT NOT NULL DEFAULT ''
            )
            """
        )

    def create(self, group_name: str, member_uids: Optional[List[int]] = None) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO user_groups (group_name, member_uids)
                VALUES (?, ?)
                """,
                (group_name, _join_uid_list(member_uids or [])),
            )
            group_uid = cursor.lastrowid
            if not group_uid:
                raise ValueError("Failed to retrieve the group uid after insertion.")
            return group_uid

    def fetch_by_uid(self, group_uid: int) -> Optional[UserGroups]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT group_uid, group_name, member_uids
                FROM user_groups
                WHERE group_uid = ?
                """,
                (group_uid,),
            )
            row = cursor.fetchone()
            return _user_group_from_row(row) if row else None

    def list_all(self) -> List[UserGroups]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT group_uid, group_name, member_uids
                FROM user_groups
                ORDER BY group_uid ASC
                """
            )
            return [_user_group_from_row(row) for row in cursor.fetchall()]

    def update(self, group_uid: int, **updates) -> bool:
        if not updates:
            return False

        allowed_fields = {"group_name", "member_uids"}
        invalid_fields = set(updates) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Unsupported user group update fields: {sorted(invalid_fields)}")

        normalized_updates = dict(updates)
        if "member_uids" in normalized_updates and isinstance(normalized_updates["member_uids"], list):
            normalized_updates["member_uids"] = _join_uid_list(normalized_updates["member_uids"])

        set_clause = ", ".join([f"{key} = ?" for key in normalized_updates.keys()])
        query = f"""
            UPDATE user_groups
            SET {set_clause}
            WHERE group_uid = ?
        """

        with self.connection() as conn:
            cursor = conn.execute(query, list(normalized_updates.values()) + [group_uid])
            return cursor.rowcount > 0

    def delete(self, group_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM user_groups
                WHERE group_uid = ?
                """,
                (group_uid,),
            )
            return cursor.rowcount > 0

    def get_member_uids(self, group_uid: int) -> List[int]:
        group = self.fetch_by_uid(group_uid)
        if not group:
            return []
        return _split_uid_list(group.member_uids)

    def add_member(self, group_uid: int, user_uid: int) -> bool:
        group = self.fetch_by_uid(group_uid)
        if not group:
            return False

        member_uids = _split_uid_list(group.member_uids)
        if user_uid in member_uids:
            return True

        member_uids.append(user_uid)
        return self.update(group_uid, member_uids=member_uids)

    def remove_member(self, group_uid: int, user_uid: int) -> bool:
        group = self.fetch_by_uid(group_uid)
        if not group:
            return False

        member_uids = [member_uid for member_uid in _split_uid_list(group.member_uids) if member_uid != user_uid]
        return self.update(group_uid, member_uids=member_uids)

    def is_member(self, group_uid: int, user_uid: int) -> bool:
        return user_uid in self.get_member_uids(group_uid)


class PersonaGroupAccessRepository(SQLiteRepository):
    def create_tables(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS persona_group_access (
                group_uid INTEGER NOT NULL,
                persona_uid INTEGER NOT NULL,
                PRIMARY KEY (group_uid, persona_uid),
                FOREIGN KEY (group_uid) REFERENCES user_groups (group_uid),
                FOREIGN KEY (persona_uid) REFERENCES personas (uid)
            )
            """
        )

    def grant_access(self, group_uid: int, persona_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO persona_group_access (group_uid, persona_uid)
                VALUES (?, ?)
                """,
                (group_uid, persona_uid),
            )
            return cursor.rowcount > 0

    def revoke_access(self, group_uid: int, persona_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                DELETE FROM persona_group_access
                WHERE group_uid = ? AND persona_uid = ?
                """,
                (group_uid, persona_uid),
            )
            return cursor.rowcount > 0

    def list_access_by_group(self, group_uid: int) -> List[PersonaGroupAccess]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT group_uid, persona_uid
                FROM persona_group_access
                WHERE group_uid = ?
                ORDER BY persona_uid ASC
                """,
                (group_uid,),
            )
            return [_persona_group_access_from_row(row) for row in cursor.fetchall()]

    def list_access_by_persona(self, persona_uid: int) -> List[PersonaGroupAccess]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT group_uid, persona_uid
                FROM persona_group_access
                WHERE persona_uid = ?
                ORDER BY group_uid ASC
                """,
                (persona_uid,),
            )
            return [_persona_group_access_from_row(row) for row in cursor.fetchall()]

    def has_access(self, group_uid: int, persona_uid: int) -> bool:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT 1
                FROM persona_group_access
                WHERE group_uid = ? AND persona_uid = ?
                LIMIT 1
                """,
                (group_uid, persona_uid),
            )
            return cursor.fetchone() is not None

    def list_persona_uids_for_group(self, group_uid: int) -> List[int]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT persona_uid
                FROM persona_group_access
                WHERE group_uid = ?
                ORDER BY persona_uid ASC
                """,
                (group_uid,),
            )
            return [row[0] for row in cursor.fetchall()]

    def list_group_uids_for_persona(self, persona_uid: int) -> List[int]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT group_uid
                FROM persona_group_access
                WHERE persona_uid = ?
                ORDER BY group_uid ASC
                """,
                (persona_uid,),
            )
            return [row[0] for row in cursor.fetchall()]


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
        self.user_groups = UserGroupsRepository(self._conn)
        self.persona_group_access = PersonaGroupAccessRepository(self._conn)

        self._init_db()

    def _init_db(self):
        self.personas.create_tables(self._conn)
        self.personas.rename_legacy_persona_column(self._conn)
        self.users.create_tables(self._conn)
        self.interactions.create_tables(self._conn)
        self.chat_interactions.create_tables(self._conn)
        self.persona_memories.create_tables(self._conn)
        self.user_groups.create_tables(self._conn)
        self.persona_group_access.create_tables(self._conn)

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

    def create_user_group(self, group_name: str, member_uids: Optional[List[int]] = None) -> int:
        """Create a user group."""
        return self.user_groups.create(group_name, member_uids=member_uids)

    def get_user_group(self, group_uid: int) -> Optional[UserGroups]:
        """Get a user group by uid."""
        return self.user_groups.fetch_by_uid(group_uid)

    def list_user_groups(self) -> List[UserGroups]:
        """List all user groups."""
        return self.user_groups.list_all()

    def update_user_group(self, group_uid: int, **updates) -> bool:
        """Update a user group."""
        return self.user_groups.update(group_uid, **updates)

    def delete_user_group(self, group_uid: int) -> bool:
        """Delete a user group."""
        return self.user_groups.delete(group_uid)

    def add_user_to_group(self, group_uid: int, user_uid: int) -> bool:
        """Add a user to a group."""
        return self.user_groups.add_member(group_uid, user_uid)

    def remove_user_from_group(self, group_uid: int, user_uid: int) -> bool:
        """Remove a user from a group."""
        return self.user_groups.remove_member(group_uid, user_uid)

    def is_user_in_group(self, group_uid: int, user_uid: int) -> bool:
        """Check whether a user belongs to a group."""
        return self.user_groups.is_member(group_uid, user_uid)

    def grant_persona_group_access(self, group_uid: int, persona_uid: int) -> bool:
        """Grant a group access to a persona."""
        return self.persona_group_access.grant_access(group_uid, persona_uid)

    def revoke_persona_group_access(self, group_uid: int, persona_uid: int) -> bool:
        """Revoke a group's access to a persona."""
        return self.persona_group_access.revoke_access(group_uid, persona_uid)

    def list_group_persona_access(self, group_uid: int) -> List[PersonaGroupAccess]:
        """List persona access grants for a group."""
        return self.persona_group_access.list_access_by_group(group_uid)

    def list_persona_group_access(self, persona_uid: int) -> List[PersonaGroupAccess]:
        """List group access grants for a persona."""
        return self.persona_group_access.list_access_by_persona(persona_uid)

    def user_can_access_persona_via_group(self, user_uid: int, persona_uid: int) -> bool:
        """Check whether a user can access a persona through any group membership."""
        group_uids = self.persona_group_access.list_group_uids_for_persona(persona_uid)
        for group_uid in group_uids:
            if self.user_groups.is_member(group_uid, user_uid):
                return True
        return False

    def list_personas_accessible_via_group(self, user_uid: int) -> List[Persona]:
        """List personas a user can access through group membership."""
        accessible_persona_uids = set()
        for group in self.user_groups.list_all():
            if not self.user_groups.is_member(group.group_uid, user_uid):
                continue
            accessible_persona_uids.update(self.persona_group_access.list_persona_uids_for_group(group.group_uid))

        personas: List[Persona] = []
        for persona_uid in sorted(accessible_persona_uids):
            persona = self.personas.fetch_by_uid(persona_uid)
            if persona:
                personas.append(persona)
        return personas

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