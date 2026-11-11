from helper_func.utilFunc import _chunks

test_str = """Synced 22 commands: ['reload', 'sync', 'toml', 'hello', 'clear', 'latex', 'clearcache', 'debugmode', 'refreshmodels', 'chathistory', 'selectmodel', 'testmodal', 'bonk', 'goback', 'currentpersona', 'memo', 'selectpersona', 'listpersonas', 'scoreboard', 'createpersona', 'editpersona', 'setname']
INFO:discord.gateway:Shard ID None has connected to Gateway (Session ID: 0cbf569145b103d9f7f233aadde6bcfb).
Connected! Latency: 197 ms
Bot is online as hachiya_chan#1261
INFO:httpx:HTTP Request: GET https://odyfree.spinsnow.fun/v1/models "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: GET https://odyfree.spinsnow.fun/v1/models "HTTP/1.1 200 OK"
load persona 21 from db
from db loaded user 225833749156331520
INFO:httpx2:HTTP Request: POST http://localhost:8017/v1/systemone "HTTP/1.1 200 OK"
INFO:typesafe_sdk:POST http://localhost:8017/v1/systemone <- 200 in 390ms (request -)
jasonzzz    @哈基亞（通用）: 現在幾點? 內褲顏色? 等等吃什麼?

INFO:httpx:HTTP Request: POST https://odyfree.spinsnow.fun/v1/chat/completions "HTTP/1.1 200 OK"""

title = "Test Message"
parts = _chunks(test_str, 400)
total = len(parts)

for i, part in enumerate(parts, start=1):
    header = f"# {title} part {i}/{total}\n" if total > 1 else f"# {title}\n"
    print(header + part)