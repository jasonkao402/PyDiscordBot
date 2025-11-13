from discord import Client as DC_Client
from discord import Interaction, app_commands, File
from discord.ext import commands
from aiohttp import ClientSession, TCPConnector
from time import strftime
from config_loader import configToml
from typing import Optional
import base64

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
        print(f"SD Image Gen Payload:\n\t{payload['prompt']}\n\t{payload['negative_prompt']}\n\t{payload['width']}x{payload['height']}")
        async with self.clientSession.post(configToml['llmChat']['linkSDImg'], json=payload) as request:
            response = await request.json()
        return response
    
class drawing_sd(commands.Cog):
    __slots__ = ('bot')
    
    def __init__(self, bot: DC_Client):
        self.bot = bot
        self.sdimageAPI = SDImage_APIHandler()
        
    # TODO: Refactor to other dedicated cog
    @app_commands.command(name = 'sd2')
    @app_commands.describe(prompt = 'Prompt for the image', width = 'Width of the image', height = 'Height of the image')
    async def _sd2(self, interaction: Interaction, prompt:str, width: Optional[int] = 640, height: Optional[int] = 640):
        # clip w and h to 512 - 1024, in step of 16
        width = max(512, min(1024, (width + 8) // 16 * 16))
        height = max(512, min(1024, (height + 8) // 16 * 16))

        await interaction.response.defer()
        response = await self.sdimageAPI.imageGen(prompt, width, height)
        for image in response['images']:
            dest = f'acc/imgLog/{strftime("%Y_%m%d_%H%M")}.png'
            with open(dest, 'wb') as f:
                f.write(base64.b64decode(image))
        await interaction.followup.send(prompt, file=File(dest))

async def setup(bot:commands.Bot):
    await bot.add_cog(drawing_sd(bot))

async def teardown(bot:commands.Bot):
    pass