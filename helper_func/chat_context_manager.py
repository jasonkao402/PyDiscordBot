from typing import Optional
from discord import TextChannel, Client as DC_Client
from persona_db.PersonaDatabase import PersonaDatabase, Persona
from helper_func.llmAgentAPI import LLMAPI
from discord.ext.commands import Bot
from helper_func.utilFunc import UserDict
from config_loader import configToml

class ChatContextManager:
    """Holds shared database, API, and cache references across multiple Cogs."""
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.db = PersonaDatabase("llm_character_cards.db")
        self.llm_api = LLMAPI()
        self.ban_list: list[int] = configToml.get("auth", {}).get("ban_list", [])
        
        # Shared caches (mutating these in one Cog updates them everywhere)
        self.persona_cache: dict[int, Persona] = {}
        self.selection_cache: dict[int, int] = {}
        self.discord_user_cache: dict[int, UserDict] = {}

    @property
    def debug_channel(self) -> Optional[TextChannel]:
        ch = self.bot.get_channel(configToml.get("debug_channel_id", -1))
        return ch if isinstance(ch, TextChannel) else None

    async def cleanup(self):
        await self.llm_api.cleanup()