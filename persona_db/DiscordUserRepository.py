from typing import List, Optional
from persona_db.DatabaseModels import DiscordUser
from persona_db.helper_func import SQLiteRepository

def _discord_user_from_row(row: tuple) -> DiscordUser:
    return DiscordUser(
        user_uid=row[0],
        selected_persona_uid=row[1],
        last_interaction_send_at=row[2],
        interaction_count=row[3],
        last_payout_at=row[4],
        balance=row[5],
    )

class DiscordUserRepository(SQLiteRepository):
    allowed_update_fields = {
        "selected_persona_uid",
        "last_interaction_send_at",
        "interaction_count",
        "last_payout_at",
        "balance",
        "preferred_name",
    }

    def create_tables(self, conn) -> None:
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

    def deselect_persona(self, user_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE discord_users
                SET selected_persona_uid = -1
                WHERE user_uid = ?
                """,
                (user_uid,),
            )

    def _unbind_selected_user_for_persona(self, persona_uid: int) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                UPDATE discord_users
                SET selected_persona_uid = -1
                WHERE selected_persona_uid = ?
                """,
                (persona_uid,),
            )
