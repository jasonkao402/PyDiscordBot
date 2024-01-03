from datetime import datetime, timedelta, timezone
from discord.ext import commands, tasks
from discord import Client as DC_Client, Embed, Color
from cog.utilFunc import utctimeFormat, TWTZ

timet = datetime.now(timezone.utc) + timedelta(seconds=-10)
timet = timet.time()
    
class botSchedule(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.channel = self.bot.get_channel(1088253899871371284)
        # self.my_task.start()

    def cog_unload(self):
        self.my_task.cancel()
        
    @commands.hybrid_command(name = 'schedule')
    async def _schedule(self, ctx, *, args:str):
        dt = datetime.now(timezone.utc) + timedelta(seconds=int(args))
        
        self.channel = ctx.channel
        tsk = self.my_task
        tsk.change_interval(time=dt.time())
        tsk.restart()
        
        embed = Embed(title = "您的AI貓娘伊莉亞", description = "伊莉亞來找主人了！", color = Color.random())
        embed.add_field(name = "時間", value = utctimeFormat(tsk.next_iteration))
        await ctx.send(embed = embed)
        
    @commands.hybrid_command(name = 'isrun')
    async def _isRun(self, ctx):
        if self.channel:
            embed = Embed(title = "您的AI貓娘伊莉亞", description = "伊莉亞來找主人了！", color = Color.random())
            embed.add_field(name = "時間", value = utctimeFormat(self.my_task.next_iteration))
            embed.add_field(name = "狀態", value = self.my_task.is_running())
            await ctx.send(embed=embed)
        
    @tasks.loop(time=timet)
    async def my_task(self):
        if self.channel:
            await self.channel.send('喵喵喵~')

async def setup(bot):
    await bot.add_cog(botSchedule(bot))
    
if __name__ == '__main__':
    # tw timezone
    timet = datetime.now(timezone.utc)
    print(timet)
    print(timet.astimezone(TWTZ))