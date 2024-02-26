import openai
import asyncio
import os
import pandas as pd
import numpy as np
from opencc import OpenCC
from aiohttp import ClientSession, TCPConnector, ClientTimeout
from collections import deque
from cog.askAI import localRead
from cog.utilFunc import embedVector, replyDict
from sklearn.metrics.pairwise import cosine_similarity
from time import strftime

with open('./acc/aiKey.txt', 'r') as acc_file:
    k, o = acc_file.read().splitlines()[:2]
    openai.api_key = k
    openai.organization = o
    
with open('./acc/aiSet_extra.txt', 'r', encoding='utf-8') as set1_file:
    setsys_tmp = set1_file.readlines()
    setsys_extra = []
    for i in range(len(setsys_tmp)//2):
        setsys_extra.append(setsys_tmp[2*i+1])
        
def reactString(extra, context):
    reactBase = f"""{extra}，現在時間：{strftime("%Y-%m-%d %H:%M")}，反饋的上下文摘要：{context}
你會給自己安排適合的計畫去執行，在面對問題時需分析問題，拆成多個步驟並確保答案的正確性，可以利用 Operations 來輔助你實行想法，並等待反饋。
Operations: 
- talk: talk with people
- interaction: make specific interaction with objects
- wait: wait for more information
- search: search from local memory system
- plan: make a plan to solve the problem
Output formats:
- talk: <text>
- interaction: <object>
- wait: None
- search: [<text1>, <text2>,...]
- plan: [<step1>, <step2>,...]

Example 1:
是的主人♡，我會去閱讀那本書了解更多資訊，並且拿起書本，閱讀內容。
{{
    "intention": "gain knowledge and information",
    "operations": "interaction",
    "output": ["book"]
}}
Example 2:
是的主人♡，我將回憶主人喜歡的食物，並且去廚房拿取食材，開始烹飪。
{{
    "intention": "make a meal which master likes",
    "operations": "plan",
    "output": ["recall", "kitchen", "cook"]
}}
"""
    return reactBase

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {openai.api_key}",
    "OpenAI-Organization": openai.organization,
}

chatTok = 0
N = 4
chatMem = deque(maxlen=2*N)
cc = OpenCC('s2twp')
vectorDB = pd.DataFrame(columns=['text', 'vector'])

async def embedding_v1(inputStr:str):
    url = "https://api.openai.com/v1/embeddings"
    inputStr = inputStr.replace("\n", " ")
    async def Embed_Result(session:ClientSession, inputStr, headers=headers):
        data = {
            "model": "text-embedding-ada-002",
            "input": inputStr,
        }
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()
    async def get_response():
        to, co = ClientTimeout(total=60), TCPConnector(ssl=False)
        async with ClientSession(connector=co, timeout=to) as session:
            return await Embed_Result(session, inputStr)
    response = await get_response()
    if 'error' in response:
        # print(response)
        return embedVector(str(response['error']), np.zeros(1536))
    return embedVector(inputStr, np.array(response['data'][0]['embedding']))

async def aiaiv2(msgs, tokens=256):
    url = "https://api.openai.com/v1/chat/completions"
    async def Chat_Result(session, msgs, headers=headers):
        data = {
            "model": "gpt-3.5-turbo-0301",
            "messages": msgs,
            "max_tokens": min(tokens, 4096-chatTok),
            "temperature": 0.8,
            "frequency_penalty": 0.6,
            "presence_penalty": 0.6
        }
        # print(data)
        async with session.post(url, headers=headers, json=data) as result:
            return await result.json()

    async def get_response():
        to, co = ClientTimeout(total=60), TCPConnector(ssl=False)
        async with ClientSession(connector=co, timeout=to) as session:
            return await Chat_Result(session, msgs)
    
    response = await get_response()
    if 'error' in response:
        # print(response)
        return replyDict(rol='error', msg=response['error'])
    return replyDict(msg = response['choices'][0]['message']['content'])

async def main():
    for _ in range(N+1):
        prompt = input('You: ')
        try:
            prompt = replyDict('user'  , f'jasonZzz said {prompt}', 'jasonZzz')
            # embed  = await embedding_v1(prompt['content'])
            embed  = embedVector(prompt.content, np.random.uniform(0, 1, 1536))
            assert embed.vector[0] != 0
            
            sys_context = '\n'.join((f'{cc.convert(i["content"])}' for i in [*chatMem, prompt.asdict]))
            setsys = replyDict('system', reactString(setsys_extra[6], sys_context))
            # print(setsys.content)
            
            # reply = replyDict(msg = '優咪 debug')
            reply  = await aiaiv2([setsys.asdict, *chatMem, prompt.asdict])
            assert reply.role != 'error'
            
            reply2 = reply.content
            print(f'{cc.convert(reply2)}') 
        except TimeoutError:
            print('timeout')
        except AssertionError:
            if embed.vector[0] == 0:
                print(f'Embed error:\n{embed.text}')
            if reply.role == 'error':
                reply2 = '\n'.join((f'{k}: {v}' for k, v in reply.content.items()))
                print(f'Reply error:\n{reply2}')
        else:
            chatMem.append(prompt.asdict)
            chatMem.append(reply.asdict)

asyncio.run(main())