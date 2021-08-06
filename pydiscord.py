# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands

ERRORMSG = '我把你當朋友，你卻想玩壞我...  。･ﾟ･(つд`ﾟ)･ﾟ･\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'
NOTPLAYING = '前提是我有播東西啊~(っ・д・)っ\n'
MISSINGARG = '求後續(´・ω・`)\n'
POSINT = '正整數啦!  (´_ゝ`)\n'
MEME = ['不要停下來阿', '卡其脫離太', '穿山甲', '卡打掐', '豆花', '阿姨壓一壓', 'Daisuke']
COG_LIST = {'cog_trigger_meme', 'cog_ytdl', 'cog_pixivrec', 'cog_headCounter', 'cog_todolist'}

def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))

    with open('./acc/tokenDC.txt', 'r') as acc_file:
        acc_data = acc_file.read().splitlines()
        TOKEN = acc_data[0]
    
    client = commands.Bot(command_prefix='%')

    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # do NOT remove cog_mainbot
        client.load_extension("cog_mainbot")
        client.load_extension("cog_todolist")
        client.load_extension("cog_ytdl")
        client.LOADED_COG = {'cog_todolist', 'cog_ytdl'}
        print('\nBot is now online.')

    @client.command()
    async def reload(ctx):
        # main doesnt need reload = =
        #client.reload_extension("cog_mainbot")
        suc = 0
        for c in client.LOADED_COG:
            client.reload_extension(c)
            suc += 1
        await ctx.send(f'reload {suc} cog done')
        print(f'[C] reloaded {suc}')

    @client.command()
    async def load(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or '-l' in args:
            await ctx.send(',  '.join(COG_LIST))
            return

        elif '-a' in args:
            for cl in COG_LIST:
                suc+=1
                client.load_extension(cl)

        else:
            for cog in args:
                if cog in client.LOADED_COG:
                    fal+=1
                    print(f"{cog} already loaded")
                elif cog in COG_LIST:
                    suc+=1
                    client.LOADED_COG.add(cog)
                    client.load_extension(cog)
                    print(f"{cog} load done")
                else:
                    fal+=1
                    print(f"{cog} not exist")
        await ctx.send(f'load {suc} done\nload {fal} failed')
        print('[C] loaded, now : ', client.LOADED_COG)

    @client.command()
    async def unload(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or ('-l' in args):
            await ctx.send(f"current loaded : {',  '.join(client.LOADED_COG)}")
            return

        elif '-a' in args:
            for cl in client.LOADED_COG:
                client.unload_extension(cl)
            # reset loaded set
            client.LOADED_COG = set()
            await ctx.send('full unload completed')
        
        for cog in args:
            if cog in client.LOADED_COG:
                suc+=1
                client.LOADED_COG.remove(cog)
                client.unload_extension(cog)
                print(f"{cog} unload done")
            else:
                fal+=1
                print(f"{cog} not exist")
        await ctx.send(f'unload {suc} done\nunload {fal} failed')
        print('[C] unloaded, now : ', client.LOADED_COG)

    # Game Start!
    client.run(TOKEN)

if __name__ == "__main__":
    main()
