# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands
from cog.utilFunc import devChk, sepLines

with open('./acc/tokenDC.txt', 'r') as acc_file:
    acc_data = acc_file.read().splitlines()
    TOKEN = acc_data[0]
    
def main():
    absFilePath = os.path.abspath(__file__)
    currWorkDir = os.path.dirname(absFilePath)
    os.chdir(currWorkDir)
    
    global client, COG_LIST, LOADED_COG
    
    # PreLoad
    COG_LIST, LOADED_COG = set(), {'mainbot', 'askAI', 'okgoodjoke', 'latex_render'}
    cog_folder = os.path.join(currWorkDir, 'cog')
    for file in os.listdir(cog_folder):
        if file.endswith('.py'):
            file = os.path.splitext(file)[0]
            COG_LIST.add(file)
    
    # Instaniate bot client
    intents = discord.Intents.all()
    client = commands.Bot(command_prefix='%', intents=intents)
    
    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        # LOADED_COG = {'mainbot', 'askAI', 'okgoodjoke', 'tex'}
        for c in LOADED_COG:
            await client.load_extension(f'cog.{c}')
        # await client.tree.sync()
        print('Bot is online.')
        print('Default cogs loaded : ', LOADED_COG)

    @client.event
    async def on_connect():
        print(f'Connected, discord latency: {round(client.latency*1000)} ms')

    @client.hybrid_command(name = 'reload')
    # @commands.has_permissions(manage_guild=True)
    async def _reload(ctx):
        if devChk(ctx.author.id):
            suc = 0
            for c in LOADED_COG:
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
                if c in LOADED_COG:
                    fal+=1
                    print(f"{c} already loaded")
                elif c in COG_LIST:
                    suc+=1
                    LOADED_COG.add(c)
                    await client.load_extension(f'cog.{c}')
                    print(f"{c} load done")
                else:
                    fal+=1
                    print(f"{c} not exist")
        await ctx.send(f'load {suc} done,  load {fal} failed')
        print('[C] loaded, now : ', LOADED_COG)

    @client.command()
    @commands.has_permissions(manage_guild=True)
    async def unload(ctx, *args):
        global LOADED_COG
        suc = 0
        fal = 0
        if (not args) or ('-l' in args):
            await ctx.send(f"current loaded : {',  '.join(LOADED_COG)}")
            return

        elif '-a' in args:
            for c in LOADED_COG:
                await client.unload_extension(f'cog.{c}')
            # reset loaded set
            LOADED_COG = set()
            await ctx.send('full unload completed')
        
        for c in args:
            if c in LOADED_COG:
                suc+=1
                LOADED_COG.remove(c)
                await client.unload_extension(f'cog.{c}')
                print(f"{c} unload done")
            else:
                fal+=1
                print(f"{c} not exist")
        await ctx.send(f'unload {suc} done,  unload {fal} failed')
        print('[C] unloaded, now : ', LOADED_COG)

    @client.command()
    @commands.has_permissions(manage_guild=True)
    async def close(ctx):
        await ctx.send('今天的網路夠多了。')
        await client.close()

    # Start!
    client.run(TOKEN)

if __name__ == "__main__":
    main()
