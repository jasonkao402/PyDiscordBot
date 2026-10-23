from datetime import datetime, timedelta, timezone
from discord import Interaction, Message, Webhook, app_commands
from discord.abc import Messageable
from numpy import argsort, array, dot, ndarray
from numpy.linalg import norm
from typing import List, Optional
from wcwidth import wcswidth
from config_loader import config_toml
from dataclasses import dataclass
import re

TWTZ = timezone(timedelta(hours = 8))

def clamp(n: float, minn: float = 0, maxn: float = 100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def is_admin_check():
    ''' Check if the user is in the admin list from config_toml. Use as a decorator for commands.'''
    def predicate(interaction: Interaction) -> bool:
        return int(interaction.user.id) in config_toml.get('auth', {}).get('admin_list', [])
    return app_commands.check(predicate)

def devChk(id:int) -> bool:
    # admin = 
    return int(id) in config_toml.get('auth', {}).get('admin_list', [])

def sepLines(itr, sep='\n'):
    return sep.join(itr)

def utctimeFormat(t:datetime):
    return t.replace(tzinfo=timezone.utc).astimezone(TWTZ).strftime("%Y-%m-%d %H:%M:%S")

def wcformat(s:str, w=12, strFront=True):
    if strFront:
        return (s + ' '*(w - wcswidth(s)))
    else:
        return (' '*(w - wcswidth(s)) + s)
    
def multiChk(s:str, l:list) -> int:
    for i in l:
        if i in s: return i
    return -1

def cosineSim(a, b) -> float:
    return dot(a, b) / (norm(a) * norm(b))

def simRank(a, b, K=3) -> tuple:
    sim = array([cosineSim(a, vector) for vector in b])
    idx = argsort(sim)[:-K-1:-1]
    return idx, sim[idx]

async def long_message_splitter(_ch: Messageable | Webhook, text: str, title: str = "", chunk_size: int = 1900) -> Message:
    """Split a long message into chunks that fit within Discord's message limits and send them sequentially."""
    
    last_message: Message | None = None

    if len(text) > chunk_size:
        parts = [text[i:i+chunk_size] for i in range(0, len(text), chunk_size)]
        len_parts = len(parts)
        for i, part in enumerate(parts):
            last_message = await _ch.send(f"# {title} part {i+1}/{len_parts}\n{part}")
    else:
        last_message = await _ch.send(f"# {title}\n{text}")
    
    if last_message is None:
        raise RuntimeError("Failed to send message chunk")

    return last_message

@dataclass
class UserDict:
    uid: int
    name: str
    preferred_name: Optional[str] = None
    descr: Optional[str] = None
    
    @property
    def effective_name(self):
        # Priority: preferred_name > display_name > name
        return self.preferred_name or self.name
    
    # discord name regex = ^[a-z0-9._]{2,32}$
    # openai api role name regex = ^[a-zA-Z0-9_-]{1,64}$ 
    @property
    def role_name(self):
        return self.name.replace('.', '_')
        
class embedVector:
    def __init__(self, text:str, vector:ndarray):
        # self.id = id
        self.text = text.replace('\n', ' ')
        self.vector = vector

    @property
    def asdict(self):
        return {'text':self.text, 'vector':self.vector}

class replyDict:
    def __init__(self, role: str = 'assistant', content: str = '', name: str = '', image_url: str = ''):
        self.role = role
        self.name = name
        if len(image_url) > 0:
            self.content = [{'type': 'text', 'text': content}, {'type': 'image_url', 'image_url': {'url': image_url, 'detail': "auto"}}]
        else:
            self.content = content
        # self.image_url = image_url

    def __str__(self):
        return f"{self.role} : {self.content}"
    
    @property
    def asdict(self):
        result = {'role': self.role, 'content': self.content}
        if self.name:
            result['name'] = self.name
        # if self.images:
        #     result['images'] = self.images
        return result

class PlaceholderReplacer:
    def __init__(self, _user_dict: UserDict):
        self.user_dict = _user_dict
        self.converters = {
            "user": lambda: self.user_dict.effective_name,
            "descr": lambda: self.user_dict.descr or "",
            "time": lambda: datetime.now().strftime("%Y/%m/%d %H:%M %a"),
        }

    # 支援 Unicode（包含中文、日文、數字、底線）
    def replace_placeholders(self, text: str) -> str:
        PLACEHOLDER_PATTERN = re.compile(r"\\?\{\{([\w]+)\}\}", re.UNICODE)
        
        def replacer(match: re.Match) -> str:
            full = match.group(0)
            var = match.group(1)
            if full.startswith("\\"):
                return f"{{{{{var}}}}}"   # 輸出 {{var}}
            if var in self.converters:
                return str(self.converters[var]())
            return full   # 未知變數保留原樣

        return PLACEHOLDER_PATTERN.sub(replacer, text)
# testing
if __name__ == "__main__":
    d = {"a": 1, "b": 2, "c": 3}
    print(sepLines([f"{k}: {v}" for k, v in d.items()]))