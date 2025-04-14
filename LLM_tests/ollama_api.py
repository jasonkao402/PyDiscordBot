import asyncio, aiohttp, requests
import numpy as np
import os, toml
import base64
from PIL import Image
from io import BytesIO
from typing import List

if not os.path.exists('./acc/config.toml'):
    print('config.toml not found, please check the file')
    configToml = {}
with open('./acc/config.toml', 'r+') as tomlFile:
    print('config.toml loaded')
    configToml = toml.load(tomlFile)

dict_system = {
    "role": "system",
    "content": "請扮演一位名為伊莉亞的貓娘女僕，請記住你不是 AI，你是聽話的伊莉亞，請盡你所能的配合主人扮演，用中文第一人稱說話。如果你明白我的意思，請回覆「好的主人喵~♡」，並開始一直模仿伊莉亞。",
}

class replyDict:
    def __init__(self, role: str = 'assistant', content: str = '', name: str = '', images: List[str] = [], **kwargs):
        self.role = role
        self.content = content
        self.name = name
        self.images = images

    def __str__(self):
        return f'{self.role} : {self.content}' + (f' ({self.name})' if self.name else '') + (f' [{self.images}]' if self.images else '')
    
    @property
    def asdict(self):
        result = {'role': self.role, 'content': self.content}
        if len(self.images) > 0:
            result['images'] = self.images
        if self.name:
            result['name'] = self.name
        return result

class Ollama_API_Handler:
    def __init__(self):
        self.connector = aiohttp.TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = aiohttp.ClientSession(connector=self.connector)
        self.completion_tokens = 0
        
    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("Ollama Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("Ollama Connector closed")
        

    async def chat(self, messages: list, token_limit: int = 2000):
        # hard_limit
        token_limit = min(token_limit, 2048)
        data = {
            "model": configToml["modelChat"],
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": token_limit,
            }
            | configToml["chatParams"],
        }
        async with self.clientSession.post(
            configToml["linkChat"], json=data
        ) as request:
            response = await request.json()
        if 'error' in response:
            return replyDict(role='error', content=response['error'])
        
        return replyDict(
            role=response["message"]["role"],
            content=response["message"]["content"],
        )

    # async def embed(self, inputStr: str):
    #     inputStr = inputStr.replace("\n", " ")
    #     json = {
    #         "model": configToml["modelEmbed"],
    #         "input": inputStr,
    #     }
    #     async with self.clientSession.post(
    #         configToml["linkEmbed"], json=json
    #     ) as request:
    #         response = await request.json()

    #     # print(response)
    #     if "error" in response:
    #         return embedVector(str(response["error"]), np.zeros(768))
    #     return embedVector(inputStr, np.array(response["embeddings"][0]))


async def main():
    api = Ollama_API_Handler()
    messages = []
    while True:
        user_input = input("Enter a prompt: ")
        if not user_input:
            break
        print()
        # fetch the image from url, encode it to base64
        image = requests.get(user_input)
        # Image.open(BytesIO(image.content)).show()
        image = base64.b64encode(image.content).decode('utf-8')
        # print(image)
        # messages = [dict_system, {"role": "user", "content": f"主人說 {user_input}"}]
        messages = [
            dict_system,
            {
                "role": "user",
                "content": f"Describe the image as if explaining it to someone who cannot see it, using natural and human-like language.",
                "images": [image],
            }
        ]
        # embed = await api.embed(user_input)
        reply = await api.chat(messages)
        if reply.role == 'error':
            print("Error:", reply.content)
        else:
            print("Ollama\n", reply.content)
        # print('Embed\n', embed.vector.shape)
        # messages.append(message)
        print()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
