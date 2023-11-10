from wcwidth import wcswidth
from numpy import array, ndarray, dot, argsort
from numpy.linalg import norm

def clamp(n:int, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id:int) -> bool:
    admin = [225833749156331520, 316141566173642752, 304589833484107786, 619168250487504916, 868448833556840478, 662585167432646668, 336527947299028992]
    return int(id) in admin

def sepLines(itr, sep='\n'):
    return sep.join(itr)

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
    def __init__(self, rol='assistant', msg='', name=''):
        self.role = rol
        self.content = msg
        self.name = name
    @property
    def asdict(self):
        if self.name != '':
            return {'role': self.role, 'content': self.content, 'name': self.name}
        else:
            return {'role': self.role, 'content': self.content}