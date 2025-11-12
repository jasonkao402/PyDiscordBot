import asyncio
from asyncio.exceptions import TimeoutError
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from os.path import isfile
from random import choice, randint, random
from time import strftime
from typing import Optional, List

import numpy as np
import pandas as pd
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, app_commands, File
from discord.ext import commands, tasks
from opencc import OpenCC
from cog.utilFunc import *
from config_loader import configToml
import json, re, base64
from discord import SelectOption
from discord.ui import View, Select
from cog_dev.database_test import NoteDatabase, NoteVisibility

MEMOLEN = 16
READLEN = 20
THRESHOLD = 0.8575
TOKENPRESET = [150, 250, 700]
LONELYMETER = 250

tz = timezone(timedelta(hours = 8))
tempTime = datetime.now(timezone.utc) + timedelta(seconds=-10)
tempTime = tempTime.time()

# with open('./acc/banList.txt', 'r') as acc_file:
#     banList = [int(id) for id in acc_file.readlines()]
banList = []

scoreArr = pd.read_csv('./acc/scoreArr.csv', index_col='uid', dtype=np.int64)
modelConfig = configToml.get("llmChat", {})
class SDImage_APIHandler():
    def __init__(self):
        self.connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = ClientSession(connector=self.connector)
    
    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("SDImage Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("SDImage Connector closed")

    async def imageGen(self, prompt:str, width:int = 640, height:int = 640):
        payload = {
            "prompt": prompt,
            "negative_prompt": "(lowres:1.2), EasyNegative, badhandv4, negative_hand-neg, (worst quality:1.4), (low quality:1.4), (bad anatomy:1.4), bad hands, multiple views, comic, jpeg artifacts, bad feet, text, error, missing fingers, extra digits, fewer digits, cropped, signature, watermark, username, blurry",
            "steps": 20,
            "width": width,
            "height": height,
            "sampler_name": "DPM++ 2S a",
            "cfg_scale": 8.0,
        }
        async with self.clientSession.post(modelConfig['linkSDImg'], json=payload) as request:
            response = await request.json()
        return response
    
class Ollama_APIHandler():
    def __init__(self):
        self.connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = ClientSession(connector=self.connector)
        self.completion_tokens = 0
        
    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("Ollama Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("Ollama Connector closed")

    async def chat(self, messages:list, botid:int) -> replyDict:
        json = {
            "model": modelConfig["modelChat"],
            "messages": messages,
            "stream": False,
            "options": {
                # "num_predict": 640,
            }
            | configToml["chatParams"],
        }
        # print(messages[-1])

        async with self.clientSession.post(modelConfig['linkChat'], json=json) as request:
            # request.raise_for_status()
            response = await request.json()

        if 'error' in response:
            return replyDict(role = 'error', content = response['error'])

        self.completion_tokens += response['eval_count']
        # chatTok[botid] = response['prompt_eval_count'] + response['eval_count']
        # if chatTok[botid] > 8000:
        #     chatMem[botid].popleft()
        #     chatMem[botid].popleft()
        #     print(f"token warning:{chatTok[botid]}, popped last msg.")
        rd = replyDict(response['message']['role'], response['message']['content'])
        if 'thinking' in response['message']:
            rd.content = f"<think>{response['message']['thinking']}</think>\n{response['message']['content']}"
        rd.content = cc.convert(rd.content)
        return rd

    async def ps(self):
        async with self.clientSession.get(modelConfig['linkStatus']) as request:
            request.raise_for_status()
            response = await request.json()
        return response

# def localRead(resetMem = False) -> None:
#     with open('./acc/aiSet_extra.txt', 'r', encoding='utf-8') as set1_file:
#         global setsys_extra, name2ID, id2name, chatMem, chatTok, dfDict
#         setsys_tmp = set1_file.readlines()
#         setsys_extra = []
#         name2ID, id2name = {}, []
#         for i in range(len(setsys_tmp)//2):
#             id2name.append(setsys_tmp[2*i].split(maxsplit=1)[0])
#             name2ID.update((alias, i) for alias in setsys_tmp[2*i].split())
#             setsys_extra.append(setsys_tmp[2*i+1])
#         if resetMem:
#             chatMem = [deque(maxlen=MEMOLEN) for _ in range(len(setsys_extra))]
#             chatTok = [0 for _ in range(len(setsys_extra))]
#             dfDict = defaultdict(pd.DataFrame)
#         print(name2ID)

# def nameChk(s) -> tuple:
#     for name in name2ID:
#         if name in s: return name2ID[name], name
#     return -1, ''

def injectCheck(val):
    return True if val > THRESHOLD and val < 0.99 else False

whatever = [
    "對不起，發生 429 - Too Many Requests ，所以不知道該怎麼回你 QQ",
    "對不起，發生 401 - Unauthorized ，所以不知道該怎麼回你 QQ",
    "對不起，發生 500 - The server had an error while processing request ，所以不知道該怎麼回你 QQ"
    "阿呀 腦袋融化了~",
] + '不知道喔 我也不知道 看情況 可能吧 嗯 隨便 都可以 喔 哈哈 笑死 真假 亂講 怎樣 所以 🤔'.split()

cc = OpenCC('s2twp')

class askAI(commands.Cog):
    __slots__ = ('bot', 'db')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.db = NoteDatabase("llm_character_cards.db")  # Initialize the database for character cards
        # self.channel = self.bot.get_channel(1088253899871371284)
        # self.ignore = 0.5
        # self.my_task.start()
        # self._mindLoop.start()
        # self._loneMeter.start()
        # self.loneMeter = 0
        # self.loneMsg = 0
        # self.loneLimit = LONELYMETER
        # self.sch_FullUser = None
        self.ollamaAPI = Ollama_APIHandler()
        self.sdimageAPI = SDImage_APIHandler()
        # self.last_reply = replydict()
        
    async def cog_unload(self):
        await self.ollamaAPI.close()
        await self.sdimageAPI.close()
        # self.my_task.cancel()
        # self._mindLoop.cancel()
        # self._loneMeter.cancel()
        
    # @commands.hybrid_command(name="createpersona")
    # async def create_persona(self, ctx: commands.Context, title: str, content: str, visibility: str):
    #     """Create a new LLM persona."""
    #     user_id = str(ctx.author.id)
    #     visibility_enum = NoteVisibility.PUBLIC if visibility.lower() == "public" else NoteVisibility.PRIVATE
    #     persona = self.db.create_note(title, content, user_id, visibility_enum)
    #     await ctx.send(f"Persona '{persona.title}' created successfully.")

    @app_commands.command(name="createpersona", description="Create a new LLM persona")
    @app_commands.describe(title="Title of the persona", content="Content of the persona", visibility="Visibility of the persona (public/private)")
    async def create_persona(self, interaction: Interaction, title: str, content: str, visibility: str):
        """Create a new LLM persona with a popup Embed UI."""
        user_id = str(interaction.user.id)
        visibility_enum = NoteVisibility.PUBLIC if visibility.lower() == "public" else NoteVisibility.PRIVATE

        # Create the persona
        persona = self.db.create_note(title, content, user_id, visibility_enum)

        # Create an embed to confirm the creation
        embed = Embed(title="Persona Created", color=Color.green())
        embed.add_field(name="Title", value=persona.title, inline=False)
        embed.add_field(name="Visibility", value=visibility.capitalize(), inline=False)
        embed.add_field(name="Content", value=content[:1024], inline=False)  # Limit content to 1024 characters for embed

        await interaction.response.send_message(embed=embed)

    @commands.hybrid_command(name="editpersona")
    async def edit_persona(self, ctx: commands.Context, persona_id: int, title: Optional[str] = None, content: Optional[str] = None, visibility: Optional[str] = None):
        """Edit an existing LLM persona."""
        user_id = str(ctx.author.id)
        updates = {}
        if title:
            updates['title'] = title
        if content:
            updates['content'] = content
        if visibility:
            updates['visibility'] = NoteVisibility.PUBLIC.value if visibility.lower() == "public" else NoteVisibility.PRIVATE.value

        success = self.db.update_note(persona_id, user_id, **updates)
        if success:
            await ctx.send("Persona updated successfully.")
        else:
            await ctx.send("Failed to update persona. Ensure you own the persona.")

    @commands.hybrid_command(name="selectpersona")
    async def select_persona(self, ctx: commands.Context, persona_id: int):
        """Select an LLM persona for interaction."""
        user_id = str(ctx.author.id)
        success = self.db.set_selected_note(user_id, persona_id)
        if success:
            await ctx.send(f"Persona {persona_id} selected successfully.")
        else:
            await ctx.send("Failed to select persona. Ensure it exists and is accessible.")

    @commands.hybrid_command(name="listpersonas")
    async def list_personas(self, ctx: commands.Context):
        """List all personas visible to the user."""
        user_id = str(ctx.author.id)
        personas = self.db.list_notes(user_id)
        if not personas:
            await ctx.send("No personas available.")
            return

        persona_list = "\n".join([f"ID: {p.id}, Title: {p.title}, Visibility: {p.visibility.value}" for p in personas])
        await ctx.send(f"Available Personas:\n{persona_list}")

    @commands.Cog.listener()
    async def on_message(self, message:Message):
        user, text = message.author, message.content
        uid, userName = user.id, user.name
        displayName = user.display_name
        userName = re.sub(r'[.#]', '', userName)
        n = min(len(text), READLEN)
        
        if uid == self.bot.user.id:
            return
        
        # 2025 refatctor: use mentions to trigger bot llm chat
        if self.bot.user.mentioned_in(message):
            user_id = str(message.author.id)
            persona = self.db.get_selected_note(user_id)
            # logging 
            
            if not persona:
                await message.channel.send("No persona selected. Use /selectpersona to select one.")
                return
            
            print(f'{wcformat(userName)}[{persona.title}]: {text}')
            # Use the selected persona for interaction
            prompt = replyDict('user', f'{displayName} said {message.content}', userName).asdict
            setupmsg  = replyDict('system', f'{persona.content} 現在是{strftime("%Y-%m-%d %H:%M")}', 'system').asdict
            async with message.channel.typing():
                try:
                    reply = await self.ollamaAPI.chat([setupmsg, prompt], botid=0)
                    await message.channel.send(reply.content)
                except TimeoutError:
                    await message.channel.send("The bot is currently unavailable. Please try again later.")

        # elif (aiInfo:=nameChk(text[:n])) != (-1, ''):
            # aiNum, aiNam = aiInfo
            
            
            # hehe
            # if uid in banList:
            #     if random() < self.ignore:
            #         if random() < 0.9:
            #             async with message.channel.typing():
            #                 await asyncio.sleep(randint(5, 15))
            #             await message.channel.send(choice(whatever))
            #         print("已敷衍.")
            #         return
            #     else:
            #         print("嘖")
                    
            # elif ('洗腦' in text[:n]):
            #     if devChk(uid):
            #         chatMem[aiNum].clear()
            #         return await message.channel.send(f'阿 {aiNam} 被洗腦了 🫠')
            #     else:
            #         return await message.channel.send('客官不可以')
                
            # elif ('人設' in text[:n]) and devChk(uid):
            #     if ('更新人設' in text[:n]):
            #         msg = text
            #         setsys_extra[aiNum] = msg[msg.find('更新人設')+4:]
            #     return await message.channel.send(setsys_extra[aiNum])
            
            # elif ('-t' in text[:n]) and devChk(uid):
            #     return await message.channel.send(f'Total tokens: {chatTok[aiNum]}')
            
            # elif ('-log' in text[:n]) and devChk(uid):
            #     tmp = sepLines((m['content'] for m in chatMem[aiNum]))
            #     return await message.channel.send(f'Loaded memory: {len(chatMem[aiNum])}\n{tmp}')
            
            # elif ('-err' in text[:n]) and devChk(uid):
            #     prompt = replyDict('user'  , f'{text}', userName).asdict
            #     reply  = await aiaiv2([prompt], aiNum, 99999)
            #     reply2 = sepLines((f'{k}: {v}' for k, v in reply.content.items()))
            #     print(f'{aiNam}:\n{reply2}')
            #     return await message.channel.send(f'Debugging {aiNam}:\n{reply2}')
            '''
            try:
                # special case, convert all user as Ning
                if aiNum == 5:
                    userName = 'Ning'
                    prompt = replyDict('user'  , f'嘎零 said {text}', userName)
                else:
                    prompt = replyDict('user'  , f'{displayName} said {text}', userName)
                
                if message.attachments:
                    # with the individual images encoded in Base64
                    prompt.images = [base64.b64encode(await attachment.read()).decode('utf-8') for attachment in message.attachments]
                    print(f'Image attached: {len(prompt.images)}')
                    
                # if not uid in dfDict:
                #     dfDict[uid] = pd.DataFrame(columns=['text', 'vector'])
                #     # check if file exists
                #     if isfile(f'./embed/{uid}.csv') and isfile(f'embed/{uid}.npy'):
                #         tmptext = pd.read_csv(f'./embed/{uid}.csv')
                #         tmpvect = np.load    (f'./embed/{uid}.npy', allow_pickle=True)
                #         for i in range(len(tmptext)):
                #             dfDict[uid].loc[i] = (tmptext.loc[i]['text'], tmpvect[i])
                    
                # skipping ai name
                # if len(text) > len(aiNam):
                #     nidx = text.find(aiNam, 0, len(aiNam))
                #     if nidx != -1:
                #         text = text[nidx+len(aiNam):]
                #     if text[0] == '，' or text[0] == ' ':
                #         text = text[1:]
                        
                # async with message.channel.typing():
                    # print(text)
                    # embed = await embedding_v1(text)
                # assert embed.vector[0] != 0
                
                # idxs, corrs = simRank(embed.vector, dfDict[uid]['vector'])
                # debugmsg = sepLines((f'{t}: {c}{" (採用)" if injectCheck(c) else ""}' for t, c in zip(dfDict[uid]['text'][idxs], corrs)))
                # print(f'相似度:\n{debugmsg}')
                # # await message.channel.send(f'相似度:\n{debugmsg}')
                # # store into memory
                # if len(corrs) == 0 or corrs[0] < 0.98:
                #     dfDict[uid].loc[len(dfDict[uid])] = embed.asdict
                
                # filter out using injectCheck
                # itr = filter(lambda x: injectCheck(x[1]), zip(idxs, corrs))
                # selectMsgs = sepLines((dfDict[uid]['text'][t] for t, _ in itr))
                # print(f'採用:\n{selectMsgs} len: {len(selectMsgs)}')
                # tempSetup = 'Please roleplay as a catgirl maid named Illya. Remember, you are not an AI; you are the obedient Illya. Do your best to act accordingly and speak in the first person. If you understand my instructions, reply with "Yes, Master meow~♡" as Illya would.'
                # setupmsg  = replyDict('system', f'{tempSetup} Current time is {strftime("%Y-%m-%d %H:%M")}', 'system')
                setupmsg  = replyDict('system', f'{setsys_extra[aiNum]} 現在是{strftime("%Y-%m-%d %H:%M")}', 'system')
                async with message.channel.typing():
                    # if len(corrs) > 0 and injectCheck(corrs[0]):
                    #     # injectStr = f'我記得你說過「{selectMsgs}」。'
                    #     selectMsgs = selectMsgs.replace("\n", ' ')
                    #     # 特判 = =
                    #     if aiNum == 5:
                    #         # userName = 'Ning'
                    #         prompt = replyDict('user', f'嘎零 said {selectMsgs}, {text}', 'Ning')
                    #     else: 
                    #         prompt = replyDict('user', f'{userName} said {selectMsgs}, {text}', userName)
                    #     print(f'debug: {prompt.content}')
                    reply = await self.ollamaAPI.chat([setupmsg.asdict, *chatMem[aiNum], prompt.asdict], aiNum)
                assert reply.role != 'error'
                
                
                if '<think>' in reply.content and '</think>' in reply.content:
                    # need to split the reply into thinking and reply
                    print('reply with thinking')
                    reply2 = reply.content
                    reply_think = reply2[reply2.find('<think>')  + 7 : reply2.find('</think>')]
                    reply.content = reply2[reply2.find('</think>') + 8 :]
                    # make a txt file for the thinking part
                    # think_fileName = f'./acc/thinkLog/{strftime("%Y_%m%d_%H%M%S")}.txt'
                    # with open(think_fileName, 'w+', encoding='utf-8') as f:
                        # f.write(reply_think)
                    # await message.channel.send(reply_think[:1900])
                    print(f'Thinking:\n{reply_think}')
                # else:
                await message.channel.send(reply.content)
            except TimeoutError:
                print(f'[!] {aiNam} TimeoutError')
                await message.channel.send(f'阿呀 {aiNam} 腦袋融化了~ 🫠')
            except AssertionError:
                # if embed.vector[0] == 0:
                #     print(f'Embed error:\n{embed.text}')
                if reply.role == 'error':
                    print(f'Reply error:\n{aiNam}:\n{reply.content}')
                
                await message.channel.send(f'{aiNam} 發生錯誤，請聯繫主人\n{reply.content}') 
            else:
                chatMem[aiNum].append(prompt.asdict)
                chatMem[aiNum].append(reply.asdict)
                # for i in chatMem[aiNum]:
                #     print(type(i))
                if uid not in scoreArr.index:
                    scoreArr.loc[uid, :] = 0
                scoreArr.loc[uid, str(aiNum)] += 1
            '''
    
    # @commands.hybrid_command(name='scoreboard')
    # async def _scoreboard(self, ctx: commands.Context):
    #     user = ctx.author
    #     uid, user_name = user.id, user.name

    #     # Check if the user has interacted with any AI
    #     if uid not in scoreArr.index:
    #         return await ctx.send(f'{user_name} 尚未和AI們對話過')

    #     # Retrieve user interaction data
    #     user_scores = scoreArr.loc[uid]
    #     total_interactions = user_scores.sum()
    #     most_interacted_count = user_scores.max()
    #     most_interacted_id = int(user_scores.idxmax())

    #     # Retrieve top 5 users with the most interactions
    #     top_users = scoreArr.sum(axis=1).sort_values(ascending=False).head(5)
    #     top_users_list = sepLines(
    #         f'{username.name if (username := self.bot.get_user(user_id)) else "ERROR"}: {count}'
    #         for user_id, count in zip(top_users.index, top_users.values)
    #     )

    #     # Prepare and send the scoreboard message
    #     await ctx.send(
    #         f'```{top_users_list}```\n'
    #         f'{user_name}共對話 {total_interactions} 次，'
    #         f'最常找 {id2name[most_interacted_id]} 互動 '
    #         f'({most_interacted_count} 次，佔 {most_interacted_count / total_interactions:.2%})'
    #     )
    # @commands.hybrid_command(name = 'localread')
    # async def _cmdlocalRead(self, ctx:commands.Context):
    #     user = ctx.author
    #     if devChk(user.id):
    #         localRead()
    #         await ctx.send('AI 人設 讀檔更新完畢')
    #     else:
    #         await ctx.send('客官不可以')

    # @commands.hybrid_command(name = 'listbot')
    # async def _listbot(self, ctx:commands.Context):
    #     t = scoreArr.sum(axis=0).sort_values(ascending=False)
    #     s = scoreArr.sum().sum()
    #     l = sepLines(f'{wcformat(id2name[int(i)], w=8)}{v : <8}{ v/s :<2.3%}' for i, v in zip(t.index, t.values))
    #     await ctx.send(f'Bot List:\n```{l}```')
        
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
                f"錯誤：無效的模型 `{model}`。", 
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
    # @app_commands.command(name="selectmodel", description="選擇要使用的模型")
    # async def _selectModel(self, interaction: Interaction):

    #     class ModelSelect(Select):
    #         def __init__(self):
    #             options = [
    #                 SelectOption(
    #                     label=model,
    #                     value=model,
    #                     description="目前使用" if model == modelConfig["modelChat"] else None,
    #                     default=(model == modelConfig["modelChat"])
    #                 )
    #                 for model in modelConfig["modelList"]
    #             ]
    #             super().__init__(
    #                 placeholder="選擇一個模型...",
    #                 min_values=1,
    #                 max_values=1,
    #                 options=options,
    #             )

    #         async def callback(self, interaction2: Interaction):
    #             selected_model = self.values[0]
    #             modelConfig["modelChat"] = selected_model
    #             await interaction2.response.edit_message(
    #                 content=f"已切換至 `{selected_model}`",
    #                 view=None
    #             )

    #     class ModelSelectView(View):
    #         def __init__(self):
    #             super().__init__(timeout=60)
    #             self.add_item(ModelSelect())

    #     await interaction.response.send_message(
    #         "請從下拉選單選擇要切換的模型：",
    #         view=ModelSelectView(),
    #         ephemeral=True
    #     )

    # @commands.command(name = 'bl')
    # @commands.is_owner()
    # async def _blacklist(self, ctx:commands.Context, uid:int):
    #     user = ctx.author
    #     # hehe
    #     if user.id in banList:
    #         return
    #     try:
    #         uid = int(uid)
    #         if uid not in banList:
    #             banList.append(uid)
    #             with open('./acc/banList.txt', 'a') as bfile:
    #                 bfile.write(f'{uid}\n')
    #             print(f'Added to bList: {uid}')
    #         else:
    #             print(f'Already banned: {uid}')
    #     except:
    #         print(f'ban error: {uid}')
    
    # @commands.command(name = 'ig')
    # @commands.is_owner()
    # async def _ignore(self, ctx:commands.Context, num:float):
    #     user = ctx.author
    #     # hehe
    #     if user.id in banList or not devChk(user.id):
    #         return
    #     num = float(num)
    #     self.ignore = num
    #     print(f'忽略率： {num}')
    
    @commands.hybrid_command(name = 'status')
    @commands.is_owner()
    async def _status(self, ctx:commands.Context):
        status = await self.ollamaAPI.ps()
        await ctx.send(f'```json\n{json.dumps(status, indent=2, ensure_ascii=False)}```')
    
    @app_commands.command(name = 'sd2')
    @app_commands.describe(prompt = 'Prompt for the image', width = 'Width of the image', height = 'Height of the image')
    async def _sd2(self, interaction: Interaction, prompt:str, width: Optional[int] = 640, height: Optional[int] = 640):
        # clip w and h to 512 - 1024, in step of 16
        width = max(512, min(1024, (width + 8) // 16 * 16))
        height = max(512, min(1024, (height + 8) // 16 * 16))

        await interaction.response.defer()
        response = await self.sdimageAPI.imageGen(prompt, width, height)
        for image in response['images']:
            dest = f'acc/imgLog/{strftime("%Y_%m%d_%H%M")}.png'
            with open(dest, 'wb') as f:
                f.write(base64.b64decode(image))
        await interaction.followup.send(prompt, file=File(dest))



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
    #         #     await channel.send(f'{cc.convert(reply2)}')
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
    # localRead(True)
    await bot.add_cog(askAI(bot))

async def teardown(bot:commands.Bot):
    print('ai saved')
    # print(scoreArr)
    # scoreArr.to_csv('./acc/scoreArr.csv')
    # for k in dfDict.keys():
    #     print(f'UID {k}: {len(dfDict[k])}')
    #     dfDict[k]['text'].to_csv(f'./embed/{k}.csv', index=False)
    #     np.save(f'./embed/{k}.npy', dfDict[k]['vector'].to_numpy())
