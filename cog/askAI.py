import openai
from discord import Client as DC_Client
from discord.ext import commands
from collections import deque
from random import choice, random, randint
from opencc import OpenCC
from aiohttp import ClientSession, TCPConnector, ClientTimeout
import asyncio
from asyncio.exceptions import TimeoutError
from cog.utilFunc import devChk, sepLines, wcformat
import pandas as pd
from time import localtime, strftime

MEMOLEN = 12
READLEN = 30

with open('./acc/aiKey.txt', 'r') as acc_file:
    k, o = acc_file.read().splitlines()
    openai.api_key = k
    openai.organization = o
    
with open('./acc/banList.txt', 'r') as acc_file:
    banList = [int(id) for id in acc_file.readlines()]

scoreArr = pd.read_csv('./acc/scoreArr.csv', index_col='uid', dtype=int)
# with open('./acc/aiSet_base.txt', 'r', encoding='utf-8') as set2_file:
#     setsys_base = set2_file.read()
#     # setsys = {'role': 'system', 'content': acc_data}
#     setsys = {'role': 'system', 'content': setsys_base}
    
def localRead(resetMem = False) -> None:
    with open('./acc/aiSet_extra.txt', 'r', encoding='utf-8') as set1_file:
        global setsys_extra, name2ID, id2name, chatMem, chatTok
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
        print(name2ID)

def nameChk(s) -> tuple:
    for name in name2ID:
        if name in s: return name2ID[name], name
    return -1, ''

def replydict(rol='assistant', msg=''):
    return {'role': rol, 'content': msg}

whatever = [
    "對不起，發生 429 - Too Many Requests ，所以不知道該怎麼回你 QQ",
    "對不起，發生 401 - Unauthorized ，所以不知道該怎麼回你 QQ",
    "對不起，發生 500 - The server had an error while processing request ，所以不知道該怎麼回你 QQ"
    "阿呀 腦袋融化了~",
] + '不知道喔 我也不知道 看情況 可能吧 嗯 隨便 都可以 喔 哈哈 笑死 真假 亂講 怎樣 所以 🤔'.split()
   
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + openai.api_key,
}
# "organization": openai.organization,
url = "https://api.openai.com/v1/chat/completions"
cc = OpenCC('s2twp')

async def aiaiv2(msgs, botid, tokens=700) -> dict:
    async def Chat_Result(session:ClientSession, msgs, url=url, headers=headers):
        data = {
            "model": "gpt-3.5-turbo",
            "messages": msgs,
            "max_tokens": min(tokens, 4096-chatTok[botid]),
            "temperature": 0.8,
            "frequency_penalty": 0.4,
            "presence_penalty": 0.4
        }
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()

    async def get_response():
        to, co = ClientTimeout(total=60), TCPConnector(ssl=False)
        async with ClientSession(connector=co, timeout=to) as session:
            return await Chat_Result(session, msgs)

    response = await get_response()
    if 'error' in response:
        # print(response)
        return replydict(rol='error', msg=response['error'])
    chatTok[botid] = response['usage']['total_tokens']
    if chatTok[botid] > 3200:
        chatMem[botid].popleft()
        chatMem[botid].popleft()
        print(f"token warning:{response['usage']['total_tokens']}, popped last msg.")
    return response['choices'][0]['message']
    
