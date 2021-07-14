import csv
import os
from discord.ext import commands

class headCounter(commands.Cog):
    """scoreboard of lame jokes, suggested by 黑醬"""
    __slots__ = ('bot', 'score')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'sb', aliases = ['記分板'])
    async def _sb(self, ctx):
        user = ctx.message.author
        #await ctx.send(f'{user.mention}主人您好 ฅ>ω<ฅ\n我是 LoliSagiri 所開發的互動式機器人\nSource code here: https://github.com/jasonkao402/PyDiscord_chat_bot')
        print(user)

def setup(bot):
    bot.add_cog(headCounter(bot))
