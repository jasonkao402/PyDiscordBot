
from enum import Enum
from persona_db.DatabaseModels import Persona, PersonaVisibility
from persona_db.helper_func import _now_iso, SQLiteRepository
from typing import List, Optional

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

class PersonaRepository(SQLiteRepository):
    allowed_update_fields = {"persona_name", "content", "visibility", "last_interaction_recv_at", "interaction_count"}

    def create_tables(self, conn) -> None:
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

    def rename_legacy_persona_column(self, conn) -> None:
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