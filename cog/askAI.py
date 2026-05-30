from typing import Optional, List
from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, TextChannel, app_commands
from discord.ext import commands
from discord.abc import Messageable
from typing import Optional
from cog.llmAgentAPI import LLMAPI
from cog.utilFunc import sepLines, wcformat, UserDict
from cog.ui_modal import CreatePersonaModal, EditPersonaModal
from config_loader import configToml
import re
from cog_dev.database_test import PersonaDatabase, PersonaVisibility, Persona
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
        pc, sc = len(self.persona_cache), len(self.selection_cache)
        self.persona_cache.clear()
        self.selection_cache.clear()
        await interaction.response.send_message(f"Persona and selection caches have been cleared. (Removed {pc} personas and {sc} selections)", ephemeral=True)
        
    @app_commands.command(name="createpersona", description="Create a new LLM persona")
    async def create_persona(self, interaction: Interaction):
        """Create a new LLM persona using a modal."""
        modal = CreatePersonaModal(callback=self.handle_create_persona_submission)
        await interaction.response.send_modal(modal)

    async def handle_create_persona_submission(self, interaction: Interaction, persona_name: str, content: str, visibility: bool):
        """Handle the submission of the create persona modal."""
        user_id = interaction.user.id
        visibility_enum = PersonaVisibility.PUBLIC if visibility else PersonaVisibility.PRIVATE

        # Create the persona
        _persona_id = self.db.create_persona(persona_name, content, user_id, visibility_enum)

        if _persona_id == -1:
            # Send a warning message if persona creation fails
            await interaction.response.send_message(
                content="You have reached the maximum limit of 5 personas. Please delete an existing persona to create a new one.",
                ephemeral=True
            )
            return

        # Create an embed to confirm the creation
        embed = Embed(title=f"{persona_name} (#{_persona_id}) Created", color=Color.green())
        embed.add_field(name="Visibility", value="Public" if visibility else "Private", inline=False)
        embed.add_field(name="Content", value=content[:1024], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="editpersona", description="Edit an existing LLM persona")
    @app_commands.describe(persona_id="ID of the persona to edit")
    async def edit_persona(self, interaction: Interaction, persona_id: int):
        """Edit an existing LLM persona using a modal."""
        user_id = interaction.user.id

        # Fetch the persona from the database
        _persona = self.db.get_persona(persona_id, user_id)
        if not _persona:
            await interaction.response.send_message("Persona not found or you do not have permission to edit it.", ephemeral=True)
            return

        # Create and send the modal
        modal = EditPersonaModal(
            persona_id=persona_id,
            persona_name=_persona.persona,
            content=_persona.content,
            visibility=_persona.visibility == PersonaVisibility.PUBLIC,
            callback=self.handle_edit_persona_submission
        )
        await interaction.response.send_modal(modal)

    async def handle_edit_persona_submission(self, interaction: Interaction, persona_id: int, persona_name: str, content: str, visibility: bool):
        """Handle the submission of the edit persona modal."""
        user_id = interaction.user.id
        updates = {
            'persona': persona_name,
            'content': content,
            'visibility': PersonaVisibility.PUBLIC.value if visibility else PersonaVisibility.PRIVATE.value
        }

        success = self.db.update_persona(persona_id, user_id, **updates)
        if success:
            await interaction.response.send_message(f"Persona #{persona_id} updated successfully.", ephemeral=True)
            # Update cache
            if persona_id in self.persona_cache:
                _persona = self.persona_cache[persona_id]
                _persona.persona = persona_name
                _persona.content = content
                _persona.visibility = PersonaVisibility(updates['visibility'])
        else:
            await interaction.response.send_message("Failed to update persona. Ensure you own the persona.", ephemeral=True)

    @commands.hybrid_command(name="selectpersona")
    async def select_persona(self, ctx: commands.Context, persona_id: int):
        """Select an LLM persona for interaction."""
        user_id = ctx.author.id

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
        
        if not _persona.permission_check(user_id):
            await ctx.send(f"You do not have permission to select persona ID {persona_id}.")
            return
        self.selection_cache[user_id] = persona_id
        
        # Set selected persona in database
        success = self.db.set_selected_persona(user_id, persona_id)
        if success:
            await ctx.send(f"{self.persona_cache[persona_id].persona}(#{persona_id}) selected successfully.")
        else:
            await ctx.send(f"Failed to select {self.persona_cache[persona_id].persona}(#{persona_id}).")

    @commands.hybrid_command(name="listpersonas")
    async def list_personas(self, ctx: commands.Context):
        """List all personas visible to the user."""
        user_id = ctx.author.id
        personas = self.db.list_personas(user_id)
        if not personas:
            await ctx.send("No personas available.")
            return

        persona_list = sepLines([f"ID: {p.uid:03d}, Name: {wcformat(p.persona, w=10, strFront=False)}, Visibility: {p.visibility.name}" for p in personas])
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
        await interaction.response.send_message(f"Session memory for {_persona.persona} has been erased.")
            
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
        embed = Embed(title=f"Current Persona: {_persona.persona} (#{_persona.uid})", color=Color.blue())
        embed.add_field(name="Visibility", value="Public" if _persona.visibility == PersonaVisibility.PUBLIC else "Private", inline=False)
        embed.add_field(name="Content", value=_persona.content[:1024], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)
        
    async def _long_message_splitter(self, ctx: Messageable, text: str, title: str = "", chunk_size: int = 1900) -> Message:
        """Split a long message into chunks that fit within Discord's message limits and send them sequentially."""
        last_message: Message | None = None

        if len(text) > chunk_size:
            parts = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
            len_parts = len(parts)
            for i, part in enumerate(parts):
                last_message = await ctx.send(f"# {title} part {i+1}/{len_parts}\n{part}")
        else:
            last_message = await ctx.send(f"# {title}\n{text}")
        
        if last_message is None:
            raise RuntimeError("Failed to send message chunk")

        return last_message
    
    async def handle_llm_trigger(self, message: Message, user: UserDict):
        """Handle the logic for detecting and triggering the LLM feature."""
        # Load persona selection from cache or database
        if user.uid not in self.selection_cache:
            self.selection_cache[user.uid] = self.db.get_selected_persona_uid(user.uid)
            print(f'from db load persona # {self.selection_cache[user.uid]} for user {user.uid} selection')
            if self.selection_cache[user.uid] != -1:
                # Load persona into cache
                db_persona = self.db.get_persona_no_check(self.selection_cache[user.uid])
                if not db_persona:
                    await message.channel.send("Selected persona not found in database.\nPlease select another persona using /selectpersona.")
                    return
                self.persona_cache[db_persona.uid] = db_persona

        persona_id = self.selection_cache.get(user.uid, -1)
        _persona = self.persona_cache.get(persona_id, None)
        if not _persona:
            await message.channel.send("No persona selected. Use /selectpersona to select one. (lvl 2)")
            return

        async with message.channel.typing():
            encoded_image = None
            if message.attachments:
                attachment = message.attachments[0]
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    image_bytes = await attachment.read()
                    encoded_image = base64.b64encode(image_bytes).decode('utf-8')
                    
            # strip out the bot mention part from the message content
            if self.bot.user.mentioned_in(message):
                _content = message.content.replace(self.bot.user.mention, '', 1).strip()
            else:
                _content = message.content
            tResponse = await self.llm_api.handle_llm_agent(
                content=_content,
                _persona=_persona,
                _user_dict=user,
                encoded_image=encoded_image
            )
            
            # split both main and thinking content into multiple messages if too long for one message.
            # send thinking content reference link in the original channel to reduce clutter.
            msg_response_text = await self._long_message_splitter(message.channel, tResponse.response_text, title=_persona.persona)
                
            if tResponse.thinking_content and self.debug_channel:
                msg_thinking_text = await self._long_message_splitter(self.debug_channel, tResponse.thinking_content, title=f"{_persona.persona} Thinking")
                usage_info = '\n'.join(f'-# {k}: {v}' for k, v in tResponse.token_usage.items())
                await self.debug_channel.send(f"-# Main content {msg_response_text.jump_url}\n-# Token usage:\n{usage_info}")
                # Edit the original response message to include a reference to the thinking content in the debug channel
                await msg_response_text.edit(content=f"{tResponse.response_text}\n-# Thinking {msg_thinking_text.jump_url}")
                 
            else:
                # No thinking content or debug channel available, just print response and token usage in debug channel or console
                print(str(tResponse))
            self.db.increment_interaction_count(_persona.uid, user.uid)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        user, message_text = message.author, message.content
        _user = UserDict(
            uid = user.id,
            name = user.name,
            display_name = user.display_name
        )
        # Ignore self messages
        if _user.uid == self.bot.user.id:
            return
        if _user.uid in self.ban_list:
            print(f'Ignored message from banned user {_user.name} ({_user.uid})')
            return
        
        # Use mentions to trigger bot LLM chat
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            roles = getattr(user, 'roles', [])  # Ensure user.roles exists
            if not any(role.id in configToml.get("auth", {}).get("roleList", []) for role in roles):
                extra_msg = 'You do not have the required role to interact with the bot.'
                print(f'Rejected message from {_user.name} ({_user.uid}): {extra_msg}')
                await message.channel.send(f'# To {_user.name}...\n{extra_msg}')
                return
            await self.handle_llm_trigger(message, _user)

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
        
async def setup(bot:commands.Bot):
    cog_instance = askAI(bot)
    await bot.add_cog(cog_instance)

async def teardown(bot:commands.Bot):
    print('ai saved')
