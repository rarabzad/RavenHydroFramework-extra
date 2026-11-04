"""T1 / T1b (plan §9.2): flat closed column, water table rising into the soil zone (James Craig's first drawing).

T1 : S_y = drainable porosity n(1-SF)(1-S_fc) = 0.2; recharge 10 mm/d -> 50 mm/d rise below the base and inside the
     soil; heads and soil level agree once connected; soil full (400 mm) on day 41; the balances close.
T1b: S_y = 0.08 -> 125 mm/d below the base, 50 mm/d inside the soil, and a storage-consistency warning.
Full mode: 70 days each; quick mode (RAVEN_TEST_QUICK=1): 45 days each (the soil zone is full on day 41), same checks.
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'column')
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 45 if QUICK else 70
ok_all = True
for name, Sy, below in (('T1', 0.2, 50.0), ('T1b', 0.08, 125.0)):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, days=DAYS, Sy=Sy)
    ok, txt = sz_check.run(d)
    print('%s: S_y=%g: run %s' % (name, Sy, 'ok' if ok else 'FAILED'))
    if not ok:
        print(txt[-2000:]); ok_all = False; continue
    b, s, w = sz_check.outputs(d)
    res = sz_check.checks(d)
    wt = s['water table [m]'].values; hs = s['soil water level [m]'].values; F = s['saturated fraction [-]'].values
    zb = s['soil-zone base [m]'].values[0]
    dwt = np.diff(wt) * 1000
    pre = [i for i in range(1, len(wt) - 1) if wt[i + 1] < zb - 0.05]                 # below the base
    ins = [i for i in range(1, len(wt) - 1) if F[i] > 0.999 and hs[i + 1] < zb + 0.95]  # connected, soil not yet full
    res['rise_below_mm_d'] = float(np.median(dwt[pre])) if pre else float('nan')
    res['rise_in_soil_mm_d'] = float(np.median(np.diff(hs)[ins] * 1000)) if ins else float('nan')
    res['max_gap_connected_m'] = float(np.abs(wt - hs)[F > 0.999].max()) if (F > 0.999).any() else float('nan')
    full = np.where(s['soil-zone water [mm]'].values >= 399.99)[0]   # within 0.01 mm (the aquifer's elastic storage takes a little)
    res['day_full'] = int(s['time [d]'].values[full[0]]) if len(full) else -1
    warned = 'drainable porosity' in open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
    lim = dict(sz_check.STD_LIMITS)
    good = sz_check.report(name, res, lim)
    good &= abs(res['rise_below_mm_d'] - below) < 0.01 * below; print('  rise below the base %.3f mm/d (want %g)' % (res['rise_below_mm_d'], below))
    good &= abs(res['rise_in_soil_mm_d'] - 50.0) < 0.5; print('  rise inside the soil %.3f mm/d (want 50)' % res['rise_in_soil_mm_d'])
    good &= res['max_gap_connected_m'] < 0.005; print('  max |water table - soil level| once connected %.2e m (limit 5e-3)' % res['max_gap_connected_m'])
    if name == 'T1':
        good &= res['day_full'] in (40, 41, 42); print('  soil zone full on day %d (want ~41)' % res['day_full'])
        good &= not warned
    else:
        good &= warned; print('  storage-consistency warning given: %s' % warned)
    print('  %s: %s' % (name, 'PASS' if good else 'FAIL'))
    ok_all &= bool(good)
print('column tests: %s' % ('ALL PASSED' if ok_all else 'FAILED'))
sys.exit(0 if ok_all else 1)
