from collections import deque
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import pyautogui as pag
import keyboard

RATE = 0.333
LIMIT = 25
P, I, D = 0.1, 0.5, 0.1
x = 0
y = 0
k = 0
v = 0
i = 0

def setLimit():
    # return np.random.normal(LIMIT, SCALE)
    return np.random.normal()*LIMIT

def mouse_move(event):
    x, y = event.xdata, event.ydata
    global limit
    if y is not None:
        limit = y
    # print(x, y)

def boost():
    global limit
    limit += LIMIT
      
def rolling(z):
    global x, y, k, v, i, limit
    x += 1
    
    e = limit - y
    i += e
    d = e - v
    y += P*e
    v = e
    # y += RATE
    data.append((x, y))
    # if abs(e) < 0.05:
    #     limit = setLimit()
    #     k = x
    limit += P*(LIMIT - limit)
    
    ax.relim()
    ax.autoscale_view()
    line.set_data(*zip(*data))
    ref.set_ydata([limit])

fig, ax = plt.subplots()

limit = setLimit()
data = deque([(x, y)], maxlen=128)
line, = plt.plot(*zip(*data), c='black')
ref = plt.axhline(y=limit, color='r', linestyle='--')

keyboard.add_hotkey('z', boost)
# while True:
#     rolling(0)
# plt.connect('motion_notify_event', mouse_move)
ani = animation.FuncAnimation(fig, rolling, interval=40, frames=1000)
plt.show()