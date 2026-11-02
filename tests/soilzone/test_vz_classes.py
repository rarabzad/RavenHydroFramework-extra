"""Depth classes of the unsaturated columns (:SoilZoneVadoseClasses K; design note soil_zone_depth_classes.md).

Every exchange column (HRU-cell link) gets up to K unsaturated columns, one per depth class of its DEM samples (least-
spread grouping of the samples' soil-zone bases); class c has the area share a_c = n_c/N, starts at its class's mean base
and takes the unsaturated share a_c (1 - F_c) of the link's recharge. The test cases are synthetic strips (sz_models) with
irregular land (dem_fn: hummocks, terraces) over a generated MODFLOW model.

C1  K = 1 byte-identical to the reference build (RAVEN_EXE_REF; every out/*.csv and solution.rvc, the diagnostic column
    'interface change [m]' left out) for RICHARDS and NONE on a planar and a hummocky case; without a reference build
    SKIP, and K = 1 given explicitly vs the default only.
C2  hummocky cell whose mean soil-zone base is near the water table while the hummocks are well above it: with K = 1 the
    hummocks' recharge reaches MODFLOW in the step (no column), with K = 3 and 5 it is delayed (recharge centroid later).
C3  convergence: the result approaches a reference in which the depth classes are modelled separately (one HRU per
    terrace, each with flat land, K = 1) as K grows: terraces (2 levels), squares (4 levels), a deep case.
C4  capillary rise from the class columns (RICHARDS, K = 4, PET): rise > 0, identities below 1e-9.
C5  rising and falling water tables through several class columns at once (the shared source-cell limits): identities.
C6  a dried thin top cell (the water table in the cell below: SZW_RAVEN path) and a specified-head toe with K = 3.
    Hotstart: K = 3, 20 + 20 days vs 40 days (:GWVadoseClassColumns); a K = 1 hotstart read with K = 3 and a K = 3 one
    read with K = 1: no crash, the mismatch warning, identities.
C7  cost of K = 1, 3, 5 (timings machine-dependent).
C8  identities below 1e-9 for KINEMATIC and LAG with K = 3 (the column machinery does not depend on the method).
C9  band_e43 LAG K = 3 connection test: belongs to the interface iteration (GWSoilZoneModel.cpp), SKIP here.
All runs: the standard limits of sz_check (STD_LIMITS) plus vz_identity 1e-8.
Quick mode (RAVEN_TEST_QUICK=1): shorter runs, C3 only terraces at K = 1, 2, 4, C7 shorter.
"""
import os, sys, shutil, math, time, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check

tc = sz_check.tc
W = tc.work('soilzone', 'vz_classes')
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')
REF = os.environ.get('RAVEN_EXE_REF', '') or os.environ.get('RAVEN_REF_EXE', '')
LIM = dict(sz_check.STD_LIMITS); LIM['vz_identity'] = 1e-8
LIM9 = dict(LIM); LIM9.update({'rch_identity': 1e-9, 'sz_identity': 1e-9, 'vz_identity': 1e-9})
DIAG = ('interface change [m]',)
RESULTS = {}

def vz(method='RICHARDS', K=None, extra=''):
    s = ':SoilZoneVadose %s\n' % method
    if K is not None:
        s += ':SoilZoneVadoseClasses %d\n' % K
    return s + extra

def hummocks(amp, lam=100.0):
    """egg-crate relief +-amp [m] with wavelength lam [m]: a hummock and a hollow in every 100 m cell"""
    return lambda x, y: amp * math.sin(2 * math.pi * (x + 0.25 * lam) / lam) * math.sin(2 * math.pi * (y + 0.25 * lam) / lam)

BASE = dict(nhru=1, hru_w=200.0, width=200.0, cell=100.0, subgrid=5, perc=50.0, ksat=500.0, Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3,
            smooth=0.2, aq_thick=20.0, dem_res=400)

