from aiohttp import ClientSession, ClientTimeout, TCPConnector
import asyncio
import json
import time

apikey = '59e4ffbf05284f7db9ad507dda90e436'
async def newsAPI_v1(keyword:str=None):
    url = "https://newsapi.org/v2/top-headlines"
    # inputStr = inputStr.replace("\n", " ")
    async def news_Result(session:ClientSession):
        params = {
            "country": "tw",
            "apiKey": apikey
        }
        if keyword:
            params["q"] = keyword
        async with session.get(url, params=params) as result:
            if result.status == 200:
                return await result.json()
            else:
                print(f"newsAPI_v1 error {result.status}")
                return None
    to, co = ClientTimeout(total=60), TCPConnector(ssl=False)
    async with ClientSession(connector=co, timeout=to) as session:
        return await news_Result(session)
    # return await get_response()
    
async def main():
    data = await newsAPI_v1()
    if data:
        # print(json.dumps(data, indent=4, sort_keys=True))
        # to file
        ddd = time.strftime("%Y%m%d_%H%M", time.localtime())
        with open(f"news_{ddd}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, sort_keys=True, ensure_ascii=False)

# 運行主程序
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())