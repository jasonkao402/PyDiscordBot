import asyncio
import random
import keyboard
import matplotlib.pyplot as plt
import numpy as np

v = 0
N = 100
SCALE = 10
vl = [0]

def plot_update(x:np.array):
    plt.clf()  # Clear the previous plot
    plt.plot(x, color='blue')
    plt.draw()
    plt.pause(0.1)  # Pause to update the plot

async def update_variable():
    global v, vl
    
    tot = 0
    rnd = np.random.poisson(SCALE, N)
    limit = np.random.triangular(100, 200, 200)
    while len(vl) < 1000:
        v += rnd[tot]
        if v > limit:
            resetting()
            limit = np.random.normal(200, 50)
        tot += 1
        if tot == N:
            rnd = np.random.poisson(SCALE, N)
            tot = 0
            print('reset')
        vl.append(v)

async def refresh_plot():
    global vl
    while True:
        plot_update(vl)
        await asyncio.sleep(0.08)
        
def resetting():
    global v
    x = np.random.poisson(5*SCALE)
    print(np.round(-x, 3))
    v -= x

# Run both tasks concurrently
async def main():
    task1 = asyncio.create_task(update_variable())
    task2 = asyncio.create_task(refresh_plot())
    await asyncio.gather(task1, task2)

# Run the main function
keyboard.add_hotkey('q', resetting)
asyncio.run(main())
