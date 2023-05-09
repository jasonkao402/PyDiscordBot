from discord.ext import commands
from discord import Client as DC_Client, File as DC_File
from glob import glob
from os.path import basename, getsize
from cog.utilFunc import devChk

class networkVideo(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: DC_Client):
        self.bot = bot

    @commands.hybrid_command(name = 'video')
    async def _video(self, ctx:commands.Context, filename):
        if ctx.guild.id == 477839636404633600 or devChk(ctx.author.id):
            for path in glob('/home/lolisagiri/PyDiscordBot/.videos/*.mp4'):
                if filename == basename(path):
                    if getsize(path)/1048576 < 20:
                        await ctx.send(f'{filename} requested!', file=DC_File(path))
                    else:
                        await ctx.send(f'{filename} too big!')
                    return
            await ctx.send(f'{filename} not found!')
    
async def setup(bot):
    await bot.add_cog(networkVideo(bot))
    
async def teardown(bot):
    pass

if __name__ == '__main__':
    for path in glob('/home/lolisagiri/PyDiscordBot/.videos/*.mp4'):
        print(basename(path), getsize(path))