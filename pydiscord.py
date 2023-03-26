# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands

COG_LIST = {
    'headCounter', 'slash', 'mainbot', 'musicV2', 'old_ytdl',
    'pixivRec', 'queueSys', 'reactionRole', 'trigger_meme', 
    'trpgUtil', 'selectRoleV2', 'askAI', 
}

with open('./acc/tokenDC.txt', 'r') as acc_file:
    acc_data = acc_file.read().splitlines()
    TOKEN = acc_data[0]
with open('./acc/aiSet_extra.txt', 'r', encoding='utf-8') as set1_file:
    setsys_extra = set1_file.read()
with open('./acc/aiSet_base.txt', 'r', encoding='utf-8') as set2_file:
    setsys_base = set2_file.read()
    # setsys = {'role': 'system', 'content': acc_data}
    setsys = {'role': 'system', 'content': setsys_base + setsys_extra}
    
def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))
        
    intents = discord.Intents.all()
    global client
    client = commands.Bot(command_prefix='%', intents=intents)
    # atree = app_commands.CommandTree(client)
    # slash = SlashCommand(client, override_type = True, sync_commands = True)
    # DiscordComponents(client)
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

    @client.command(aliases = ['rl'])
    @commands.has_permissions(manage_guild=True)
    async def reload(ctx):
        suc = 0
        for c in client.LOADED_COG:
            await client.reload_extension(f'cog.{c}')
            suc += 1
        
        await client.tree.sync()
        await ctx.send(f'reload {suc} cog and sync done')
        print(f'[C] reloaded {suc}')

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
