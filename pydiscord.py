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

COG_LIST = {'headCounter', 'mainbot', 'musicV2', 'old_ytdl', 'pixivRec', 'queueSys', 'reactionRole', 'trigger_meme'}

def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))

    with open('./acc/tokenDC.txt', 'r') as acc_file:
        acc_data = acc_file.read().splitlines()
        TOKEN = acc_data[0]
    
    intents = discord.Intents.default()
    intents.members = True
    client = commands.Bot(command_prefix='%', intents=intents)

    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        client.LOADED_COG = {'mainbot', 'queueSys'}
        for c in client.LOADED_COG:
            client.load_extension(f'cog.{c}')
        print('\nBot ready.\n')

    @client.event
    async def on_connect():
        print(f'Discord latency: {round(client.latency*1000)} ms')

    @client.command()
    async def reload(ctx):
        suc = 0
        for c in client.LOADED_COG:
            client.reload_extension(f'cog.{c}')
            suc += 1
        await ctx.send(f'reload {suc} cog done')
        print(f'[C] reloaded {suc}')

    @client.command()
    async def load(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or '-l' in args:
            await ctx.send(f"available cogs : {',  '.join(COG_LIST)}")
            return

        elif '-a' in args:
            for c in COG_LIST:
                suc+=1
                client.load_extension(f'cog.{c}')

        else:
            for c in args:
                if c in client.LOADED_COG:
                    fal+=1
                    print(f"{c} already loaded")
                elif c in COG_LIST:
                    suc+=1
                    client.LOADED_COG.add(c)
                    client.load_extension(f'cog.{c}')
                    print(f"{c} load done")
                else:
                    fal+=1
                    print(f"{c} not exist")
        await ctx.send(f'load {suc} done,  load {fal} failed')
        print('[C] loaded, now : ', client.LOADED_COG)

    @client.command()
    async def unload(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or ('-l' in args):
            await ctx.send(f"current loaded : {',  '.join(client.LOADED_COG)}")
            return

        elif '-a' in args:
            for c in client.LOADED_COG:
                client.unload_extension(f'cog.{c}')
            # reset loaded set
            client.LOADED_COG = set()
            await ctx.send('full unload completed')
        
        for c in args:
            if c in client.LOADED_COG:
                suc+=1
                client.LOADED_COG.remove(c)
                client.unload_extension(f'cog.{c}')
                print(f"{c} unload done")
            else:
                fal+=1
                print(f"{c} not exist")
        await ctx.send(f'unload {suc} done,  unload {fal} failed')
        print('[C] unloaded, now : ', client.LOADED_COG)

    # Game Start!
    client.run(TOKEN)

if __name__ == "__main__":
    main()
