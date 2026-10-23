from __future__ import annotations

import pathlib
from io import BytesIO
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from discord import File as DC_File
from discord.ext import commands

if TYPE_CHECKING:
    from setup_bot import MyBot
def render_text(formula: str, fontsize: int = 10, dpi: int = 256) -> bytes:
    """Renders LaTeX formula into image."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, f'${formula}$', fontsize=fontsize, color='#ffffff')
    buffer_ = BytesIO()
    fig.savefig(buffer_, dpi=dpi, transparent=True, format='png', bbox_inches='tight', pad_inches=0.02)
    buffer_.seek(0)
    plt.close(fig)

    return buffer_.getvalue()

class LatexRendererCog(commands.Cog):

    def __init__(self, bot: MyBot):
        self.bot = bot

    @commands.hybrid_command(name='latex')
    async def render_latex(self, ctx: commands.Context, *, args: str):
        # print(args, len(args))
        b = render_text(args)
        await ctx.send(file=DC_File(fp=BytesIO(b), filename='latex_.png'))

async def setup(bot: MyBot):
    await bot.add_cog(LatexRendererCog(bot))


if __name__ == '__main__':
    image_bytes = render_text(
        r'\theta=\theta+C(1+\theta-\beta)\sqrt{1-\theta}succ_mul')
    pathlib.Path('formula.png').write_bytes(image_bytes)
