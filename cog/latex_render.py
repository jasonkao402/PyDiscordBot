from discord import File as DC_File, Client as DC_Client
from discord.ext import commands
import sympy
import matplotlib.pyplot as plt
from io import BytesIO

def render_text(formula:str, fontsize=12, dpi=256) -> bytes:
    """Renders LaTeX formula into image."""
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, u'${}$'.format(formula), fontsize=fontsize)
    buffer_ = BytesIO()
    fig.savefig(buffer_, dpi=dpi, transparent=False, format='png', bbox_inches='tight', pad_inches=0.02)
    buffer_.seek(0)
    plt.close(fig)
    
    return buffer_.getvalue()

class latex_render(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
    
    @commands.hybrid_command(name = 'latex')
    async def _latex(self, ctx, *, args:str):
        # print(args, len(args))
        b = render_text(args)
        await ctx.send(file=DC_File(fp=BytesIO(b), filename='latex_.png'))
                
async def setup(bot):
    await bot.add_cog(latex_render(bot))
    
if __name__ == '__main__':
    image_bytes = render_text(
        r'\theta=\theta+C(1+\theta-\beta)\sqrt{1-\theta}succ_mul')
    with open('formula.png', 'wb') as image_file:
        image_file.write(image_bytes)