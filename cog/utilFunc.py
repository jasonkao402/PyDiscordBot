from datetime import datetime, timedelta, timezone
from numpy import argsort, array, dot, ndarray
from numpy.linalg import norm
from typing import List, Optional
from wcwidth import wcswidth
from config_loader import configToml
from dataclasses import dataclass

TWTZ = timezone(timedelta(hours = 8))

def clamp(n: float, minn: float = 0, maxn: float = 100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id:int) -> bool:
    # admin = 
    return int(id) in configToml.get('auth', {}).get('adminList', [])

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

@dataclass
class UserDict:
    uid: int
    name: str
    preferred_name: Optional[str] = None
    
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

# testing
if __name__ == "__main__":
    d = {"a": 1, "b": 2, "c": 3}
    print(sepLines([f"{k}: {v}" for k, v in d.items()]))