from persona_db.DatabaseModels import PersonaMemories
from typing import List, Optional
from persona_db.helper_func import SQLiteRepository, _now_iso, _join_uid_list, _split_uid_list

def _persona_memory_from_row(row: tuple) -> PersonaMemories:
    return PersonaMemories(
        memory_uid=row[0],
        memory_content=row[1],
        persona_uid=row[2],
        source_msg_uids=_split_uid_list(row[3]),
        created_at=row[4],
        updated_at=row[5],
    )

class PersonaMemoriesRepository(SQLiteRepository):
    def create_tables(self, conn) -> None:
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
        source_msg_uids: List[int],
    ) -> int:
        _now = _now_iso()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO persona_memories (
                    memory_content, persona_uid, source_msg_uids, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_content, persona_uid, _join_uid_list(source_msg_uids), _now, _now),
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