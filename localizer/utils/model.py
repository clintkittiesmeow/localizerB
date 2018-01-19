from matplotlib import pyplot as plt
from scipy.optimize import curve_fit


def symmetric_sigmoid(x, a, b, c, d):
    return a + (b - a) / (1 + (x / c) ** d)

    #           0                 20
    #          90                  7
    #         180                  5
    #         360                  4

x = [0,90,180,360]
y = [20,7,5,4]

init_vals = [1, 0, 1]     # for [amp, cen, wid]

best_vals, _ = curve_fit(symmetric_sigmoid, x, y)

get_reset_rate = lambda x: symmetric_sigmoid(x, *tuple(best_vals))

RESET_RATE = [get_reset_rate(x) for x in range(1080)]

ax = plt.gca()
ax.plot(range(1080), RESET_RATE)
ax.set_xlim([0,1080])
plt.show()
print(best_vals)
input('')
print(RESET_RATE[720])
print(RESET_RATE[1079])