class askAI(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.ignore = 0.5
        # self.last_reply = replydict()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author
        uid = user.id
        n = min(len(message.content), READLEN)
        
        if uid == self.bot.user.id:
            return
        
        elif (aiInfo:=nameChk(message.content[:n])) != (-1, ''):
            aiNum, aiNam = aiInfo
            
            # logging 
            print(f'{wcformat(user.name)}[{aiNam}]: {message.content}')
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
                    
            elif ('洗腦' in message.content[:n]):
                if devChk(uid):
                    chatMem[aiNum].clear()
                    return await message.channel.send(f'阿 {aiNam} 被洗腦了 🫠')
                else:
                    return await message.channel.send('客官不可以')
                
            elif ('人設' in message.content[:n]) and devChk(uid):
                if ('更新人設' in message.content[:n]):
                    msg = message.content
                    setsys_extra[aiNum] = msg[msg.find('更新人設')+4:]
                return await message.channel.send(setsys_extra[aiNum])
            
            elif ('-t' in message.content[:n]) and devChk(uid):
                return await message.channel.send(f'Total tokens: {chatTok[aiNum]}')
            
            elif ('-log' in message.content[:n]) and devChk(uid):
                tmp = sepLines((m['content'] for m in chatMem[aiNum]))
                return await message.channel.send(f'Loaded memory: {len(chatMem[aiNum])}\n{tmp}')
            
            elif ('-err' in message.content[:n]) and devChk(uid):
                prompt = replydict('user'  , f'{user.name} said {message.content}' )
                reply  = await aiaiv2([prompt], aiNum, 99999)
                reply2 = sepLines((f'{k}: {v}' for k, v in reply["content"].items()))
                print(f'{aiNam}:\n{reply2}')
                return await message.channel.send(f'Debugging {aiNam}:\n{reply2}')
            
            try:
                prompt = replydict('user'  , f'{user.name} said {message.content}')
                setup  = replydict('system', setsys_extra[aiNum]+f'現在是{strftime("%Y-%m-%d %H:%M", localtime())}')
                async with message.channel.typing():
                    reply = await aiaiv2([setup, *chatMem[aiNum], prompt], aiNum)
                
                assert reply['role'] != 'error'
                
                reply2 = reply["content"]
                # await message.channel.send(f'{cc.convert(reply2.replace("JailBreak", aiNam))}')
                await message.channel.send(f'{cc.convert(reply2)}')
            except TimeoutError:
                print(f'{aiNam} timeout 了')
                await message.channel.send(f'阿呀 {aiNam} 腦袋融化了~ 🫠')
            except AssertionError:
                reply2 = sepLines((f'{k}: {v}' for k, v in reply["content"].items()))
                print(f'{aiNam}:\n{reply2}')
                
                await message.channel.send(f'{aiNam} 發生錯誤，請聯繫主人\n{reply2}') 
            else:
                chatMem[aiNum].append(prompt)
                chatMem[aiNum].append(reply)
                if uid not in scoreArr.index:
                    scoreArr.loc[uid] = 0
                scoreArr.loc[uid].iloc[aiNum] += 1
    
    @commands.hybrid_command(name = 'scoreboard')
    async def _scoreboard(self, ctx):
        user = ctx.author
        uid = user.id
        if uid not in scoreArr.index: 
            return await ctx.send(f'{user.name} 尚未和AI們對話過')
        arr = scoreArr.loc[uid]
        m = arr.max()
        i = int(arr.idxmax())
        s = arr.sum()
        t = scoreArr.sum(axis=1).sort_values(ascending=False).head(5)
        sb = sepLines((f'{wcformat(self.bot.get_user(i).name)}: {v}'for i, v in zip(t.index, t.values)))
        await ctx.send(f'```{sb}```\n{user.name}最常找{id2name[i]}互動 ({m} 次)，共對話 {s} 次')
    
    @commands.hybrid_command(name = 'localread')
    async def _cmdlocalRead(self, ctx):
        user = ctx.author
        if devChk(user.id):
            localRead()
            await ctx.send('AI 人設 讀檔更新完畢')
        else:
            await ctx.send('客官不可以')

    @commands.hybrid_command(name = 'listbot')
    async def _listbot(self, ctx):
        t = scoreArr.sum(axis=0).sort_values(ascending=False)
        s = scoreArr.sum().sum()
        l = sepLines(f'{wcformat(id2name[int(i)], w=8)}{v : <8}{ v/s :<2.3%}' for i, v in zip(t.index, t.values))
        await ctx.send(f'Bot List:\n```{l}```')
            
    @commands.command(name = 'bl')
    async def _blacklist(self, ctx, uid):
        user = ctx.author
        # hehe
        if user.id in banList:
            return
        try:
            uid = int(uid)
            if uid not in banList and devChk(user.id):
                banList.append(uid)
                with open('./acc/banList.txt', 'a') as bfile:
                    bfile.write(str(uid))
                print(f'Added to bList: {uid}')
            else:
                print(f'Already banned: {uid}')
        except:
            print(f'ban error: {uid}')
    
    @commands.command(name = 'ig')
    async def _ignore(self, ctx, num):
        user = ctx.author
        # hehe
        if user.id in banList or not devChk(user.id):
            return
        num = float(num)
        self.ignore = num
        print(f'忽略率： {num}')

async def setup(bot):
    localRead(True)
    await bot.add_cog(askAI(bot))

async def teardown(bot):
    print('ai saved')
    # print(scoreArr)
    scoreArr.to_csv('./acc/scoreArr.csv')