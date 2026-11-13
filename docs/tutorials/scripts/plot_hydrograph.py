#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Plots the streamflow of one subbasin in two (or more) Raven runs, for one year.

    python3 plot_hydrograph.py OUT1 OUT2 ... [--labels L1 L2 ...] [--subbasin NAME] [--year YYYY] [--png FILE]

Reads Hydrographs.csv of each output folder and draws the column "NAME [m3/s]" (default: the last subbasin) over the
year given (default: the second year of the runs). Prints the mean flow of each run over the whole run, without its
first line (the initial state). Writes hydrograph.png in the current folder unless --png is given. Needs Python 3 with
pandas and matplotlib.
"""
import argparse
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outs', nargs='+'); ap.add_argument('--labels', nargs='+'); ap.add_argument('--subbasin')
    ap.add_argument('--year', type=int); ap.add_argument('--png', default='hydrograph.png')
    a = ap.parse_args()
    labels = a.labels or a.outs
    colors = ['#d08a2b', '#1f4e79', '#2e8b57', '#7a3b8f']
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    for k, (o, lab) in enumerate(zip(a.outs, labels)):
        h = pd.read_csv(o + '/Hydrographs.csv')
        h['date'] = pd.to_datetime(h['date'])
        q = [c for c in h.columns if c.endswith('[m3/s]') and not c.endswith('(observed) [m3/s]')]
        col = (a.subbasin + ' [m3/s]') if a.subbasin else q[-1]
        year = a.year or h['date'].dt.year.iloc[0] + 1
        sel = h['date'].dt.year == year
        ax.plot(h['date'][sel], h[col][sel], color=colors[k % len(colors)], lw=0.9, label=lab)
        print('%-24s mean flow %s %.2f m3/s' % (lab, col.replace(' [m3/s]', ''), h[col].iloc[1:].mean()))
    ax.set_ylabel('m$^3$/s'); ax.set_title('streamflow at the outlet of subbasin %s, %d' % (col.replace(' [m3/s]', ''), year))
    ax.legend()
    fig.tight_layout(); fig.savefig(a.png, dpi=150)
    print('wrote ' + a.png)


if __name__ == '__main__':
    main()
