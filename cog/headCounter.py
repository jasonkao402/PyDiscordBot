import csv
import os
from itertools import islice
import discord
from discord.ext import commands

TITLE = ['真正的砍頭王者', '無頭騎士', '砍頭大師', '專業送頭', '獻上頭顱']

class headCounter(commands.Cog):
    """scoreboard of lame jokes, suggested by 黑醬"""
    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'sb', aliases = ['記分板', '排行榜'])
    async def _sb(self, ctx):
        top5 = list(islice(headCounter.score, 0, 5))
        fmt = '\n'.join(f"[**{t}**] {self.bot.get_user(i[0])} ({i[1]} pt)" for (t, i) in zip(TITLE, top5))
        embed = discord.Embed(title=f'排行榜前 5 名', description=fmt)

        await ctx.send(embed=embed)
        print(fmt)

    @commands.command(name = 'mybad')
    async def _mybad(self, ctx):
        user = ctx.message.author
        uid = user.id
        d = {int(i[0]):int(i[1]) for i in headCounter.score}
        d[uid] = ((d[uid]+1 if uid in d else 1))

        headCounter.score = [(k, v)for k,v in d.items()]

        await ctx.send(f'{user.mention}, 現在有 {d[uid]} 顆頭')

    @commands.command(name = 'rev')
    async def _rev(self, ctx):
        user = ctx.message.author
        uid = user.id
        d = {int(i[0]):int(i[1]) for i in headCounter.score}

        if uid in d:
            d[uid] -= 1

        headCounter.score = [(k, v)for k,v in d.items()]

        await ctx.send(f'{user.mention}, 現在有{d[uid]}顆頭')

    @commands.command(name = 'save')
    async def _save(self, ctx):
        userid = ctx.message.author.id
        if (userid == 225833749156331520):
            with open('./scoreboard/score.csv', 'w+', newline='', encoding='utf-8-sig') as output:
                writer = csv.writer(output, delimiter=',')
                for i in headCounter.score:
                    writer.writerow(i)
            await ctx.send(f'Save done.')
        else:
            await ctx.send(f'No permission, bot dev only func.')

    @commands.command(name = 'testuser')
    async def _testUser(self, ctx, arg):
        await ctx.send(f"Found {self.bot.get_user(arg)}")


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
