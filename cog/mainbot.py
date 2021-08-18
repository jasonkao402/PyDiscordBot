from discord.ext import commands
import random

POSINT = '正整數啦!  (´_ゝ`)\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'
MEME = ['不要停下來阿', '卡其脫離太', '穿山甲', '卡打掐', '豆花', '阿姨壓一壓', 'Daisuke']

class mainbot(commands.Cog):
    """Main functions."""
    __slots__ = ('bot')
    
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, err):
        if hasattr(ctx.command, 'on_error'):
            return
        await ctx.send(f'```{err}```')

    @commands.command(name = 'hello', aliases = ['greet'])
    async def _hello(self, ctx):
        user = ctx.message.author
        if (user.id == 225833749156331520):
            await ctx.send(f'{user.mention}主人我來了 ฅ(>ω<)ฅ\n我是只屬於主人的呦~\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        else:
            await ctx.send(f'{user.mention}主人您好，很榮幸能為您服務 <(✿◡‿◡)>\n我是 LoliSagiri 所開發的互動式機器人\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        print(f'hi, {user.name}')
 
    @commands.command(name = 'ping')
    async def _ping(self, ctx):
        PINGT = round(self.bot.latency*1000)
        await ctx.send(f'pong : {PINGT} ms')
        print(f'pong : {PINGT}')
    
    @commands.command(name = 'dice', aliases = ['亂數'])
    async def _dice(self, ctx, rpt : int = 1):
        user = ctx.message.author
        s = ''
        try:
            rpt = int(rpt)
        except:
            await ctx.send(BADARGUMENT, delete_after=20)
            print('dice cmd error')
            return

        if rpt <= 0 : 
            s += self.POSINT
        elif rpt <= 10 :
            for _ in rpt:
                r = random.randint(1,6)
                s += (('非洲酋長' if r < 5 else '恭喜歐皇') + f', 抽出 {r} 星卡\n')
        else :
            s += ('抽那麼多不怕沒錢嗎? Σ(O△O)\n提示 : 最多10抽\n')
        s += (f'繼續敗家, {user.name}?')
        #await ctx.send(content=s, file=discord.File('fbk_question.gif'))
        await ctx.send(content=s)
        print(f'{user.name[:16]}... generated {rpt} numbers')

    @commands.command(name = 'clear')
    @commands.has_permissions(manage_messages=True)
    async def _clear(self, ctx, rpt : int = 1):
        try:
            rpt = int(rpt)
        except:
            await ctx.send(self.BADARGUMENT, delete_after=20)
            print('clear cmd error')
            return

        if rpt <= 0 or rpt > 10 : await ctx.send(BADARGUMENT)
        else : await ctx.channel.purge(limit = rpt+1)
        print(f'{ctx.message.author.name[:16]} tried removed {rpt} messages')

    @commands.command(name = 'meme')
    async def _meme(self, ctx):
        '''此指令與MZGamer的機器人連動'''
        userName = ctx.message.author.name[:16]
        TGTMEME = random.choice(MEME)
        await ctx.send(TGTMEME)
        print(f'{userName} : {TGTMEME}')
    
    @commands.command(name = 'sel', aliases = ['rnd', 'rs'])
    async def _sel(self, ctx, *args):
        '''randomly select one item from your inputs'''
        TGTMEME = random.choice(args)
        await ctx.send(TGTMEME)
        print('\n', *args)

def setup(bot):
    bot.add_cog(mainbot(bot))
