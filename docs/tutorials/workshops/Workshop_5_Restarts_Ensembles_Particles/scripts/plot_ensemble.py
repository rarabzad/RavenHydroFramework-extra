#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Plots the members of a Raven ensemble run with groundwater.

    python3 plot_ensemble.py OUT_ENS [--ref OUT] [--well ID] [--png FILE]

Reads GWHeads.csv and GWBudget.csv of every member folder OUT_ENS/ens_N: the head at the observation well ID (default:
the last well of GWHeads.csv) and the recharge reaching MODFLOW (30-day means). --ref adds the head of a single run as a
dashed line. Prints, per member, the mean recharge [m3/d] and the head on the last day [m]. Writes ensemble.png in the
current folder unless --png is given. Needs Python 3 with pandas and matplotlib.
"""
import argparse, glob, os, re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ens'); ap.add_argument('--ref'); ap.add_argument('--well'); ap.add_argument('--png', default='ensemble.png')
    a = ap.parse_args()
    members = sorted(glob.glob(os.path.join(a.ens, 'ens_*')), key=lambda p: int(re.search(r'(\d+)$', p).group(1)))
    fig, ax = plt.subplots(2, 1, figsize=(8.6, 5.0), sharex=True)
    col = None
    for m in members:
        n = int(re.search(r'(\d+)$', m).group(1))
        g = pd.read_csv(os.path.join(m, 'GWHeads.csv')); b = pd.read_csv(os.path.join(m, 'GWBudget.csv'))
        col = col or ([c for c in g.columns if '(%s)' % a.well in c][0] if a.well else g.columns[-1])
        ax[0].plot(pd.to_datetime(g['date']), g[col], lw=1.0, label='member %d' % n)
        ax[1].plot(pd.to_datetime(b['date']), b['MF6 recharge [m3/d]'].rolling(30, min_periods=1).mean() / 1000.0, lw=1.0)
        print('member %d: mean recharge %.0f m3/d, head at %s on the last day %.2f m'
              % (n, b['MF6 recharge [m3/d]'].mean(), col.replace(' [m]', ''), g[col].iloc[-1]))
    if a.ref:
        g = pd.read_csv(os.path.join(a.ref, 'GWHeads.csv'))
        ax[0].plot(pd.to_datetime(g['date']), g[col], 'k--', lw=1.0, label='single run')
    ax[0].set_ylabel('head [m]'); ax[0].set_title('%s: head in each member' % col.replace(' [m]', ''))
    ax[0].legend(fontsize=7, ncol=3)
    ax[1].set_ylabel('1000 m$^3$/d'); ax[1].set_title('recharge reaching MODFLOW, 30-day means')
    fig.tight_layout(); fig.savefig(a.png, dpi=150)
    print('wrote ' + a.png)


if __name__ == '__main__':
    main()
