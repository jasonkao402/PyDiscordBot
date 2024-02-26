import matplotlib.pyplot as plt
import numpy as np

SHAPE = (10000)
SCALE = 250


normal = np.random.normal(SCALE, 10, SHAPE)
exponential = np.random.exponential(SCALE, SHAPE)
poisson = np.random.poisson(SCALE, SHAPE)
poisson2 = np.random.exponential(SCALE/2, SHAPE) + SCALE/2
all_arrays = [normal, exponential, poisson, poisson2]

for i, arr in enumerate(all_arrays):
    plt.subplot(2, 2, i+1)
    # arr2 = np.cumsum(arr, axis=0)
    plt.hist(arr, bins=64, color=plt.cm.tab10(i))
    # plt.plot(arr2, color=plt.cm.tab10(i))
plt.show()