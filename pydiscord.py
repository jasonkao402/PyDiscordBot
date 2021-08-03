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
        client.load_extension("cog_mainbot")
        #client.load_extension("cog_trigger_meme")
        client.load_extension("cog_ytdl")
        #client.load_extension("cog_pixivrec")
        #client.load_extension("cog_headCounter")
        print('\nBot is now online.')

    @client.command()  
    async def reload(ctx):
        client.reload_extension("cog_mainbot")
        await ctx.send('reloading...0%', delete_after=1)
        #client.reload_extension("cog_trigger_meme")
        #client.reload_extension("cog_pixivrec")
        #await ctx.send('reloading...50%', delete_after=1)
        client.reload_extension("cog_ytdl")
        #client.reload_extension("cog_headCounter")
        await ctx.send('reload completed')
        print('\nBot cog reloaded')

    client.run(TOKEN)

if __name__ == "__main__":
    main()
