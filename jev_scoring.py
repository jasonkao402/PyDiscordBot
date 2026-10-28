# jev_scoring.py
from __future__ import annotations

import asyncio
import pathlib

from tqdm import tqdm

from helper_func.chat_context_manager import ChatContextManager
from helper_func.jev_API import chat_formatting

jev_output_dir = pathlib.Path("./jev_outputs")
start_index = 0
end_index = 30

async def main_jev_scoring(start_index: int = 0, end_index: int = 300) -> tuple[list[str], list[str]]:
    state = ChatContextManager()
    db = state.db
    jev_api = state.jev_api
    logging_full, logging_jev = [], []
    pname_cache = {}
    # pcontent_cache = {}
    chat_history = db.list_chat_interactions_for_persona(persona_uid=21)
    print("length of chat history:", len(chat_history))

    i = start_index
    for interaction in tqdm(chat_history[start_index:end_index]):
        if interaction.persona_uid not in pname_cache:
            persona = db.get_persona_no_check(interaction.persona_uid)
            assert persona is not None, f"Persona with UID {interaction.persona_uid} not found."
            pname_cache[interaction.persona_uid] = persona.persona_name
            # pcontent_cache[interaction.persona_uid] = persona.content
        persona_name = pname_cache[interaction.persona_uid]
        # persona_content = pcontent_cache[interaction.persona_uid]
        formatted = chat_formatting(interaction)

        gate_result = await jev_api.gate_message(
            recent_context=formatted,
            persona_name=persona_name,
            subject_name=interaction.user_internal_name or f"User_{interaction.user_uid}",
        )
        intent_result = await jev_api.message_intent(
            recent_context=formatted,
            persona_name=persona_name,
            subject_name=interaction.user_internal_name or f"User_{interaction.user_uid}",
        )
        jev_result = {**gate_result, **intent_result}

        i += 1
        display_str = f"{i:03d}. [{interaction.created_at}]\n{formatted}\nScoring result: {jev_result}\n{'-' * 40}\n"
        archive_str = f"{i:03d}. {jev_result | formatted}\n"
        print(display_str)
        logging_full.append(display_str)
        logging_jev.append(archive_str)

    return logging_full, logging_jev


if __name__ == "__main__":
    try:
        log_full, log_jev = asyncio.run(main_jev_scoring(start_index=start_index, end_index=end_index))

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")

    else:
        jev_output_dir.mkdir(exist_ok=True)
        text_log = jev_output_dir / f"scoring_log_{start_index:03d}_{end_index:03d}.txt"
        text_log.write_text("\n".join(log_full), encoding="utf-8")
        scoring_log = jev_output_dir / f"scoring_jev_{start_index:03d}_{end_index:03d}.txt"
        scoring_log.write_text("\n".join(log_jev), encoding="utf-8")

    finally:
        print("Scoring complete.")

# for reference
"""
class ChatInteraction(
    msg_uid: int,
    user_uid: int,
    persona_uid: int,
    created_at: str = _now_iso(),
    is_memorized: bool = False,
    main_content: str = "",
    summary: str = "",
    user_prompt: str = "",
    user_internal_name: str | None = None
)
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
