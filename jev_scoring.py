# jev_scoring.py
from __future__ import annotations

import asyncio
import pathlib
from typing import TYPE_CHECKING

from tqdm import tqdm
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

provider_jev = config_toml["llm_model"].get("provider_jev", "local_jev")  # Default to "local_jev" if not specified
class JevAPI:
    def __init__(self) -> None:
        self.state = ChatContextManager()
        self.db = self.state.db
        jev_model = config_toml["llm_model"].get("model_jev", "")
        jev_url = config_toml["api_token"][provider_jev].get("url", "")
        jev_key = config_toml["api_token"][provider_jev].get("keys", "")[0]
        self.client = AsyncTypeSafeClient(api_key=jev_key, model=jev_model, base_url=jev_url)

    def get_user_chat(self, user_id: int) -> list[ChatInteraction]:
        """Get the chat history for a specific user"""
        return self.db.list_chat_interactions_for_user(user_id)

    async def gate_message(self, recent_context: str, persona_name: str, subject_name: str) -> dict:
        result = {}
        response = await self.client.system_one(
            state={"AI companion": persona_name, "user": subject_name, "user_context": recent_context},
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
                        "opinion": "A strong subjective statement, personal belief or preference",
                        "casual": "A casual or off-topic remark, not relevant to the main discussion",
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

def chat_formatting(interaction: ChatInteraction, subject_name: str, persona_name: str, persona_content: str) -> str:
    """Format a chat interaction for jev scoring."""
    return (
        f"{subject_name}: {interaction.user_prompt}\n"
        f"{persona_name}: {interaction.main_content}\n"
    )

async def jev_scoring(subject_name: str, start_index: int = 0, end_index: int = 300) -> tuple[list[str], list[str]]:
    logging_full, logging_jev = [], []
    pname_cache = {}
    pcontent_cache = {}
    i = start_index
    for interaction in tqdm(chat_history[start_index:end_index]):
        if interaction.persona_uid not in pname_cache:
            persona = cog.db.get_persona_no_check(interaction.persona_uid)
            assert persona is not None, f"Persona with UID {interaction.persona_uid} not found."
            pname_cache[interaction.persona_uid] = persona.persona_name
            pcontent_cache[interaction.persona_uid] = persona.content
        persona_name = pname_cache[interaction.persona_uid]
        persona_content = pcontent_cache[interaction.persona_uid]
        formatted = chat_formatting(interaction, subject_name, persona_name, persona_content)
        gate_result = await cog.gate_message(
            recent_context=formatted,
            persona_name=persona_name,
            subject_name=subject_name,
        )
        i += 1
        story_str = f"{i:03d}. [{interaction.created_at}]\n{formatted}\n"
        result_str = f"Scoring result: {gate_result}\n{'-' * 40}\n"
        full = story_str + result_str
        print(full)
        logging_full.append(full)
        logging_jev.append(f"{i:03d}. {gate_result}")
    return logging_full, logging_jev


if __name__ == "__main__":
    cog = JevAPI()
    user_id = config_toml["auth"]["admin_list"][0]
    user_profile = cog.db.get_discord_user(user_id)
    assert user_profile is not None, f"User with ID {user_id} not found."
    chat_history = cog.get_user_chat(user_id)  # Get the last 10 chat interactions
    print("length of chat history:", len(chat_history))

    print(f"Chat history for user {user_id}:\n")
    try:
        start_index = 000
        end_index = 100
        log_full, log_jev = asyncio.run(jev_scoring(subject_name=user_profile.preferred_name or "Test User", start_index=start_index, end_index=end_index))
        pathlib.Path(f"scoring_log_{start_index:03d}_{end_index:03d}.txt").write_text("\n".join(log_full), encoding="utf-8")
        pathlib.Path(f"scoring_jev_{start_index:03d}_{end_index:03d}.txt").write_text("\n".join(log_jev), encoding="utf-8")
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")
    finally:
        print("Shutdown complete.")
