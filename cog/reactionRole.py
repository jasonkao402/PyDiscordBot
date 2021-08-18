import discord
from discord.ext import commands

KEYWORD = "[⚡] 找我領取身分組 [⚡]"
roleDict = {"❔": "A", "⚡": "B", "<:nsysu_isc:877159351272493058>": "資安社", "<:nsysu_cc:877159351582871552>": "程式研習社" }

class React(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name = 'lrole')
    @commands.has_any_role('botMaster', '社團幹部')
    async def _listRole(self, ctx):
        print(", ".join([str(r.id) for r in ctx.guild.roles]))
        print(", ".join([str(r) for r in ctx.guild.roles]))

    @commands.command(name = 'reactionRole')
    @commands.has_any_role('botMaster', '社團幹部')
    async def _reactionRole(self, ctx):
        await ctx.message.delete()
        msg = await ctx.send(KEYWORD)
        for k in roleDict:
            try   : await msg.add_reaction(k)
            except: pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if KEYWORD not in reaction.message.content:
            return
        for k, v in roleDict.items():
            if reaction.emoji == k :
                Role = discord.utils.get(user.guild.roles, name=v)
                if Role :
                    await user.add_roles(Role)
    
    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if KEYWORD not in reaction.message.content:
            return
        for k, v in roleDict.items():
            if reaction.emoji == k :
                Role = discord.utils.get(user.guild.roles, name=v)
                if Role :
                    await user.remove_roles(Role)


def setup(bot):
    bot.add_cog(React(bot))
