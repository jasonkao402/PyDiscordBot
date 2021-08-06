import asyncio
from discord.ext import commands
import random

class TestList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue()

def setup(bot):
    bot.add_cog(TestList(bot))
