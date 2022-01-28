def clamp(n, minn=0, maxn=100):
    '''clamp n in set range'''
    return max(min(maxn, n), minn)
