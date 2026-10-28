"""Soil zone with an existing MODFLOW 6 model (docs/design/soil_zone_columns_plan.md section 6), and columns over
specified heads (section 5).

X1  round trip: the T2/T3 hillslope run with :SoilZone PHYSICAL; its MODFLOW model (without Raven's packages) is then
    coupled as an existing model (:MF6Simulation) with the same soil zone. Flows agree within the interface
    tolerances (relative 1e-3), and every identity holds.
X2  the same with the existing model converted to feet and seconds (unit factors of heads, conductances and rates).
X4  a specified-head toe with capillary rise off.
X3  the same with a specified-head toe (columns over specified heads; in the existing model they become specified
    heads through its own CHD package), unsaturated columns (:SoilZoneAquiferClass) and three column classes.
"""
import os, sys, shutil, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check
from test_hillslope import CFG

W = sz_check.tc.work('soilzone', 'v2ext')
LIM = {'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 1e-6, 'sz_identity': 1e-8, 'shortfall': 1e-6, 'vz_identity': 1e-5}
COLS = ['MF6 recharge [m3/d]', 'soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]', 'rejected recharge [m3]',
        'soil-zone exchange applied to Raven [m3]', 'storage release [m3/d]']

def roundtrip(name, extra='', feet=False, **over):
    cfg = dict(CFG); cfg.update(over); cfg['extra_rvg'] = extra
    g = os.path.join(W, name + '_gen'); shutil.rmtree(g, ignore_errors=True); sz_models.make_case(g, **cfg)
    ok, txt = sz_check.run(g)
    if not ok:
        print('  %s: generated run FAILED\n%s' % (name, txt[-1500:])); return False
    m = os.path.join(W, name + '_model'); shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in ('gwf.rch', 'gwf.drn', 'gwf.szx', 'gwf.szq', 'gwf.szd', 'linkage.cache', 'mfsim.lst', 'gwf.lst', 'gwf.hds', 'gwf.cbc'):
        if os.path.exists(os.path.join(m, f)): os.remove(os.path.join(m, f))
    nam = open(os.path.join(m, 'gwf.nam')).read()
    open(os.path.join(m, 'gwf.nam'), 'w').write('\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN', l)))
    if feet:
        subprocess.run([sys.executable, os.path.join(HERE, 'mf6_to_feet.py'), m, m + '_ft'], check=True, capture_output=True); m = m + '_ft'
    e = os.path.join(W, name + '_ext'); shutil.rmtree(e, ignore_errors=True); sz_models.make_case(e, **cfg)
    shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
    rvg = open(os.path.join(e, 'm.rvg')).read()
    rvg = '\n'.join(l for l in rvg.split('\n') if not l.startswith((':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary')))
    rvg += '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m
    open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
    ok, txt = sz_check.run(e)
    if not ok:
        print('  %s: existing-model run FAILED\n%s' % (name, txt[-2500:])); return False
    good = True
    for d, lab in ((g, 'generated'), (e, 'existing')):
        r = sz_check.checks(d); print('  %s %s:' % (name, lab))
        good &= sz_check.report(lab, r, {k: v for k, v in LIM.items() if k in r})
    a, b = pd.read_csv(os.path.join(g, 'out', 'GWBudget.csv')), pd.read_csv(os.path.join(e, 'out', 'GWBudget.csv'))
    cols = COLS + ([c for c in ('soil zone to specified heads [m3/d]', 'specified heads to soil zone [m3/d]', 'unsaturated zone inflow [m3]') if c in a and c in b])
    worst = max((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0) for c in cols)
    ok2 = worst < 1e-3
    print('  %s: largest relative difference of the flows, generated vs existing model %.2e -> %s' % (name, worst, 'ok' if ok2 else 'FAIL'))
    return good and ok2

def main():
    res = [roundtrip('x1'),
           roundtrip('x2', feet=True),
           roundtrip('x3', ':SoilZoneVadose RICHARDS\n:SoilZoneAquiferClass SAND\n:SoilZoneClasses 3\n',
                     chd=94.8, aq_b=4.0, aq_psia=0.3, init_depth=3.0, soil_b=5.0, soil_psia=200.0, pet=2.0),
           roundtrip('x4', ':SoilZoneCapillaryRise OFF\n', chd=94.8)]   # (capillary arrays unsized with the rise off)
    print('soil-zone existing-model tests: %s' % ('ALL PASSED' if all(res) else 'FAILED (%d of %d)' % (res.count(False), len(res))))
    return all(res)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
