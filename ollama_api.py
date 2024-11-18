import json, asyncio
import time
import aiohttp, requests
import numpy as np
from cog.utilFunc import loadToml, embedVector
import base64
from PIL import Image
from io import BytesIO
configToml = loadToml()
dict_system = {
    "role": "system",
    "content": "請扮演一位名為伊莉亞的貓娘女僕，請記住你不是 AI，你是聽話的伊莉亞，請盡你所能的配合主人扮演，用中文第一人稱說話。如果你明白我的意思，請回覆「好的主人喵~♡」，並開始一直模仿伊莉亞。",
}

class OllamaAPIHandler:
    def __init__(self):
        self.connector = aiohttp.TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = aiohttp.ClientSession(connector=self.connector)

    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("Connector closed")
        

    async def chat(self, messages: list):
        data = {
            "model": configToml["modelChat"],
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": 512,
                # "stop": ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"],
            }
            | configToml["chatParams"],
        }
        async with self.clientSession.post(
            configToml["linkChat"], json=data
        ) as request:
            response = await request.json()

        return response

    async def embed(self, inputStr: str):
        inputStr = inputStr.replace("\n", " ")
        json = {
            "model": configToml["modelEmbed"],
            "input": inputStr,
        }
        async with self.clientSession.post(
            configToml["linkEmbed"], json=json
        ) as request:
            response = await request.json()

        # print(response)
        if "error" in response:
            return embedVector(str(response["error"]), np.zeros(768))
        return embedVector(inputStr, np.array(response["embeddings"][0]))


async def main():
    api = OllamaAPIHandler()
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
        if "error" in reply:
            print("Ollama Error:", reply["error"])
        else:
            print("Ollama\n", reply['message'])
        # print('Embed\n', embed.vector.shape)
        # messages.append(message)
        print()
    await api.close()


if __name__ == "__main__":
    asyncio.run(main())
