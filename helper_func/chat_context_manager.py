from __future__ import annotations

from typing import TYPE_CHECKING

from config_loader import configToml
from helper_func.llm_agent_API import LLMAPI
from persona_db.PersonaDatabase import Persona, PersonaDatabase

if TYPE_CHECKING:
    from helper_func.utilFunc import UserDict


class ChatContextManager:
    """Holds shared database, API, and cache references across multiple Cogs."""
    def __init__(self):
        self.db = PersonaDatabase("llm_character_cards.db")
        self.llm_api = LLMAPI()
        self.ban_list: list[int] = configToml.get("auth", {}).get("ban_list", [])

        # Shared caches (mutating these in one Cog updates them everywhere)
        self.persona_cache: dict[int, Persona] = {}
        self.selection_cache: dict[int, int] = {}
        self.discord_user_cache: dict[int, UserDict] = {}

    async def clear_cache(self):
        """Clear the persona and selection caches."""
        pc, sc, nc = len(self.persona_cache), len(self.selection_cache), len(self.discord_user_cache)
        self.persona_cache.clear()
        self.selection_cache.clear()
        self.discord_user_cache.clear()
        return f"Cleared caches: {pc} personas, {sc} selections, {nc} user names."

    async def refresh_models(self):
        """Refresh the available models in the LLM API."""
        models = await self.llm_api.get_available_models(force_refresh=True)  # Refresh the model list in the LLM API
        models_str = "\n  - ".join(models) if models else "No models available."
        return f"Available models:\n  - {models_str}"

    async def cleanup(self):
        await self.llm_api.cleanup()

    async def autocomplete_persona_id(self, user_id: int, user_role_ids: set[int], current: str) -> list[Persona]:
        """Autocomplete function for persona_id parameter in editpersona command."""
        personas = self.persona_cache.values() if self.persona_cache else self.db.list_personas(user_id, user_role_ids)
        return [p for p in personas if current in str(p.uid) or current.lower() in p.persona_name.lower()]
