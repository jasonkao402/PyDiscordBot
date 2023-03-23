import openai
from collections import deque

with open('./acc/aiKey.txt', 'r') as acc_file:
       openai.api_key = acc_file.read().splitlines()[0]
       
def aiai(msg):
    return openai.ChatCompletion.create(
       model="gpt-3.5-turbo",
       messages=msg,
       temperature=0.6,
       max_tokens=256,
       top_p=1,
       frequency_penalty=0,
       presence_penalty=0)['choices'][0]['message']

mem = deque(maxlen=6)
sys = {'role': 'system', 'content': '主人您好，很榮幸能為您服務 <(✿◡‿◡)>\n我是 LoliSagiri 所開發的互動式機器人'}
            
while 1:
       prompt = input('You: ')
       mem.append({'role':'user', 'content':prompt})
       print([sys, *mem])
       reply = aiai([*mem])
       mem.append(reply)
       print('AI: ', reply["content"])