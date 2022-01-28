from discord.ext import commands
import random
import re
from cog.utilFunc import *

class trpgUtil(commands.Cog):
    @commands.Cog.listener()
    async def on_message(self, message):
        USER = message.author
        s = message.content
        if USER.bot:
            return

        if re.match('([1-9]\d*)?[Dd][1-9]\d*', s):
            a, b = map(clamp, map(int, s.split("d", 1)))
            if a > 1 and a < 10:
                tmp = [random.randint(1, b) for _ in range(a)]
                detail = f'[{", ".join(map(str, tmp))}] = '
                ans = sum(tmp)
            else:
                detail, ans = '', sum(random.randint(1, b) for _ in range(a))
            await message.channel.send(f"{s} = {detail}{ans}")

    @commands.command(name = 'delComment')
    @commands.has_permissions(manage_messages=True)
    async def _delComment(self, ctx, rpt=16):
        '''delete comments'''
        try:
            rpt = clamp(int(rpt), 1, 100)
        except:
            await ctx.send('錯誤 : 參數異常。', delete_after=20)
            print('clear cmd error')

        has_any = lambda b: lambda a: any(map(lambda x:x in b, a))
        f1 = has_any(['//', '\\', '# '])
        deleted = await ctx.channel.purge(limit=rpt+1, check=lambda msg: f1(msg.content))
        await ctx.send(f'Delete {len(deleted)} message(s).', delete_after=10)
        print(f'{ctx.message.author.name[:16]} tried removed {len(deleted)} messages')
        

def setup(bot):
    bot.add_cog(trpgUtil(bot))