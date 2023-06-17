from wcwidth import wcswidth

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