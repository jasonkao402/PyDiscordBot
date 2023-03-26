def clamp(n, minn=0, maxn=100) -> float:
    '''clamp n in set range'''
    return max(min(maxn, n), minn)

def devChk(id) -> bool:
    return int(id) == 225833749156331520

def nameChk(s) -> bool:
    illya = ('伊莉亞', '伊利亞', 'illya')
    return any(i in s for i in illya)