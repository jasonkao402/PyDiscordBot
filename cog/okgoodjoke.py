from collections import deque
import pandas as pd
from discord import RawReactionActionEvent
from discord.ext import commands
from cog.utilFunc import sepLines, wcformat
import numpy as np

MEMOLEN = 32
cachedMsg = deque(maxlen=MEMOLEN)
okok = '''👌 🆗
❓ ❔
🈸 🥵
🛐 💯 ⚡
😡
'''.splitlines()

emojiArr = pd.read_csv('./acc/emojiArr.csv', index_col='uid', dtype=np.int64).fillna(0)

def localRead():
    global emoji2id, id2emoji, okok
    setsys_tmp = okok
    emoji2id, id2emoji = {}, []
    for i in range(len(setsys_tmp)):
        id2emoji.append(setsys_tmp[i].split(maxsplit=1)[0])
        emoji2id.update((alias, i) for alias in setsys_tmp[i].split())
    # print(emoji2id)
    
def nameChk(s):
    for emoji in emoji2id:
        if emoji in s: return emoji2id[emoji]
    return -1

class okgoodjoke(commands.Cog):
    __slots__ = ('bot')

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload:RawReactionActionEvent):
        emj, mid = str(payload.emoji), payload.message_id
        if payload.guild_id == 477839636404633600 and mid not in cachedMsg:
            ch = self.bot.get_partial_messageable(payload.channel_id, guild_id=payload.guild_id)
            msg = await ch.fetch_message(payload.message_id)
            uid = msg.author.id
            emoji_count = {str(emoji) : emoji.count for emoji in msg.reactions}[emj]
            
            if emoji_count >= 1 and (eid:=nameChk(emj)) != -1:
                cachedMsg.append(mid)
                if uid not in emojiArr.index:
                    emojiArr.loc[uid, :] = 0
                print(emojiArr)
                emojiArr.loc[uid, str(eid)] += 1
                top_users  = emojiArr.iloc[:,eid].nlargest(5)
                ranking_text = sepLines(
                    f'{username.name if (username := self.bot.get_user(i)) else "ERROR"}: {v}'
                    for i, v in zip(top_users.index, top_users.values)
                )
                return await ch.send(f'{emj} Emoji Rank:\n```{ranking_text}```', reference=msg, silent=True)
    
    @commands.hybrid_command(name = 'erank')
    async def _emojiRank(self, ctx:commands.Context, emj:str):
        uid, eid = ctx.author.id, nameChk(emj)
        if ctx.guild.id == 477839636404633600:
            if uid not in emojiArr.index:
                emojiArr.loc[uid, :] = 0
            if eid == -1:
                return await ctx.send(f'{emj} Emoji Rank 404 not found.', silent=True)
            # print('debug', eid)
            top_users  = emojiArr.iloc[:,eid].nlargest(5)
            ranking_text = sepLines(
                f'{username.name if (username := self.bot.get_user(user_id)) else "ERROR"}: {v}'
                for user_id, v in zip(top_users.index, top_users.values)
            )
            return await ctx.send(f'{emj} Emoji Rank:\n```{ranking_text}```', silent=True)

async def setup(bot:commands.Bot):
    localRead()
    await bot.add_cog(okgoodjoke(bot))
    
async def teardown(bot):
    print('emoji saved')
    # print(emojiArr)
    # emojiArr = emojiArr.astype(np.int64)
    emojiArr.to_csv('./acc/emojiArr.csv')
    print(emojiArr)

if __name__ == '__main__':
    print(emojiArr)