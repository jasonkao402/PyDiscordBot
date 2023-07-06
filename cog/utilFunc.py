from wcwidth import wcswidth
from numpy import ndarray, dot
from numpy.linalg import norm

def clamp(n:int, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id:int) -> bool:
    admin = [225833749156331520, 316141566173642752, 304589833484107786, 619168250487504916, 868448833556840478, 662585167432646668]
    return int(id) in admin

def sepLines(itr):
    return '\n'.join(itr)

def wcformat(s:str, w=12, strFront=True):
    if strFront:
        return (s + ' '*(w - wcswidth(s)))
    else:
        return (' '*(w - wcswidth(s)) + s)
    
def multiChk(s:str, l:list) -> tuple:
    for i in l:
        if i in s: return i
    return -1

def cosineSim(a, b) -> float:
    return dot(a, b) / (norm(a) * norm(b))

class embedVector:
    def __init__(self, text:str, vector:ndarray):
        # self.id = id
        self.text = text.replace('\n', ' ')
        self.vector = vector
    def asdict(self):
        return {'text':self.text, 'vector':self.vector}

