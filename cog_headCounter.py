import csv
import os
import itertools
import discord
from discord.ext import commands

class headCounter(commands.Cog):
    """scoreboard of lame jokes, suggested by 黑醬"""
    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'sb', aliases = ['記分板'])
    async def _sb(self, ctx):
        top5 = enumerate(itertools.islice(headCounter.score, 0, 5), start=1)
        
        fmt = '\n'.join(f"[Rank {r}] {self.bot.get_user(i[0])} ({i[1]}pt) : \"{i[2]}\"" for r, i in top5)
        embed = discord.Embed(title=f'排行榜前 5 名', description=fmt)

        await ctx.send(embed=embed)
        print(fmt)

    @commands.command(name = 'mybad')
    async def _mybad(self, ctx, *args):
        USER = ctx.author.id
        d = {int(i[0]):(int(i[1]),i[2]) for i in headCounter.score}
        d[USER] = ((d[USER][0]+1 if USER in d else 1), ''.join(args))

        headCounter.score = [[k, v[0], v[1]]for k,v in d.items()]

absFilePath = os.path.abspath(__file__)
os.chdir( os.path.dirname(absFilePath))

def setup(bot):
    with open('./scoreboard/score.csv', mode='r', encoding='utf-8-sig') as sco_file:
        data = csv.reader(sco_file)
        headCounter.score = sorted(data, key=lambda i: int(i[1]), reverse=True)
    bot.add_cog(headCounter(bot))

def teardown(bot):
    print("removed headCounter")
    with open('./scoreboard/score.csv', 'w+', newline='', encoding='utf-8-sig') as output:
        # 以空白分隔欄位，建立 CSV 檔寫入器
        writer = csv.writer(output, delimiter=',')
        for i in headCounter.score:
            writer.writerow(i)
