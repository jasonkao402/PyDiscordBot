from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from discord import Color, Embed, Interaction, Message, app_commands
from discord.ext import commands

from config_loader import config_toml
from helper_func.utilFunc import UserDict, long_message_splitter

if TYPE_CHECKING:
    from discord.abc import Messageable

    from setup_bot import MyBot


class LLMChatCog(commands.Cog):

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.state = bot.chat_state
        self.db = self.state.db
        self.llm_api = self.state.llm_api
        self.ban_list = self.state.ban_list

        self.persona_cache = self.state.persona_cache
        self.selection_cache = self.state.selection_cache
        self.discord_user_cache = self.state.discord_user_cache
        self.debug_channel = self.bot.debug_channel

        if self.debug_channel:
            ch_name = getattr(self.debug_channel, 'name', 'Unknown')
            print(f"Debug channel found: {ch_name} (ID: {getattr(self.debug_channel, 'id', 'N/A')}, Type: {type(self.debug_channel)})")
        else:
            print("Debug channel not found or invalid. Debug messages will be printed to console.")

    @app_commands.command(name="bonk", description="Erase the current chat session memory for the selected persona")
    async def bonk(self, interaction: Interaction):
        """Erase the current chat session memory for the selected persona."""
        user_id = interaction.user.id

        # Get the selected persona
        _persona = self.persona_cache.get(self.selection_cache.get(user_id, -1), None)

        if not _persona:
            await interaction.response.send_message("No persona selected. Use /selectpersona to select one.", ephemeral=True)
            return

        # Clear the memory for the selected persona
        self.llm_api.reset_memory(_persona.uid)
        await interaction.response.send_message(f"Session memory for {_persona.persona_name} has been erased.")

    @app_commands.command(name="goback", description="Revert the last interaction for the selected persona")
    async def goback(self, interaction: Interaction):
        """Revert the last interaction for the selected persona."""
        user_id = interaction.user.id

        # Get the selected persona
        _persona = self.persona_cache.get(self.selection_cache.get(user_id, -1), None)

        if not _persona:
            await interaction.response.send_message("No persona selected. Use /selectpersona to select one.", ephemeral=True)
            return

        # Revert the last interaction for the selected persona
        success = self.llm_api.revert_last_interaction(_persona.uid)
        if success:
            await interaction.response.send_message(f"The last interaction for {_persona.persona_name} has been reverted.")
        else:
            await interaction.response.send_message(f"No interactions to revert for {_persona.persona_name}.")

    @app_commands.command(name="currentpersona", description="Show the currently selected persona")
    async def current_persona(self, interaction: Interaction):
        """Show the currently selected persona."""
        user_id = interaction.user.id

        # Get the selected persona
        persona_id = self.selection_cache.get(user_id, -1)
        _persona = self.persona_cache.get(persona_id, None)

        if not _persona:
            await interaction.response.send_message("No persona selected. Use /selectpersona to select one.", ephemeral=True)
            return

        # Create an embed to display persona details
        embed = Embed(title=f"Current Persona: {_persona.persona_name} (#{_persona.uid})", color=Color.blue())
        embed.add_field(name="is_public", value="Yes" if _persona.is_public else "No", inline=False)
        # if not _persona.is_public:
        #     embed.add_field(name="Content", value=_persona.content[:50], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)

    async def handle_cache(self, _user_dict: UserDict, _ch: Messageable):
        _user_id = _user_dict.uid
        if _user_id not in self.discord_user_cache:
            user_fromDB = self.db.get_discord_user(_user_id)
            print(f'from db loaded user {_user_id}')
            if not user_fromDB:
                # if user not in database, create a new record with default preferred name as display name
                self.db.create_discord_user(_user_id)
                print(f'created new user {_user_id} in db')
                self.discord_user_cache[_user_id] = UserDict(uid=_user_id, name=_user_dict.name, preferred_name=_user_dict.preferred_name)
            else:
                self.discord_user_cache[_user_id] = UserDict(uid=_user_id, name=_user_dict.name, preferred_name=user_fromDB.preferred_name, descr=user_fromDB.descr)

        _personaID_fromDB = -1
        if _user_id not in self.selection_cache:
            # get selected persona from database if not in cache
            _personaID_fromDB = self.db.get_selected_persona_uid(_user_id) or -1
            print(f'from db load persona # {_personaID_fromDB} for user {_user_id} selection')
            if _personaID_fromDB == -1:
                await _ch.send("No persona selected. Use /selectpersona to select one. (lvl 1)")
            self.selection_cache[_user_id] = _personaID_fromDB

        if _personaID_fromDB != -1 and _personaID_fromDB not in self.persona_cache:
            # load the selected persona into cache
            db_persona = self.db.get_persona_no_check(self.selection_cache[_user_id])
            if not db_persona:
                await _ch.send("Selected persona not found in database.\nPlease select another persona using /selectpersona.")
                return
            self.persona_cache[db_persona.uid] = db_persona

    async def handle_llm_trigger(self, _ch: Messageable, _msg: Message, _user_dict: UserDict):
        """Handle the logic for detecting and triggering the LLM feature."""
        # Load persona selection from cache or database
        _user_id = _user_dict.uid
        await self.handle_cache(_user_dict, _ch)

        _persona = self.persona_cache.get(self.selection_cache.get(_user_id, -1), None)
        _user_dict = self.discord_user_cache.get(_user_id, _user_dict)

        if self.llm_api.debug_mode:
            debug_info = f"""
                Debug Info:
                  - User: {_user_dict}
                  - Selected Persona ID: {self.selection_cache.get(_user_id, 'None')}
                """
            print(debug_info)

            system_instruction = self.llm_api._debug_system_instruction(_persona, _user_dict) if _persona else "No persona available for system instruction."
            print(f"System Instruction:\n{system_instruction}")

        if not _persona:
            await _ch.send("No persona selected. Use /selectpersona to select one. (lvl 2)")
            return

        encoded_image = None
        if _msg.attachments:
            attachment = _msg.attachments[0]
            if attachment.content_type and attachment.content_type.startswith('image/'):
                image_bytes = await attachment.read()
                encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        async with _ch.typing():
            # strip out the bot mention part from the message content
            if self.bot.user.mentioned_in(_msg):
                _content = _msg.content.replace(self.bot.user.mention, '', 1).strip()
            else:
                _content = _msg.content
            tResponse = await self.llm_api.persona_chat_oneshot(
                prompt_str=_content,
                _persona=_persona,
                _user_dict=_user_dict,
                encoded_image=encoded_image
            )
            if tResponse._code == -1:
                await _ch.send(f"Error from LLM API: {tResponse.response_text}")
                return
            self.db.increment_interaction_count(_persona.uid, _user_id)
            res = self.db.create_chat_interaction(
                msg_uid=tResponse.timestamp,
                user_uid=_user_id,
                persona_uid=_persona.uid,
                main_content=tResponse.response_text,
                user_prompt=_content,
            )
            if not res:
                print("Failed to create chat interaction in database")

        # split both main and thinking content into multiple messages if too long for one message.
        # send thinking content reference link in the original channel to reduce clutter.
        msg_response_text = await long_message_splitter(_ch, tResponse.response_text, title=_persona.persona_name)

        if tResponse.thinking_content and self.debug_channel:
            msg_thinking_text = await long_message_splitter(self.debug_channel, tResponse.thinking_content, title=f"{_persona.persona_name} Thinking")
            usage_info = '\n'.join(f'-# {k}: {v}' for k, v in tResponse.token_usage.items())
            await self.debug_channel.send(f"-# Main content {msg_response_text.jump_url}\n-# Token usage:\n{usage_info}")
            # Edit the last one of original response messages to include a reference to the thinking content in the debug channel
            edit_content = f"{msg_response_text.content}\n\n-# Thinking {msg_thinking_text.jump_url}"
            await msg_response_text.edit(content=edit_content)
        else:
            # No thinking content or debug channel available, just print response and token usage in debug channel or console
            print(str(tResponse))

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        user = message.author
        channel = message.channel
        _user_id = user.id
        ch_whitelist = config_toml.get("auth", {}).get("channel_list", [])
        userDict = UserDict(
            uid=_user_id,
            name=user.name,
            preferred_name=user.display_name
        )
        # Ignore self messages
        if _user_id == self.bot.user.id:
            return

        # Use mentions to trigger bot LLM chat
        if self.bot.user.mentioned_in(message) and not message.mention_everyone and not message.role_mentions:
            if _user_id in self.ban_list:
                print(f'Ignored message from banned user {userDict.name} ({_user_id})')
                return
            if channel.id not in ch_whitelist:
                ch_name = getattr(channel, 'name', "Unknown(DM)")
                print(f'Ignored message from {userDict.name} ({_user_id}) in channel {ch_name} ({channel.id})')
                return
            await self.handle_llm_trigger(message.channel, message, userDict)

    @app_commands.command(name="memo", description="Summarize the current persona's short term memory into a long term memory")
    async def memo(self, interaction: Interaction):
        user_id = interaction.user.id
        persona_id = self.selection_cache.get(user_id, -1)
        _user_dict = self.discord_user_cache.get(user_id, UserDict(uid=user_id, name=interaction.user.name, preferred_name=interaction.user.display_name))
        # --- Early validation (synchronous, send direct response) ---
        if persona_id == -1:
            await interaction.response.send_message(
                "No persona selected. Use /selectpersona to select one."
            )
            return

        _persona = self.persona_cache.get(persona_id)
        if not _persona:
            await interaction.response.send_message(
                "Selected persona not found. Please select another persona using /selectpersona."
            )
            return

        # --- Defer the response (long operation) ---
        await interaction.response.defer(thinking=True)

        try:
            source_msg_uids = self.llm_api.get_msg_uids_from_memory(persona_id, skip_memorized=True)
            tResponse = await self.llm_api.persona_memory_summarize(_persona=_persona, _user_dict=_user_dict)
            print(f"Summarization response, msg_uids: {source_msg_uids}\nresponse: {tResponse}")

            if tResponse._code == -1:
                # Summarization failed
                await interaction.followup.send("Failed to summarize persona memory.")
                return

        except Exception as e:
            print(f"Unexpected error in memo command: {e}")
            await interaction.followup.send(f"An unexpected error occurred: {e}")
        else:
            # --- Success path ---
            # Send initial confirmation via followup
            await interaction.followup.send("Summarization successful. Saving summarized memory...")

            # Send the long summary via channel splitter
            msg_response_text = await long_message_splitter(interaction.followup, tResponse.response_text, title=f"{_persona.persona_name} Summary")

            if tResponse.thinking_content and self.debug_channel:
                msg_thinking_text = await long_message_splitter(self.debug_channel, tResponse.thinking_content, title=f"{_persona.persona_name} Thinking Summary")
                usage_info = '\n'.join(f'-# {k}: {v}' for k, v in tResponse.token_usage.items())
                await self.debug_channel.send(f"-# Main content {msg_response_text.jump_url}\n-# Token usage:\n{usage_info}")
                # Edit the last one of original response messages to include a reference to the thinking content in the debug channel
                edit_content = f"{msg_response_text.content}\n\n-# Thinking {msg_thinking_text.jump_url}"
                await msg_response_text.edit(content=edit_content)

            else:
                # No thinking content or debug channel available, just print response and token usage in debug channel or console
                print(str(tResponse))

            # Update interaction count and save memory in DB
            self.db.increment_interaction_count(persona_id, user_id)
            res = self.db.create_persona_memory(
                memory_content=tResponse.response_text,
                persona_uid=persona_id,
                source_msg_uids=source_msg_uids,
            )
            if not res:
                print("Failed to create persona memory in database")
                await interaction.followup.send("Failed to create persona memory.")
                return

async def setup(bot: MyBot):
    cog_instance = LLMChatCog(bot)
    await bot.add_cog(cog_instance)

async def teardown(bot: MyBot):
    await bot.remove_cog("LLMChatCog")
    print('ai saved')
