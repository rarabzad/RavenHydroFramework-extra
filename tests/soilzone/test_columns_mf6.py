"""Columns against MODFLOW's cells (manual "Drained columns").

M1  drained columns: a stiff, very low-storage hillslope drying under PET (S_y 0.001, K 5000 m/d) whose top cells dry in
    MODFLOW's iterates: KeepColumnsWet sets such columns 1 mm above their bottoms (NEWTON; columns whose active cells are all
    convertible); the run totals count it (more than 0), the run completes with finite heads and the identities hold.
M2  an unsaturated column under steady rain delivers its inflow to MODFLOW's top cell: over the last 30 days of 2 mm/d on a
    4 m deep water table, the columns' outflow to the aquifer is at least 0.9 of their inflow (qA) and MODFLOW's recharge at
    least 0.9 of it too (the column's water reaches MODFLOW's cell, not only its books).
M3  CONCEPTUAL runs are unchanged against the reference build (RAVEN_EXE_REF; SKIP without it), apart from GWBudget's
    "MF6 balance error [%]" (gross flow redefined) and the run log (solution.rvc the same state, testconfig.rvc_same).
M4  the check of M1 fails when the GWModelSummary.txt line is missing (kept_its returns None).
Quick mode (RAVEN_TEST_QUICK=1): M2 runs 75 days instead of 120 (the same check over its last 30 days).
"""
import os, sys, re, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd, numpy as np
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'columns_mf6')
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'

def kept_its(d):
    """outer iterations in which drained columns were kept wet (GWModelSummary.txt run totals); None when the line is missing"""
    m = re.search(r"drained columns\s*: kept 1 mm above their bottoms in MODFLOW's iterates in (\d+) outer iterations", sz_check.summary(d))
    return int(m.group(1)) if m else None

def case(name, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **cfg)
    ok, txt = sz_check.run(d)
    if not ok: print('  %s: run FAILED\n%s' % (name, txt[-700:]))
    return d, ok

def m1():
    print('M1 drained columns kept 1 mm wet in MODFLOW\'s iterates')
    d, ok = case('m1_dry', nhru=5, hru_w=200.0, slope=0.05, rain=[0.0] * 15 + [150.0] + [0.0] * 4 + [150.0] + [0.0] * 9, days=30, pet=8.0,
                 init_depth=0.0, phi0=(10.0, 10.0), Kv=5000.0, Kh=1000.0, Sy=0.001)
    if not ok: return False
    k = kept_its(d); h = pd.read_csv(os.path.join(d, 'out', 'GWHRUState.csv'))
    fin = bool(np.isfinite(h[[c for c in h.columns if c.startswith("head_")]].values.astype(float)).all())
    r = sz_check.checks(d)
    g = (k is not None) and k > 0 and fin
    print('  M1: kept wet in %s outer iterations, heads finite %s -> %s' % (k, fin, 'ok' if g else 'FAIL'))
    return g & sz_check.report('m1', r, {x: v for x, v in sz_check.ID_LIMITS.items() if x in r})

def m2():
    print('M2 an unsaturated column delivers its inflow to MODFLOW')
    d, ok = case('m2_richards', nhru=1, hru_w=200.0, rain=2.0, days=75 if QUICK else 120, perc=2.0, init_depth=4.0, aq_b=4.0, aq_psia=0.3, Kv=1.0,
                 extra_rvg=':SoilZoneVadose RICHARDS\n')
    if not ok: return False
    b = sz_check.outputs(d)[0].iloc[-30:]
    qA = b['unsaturated zone inflow [m3]'].sum(); qo = b['unsaturated zone to aquifer [m3]'].sum(); mr = b['MF6 recharge [m3/d]'].sum()
    g = qA > 0 and qo >= 0.9 * qA and mr >= 0.9 * qA
    print('  M2: last 30 days: column inflow %.1f m3, outflow %.1f m3, MF6 recharge %.1f m3 -> %s' % (qA, qo, mr, 'ok' if g else 'FAIL'))
    r = sz_check.checks(d)
    return g & sz_check.report('m2', r, {x: v for x, v in sz_check.ID_LIMITS.items() if x in r})

def m3():
    print('M3 CONCEPTUAL against the reference build')
    if not sz_check.tc.REF or not os.path.exists(sz_check.tc.REF):
        sz_check.tc.skip('M3', 'RAVEN_EXE_REF not set'); return True
    a, ok = case('m3_conc', nhru=5, hru_w=200.0, slope=0.02, rain=5.0, days=20, physical=False)
    if not ok: return False
    b = os.path.join(W, 'm3_conc_ref'); shutil.rmtree(b, ignore_errors=True); shutil.copytree(a, b, ignore=shutil.ignore_patterns('out'))
    subprocess.run([sz_check.tc.REF, 'm', '-o', 'out/'], cwd=b, capture_output=True, env=sz_check.tc.ENV)
    bad = sz_check.same_outputs(a, b, skip=('MF6 balance error [%]',))
    print('  M3: files that differ (balance-error percentage left out): %s -> %s' % (bad or 'none', 'ok' if not bad else 'FAIL'))
    return not bad

def m4():
    print('M4 the drained-column check fails without the summary line')
    d = os.path.join(W, 'm4_fake', 'out'); os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'GWModelSummary.txt'), 'w').write('Run totals (end of run)\n  time steps : 3\n')
    g = kept_its(os.path.dirname(d)) is None
    print('  M4: kept_its without the line: %s -> %s' % (kept_its(os.path.dirname(d)), 'ok' if g else 'FAIL'))
    return g

if __name__ == '__main__':
    names = [a.lower() for a in sys.argv[1:]] or ['m1', 'm2', 'm3', 'm4']
    ok = all([globals()[n]() for n in names])
    print('columns and MODFLOW side: %s' % ('ALL PASSED' if ok else 'FAILED'))
    sys.exit(0 if ok else 1)
