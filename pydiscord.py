# -*- coding: utf-8 -*-
import discord
import os
from discord.ext import commands
# from discord_slash import SlashCommand
# from discord_components import DiscordComponents

COG_LIST = {
    'headCounter', 'slash', 'mainbot', 'musicV2', 'old_ytdl',
    'pixivRec', 'queueSys', 'reactionRole', 'trigger_meme', 
    'trpgUtil', 'selectRoleV2', 'askAI', 
}

def main():
    absFilePath = os.path.abspath(__file__)
    os.chdir( os.path.dirname(absFilePath))

    with open('./acc/tokenDC.txt', 'r') as acc_file:
        acc_data = acc_file.read().splitlines()
        TOKEN = acc_data[0]
    
    intents = discord.Intents.all()
    client = commands.Bot(command_prefix='%', intents=intents)
    # atree = app_commands.CommandTree(client)
    # slash = SlashCommand(client, override_type = True, sync_commands = True)
    # DiscordComponents(client)
    @client.event
    async def on_ready():
        await client.change_presence(activity = discord.Game('debugger(殺蟲劑)'))
        # PreLoad
        client.LOADED_COG = {'mainbot', 'trpgUtil', 'askAI'}
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
        await ctx.send('Bye bye.')
        await client.close()

    # Game Start!
    client.run(TOKEN)

if __name__ == "__main__":
    main()
