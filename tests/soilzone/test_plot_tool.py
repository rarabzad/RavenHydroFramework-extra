"""tools/plot_soilzone.py with soil-zone columns over specified heads (no MODFLOW run).

    python3 soilzone/test_plot_tool.py

Output files written here with the column names of GWSoilExchange.csv and GWBudget.csv: seven HRUs exchange with the
aquifer (10 to 70 m3/d), and HRU 8 lies wholly over specified heads, so its exchange (1,000 m3/d up) is only in the
columns "specified heads to soil zone" / "soil zone to specified heads".
P1 the default choice of HRUs (largest exchange) puts HRU 8 first;
P2 HRU 8's exchange panel and the model-wide exchange panel draw the specified-head exchange (lines "specified heads to
   soil" and "soil to specified heads (neg.)"), and the model-wide upward lines add up to GWBudget.csv's total;
P3 output without those columns (CONCEPTUAL-only specified heads) still plots, with the aquifer exchange only.
The same in both modes (RAVEN_TEST_QUICK has no effect: the check takes a second).
"""
import os, sys, shutil
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import testconfig as tc   # noqa: E402
sys.path.insert(0, os.path.join(tc.REPO, 'tools'))
import plot_soilzone as ps   # noqa: E402

W = os.path.dirname(tc.work('plot_tool', 'x'))
CHD_DOWN, CHD_UP = 'soil zone to specified heads [m3/d]', 'specified heads to soil zone [m3/d]'
fails = 0


def report(name, ok, detail=''):
    global fails
    print('%-70s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def write(d, chd):
    shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    t = np.arange(1.0, 11.0); rows = []
    for k in range(1, 9):
        up = 0.0 if k == 8 else 10.0 * k
        for ti in t:
            r = {'time [d]': ti, 'HRU_ID': k, 'soil-zone base [m]': 99.0, 'water table [m]': 99.5 if k == 8 else 98.5,
                 'soil water level [m]': 99.5 if k == 8 else 99.0, 'saturated fraction [-]': 1.0 if k == 8 else 0.0,
                 'soil zone to aquifer [m3/d]': 0.0, 'aquifer to soil zone [m3/d]': up}
            if chd:
                r[CHD_DOWN] = 0.0; r[CHD_UP] = 1000.0 if k == 8 else 0.0
            rows.append(r)
    s = pd.DataFrame(rows); s.to_csv(os.path.join(d, 'GWSoilExchange.csv'), index=False)
    b = s.groupby('time [d]')[['soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]'] + ([CHD_DOWN, CHD_UP] if chd else [])].sum().reset_index()
    b['rejected recharge [m3]'] = 0.0; b['soil-zone overflow [m3]'] = 0.0
    b['interface updates'] = 2; b['interface converged'] = 1; b['interface change [m]'] = 1e-6
    b.to_csv(os.path.join(d, 'GWBudget.csv'), index=False)
    return b


def labels(ax):
    return [l.get_label() for l in ax.get_lines()]


d = os.path.join(W, 'with_chd'); b = write(d, True)
def plot(d):
    """runs the tool; the HRUs drawn are read from the panel titles ('HRU k: levels')"""
    import re
    import matplotlib.pyplot as plt
    plt.close('all')
    ps.main(['plot_soilzone.py', d, '--png', os.path.join(d, 'p.png')])
    fig = plt.gcf()
    hrus = [int(m.group(1)) for a in fig.axes for m in [re.match(r'HRU (\d+): levels', a.get_title())] if m]
    return hrus, fig


try:
    hrus, fig = plot(d)
except Exception as e:   # (a tool that fails on the columns)
    hrus, fig = None, None
    report('plot_soilzone.py runs', False, repr(e)[:120])
if fig is not None:
    report('P1 HRU 8 (exchange only with specified heads) is chosen first', len(hrus) > 0 and hrus[0] == 8, 'HRUs %s' % hrus)
    ax = fig.axes
    i8 = hrus.index(8) if 8 in hrus else -1
    l8 = labels(ax[2 * i8 + 1]) if i8 >= 0 else []
    n = len(hrus); lw = labels(ax[2 * n])
    report('P2 HRU 8 panel draws the specified-head exchange', 'specified heads to soil' in l8 and 'soil to specified heads (neg.)' in l8, ', '.join(l8))
    lines = {l.get_label(): l.get_ydata() for l in ax[2 * n].get_lines()}
    tot = lines.get('aquifer to soil', 0) + lines.get('specified heads to soil', 0)
    want = (b['aquifer to soil zone [m3/d]'] + b[CHD_UP]).values
    report('P2 model-wide panel: upward lines add up to the total (aquifer + specified heads)', 'specified heads to soil' in lw and np.allclose(tot, want),
           ', '.join(lw))
d = os.path.join(W, 'without_chd'); write(d, False)
try:
    hrus, fig = plot(d)
    report('P3 output without the specified-head columns plots (aquifer exchange only)', 8 not in hrus[:1] and 'specified heads to soil' not in labels(fig.axes[1]),
           'HRUs %s' % hrus)
except Exception as e:
    report('P3 output without the specified-head columns plots', False, repr(e)[:120])
shutil.rmtree(W, ignore_errors=True)
print('plot tool tests: ALL PASSED' if fails == 0 else 'plot tool tests: %d FAILED' % fails)
sys.exit(1 if fails else 0)
