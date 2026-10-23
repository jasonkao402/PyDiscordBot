# jev_scoring.py
from __future__ import annotations

from typing import TYPE_CHECKING

from typesafe_sdk import AsyncTypeSafeClient, Noul, Score

from config_loader import configToml
from helper_func.chat_context_manager import ChatContextManager

if TYPE_CHECKING:
    # from helper_func.llmAgentAPI import LLMAPI
    from persona_db.PersonaDatabase import ChatInteraction

# for reference
# class ChatInteraction(
#     msg_uid: int,
#     user_uid: int,
#     persona_uid: int,
#     created_at: str = _now_iso(),
#     is_memorized: bool = False,
#     main_content: str = "",
#     summary: str = "",
#     user_prompt: str = "",
#     user_internal_name: str | None = None
# )
# CREATE TABLE IF NOT EXISTS chat_interactions (
#     msg_uid INTEGER PRIMARY KEY,
#     user_uid INTEGER NOT NULL,
#     persona_uid INTEGER NOT NULL,
#     created_at TEXT NOT NULL,
#     is_memorized INTEGER NOT NULL DEFAULT 0 CHECK(is_memorized IN (0, 1)),
#     main_content TEXT NOT NULL DEFAULT '',
#     summary TEXT DEFAULT NULL,
#     user_prompt TEXT DEFAULT NULL,
#     FOREIGN KEY (user_uid) REFERENCES discord_users (user_uid),
#     FOREIGN KEY (persona_uid) REFERENCES personas (uid)
# )


class JevAPI:
    def __init__(self) -> None:
        self.state = ChatContextManager()
        self.db = self.state.db
        # self.llm_api: LLMAPI = self.state.llm_api
        jev_url = configToml["api_token"].get("url", "")
        jev_model = configToml["llm_model"].get("model_jev", "")
        jev_key = configToml["api_token"].get("key", "")
        self.client = AsyncTypeSafeClient(api_key=jev_key, model=jev_model, base_url=jev_url)

    def get_user_chat(self, user_id: int) -> list[ChatInteraction]:
        """Get the chat history for a specific user"""
        return self.db.get_discord_user_chat_history(user_id)

    async def gate_message(
        self,
        message: str,
        recent_context: list[str],
        persona_name: str,
        subject_name: str,
    ) -> dict:
        result = {}
        response = await self.client.system_one(
            state={
                "persona": persona_name,
                "speaker": subject_name,
                "recent_context": recent_context[-3:],
                "message": message,
            },
            questions={
                "memorable": Noul(
                    instructions="Is this message a non-repeatable, memory-worthy fact "
                    "about the speaker or the ongoing topic? "
                    "Ignore small talk, emoji-only, repetition, and "
                    "information already present in recent_context."
                ),
                "decision_impact": Score(
                    instructions="If this knowledge did not exist, how likely is the agent "
                    "to make a different or incorrect decision in a future interaction?",
                    criteria=[
                        "No impact — generic knowledge the LLM already has",
                        "Minor — slightly better phrasing only",
                        "Moderate — would get a preference or detail wrong",
                        "High — would give a factually wrong answer about this person",
                    ],
                ),
            }
        )
        result["memorable"] = response.nouls["memorable"].noul
        result["decision_impact"] = response.scores["decision_impact"].score
        return result


if __name__ == "__main__":
    cog = JevAPI()
    user_id = configToml["auth"]["admin_list"][0]
    chat_history = cog.get_user_chat(user_id)  # Get the last 10 chat interactions
    print("length of chat history:", len(chat_history))

    print(f"Chat history for user {user_id}:\n")
    for i, interaction in enumerate(chat_history[:10]):
        print(
            f"{i + 1}. [{interaction.created_at}]\n{interaction.user_prompt}\n->\n{interaction.main_content}"
        )
