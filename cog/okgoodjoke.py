import pandas as pd
from discord.ext import commands
from cog.utilFunc import sepLines, wcformat
from discord import Client as DC_Client

memo = dict()
okok = '''👌 🆗
❓ ❔
🈸
'''.splitlines()

emojiArr = pd.read_csv('./acc/emojiArr.csv', index_col='uid', dtype=int)

def localRead():
    global emoji2id, id2emoji, okok
    setsys_tmp = okok
    emoji2id, id2emoji = {}, []
    for i in range(len(setsys_tmp)):
        id2emoji.append(setsys_tmp[i].split(maxsplit=1)[0])
        emoji2id.update((alias, i) for alias in setsys_tmp[i].split())
    print(emoji2id)
    
def nameChk(s) -> tuple:
    for name in emoji2id:
        if name in s: return emoji2id[name], name
    return -1, ''

class okgoodjoke(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        global memo
        memo = dict()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id == 477839636404633600:
            ch = self.bot.get_partial_messageable(payload.channel_id, guild_id=payload.guild_id)
            msg = await ch.fetch_message(payload.message_id)
            mdc = {emoji.__str__ : emoji.count for emoji in msg.reactions}
            for k, v in mdc.items():
                if v >= 2:
                    ch.send()
                
async def setup(bot):
    localRead()
    await bot.add_cog(okgoodjoke(bot))
    
async def teardown(bot):
    print('emoji saved')
    print(emojiArr)
    emojiArr.to_csv('./acc/emojiArr.csv')