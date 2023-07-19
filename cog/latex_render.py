from discord import File as DC_File
from discord.ext import commands
import sympy

@commands.hybrid_command(name = 'latex')
async def _latex(self, ctx, *, args):
    sympy.preview(args, viewer='file', filename='__LATEX__OUTPUT.png')
    await ctx.send(file='__LATEX__OUTPUT.png')
