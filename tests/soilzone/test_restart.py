"""Restart (hotstart) of the soil-zone columns.

The T2/T3 hillslope runs 300 days in one go, and again as 150 days plus 150 days started from the first run's
solution.rvc (Raven's state, MODFLOW heads and the :GWSoilZoneColumns block). Both must give the same heads and
soil water on days 151-300 to 1e-6 relative, and the same flows to 1e-4 (within the interface's tolerances).
"""
import os, sys, shutil, re, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check
from test_hillslope import CFG, RAIN

W = sz_check.tc.work('soilzone', 'restart')
N1 = 150

def case(name, days, rain, start=None, rvc=None):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    cfg = dict(CFG); cfg.update(days=days, rain=rain)
    sz_models.make_case(d, **cfg)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read()
            open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    ok, txt = sz_check.run(d)
    if not ok:
        print('%s: run FAILED\n%s' % (name, txt[-2000:]))
    return d if ok else None

def main():
    full = case('full', len(RAIN), RAIN)
    first = case('first', N1, RAIN[:N1])
    if not (full and first):
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    has = ':GWSoilZoneColumns' in open(rvc).read()
    start = (datetime.date(2000, 1, 1) + datetime.timedelta(days=N1)).isoformat()
    second = case('second', len(RAIN) - N1, RAIN[N1:], start, rvc)
    if not second:
        return False
    cols = ['water table [m]', 'soil water level [m]', 'saturated fraction [-]', 'soil-zone water [mm]',
            'soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]', 'overflow [mm]', 'rejected recharge [mm]']
    a = pd.read_csv(os.path.join(full, 'out', 'GWSoilExchange.csv'))
    b = pd.read_csv(os.path.join(second, 'out', 'GWSoilExchange.csv'))
    m = a.merge(b, on=['date', 'HRU_ID'], suffixes=('_f', '_r'))
    dev = {c: float(((m[c + '_f'] - m[c + '_r']).abs() / (m[c + '_f'].abs() + 1.0)).max()) for c in cols}
    print('restart: :GWSoilZoneColumns in solution.rvc: %s; %d rows compared' % (has, len(m)))
    for c in cols:
        print('  %-30s max relative deviation %.2e' % (c, dev[c]))
    res = sz_check.checks(second)
    good = sz_check.report('restarted run', res, dict(sz_check.STD_LIMITS))
    # levels and water to 1e-6; flows (and F, rejection) to 1e-4: the interface converges to its tolerances (1e-4 m of
    # soil level, 1e-6 of the gross exchange), so a restart that perturbs the state at round-off moves each link's flow
    # within C x 1e-4 m
    flows = ('saturated fraction [-]', 'soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]', 'overflow [mm]', 'rejected recharge [mm]')
    good &= has and len(m) == (len(RAIN) - N1) * CFG['nhru'] and all(dev[c] < (1e-4 if c in flows else 1e-6) for c in cols)
    print('restart test: %s' % ('PASS' if good else 'FAIL'))
    return bool(good)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
