import random
from discord.ext import commands
from cog.utilFunc import *

POSINT = '正整數啦!  (´_ゝ`)\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'

class mainbot(commands.Cog):
    """Main functions."""
    __slots__ = ('bot')
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if hasattr(ctx.command, 'on_error'):
            return
        await ctx.send(f'```{err}```')
        
    # @app_commands.command(name = '')
    @commands.hybrid_command(name = 'hello')
    async def _hello(self, ctx:commands.Context):
        user = ctx.author
        if devChk(user.id):
            await ctx.send(f'{user.mention}主人我來了 ฅ(>ω<)ฅ\n我是只屬於主人的呦~\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        else:
            await ctx.send(f'{user.mention}主人您好，很榮幸能為您服務 <(✿◡‿◡)>\n我是 LoliSagiri 所開發的互動式機器人\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        print(f'hi, {user.name}')
 
    @commands.command(name = 'ping')
    async def _ping(self, ctx):
        PINGT = round(self.bot.latency*1000)
        await ctx.send(f'pong : {PINGT} ms')
        print(f'pong : {PINGT}')
    
    @commands.hybrid_command(name = 'clear')
    @commands.has_permissions(manage_messages=True)
    async def _clear(self, ctx, rpt : int = 1):
        try:
            rpt = int(rpt)
        except:
            await ctx.send(BADARGUMENT, delete_after=20)
            print('clear cmd error')
            return

        if rpt <= 0 or rpt > 10 : await ctx.send(BADARGUMENT, delete_after=20)
        else : await ctx.channel.purge(limit = rpt+1)
        print(f'{ctx.author.name[:16]} tried removed {rpt} messages')
    
    @commands.command(name = 'sel', aliases = ['rnd', '幫我選一個'])
    async def _sel(self, ctx, *args):
        '''randomly select one item from your inputs'''
        sel = random.choice(args)
        await ctx.send(sel)
        print(*args, f'->{sel}')

async def setup(bot:commands.Bot):
    await bot.add_cog(mainbot(bot))
