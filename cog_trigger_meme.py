import discord
from discord.ext import commands

class EXT_COG(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_message(self, message):
        USER = message.author
        if USER.bot:
            return

        if 'AMD' in message.content:
            await message.channel.send(f'{USER.mention}, AMD YES!')
            print(f'{USER.name} AMD YES')

        if any(x in message.content for x in ['上車', '開車']):
            #await message.channel.send(file=discord.File('aqua_driver.gif'))
            await message.channel.send(f'{USER.mention}, 老司機永不停車!')
            print(f'{USER.name} old driver')

        if 'peko' in message.content:
            await message.channel.send(f'{USER.mention} 哈↗哈↗哈↗哈↗哈↗哈↗')
            print(f'{USER.name} peko peko')
    
def setup(bot):
    bot.add_cog(EXT_COG(bot))
