
from persona_db.DatabaseModels import ChatInteraction
from persona_db.helper_func import SQLiteRepository, _now_iso
from typing import List, Optional, Any, Dict

def _chat_interaction_from_row(row: tuple) -> ChatInteraction:
    return ChatInteraction(
        msg_uid=row[0],
        user_uid=row[1],
        persona_uid=row[2],
        user_prompt=row[7],
        main_content=row[5],
        summary=row[6],
        created_at=row[3],
        is_memorized=bool(row[4]),
    )

class ChatInteractionRepository(SQLiteRepository):
    def create_tables(self, conn) -> None:
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
                user_prompt TEXT DEFAULT NULL,
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
        summary: Optional[str] = None,
        user_prompt: Optional[str] = None,
    ) -> bool:
        _now = _now_iso()
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO chat_interactions (
                    msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary, user_prompt
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    msg_uid,
                    user_uid,
                    persona_uid,
                    _now,
                    0,
                    main_content,
                    summary,
                    user_prompt,
                ),
            )
            return cursor.rowcount > 0

    def fetch_by_msg_uid(self, msg_uid: int) -> Optional[ChatInteraction]:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary, user_prompt
                FROM chat_interactions
                WHERE msg_uid = ?
                """,
                (msg_uid,),
            )
            row = cursor.fetchone()
            return _chat_interaction_from_row(row) if row else None

    def list_by_persona_uid(self, persona_uid: int, limit: Optional[int] = None) -> List[ChatInteraction]:
        query = """
            SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary, user_prompt
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
            SELECT msg_uid, user_uid, persona_uid, created_at, is_memorized, main_content, summary, user_prompt
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

        allowed_fields = {"user_uid", "persona_uid", "created_at", "is_memorized", "main_content", "summary", "user_prompt"}
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