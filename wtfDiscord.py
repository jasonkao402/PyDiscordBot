import openai
import asyncio
import os
from opencc import OpenCC
from aiohttp import ClientSession, TCPConnector
from collections import deque

with open('./acc/aiKey.txt', 'r') as acc_file:
        openai.api_key = acc_file.read().splitlines()[0]
        
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + openai.api_key,
}

url = "https://api.openai.com/v1/chat/completions"

async def aiaiv2(msgs):
    async def Chat_Result(session, msgs, url=url, headers=headers):
        data = {
            "model": "gpt-3.5-turbo",
            "messages": msgs,
            "max_tokens": 256,
            "temperature": 0.7
        }
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()

    async def get_response():
        async with ClientSession(connector=TCPConnector(ssl=False)) as session:
            return await Chat_Result(session, msgs)
    # return await get_response()
    return await get_response()

# def aiai(msg):
#     return openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=msg,
#         temperature=0.6,
#         max_tokens=256,
#         top_p=1,
#         frequency_penalty=0,
#         presence_penalty=0)['choices'][0]['message']

N = 5
mem = deque(maxlen=2*N)
cc = OpenCC('s2twp')
sys = {'role': 'system', 'content': '''你是一位貓娘女僕，你的主人是 jasonZzz, 你的名字是【伊莉亞】, 英文名【illya】'''}

async def main():
    for _ in range(N):
        prompt = input('You: ')
        mem.append({'role':'user', 'content':prompt})
        # print([sys, *mem])
        response = await aiaiv2([sys, *mem])
        response, usage = response['choices'][0]['message'], response['usage']['total_tokens']
        mem.append(response)
        print('AI: ', cc.convert(response['content']))
        print('tok:', usage)

# print(certifi.where())
asyncio.run(main())