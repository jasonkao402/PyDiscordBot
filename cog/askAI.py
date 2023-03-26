import sys
sys.path.append('..')
import pydiscord as client

import openai
from discord.ext import commands
from collections import deque
from random import choice
from opencc import OpenCC
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from asyncio.exceptions import TimeoutError

whatever = '不知道 看情況 可能吧 嗯 隨便 都可以 喔 哈哈 笑死 真假 亂講'.split()

def replydict(rol='assistant', msg=''):
    return {'role': rol, 'content': msg}

with open('./acc/aiKey.txt', 'r') as acc_file:
    openai.api_key = acc_file.read().splitlines()[0]
        
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
            "temperature": 0.5,
            "frequency_penalty": 0.25,
            "presence_penalty": 0.25
        }
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()

    async def get_response():
        to, co = ClientTimeout(total=30), TCPConnector(ssl=False)
        async with ClientSession(connector=co, timeout=to) as session:
            return await Chat_Result(session, msgs)
    # return await get_response()
    response = await get_response()
    return response['choices'][0]['message'], response['usage']['total_tokens']
    
class askAI(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot):
        self.bot = bot
        self.mem = deque(maxlen=15)
        # self.last_reply = replydict()
        
    @commands.hybrid_command(name = 'aa')
    async def _askai(self, ctx, *, prompt):
        user = ctx.author
        # hehe
        if user.id == 1028322037497864212:
            await ctx.send(choice(whatever))
            return
            
        self.mem.append({'role':'user', 'content':f'{user.name} said {prompt}'})
        try:
            reply, usage = await aiaiv2([client.setsys, *self.mem])
            self.mem.append(reply)
            await ctx.send(f'{cc.convert(reply["content"])}\nToken: {usage}')
        except TimeoutError:
            await ctx.send(f'阿呀 腦袋融化了~')
            
    @commands.hybrid_command(name = 'set')
    async def _setai(self, ctx, *, prompt):
        user = ctx.author
        if prompt == '-log' and user.id == 225833749156331520:
            tmp = '\n'.join((m['content'] for m in self.mem))
            await ctx.send(tmp)
        elif prompt == '-l':
            await ctx.send(client.setsys["content"][-256:])
        elif prompt == '-m' and user.id == 225833749156331520:
            self.mem.clear()
            await ctx.send('阿 被洗腦了')
        elif prompt == '-pop':
            self.mem.pop()
            await ctx.send('已忘記最後一個回覆')
        else:
            if user.id == 1028322037497864212:
                return
            elif user.id == 225833749156331520:
                client.setsys = replydict(rol='system', msg=client.setsys_base+prompt)
                await ctx.send(f'{client.setsys["content"][-256:]}...\nChara set!')
            
    @commands.Cog.listener()
    async def on_message(self, message):
        user = message.author
        n = min(len(message.content), 10)
        
        if user.id == self.bot.user.id:
            return
        elif ('洗腦' in message.content[:n]) and user.id == 225833749156331520 :
            self.mem.clear()
            return await message.channel.send('阿 被洗腦了')
        elif ('伊莉亞' in message.content[:n]) or ('illya' in message.content[:n]):
            # hehe
            if user.id == 1028322037497864212:
                await message.channel.send(choice(whatever))
                return
            
            try:
                print(f'{user.name: <10}: {message.content}')
                self.mem.append({'role':'user', 'content':f'{user.name} said {message.content}'})
                reply, usage = await aiaiv2([client.setsys, *self.mem])
                # self.last_reply = reply
                self.mem.append(reply)
                await message.channel.send(f'{cc.convert(reply["content"])}\nToken: {usage}')
            except TimeoutError:
                await message.channel.send(f'阿呀 腦袋融化了~')
            
async def setup(bot):
    await bot.add_cog(askAI(bot))