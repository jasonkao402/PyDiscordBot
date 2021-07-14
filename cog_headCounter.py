import csv
import os
import itertools
import discord
from discord.ext import commands

class headCounter(commands.Cog):
    """scoreboard of lame jokes, suggested by 黑醬"""
    __slots__ = ('bot', 'score')

    def __init__(self, bot):
        self.bot = bot
        
        absFilePath = os.path.abspath(__file__)
        os.chdir( os.path.dirname(absFilePath))
        with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as sco_file:
            data = csv.reader(sco_file)
            next(data)
            self.score = sorted(data, key=lambda item: (item[1]))

    @commands.command(name = 'sb', aliases = ['記分板'])
    async def _sb(self, ctx):
        top5 = enumerate(itertools.islice(self.score, 0, 5))
        fmt = '\n'.join(f"[Rank {r+1}] {(i[0])} ({i[1]}pt) : \"{i[2]}\"" for r,i in top5)
        embed = discord.Embed(title=f'排行榜前 {len(top5)} 名', description=fmt)
        await ctx.send(embed=embed)

    @commands.command(name = 'mybad')
    async def _mybad(self, ctx):
        USER = ctx.author

def setup(bot):
    bot.add_cog(headCounter(bot))

def teardown(bot):
    bot.remove_cog(headCounter(bot))
