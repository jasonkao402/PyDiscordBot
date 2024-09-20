import pandas as pd
with open('./acc/scoreArr.csv', 'r') as f:
    df = pd.read_csv(f)
    print(df)
    # group by uid as HEX
    df['hexuid'] = df['uid'].astype('uint64').apply(lambda x: f'{x:08x}'[-8:])
    df['sum'] = df.drop(columns = ['uid']).sum(axis=1)
    print(df.groupby('hexuid').sum())