import collections
import discord
from discord.ext import commands
from itertools import islice

class TestList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ans_que = collections.deque()
        self.hnd_que = collections.deque()
        self.now_ans = None

    def _updateAns(self):
        pass

    @commands.command(name = 'quiz', aliases=['qz'])
    async def _quiz(self, ctx, *args):
        '''make a quiz'''

        args = set(args)
        if not args:
            print("Answer cannot be none")
            return await ctx.send(f"Answer cannot be none")
            
        self.ans_que.append(args)
        await ctx.send(f"preview ans = {args}")
        print(f"preview ans = {args}")

    @commands.command(name = 'guess', aliases=['gs'])
    async def _guess(self, ctx, *args):
        '''guess the answer'''

        #await ctx.send(f'**`{ctx.author}`**: guessed {"  ".join(args)}')
        if not self.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')
        elif not args:
            return await ctx.send('隨便猜也好嘛(´・ω・`)', delete_after=20)
        elif len(args) > 1:
            await ctx.send('一次只能猜一個(´・ω・`)，只看第一個囉', delete_after=20)
        args = args[0]
        
        print("corr ans : ", self.ans_que[0], "your ans : ", args)

        if args in self.ans_que[0]:
            await ctx.send(f'**`{ctx.author}`** guessed {args}: Correct, next!')
            self.ans_que.popleft()
        else:
            await ctx.send(f'**`{ctx.author}`** guessed {args}: Wrong~ Try again?')

    @commands.command(name = 'ans_queue', aliases=['aq'])
    async def _ans_queue(self, ctx):
        """get answer queue"""

        if not self.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')

        upcoming = list(islice(self.ans_que, 0, 10))
        print(*upcoming, sep = '\n')
        fmt = '\n'.join(str(i) for i in upcoming)

        await ctx.send(embed=discord.Embed(title=f'Next {len(upcoming)} Answer', description=fmt))
    
    @commands.command(name = 'hand', aliases=['舉'])
    async def _raiseHand(self, ctx):
        """舉手"""

        user = ctx.message.author
        
        if not self.hnd_que:
            await ctx.send(f"{user.mention}  你是第一個舉手的 好耶!")
        else:
            await ctx.message.add_reaction('\U0001F44D')
        self.hnd_que.append(user)
        print(f"{user} hand")

    @commands.command(name = 'hf')
    async def _handFirst(self, ctx):
        """看看誰先舉手"""
        if self.hnd_que:
            firstOne = self.hnd_que.popleft()
            await ctx.send(f"{firstOne.mention}，輪到你囉!")
            print(f"hand queue pop 1")
        else:
            await ctx.send(f"沒人舉手  QwQ")
            print(f"queue empty")

    @commands.command(name = 'hc')
    async def _handClear(self, ctx):
        """clear hand queue"""

        self.hnd_que.clear()
        await ctx.send(f"清空等待列囉~")
        print(f"Cleared queue")

    @commands.command(name = 'hq')
    async def _handQueue(self, ctx):
        """get hand queue"""

        if not self.hnd_que:
            print('queue empty')
            return await ctx.send('queue empty')

        upcoming = list(islice(self.hnd_que, 0, 5))
        print(*upcoming, sep = '\n')
        fmt = '\n'.join(str(i) for i in upcoming)

        await ctx.send(embed=discord.Embed(title=f'Next {len(upcoming)} Hands', description=fmt))
    
def setup(bot):
    bot.add_cog(TestList(bot))
