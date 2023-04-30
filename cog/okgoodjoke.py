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
    
def nameChk(s):
    for emoji in emoji2id:
        if emoji in s: return emoji2id[emoji]
    return -1

class okgoodjoke(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: DC_Client):
        self.bot = bot
        global memo
        memo = dict()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        emj = str(payload.emoji)
        if payload.guild_id == 477839636404633600:
            ch = self.bot.get_partial_messageable(payload.channel_id, guild_id=payload.guild_id)
            msg = await ch.fetch_message(payload.message_id)
            uid = msg.author.id
            mdc = {str(emoji) : emoji.count for emoji in msg.reactions}[emj]
            if mdc == 3 and (eid:=nameChk(emj)) != -1:
                if uid not in emojiArr.index:
                    emojiArr.loc[uid] = 0
                emojiArr.loc[uid].iloc[eid] += 1
                t = emojiArr.iloc[:,eid].sort_values(ascending=False).head(5)
                sb = sepLines((f'{wcformat(self.bot.get_user(i).name)}: {v}'for i, v in zip(t.index, t.values)))
                return await ch.send(f'{emj} Scoreboard:\n```{sb}```', reference=msg)
                
async def setup(bot):
    localRead()
    await bot.add_cog(okgoodjoke(bot))
    
async def teardown(bot):
    print('emoji saved')
    # print(emojiArr)
    emojiArr.to_csv('./acc/emojiArr.csv')