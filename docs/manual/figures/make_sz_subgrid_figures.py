"""Figures of the soil zone's sub-grid treatment (manual Section 'Sloping and irregular land'; symbols as in the manual's notation table):
  fig_sz_subgrid.png    one cell with irregular land: DEM points, soil-zone bases, the flat water table and soil water
                        level, the saturated part of every point, the contact weights and the saturated fraction F
                        (computed with the model's own formulas, gwsz SatFraction / contact weight / level)
  fig_sz_hillslope.png  a coupled run: the T2/T3 hillslope with an irregular DEM (slope plus undulations) and 25 DEM
                        points per cell: water table along the slope, the saturated part of the soil, and F per HRU
Usage: RAVEN_EXE=... RAVEN_MF6_LIB=... python3 make_sz_subgrid_figures.py"""
import os, sys, math, shutil
import numpy as np, pandas as pd, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', '..', '..', 'tests'); sys.path.insert(0, T); sys.path.insert(0, os.path.join(T, 'soilzone'))
plt.rcParams.update({'font.size': 9, 'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.grid': True, 'grid.color': '#e4e3df', 'grid.linewidth': 0.6, 'axes.edgecolor': '#52514e',
                     'axes.labelcolor': '#0b0b0b', 'xtick.color': '#52514e', 'ytick.color': '#52514e', 'legend.frameon': False})
C = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#6250d6']
INK2 = '#52514e'; SOIL = '#d9c3a5'; SAT = '#7fb2e5'; AQ = '#dbe8f6'

def sstep(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3.0 - 2.0 * x)

def save(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(HERE, name)); plt.close(fig); print('wrote', name)

# ---------------------------------------------------------------- 1. one cell, irregular land
D, ds = 1.0, 0.3                                    # soil-zone thickness, smoothing depth (capillary fringe) [m]
xs = np.linspace(5, 95, 10)                         # DEM points across the cell (a transect of the N x N samples)
land = 101.0 - 0.012 * xs + 0.55 * np.exp(-((xs - 30) / 14.0) ** 2) - 0.45 * np.exp(-((xs - 68) / 10.0) ** 2)
zb = land - D
def state(h, Lv=None):
    Lv = h if Lv is None else Lv                                     # soil water level (= water table at rest)
    F = sstep((h - zb) / ds).mean()                                  # saturated fraction (recharge rejected there)
    w = sstep((h - zb) / ds + 1.0)                                   # contact weight of each point
    sat = np.clip(Lv - zb, 0.0, D)                                   # free water standing in the soil at each point
    qs = w * (np.clip(Lv, zb, zb + D) - np.maximum(h, zb))           # exchange of each point / C (positive down)
    return F, w, sat, sat.mean(), qs
hb = zb.min() + 0.45
cases = [(zb.min() - 0.25, None, 'deep water table'),
         (hb, None, 'water table partly in the soil, at rest'),
         (hb, hb + 0.45, 'after rain: soil water above the water table'),
         (zb.mean() + 0.55, zb.mean() + 0.2, 'high water table, soil drier')]
