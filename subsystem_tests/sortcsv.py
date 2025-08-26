import os
import pandas as pd
from collections import defaultdict

convertDict = defaultdict(list)
backDict = {}
nameDict = {}

with open('./acc/emojiArr_backup.csv', 'r') as f:
    df = pd.read_csv(f)
# print(df)
for memberList in os.listdir('./acc/'):
    if memberList.startswith('members_'):
        with open(f'./acc/{memberList}', 'r', encoding='utf8') as f:
            lines = f.readlines()
            for line in lines:
                uid, hexuid, username = line.split(',')
                uid = int(uid.strip())
                hexuid = hexuid.strip()
                backDict[hexuid] = uid
                nameDict[uid] = username.strip()
                
# group by uid as HEX
df['hexuid'] = df['uid'].astype('uint64').apply(lambda x: f'{x:08x}'[-8:])
# print(df)

for index, row in df.iterrows():
    # print(row[['hexuid', 'uid']])
    convertDict[row['hexuid']].append(row['uid'])

for key, value in convertDict.items():
    print(f'{key}: {max(value)}')
    convertDict[key] = max(value)
    # backDict[max(value)] = key

df = df.drop(columns = ['uid'])
df['hexuid'] = df['hexuid'].apply(lambda x: backDict[x])
df_g = df.groupby('hexuid').sum()
# df_g['username'] = df_g.index.map(lambda x: nameDict[x])
# new_order = ['username'] + [col for col in df_g.columns if col != 'username']
# df_g = df_g[new_order]
df_g.to_csv('./acc/emojiArr2.csv')
print(df_g)