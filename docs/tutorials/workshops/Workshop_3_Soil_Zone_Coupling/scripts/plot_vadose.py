#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Plots the unsaturated columns (:SoilZoneVadose) of one or more coupled runs.

    python3 plot_vadose.py OUT1 OUT2 ... [--png FILE]

Reads GWBudget.csv of each output folder: the water entering the unsaturated columns, the water they pass to the water
table (30-day means) and the water they store. The label of a run is its folder name without "out_", in capitals.
Prints, per run, the mean inflow and outflow [m3/d] and the storage at the end [m3]. Writes vadose.png in the current
folder unless --png is given. Needs Python 3 with pandas and matplotlib.
"""
import argparse, os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('outs', nargs='+'); ap.add_argument('--png', default='vadose.png')
    a = ap.parse_args()
    colors = ['#1f4e79', '#2e8b57', '#d08a2b', '#7a3b8f']
    fig, ax = plt.subplots(2, 1, figsize=(8.6, 5.4), sharex=True)
    for k, o in enumerate(a.outs):
        lab = os.path.basename(os.path.normpath(o)).replace('out_', '').upper()
        b = pd.read_csv(os.path.join(o, 'GWBudget.csv'))
        b['date'] = pd.to_datetime(b['date'])
        qin, qout, st = (b['unsaturated zone inflow [m3]'], b['unsaturated zone to aquifer [m3]'],
                         b['unsaturated zone storage [m3]'])
        if k == 0:
            ax[0].plot(b['date'], qin.rolling(30, min_periods=1).mean() / 1000.0, color='0.5', lw=1.0, label='into the columns')
        ax[0].plot(b['date'], qout.rolling(30, min_periods=1).mean() / 1000.0, color=colors[k % len(colors)], lw=1.0,
                   label='to the water table, ' + lab)
        ax[1].plot(b['date'], st / 1e6, color=colors[k % len(colors)], lw=1.2, label=lab)
        print('%-10s inflow %8.0f m3/d   to the water table %8.0f m3/d   storage at the end %10.0f m3'
              % (lab, qin.mean(), qout.mean(), st.iloc[-1]))
    ax[0].set_ylabel('1000 m$^3$/d'); ax[0].set_title('unsaturated columns: inflow and outflow to the aquifer, 30-day means')
    ax[0].legend(fontsize=7)
    ax[1].set_ylabel('million m$^3$'); ax[1].set_title('water stored in the unsaturated columns'); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(a.png, dpi=150)
    print('wrote ' + a.png)


if __name__ == '__main__':
    main()
