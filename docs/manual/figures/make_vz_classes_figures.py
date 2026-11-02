"""Figure of the depth classes of the unsaturated columns (manual Section sec:vzclasses): (a) least-spread grouping of the 25
DEM samples of a hummocky cell (the relief of test C2) into 3 and 5 classes; (b) test C2: water entering and leaving the
class columns (cumulative) with K = 1, 3, 5, from the outputs of tests/soilzone/test_vz_classes.py (run it first, or set
RAVEN_TEST_WORK to its scratch folder). Usage: python3 make_vz_classes_figures.py"""
import os, sys, math, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', '..', '..', 'tests'); sys.path.insert(0, T); sys.path.insert(0, os.path.join(T, 'soilzone'))
import testconfig as tc
W = tc.work('soilzone', 'vz_classes')
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'axes.edgecolor': '#52514e',
                     'axes.labelcolor': '#0b0b0b', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']
INK2 = '#52514e'

def groups(z, K):
    """least-spread grouping of sorted z into at most K classes (as VZGroups in GWVadoseModel.cpp): boundaries"""
    z = np.sort(np.asarray(z)); N = len(z)
    cut = [j for j in range(1, N) if z[j] - z[j - 1] > 1e-9]; nd = len(cut) + 1; K = max(1, min(K, nd))
    ok = set([0, N] + cut)
    s1 = np.concatenate([[0], np.cumsum(z - z[0])]); s2 = np.concatenate([[0], np.cumsum((z - z[0]) ** 2)])
    sse = lambda a, b: max(s2[b] - s2[a] - (s1[b] - s1[a]) ** 2 / (b - a), 0.0)
    D = np.full((K + 1, N + 1), np.inf); B = np.full((K + 1, N + 1), -1, int); D[0, 0] = 0
    for k in range(1, K + 1):
        for j in range(1, N + 1):
            if j not in ok: continue
            for i in range(k - 1, j):
                if i not in ok or not np.isfinite(D[k - 1, i]): continue
                v = D[k - 1, i] + sse(i, j)
                if v < D[k, j]: D[k, j] = v; B[k, j] = i
    b = [N]
    for k in range(K, 0, -1): b.insert(0, B[k, b[0]])
    return z, b

# relief of C2: hummocks of 2.5 m in a 100 m cell, 5 x 5 samples at the sub-square centres; soil zone 1 m
amp, lam = 2.5, 100.0
pts = [(-50 + 10 + 20 * i, -50 + 10 + 20 * j) for i in range(5) for j in range(5)]
zb = [amp * math.sin(2 * math.pi * (x + 25) / lam) * math.sin(2 * math.pi * (y + 25) / lam) - 1.0 for x, y in pts]
fig, axs = plt.subplots(1, 2, figsize=(6.6, 2.9))
ax = axs[0]
z3, b3 = groups(zb, 3)
for c in range(len(b3) - 1):                                      # samples coloured by their K = 3 class, its mean (solid)
    seg = z3[b3[c]:b3[c + 1]]
    ax.plot(np.arange(b3[c], b3[c + 1]), seg, 'o', ms=3.5, color=C[c])
    ax.hlines(seg.mean(), b3[c] - 0.4, b3[c + 1] - 0.6, color=C[c], lw=1.6)
z5, b5 = groups(zb, 5)
for c in range(len(b5) - 1):                                      # K = 5 class means (dashed, grey), bounds as ticks
    seg = z5[b5[c]:b5[c + 1]]
    ax.hlines(seg.mean() + 0.12, b5[c] - 0.4, b5[c + 1] - 0.6, color=INK2, lw=1.0, linestyles='--')
ax.axhline(-1.03, color=INK2, lw=0.8, ls=':'); ax.text(0.3, -0.95, 'water table', color=INK2, fontsize=7)
ax.set_xlabel('DEM sample (sorted by base)'); ax.set_ylabel('soil-zone base [m] (mean land 0)')
ax.set_title('(a) K = 3 (colours, means solid); K = 5 means (dashed)', fontsize=8, loc='left')
ax = axs[1]
have = False
for i, K in enumerate((1, 3, 5)):
    f = os.path.join(W, 'c2_k%d' % K, 'out', 'GWBudget.csv')
    if not os.path.exists(f): continue
    b = pd.read_csv(f); t = np.arange(1, len(b) + 1); have = True
    ax.plot(t, b['unsaturated zone inflow [m3]'].cumsum(), color=C[i], lw=1.6, label='K = %d in' % K)
    ax.plot(t, b['unsaturated zone to aquifer [m3]'].cumsum(), color=C[i], lw=1.0, ls='--', label='K = %d out' % K)
ax.set_xlabel('time [d]'); ax.set_ylabel('through the class columns [m$^3$]')
ax.set_title('(b) test C2 (cumulative)', fontsize=8, loc='left')
if have: ax.legend(fontsize=7, ncol=1)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig_vz_classes.png')); plt.close(fig); print('wrote fig_vz_classes.png')
