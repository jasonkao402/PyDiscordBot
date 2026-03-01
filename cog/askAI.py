from collections import deque
from math import exp
from time import strftime
from typing import Optional, List

from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, app_commands, File
from discord.ext import commands, tasks
from cog.utilFunc import sepLines, wcformat
from cog.ui_modal import CreatePersonaModal, EditPersonaModal
from config_loader import configToml
import json, re
from cog_dev.database_test import PersonaDatabase, PersonaVisibility, Persona

import base64
from openai import AsyncOpenAI
# from google import genai
from google.genai import types as gtypes, errors

MEMOLEN = 26
THRESHOLD = 0.8575

chat_config: dict[str, str] = configToml.get("llmChat", "")
link_config: dict[str, str] = configToml.get("llmLink", "")
llm_base_url = link_config.get("link_deepseek", "")

http_options = gtypes.HttpOptions(
    # base_url=str(configToml["llmLink"]["link_build_server"]), timeout=60
    # base_url=str(link_config.get("link_gcli2api", "")), timeout=60
    base_url=str(llm_base_url), timeout=60
)
class askAI(commands.Cog):
    __slots__ = ('bot', 'db')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.db = PersonaDatabase("llm_character_cards.db")  # Initialize the database for character cards
        self.ban_list = configToml.get("auth", {}).get("ban_list", [])
        self.round_robin_api_index = 0
        self.api_call_count = 0  # Counter to track the number of API calls
        self.api_switch_threshold = 5  # Number of calls before switching to the next API
        self.round_robin_api_collection = configToml['apiToken'].get('deepseek_llm', [])
        # self.llm_apis = [genai.Client(
        #     api_key=api_key,
        #     http_options=http_options,
        # ) for api_key in self.round_robin_api_collection]
        self.llm_apis = [AsyncOpenAI(api_key=api_key, base_url=llm_base_url) for api_key in self.round_robin_api_collection]
        self.persona_session_memory: dict[int, deque] = {} # deque of session messages
        self.persona_cache: dict[int, Persona] = {}  # Cache for persona objects
        self.selection_cache: dict[int, int] = {}  # Cache for user selected persona IDs
        print(f'Loaded askAI cog with {len(self.llm_apis)} LLM API clients @ {llm_base_url}.')
        # print("ban list:")
        # print(', '.join(str(uid) for uid in self.ban_list))
        
    async def cog_unload(self):
        for llm_api in self.llm_apis:
            await llm_api.close()

    async def llm_chat_v5(self, messages: list[dict], system: str, image: Optional[gtypes.Part] = None) -> str:
        """
        messages: list of strings (model / user messages)
        system: system instruction string
        """
        try:
            # Google API
            """
            # 將 messages 轉成 Google GenAI 的 contents
            message_contents = [
                gtypes.Content(parts=list([gtypes.Part(text=msg['content'])]), role=msg["role"]) for msg in messages
            ]
            
            if image:
                message_contents.append(
                    gtypes.Content(parts=[image], role="user")
                )
            content_config = gtypes.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=4096,
                thinking_config=gtypes.ThinkingConfig(
                    thinking_level=gtypes.ThinkingLevel.LOW
                ),
            )
            response = await self.llm_apis[self.round_robin_api_index].aio.models.generate_content(
                model=chat_config["modelChat"],
                contents=list(message_contents),
                config=content_config,
            )
            """
            # Deepseek API / OpenAI API
            response = await self.llm_apis[self.round_robin_api_index].chat.completions.create(
                model=chat_config["modelChat"],
                messages=[
                    {"role": "system", "content": system},
                    *[
                        {
                            "role": msg["role"],
                            "content": msg["content"]
                        } for msg in messages
                    ]
                ],
                max_tokens=4096,
            )
        except errors.APIError as e:
            api_error = f"[{e.code}]{e.message}"
            print(f"GenAI Error: {api_error}\n---")
            return api_error

        response_text = str(response.choices[0].message.content)
        
        # if response.usage_metadata:
            # print(response.usage_metadata.total_token_count)
        if response.usage:
            print(f'Token usage: {response.usage.total_tokens} tokens')
        return response_text
    
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
        # Update session memory
        if persona_id not in self.persona_session_memory:
            self.persona_session_memory[persona_id] = deque(maxlen=MEMOLEN)
            
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
        if _persona.uid in self.persona_session_memory:
            self.persona_session_memory[_persona.uid].clear()
            await interaction.response.send_message(f"Session memory for {_persona.persona} has been erased.")
        else:
            await interaction.response.send_message("No session memory to erase for the selected persona.")
            
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
    
    async def handle_llm_trigger(self, message: Message, user_id: int, user_name: str, display_name: str):
        """Handle the logic for detecting and triggering the LLM feature."""
        # Load persona selection from cache or database
        if user_id not in self.selection_cache:
            self.selection_cache[user_id] = self.db.get_selected_persona_uid(user_id)
            print(f'from db load persona # {self.selection_cache[user_id]} for user {user_id} selection')
            if self.selection_cache[user_id] != -1:
                # Load persona into cache
                db_persona = self.db.get_persona_no_check(self.selection_cache[user_id])
                if not db_persona:
                    await message.channel.send("Selected persona not found in database.\nPlease select another persona using /selectpersona.")
                    return
                self.persona_cache[db_persona.uid] = db_persona

        persona_id = self.selection_cache.get(user_id, -1)
        _persona = self.persona_cache.get(persona_id, None)
        if not _persona:
            await message.channel.send("No persona selected. Use /selectpersona to select one. (lvl 2)")
            return

        user_persona_pair = f'{wcformat(user_name)}[{_persona.persona}]'
        # Filter out mention bot part
        content = message.content.replace(self.bot.user.mention, '', 1).strip()
        print(f'{user_persona_pair}: {content}')

        system_instruction = f'{_persona.content}\n最新對話發生在:{strftime("%Y/%m/%d %H:%M %a")}'
        prompt = {'role': 'user', 'content': f'{display_name} said {content}'}

        async with message.channel.typing():
            if _persona.uid not in self.persona_session_memory:
                self.persona_session_memory[_persona.uid] = deque(maxlen=MEMOLEN)
            chatMem = self.persona_session_memory[_persona.uid]
            try:
                if message.attachments:
                    # Handle image attachments
                    decoded_image = base64.b64encode(await message.attachments[0].read()).decode('utf-8')
                    # print(f'Encoded image size: {len(decoded_image)} characters')
                    image_part = gtypes.Part(
                        inline_data=gtypes.Blob(
                            mime_type="image/jpeg",
                            data=base64.b64decode(decoded_image),
                        ),
                        media_resolution=gtypes.MediaResolution.MEDIA_RESOLUTION_LOW
                    )
                    reply_content = await self.llm_chat_v5([*chatMem, prompt], system_instruction, image=image_part)
                else:
                    reply_content = await self.llm_chat_v5([*chatMem, prompt], system_instruction)

                # Validate and parse the JSON response
                try:
                    l_cursor = reply_content.find('```json') + 7
                    r_cursor = reply_content.rfind('```')
                    if l_cursor == -1 or r_cursor == -1 or l_cursor >= r_cursor:
                        response_data = json.loads(reply_content)
                    else:
                        response_data = json.loads(reply_content[l_cursor:r_cursor])
                    what_to_reply = response_data.get("what_to_reply", "無法解析的回覆")
                    delta_affection = response_data.get("delta_affection", 0)

                    # Send the parsed response
                    if len(what_to_reply) > 2000:
                        print(f'GenAI Response: {what_to_reply}')
                        return what_to_reply[:1980] + "\n...[truncated]"
                    
                    await message.channel.send(f"{what_to_reply}\n\n* 好感度變化: {delta_affection}")
                    print(f"Delta Affection: {delta_affection}")
                    reply_content = what_to_reply  # Update reply_content for memory logging
                
                except json.JSONDecodeError:
                    if len(reply_content) > 2000:
                        print(f'GenAI Response: {reply_content}')
                        return reply_content[:1980] + "\n...[truncated]"
                    await message.channel.send(reply_content)
                    print(f"Invalid JSON response, sent as plain text.")
                    
                except ValueError:
                    await message.channel.send(reply_content)
                    print(f"No JSON code block found, sent as plain text.")

            except TimeoutError:
                await message.channel.send("The bot is currently unavailable. Please try again later.")
            except Exception as e:
                print(f'Reply error:\n{user_persona_pair}:\n{e}')
                await message.channel.send(f'{user_persona_pair} 發生錯誤，請聯繫主人\n{e}')
            else:
                # Only append to memory if no exception
                chatMem.append(prompt)
                chatMem.append({'role': 'assistant', 'content': reply_content})
                self.db.increment_interaction_count(_persona.uid, user_id)

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        user, message_text = message.author, message.content
        user_id, user_name = user.id, user.name
        display_name = user.display_name
        user_name = re.sub(r'[.#]', '', user_name)

        # Ignore self messages
        if user_id == self.bot.user.id:
            return
        if user_id in self.ban_list:
            print(f'Ignored message from banned user {user_name} ({user_id})')
            return

        # Use mentions to trigger bot LLM chat
        if self.bot.user.mentioned_in(message) and not message.mention_everyone:
            roles = getattr(user, 'roles', [])  # Ensure user.roles exists
            if not any(role.id in configToml.get("auth", {}).get("roleList", []) for role in roles):
                extra_msg = 'does not have the required role to interact with the bot.'
                print(f'User {user_name} ({user_id}) {extra_msg}')
                await message.channel.send(f'User {user_name} {extra_msg}')
                return
            await self.handle_llm_trigger(message, user_id, user_name, display_name)

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
    
    async def llm_create_memory(self, messages: list[dict]) -> list[dict]:
        """Convert messages to the format required by the LLM API."""
        
        return []
    # @commands.hybrid_command(name = 'status')
    # @commands.is_owner()
    # async def _status(self, ctx:commands.Context):
    #     # status = await self.llm_api.ps()
    #     connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
    #     clientSession = ClientSession(connector=connector)
        
    #     async with clientSession.get(modelConfig['linkStatus']) as request:
    #         request.raise_for_status()
    #         status = await request.json()
    #     await ctx.send(f'```json\n{json.dumps(status, indent=2, ensure_ascii=False)}```')
    
    # TODO: gotowork command: I want to create a gameplay chatbot mechanic similar to earning hourly wages with some added randomnesswhile staying true to the character's backstory
    # @app_commands.command(name = 'schedule')
    # async def _schedule(self, interaction: Interaction, delay_time:int, text:Optional[str] = ''):
    #     dt = datetime.now(timezone.utc) + timedelta(seconds=int(delay_time))
        
    #     self.channel = interaction.channel
    #     self.sch_FullUser = interaction.user
    #     self.sch_User = str(interaction.user).replace('.', '')
    #     self.sch_Text = text if text != '' else '好無聊，想找伊莉亞聊天，要聊甚麼呢?'
        
    #     tsk = self._loneMeter
    #     if not tsk.is_running():
    #         print(f'start task {tsk.__name__}')
    #         tsk.start()
    #     tsk.change_interval(seconds=4)
    #     tsk.restart()
        
    #     tsk = self.my_task
    #     if not tsk.is_running():
    #         print('start task')
    #         tsk.start()
    #     tsk.change_interval(time=dt.time())
    #     tsk.restart()
        
    #     tsk = self._mindLoop
    #     if not tsk.is_running():
    #         print('start task')
    #         tsk.start()
            
    #     time_points = np.random.exponential(60/5, (5))
    #     time_points = np.round(time_points, 3)
    #     cumulative_times = np.cumsum(time_points)
    #     cur_time = datetime.now(timezone.utc)
        
    #     seq_t = [(cur_time + timedelta(seconds = i)).time() for i in cumulative_times]
    #     for i in seq_t:
    #         print(f'{i}')
    #     tsk.change_interval(time=seq_t)
    #     tsk.restart()
        
    #     embed = Embed(title = "AI貓娘伊莉亞", description = f"伊莉亞來找主人 {self.sch_User} 了！", color = Color.random())
    #     embed.add_field(name = "時間", value = utctimeFormat(tsk.next_iteration))
    #     embed.add_field(name = "狀態", value = self.my_task.is_running())
    #     await interaction.response.send_message(embed = embed)
        
    # @tasks.loop(time=tempTime)
    # async def my_task(self):
    #     channel = self.channel
    #     aiNam = id2name[0]
    #     if channel:
    #         print("debugging")
    #         # setupmsg  = replyDict('system', f'{setsys_extra[0]} 現在是{strftime("%Y-%m-%d %H:%M")}', 'system')
    #         # try:
    #         #     async with channel.typing():
    #         #         prompt = replyDict('user', f'{self.sch_User} said {self.sch_Text}', self.sch_User)
    #         #         reply = await aiaiv2([setupmsg.asdict, *chatMem[0], prompt.asdict], 0, TOKENPRESET[0])
    #         #     assert reply.role != 'error'
                
    #         #     reply2 = reply.content
    #         # except TimeoutError:
    #         #     print(f'[!] {aiNam} TimeoutError')
    #         #     await channel.send(f'阿呀 {aiNam} 腦袋融化了~ 🫠')
    #         # except AssertionError:
    #         #     if reply.role == 'error':
    #         #         reply2 = sepLines((f'{k}: {v}' for k, v in reply.content.items()))
    #         #         print(f'Reply error:\n{aiNam}:\n{reply2}')
                
    #         #     await channel.send(f'{aiNam} 發生錯誤，請聯繫主人\n{reply2}')
    #         # else:
    #         #     chatMem[0].append(reply.asdict)
    
    # @tasks.loop(time=tempTime)
    # async def _mindLoop(self):
    #     channel = self.channel
    #     user = self.sch_FullUser
    #     # await channel.send(f'{user.mention} {talkList[self._mindLoop.current_loop]}')
    #     # print(f'{user} {talkList[self._mindLoop.current_loop]}')
    
    # @tasks.loop(time=tempTime)
    # async def _loneMeter(self):
    #     SCALE = 10
        
    #     channel = self.channel
    #     user = self.sch_FullUser
    #     limit = self.loneLimit
    #     self.loneMeter += np.random.poisson(SCALE)
    #     print(f'loneMeter: {self.loneMeter}/{limit}')
    #     if self.loneMeter > limit:
    #         self.loneLimit = LONELYMETER/2 + np.random.exponential(LONELYMETER/2)
    #         consume = np.random.poisson(10*SCALE)
    #         self.loneMeter -= consume
            
    #         # await channel.send(f'{talkList[self.loneMsg % len(talkList)]}\n({-consume} energy) (meter: {self.loneMeter}/{limit}))')
    #         self.loneMsg += 1

async def setup(bot:commands.Bot):
    await bot.add_cog(askAI(bot))

async def teardown(bot:commands.Bot):
    print('ai saved')
