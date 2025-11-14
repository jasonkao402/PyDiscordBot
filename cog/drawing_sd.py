from discord import Client as DC_Client
from discord import Interaction, app_commands, File
from discord.ext import commands
from aiohttp import ClientSession, TCPConnector
from time import strftime
from config_loader import configToml
from typing import Optional
from cog.utilFunc import clamp
import base64
import asyncio
from datetime import datetime, timezone, timedelta
class SDImage_APIHandler():
    def __init__(self):
        self.connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = ClientSession(connector=self.connector)
    
    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("SDImage Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("SDImage Connector closed")

    async def imageGen(self, prompt:str, width:int = 640, height:int = 640):
        payload = {
            "prompt": prompt,
            "negative_prompt": configToml['llmChat'].get('promptNeg', ''),
            "steps": 20,
            "width": width,
            "height": height,
            "sampler_name": "DPM++ 2S a",
            "cfg_scale": 8.0,
        }
        print(f"SD Image Gen Payload:\n\t{payload['prompt']}\n\t{payload['width']}x{payload['height']}")
        async with self.clientSession.post(configToml['llmChat']['linkSDImg'], json=payload) as request:
            response = await request.json()
        return response

# Rate limit per hour
RATELIMIT_SDIMAGE_API = 6

class drawing_sd(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.sdimageAPI = SDImage_APIHandler()
        self.isEnabled = True
        self.reenable_timestamp = None
        
    # TODO: Refactor to other dedicated cog
    @app_commands.command(name = 'sd2')
    @app_commands.describe(prompt = 'Prompt for the image', width = 'Width of the image', height = 'Height of the image')
    @commands.cooldown(RATELIMIT_SDIMAGE_API, 3600.0, commands.BucketType.user)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    async def _sd2(self, interaction: Interaction, prompt:str, width: Optional[int] = 640, height: Optional[int] = 640):
        
        if self.isEnabled is False:
            await interaction.response.send_message(f"Drawing cog is currently disabled.\nRe-enable at <t:{int(self.reenable_timestamp.timestamp())}:R>", ephemeral=True)
            return
        
        # clip w and h to 512 - 1024, in step of 16
        width  = clamp((width  + 8) // 16 * 16, 512, 1024)
        height = clamp((height + 8) // 16 * 16, 512, 1024)

        await interaction.response.defer()
        response = await self.sdimageAPI.imageGen(prompt, width, height)
        for image in response['images']:
            dest = f'acc/imgLog/{strftime("%Y_%m%d_%H%M")}.png'
            with open(dest, 'wb') as f:
                f.write(base64.b64decode(image))
        await interaction.followup.send(prompt, file=File(dest))
    
    @app_commands.command(name = 'sdtoggle')
    @app_commands.describe(duration = 'Duration to temporarily disable the drawing cog (in minutes)')
    @commands.is_owner()
    async def _sdtoggle(self, interaction: Interaction, duration: Optional[int] = 0, toggle: Optional[bool] = None):
        """Temporarily disable the drawing cog"""
        if toggle is not None:
            self.isEnabled = toggle
            status = "enabled" if toggle else "disabled"
            await interaction.response.send_message(f"Drawing cog has been {status}.")
            return
        
        if duration <= 0:
            await interaction.response.send_message("Please specify a valid duration in minutes.", ephemeral=True)
            return

        self.isEnabled = False
        # convert to discord relative timestamp <t:1763075460:R>
        self.reenable_timestamp = datetime.now(timezone.utc) + timedelta(minutes=duration)
        timestamp = int(self.reenable_timestamp.timestamp())
        await interaction.response.send_message(f"Drawing cog has been disabled for {duration} minutes. Re-enabling at <t:{timestamp}:R>")

        # Re-enable the cog after the specified duration
        async def reenable():
            await asyncio.sleep(duration * 60)  # Convert minutes to seconds
            self.isEnabled = True
            self.reenable_timestamp = None
            print("Drawing cog has been re-enabled.")

        # Start the re-enabling task
        self.bot.loop.create_task(reenable())

async def setup(bot:commands.Bot):
    await bot.add_cog(drawing_sd(bot))

async def teardown(bot:commands.Bot):
    pass