def case(name, exe=None, rvc=None, start=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read()
            open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    t0 = time.time()
    if exe:
        import subprocess
        r = subprocess.run([exe, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=3600)
        ok, txt = ('Successful Simulation' in r.stdout + r.stderr), r.stdout + r.stderr
    else:
        ok, txt = sz_check.run(d)
    RESULTS[name] = time.time() - t0
    if not ok:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:]))
        return None
    return d

def check(name, d, lim=LIM, dt=1.0):
    if d is None:
        return False
    r = sz_check.checks(d, dt=dt)
    print('  %s:' % name)
    return sz_check.report(name, r, {k: v for k, v in lim.items() if k in r})

def budget(d):
    return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))

def warnings(d):
    f = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(f).read() if os.path.exists(f) else ''

def same_outputs(a, b):
    """every out/*.csv and solution.rvc identical (the diagnostic column left out); returns the list of differing files"""
    bad = []
    fa = sorted(os.path.basename(f) for f in glob.glob(os.path.join(a, 'out', '*.csv'))) + ['solution.rvc']
    for f in fa:
        pa, pb = os.path.join(a, 'out', f), os.path.join(b, 'out', f)
        if not os.path.exists(pb):
            bad.append(f + ' (missing)'); continue
        if f.endswith('.csv'):
            A, B = pd.read_csv(pa, dtype=str), pd.read_csv(pb, dtype=str)
            A = A.drop(columns=[c for c in DIAG if c in A]); B = B.drop(columns=[c for c in DIAG if c in B])
            if list(A.columns) != list(B.columns) or not A.equals(B):
                bad.append(f)
        elif open(pa).read() != open(pb).read():
            bad.append(f)
    return bad

def centroid(d, col='MF6 recharge [m3/d]'):
    m = budget(d)[col].values; t = np.arange(1, len(m) + 1)
    return (m * t).sum() / max(m.sum(), 1e-30)

# --------------------------------------------------------------------------------------------------------------------
def c1():
    print('C1 K = 1 byte-identical')
    rain = [0.0] * 5 + [30.0] * 3 + [0.0] * (12 if QUICK else 32)
    cases = [('plan', dict(BASE, init_depth=4.0, rain=rain, days=len(rain))),
             ('hum', dict(BASE, init_depth=1.6, rain=rain, days=len(rain), dem_fn=hummocks(1.0)))]
    ok = True
    for nm, cfg in cases:
        for meth in ('RICHARDS', 'NONE'):
            a = case('c1_%s_%s' % (nm, meth), extra_rvg=vz(meth), **cfg)
            b = case('c1_%s_%s_k1' % (nm, meth), extra_rvg=vz(meth, 1), **cfg)
            ok &= check('c1_%s_%s' % (nm, meth), a)
            if a and b:
                bad = same_outputs(a, b); ok &= not bad
                print('    K = 1 given vs default: %s' % ('identical' if not bad else 'DIFFER ' + ', '.join(bad)))
            if REF and os.path.exists(REF):
                r = case('c1_%s_%s_ref' % (nm, meth), exe=REF, extra_rvg=vz(meth), **cfg)
                if a and r:
                    bad = same_outputs(a, r); ok &= not bad
                    print('    vs reference build: %s' % ('identical' if not bad else 'DIFFER ' + ', '.join(bad)))
                else:
                    ok = False
            else:
                tc.skip('C1 %s %s vs reference build' % (nm, meth), 'RAVEN_EXE_REF not set')
    print('C1 %s' % ('ok' if ok else 'FAIL'))
    return ok

TESTS = [('C1', c1)]

def main():
    tc.need_mf6()
    only = [a for a in sys.argv[1:]]
    res = {}
    for n, f in TESTS:
        if only and n not in only:
            continue
        res[n] = f()
    print('results: ' + ', '.join('%s %s' % (k, 'ok' if v else 'FAIL') for k, v in res.items()))
    good = all(res.values())
    print('vz classes tests: ALL PASSED' if good else 'vz classes tests: FAILED')
    return 0 if good else 1

if __name__ == '__main__':
    sys.exit(main())
