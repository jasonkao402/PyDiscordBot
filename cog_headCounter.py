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

    @commands.command(name = 'sb', aliases = ['記分板'])
    async def _sb(self, ctx):
        with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as sco_file:
            data = csv.DictReader(sco_file)
            line_count = 1
            '''
            for row in data:
                if line_count > 5:
                    break
                print(f"[Rank {line_count}] {self.bot.get_user(row['id'])} ({row['score']}pt) : \"{row['last_msg']}\"")
                line_count += 1
            '''
            top5 = list(itertools.islice(data, 0, 5))
            fmt = '\n'.join(f"[Rank {line_count}] {self.bot.get_user(row['id'])} ({row['score']}pt) : \"{row['last_msg']}\"" for row in top5)
            embed = discord.Embed(title=f'排行榜前 {len(top5)} 名', description=fmt)

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(headCounter(bot))
