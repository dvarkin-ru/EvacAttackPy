import numpy as np
from scipy import optimize
import matplotlib.pyplot as plt 

def approximation(X, k1, k2, k3, k4):
    d, v, omega = X
    return k1*d + k2*v + k3*omega + k4

y = [43.68323663473972,89.5856871808333,454.15493954890496,
165.92440735774144,350.76086829188637,862.7870487462368,
349.390187418946,724.1124568320254,1018.7269336990648,
338.9471371038573,724.3101260669627,1033.6501029518786,
405.38437751945827,723.0440434045217,1211.6301820630094,
342.97516416952465,751.586374604954,1216.031222839804,
343.3453547361189,752.4870003387236,1206.6059432994005,
13.442745574176454,72.11341218839814,119.18901373446865,
108.0468405870175,306.5170874333156,510.5298280105897,
144.00831063720543,458.16641918855856,779.4341443333017,
139.88769215298703,455.8354750956801,780.9264623963097,
191.07622344835846,455.7132304833196,781.4137746314614,
194.51362348105675,455.4235353539525,780.6865755135036,
196.26674404164356,455.7132304833196,781.4137746314614,
7.458896111968635,48.477341364747204,227.40409707814513,
105.82830318303594,242.96072875107006,374.5559245419268,
120.8940970288714,252.4857930046958,358.1758510439697,
112.90490028324945,232.94065630740286,381.05595693320134,
112.84436490089831,245.8660580320276,389.2499712772533,
113.66425669063763,258.1188556634625,368.26551746356233,
123.8406306484752,234.3242551966885,396.4808609850014]

denss = (1/3, 2/3, 1.0)
speeds = (2/8, 3/8, 4/8, 5/8, 6/8, 7/8, 1)
omegas = (1.36, 0.84, 0.32)
m, n, p = len(denss), len(speeds), len(omegas)

# создание массивов значений независимых переменных, потом переделаю
x_d = [d for _ in range(n) for d in denss]*p
x_s  = [s for s in speeds for _ in range(m)]*p
x_omega = [omega for omega in omegas for _ in range(n*m)]
x = (x_d, x_s, x_omega)

k, _ = optimize.curve_fit(approximation, x, y)

print("K", k)
print(np.sqrt(np.diag(_)))
err = []
for i in range(len(y)):
    e = approximation((x_d[i], x_s[i], x_omega[i]), *k)
    err.append(e/y[i] if e > 0 else 0)
print(sum(err)/len(y))

fig = plt.figure()
ax = fig.add_subplot(projection='3d')
ax.scatter(x_d[:n*m], x_s[:n*m], y[0:n*m], marker="o", color="red")
ax.scatter(x_d[:n*m], x_s[:n*m], y[n*m:n*m*2], marker="v", color="green")
ax.scatter(x_d[:n*m], x_s[:n*m], y[n*m*2:n*m*3], marker="^", color="blue")
ax.plot_trisurf(x_d[:n*m], x_s[:n*m], np.array([approximation((x_d[i], x_s[i], 1.36), *k) for i in range(n*m)]), color="red")
ax.plot_trisurf(x_d[:n*m], x_s[:n*m], np.array([approximation((x_d[i], x_s[i], 0.84), *k) for i in range(n*m)]), color="green")
ax.plot_trisurf(x_d[:n*m], x_s[:n*m], np.array([approximation((x_d[i], x_s[i], 0.32), *k) for i in range(n*m)]), color="blue")
ax.set(xlabel="d", ylabel="v", zlabel="U")
plt.show()
