# jev_scoring.py
from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, Score

from config_loader import config_toml
from helper_func.chat_context_manager import ChatContextManager

if TYPE_CHECKING:
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
        jev_model = config_toml["llm_model"].get("model_jev_local", "")
        jev_url = config_toml["api_token"]["jev"].get("url", "")
        jev_key = config_toml["api_token"]["jev"].get("keys", "")[0]
        self.client = AsyncTypeSafeClient(api_key=jev_key, model=jev_model, base_url=jev_url)

    def get_user_chat(self, user_id: int) -> list[ChatInteraction]:
        """Get the chat history for a specific user"""
        return self.db.list_chat_interactions_for_user(user_id)

    async def gate_message(self, recent_context: list[str], persona_name: str, subject_name: str) -> dict:
        result = {}
        response = await self.client.system_one(
            state={"AI companion": persona_name, "user": subject_name, "recent_context": recent_context[-3:]},
            questions={
                "memorable": Noul(
                    instructions=f"From {persona_name}'s perspective, is this message a non-repeatable, memory-worthy fact about {subject_name} or the ongoing topic?"
                    "Ignore small talk, spam-like content, repetition and perishable information."
                ),
                "type": Choice(
                    instructions="What type of information is this message?",
                    criteria={
                        "rules": "A guideline or instruction to follow",
                        "correction": "A correction or clarification of previous information",
                        "fact": "A verifiable piece of objective information",
                        "opinion": "A subjective statement or personal belief",
                    },
                ),
                "decision_impact": Score(
                    instructions=f"From {persona_name}'s perspective, if this knowledge did not exist, "
                    "how likely is a different or incorrect decision to be made in a future interaction?",
                    criteria=[
                        "No impact — generic knowledge the LLM already has",
                        "Minor — slightly better phrasing only",
                        "Moderate — would get a preference or detail wrong",
                        "High — would give a factually wrong answer about this person",
                    ],
                ),
            },
        )
        result["memorable"] = response.nouls["memorable"].noul
        result["type"] = response.choices["type"].choice
        result["decision_impact"] = response.scores["decision_impact"].score
        return result

async def jev_scoring(subject_name: str):
    for i, interaction in enumerate(chat_history[:10]):
        persona = cog.db.get_persona_no_check(interaction.persona_uid)
        assert persona is not None, f"Persona with UID {interaction.persona_uid} not found."
        # print(f"{i + 1}. [{interaction.created_at}]\n{interaction.user_prompt}\n->\n{interaction.main_content}")
        gate_result = await cog.gate_message(
            recent_context=[interaction.main_content for interaction in chat_history[max(0, i - 3):i]],  # Get the last 3 messages before the current one
            persona_name=persona.persona_name,
            subject_name=subject_name,
        )
        print(f"{i + 1}. [{interaction.created_at}]\n{interaction.user_prompt}\n->\n{interaction.main_content}\n")
        print(f"Scoring result: {gate_result}\n{'-' * 40}\n")


if __name__ == "__main__":
    cog = JevAPI()
    user_id = config_toml["auth"]["admin_list"][0]
    user_profile = cog.db.get_discord_user(user_id)
    chat_history = cog.get_user_chat(user_id)  # Get the last 10 chat interactions
    print("length of chat history:", len(chat_history))

    print(f"Chat history for user {user_id}:\n")
    try:
        asyncio.run(jev_scoring(subject_name=user_profile.preferred_name or "Test User"))
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")
    finally:
        print("Application shutdown complete.")