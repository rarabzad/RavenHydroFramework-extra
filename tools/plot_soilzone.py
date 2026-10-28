"""Plots the soil-zone <-> groundwater exchange of a run with :SoilZone PHYSICAL (GWSoilExchange.csv, GWBudget.csv).

    python3 tools/plot_soilzone.py OUTPUT_FOLDER [HRU_ID ...] [--png FILE]

Per HRU (default: up to six HRUs with the largest exchange): water table and soil water level against the soil-zone
base and the land surface, connected fraction, exchange up and down, rejected recharge and overflow. Below, the
model-wide totals of GWBudget.csv and the interface updates per step. Use it to inspect the dynamics of a case: the
soil level should follow the water table once connected, the exchange should change sign only at physical turning
points, and rejection should start when the water table reaches the base.
"""
import os, sys
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    out = argv[1]
    png = None
    if '--png' in argv:
        png = argv[argv.index('--png') + 1]
        argv = argv[:argv.index('--png')] + argv[argv.index('--png') + 2:]
    s = pd.read_csv(os.path.join(out, 'GWSoilExchange.csv'))
    b = pd.read_csv(os.path.join(out, 'GWBudget.csv'))
    hrus = [int(x) for x in argv[2:]]
    if not hrus:
        g = s.groupby('HRU_ID')[['soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]']].sum().sum(axis=1)
        hrus = list(g.sort_values(ascending=False).index[:6])
    n = len(hrus)
    fig, ax = plt.subplots(n + 2, 2, figsize=(12, 2.6 * (n + 2)), squeeze=False)
    for r, k in enumerate(hrus):
        x = s[s['HRU_ID'] == k]
        t = x['time [d]']
        a = ax[r][0]
        zb = x['soil-zone base [m]']
        a.plot(t, x['water table [m]'], label='water table')
        a.plot(t, x['soil water level [m]'], label='soil water level')
        a.plot(t, zb, 'k--', lw=0.8, label='soil-zone base')
        a.set_title('HRU %d: levels' % k, fontsize=9); a.legend(fontsize=7); a.set_ylabel('m')
        a = ax[r][1]
        a.plot(t, x['aquifer to soil zone [m3/d]'], label='aquifer to soil')
        a.plot(t, -x['soil zone to aquifer [m3/d]'], label='soil to aquifer (neg.)')
        a2 = a.twinx(); a2.plot(t, x['saturated fraction [-]'], 'k:', lw=0.8, label='F'); a2.set_ylim(-0.05, 1.05)
        a.set_title('HRU %d: exchange [m3/d], connected fraction (dotted)' % k, fontsize=9); a.legend(fontsize=7)
    a = ax[n][0]
    a.plot(b['time [d]'], b['aquifer to soil zone [m3/d]'], label='aquifer to soil')
    a.plot(b['time [d]'], -b['soil zone to aquifer [m3/d]'], label='soil to aquifer (neg.)')
    a.set_title('all HRUs: exchange [m3/d]', fontsize=9); a.legend(fontsize=7)
    a = ax[n][1]
    a.plot(b['time [d]'], b['rejected recharge [m3]'], label='rejected recharge')
    a.plot(b['time [d]'], b['soil-zone overflow [m3]'], label='soil-zone overflow')
    a.set_title('all HRUs: rejected recharge and overflow [m3 per step]', fontsize=9); a.legend(fontsize=7)
    a = ax[n + 1][0]
    a.plot(b['time [d]'], b['interface updates'], '.', ms=3)
    a.set_title('interface updates per step', fontsize=9)
    a = ax[n + 1][1]
    nc = b['interface converged'] == 0
    a.plot(b['time [d]'], b['interface change [m]'], '.', ms=3, label='last change')
    if nc.any():
        a.plot(b['time [d]'][nc], b['interface change [m]'][nc], 'rx', label='not converged')
    a.set_yscale('symlog', linthresh=1e-8); a.legend(fontsize=7)
    a.set_title('interface: last change of the soil level [m]', fontsize=9)
    fig.tight_layout()
    png = png or os.path.join(out, 'soilzone.png')
    fig.savefig(png, dpi=110)
    print('wrote', png)


if __name__ == '__main__':
    main(sys.argv)
