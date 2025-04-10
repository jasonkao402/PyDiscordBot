from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

RATE = 0.333
LIMIT = 15

def setLimit():
    # return np.random.normal(LIMIT, SCALE)
    return np.random.exponential()*LIMIT
    
def rolling(i):
    global x, y, k, v, limit
    x += 1
    y += np.random.poisson(RATE)
    # y += RATE
    # data.append((x, y))
    if y > limit:
        v += 1
        mrate.append((x-k)/RATE)
        
        print(f'{v:8d} reached {limit:6.2f} in {(x-k)/RATE:8.2f} sec ({np.std(mrate):8.6f}) ({v/x/RATE:8.6f} per sec)', end='\r')
        
        
        y = 0
        limit = setLimit()
        k = x
    # ax.relim()
    # ax.autoscale_view()
    # line.set_data(*zip(*data))

fig, ax = plt.subplots()
x = 0
y = 0
k = 0
v = 0
limit = setLimit()
data = deque([(x, y)], maxlen=80)
mrate = deque(maxlen=8192)
line, = plt.plot(*zip(*data), c='black')

while True:
    rolling(0)
# ani = animation.FuncAnimation(fig, rolling, interval=25, frames=1000)
# plt.show()