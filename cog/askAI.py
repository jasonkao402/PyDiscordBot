import sys
sys.path.append('..')
import pydiscord as client

import openai
from discord.ext import commands
from collections import deque
from random import choice, random, randint
from opencc import OpenCC
from aiohttp import ClientSession, TCPConnector, ClientTimeout
import asyncio
from asyncio.exceptions import TimeoutError
from cog.utilFunc import nameChk, devChk

manmadeErr = [
    "對不起，發生 429 - Too Many Requests ，所以不知道該怎麼回你 QQ",
    "對不起，發生 401 - Unauthorized ，所以不知道該怎麼回你 QQ",
    "對不起，發生 500 - The server had an error while processing request ，所以不知道該怎麼回你 QQ"
    "阿呀 腦袋融化了~",
    "阿呀 腦袋融化了~",
]
whatever = '不知道喔 我也不知道 看情況 可能吧 嗯 隨便 都可以 喔 哈哈 笑死 真假? 亂講 怎樣 所以?'.split()+manmadeErr

def replydict(rol='assistant', msg=''):
    return {'role': rol, 'content': msg}

with open('./acc/aiKey.txt', 'r') as acc_file:
    openai.api_key = acc_file.read().splitlines()[0]
    
with open('./acc/banList.txt', 'r') as acc_file:
    banList = [int(id) for id in acc_file.read().splitlines()]
    
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + openai.api_key,
}

url = "https://api.openai.com/v1/chat/completions"
cc = OpenCC('s2twp')

async def aiaiv2(msgs):
    async def Chat_Result(session, msgs, url=url, headers=headers):
        data = {
            "model": "gpt-3.5-turbo",
            "messages": msgs,
            "max_tokens": 800,
            "temperature": 0.6,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.3
        }
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()

    async def get_response():
        to, co = ClientTimeout(total=40), TCPConnector(ssl=False)
        async with ClientSession(connector=co, timeout=to) as session:
            return await Chat_Result(session, msgs)

    response = await get_response()
    if 'error' in response:
        print(response)
    print(f"token :{response['usage']['total_tokens']}")
    return response['choices'][0]['message']
    
class askAI(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot):
        self.bot = bot
        self.mem = deque(maxlen=15)
        self.ignore = 0.2
        # self.last_reply = replydict()
    
    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author
        n = min(len(message.content), 10)
        
        if user.id == self.bot.user.id:
            return
        elif ('洗腦' in message.content[:n]) and devChk(user.id) :
            self.mem.clear()
            return await message.channel.send('阿 被洗腦了')
        elif nameChk(message.content[:n]):
            # logging 
            print(f'{user.name: <10}: {message.content}')
            # hehe
            if user.id in banList:
                if random() < self.ignore:
                    if random() < 0.9:
                        await asyncio.sleep(randint(5, 15))
                        await message.channel.send(choice(whatever))
                    print("已敷衍.")
                    return
                else:
                    print("嘖")
                    
            try:
                prompt = {'role':'user', 'content':f'{user.name} said {message.content}'}
                reply = await aiaiv2([client.setsys, *self.mem, prompt])
                # monkey fix
                reply2 = reply["content"][11:] if reply["content"].startswith("JailBreak:") else reply["content"]
                reply['content'] = reply2
                await message.channel.send(f'{cc.convert(reply2)}')
            except TimeoutError:
                print(f'腦袋 timeout 了')
                await message.channel.send(f'阿呀 腦袋融化了~')
            else:
                self.mem.append(prompt)
                self.mem.append(reply)
            
    @commands.hybrid_command(name = 'set')
    async def _setai(self, ctx, *, prompt):
        user = ctx.author
        if user.id in banList:
            await ctx.send('客官不可以')
        elif prompt == '-l' or len(prompt) < 1:
            await ctx.send(client.setsys["content"][-256:])
        elif prompt == '-pop':
            self.mem.pop()
            await ctx.send('已忘記最後一個回覆')
        elif prompt == '-log' and devChk(user.id):
            dict().values
            tmp = '\n'.join((m['content'] for m in self.mem))
            await ctx.send(f'Memory:\n{tmp}')
        elif prompt == '-m' and devChk(user.id):
            self.mem.clear()
            await ctx.send('阿 被洗腦了')
        elif len(prompt) > 10 and devChk(user.id):
            client.setsys = replydict(rol='system', msg=client.setsys_base+prompt)
            await ctx.send(f'...{client.setsys["content"][-256:]}\nChara set!')
                
    @commands.command(name = 'bl')
    async def _blacklist(self, ctx, id):
        user = ctx.author
        # hehe
        if user.id in banList:
            return
        try:
            id = int(id)
            if id not in banList:
                banList.append(id)
                with open('./acc/banList.txt', 'a') as bfile:
                    bfile.write(str(id))
                print(f'Added to bList: {id}')
            else:
                print(f'Already banned: {id}')
        except:
            print(f'ban error: {id}')
    
    @commands.command(name = 'ig')
    async def _ignore(self, ctx, num):
        user = ctx.author
        # hehe
        if user.id in banList:
            return
        num = float(num)
        self.ignore = num
        print(f'忽略率： {num}')
            
async def setup(bot):
    await bot.add_cog(askAI(bot))