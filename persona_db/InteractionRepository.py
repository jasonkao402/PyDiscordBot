from typing import List, Optional, Dict, Any
from persona_db.helper_func import _now_iso, SQLiteRepository

class InteractionRepository(SQLiteRepository):
    def create_tables(self, conn) -> None:
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