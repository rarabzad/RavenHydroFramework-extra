"""Figures of :SoilZoneVadose KINEMATIC (manual Section sec:szvadosekw): from the outputs of tests/soilzone/test_vz_kinematic.py
(run it first, or set RAVEN_TEST_WORK to its scratch folder). Usage: python3 make_vz_kinematic_figures.py
  fig_vz_kinematic.png  (a) conductivity curves; (b) K1: bottom flux of a 6 m column against the analytical kinematic
                        wave (front, drainage tail), N = 16 and 128; (c) K2: the storm after 400 days of 2 mm/d"""
import os, sys, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', '..', '..', 'tests'); sys.path.insert(0, T)
import testconfig as tc
W = tc.work('soilzone', 'vz_kinematic')
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'axes.edgecolor': '#52514e',
                     'axes.labelcolor': '#0b0b0b', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']
INK2 = '#52514e'

fig, ax = plt.subplots(1, 3, figsize=(10.0, 3.1))
# (a) conductivity: Campbell (RICHARDS), shifted to vanish at ths - Sy (KINEMATIC), UZF form measured from ths - Sy
ths, Sy, b = 0.30, 0.20, 4.0; e = 2 * b + 3; thr = ths - Sy; x0e = (thr / ths) ** e
th = np.linspace(thr, ths, 300)
ax[0].semilogy(th, (th / ths) ** e, color=C[0], lw=2, label='RICHARDS (Campbell)')
ax[0].semilogy(th, np.maximum(((th / ths) ** e - x0e) / (1 - x0e), 1e-12), color=C[1], lw=2, label='KINEMATIC')
ax[0].semilogy(th, np.maximum(((th - thr) / (ths - thr)) ** e, 1e-12), color=INK2, lw=1.5, ls='--', label='UZF form (not used)')
ax[0].set_ylim(1e-7, 1.5); ax[0].set_xlabel(r'water content $\theta$'); ax[0].set_ylabel(r'$K/K_s$')
ax[0].set_title(r'(a) $\theta_s$ 0.30, $S_y$ 0.20, $b$ 4', fontsize=8, color=INK2); ax[0].legend(fontsize=7)
# (b) analytical kinematic wave (K1)
f = os.path.join(W, 'kw_wave.txt')
if os.path.exists(f):
    s = np.loadtxt(f)
    for N, c in ((16, C[1]), (128, C[2])):
        m = s[:, 0] == N
        ax[1].plot(s[m, 1], s[m, 2] * 1000, color=c, lw=1.5, label='Raven, N = %d' % N)
    m = s[:, 0] == 128
    ax[1].plot(s[m, 1], s[m, 3] * 1000, color=C[0], lw=1, ls='--', label='analytical')
    ax[1].set_xlabel('time [d]'); ax[1].set_ylabel('flux to the water table [mm/d]'); ax[1].legend(fontsize=7)
    ax[1].set_title('(b) 10 mm/d into 6 m, stopped at day 117', fontsize=8, color=INK2)
# (c) storm after a wet spell (K2)
warm = 400
for lab, c, name in (('none', C[0], 'NONE'), ('ric', C[2], 'RICHARDS'), ('kw', C[1], 'KINEMATIC')):
    p = os.path.join(W, 'k2b_' + lab, 'out', 'GWBudget.csv')
    if os.path.exists(p):
        m = pd.read_csv(p)['MF6 recharge [m3/d]'].values[warm - 5:warm + 45] / 80.0
        ax[2].plot(np.arange(-5, 45), m, color=c, lw=2, label=name)
ax[2].axvspan(0, 3, color='#e4e3df', lw=0)
ax[2].set_xlabel('days after the storm began'); ax[2].set_ylabel('recharge reaching MODFLOW [mm/d]'); ax[2].legend(fontsize=7)
ax[2].set_title('(c) 3 days of 40 mm/d, water table 4.4 m deep', fontsize=8, color=INK2)
fig.tight_layout(); fig.savefig(os.path.join(HERE, 'fig_vz_kinematic.png')); plt.close(fig); print('wrote fig_vz_kinematic.png')
