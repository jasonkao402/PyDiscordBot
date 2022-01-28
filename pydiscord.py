# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands
from discord_slash import SlashCommand

ERRORMSG = '我把你當朋友，你卻想玩壞我...  。･ﾟ･(つд`ﾟ)･ﾟ･\n'
BADARGUMENT = '參數 Bad!  (#`Д´)ノ\n'
NOTPLAYING = '前提是我有播東西啊~(っ・д・)っ\n'
MISSINGARG = '求後續(´・ω・`)\n'
POSINT = '正整數啦!  (´_ゝ`)\n'
MEME = ['不要停下來阿', '卡其脫離太', '穿山甲', '卡打掐', '豆花', '阿姨壓一壓', 'Daisuke']

COG_LIST = {
    'headCounter', 'slash', 'mainbot', 'musicV2', 'old_ytdl',
    'pixivRec', 'queueSys', 'reactionRole', 'trigger_meme', 'trpgUtil'
}

def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))

    with open('./acc/tokenDC.txt', 'r') as acc_file:
        acc_data = acc_file.read().splitlines()
        TOKEN = acc_data[0]
    
    intents = discord.Intents.all()
    botCli = commands.Bot(command_prefix='%', intents=intents)
    slash = SlashCommand(botCli, override_type = True, sync_commands = True)
    @botCli.event
    async def on_ready():
        await botCli.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        botCli.LOADED_COG = {'mainbot', 'queueSys', 'trpgUtil', 'slash'}
        for c in botCli.LOADED_COG:
            botCli.load_extension(f'cog.{c}')
        print('\nBot ready.\n')

    @botCli.event
    async def on_connect():
        print(f'Discord latency: {round(botCli.latency*1000)} ms')

    @botCli.command()
    async def reload(ctx):
        suc = 0
        for c in botCli.LOADED_COG:
            botCli.reload_extension(f'cog.{c}')
            suc += 1
        await ctx.send(f'reload {suc} cog done')
        print(f'[C] reloaded {suc}')

    @botCli.command()
    async def load(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or '-l' in args:
            await ctx.send(f"available cogs : {',  '.join(COG_LIST)}")
            return

        elif '-a' in args:
            for c in COG_LIST:
                suc+=1
                botCli.load_extension(f'cog.{c}')

        else:
            for c in args:
                if c in botCli.LOADED_COG:
                    fal+=1
                    print(f"{c} already loaded")
                elif c in COG_LIST:
                    suc+=1
                    botCli.LOADED_COG.add(c)
                    botCli.load_extension(f'cog.{c}')
                    print(f"{c} load done")
                else:
                    fal+=1
                    print(f"{c} not exist")
        await ctx.send(f'load {suc} done,  load {fal} failed')
        print('[C] loaded, now : ', botCli.LOADED_COG)

    @botCli.command()
    async def unload(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or ('-l' in args):
            await ctx.send(f"current loaded : {',  '.join(botCli.LOADED_COG)}")
            return

        elif '-a' in args:
            for c in botCli.LOADED_COG:
                botCli.unload_extension(f'cog.{c}')
            # reset loaded set
            botCli.LOADED_COG = set()
            await ctx.send('full unload completed')
        
        for c in args:
            if c in botCli.LOADED_COG:
                suc+=1
                botCli.LOADED_COG.remove(c)
                botCli.unload_extension(f'cog.{c}')
                print(f"{c} unload done")
            else:
                fal+=1
                print(f"{c} not exist")
        await ctx.send(f'unload {suc} done,  unload {fal} failed')
        print('[C] unloaded, now : ', botCli.LOADED_COG)

    @botCli.command()
    @commands.has_role('botMaster')
    async def close(ctx):
        await ctx.send('Bye bye.')
        await botCli.close()

    # Game Start!
    botCli.run(TOKEN)

if __name__ == "__main__":
    main()
