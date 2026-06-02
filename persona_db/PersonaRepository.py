
from enum import Enum
import json
from persona_db.DatabaseModels import Persona, PersonaVisibility
from persona_db.helper_func import _now_iso, SQLiteRepository, _join_uid_list, _split_uid_list
from typing import List, Optional, Set

def _persona_from_row(row: tuple) -> Persona:
    return Persona(
        uid=row[0],
        persona_name=row[1],
        content=row[2],
        owner_uid=row[3],
        # visibility=PersonaVisibility(row[4]),
        is_public=bool(row[4]),
        allowed_role_ids=set(_split_uid_list(row[5])) if row[5] else set(),
        created_at=row[6],
        updated_at=row[7],
        last_interaction_recv_at=row[8],
        interaction_count=row[9],
    )

class PersonaRepository(SQLiteRepository):
    allowed_everyone_update_fields = {"last_interaction_recv_at"}
    allowed_owner_update_fields = {"persona_name", "content", "visibility", "is_public", "allowed_role_ids"} | allowed_everyone_update_fields
    allowed_teammember_update_fields = {"persona_name", "content"} | allowed_everyone_update_fields
    
    
    def create_tables(self, conn) -> None:
        conn.execute(
            # """
            # CREATE TABLE IF NOT EXISTS personas (
            #     uid INTEGER PRIMARY KEY AUTOINCREMENT,
            #     persona_name TEXT NOT NULL,
            #     content TEXT NOT NULL,
            #     owner_uid INTEGER NOT NULL,
            #     visibility INTEGER NOT NULL CHECK(visibility IN (0, 1)),
            #     created_at TEXT NOT NULL,
            #     updated_at TEXT NOT NULL,
            #     last_interaction_recv_at TEXT NOT NULL,
            #     interaction_count INTEGER DEFAULT 0,
            #     FOREIGN KEY (owner_uid) REFERENCES discord_users (user_uid)
            # )
            # """
            """
            CREATE TABLE IF NOT EXISTS personas (
                uid INTEGER PRIMARY KEY AUTOINCREMENT,
                persona_name TEXT NOT NULL,
                content TEXT NOT NULL,
                owner_uid INTEGER NOT NULL,
                is_public INTEGER NOT NULL CHECK(is_public IN (0, 1)),
                allowed_role_ids TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_interaction_recv_at TEXT NOT NULL,
                interaction_count INTEGER DEFAULT 0,
                FOREIGN KEY (owner_uid) REFERENCES discord_users (user_uid)
            )
            """
        )

    def rename_legacy_persona_column(self, conn) -> None:
        cursor = conn.execute("PRAGMA table_info(personas)")
        columns = {row[1] for row in cursor.fetchall()}

        if "persona" in columns and "persona_name" not in columns:
            conn.execute("ALTER TABLE personas RENAME COLUMN persona TO persona_name")

    def add_is_public_column(self, conn) -> None:
        cursor = conn.execute("PRAGMA table_info(personas)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Only migrate if old 'visibility' exists and new 'is_public' doesn't
        if "visibility" in columns and "is_public" not in columns:
            print(f"Existing columns in personas table before migration: {columns}")
            conn.execute("ALTER TABLE personas ADD COLUMN is_public INTEGER NOT NULL CHECK(visibility IN (0, 1)) DEFAULT 0")
            conn.execute("ALTER TABLE personas ADD COLUMN allowed_role_ids TEXT DEFAULT '[]'")
            conn.execute("UPDATE personas SET is_public = 1 WHERE visibility = 1")
            
            cursor = conn.execute("PRAGMA table_info(personas)")
            columns = {row[1] for row in cursor.fetchall()}
            print(f"Existing columns in personas table after migration: {columns}")
        
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

    def create(self, persona: str, content: str, owner_uid: int, is_public: bool | PersonaVisibility, allowed_role_ids: Set[int] = set()) -> int:
        now = _now_iso()
        is_public_value = is_public.value if isinstance(is_public, PersonaVisibility) else int(is_public)
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO personas (persona_name, content, owner_uid, is_public, allowed_role_ids, created_at, updated_at, last_interaction_recv_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (persona, content, owner_uid, is_public_value, _join_uid_list(allowed_role_ids), now, now, now),
            )
            persona_uid = cursor.lastrowid
            if not persona_uid:
                raise ValueError("Failed to retrieve the persona uid after insertion.")
            return persona_uid

    def fetch_by_uid(self, persona_uid: int) -> Optional[Persona]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT uid, persona_name, content, owner_uid, is_public, allowed_role_ids, created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas
                WHERE uid = ?
                """,
                (persona_uid,),
            )
            row = cursor.fetchone()
            return _persona_from_row(row) if row else None

    def list_visible_for_user(self, user_uid: int, user_role_ids: List[int]) -> List[Persona]:
        with self.connection() as conn:
            cursor = conn.execute("""
                SELECT uid, persona_name, content, owner_uid, is_public, allowed_role_ids,
                    created_at, updated_at, last_interaction_recv_at, interaction_count
                FROM personas
                ORDER BY updated_at DESC
            """)
            rows = cursor.fetchall()

        visible = []
        for row in rows:
            # Unpack row (adapt to your _persona_from_row)
            is_public = row[4]
            owner = row[3]
            allowed_roles = json.loads(row[5]) if row[5] else []

            if is_public:
                visible.append(_persona_from_row(row))
            elif owner == user_uid:
                visible.append(_persona_from_row(row))
            elif any(role_id in allowed_roles for role_id in user_role_ids):
                visible.append(_persona_from_row(row))
        return visible
    
    def get_allowed_fields_for_user(self, persona_uid: int, user_uid: int, user_role_ids: Set[int] = set()) -> Set[str]:
        persona = self.fetch_by_uid(persona_uid)
        if not persona:
            raise ValueError(f"Persona with uid {persona_uid} not found.")

        if persona.owner_uid == user_uid:
            return self.allowed_owner_update_fields
        elif any(role_id in persona.allowed_role_ids for role_id in user_role_ids):
            return self.allowed_teammember_update_fields
        else:
            return self.allowed_everyone_update_fields
        
    def update(self, persona_uid: int, allowed_fields: Set[str], **updates) -> bool:
        if not updates:
            return False

        invalid_fields = set(updates) - allowed_fields
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
            WHERE uid = ?
        """

        with self.connection() as conn:
            cursor = conn.execute(query, list(normalized_updates.values()) + [persona_uid])
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