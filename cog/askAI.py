import asyncio
from asyncio.exceptions import TimeoutError
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from os.path import isfile
from random import choice, randint, random
from time import strftime
from typing import Optional

import numpy as np
import pandas as pd
from aiohttp import ClientSession, ClientTimeout, TCPConnector
from discord import Client as DC_Client
from discord import Color, Embed, Interaction, Message, app_commands
from discord.ext import commands, tasks
from opencc import OpenCC
from cog.utilFunc import *
from pydiscord import configToml
import json, re

MEMOLEN = 8
READLEN = 20
THRESHOLD = 0.8575
TOKENPRESET = [150, 250, 700]
LONELYMETER = 250

tz = timezone(timedelta(hours = 8))
tempTime = datetime.now(timezone.utc) + timedelta(seconds=-10)
tempTime = tempTime.time()

with open('./acc/banList.txt', 'r') as acc_file:
    banList = [int(id) for id in acc_file.readlines()]

scoreArr = pd.read_csv('./acc/scoreArr.csv', index_col='uid', dtype=np.int64)
class OllamaAPIHandler():
    def __init__(self):
        self.connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = ClientSession(connector=self.connector)
    
    def close(self):
        if not self.connector.closed:
            self.connector.close()
            print("Connector closed")
        if not self.clientSession.closed:
            self.clientSession.close()
            print("Client session closed")
            
    async def chat(self, messages:list, botid:int, tokens:int) -> replyDict:
        json = {
            "model": configToml['LLM']['model'],
            "messages": messages,
            "max_tokens": min(tokens, 2500 - chatTok[botid]),
            "seed": 42,
            "stop": ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"],
            "temperature": configToml['LLM']['temperature'],
            "repeat_penalty": 1.25,
            "mirostat_mode": 2,
            "stream": False,
        }
        async with self.clientSession.post(configToml['linkChat'], json=json) as request:
            # request.raise_for_status()
            response = await request.json()
            
        if 'error' in response:
            return replyDict(role = 'error', content = response['error'])
        
        chatTok[botid] = response['prompt_eval_count'] + response['eval_count']
        if chatTok[botid] > 3000:
            chatMem[botid].popleft()
            chatMem[botid].popleft()
            print(f"token warning:{chatTok[botid]}, popped last msg.")
        rd = replyDict(**response['message'])
        rd.content = cc.convert(rd.content)
        return rd
    
    async def ps(self):
        async with self.clientSession.get(configToml['stat']) as request:
            request.raise_for_status()
            response = await request.json()
        return response
        
