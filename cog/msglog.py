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

async def setup(bot:commands.Bot):
    await bot.add_cog(msglog(bot))

async def teardown(bot:commands.Bot):
    # scoreArr.to_csv('./acc/scoreArr.csv')
    # json.
    print('msg saved')