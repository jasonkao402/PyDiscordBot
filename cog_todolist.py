import collections
import discord
from discord.ext import commands
from itertools import islice

class TestList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ans_que = collections.deque()
        self.now_ans = None

    def _updateAns(self):
        pass

    @commands.command(name = 'quiz', aliases=['qz'])
    async def _quiz(self, ctx, *args):
        args = set(args)
        '''make a quiz'''
        if not args:
            print("Answer cannot be none")
            return await ctx.send(f"Answer cannot be none")
            
        self.ans_que.append(args)
        await ctx.send(f"preview ans = {args}")
        print(f"preview ans = {args}")

    @commands.command(name = 'guess', aliases=['gs'])
    async def _guess(self, ctx, *args):
        '''guess the answer'''

        await ctx.send(f'**`{ctx.author}`**: guessed {" ".join(args)}')
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
            await ctx.send(f'**`{ctx.author}`**: Correct, next!')
            self.ans_que.popleft()
        else:
            await ctx.send(f'**`{ctx.author}`**: Wrong~ Try again?')

    @commands.command(name = 'ans_queue', aliases=['aq'])
    async def _ans_queue(self, ctx):
        """get answer queue"""
        if not self.ans_que:
            print('queue empty')
            return await ctx.send('queue empty')

        upcoming = list(islice(self.ans_que, 0, 10))
        print(*upcoming, sep = '\n')
        fmt = '\n'.join(str(i) for i in upcoming)

        await ctx.send(embed=discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt))

def setup(bot):
    bot.add_cog(TestList(bot))
