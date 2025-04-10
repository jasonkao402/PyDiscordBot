import pandas as pd
from collections import defaultdict
with open('./acc/emojiArr.csv', 'r') as f:
    df = pd.read_csv(f)
print(df)
# group by uid as HEX
df['hexuid'] = df['uid'].astype('uint64').apply(lambda x: f'{x:08x}'[-8:])
# print(df)

convertDict = defaultdict(list)
for index, row in df.iterrows():
    # print(row[['hexuid', 'uid']])
    convertDict[row['hexuid']].append(row['uid'])

for key, value in convertDict.items():
    print(f'{key}: {value}')

df = df.drop(columns = ['uid'])
print(df.groupby('hexuid').sum())