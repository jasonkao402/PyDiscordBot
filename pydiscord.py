# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands

from cog.utilFunc import devChk

# COG_LIST = {
#     'headCounter', 'slash', 'mainbot', 'musicV2', 'old_ytdl',
#     'pixivRec', 'queueSys', 'reactionRole', 'trigger_meme', 
#     'trpgUtil', 'selectRoleV2', 'askAI', 
# }
COG_LIST = {'mainbot', 'askAI'}

with open('./acc/tokenDC.txt', 'r') as acc_file:
    acc_data = acc_file.read().splitlines()
    TOKEN = acc_data[0]
    
def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))
        
    intents = discord.Intents.all()
    global client
    client = commands.Bot(command_prefix='%', intents=intents)
    
    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        client.LOADED_COG = {'mainbot', 'askAI'}
        for c in client.LOADED_COG:
            await client.load_extension(f'cog.{c}')
        print('Bot is online.')

    @client.event
    async def on_connect():
        print(f'Connected, discord latency: {round(client.latency*1000)} ms')

    @client.hybrid_command(name = 'reload')
    # @commands.has_permissions(manage_guild=True)
    async def _reload(ctx):
        if devChk(ctx.author.id):
            suc = 0
            for c in client.LOADED_COG:
                await client.reload_extension(f'cog.{c}')
                suc += 1
            
            await client.tree.sync()
            await ctx.send(f'{suc} reloaded and sync done')
            print(f'[C] {suc} reloaded')

    @client.command()
    @commands.has_permissions(manage_guild=True)
    async def load(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or '-l' in args:
            await ctx.send(f"available cogs : {',  '.join(COG_LIST)}")
            return

        elif '-a' in args:
            for c in COG_LIST:
                suc+=1
                await client.load_extension(f'cog.{c}')

        else:
            for c in args:
                if c in client.LOADED_COG:
                    fal+=1
                    print(f"{c} already loaded")
                elif c in COG_LIST:
                    suc+=1
                    client.LOADED_COG.add(c)
                    await client.load_extension(f'cog.{c}')
                    print(f"{c} load done")
                else:
                    fal+=1
                    print(f"{c} not exist")
        await ctx.send(f'load {suc} done,  load {fal} failed')
        print('[C] loaded, now : ', client.LOADED_COG)

    @client.command()
    @commands.has_permissions(manage_guild=True)
    async def unload(ctx, *args):
        suc = 0
        fal = 0
        if (not args) or ('-l' in args):
            await ctx.send(f"current loaded : {',  '.join(client.LOADED_COG)}")
            return

        elif '-a' in args:
            for c in client.LOADED_COG:
                await client.unload_extension(f'cog.{c}')
            # reset loaded set
            client.LOADED_COG = set()
            await ctx.send('full unload completed')
        
        for c in args:
            if c in client.LOADED_COG:
                suc+=1
                client.LOADED_COG.remove(c)
                await client.unload_extension(f'cog.{c}')
                print(f"{c} unload done")
            else:
                fal+=1
                print(f"{c} not exist")
        await ctx.send(f'unload {suc} done,  unload {fal} failed')
        print('[C] unloaded, now : ', client.LOADED_COG)

    @client.command()
    @commands.has_permissions(manage_guild=True)
    async def close(ctx):
        await ctx.send('今天的網路夠多了。')
        await client.close()

    # Game Start!
    client.run(TOKEN)

if __name__ == "__main__":
    main()
