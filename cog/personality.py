from collections import deque
from discord.ext import commands

class personality(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
async def setup(bot:commands.Bot):
    # localRead()
    await bot.add_cog(personality(bot))
    
async def teardown(bot):
    pass