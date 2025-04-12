from discord.ext import commands
from discord import Message
from cog.utilFunc import devChk, loadToml
import re, json
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(filename='./acc/msgs.log', encoding='utf-8', level=logging.INFO)

class msglog(commands.Cog):
    """Main functions."""
    __slots__ = ('bot')
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logs = []
    
    @commands.Cog.listener()
    async def on_message(self, message:Message):
        user, text = message.author, message.content
        uid, userName = user.id, user.name
        userName = re.sub(r'[.#]', '', userName)
        
        if uid == self.bot.user.id:
            return
        logger.info(f'{userName} : {text}')
        # self.logs.append(f'{userName} : {text}')
    
    @commands.command(name='listmembers')
    async def list_members(self, ctx: commands.Context):
        # ctx.guild gives us the guild where the command was called
        guild = ctx.guild
        
        if not guild:
            await ctx.send("Oh no, I couldn’t find the guild! (>_<)")
            return
        
        # Get all members
        members = guild.members
        member_count = len(members)
        
        if member_count == 0:
            await ctx.send("Hmm, it seems there are no members here... or I can’t see them! (⁄⁄>ω<⁄⁄)")
            return
        
        # Join the list into a string (limit to avoid message length issues)
        response = f"Here are the {member_count} members in {guild.name}:\n"
        
        # write to txt file
        with open(f'./acc/members_{guild.id}.txt', 'w', encoding='utf-8') as f:
            for member in members:
                hexuid = f'{member.id:08x}'[-8:]
                f.write(f"{member.id},  {hexuid}, {member.name}\n")
        
        await ctx.send(response)

async def setup(bot:commands.Bot):
    await bot.add_cog(msglog(bot))

async def teardown(bot:commands.Bot):
    # scoreArr.to_csv('./acc/scoreArr.csv')
    # json.
    print('msg saved')