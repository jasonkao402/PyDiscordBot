from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Interaction, app_commands
from discord.app_commands import Choice
from discord.ext import commands

from helper_func.ui_modal import TestSelect
from helper_func.utilFunc import is_admin_check, long_message_splitter

if TYPE_CHECKING:
    from helper_func.chat_context_manager import ChatContextManager
    from helper_func.llm_agent_API import LLMAPI
    from setup_bot import MyBot


class LLMAdminCog(commands.Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.state: ChatContextManager = bot.chat_state
        self.db = self.state.db
        self.llm_api: LLMAPI = self.state.llm_api

    @is_admin_check()
    @app_commands.command(name="clearcache", description="Clear the persona and selection caches")
    async def clear_cache(self, interaction: Interaction):
        """Clear the persona and selection caches."""
        result = await self.state.clear_cache()
        await interaction.response.send_message(result)

    @is_admin_check()
    @app_commands.command(name="debugmode", description="Toggle debug mode for the user (for testing purposes)")
    async def toggle_debug_mode(self, interaction: Interaction):
        self.llm_api.debug_mode = not self.llm_api.debug_mode
        await interaction.response.send_message(f"Debug mode is now {'enabled' if self.llm_api.debug_mode else 'disabled'} for you.")

    @is_admin_check()
    @app_commands.command(name="refreshmodels", description="Refresh the available models in the LLM API")
    async def refresh_models(self, interaction: Interaction):
        """Refresh the available models in the LLM API."""
        await self.state.refresh_models()
        models = self.llm_api.available_models
        models_str = "\n- ".join(models) if models else "No models available."
        await interaction.response.send_message(f"Current main model: `{self.llm_api.main_model}`\nAvailable models:\n- {models_str}")

    async def autocomplete_persona_id(
        self,
        interaction: Interaction,
        current: str
    ) -> list[Choice[str]]:
        """Autocomplete function for persona_id parameter in editpersona command."""
        user_id = interaction.user.id
        user_roles = getattr(interaction.user, 'roles', [])
        user_role_ids = {role.id for role in user_roles}

        result = await self.state.autocomplete_persona_id(user_id, user_role_ids, current)
        return [Choice(name=f"{p.persona_name} (#{p.uid})", value=str(p.uid)) for p in result[:25]]

    @is_admin_check()
    @app_commands.command(name="chathistory", description="Inspect the current short term memory of the bot")
    @app_commands.describe(persona_id="The ID of the persona to inspect")  # Add a description for the option
    @app_commands.autocomplete(persona_id=autocomplete_persona_id)  # Link the autocomplete function
    async def inspect_memory(self, interaction: Interaction, persona_id: int):
        """Inspect the persona's chat history"""
        persona = self.db.get_persona_no_check(persona_id)
        if persona is None:
            await interaction.response.send_message("Please provide a valid persona ID to inspect its chat history.", ephemeral=True)
            return

        history = self.llm_api.inspect_memory(persona_id)
        history_str = "\n".join([f"{i + 1}. {txt[:50]}..." if len(txt := entry.chat_text) > 50 else f"{i + 1}. {txt}" for i, entry in enumerate(history)]) if history else "No chat history found."
        # await interaction.response.send_message(f"Chat history for {persona.persona_name}:\n{history_str}")
        await long_message_splitter(interaction.message.channel, history_str, title=f"Chat history for {persona.persona_name}", chunk_size=1900)

    async def model_autocomplete(
        self,
        interaction: Interaction,
        current: str
    ) -> list[Choice[str]]:

        # Get your list of models
        api_models = await self.llm_api.get_available_models()  # Fetch available models from the API
        # Filter models based on what the user is typing
        filtered_models = [model for model in api_models if current.lower() in model.lower()]

        # Return the choices (max 25)
        return [
            Choice(name=model, value=model)
            for model in filtered_models[:25]
        ]

    @is_admin_check()
    @app_commands.command(name="selectmodel", description="選擇要使用的模型")
    @app_commands.describe(model="請從列表中選擇一個模型")  # Add a description for the option
    @app_commands.autocomplete(model=model_autocomplete)   # Link the autocomplete function
    async def select_model(self, interaction: Interaction, model: str):
        # 'model' is now the string the user selected from the autocomplete list

        # make sure the model is valid
        if model not in self.llm_api.available_models:
            await interaction.response.send_message(
                f"錯誤：無效的模型 `{model}`",
                ephemeral=True
            )
            return

        # Update config
        self.llm_api.main_model = model

        # Send the confirmation
        await interaction.response.send_message(
            f"成功，已切換模型至 `{self.llm_api.main_model}`",
        )

    @app_commands.command(name="testmodal", description="Test the select modal")
    async def test_modal(self, interaction: Interaction):
        modal = TestSelect(member=interaction.user)
        # await interaction.response.defer(thinking=True)  # Defer the response to allow time for the modal to be filled out
        # await interaction.guild..send("Opening test modal...")
        print(f"Opening test modal for {interaction.user.display_name} ({interaction.user.id})")
        await interaction.response.send_modal(modal)

async def setup(bot: MyBot):
    cog_instance = LLMAdminCog(bot)
    await bot.add_cog(cog_instance)
