import asyncio

class TestList:
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue()

def setup(bot):
    bot.add_cog(TestList(bot))
