import discord
from discord.ext import commands
from discord_slash import SlashContext, cog_ext

valid_guild = [477839636404633600]

class Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @cog_ext.cog_slash(name="test", guild_ids=valid_guild, description="123")
    async def _test(self, ctx: SlashContext):
        #await ctx.defer()
        embed = discord.Embed(title="embed test")
        await ctx.send(content="send loli", embeds=[embed])

def setup(bot):
    bot.add_cog(Slash(bot))