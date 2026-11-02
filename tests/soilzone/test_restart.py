"""Restart (hotstart) of the soil-zone columns.

The T2/T3 hillslope runs 300 days in one go, and again as 150 days plus 150 days started from the first run's
solution.rvc (Raven's state, MODFLOW heads and the :GWSoilZoneColumns block). Both must give the same heads and
soil water on days 151-300 to 1e-6 relative, and the same flows to 1e-4 (within the interface's tolerances).

R2: the same for an existing model (the x3-style hillslope with a specified-head toe and unsaturated
columns) run 10 days in one go and as 5 + 5 days. The restart's first step must not apply the specified-head links'
exact exchange of the last step as a lagged source (the existing model's specified heads are known only once MODFLOW has
read the step's period data, after the lagged source): the hotstart writes 0 for those links.
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

def ext_restart(N=10, N1=5):
    """R2: an existing model with specified-head top cells, continuous vs restarted"""
    cfg = dict(CFG); cfg.update(days=N, rain=RAIN[:N], subgrid=5, smooth=0.2, chd=94.8, aq_b=4.0, aq_psia=0.3, init_depth=3.0, pet=2.0)
    cfg['extra_rvg'] = ':SoilZoneVadose RICHARDS\n:SoilZoneAquiferClass SAND\n'
    g = os.path.join(W, 'r2_gen'); shutil.rmtree(g, ignore_errors=True); sz_models.make_case(g, **cfg)
    ok, txt = sz_check.run(g)
    if not ok:
        print('R2: generated run FAILED\n%s' % txt[-1500:]); return False
    m = os.path.join(W, 'r2_model'); shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in ('gwf.rch', 'gwf.drn', 'gwf.szx', 'gwf.szq', 'gwf.szd', 'gwf.szw', 'linkage.cache', 'mfsim.lst', 'gwf.lst', 'gwf.hds', 'gwf.cbc'):
        if os.path.exists(os.path.join(m, f)): os.remove(os.path.join(m, f))
    nam = open(os.path.join(m, 'gwf.nam')).read()
    open(os.path.join(m, 'gwf.nam'), 'w').write('\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN', l)))
    def ext(name, days, rain, start=None, rvc=None):
        e = os.path.join(W, 'r2_' + name); shutil.rmtree(e, ignore_errors=True)
        c = dict(cfg); c.update(days=days, rain=rain); sz_models.make_case(e, **c)
        shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
        rvg = open(os.path.join(e, 'm.rvg')).read()
        rvg = '\n'.join(l for l in rvg.split('\n') if not l.startswith((':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary')))
        rvg += '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m
        open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
        if start:
            for f in ('m.rvi', 'm.rvt'):
                p = os.path.join(e, f); t = open(p).read(); open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
        if rvc: shutil.copy(rvc, os.path.join(e, 'm.rvc'))
        ok, txt = sz_check.run(e)
        if not ok:
            print('R2 %s: run FAILED\n%s' % (name, txt[-1500:]))
        return e if ok else None
    full = ext('full', N, RAIN[:N]); first = ext('first', N1, RAIN[:N1])
    if not (full and first):
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    lag = re.search(r':GWSoilZoneLag[^\n]*\n([\s\S]*?):EndGWSoilZoneLag', open(rvc).read())
    start = (datetime.date(2000, 1, 1) + datetime.timedelta(days=N1)).isoformat()
    sec = ext('second', N - N1, RAIN[N1:N], start, rvc)
    if not (sec and lag):
        return False
    # (time [d] counts from each run's start; the restart's first step books the hotstart's columns brought to Raven's
    # state, written to 15 digits, as layer redistribution: a round-off volume, checked below 1e-3 m3)
    SKIP = ('time [d]', 'soil-zone layer redistribution [m3]')
    red = float(pd.read_csv(os.path.join(sec, 'out', 'GWBudget.csv'))['soil-zone layer redistribution [m3]'].abs().max())
    good = red < 1e-3
    print('  R2 restarted run: largest layer redistribution %.2e m3 -> %s' % (red, 'ok' if good else 'FAIL'))
    for f, key in (('GWSoilExchange.csv', ['date', 'HRU_ID']), ('GWBudget.csv', ['date'])):
        a = pd.read_csv(os.path.join(full, 'out', f)); b = pd.read_csv(os.path.join(sec, 'out', f))
        mm = a.merge(b, on=key, suffixes=('_f', '_r'))
        dev = 0.0; worst = ''
        for c in a.columns:
            if c in key or c in SKIP or c + '_r' not in mm or not np.issubdtype(mm[c + '_f'].dtype, np.number): continue
            d = float(((mm[c + '_f'] - mm[c + '_r']).abs() / (mm[c + '_f'].abs() + 1.0)).max())
            if d > dev: dev, worst = d, c
        ok = len(mm) > 0 and dev < 1e-4
        print('  R2 %s: %d rows, largest relative deviation restarted vs continuous %.2e (%s) -> %s' % (f, len(mm), dev, worst, 'ok' if ok else 'FAIL'))
        good &= ok
    res = sz_check.checks(sec)
    good &= sz_check.report('R2 restarted run', res, {k: v for k, v in sz_check.ID_LIMITS.items() if k in res})
    print('R2 existing-model restart with specified heads: %s' % ('PASS' if good else 'FAIL'))
    return bool(good)

def main():
    r2 = ext_restart()
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
    return bool(good) and r2

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
