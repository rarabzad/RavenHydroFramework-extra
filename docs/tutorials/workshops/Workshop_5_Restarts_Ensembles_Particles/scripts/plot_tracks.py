#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Plots the particle tracks of tools/make_prt.py on the grid of a coupled Raven-MODFLOW 6 run.

    python3 plot_tracks.py OUTPUT_FOLDER [--png FILE] [--zoom M]

Reads OUTPUT_FOLDER/mf6/gwf.dis.grb (the regular grid Raven built), OUTPUT_FOLDER/prt/prt.trk.csv (the tracks) and
OUTPUT_FOLDER/prt/endpoints.csv (the travel times), and draws the active cells, the tracks and their end points, around
the release points (--zoom: half width of the window [m], default 600). PRT writes its tracks relative to the corner of
the grid; they are shifted by XORIGIN/YORIGIN of the grid file, so that the plot and the printed points use the frame of
endpoints.csv (the model coordinates of the .rvg). Writes OUTPUT_FOLDER/prt/tracks.png unless --png is given, and prints
the length and travel time of each track. Needs Python 3 with numpy, pandas and matplotlib.
"""
import argparse, os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.dont_write_bytecode = True   # (no __pycache__ beside the workshop's scripts)
from plot_gw import read_grb   # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out'); ap.add_argument('--png'); ap.add_argument('--zoom', type=float, default=600.0)
    a = ap.parse_args()
    g = read_grb(os.path.join(a.out, 'mf6', 'gwf.dis.grb'))
    nrow, ncol, nlay = int(g['NROW']), int(g['NCOL']), int(g['NLAY'])
    xo, yo = float(g.get('XORIGIN', 0.0)), float(g.get('YORIGIN', 0.0))
    xe = xo + np.concatenate([[0.0], np.cumsum(g['DELR'])])
    ye = yo + np.concatenate([[0.0], np.cumsum(g['DELC'][::-1])])  # row 1 is the northern row
    idom = g['IDOMAIN'].reshape(nlay, nrow, ncol)
    t = pd.read_csv(os.path.join(a.out, 'prt', 'prt.trk.csv'))
    t['x'] += xo; t['y'] += yo                                      # PRT's local frame -> the frame of endpoints.csv
    ep = pd.read_csv(os.path.join(a.out, 'prt', 'endpoints.csv')).set_index('particle')
    fig, ax = plt.subplots(figsize=(6.4, 5.6))
    for r in range(nrow):
        for c in range(ncol):
            if idom[0, r, c] > 0:
                y0 = ye[nrow - 1 - r]
                ax.add_patch(plt.Rectangle((xe[c], y0), xe[c + 1] - xe[c], ye[nrow - r] - y0, fc='#f3f6ee', ec='#9a9a9a', lw=0.4))
    print('particle  release point (x, y) [m]   track length [m]   travel time [d]')
    for (irpt, tr), g1 in t.groupby(['irpt', 'trelease']):
        if tr != t['trelease'].min():
            continue                                     # the first release only
        g1 = g1.sort_values('t')
        ax.plot(g1['x'], g1['y'], '-', lw=1.2)
        ax.plot(g1['x'].iloc[0], g1['y'].iloc[0], 'k.', ms=4)
        ax.plot(g1['x'].iloc[-1], g1['y'].iloc[-1], 'o', mfc='white', mec='k', ms=4)
        L = np.hypot(np.diff(g1['x']), np.diff(g1['y'])).sum()
        tt = ep.loc[irpt, 'travel_time_d'] if irpt in ep.index else np.nan
        print('%8d  (%8.1f, %8.1f)        %10.1f        %10.1f' % (irpt, g1['x'].iloc[0], g1['y'].iloc[0], L, tt))
    x0, y0 = t['x'].iloc[0], t['y'].iloc[0]
    ax.set_xlim(x0 - a.zoom, x0 + a.zoom); ax.set_ylim(y0 - a.zoom, y0 + a.zoom); ax.set_aspect(1.0)
    ax.set_xlabel('x, model coordinates [m]'); ax.set_ylabel('y, model coordinates [m]')
    ax.set_title('particle tracks (dots: release points, circles: end points)', fontsize=10)
    fig.tight_layout()
    png = a.png or os.path.join(a.out, 'prt', 'tracks.png')
    fig.savefig(png, dpi=130)
    print('wrote', png)


if __name__ == '__main__':
    main()
