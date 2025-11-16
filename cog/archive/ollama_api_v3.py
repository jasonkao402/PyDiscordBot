from aiohttp import ClientSession, ClientTimeout, TCPConnector
from config_loader import configToml
from cog.utilFunc import replyDict

modelConfig = configToml.get("llmChat", {})
class Ollama_APIHandler():
    def __init__(self):
        self.connector = TCPConnector(ttl_dns_cache=600, keepalive_timeout=600)
        self.clientSession = ClientSession(connector=self.connector)
        self.completion_tokens = 0
        
    async def close(self):
        if not self.clientSession.closed:
            await self.clientSession.close()
            print("Ollama Client session closed")
            
        if not self.connector.closed:
            await self.connector.close()
            print("Ollama Connector closed")

    async def chat(self, messages:list) -> replyDict:
        json = {
            "model": modelConfig["modelChat"],
            "messages": messages,
            "stream": False,
            "options": {
                # "num_predict": 640,
            }
            | configToml["chatParams"],
        }
        # print(messages[-1])

        async with self.clientSession.post(modelConfig['linkChat'], json=json) as request:
            # request.raise_for_status()
            response = await request.json()

        if 'error' in response:
            return replyDict(role = 'error', content = response['error'])

        self.completion_tokens += response['eval_count']
        rd = replyDict(response['message']['role'], response['message']['content'])
        if 'thinking' in response['message']:
            rd.content = f"<think>{response['message']['thinking']}</think>\n{response['message']['content']}"
        return rd

    async def ps(self):
        async with self.clientSession.get(modelConfig['linkStatus']) as request:
            request.raise_for_status()
            response = await request.json()
        return response