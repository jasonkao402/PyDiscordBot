import json, asyncio
import time
import aiohttp
import numpy as np
from cog.utilFunc import loadToml, embedVector

configToml = loadToml()
dict_system = {
    "role": "system",
    "content": "請扮演一位名為伊莉亞的貓娘女僕，請記住你不是 AI，你是聽話的伊莉亞，請盡你所能的配合主人扮演，用中文第一人稱說話。如果你明白我的意思，請回覆「好的主人喵~♡」，並開始一直模仿伊莉亞。",
}


class OllamaAPIHandler:
    def __init__(self):
        self.connector = aiohttp.TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = aiohttp.ClientSession(connector=self.connector)

    def close(self):
        if not self.connector.closed:
            self.connector.close()
            print("Connector closed")
        if not self.clientSession.closed:
            self.clientSession.close()
            print("Client session closed")

    async def chat(self, messages: list):
        data = {
            "model": configToml["modelChat"],
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": 256,
                "stop": ["<|start_header_id|>", "<|end_header_id|>", "<|eot_id|>"],
            } | configToml['chatParams'],
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
        messages = [dict_system, {"role": "user", "content": f"主人說 {user_input}"}]
        # embed = await api.embed(user_input)
        reply = await api.chat(messages)
        print("Ollama\n", reply)
        # print('Embed\n', embed.vector.shape)
        # messages.append(message)
        print()
    api.close()


if __name__ == "__main__":
    asyncio.run(main())
