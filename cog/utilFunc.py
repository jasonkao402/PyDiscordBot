import os
from datetime import datetime, timedelta, timezone
from numpy import argsort, array, dot, ndarray
from numpy.linalg import norm
import toml
from typing import List
from wcwidth import wcswidth

TWTZ = timezone(timedelta(hours = 8))

def loadToml():
    if not os.path.exists('./acc/config.toml'):
        print('config.toml not found, please check the file')
        return {}
    with open('./acc/config.toml', 'r+') as tomlFile:
        print('config.toml loaded')
        configToml = toml.load(tomlFile)
        return configToml
    
def clamp(n:int, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id:int) -> bool:
    admin = [225833749156331520, 316141566173642752, 304589833484107786, 619168250487504916, 868448833556840478, 662585167432646668, 336527947299028992]
    return int(id) in admin

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

class embedVector:
    def __init__(self, text:str, vector:ndarray):
        # self.id = id
        self.text = text.replace('\n', ' ')
        self.vector = vector

    @property
    def asdict(self):
        return {'text':self.text, 'vector':self.vector}

class replyDict:
    def __init__(self, role: str ='assistant', content: List[str]=[], name: str=''):
        self.role = role
        self.content = content
        self.name = name
    def __str__(self):
        return f'{self.role} : {self.content}'
    @property
    def asdict(self):
        if self.name != '':
            return {'role': self.role, 'content': self.content, 'name': self.name}
        else:
            return {'role': self.role, 'content': self.content}