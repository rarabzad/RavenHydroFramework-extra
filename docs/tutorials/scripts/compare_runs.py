#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Compares coupled Raven-MODFLOW 6 runs of the same model.

    python3 compare_runs.py OUT1 OUT2 ... [--hrus ID ...] [--png FILE]
    python3 compare_runs.py --diff OUT_A OUT_B

First form: one line per run (output folder) with the 3-year means of the groundwater budget, the mean water-table
depth of the HRUs given with --hrus, and the mean streamflow at the outlet; and a figure (default compare_runs.png in
the current folder): recharge reaching the water table (30-day means), water-table depth of the first --hrus HRU, and
streamflow.

Second form (--diff): the largest absolute difference of every number in GWBudget.csv, GWHeads.csv, GWHRUState.csv and
Hydrographs.csv on the dates the two runs share (for example a run continued from solution.rvc against one continuous
run); 0 means identical.

Needs Python 3 with numpy, pandas and matplotlib.
"""
import argparse, os, sys
import numpy as np
import pandas as pd

COLS = [('Raven recharge [m3/d]', 'leaves soil'), ('MF6 recharge [m3/d]', 'reaches WT'),
        ('rejected recharge [m3]', 'rejected'), ('aquifer to soil zone [m3/d]', 'aq->soil'),
        ('seepage to Raven [m3/d]', 'seepage'), ('aquifer discharge to rivers [m3/d]', 'to rivers')]


def read(out, name):
    p = os.path.join(out, name)
    if not os.path.exists(p):
        return None
    t = pd.read_csv(p, skipinitialspace=True)
    t.columns = [c.strip() for c in t.columns]
    return t


def outlet(h):
    """the last flow column of Hydrographs.csv (Raven lists the subbasins in order; here the outlet is last)"""
    q = [c for c in h.columns if c.endswith('[m3/s]') and '(observed)' not in c and '(res. inflow)' not in c]
    return q[-1]


def metrics(out, hrus):
    b, h, s = read(out, 'GWBudget.csv'), read(out, 'Hydrographs.csv'), read(out, 'GWHRUState.csv')
    m = {'run': os.path.basename(os.path.normpath(out))}
    for c, lab in COLS:
        m[lab] = b[c].mean() if c in b else 0.0
    m['UZ storage end'] = b['unsaturated zone storage [m3]'].iloc[-1] if 'unsaturated zone storage [m3]' in b else 0.0
    for k in hrus:
        m['WT depth %d' % k] = s['wtdepth_%d [m]' % k].mean()
    m['Q outlet'] = h[outlet(h)].iloc[1:].mean()
    return m


def diff(a, b):
    worst = 0.0
    for f in ('GWBudget.csv', 'GWHeads.csv', 'GWHRUState.csv', 'Hydrographs.csv'):
        x, y = read(a, f), read(b, f)
        if x is None or y is None:
            continue
        x, y = x.set_index('date'), y.set_index('date')
        common = x.index.intersection(y.index)
        if f == 'Hydrographs.csv':
            common = common[1:]          # the first row of a run is its initial state (no precipitation, no step)
        num = [c for c in x.columns if c in y.columns and pd.api.types.is_numeric_dtype(x[c]) and c not in ('time [d]', 'time')]
        d = max((np.abs(x.loc[common, c].values - y.loc[common, c].values).max() for c in num), default=0.0)
        print('%-16s %5d common dates, %3d columns: largest difference %g' % (f, len(common), len(num), d))
        worst = max(worst, d)
    print('largest difference of all: %g' % worst)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outs', nargs='+')
    ap.add_argument('--hrus', type=int, nargs='*', default=[])
    ap.add_argument('--png', default='compare_runs.png')
    ap.add_argument('--diff', action='store_true')
    a = ap.parse_args()
    if a.diff:
        if len(a.outs) != 2:
            sys.exit('--diff compares two output folders')
        diff(*a.outs)
        return
    rows = [metrics(o, a.hrus) for o in a.outs]
    t = pd.DataFrame(rows).set_index('run')
    pd.set_option('display.width', 200)
    print('means over the run; flows in m3/d (rejected recharge in m3 per day), storage in m3, depths in m, Q in m3/s')
    print(t.T.to_string(float_format=lambda v: '%.4g' % v))         # one column per run
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 1, figsize=(8.6, 7.6), sharex=True)
    for o in a.outs:
        b, h, s = read(o, 'GWBudget.csv'), read(o, 'Hydrographs.csv'), read(o, 'GWHRUState.csv')
        lab = os.path.basename(os.path.normpath(o))
        d = pd.to_datetime(b['date'])
        ax[0].plot(d, b['MF6 recharge [m3/d]'].rolling(30, min_periods=1).mean() / 1000.0, lw=1.0, label=lab)
        if a.hrus:
            ax[1].plot(pd.to_datetime(s['date']), s['wtdepth_%d [m]' % a.hrus[0]], lw=1.0, label=lab)
        ax[2].plot(pd.to_datetime(h['date']), h[outlet(h)].rolling(7, min_periods=1).mean(), lw=0.9, label=lab)
    ax[0].set_ylabel('1000 m$^3$/d'); ax[0].set_title('recharge reaching the water table (MF6 recharge), 30-day means')
    if a.hrus:
        ax[1].invert_yaxis(); ax[1].set_ylabel('m'); ax[1].set_title('water-table depth, HRU %d' % a.hrus[0])
    ax[2].set_ylabel('m$^3$/s'); ax[2].set_title('streamflow at the outlet, 7-day means')
    ax[0].legend(fontsize=7, ncol=3)
    fig.tight_layout()
    fig.savefig(a.png, dpi=130)
    print('wrote', a.png)


if __name__ == '__main__':
    main()
