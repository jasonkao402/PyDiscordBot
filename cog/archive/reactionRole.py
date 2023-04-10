import discord
from discord.ext import commands

KEYWORD = "[⚡] 找我領取身分組 [⚡]"
roleDict = {
"❔": "A", "⚡": "B",
"<:nsysu_isc:877159351272493058>": "資安社",
"<:nsysu_cc:877159351582871552>": "程式研習社",
}

class React(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'lrole')
    @commands.has_permissions(manage_roles=True)
    async def _listRole(self, ctx):
        print(", ".join([str(r.id) for r in ctx.guild.roles]))
        print(", ".join([str(r) for r in ctx.guild.roles]))

    @commands.command(name = 'reactionRole')
    @commands.has_permissions(manage_roles=True)
    async def _reactionRole(self, ctx):
        await ctx.message.delete()
        msg = await ctx.send(KEYWORD)
        for k in roleDict:
            try   : await msg.add_reaction(k)
            except: pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        # skip DM messages
        if isinstance(channel, discord.DMChannel): return

        message = await channel.fetch_message(payload.message_id)
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        
        if member.bot or KEYWORD not in message.content:  return

        if payload.emoji.name in roleDict:
            Role = discord.utils.get(guild.roles, name=roleDict[payload.emoji.name])
            print(f'{member}: assigned {Role}')
            if Role :
                await member.add_roles(Role)
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        channel = self.bot.get_channel(payload.channel_id)
        # skip DM messages
        if isinstance(channel, discord.DMChannel): return

        message = await channel.fetch_message(payload.message_id)
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        
        if member.bot or KEYWORD not in message.content:  return

        if payload.emoji.name in roleDict:
            Role = discord.utils.get(guild.roles, name=roleDict[payload.emoji.name])
            print(f'{member}: revoked {Role}')
            if Role :
                await member.remove_roles(Role)

def setup(bot):
    bot.add_cog(React(bot))
