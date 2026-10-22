import asyncio
import json
import logging
import os
import traceback
from pathlib import Path
from typing import Optional

import discord
import uvicorn
from discord.ext import commands

import cog_dev.web_api as web_api
from cog_dev.moderation import PendingMessageManager
from config_loader import configToml, loadToml
from helper_func.chat_context_manager import ChatContextManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("setup_bot")

BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

def get_available_cogs() -> set[str]:
    """Return all .py files in the configured cog directory as 'cog.filename'."""
    cog_dir = Path(configToml.get("discord_bot", {}).get("cog_directory", "./cog"))
    if not cog_dir.exists():
        return set()
    return {f"{cog_dir.name}.{f.stem}" for f in cog_dir.glob("*.py") if not f.name.startswith("_")}

def ext_name(name: str) -> str:
    """Normalize 'askAI' -> 'cog.askAI'."""
    cog_pkg = Path(configToml.get("discord_bot", {}).get("cog_directory", "./cog")).name
    return name if "." in name else f"{cog_pkg}.{name}"

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="%", intents=discord.Intents.all())
        self.chat_state: ChatContextManager
        self.debug_guild_cache: Optional[discord.Guild] = None
        self.debug_channel_cache: Optional[discord.PartialMessageable] = None

    @property
    def bot_config(self) -> dict:
        return configToml.get("discord_bot", {})

    @property
    def debug_guild_id(self) -> Optional[discord.Guild]:
        if self.debug_guild_cache is not None:
            return self.debug_guild_cache
        gid = self.bot_config.get("debug_guild_id", -1)
        return self.get_guild(gid) if isinstance(gid, int) and gid > 0 else None

    @property
    def debug_channel(self) -> Optional[discord.PartialMessageable]:
        if self.debug_channel_cache is not None:
            return self.debug_channel_cache
        cid = self.bot_config.get("debug_channel_id", -1)
        return self.get_partial_messageable(cid) if isinstance(cid, int) and cid > 0 else None

    async def sync_tree(self, target_guild: Optional[discord.abc.Snowflake] = None):
        """Sync the command tree to a specific guild or globally."""
        if target_guild:
            self.tree.copy_global_to(guild=target_guild)
            cmds = await self.tree.sync(guild=target_guild)
        else:
            cmds = await self.tree.sync()

        logger.info(f"Synced {len(cmds)} commands: {[c.name for c in cmds]}")

    async def setup_hook(self):
        # 1. Attach shared state singleton
        self.chat_state = ChatContextManager()

        # 2. Load preload cogs from config.toml
        for cog in self.bot_config.get("preload", []):
            await self.load_extension(ext_name(cog))
        logger.info(f"Preloaded cogs: {list(self.extensions.keys())}")

        # 3. Sync slash commands to debug guild for faster iteration during development
        gid = self.bot_config.get("debug_guild_id", -1)
        if isinstance(gid, int) and gid > 0:
            await self.sync_tree(target_guild=self.get_guild(gid))
        else:
            await self.sync_tree()  # Sync globally if no debug guild is specified

    async def on_ready(self):
        activity = self.bot_config.get("activity", "正在殺蟲...(debugging...)")
        await self.change_presence(activity=discord.Game(activity))
        logger.info(f"Bot is online as {self.user}")

    async def on_connect(self):
        logger.info(f"Connected! Latency: {round(self.latency * 1000)} ms")

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        traceback.print_exception(type(error), error, error.__traceback__)

    async def close(self):
        if self.chat_state:
            await self.chat_state.cleanup()
        await super().close()


def register_admin_commands(client: MyBot):
    @client.hybrid_command(name="reload", description="Reload all loaded cogs and sync slash commands.")
    @commands.is_owner()
    async def _reload(ctx: commands.Context):
        await ctx.defer()
        loaded = list(client.extensions.keys())
        for ext in loaded:
            await client.reload_extension(ext)

        await client.sync_tree()
        await ctx.send(f"Reloaded `{len(loaded)}` cogs and synced commands.")

    @client.hybrid_command(name="sync", description="Sync slash commands to a specific guild or globally.")
    @commands.is_owner()
    async def _sync(ctx: commands.Context, guild_id: Optional[int] = None):
        target_guild = client.get_guild(guild_id) if guild_id else None
        await client.sync_tree(target_guild)
        await ctx.send(f"Synced commands to {target_guild.name if guild_id else 'global scope'}.")

    @client.command(name="load")
    @commands.is_owner()
    async def _load(ctx: commands.Context, *args: str):
        available = get_available_cogs()
        loaded = set(client.extensions.keys())

        if not args or "-l" in args:
            await ctx.send(f"**Available:** `{', '.join(available)}`\n**Loaded:** `{', '.join(loaded)}`")
            return

        targets = (available - loaded) if "-a" in args else [ext_name(a) for a in args]
        suc, fal = 0, 0
        for ext in targets:
            if ext not in loaded and ext in available:
                await client.load_extension(ext)
                suc += 1
            else:
                fal += 1
        await ctx.send(f"Load: `{suc}` done, `{fal}` failed/already loaded.")

    @client.command(name="unload")
    @commands.is_owner()
    async def _unload(ctx: commands.Context, *args: str):
        loaded = list(client.extensions.keys())
        if not args or "-l" in args:
            await ctx.send(f"**Loaded:** `{', '.join(loaded)}`")
            return

        targets = loaded if "-a" in args else [ext_name(a) for a in args]
        suc, fal = 0, 0
        for ext in targets:
            if ext in client.extensions:
                await client.unload_extension(ext)
                suc += 1
            else:
                fal += 1
        await ctx.send(f"Unload: `{suc}` done, `{fal}` failed.")

    @client.hybrid_command(name="toml", description="Reload config.toml in-place.")
    @commands.is_owner()
    async def _toml(ctx: commands.Context):
        loadToml()
        llm_cfg = json.dumps(configToml.get("llm_model", {}), indent=2, ensure_ascii=False)
        await ctx.send(f"`config.toml` reloaded.\n```json\n{llm_cfg}```")

    @client.command(name="close")
    @commands.is_owner()
    async def _close(ctx: commands.Context):
        await ctx.send(f"cya {ctx.author.mention}")
        await client.close()
        
async def run_discord():
    client = MyBot()
    register_admin_commands(client)

    token = configToml.get("api_token", {}).get("discord")
    if not token:
        raise RuntimeError("Missing [api_token].discord in config.toml")
    # Start!
    pending_manager = PendingMessageManager(update_callback=web_api.push_update)
    web_api.pending_manager = pending_manager # Export to web_api so that UI can get it
    
    bot_task = asyncio.create_task(client.start(token))
    
    # Run web API in background
    host = configToml.get("webui", {}).get("host", "localhost")
    port = configToml.get("webui", {}).get("port", 8080)
    uvicorn_config = uvicorn.Config("cog_dev.web_api:app", host=host, port=port, log_level="info")
    server = uvicorn.Server(uvicorn_config)
    api_task = asyncio.create_task(server.serve())
    
    try:
        # Wait until the user quits the chatbot
        await bot_task
    except asyncio.CancelledError:
        pass
    finally:
        # Gracefully shut down the web server
        print("\nShutting down web server...")
        server.should_exit = True
        await api_task

if __name__ == "__main__":
    try:
        asyncio.run(run_discord())
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Shutting down...")
    finally:
        print("Application shutdown complete.")