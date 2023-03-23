import openai
from cog.utilFunc import *
from discord.ext import commands
from collections import deque

def aiai(msg):
    return openai.ChatCompletion.create(
       model="gpt-3.5-turbo",
       messages=msg,
       temperature=0.6,
       max_tokens=256,
       top_p=1,
       frequency_penalty=0,
       presence_penalty=0)['choices'][0]['message']
    
class askAI(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot):
        self.bot = bot
        self.mem = deque(maxlen=18)
        self.sys = {'role': 'system', 'content': '主人您好，很榮幸能為您服務 <(✿◡‿◡)>\n我是 LoliSagiri 所開發的互動式機器人'}
        
    @commands.hybrid_command(name = 'aa')
    async def _askai(self, ctx, *, prompt):
        if prompt == '-log':
            tmp = '\n'.join(self.mem)
            await ctx.send(tmp)
            # await ctx.send(f'Words: {len(tmp.split())}')
        else:
            self.mem.append({'role':'user', 'content':prompt})
            # tmp = '\n'.join(self.mem)
            reply = aiai([self.sys, *self.mem])
            self.mem.append(reply)
            # tmp = '\n'.join(self.mem)
            # print('Words: ', len(self.mem.split()))
            user = ctx.author
            await ctx.send(f'{user.mention}{reply["content"]}')

async def setup(bot):
    with open('./acc/aiKey.txt', 'r') as acc_file:
        openai.api_key = acc_file.read().splitlines()[0]
    await bot.add_cog(askAI(bot))