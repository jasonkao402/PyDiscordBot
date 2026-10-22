from discord.ext import commands
from typing import Optional, List, Set
from discord import Color, Embed, Interaction, Message, app_commands
from discord.app_commands import Choice
from helper_func.llmAgentAPI import LLMAPI
from helper_func.chat_context_manager import ChatContextManager
from helper_func.utilFunc import UserDict, sepLines, wcformat, is_admin_check
from helper_func.ui_modal import CreatePersonaModal, EditPersonaModal_Full, EditPersonaModal_Basic
from persona_db.helper_func import _split_uid_list
from setup_bot import MyBot

class PersonaManagerCog(commands.Cog):
    def __init__(self, bot: MyBot):
        self.bot = bot
        self.state: ChatContextManager = bot.chat_state
        self.db = self.state.db
        self.llm_api: LLMAPI = self.state.llm_api

        self.persona_cache = self.state.persona_cache
        self.selection_cache = self.state.selection_cache
        self.discord_user_cache = self.state.discord_user_cache
        # self.debug_guild = self.bot.debug_guild
        self.debug_channel = self.bot.debug_channel

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
            await interaction.response.send_message(f"Persona #{persona_id} not found.")
            return
        
        if _persona.owner_uid == user_id:
            # owner edit modal
            modal = EditPersonaModal_Full(
                _persona=_persona,
                callback=self.handle_edit_persona_submission
            )
            await interaction.response.send_modal(modal)
        elif _persona.permission_full(user_id, user_role_ids):
            # non-owner edit modal
            modal = EditPersonaModal_Basic(
                _persona=_persona,
                callback=self.handle_edit_persona_submission
            )
            await interaction.response.send_modal(modal)
        else:
            await interaction.response.send_message("You do not have permission to edit this persona.", ephemeral=True)
            
    async def handle_edit_persona_submission(self, interaction: Interaction, persona_id: int, persona_name: str, content: str, is_public: bool, allowed_role_ids: str):
        """Handle the submission of the edit persona modal."""
        user_id = interaction.user.id
        user_roles = getattr(interaction.user, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)
        _allowed_fields = self.db._get_allowed_fields_for_user(persona_id, user_id, user_role_ids)  # This will check permissions and return allowed fields, but we can skip the returned value since the modal already restricts input based on ownership
        updates = {
            'persona_name': persona_name,
            'content': content,
            'is_public': is_public,
            'allowed_role_ids': allowed_role_ids
        }
        updates = {k: v for k, v in updates.items() if k in _allowed_fields}

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
            
    async def autocomplete_persona_id(self, interaction: Interaction, current: str) -> List[Choice[str]]:
        """Autocomplete function for persona_id parameter in editpersona command."""
        user_id = interaction.user.id
        user_roles = getattr(interaction.user, 'roles', [])
        user_role_ids = set(role.id for role in user_roles)

        result = await self.state.autocomplete_persona_id(user_id, user_role_ids, current)
        return [Choice(name=f"{p.persona_name} (#{p.uid})", value=str(p.uid)) for p in result[:25]
        ]
        
    @commands.hybrid_command(name="selectpersona", description="選擇一個角色進行互動")
    @app_commands.describe(persona_id="請輸入要選擇的角色ID")
    @app_commands.autocomplete(persona_id=autocomplete_persona_id)
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
        success = self.db.set_selected_persona(persona_id, user_id, user_role_ids)
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
        personas = sorted(personas, key=lambda p: p.uid)  # Sort by persona ID
        persona_list = sepLines([f"ID: {p.uid:03d}, [{['私人', '公開'][int(p.is_public)]}] Name: {wcformat(p.persona_name)}" for p in personas])
        await ctx.send(f"Available Personas:\n```{persona_list}```")

    @app_commands.command(name="setname", description="Update the preferred name and description for the user")
    async def _set_name(self, interaction: Interaction, name: Optional[str], description: Optional[str]):
        user_id = interaction.user.id
        # reset to default only if both name and description are empty, else keep the existing value if one of them is provided, 
        # final fallback to display name for preferred name and "None" for description if both are empty and no existing value in database
        orig = self.db.get_discord_user(user_id)
        # Condition 1: Both are empty -> Reset to defaults
        if name is None and description is None:
            _new_name = interaction.user.display_name
            _new_description = "None"
            
        # Condition 2: At least one is provided -> Update given, keep existing for the other
        else:
            # Fallbacks for existing data if the user only updates one field
            existing_name = orig.preferred_name if orig and orig.preferred_name else interaction.user.display_name
            existing_desc = orig.descr if orig and orig.descr else "None"
            
            _new_name = name if name is not None else existing_name
            _new_description = description if description is not None else existing_desc
            
        res = self.db.update_discord_user(user_id, preferred_name=_new_name, descr=_new_description)
        if res:
            await interaction.response.send_message(f"Your preferred name has been set to {_new_name} and description to {_new_description}.")
        else:
            await interaction.response.send_message("Failed to update preferred name.")
        self.discord_user_cache[user_id] = UserDict(uid=user_id, name=interaction.user.name, preferred_name=_new_name, descr=_new_description)
    
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
    
async def setup(bot:MyBot):
    cog_instance = PersonaManagerCog(bot)
    await bot.add_cog(cog_instance)