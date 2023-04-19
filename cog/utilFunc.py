from wcwidth import wcswidth

def clamp(n:int, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id:int) -> bool:
    admin = [225833749156331520, 316141566173642752, 304589833484107786, 619168250487504916]
    return int(id) in admin

def iterLines(itr):
    return '\n'.join(itr)

def wcformat(s:str, w=12, strFront=True):
    if strFront:
        return (s + ' '*(w - wcswidth(s)))
    else:
        return (' '*(w - wcswidth(s)) + s)