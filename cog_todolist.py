import asyncio

class TestList:
    def __init__(self, ctx):
        self.bot = ctx.bot
        self.queue = asyncio.Queue()