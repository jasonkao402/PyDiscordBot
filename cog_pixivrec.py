from discord.ext import commands
from pixivpy3 import AppPixivAPI
import random
import os

POSINT = '正整數啦!  (´_ゝ`)\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'

class pixivRec(commands.Cog):
    """Main functions."""
    __slots__ = ('bot', "papi")
    
    def __init__(self, bot):
        self.bot = bot
        
        absFilePath = os.path.abspath(__file__)
        os.chdir( os.path.dirname(absFilePath))
        with open('./acc/tokenPX.txt', 'r') as acc_file:
            acc_data = acc_file.read().splitlines()
            REFRESH_TOKEN = acc_data[0]

        self.papi = AppPixivAPI()
        self.papi.auth(refresh_token=REFRESH_TOKEN)

    @commands.command(name = 'pget', aliases=['getloli'])
    async def _pget(self, ctx, rpt : int = 1):
        USER = ctx.author
        try:
            rpt = int(rpt)
        except:
            await ctx.send(BADARGUMENT, delete_after=20)
            print('pget cmd error')
            return
        if rpt <= 0 :
            await ctx.send(POSINT)
        elif rpt <= 10 :
            json_result = self.papi.user_bookmarks_illust(26019898)
            illusts = json_result.illusts

            await ctx.send(f'{USER.mention}, fetched {len(illusts)}', delete_after=20)
            print(f'fetched {len(illusts)}')
            if(len(illusts) > 0) : 
                for i in random.sample(illusts, rpt):
                    #papi.download(i.image_urls.large, fname='i_%s.jpg' % (i.id))
                    #await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (i.id), file = discord.File('i_%s.jpg' % (i.id) ))
                    await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (i.id))
        else :
            await ctx.send(f'{USER.mention}, 太...太多了啦! (> д <)', delete_after=20)
        
    @commands.command(name = 'psearch')
    async def _psearch(self, ctx, tgt):
        poll = 34
        offset = 0
        accepted = []
        json_result = self.papi.search_illust(tgt, search_target='partial_match_for_tags')
        illusts = json_result.illusts

        if not isinstance(illusts, list):
            print('[find none...]')
            await ctx.send('窩找不到香圖 QAQ')

        else:
            print('[searching...]')
            await ctx.send('[searching...]', delete_after = 5)
            for i in range(poll):
                print('\r%.2f%%' % (100*(i+1)/poll), end = '')
                next_qs = self.papi.parse_qs(json_result.next_url)
                if not next_qs:
                    print('\n[Stopped]')
                    await ctx.send('窩找不到香圖 QAQ')
                    return

                json_result = self.papi.search_illust(**next_qs)
                illusts+=json_result.illusts

            ilen = len(illusts)
            for i in illusts:
                offset += max(1500, i.total_bookmarks)
            offset /= ilen

            print('\n[pick from : %d, offset : %d]\n' % (ilen, offset))
            print('last : %s' % illusts[ilen-1].create_date)

            idx = 1
            for i in illusts:
                if ((i.total_bookmarks > offset and i.total_view/i.total_bookmarks < 4) or i.total_bookmarks > 9000) and i.x_restrict == 0:
                    accepted.append(i)
                    print('(%4d/%4d)    [%s]' % (idx, ilen, i.title))
                    print('like :%6d   view :%6d   1 : %.3f   %9d' % (i.total_bookmarks, i.total_view, i.total_view/i.total_bookmarks, i.id))
                idx+=1

            alen = len(accepted)
            print('\n[accepted : %d, offset : %d]\n' % (alen,offset))

            await ctx.send('from %d picked %d, offset : %d.' % (ilen, alen, offset), delete_after=30)
            if alen:
                a = random.choice(accepted)
                print('(%2d/%2d)       [%s]' % (idx, alen, a.title))
                print('like:%6d   view:%6d   1 : %.3f   ID = %9d' % (a.total_bookmarks, a.total_view, a.total_view/a.total_bookmarks, a.id))
                #papi.download(a.image_urls.medium, fname='i_%d.jpg' % (a.id))
                #await ctx.send(content = 'PixivID : %d' % (a.id), file = discord.File('i_%s.jpg' % (a.id) ))
                await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (a.id))

def setup(bot):
    bot.add_cog(pixivRec(bot))
