#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Plots the groundwater results of a coupled Raven-MODFLOW 6 run.

    python3 plot_gw.py OUTPUT_FOLDER [--hrus ID ...] [--title TEXT]

OUTPUT_FOLDER is Raven's output folder (the one given with -o). Writes into it:
  gw_budget.png      daily groundwater budget (GWBudget.csv), 7-day means
  gw_watertable.png  water-table depth below the land surface of some coupled HRUs (GWHRUState.csv);
                     default: the shallowest and the deepest two HRUs, or the HRUs given with --hrus
  gw_map.png         map of the water-table depth on the last head record of the MODFLOW head file (mf6/*.hds),
                     on the cells of mf6/grid_cells.geojson
  gw_obswells.png    heads at the observation wells (GWHeads.csv), when the model has some
and prints a short summary. Needs Python 3 with numpy, pandas and matplotlib (no FloPy).
"""
import argparse, glob, json, math, os, struct, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection


def read_grb(path):
    """MODFLOW 6 binary grid file (*.grb): dict of its arrays (TOP, BOTM, IDOMAIN, ...)"""
    with open(path, 'rb') as f:
        hdr = [f.read(50).decode().strip() for _ in range(4)]
        ntxt, lentxt = int(hdr[2].split()[1]), int(hdr[3].split()[1])
        defs = [f.read(lentxt).decode().strip() for _ in range(ntxt)]
        out = {}
        for d in defs:
            w = d.split()
            name, typ, ndim = w[0], w[1], int(w[3])
            dims = [int(x) for x in w[4:4 + ndim]]
            n = int(np.prod(dims)) if ndim else 1
            dt = '<i4' if typ == 'INTEGER' else '<f8'
            a = np.frombuffer(f.read(n * np.dtype(dt).itemsize), dtype=dt)
            out[name] = a[0] if ndim == 0 else a
    return out


def read_last_heads(path, nlay, ncpl):
    """last saved head of every cell (nlay x ncpl) of a MODFLOW 6 head file, and its time [d]"""
    rec = 4 + 4 + 8 + 8 + 16 + 4 + 4 + 4
    size = os.path.getsize(path)
    with open(path, 'rb') as f:
        first = f.read(rec)
        ncol, nrow = struct.unpack('<ii', first[40:48])
        step = rec + 8 * ncol * nrow
        nrec = size // step
        last = nrec - nlay
        h = np.empty((nlay, ncpl))
        for k in range(nlay):
            f.seek((last + k) * step)
            hd = f.read(rec)
            totim = struct.unpack('<d', hd[16:24])[0]
            ilay = struct.unpack('<i', hd[48:52])[0]
            h[ilay - 1] = np.frombuffer(f.read(8 * ncol * nrow), dtype='<f8')
    return h, totim


def water_table(top, botm, heads, idomain):
    """water-table elevation of every column: the head of the highest layer whose head lies above its bottom"""
    nlay, ncpl = heads.shape
    wt = np.full(ncpl, np.nan)
    for k in range(nlay - 1, -1, -1):
        ok = (idomain[k] > 0) & (np.abs(heads[k]) < 1e20) & (heads[k] > botm[k])
        wt[ok] = heads[k][ok]
    return wt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--hrus', type=int, nargs='*', default=None)
    ap.add_argument('--title', default='')
    a = ap.parse_args()
    out = a.out
    b = pd.read_csv(os.path.join(out, 'GWBudget.csv'))
    s = pd.read_csv(os.path.join(out, 'GWHRUState.csv'))
    b['date'] = pd.to_datetime(b['date']); s['date'] = pd.to_datetime(s['date'])
    title = (a.title + ': ') if a.title else ''

    # --- budget
    terms = [('MF6 recharge [m3/d]', 'recharge received by MODFLOW', 1), ('seepage to Raven [m3/d]', 'seepage to Raven', -1),
             ('aquifer discharge to rivers [m3/d]', 'aquifer to rivers', -1), ('river leakage to aquifer [m3/d]', 'rivers to aquifer', 1),
             ('storage release [m3/d]', 'storage release', 1)]
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for col, lab, sg in terms:
        if col in b and b[col].abs().max() > 0:
            ax.plot(b['date'], sg * b[col].rolling(7, min_periods=1).mean() / 1000.0, lw=1.0, label=lab)
    for col, lab in (('wells actual [m3/d]', 'wells'), ('GHB [m3/d]', 'head boundaries (GHB)'), ('CHD [m3/d]', 'specified heads (CHD)'),
                     ('water-table ET [m3/d]', 'water-table ET'), ('other model packages [m3/d]', 'model\'s own packages')):
        if col in b and b[col].abs().max() > 0:
            sg = -1 if col == 'water-table ET [m3/d]' else 1
            ax.plot(b['date'], sg * b[col].rolling(7, min_periods=1).mean() / 1000.0, lw=1.0, ls='--', label=lab)
    ax.axhline(0, color='k', lw=0.5)
    ax.set_ylabel('1000 m$^3$/d  (+ into the aquifer)')
    ax.set_title(title + 'groundwater budget, 7-day means', fontsize=10)
    ax.legend(fontsize=7, ncol=2, loc='upper right')
    fig.tight_layout(); fig.savefig(os.path.join(out, 'gw_budget.png'), dpi=130); plt.close(fig)

    # --- water-table depth
    dcols = [c for c in s.columns if c.startswith('wtdepth_')]
    means = s[dcols].mean()
    if a.hrus:
        pick = ['wtdepth_%d [m]' % h for h in a.hrus]
    else:
        srt = means.sort_values()
        pick = list(dict.fromkeys(list(srt.index[:2]) + list(srt.index[-2:])))
    fig, ax = plt.subplots(figsize=(8, 3.2))
    for c in pick:
        ax.plot(s['date'], s[c], lw=1.0, label='HRU ' + c.split('_')[1].split()[0])
    ax.invert_yaxis(); ax.set_ylabel('depth below land surface [m]')
    ax.set_title(title + 'water-table depth', fontsize=10); ax.legend(fontsize=7, ncol=4)
    fig.tight_layout(); fig.savefig(os.path.join(out, 'gw_watertable.png'), dpi=130); plt.close(fig)

    # --- map
    mf = os.path.join(out, 'mf6')
    grb = sorted(glob.glob(os.path.join(mf, '*.grb')))
    hds = sorted(glob.glob(os.path.join(mf, '*.hds')))
    if grb and hds:
        g = read_grb(grb[0])
        nlay = int(g['NLAY'])
        ncpl = int(g['NCELLS']) // nlay
        top = g['TOP'][:ncpl]
        botm = g['BOTM'].reshape(nlay, ncpl)
        idom = g['IDOMAIN'].reshape(nlay, ncpl)
        h, totim = read_last_heads(hds[0], nlay, ncpl)
        lf = 1.0
        if 'feet' in open(os.path.join(mf, os.path.basename(grb[0])[:-4]), errors='ignore').read().lower():
            lf = 0.3048                                  # a model in feet: depths shown in metres
        wt = water_table(top, botm, h, idom)
        depth = (top - wt) * lf
        cells = json.load(open(os.path.join(mf, 'grid_cells.geojson')))['features']
        polys, vals = [], []
        lat0 = None
        for c in cells:
            i = c['properties']['cell'] - 1
            if not c['properties'].get('active', 1) or not np.isfinite(depth[i]):
                continue
            ring = np.array(c['geometry']['coordinates'][0])
            lat0 = ring[0, 1] if lat0 is None else lat0
            polys.append(ring); vals.append(depth[i])
        fig, ax = plt.subplots(figsize=(7, 5))
        pc = PolyCollection(polys, array=np.array(vals), cmap='viridis_r', edgecolors='face', linewidths=0.2)
        pc.set_clim(0, max(1.0, np.nanpercentile(vals, 98)))
        ax.add_collection(pc); ax.autoscale_view()
        ax.set_aspect(1.0 / math.cos(math.radians(lat0)))
        fig.colorbar(pc, ax=ax, label='water-table depth below model top [m]', shrink=0.8)
        ax.set_xlabel('longitude'); ax.set_ylabel('latitude'); ax.ticklabel_format(useOffset=False)
        ax.set_title(title + 'water-table depth, day %g of the run' % totim, fontsize=10)
        fig.tight_layout(); fig.savefig(os.path.join(out, 'gw_map.png'), dpi=130); plt.close(fig)

    # --- observation wells
    p = os.path.join(out, 'GWHeads.csv')
    if os.path.exists(p):
        w = pd.read_csv(p); w['date'] = pd.to_datetime(w['date'])
        fig, ax = plt.subplots(len(w.columns) - 2, 1, figsize=(8, 1.9 * (len(w.columns) - 2)), sharex=True, squeeze=False)
        for k, c in enumerate(w.columns[2:]):
            ax[k][0].plot(w['date'], w[c].where(w[c] > -1.2), lw=1.0)
            ax[k][0].set_ylabel('m'); ax[k][0].set_title(c, fontsize=9)
        fig.tight_layout(); fig.savefig(os.path.join(out, 'gw_obswells.png'), dpi=130); plt.close(fig)

    # --- summary
    n = len(b)
    print('%d days, %s to %s' % (n, b['date'].iloc[0].date(), b['date'].iloc[-1].date()))
    print('mean groundwater budget [m3/d]:')
    for col, lab, sg in terms:
        if col in b:
            print('  %-32s %12.0f' % (lab, b[col].mean()))
    print('  %-32s %12.2e' % ('largest |MF6 balance error| [%]', b['MF6 balance error [%]'].abs().max()))
    print('  %-32s %12d' % ('unconverged steps', int((b['converged'] == 0).sum())))
    lst = ['HRU %s %.2f' % (c.split('_')[1].split()[0], means[c]) for c in dcols]
    more = '' if len(lst) <= 10 else ' ... (%d HRUs; range %.2f to %.2f)' % (len(lst), means.min(), means.max())
    print('mean water-table depth [m]: ' + ', '.join(lst[:10]) + more)
    print('wrote ' + ', '.join(os.path.basename(x) for x in sorted(glob.glob(os.path.join(out, 'gw_*.png')))))


if __name__ == '__main__':
    main()
