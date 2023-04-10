import discord
import random
from discord.ext import commands
from datetime import datetime
from discord_components import Select, SelectOption

roleDict = {
    731121941255028746: '機器人調教團', 914846002928820294:'TRPG', 954096190058795041: 'Genshin',
    954370855532646491: 'Tetris', 956158424297652244: 'Minecraft',
}
role = ['954370855532646491', '956158424297652244']
class Selection(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def mod_role(self, ctx, user, roleIDs):
        roleIDs = set(map(int, roleIDs))
        role = [ctx.guild.get_role(k) for k in roleIDs]
        await user.add_roles(*role)
        await ctx.send(f'{user.mention} get the role: **{", ".join(map(str, role))}**')

        role = [ctx.guild.get_role(int(k)) for k in (set(roleDict.keys())-roleIDs)]
        await user.remove_roles(*role)
        await ctx.send(f'{user.mention} remove the role: **{", ".join(map(str, role))}**')

    @commands.command(name = 'mrole')
    @commands.has_permissions(manage_roles=True)
    async def _modRole(self, ctx):
        timestamp = datetime.timestamp(datetime.now())
        
        imsg = await ctx.send('Get the roles!', components=[
            Select(
                placeholder = 'Select your role!', 
                options = [SelectOption(label=l, value=v) for v, l in roleDict.items()], 
                max_values = len(roleDict), custom_id = str(timestamp)
                )])
        interaction = await self.bot.wait_for("select_option", check=lambda inter: inter.custom_id == str(timestamp))
        await self.mod_role(ctx, interaction.user, interaction.values)
        await interaction.respond(type=6)
        await imsg.delete()

def setup(bot):
    bot.add_cog(Selection(bot))