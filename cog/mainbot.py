from __future__ import annotations

import random

from discord import DMChannel, GroupChannel, PartialMessageable
from discord.ext import commands

from helper_func.utilFunc import dev_check

POSINT = '正整數!'
BADARGUMENT = '參數 Bad!'

class MainbotCog(commands.Cog):
    """Main functions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, err: commands.CommandError):
        if hasattr(ctx.command, 'on_error'):
            return
        await ctx.send(f'```{err}```')

    # @app_commands.command(name = '')
    @commands.hybrid_command(name='hello')
    async def hello(self, ctx: commands.Context):
        user = ctx.author
        if dev_check(user.id):
            await ctx.send(f'{user.mention}主人我來了 ฅ(>ω<)ฅ\n我是只屬於主人的呦~\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        else:
            await ctx.send(f'{user.mention}主人您好，很榮幸能為您服務 <(✿◡‿◡)>\n我是 LoliSagiri 所開發的互動式機器人\nSource code here: https://github.com/jasonkao402/PyDiscordBot')
        print(f'hi, {user.name}')

    @commands.command(name='ping')
    async def ping(self, ctx: commands.Context):
        PINGT = round(self.bot.latency * 1000)
        await ctx.send(f'pong : {PINGT} ms')
        print(f'pong : {PINGT}')

    @commands.hybrid_command(name='clear')
    @commands.is_owner()
    async def purge_messages(self, ctx: commands.Context, rpt: int = 1):
        try:
            rpt = int(rpt)
        except ValueError:
            await ctx.send(BADARGUMENT, delete_after=20)
            print('clear cmd error')
            return

        if rpt <= 0 or rpt > 32:
            await ctx.send(BADARGUMENT, delete_after=20)
        if isinstance(ctx.channel, (DMChannel, PartialMessageable, GroupChannel)):
            await ctx.send('這裡不能用清除訊息指令喔!\n', delete_after=20)
        elif rpt == 1:
            await ctx.message.delete()
        else:
            await ctx.channel.purge(limit=rpt + 1)
        print(f'{ctx.author} tried removed {rpt} messages')

    @commands.command(name='sel', aliases=['rnd', '幫我選一個'])
    async def select_random_item(self, ctx: commands.Context, *args):
        '''randomly select one item from your inputs'''
        sel = random.choice(args)
        await ctx.send(sel)
        print(*args, f'->{sel}')

async def setup(bot: commands.Bot):
    await bot.add_cog(MainbotCog(bot))
