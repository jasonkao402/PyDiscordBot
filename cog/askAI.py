from typing import Optional, List, Set
from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, TextChannel, app_commands, Webhook
from discord.ext import commands
from discord.abc import Messageable
from typing import Optional
from cog.llmAgentAPI import LLMAPI
from cog.utilFunc import sepLines, wcformat, UserDict
from cog.ui_modal import CreatePersonaModal, EditPersonaModal_Full, EditPersonaModal_Basic, TestSelect
from config_loader import configToml
import re
from persona_db.PersonaDatabase import PersonaDatabase, PersonaVisibility, Persona
from persona_db.helper_func import _join_uid_list, _split_uid_list
import base64

chat_config: dict[str, str] = configToml.get("llmChat", "")

class askAI(commands.Cog):
    __slots__ = ('bot', 'db')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.db = PersonaDatabase("llm_character_cards.db")  # Initialize the database for character cards
        self.llm_api = LLMAPI()  # Initialize the LLM API handler
        self.ban_list = configToml.get("auth", {}).get("ban_list", [])
        self.persona_cache: dict[int, Persona] = {}  # Cache for persona objects
        self.selection_cache: dict[int, int] = {}  # Cache for user selected persona IDs
        self.preferred_name_cache: dict[int, str] = {}  # Cache for user preferred names
        
        debug_channel = bot.get_channel(configToml.get("debugChannelId", -1))
        # get_channel may return various channel types (TextChannel, DMChannel, Thread, etc.).
        # Use the more general TextChannel type for the attribute to avoid
        # type errors when assigning different channel kinds.
        self.debug_channel: Optional[TextChannel] = debug_channel if isinstance(debug_channel, TextChannel) else None
        if self.debug_channel:
            ch_name = getattr(self.debug_channel, 'name', 'Unknown')
            print(f"Debug channel found: {ch_name} (ID: {getattr(self.debug_channel, 'id', 'N/A')})")
        else:
            print("Debug channel not found or invalid. Debug messages will be printed to console.")
        
    async def cog_unload(self):
        await self.llm_api.cleanup()

    @app_commands.command(name="clearcache", description="Clear the persona and selection caches")
    @commands.is_owner()
    async def clear_cache(self, interaction: Interaction):
        """Clear the persona and selection caches."""
        pc, sc, nc = len(self.persona_cache), len(self.selection_cache), len(self.preferred_name_cache)
        self.persona_cache.clear()
        self.selection_cache.clear()
        self.preferred_name_cache.clear()
        await interaction.response.send_message(f"Persona and selection caches have been cleared. (Removed {pc} personas, {sc} selections and {nc} preferred names)", ephemeral=True)
        
    @app_commands.command(name="createpersona", description="Create a new LLM persona")
    async def create_persona(self, interaction: Interaction):
        """Create a new LLM persona using a modal."""
        _check = self.db.count_personas_by_owner(interaction.user.id)
        if _check >= 5:
            await interaction.response.send_message(
                content="You have reached the maximum limit of 5 personas. Please delete an existing persona to create a new one.",
                # ephemeral=True
            )
            return
        modal = CreatePersonaModal(callback=self.handle_create_persona_submission)
        await interaction.response.send_modal(modal)

    async def handle_create_persona_submission(self, interaction: Interaction, persona_id: int, persona_name: str, content: str, is_public: bool, allowed_role_ids: str):
        """Handle the submission of the create persona modal. persona_id is unused and will always be -1 for creation."""
        user_id = interaction.user.id

        # Create the persona, the database will return the new persona's ID which we can use for confirmation
        _persona_id = self.db.create_persona(persona_name, content, user_id, is_public, set(_split_uid_list(allowed_role_ids)))

        # Create an embed to confirm the creation
        embed = Embed(title=f"{persona_name} Created", color=Color.green())
        embed.add_field(name="Persona ID", value=f"#{_persona_id}", inline=False)
        embed.add_field(name="Visibility", value="Public" if is_public else "Private", inline=False)
        embed.add_field(name="Content", value=content[:50], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="editpersona", description="Edit an existing LLM persona")
    @app_commands.describe(persona_id="ID of the persona to edit")
    async def edit_persona(self, interaction: Interaction, persona_id: int):
        """Edit an existing LLM persona using a modal."""
        user_id = interaction.user.id
        user_roles = getattr(interaction.user, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)
        # Fetch the persona from the database
        _persona = self.db.get_persona(persona_id, user_id, user_role_ids)
        if not _persona:
            await interaction.response.send_message("Persona not found or you do not have permission to edit it.", ephemeral=True)
            return
        
        if _persona.owner_uid == user_id:
        # Create and send the owner edit modal
            modal = EditPersonaModal_Full(
                _persona=_persona,
                callback=self.handle_edit_persona_submission
            )
            await interaction.response.send_modal(modal)
        else:
            # Create and send the non-owner edit modal
            modal = EditPersonaModal_Basic(
                _persona=_persona,
                callback=self.handle_edit_persona_submission
            )
            await interaction.response.send_modal(modal)

    async def handle_edit_persona_submission(self, interaction: Interaction, persona_id: int, persona_name: str, content: str, is_public: bool, allowed_role_ids: str):
        """Handle the submission of the edit persona modal."""
        user_id = interaction.user.id
        user_roles = getattr(interaction.user, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)
        updates = {
            'persona_name': persona_name,
            'content': content,
            'is_public': is_public,
            'allowed_role_ids': allowed_role_ids
        }

        success = self.db.update_persona(persona_id, user_id, user_role_ids, **updates)
        if success:
            await interaction.response.send_message(f"Persona #{persona_id} updated successfully.", ephemeral=True)
            # Update cache
            if persona_id in self.persona_cache:
                _persona = self.db.get_persona_no_check(persona_id)
                if not _persona:
                    print(f"Failed to reload updated persona #{persona_id} into cache.")
                    return
                self.persona_cache[persona_id] = _persona  # Refresh the cache with updated persona
        else:
            await interaction.response.send_message("Failed to update persona. Ensure you own the persona.", ephemeral=True)

    @commands.hybrid_command(name="selectpersona")
    async def select_persona(self, ctx: commands.Context, persona_id: int):
        """Select an LLM persona for interaction."""
        user_id = ctx.author.id
        user_roles = getattr(ctx.author, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)
        # Check cache first
        if persona_id in self.persona_cache:
            _persona = self.persona_cache[persona_id]
        else:
            # Fetch from database if not in cache
            print(f'load persona {persona_id} from db')
            _persona = self.db.get_persona_no_check(persona_id)
            if not _persona:
                await ctx.send(f"Failed to retrieve persona ID {persona_id} details.")
                return
            # Build cache
            self.persona_cache[persona_id] = _persona
        
        if not _persona.permission_basic(user_id, user_role_ids):
            await ctx.send(f"You do not have permission to select persona ID {persona_id}.")
            return
        self.selection_cache[user_id] = persona_id
        
        # Set selected persona in database
        success = self.db.set_selected_persona(user_id, persona_id)
        if success:
            await ctx.send(f"{self.persona_cache[persona_id].persona_name}(#{persona_id}) selected successfully.")
        else:
            await ctx.send(f"Failed to select {self.persona_cache[persona_id].persona_name}(#{persona_id}).")

    @commands.hybrid_command(name="listpersonas")
    async def list_personas(self, ctx: commands.Context):
        """List all personas visible to the user."""
        user_id = ctx.author.id
        user_roles = getattr(ctx.author, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)
        personas = self.db.list_personas(user_id, user_role_ids)
        if not personas:
            await ctx.send("No personas available.")
            return

        persona_list = sepLines([f"ID: {p.uid:03d}, Name: {wcformat(p.persona_name, w=10, strFront=False)}, is_public: {p.is_public}" for p in personas])
        await ctx.send(f"Available Personas:\n```{persona_list}```")
    
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
        if not _persona.is_public:
            embed.add_field(name="Content", value=_persona.content[:50], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)
        
    async def _long_message_splitter(self, _ch: Messageable | Webhook, text: str, title: str = "", chunk_size: int = 1900) -> Message:
        """Split a long message into chunks that fit within Discord's message limits and send them sequentially."""
        
        last_message: Message | None = None

        if len(text) > chunk_size:
            parts = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            len_parts = len(parts)
            for i, part in enumerate(parts):
                last_message = await _ch.send(f"# {title} part {i+1}/{len_parts}\n{part}")
        else:
            last_message = await _ch.send(f"# {title}\n{text}")
        
        if last_message is None:
            raise RuntimeError("Failed to send message chunk")

        return last_message
    
    async def handle_llm_trigger(self, _ch: Messageable, _msg: Message, userDict: UserDict):
        """Handle the logic for detecting and triggering the LLM feature."""
        # Load persona selection from cache or database
        if userDict.uid not in self.preferred_name_cache:
            _from_db = self.db.get_discord_user_preferred_name(userDict.uid)
            print(f'from db load preferred name "{_from_db}" for user {userDict.uid}')
            self.preferred_name_cache[userDict.uid] = _from_db or userDict.name
        userDict.name = self.preferred_name_cache[userDict.uid]
        
        if userDict.uid not in self.selection_cache:
            self.selection_cache[userDict.uid] = self.db.get_selected_persona_uid(userDict.uid)
            print(f'from db load persona # {self.selection_cache[userDict.uid]} for user {userDict.uid} selection')
            if self.selection_cache[userDict.uid] != -1:
                # Load persona into cache
                db_persona = self.db.get_persona_no_check(self.selection_cache[userDict.uid])
                if not db_persona:
                    await _ch.send("Selected persona not found in database.\nPlease select another persona using /selectpersona.")
                    return
                self.persona_cache[db_persona.uid] = db_persona

        persona_id = self.selection_cache.get(userDict.uid, -1)
        _persona = self.persona_cache.get(persona_id, None)
        if not _persona:
            await _ch.send("No persona selected. Use /selectpersona to select one. (lvl 2)")
            return

        async with _ch.typing():
            encoded_image = None
            if _msg.attachments:
                attachment = _msg.attachments[0]
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_bytes = await attachment.read()
                    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                    
            # strip out the bot mention part from the message content
            if self.bot.user.mentioned_in(_msg):
                _content = _msg.content.replace(self.bot.user.mention, '', 1).strip()
            else:
                _content = _msg.content
            tResponse = await self.llm_api.persona_chat_oneshot(
                prompt_str=_content,
                _persona=_persona,
                _user_dict=userDict,
                encoded_image=encoded_image
            )
            if tResponse._code == -1:
                await _ch.send(f"Error from LLM API: {tResponse.response_text}")
                return
            self.db.increment_interaction_count(_persona.uid, userDict.uid)
            res = self.db.create_chat_interaction(
                msg_uid=tResponse.timestamp,
                user_uid=userDict.uid,
                persona_uid=_persona.uid,
                main_content=tResponse.response_text,
                user_prompt=_content,
            )
            if not res:
                print("Failed to create chat interaction in database")

            # split both main and thinking content into multiple messages if too long for one message.
            # send thinking content reference link in the original channel to reduce clutter.
            msg_response_text = await self._long_message_splitter(_ch, tResponse.response_text, title=_persona.persona_name)
                
            if tResponse.thinking_content and self.debug_channel:
                msg_thinking_text = await self._long_message_splitter(self.debug_channel, tResponse.thinking_content, title=f"{_persona.persona_name} Thinking")
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
        userDict = UserDict(
            uid = user.id,
            name = user.display_name or user.name,
        )
        # Ignore self messages
        if userDict.uid == self.bot.user.id:
            return
        if userDict.uid in self.ban_list:
            print(f'Ignored message from banned user {userDict.name} ({userDict.uid})')
            return
        
        # Use mentions to trigger bot LLM chat
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            roles = getattr(user, 'roles', [])  # Ensure user.roles exists
            if not any(role.id in configToml.get("auth", {}).get("roleList", []) for role in roles):
                extra_msg = 'You do not have the required role to interact with the bot.'
                print(f'Rejected message from {userDict.name} ({userDict.uid}): {extra_msg}')
                await message.channel.send(f'# To {userDict.name}...\n{extra_msg}')
                return
            await self.handle_llm_trigger(message.channel, message, userDict)

    @commands.hybrid_command(name='scoreboard')
    async def _scoreboard(self, ctx: commands.Context):
        """Display interaction statistics and leaderboard."""
        user = ctx.author
        uid, user_name = user.id, user.name

        # Check if the user has interacted with any AI
        user_stats = self.db.get_user_interaction_stats(uid)
        if not user_stats:
            return await ctx.send(f'{user_name} 尚未和AI們對話過')

        # Retrieve user interaction data
        total_interactions = user_stats['total_interactions']
        most_interacted_count = user_stats['most_interacted_count']
        most_interacted_name = user_stats['most_interacted_persona_name']

        # Retrieve top 5 users with the most interactions
        top_users = self.db.get_top_users(limit=5)
        top_users_list = sepLines(
            f'{username.name if (username := self.bot.get_user(user_id)) else "ERROR"}: {count}'
            for user_id, count in top_users
        )

        # Prepare and send the scoreboard message
        if most_interacted_name:
            await ctx.send(
                f'```{top_users_list}```\n'
                f'{user_name}共對話 {total_interactions} 次，'
                f'最常找 {most_interacted_name} 互動 '
                f'({most_interacted_count} 次，佔 {most_interacted_count / total_interactions:.2%})'
            )
        else:
            await ctx.send(
                f'```{top_users_list}```\n'
                f'{user_name}共對話 {total_interactions} 次'
            )
        
    async def model_autocomplete(
        self, 
        interaction: Interaction, 
        current: str
    ) -> List[app_commands.Choice[str]]:
        
        # Get your list of models
        models = chat_config["modelList"] 
        
        # Filter models based on what the user is typing
        filtered_models = [model for model in models if current.lower() in model.lower()]
        
        # Return the choices (max 25)
        return [
            app_commands.Choice(name=model, value=model)
            for model in filtered_models[:25]
        ]

    @app_commands.command(name="selectmodel", description="選擇要使用的模型")
    @app_commands.describe(model="請從列表中選擇一個模型")  # Add a description for the option
    @app_commands.autocomplete(model=model_autocomplete)   # Link the autocomplete function
    async def _selectModel(self, interaction: Interaction, model: str):
        # 'model' is now the string the user selected from the autocomplete list
        
        # A quick check to make sure the model is valid
        if model not in chat_config["modelList"]:
            await interaction.response.send_message(
                f"錯誤：無效的模型 `{model}`", 
                ephemeral=True
            )
            return

        # Update your config
        chat_config["modelChat"] = model
        
        # Send the confirmation
        await interaction.response.send_message(
            f"已切換至 `{model}`",
            ephemeral=True  # Confirmation messages are better as ephemeral
        )

    @app_commands.command(name="memo", description="Summarize the current persona memory into a new memory")
    async def _memo(self, interaction: Interaction):
        user_id = interaction.user.id
        persona_id = self.selection_cache.get(user_id, -1)

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
            print(f"Source msg_uids for summarization: {source_msg_uids}")

            tResponse = await self.llm_api.persona_memory_summarize(_persona=_persona)
            print(f"Summarization response: {tResponse}")

            if tResponse._code == -1:
                # Summarization failed
                await interaction.followup.send("Failed to summarize persona memory.")
                return

            # --- Success path ---
            # Send initial confirmation via followup
            await interaction.followup.send("Summarization successful. Saving summarized memory...")

            # Send the long summary via channel splitter
            msg_response_text = await self._long_message_splitter(interaction.followup, tResponse.response_text, title=f"{_persona.persona_name} Summary")
                
            if tResponse.thinking_content and self.debug_channel:
                msg_thinking_text = await self._long_message_splitter(self.debug_channel, tResponse.thinking_content, title=f"{_persona.persona_name} Thinking Summary")
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

            # Optional: final success message
            # (already sent a confirmation; you can skip or send another followup)

        except Exception as e:
            print(f"Unexpected error in memo command: {e}")
            await interaction.followup.send(f"An unexpected error occurred: {e}")
            
    @app_commands.command(name="testmodal", description="Test the select modal")
    async def _test_modal(self, interaction: Interaction):
        modal = TestSelect(member=interaction.user)
        # await interaction.response.defer(thinking=True)  # Defer the response to allow time for the modal to be filled out
        # await interaction.guild..send("Opening test modal...")
        print(f"Opening test modal for {interaction.user.display_name} ({interaction.user.id})")
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="setname", description="Set the preferred name for the user")
    async def _set_name(self, interaction: Interaction, name: str):
        user_id = interaction.user.id
        res = self.db.update_discord_user(user_id, preferred_name=name)
        if res:
            await interaction.response.send_message(f"Your preferred name has been set to {name}.")
        else:
            await interaction.response.send_message("Failed to update preferred name.")
        # await interaction.response.send_message(f"Your preferred name has been set to {name}.")
        
async def setup(bot:commands.Bot):
    cog_instance = askAI(bot)
    await bot.add_cog(cog_instance)

async def teardown(bot:commands.Bot):
    print('ai saved')
