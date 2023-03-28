def clamp(n, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id) -> bool:
    admin = [225833749156331520, 316141566173642752, 304589833484107786, 619168250487504916]
    return int(id) in admin
