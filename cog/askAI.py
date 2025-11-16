from asyncio.exceptions import TimeoutError
from collections import deque
from time import strftime
from typing import Optional, List

from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, app_commands, File
from discord.ext import commands, tasks
from cog.utilFunc import *
from config_loader import configToml
import json, re
from cog_dev.database_test import PersonaDatabase, PersonaVisibility, Persona
import openai

MEMOLEN = 16
THRESHOLD = 0.8575

modelConfig = configToml.get("llmChat", {})

class askAI(commands.Cog):
    __slots__ = ('bot', 'db')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.db = PersonaDatabase("llm_character_cards.db")  # Initialize the database for character cards
        self.round_robin_api_index = 0
        self.round_robin_api_collection = configToml['apiToken'].get('megaLLM', [])
        self.llm_apis = [openai.AsyncOpenAI(
            base_url = modelConfig["linkBase"],
            api_key = api_key,
        ) for api_key in self.round_robin_api_collection]
        self.persona_session_memory: dict[int, deque] = {} # deque of session messages
        self.persona_cache: dict[int, Persona] = {}  # Cache for persona objects
        self.selection_cache: dict[int, int] = {}  # Cache for user selected persona IDs
        
    async def cog_unload(self):
        for llm_api in self.llm_apis:
            await llm_api.close()
    
    async def llm_chat_v3(self, messages):
        """
        Asynchronous method to interact with a language model (LLM) API and generate a response 
        based on the provided messages.
        Args:
            messages (list): A list of dictionaries representing the conversation history. 
                             Each dictionary should contain keys like "role" (e.g., "user", "assistant") 
                             and "content" (the message text).
        Returns:
            dict: A dictionary containing the role and content of the LLM's response, or an error 
                  message if the API call fails. The dictionary structure is as follows:
                  - If successful:
                    {
                        "role": <str>,  # Role of the response (e.g., "assistant").
                        "content": <str>  # Content of the response.
                    }
                  - If an error occurs:
                    {
                        "rol": "error",
                        "msg": <str>  # JSON-formatted error message.
                    }
        Raises:
            openai.APIError: If an error occurs during the API call, it is caught and logged.
        Notes:
            - The method uses the OpenAI API to generate chat completions.
            - The `modelConfig["modelChat"]` specifies the model to be used.
            - The `temperature` parameter controls the randomness of the response.
            - The `max_tokens` parameter limits the length of the response.
            - The `completion.usage.total_tokens` is printed for debugging purposes.
        """
        
        try:
            completion = await self.llm_apis[self.round_robin_api_index].chat.completions.create(
                model=modelConfig["modelChat"],
                messages=messages,
                temperature=0.7,
                max_completion_tokens=4096,
                # n=1,
                # stop=None,
            )
            self.round_robin_api_index = (self.round_robin_api_index + 1) % len(self.llm_apis)
        except openai.APIError as e:
            print(f"OpenAI API error: {e}")
            return replyDict('error', json.dumps(e, indent=2, ensure_ascii=False))
        print(completion.usage.total_tokens)
        return replyDict(completion.choices[0].message.role, completion.choices[0].message.content)

    @app_commands.command(name="createpersona", description="Create a new LLM persona")
    @app_commands.describe(persona="Name of the persona", content="Content of the persona", visibility="Visibility of the persona (public/private)")
    async def create_persona(self, interaction: Interaction, persona: str, content: str, visibility: bool):
        """Create a new LLM persona with a popup Embed UI."""
        user_id = interaction.user.id
        visibility_enum = PersonaVisibility.PUBLIC if visibility else PersonaVisibility.PRIVATE

        # Create the persona
        _persona = self.db.create_persona(persona, content, user_id, visibility_enum)

        if not _persona:
            # Send a warning message if persona creation fails
            await interaction.response.send_message(
                content="You have reached the maximum limit of 5 personas. Please delete an existing persona to create a new one.",
                ephemeral=True
            )
            return

        # Create an embed to confirm the creation
        embed = Embed(title=f"{_persona.persona} (#{_persona.id}) Created", color=Color.green())
        embed.add_field(name="Visibility", value="Public" if visibility else "Private", inline=False)
        embed.add_field(name="Content", value=content[:1024], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)
        # Cache the newly created persona
        self.persona_cache[_persona.id] = _persona

    @commands.hybrid_command(name="editpersona")
    async def edit_persona(self, ctx: commands.Context, persona_id: int, persona: Optional[str] = None, content: Optional[str] = None, visibility: Optional[bool] = None):
        """Edit an existing LLM persona."""
        user_id = ctx.author.id
        updates = {}
        if persona:
            updates['persona'] = persona
        if content:
            updates['content'] = content
        if visibility is not None:
            updates['visibility'] = PersonaVisibility.PUBLIC.value if visibility else PersonaVisibility.PRIVATE.value
        if not updates:
            await ctx.send("No updates provided.")
            return
            
        success = self.db.update_persona(persona_id, user_id, **updates)
        if success:
            await ctx.send(f"Persona #{persona_id} updated successfully.")
            # Update cache
            if persona_id in self.persona_cache:
                _persona = self.persona_cache[persona_id]
                if 'persona' in updates:
                    _persona.persona = updates['persona']
                if 'content' in updates:
                    _persona.content = updates['content']
                if 'visibility' in updates:
                    _persona.visibility = PersonaVisibility(updates['visibility'])
        else:
            await ctx.send("Failed to update persona. Ensure you own the persona.")

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
            await ctx.send(f"Persona #{persona_id} selected successfully.")
        else:
            await ctx.send(f"Failed to select persona #{persona_id}.")
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

        persona_list = sepLines([f"ID: {p.id}, Name: {p.persona}, Visibility: {p.visibility.name}" for p in personas])
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
        if _persona.id in self.persona_session_memory:
            self.persona_session_memory[_persona.id].clear()
            await interaction.response.send_message(f"Session memory for persona '{_persona.persona}' has been erased.")
        else:
            await interaction.response.send_message("No session memory to erase for the selected persona.")
            
    @commands.Cog.listener()
    async def on_message(self, message: Message):
        user, messageText = message.author, message.content
        uid, userName = user.id, user.name
        displayName = user.display_name
        userName = re.sub(r'[.#]', '', userName)
        # ignore self messages
        if uid == self.bot.user.id:
            return

        # 2025/11/12 Refactor: Use mentions to trigger bot llm chat
        if self.bot.user.mentioned_in(message):
            # load persona selection from cache or db
            if uid not in self.selection_cache:
                self.selection_cache[uid] = self.db.get_selected_persona_id(uid)
                print(f'from db load persona # {self.selection_cache[uid]} for user {uid} selection')
                if self.selection_cache[uid] != -1:
                    # load persona into cache
                    db_persona = self.db.get_persona_no_check(self.selection_cache[uid])
                    if not db_persona:
                        await message.channel.send("Selected persona not found in database.\nPlease select another persona using /selectpersona.")
                        return
                    self.persona_cache[db_persona.id] = db_persona
                    
            persona_id = self.selection_cache.get(uid, -1)
            _persona = self.persona_cache.get(persona_id, None)
            if not _persona:
                await message.channel.send("No persona selected. Use /selectpersona to select one. (lvl 2)")
                return
            
            user_persona_pair = f'{wcformat(userName)}[{_persona.persona}]'
            # filter out mention bot part
            content = messageText.replace(self.bot.user.mention, '', 1).strip()
            print(f'{user_persona_pair}: {content}')
            prompt = replyDict('user', f'{displayName} said {content}', userName)
            setupmsg = replyDict('system', f'{_persona.content} 現在是{strftime("%Y-%m-%d %H:%M %a")}', 'system')
            async with message.channel.typing():
                if _persona.id not in self.persona_session_memory:
                    self.persona_session_memory[_persona.id] = deque(maxlen=MEMOLEN)
                chatMem = self.persona_session_memory[_persona.id]
                try:
                    reply = await self.llm_chat_v3([*chatMem, setupmsg.asdict, prompt.asdict])
                    if '<think>' in reply.content and '</think>' in reply.content:
                        # need to split the reply into thinking and reply
                        print('reply with thinking')
                        reply2 = reply.content
                        reply_think = reply2[reply2.find('<think>') + 7: reply2.find('</think>')]
                        reply.content = reply2[reply2.find('</think>') + 8:]
                        print(f'Thinking:\n{reply_think}')
                    await message.channel.send(reply.content)
                except TimeoutError:
                    await message.channel.send("The bot is currently unavailable. Please try again later.")
                except AssertionError:
                    if reply.role == 'error':
                        print(f'Reply error:\n{user_persona_pair}:\n{reply.content}')
                    await message.channel.send(f'{user_persona_pair} 發生錯誤，請聯繫主人\n{reply.content}')
                else:
                    # Only append to memory if no exception
                    # Only increase interaction count on successful reply
                    chatMem.append(prompt.asdict)
                    chatMem.append(reply.asdict)
                    self.db.increment_interaction_count(_persona.id, uid)
                    
            # elif ('-t' in text[:n]) and devChk(uid):
            #     return await message.channel.send(f'Total tokens: {chatTok[aiNum]}')
            
            # elif ('-log' in text[:n]) and devChk(uid):
            #     tmp = sepLines((m['content'] for m in chatMem[aiNum]))
            #     return await message.channel.send(f'Loaded memory: {len(chatMem[aiNum])}\n{tmp}')
            
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
        models = modelConfig["modelList"] 
        
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
        if model not in modelConfig["modelList"]:
            await interaction.response.send_message(
                f"錯誤：無效的模型 `{model}`", 
                ephemeral=True
            )
            return

        # Update your config
        modelConfig["modelChat"] = model
        
        # Send the confirmation
        await interaction.response.send_message(
            f"已切換至 `{model}`",
            ephemeral=True  # Confirmation messages are better as ephemeral
        )
    
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