def localRead(resetMem = False) -> None:
    with open('./acc/aiSet_extra.txt', 'r', encoding='utf-8') as set1_file:
        global setsys_extra, name2ID, id2name, chatMem, chatTok, dfDict
        setsys_tmp = set1_file.readlines()
        setsys_extra = []
        name2ID, id2name = {}, []
        for i in range(len(setsys_tmp)//2):
            id2name.append(setsys_tmp[2*i].split(maxsplit=1)[0])
            name2ID.update((alias, i) for alias in setsys_tmp[2*i].split())
            setsys_extra.append(setsys_tmp[2*i+1])
        if resetMem:
            chatMem = [deque(maxlen=MEMOLEN) for _ in range(len(setsys_extra))]
            chatTok = [0 for _ in range(len(setsys_extra))]
            dfDict = defaultdict(pd.DataFrame)
        # print(name2ID)

def nameChk(s) -> tuple:
    for name in name2ID:
        if name in s: return name2ID[name], name
    return -1, ''

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
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.channel = self.bot.get_channel(1088253899871371284)
        self.ignore = 0.5
        self.my_task.start()
        self._mindLoop.start()
        self._loneMeter.start()
        self.loneMeter = 0
        self.loneMsg = 0
        self.loneLimit = LONELYMETER
        self.sch_FullUser = None
        self.ollamaAPI = OllamaAPIHandler()
        # self.last_reply = replydict()
        
    def cog_unload(self):
        self.ollamaAPI.close()
        self.my_task.cancel()
        self._mindLoop.cancel()
        self._loneMeter.cancel()
        
    @commands.Cog.listener()
    async def on_message(self, message:Message):
        user, text = message.author, message.content
        uid, userName = user.id, user.name
        # userName = userName.replace('.', '').replace('#', '')
        userName = re.sub(r'[.#]', '', userName)
        n = min(len(text), READLEN)
        
        if uid == self.bot.user.id:
            return
        
        elif (aiInfo:=nameChk(text[:n])) != (-1, ''):
            aiNum, aiNam = aiInfo
            
            # logging 
            print(f'{wcformat(userName)}[{aiNam}]: {text}')
            # hehe
            if uid in banList:
                if random() < self.ignore:
                    if random() < 0.9:
                        async with message.channel.typing():
                            await asyncio.sleep(randint(5, 15))
                        await message.channel.send(choice(whatever))
                    print("已敷衍.")
                    return
                else:
                    print("嘖")
                    
            elif ('洗腦' in text[:n]):
                if devChk(uid):
                    chatMem[aiNum].clear()
                    return await message.channel.send(f'阿 {aiNam} 被洗腦了 🫠')
                else:
                    return await message.channel.send('客官不可以')
                
            elif ('人設' in text[:n]) and devChk(uid):
                if ('更新人設' in text[:n]):
                    msg = text
                    setsys_extra[aiNum] = msg[msg.find('更新人設')+4:]
                return await message.channel.send(setsys_extra[aiNum])
            
            elif ('-t' in text[:n]) and devChk(uid):
                return await message.channel.send(f'Total tokens: {chatTok[aiNum]}')
            
            elif ('-log' in text[:n]) and devChk(uid):
                tmp = sepLines((m['content'] for m in chatMem[aiNum]))
                return await message.channel.send(f'Loaded memory: {len(chatMem[aiNum])}\n{tmp}')
            
            # elif ('-err' in text[:n]) and devChk(uid):
            #     prompt = replyDict('user'  , f'{text}', userName).asdict
            #     reply  = await aiaiv2([prompt], aiNum, 99999)
            #     reply2 = sepLines((f'{k}: {v}' for k, v in reply.content.items()))
            #     print(f'{aiNam}:\n{reply2}')
            #     return await message.channel.send(f'Debugging {aiNam}:\n{reply2}')
            
            try:
                # special case, convert all user as Ning
                if aiNum == 5:
                    userName = 'Ning'
                    prompt = replyDict('user'  , f'嘎零 said {text}', userName)
                else:
                    prompt = replyDict('user'  , f'{userName} said {text}', userName)
                
                if not uid in dfDict:
                    dfDict[uid] = pd.DataFrame(columns=['text', 'vector'])
                    # check if file exists
                    if isfile(f'./embed/{uid}.csv') and isfile(f'embed/{uid}.npy'):
                        tmptext = pd.read_csv(f'./embed/{uid}.csv')
                        tmpvect = np.load    (f'./embed/{uid}.npy', allow_pickle=True)
                        for i in range(len(tmptext)):
                            dfDict[uid].loc[i] = (tmptext.loc[i]['text'], tmpvect[i])
                
                if multiChk(text, ['詳細', '繼續']):
                    tokens = TOKENPRESET[2]
                elif multiChk(text, ['簡單', '摘要', '簡略']) or len(text) < READLEN:
                    tokens = TOKENPRESET[0]
                else:
                    tokens = TOKENPRESET[1]
                    
                # skipping ai name
                if len(text) > len(aiNam):
                    nidx = text.find(aiNam, 0, len(aiNam))
                    if nidx != -1:
                        text = text[nidx+len(aiNam):]
                    if text[0] == '，' or text[0] == ' ':
                        text = text[1:]
                        
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
                        
                    reply = await self.ollamaAPI.chat([setupmsg.asdict, *chatMem[aiNum], prompt.asdict], aiNum, tokens)
                assert reply.role != 'error'
                
                reply2 = reply.content
                await message.channel.send(reply2)
            except TimeoutError:
                print(f'[!] {aiNam} TimeoutError')
                await message.channel.send(f'阿呀 {aiNam} 腦袋融化了~ 🫠')
            except AssertionError:
                # if embed.vector[0] == 0:
                #     print(f'Embed error:\n{embed.text}')
                if reply.role == 'error':
                    reply2 = sepLines((f'{k}: {v}' for k, v in reply.content.items()))
                    print(f'Reply error:\n{aiNam}:\n{reply2}')
                
                await message.channel.send(f'{aiNam} 發生錯誤，請聯繫主人\n{reply2}') 
            else:
                chatMem[aiNum].append(prompt.asdict)
                chatMem[aiNum].append(reply.asdict)
                # for i in chatMem[aiNum]:
                #     print(type(i))
                if uid not in scoreArr.index:
                    scoreArr.loc[uid] = 0
                scoreArr.loc[uid].iloc[aiNum] += 1
    
    @commands.hybrid_command(name = 'scoreboard')
    async def _scoreboard(self, ctx:commands.Context):
        user = ctx.author
        uid, userName = user.id, user.name
        if uid not in scoreArr.index: 
            return await ctx.send(f'{userName} 尚未和AI們對話過')
        arr = scoreArr.loc[uid]
        m = arr.max()
        i = int(arr.idxmax())
        s = arr.sum()
        t = scoreArr.sum(axis=1).sort_values(ascending=False).head(5)
        sb = sepLines((f'{wcformat(self.bot.get_user(i).name, w=16)}: {v}' for i, v in zip(t.index, t.values)))
        await ctx.send(f'```{sb}```\n{userName}共對話 {s} 次，最常找{id2name[i]}互動 ({m} 次，佔{m/s:.2%})')
    
    @commands.hybrid_command(name = 'localread')
    async def _cmdlocalRead(self, ctx:commands.Context):
        user = ctx.author
        if devChk(user.id):
            localRead()
            await ctx.send('AI 人設 讀檔更新完畢')
        else:
            await ctx.send('客官不可以')

    @commands.hybrid_command(name = 'listbot')
    async def _listbot(self, ctx:commands.Context):
        t = scoreArr.sum(axis=0).sort_values(ascending=False)
        s = scoreArr.sum().sum()
        l = sepLines(f'{wcformat(id2name[int(i)], w=8)}{v : <8}{ v/s :<2.3%}' for i, v in zip(t.index, t.values))
        await ctx.send(f'Bot List:\n```{l}```')
            
    @commands.command(name = 'bl')
    @commands.is_owner()
    async def _blacklist(self, ctx:commands.Context, uid:int):
        user = ctx.author
        # hehe
        if user.id in banList:
            return
        try:
            uid = int(uid)
            if uid not in banList and devChk(user.id):
                banList.append(uid)
                with open('./acc/banList.txt', 'a') as bfile:
                    bfile.write(f'{uid}\n')
                print(f'Added to bList: {uid}')
            else:
                print(f'Already banned: {uid}')
        except:
            print(f'ban error: {uid}')
    
    @commands.command(name = 'ig')
    @commands.is_owner()
    async def _ignore(self, ctx:commands.Context, num:float):
        user = ctx.author
        # hehe
        if user.id in banList or not devChk(user.id):
            return
        num = float(num)
        self.ignore = num
        print(f'忽略率： {num}')
    
    @commands.hybrid_command(name = 'status')
    @commands.is_owner()
    async def _status(self, ctx:commands.Context):
        status = await self.ollamaAPI.ps()
        await ctx.send(f'```json\n{json.dumps(status, indent=2, ensure_ascii=False)}```')
        
    @app_commands.command(name = 'schedule')
    async def _schedule(self, interaction: Interaction, delaytime:int, text:Optional[str] = ''):
        dt = datetime.now(timezone.utc) + timedelta(seconds=int(delaytime))
        
        self.channel = interaction.channel
        self.sch_FullUser = interaction.user
        self.sch_User = str(interaction.user).replace('.', '')
        self.sch_Text = text if text != '' else '好無聊，想找伊莉亞聊天，要聊甚麼呢?'
        
        tsk = self._loneMeter
        if not tsk.is_running():
            print(f'start task {tsk.__name__}')
            tsk.start()
        tsk.change_interval(seconds=4)
        tsk.restart()
        
        tsk = self.my_task
        if not tsk.is_running():
            print('start task')
            tsk.start()
        tsk.change_interval(time=dt.time())
        tsk.restart()
        
        tsk = self._mindLoop
        if not tsk.is_running():
            print('start task')
            tsk.start()
            
        time_points = np.random.exponential(60/5, (5))
        time_points = np.round(time_points, 3)
        cumulative_times = np.cumsum(time_points)
        cur_time = datetime.now(timezone.utc)
        
        seq_t = [(cur_time + timedelta(seconds = i)).time() for i in cumulative_times]
        for i in seq_t:
            print(f'{i}')
        tsk.change_interval(time=seq_t)
        tsk.restart()
        
        embed = Embed(title = "AI貓娘伊莉亞", description = f"伊莉亞來找主人 {self.sch_User} 了！", color = Color.random())
        embed.add_field(name = "時間", value = utctimeFormat(tsk.next_iteration))
        embed.add_field(name = "狀態", value = self.my_task.is_running())
        await interaction.response.send_message(embed = embed)
        
    @tasks.loop(time=tempTime)
    async def my_task(self):
        channel = self.channel
        aiNam = id2name[0]
        if channel:
            print("debugging")
            # setupmsg  = replyDict('system', f'{setsys_extra[0]} 現在是{strftime("%Y-%m-%d %H:%M")}', 'system')
            # try:
            #     async with channel.typing():
            #         prompt = replyDict('user', f'{self.sch_User} said {self.sch_Text}', self.sch_User)
            #         reply = await aiaiv2([setupmsg.asdict, *chatMem[0], prompt.asdict], 0, TOKENPRESET[0])
            #     assert reply.role != 'error'
                
            #     reply2 = reply.content
            #     await channel.send(f'{cc.convert(reply2)}')
            # except TimeoutError:
            #     print(f'[!] {aiNam} TimeoutError')
            #     await channel.send(f'阿呀 {aiNam} 腦袋融化了~ 🫠')
            # except AssertionError:
            #     if reply.role == 'error':
            #         reply2 = sepLines((f'{k}: {v}' for k, v in reply.content.items()))
            #         print(f'Reply error:\n{aiNam}:\n{reply2}')
                
            #     await channel.send(f'{aiNam} 發生錯誤，請聯繫主人\n{reply2}')
            # else:
            #     chatMem[0].append(reply.asdict)
    
    @tasks.loop(time=tempTime)
    async def _mindLoop(self):
        channel = self.channel
        user = self.sch_FullUser
        # await channel.send(f'{user.mention} {talkList[self._mindLoop.current_loop]}')
        # print(f'{user} {talkList[self._mindLoop.current_loop]}')
    
    @tasks.loop(time=tempTime)
    async def _loneMeter(self):
        SCALE = 10
        
        channel = self.channel
        user = self.sch_FullUser
        limit = self.loneLimit
        self.loneMeter += np.random.poisson(SCALE)
        print(f'loneMeter: {self.loneMeter}/{limit}')
        if self.loneMeter > limit:
            self.loneLimit = LONELYMETER/2 + np.random.exponential(LONELYMETER/2)
            consume = np.random.poisson(10*SCALE)
            self.loneMeter -= consume
            
            # await channel.send(f'{talkList[self.loneMsg % len(talkList)]}\n({-consume} energy) (meter: {self.loneMeter}/{limit}))')
            self.loneMsg += 1

async def setup(bot:commands.Bot):
    localRead(True)
    await bot.add_cog(askAI(bot))

async def teardown(bot:commands.Bot):
    print('ai saved')
    # print(scoreArr)
    scoreArr.to_csv('./acc/scoreArr.csv')
    for k in dfDict.keys():
        print(f'UID {k}: {len(dfDict[k])}')
        dfDict[k]['text'].to_csv(f'./embed/{k}.csv', index=False)
        np.save(f'./embed/{k}.npy', dfDict[k]['vector'].to_numpy())