fig = plt.figure(figsize=(7.4, 7.6))
gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.85])
xx = np.linspace(0, 100, 400)
landf = np.interp(xx, xs, land); zbf = landf - D
ylo = zb.min() - 2.0
for i, (h, Lv, lab) in enumerate(cases):
    ax = fig.add_subplot(gs[i // 2, i % 2]); F, w, sat, lam, qs = state(h, Lv); L = h if Lv is None else Lv
    ax.fill_between(xx, ylo, np.minimum(h, zbf), color=AQ, lw=0)                             # aquifer, saturated below h
    ax.fill_between(xx, zbf, landf, color=SOIL, lw=0)                                         # soil zone
    ax.fill_between(xx, zbf, np.clip(L, zbf, landf), where=L > zbf, color=SAT, lw=0)          # free water in the soil
    ax.plot(xx, landf, color='#5b4a33', lw=1.2); ax.plot(xx, zbf, color='#5b4a33', lw=0.8, ls='--')
    ax.axhline(h, color=C[0], lw=1.4); ax.plot([1.5], [h], marker='v', color=C[0], ms=6, clip_on=False)
    if Lv is not None:
        ax.axhline(Lv, color=C[4], lw=1.2, ls=(0, (4, 2)))
        ax.text(101.5, Lv, '$h^{\\mathrm{sz}}$', color=C[4], ha='left', va='center', fontsize=8, clip_on=False)
    ax.text(101.5, h, '$h$', color=C[0], ha='left', va='center', fontsize=8, clip_on=False)
    for x, z, ww, q in zip(xs, zb, w, qs):
        ax.plot([x], [z], marker='o', ms=4.5, mec=INK2, mfc=plt.cm.Blues(0.15 + 0.8 * ww), mew=0.6, zorder=5)
        if abs(q) > 0.02:
            ax.annotate('', xy=(x, z - 1.3 * q), xytext=(x, z), zorder=6,
                        arrowprops=dict(arrowstyle='-|>', color=C[2] if q > 0 else C[1], lw=1.3, mutation_scale=8))
    ov = h > land
    if ov.any(): ax.plot(xs[ov], land[ov], ls='none', marker='^', color=C[1], ms=6, zorder=6)
    ax.set_xlim(0, 100); ax.set_ylim(ylo, land.max() + 0.35)
    qn = qs.mean()
    ax.set_title('(%s) %s\nF = %.2f,  $b^{\\mathrm{sz}}$ = %.2f m,  q/C = %+.2f m%s' % ('abcd'[i], lab, F, lam, qn, ' (down)' if qn > 0.01 else ' (up)' if qn < -0.01 else ''), fontsize=8, loc='left')
    if i >= 2: ax.set_xlabel('across the cell [m]')
    else: ax.set_xticklabels([])
    if i % 2 == 0: ax.set_ylabel('elevation [m]')
    else: ax.set_yticklabels([])
    if i == 0:
        from matplotlib.lines import Line2D
        from matplotlib.patches import Patch
        hd = [Line2D([], [], color='#5b4a33', lw=1.2, label='land surface'),
              Line2D([], [], color='#5b4a33', lw=0.8, ls='--', label='soil-zone base $z_{b,g}$'),
              Line2D([], [], ls='none', marker='o', mec=INK2, mfc=plt.cm.Blues(0.6), label='DEM point (shade: contact $w_g$)'),
              Patch(color=SAT, label='free water in the soil'), Patch(color=AQ, label='aquifer below $h$')]
        ax.legend(handles=hd, fontsize=6.3, loc='lower center', ncol=2, columnspacing=1.0, handlelength=1.6)
    if i == 3:
        from matplotlib.lines import Line2D
        hd = [Line2D([], [], color=C[2], marker=r'$\downarrow$', ls='none', ms=8, label='soil to aquifer'),
              Line2D([], [], color=C[1], marker=r'$\uparrow$', ls='none', ms=8, label='aquifer to soil'),
              Line2D([], [], color=C[1], marker='^', ls='none', ms=6, label='above land: overflow')]
        ax.legend(handles=hd, fontsize=6.5, loc='lower right')
ax = fig.add_subplot(gs[2, :])
hh = np.linspace(zb.min() - 0.6, land.max() + 0.2, 400)
Fs = [state(h)[0] for h in hh]; Ls = [state(h)[3] / D for h in hh]; Cs = [state(h)[1].mean() for h in hh]
ax.plot(hh, Fs, color=C[0], lw=2, label='saturated fraction $F$ (recharge rejected; saturated soil evaporates in Raven)')
ax.plot(hh, Cs, color=C[2], lw=1.6, ls='--', label='mean contact $\\bar w$ (from $d_s$ below each base)')
ax.plot(hh, Ls, color=C[1], lw=1.6, label='saturated thickness at rest $b^{\\mathrm{sz}}/d_{\\mathrm{sz}}$')
for i, (h, Lv, lab) in enumerate(cases):
    if i == 2: continue
    ax.axvline(h, color=INK2, lw=0.8, ls=':')
    ax.text(h, 1.04, '(%s)' % ('b, c' if i == 1 else 'abcd'[i]), ha='center', fontsize=8, color=INK2)
ax.set_xlabel('water table $h$ in the cell [m]'); ax.set_ylabel('fraction [-]'); ax.set_ylim(-0.03, 1.12)
ax.legend(fontsize=7, loc='lower right')
save(fig, 'fig_sz_subgrid.png')

# ---------------------------------------------------------------- 2. coupled hillslope with an irregular DEM
EXE = os.environ.get('RAVEN_EXE')
if not EXE:
    print('RAVEN_EXE not set: fig_sz_hillslope.png not made'); sys.exit(0)
import sz_models, sz_check
from test_hillslope import CFG
W = os.environ.get('SZFIG_WORK', os.path.join(HERE, '_work_subgrid')); d = os.path.join(W, 'irregular')
shutil.rmtree(d, ignore_errors=True)
cfg = dict(CFG); cfg.update(subgrid=5, smooth=0.1)
sz_models.make_case(d, **cfg)
# irregular DEM: the 0.5 % slope plus a hump and two hollows along the slope
p = os.path.join(d, 'dem.asc'); L = open(p).read().split('\n'); hdr = L[:6]; rows = [r for r in L[6:] if r.strip()]
nc = int(hdr[0].split()[1]); xll = float(hdr[2].split()[1]); cs = float(hdr[4].split()[1])
xm = [sz_models.xy(xll + (c + 0.5) * cs, float(hdr[3].split()[1]))[0] for c in range(nc)]
x0 = -0.5 * cfg['nhru'] * cfg['hru_w']
def bump(x):
    s = x - x0
    return 0.6 * math.exp(-((s - 300.0) / 60.0) ** 2) - 0.5 * math.exp(-((s - 620.0) / 45.0) ** 2) - 0.35 * math.exp(-((s - 850.0) / 40.0) ** 2)
out = hdr + [' '.join('%.4f' % (float(v) + bump(xm[c])) for c, v in enumerate(r.split())) for r in rows]
open(p, 'w').write('\n'.join(out) + '\n')
ok, txt = sz_check.run(d)
if not ok:
    print(txt[-2000:]); sys.exit(1)
r = sz_check.checks(d); print({k: '%.2g' % v for k, v in r.items() if isinstance(v, float)})
s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
nh = cfg['nhru']; hw = cfg['hru_w']; z0 = 100.0; sl = cfg['slope']
xe = np.linspace(0, nh * hw, 600)
landx = z0 - sl * xe + np.array([bump(x0 + v) for v in xe]); zbx = landx - (cfg['H0'] + cfg['H1'])
fig, axs = plt.subplots(2, 1, figsize=(7.4, 5.4), gridspec_kw={'height_ratios': [1.2, 1.0]})
ax = axs[0]
days = (60, 120, 150, 200)
ax.fill_between(xe, zbx, landx, color=SOIL, lw=0)
ax.plot(xe, landx, color='#5b4a33', lw=1.2, label='land surface'); ax.plot(xe, zbx, color='#5b4a33', lw=0.8, ls='--', label='soil-zone base')
for i, t in enumerate(days):
    g = s[s['time [d]'] == t].sort_values('HRU_ID')
    hk = g['water table [m]'].values
    xc = (np.arange(nh) + 0.5) * hw
    hwt = hk[np.minimum((xe // hw).astype(int), nh - 1)]   # MODFLOW's head is flat over each cell
    ax.plot(xe, hwt, color=C[i], lw=1.4, label='water table, day %d' % t)
    if t == 150:
        ax.fill_between(xe, zbx, np.clip(hwt, zbx, landx), where=hwt > zbx, color=SAT, lw=0, alpha=0.9, label='saturated soil, day 150')
ax.set_xlim(0, nh * hw); ax.set_ylabel('elevation [m]'); ax.set_xlabel('distance down the slope [m] (each HRU: a 100 m wide strip of cells)')
ax.legend(fontsize=7, ncol=2, loc='lower left')
ax = axs[1]
piv = s.pivot_table(index='time [d]', columns='HRU_ID', values='saturated fraction [-]')
im = ax.imshow(piv.values.T, aspect='auto', origin='lower', cmap='Blues', vmin=0, vmax=1, interpolation='nearest',
               extent=[piv.index.min() - 0.5, piv.index.max() + 0.5, 0.5, nh + 0.5])
ax.set_xlabel('day (rain 10 mm/d until day 150, then dry)'); ax.set_ylabel('HRU (1 = top of slope)'); ax.grid(False)
ov = s.pivot_table(index='time [d]', columns='HRU_ID', values='overflow [mm]')
yy, xx2 = np.where(ov.values.T > 0.05)
ax.plot(ov.index.values[xx2], yy + 1, ls='none', marker='.', ms=1.5, color=C[1], label='overflow to surface water')
ax.legend(fontsize=7, loc='lower right', markerscale=6)
fig.colorbar(im, ax=ax, label='saturated fraction F')
save(fig, 'fig_sz_hillslope.png')
