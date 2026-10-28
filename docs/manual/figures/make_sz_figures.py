"""Figures of the soil zone (manual Sections 4.3.x and 8): from the outputs of tests/soilzone (run the suite first,
or set RAVEN_TEST_WORK to its scratch folder). Usage: python3 make_sz_figures.py"""
import os, sys, numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', '..', '..', 'tests'); sys.path.insert(0, T); sys.path.insert(0, os.path.join(T, 'soilzone'))
import testconfig as tc
W = tc.work('soilzone', 'water_table'); LOGS = os.path.join(tc.WORK, 'run_all_logs')
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'axes.edgecolor': '#52514e',
                     'axes.labelcolor': '#0b0b0b', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']   # categorical slots 1-5 (fixed order)
INK2 = '#52514e'

def save(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(HERE, name)); plt.close(fig); print('wrote', name)

def budget(d):
    return pd.read_csv(os.path.join(W, d, 'out', 'GWBudget.csv'))

# 1. drainage of a wet column: step means against the method-of-lines reference
import vadose_ref
ser = np.loadtxt(os.path.join(LOGS, 'vadose_drain.txt'))
ref, got = vadose_ref.drainage(ser)
fig, ax = plt.subplots(figsize=(6.2, 3.0))
ax.plot(ser[:, 0], ref * 1000, color=C[0], lw=2, label='reference (400 cells, BDF)')
ax.plot(ser[:, 0], got * 1000, color=C[1], lw=0, marker='o', ms=4, label='Raven column (16 nodes, half-day steps)')
ax.set_xlabel('time [d]'); ax.set_ylabel('drainage to the water table [mm/d]'); ax.legend()
save(fig, 'fig_sz_drainage.png')

# 2. delay through a deep unsaturated zone
a, b = budget('a_off'), budget('a_vz'); t = np.arange(1, len(a) + 1)
fig, ax = plt.subplots(figsize=(6.2, 3.0))
ax.plot(t, a['MF6 recharge [m3/d]'] / 40.0, color=C[0], lw=2, label='without the column (recharge leaves the soil)')
ax.plot(t, b['MF6 recharge [m3/d]'] / 40.0, color=C[1], lw=2, label='with the Richards column (water table 6 m deep)')
ax.axvspan(10, 13, color='#e4e3df', lw=0); ax.text(11.5, ax.get_ylim()[1] * 0.92, 'storm', ha='center', color=INK2, fontsize=8)
ax.set_xlim(0, 60); ax.set_xlabel('day'); ax.set_ylabel('recharge reaching MODFLOW [mm/d]'); ax.legend()
save(fig, 'fig_sz_delay.png')

# 3. capillary rise: cumulative evaporation
fig, ax = plt.subplots(figsize=(6.2, 3.0))
for i, z in enumerate((0.7, 1.3, 2.5)):
    w = pd.read_csv(os.path.join(W, 'b_on_%g' % z, 'out', 'WatershedStorage.csv'))
    ax.plot(w['time [d]'], w['Cum. Losses to Atmosphere [mm]'], color=C[i], lw=2, label='with rise, water table %.1f m deep' % z)
w = pd.read_csv(os.path.join(W, 'b_off_0.7', 'out', 'WatershedStorage.csv'))
ax.plot(w['time [d]'], w['Cum. Losses to Atmosphere [mm]'], color=INK2, lw=1.5, ls='--', label='without rise (any depth)')
ax.set_xlabel('day (no rain, PET 4 mm/d)'); ax.set_ylabel('cumulative evaporation [mm]'); ax.legend()
save(fig, 'fig_sz_caprise.png')

# 4. the steady-rise relation: exact against Gardner's limit
from scipy.integrate import quad
from scipy.optimize import brentq
def Qexact(x, s, m):
    if s is not None and s <= x: return 0.0
    def g(lq):
        Q = np.exp(lq); su = 1.0 if s is None else min(s, 1.0)
        I = quad(lambda u: 1 / (1 + Q * u ** m), 1, np.inf if s is None else max(s, 1.0), limit=400)[0]
        return su / (1 + Q) + I - x
    return np.exp(brentq(g, -25, 10))
