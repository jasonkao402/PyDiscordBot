import json
import os
import discord
from discord.ext import commands
import toml
from typing import Optional
from config_loader import configToml, loadToml

def run_discord():
    absFilePath = os.path.abspath(__file__)
    currWorkDir = os.path.dirname(absFilePath)
    os.chdir(currWorkDir)
    
    global client, COG_LIST, LOADED_COG
    
    # PreLoad
    COG_LIST, LOADED_COG = set(), {'mainbot', 'askAI', 'okgoodjoke', 'latex_render', 'msglog', 'personality', 'drawing_sd'}
    cog_folder = os.path.join(currWorkDir, 'cog')
    for file in os.listdir(cog_folder):
        if file.endswith('.py'):
            file = os.path.splitext(file)[0]
            COG_LIST.add(file)
    
    # Instaniate bot client
    intents = discord.Intents.all()
    client = commands.Bot(command_prefix='%', intents=intents)
    
    async def sync_tree(guild):
        avail_cmds = await client.tree.sync(guild=guild)
        print(f'synced {len(avail_cmds)} commands')
        for cmd in avail_cmds:
            print(f' - {cmd}')

    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        for c in LOADED_COG:
            await client.load_extension(f'cog.{c}')
        # avail_cmds = await client.tree.sync()
        await sync_tree(None)
        print('Bot is online.')
        print('Default cogs loaded : ', LOADED_COG)
        # print(f'synced {len(avail_cmds)} commands')

    @client.event
    async def on_connect():
        print(f'Connected, discord latency: {round(client.latency*1000)} ms')

    @client.hybrid_command(name = 'reload')
    @commands.is_owner()
    async def _reload(ctx:commands.Context):
        suc = 0
        for c in LOADED_COG:
            await client.reload_extension(f'cog.{c}')
            suc += 1
        
        await ctx.send(f'{suc} reloaded and sync done in {ctx.guild.name}')
        await sync_tree(ctx.guild)

    @client.command()
    @commands.is_owner()
    async def load(ctx:commands.Context, *args):
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
    @commands.is_owner()
    async def unload(ctx:commands.Context, *args):
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
    @commands.is_owner()
    async def close(ctx:commands.Context):
        await ctx.send(f'cya {ctx.author.mention}')
        await client.close()
        
    @client.hybrid_command(name = 'toml')
    @commands.is_owner()
    async def _toml(ctx:commands.Context):
        global configToml
        configToml = loadToml()
        configToml.pop('apiToken', None)
        await ctx.send(f'toml reload done.```json\n{json.dumps(configToml["llmChat"], indent=2, ensure_ascii=False)}```')
    
    # Load API token, and delete it from configToml
    TOKEN = configToml['apiToken']['discord']
    configToml.pop('apiToken', None)
    # Start!
    client.run(TOKEN)

if __name__ == "__main__":
    run_discord()
