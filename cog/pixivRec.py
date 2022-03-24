from discord.ext import commands
from pixivpy3 import AppPixivAPI
import random
from math import log
POSINT = '正整數啦!  (´_ゝ`)\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'

class pixivRec(commands.Cog):
    """Main functions."""
    __slots__ = ('bot', "papi")
    
    def __init__(self, bot):
        self.bot = bot
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
        elif rpt <= 5 :
            json_result = self.papi.user_bookmarks_illust(26019898)
            mybook = json_result.illusts
            for i in range(4):
                next_qs = self.papi.parse_qs(json_result.next_url)
                if not next_qs:
                    print('\n[Stopped]')
                    break
                json_result = self.papi.user_bookmarks_illust(**next_qs)
                mybook+=json_result.illusts
            print(len(mybook))
            await ctx.send(f'{USER.mention}, fetched {len(mybook)}', delete_after=20)
            print(f'fetched {len(mybook)}')
            if(len(mybook) > 0) : 
                for i in random.sample(mybook, rpt):
                    #papi.download(i.image_urls.large, fname='i_%s.jpg' % (i.id))
                    #await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (i.id), file = discord.File('i_%s.jpg' % (i.id) ))
                    await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (i.id))
        else :
            await ctx.send(f'{USER.mention}, 太...太多了啦! (> д <)', delete_after=20)
        
    @commands.command(name = 'psearch')
    async def _psearch(self, ctx, *tgt):
        tgt = " ".join(tgt)
        print(f'{ctx.author} : {tgt}')
        coeffs = [-5.6, 1.33, -0.095]
        poll = 24
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
                print(f'{i}/{poll}', end = '\r')
                next_qs = self.papi.parse_qs(json_result.next_url)
                if not next_qs:
                    print('\n[Stopped]')
                    await ctx.send('窩找不到香圖 QAQ')
                    return

                json_result = self.papi.search_illust(**next_qs)
                illusts+=json_result.illusts

            ilen = len(illusts)

            print(f'\n[pick from : {ilen}]\n')
            print(f'last : {illusts[ilen-1].create_date}')

            for ilu in illusts:
                if ilu.total_bookmarks < 100: continue
                x = log(ilu.total_view)
                y = log(ilu.total_bookmarks) - x

                if y > sum(coeffs[j]*( x**j) for j in range(len(coeffs))) and x > 6:
                    accepted.append(ilu)
                    print('(%4d/%4d)    [%s]' % (i, ilen, ilu.title))
                    print('like :%6d   view :%6d   1 : %.3f   %9d' % (ilu.total_bookmarks, ilu.total_view, ilu.total_view/ilu.total_bookmarks, ilu.id))
                i+=1

            alen = len(accepted)
            print(f'\n[accepted : {alen}]\n')

            await ctx.send(f'from {ilen} picked {alen}.', delete_after=30)
            if alen:
                a = random.choice(accepted)
                print('(%2d/%2d)       [%s]' % (i, alen, a.title))
                print('like:%6d   view:%6d   1 : %.3f   ID = %9d' % (a.total_bookmarks, a.total_view, a.total_view/a.total_bookmarks, a.id))
                #papi.download(a.image_urls.medium, fname='i_%d.jpg' % (a.id))
                #await ctx.send(content = 'PixivID : %d' % (a.id), file = discord.File('i_%s.jpg' % (a.id) ))
                await ctx.send(content = 'https://www.pixiv.net/artworks/%s' % (a.id))

def setup(bot):
    bot.add_cog(pixivRec(bot))
