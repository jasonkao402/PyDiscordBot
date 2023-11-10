import pandas as pd
import numpy as np
from os.path import isfile
from os import listdir
from cog.utilFunc import wcformat
import numpy as np
import matplotlib.pyplot as plt

ID = 225833749156331520
tmp = pd.DataFrame(columns=['text', 'vector'])
# check if file exists
if isfile(f'./embed/{ID}.csv') and isfile(f'embed/{ID}.npy'):
    tmptext = pd.read_csv(f'./embed/{ID}.csv')
    tmpvect = np.load    (f'./embed/{ID}.npy', allow_pickle=True)
    if len(tmptext) != len(tmpvect):
        print('lengths dont match')
        exit()
else:
    print('file doesnt exist')
    exit()
    
lenText = len(tmptext)
print(f'loaded from file {lenText} entries')
RUNS, LEN = 50, 500
x = np.arange(0, LEN, dtype=int)
memRandom = np.random.normal(0, .2, (RUNS, LEN))
y = np.zeros((RUNS, LEN))
plt.plot(x, 0.98 ** x)

for i in range(RUNS):
    mem_Decay = (0.98 ** x) - memRandom[i, :]
    y[i, :] = mem_Decay
    # plt.plot(x, mem_Decay)
rst = np.mean(y, axis=0)
plt.plot(x, rst)
plt.show()