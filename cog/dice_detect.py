from discord.ext import commands
import random
import re

def clamp(n, minn=0, maxn=100):
    return max(min(maxn, n), minn)

class dicebot(commands.Cog):
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

def setup(bot):
    bot.add_cog(dicebot(bot))