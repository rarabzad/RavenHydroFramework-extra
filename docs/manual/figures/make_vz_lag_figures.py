"""Figure of :SoilZoneVadose LAG (manual Section sec:szvadoselag, fig:vzlagcascade).
Left: response of a column of one material to an impulse at its top, for 3 to 50 nodes on the column grid (thin nodes at
both ends growing by 1.3 towards the middle, capped at 1.3^8; exact cascade, matrix exponential), time in units of the
mean travel time t_m L. Right: the storm of test L1 (tests/soilzone/test_vz_lag.py; run it first, or set
RAVEN_TEST_WORK to its scratch folder). Usage: python3 make_vz_lag_figures.py"""
import os, sys, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.linalg import expm
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', '..', '..', 'tests'); sys.path.insert(0, T)
import testconfig as tc
W = tc.work('soilzone', 'vz_lag')
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'axes.edgecolor': '#52514e',
                     'axes.labelcolor': '#0b0b0b', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']
INK2 = '#52514e'


def grid(N):
    """relative node thicknesses of the column grid (GWVadose.cpp MakeGrid with the 1.3^8 cap)"""
    w = np.array([1.3 ** min(min(k, N - 1 - k), 8) for k in range(N)]); return w / w.sum()


fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 3.0))
t = np.linspace(0, 3, 601)
for j, N in enumerate((3, 6, 16, 50)):
    k = grid(N)                                       # residence times in units of t_m L
    A = np.diag(-1.0 / k) + np.diag(1.0 / k[:-1], -1)
    out = [k[-1] ** -1 * (expm(A * x)[-1, 0]) for x in t]   # rate out of the last node per unit impulse
    a1.plot(t, out, color=C[j], lw=1.8, label='N = %d (N$_{eff}$ %.1f)' % (N, k.sum() ** 2 / (k ** 2).sum()))
a1.set_xlabel('time / mean travel time $t_m L$'); a1.set_ylabel('response [1 / ($t_m L$)]'); a1.set_xlim(0, 3); a1.legend(fontsize=8)
runs = [('l1_none', 'no column', C[0]), ('l1_ric', 'RICHARDS', C[1]), ('l1_lag2', 'LAG 2', C[2]), ('l1_lag4', 'LAG 4', C[3]),
        ('l1_lag0', 'LAG (derived $t_m$)', C[4])]
for d, lab, col in runs:
    p = os.path.join(W, d, 'out', 'GWBudget.csv')
    if os.path.exists(p):
        b = pd.read_csv(p); a2.plot(np.arange(1, len(b) + 1), b['MF6 recharge [m3/d]'] / 40.0, color=col, lw=1.8, label=lab)
a2.axvspan(10, 13, color='#e4e3df', lw=0)
a2.set_xlim(0, 90); a2.set_xlabel('day'); a2.set_ylabel('recharge reaching MODFLOW [mm/d]'); a2.legend(fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig_vz_lag_cascade.png')); plt.close(fig); print('wrote fig_vz_lag_cascade.png')