b5 = 5.0; m = 2 + 3 / b5; xs = np.logspace(np.log10(1.5), np.log10(60), 40)
fig, ax = plt.subplots(figsize=(6.2, 3.2))
ax.loglog(xs, [Qexact(x, None, m) for x in xs], color=C[0], lw=2, label='exact, infinitely dry top')
ax.loglog(xs, [Qexact(x, 3 * x, m) for x in xs], color=C[1], lw=2, label='exact, top suction 3 d')
ax.loglog(xs, [Qexact(x, 1.5 * x, m) for x in xs], color=C[2], lw=2, label='exact, top suction 1.5 d')
ax.loglog(xs, (1 + 1.5 / (m - 1)) * xs ** -m, color=INK2, lw=1.5, ls='--', label="Gardner/Eagleson $q_\\infty$")
ax.set_xlabel('depth of the water table / air-entry suction, $d/\\psi_a$'); ax.set_ylabel('steady rise $q/K_s$')
ax.legend(fontsize=8); ax.set_title('Campbell b = 5', fontsize=8, color=INK2)
save(fig, 'fig_sz_rise.png')

# 5. timing: head difference to the MODFLOW-only reference, AFTER and LAGGED
import flopy
def head_err_series(d, rd):
    R = flopy.utils.HeadFile(os.path.join(rd, 'ref.hds')); tr = np.array(R.get_times())
    H = flopy.utils.HeadFile(os.path.join(d, 'out', 'mf6', 'gwf.hds')); out = []
    for t in H.get_times():
        h = np.array(H.get_data(totim=t)[0], float); h[np.abs(h) > 1e20] = np.nan
        g = R.get_data(totim=tr[int(np.argmin(np.abs(tr - t)))])[1]
        e = np.abs(h - g); out.append((t, np.nanmean(e), np.nanmax(e)))
    return np.array(out)
ea = head_err_series(os.path.join(W, 'e_after'), os.path.join(W, 'e_ref'))
el = head_err_series(os.path.join(W, 'e_lag'), os.path.join(W, 'e_ref'))
fig, ax = plt.subplots(figsize=(6.2, 3.0))
ax.plot(ea[:, 0], ea[:, 2] * 100, color=C[0], lw=2, marker='o', ms=4, label='AFTER (the basic soil zone), largest')
ax.plot(el[:, 0], el[:, 2] * 100, color=C[1], lw=2, marker='o', ms=4, label='LAGGED (default), largest')
ax.plot(ea[:, 0], ea[:, 1] * 100, color=C[0], lw=1.2, ls='--', label='AFTER, mean')
ax.plot(el[:, 0], el[:, 1] * 100, color=C[1], lw=1.2, ls='--', label='LAGGED, mean')
ax.set_xlabel('day (rain 10 mm/d until day 150)'); ax.set_ylabel('head difference to reference [cm]'); ax.legend(fontsize=8, ncol=2)
save(fig, 'fig_sz_timing.png')

# 6. column classes: one HRU over ten cell columns
ks, means, maxs = [], [], []
for k, d in ((1, 'f_1hru_k1'), (5, 'f_1hru_k5'), (10, 'f_1hru_k10')):
    e = head_err_series(os.path.join(W, d), os.path.join(W, 'f_ref')); ks.append(k); means.append(np.mean(e[:, 1]) * 100); maxs.append(np.max(e[:, 2]) * 100)
fig, ax = plt.subplots(figsize=(4.6, 3.0))
ax.plot(ks, maxs, color=C[0], lw=2, marker='o', ms=6, label='largest')
ax.plot(ks, means, color=C[1], lw=2, marker='o', ms=6, label='mean')
for k, v in zip(ks, maxs): ax.annotate('%.1f' % v, (k, v), textcoords='offset points', xytext=(0, 6), ha='center', fontsize=8, color=INK2)
ax.set_xticks(ks); ax.set_xlabel(':SoilZoneClasses K (one HRU, ten cell columns)'); ax.set_ylabel('head difference to reference [cm]')
ax.set_ylim(0, max(maxs) * 1.25); ax.legend()
save(fig, 'fig_sz_classes.png')
