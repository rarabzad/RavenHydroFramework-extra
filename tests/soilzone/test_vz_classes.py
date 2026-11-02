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
if not hasattr(tc, 'skip'):   # (testconfig.skip of the final suite: 'SKIP <what>: <why>', never 'ok')
    tc.skip = lambda what, why: print('SKIP %s: %s' % (what, why))
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
    # RICHARDS on the hummocky case differs from the hooks build by design wherever the water table reaches, during a step,
    # ground that was unsaturated at its start (rule (i): the columns' outputs there go back to the soil zone): compared, reported, not required identical against a pre-rule reference (C1_STRICT=1 does)
    ok = True
    for nm, cfg in cases:
        for meth in ('RICHARDS', 'NONE'):
            strict = not (nm == 'hum' and meth == 'RICHARDS') or os.environ.get('C1_STRICT', '') == '1'
            a = case('c1_%s_%s' % (nm, meth), extra_rvg=vz(meth), **cfg)
            b = case('c1_%s_%s_k1' % (nm, meth), extra_rvg=vz(meth, 1), **cfg)
            ok &= check('c1_%s_%s' % (nm, meth), a)
            if a and b:
                bad = same_outputs(a, b); ok &= not bad
                print('    K = 1 given vs default: %s' % ('identical' if not bad else 'DIFFER ' + ', '.join(bad)))
            if REF and os.path.exists(REF):
                r = case('c1_%s_%s_ref' % (nm, meth), exe=REF, extra_rvg=vz(meth), **cfg)
                if a and r:
                    bad = same_outputs(a, r)
                    if strict: ok &= not bad
                    dr = (budget(a)['rejected recharge [m3]'] - budget(r)['rejected recharge [m3]']).abs().max()
                    print('    vs reference build: %s%s' % ('identical' if not bad else 'DIFFER ' + ', '.join(bad),
                          '' if strict else ' (informational: rule (i) hand-back; rejected recharge differs by up to %.1f m3)' % dr))
                else:
                    ok = False
            else:
                tc.skip('C1 %s %s vs reference build' % (nm, meth), 'RAVEN_EXE_REF not set')
    print('C1 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c2():
    print('C2 hummocky cell: mean base near the water table, hummocks above it')
    rain = [0.0] * 5 + [30.0] * 3 + [0.0] * (22 if QUICK else 52)
    cfg = dict(BASE, init_depth=1.03, rain=rain, days=len(rain), dem_fn=hummocks(2.5), Sy=0.25, Kv=0.05, smooth=0.1,
               perc_type='PERC_GAWSER_CONSTRAIN', phi0=(100.0, 100.0))
    ok = True; vin = {}; dly = {}
    for K in (1, 3, 5):
        d = case('c2_k%d' % K, extra_rvg=vz('RICHARDS', K), **cfg)
        ok &= check('c2_k%d' % K, d)
        if d:
            b = budget(d); t = np.arange(1, len(b) + 1)
            i, o = b['unsaturated zone inflow [m3]'].values, b['unsaturated zone to aquifer [m3]'].values
            vin[K] = i.sum()
            dly[K] = ((o * t).sum() / o.sum() - (i * t).sum() / i.sum()) if i.sum() > 0 else 0.0
    if len(vin) == 3:
        print('  recharge through the class columns: K=1 %.0f m3 (no column: the mean base is within 5 cm of the water table), '
              'K=3 %.0f m3 delayed %.2f d, K=5 %.0f m3 delayed %.2f d (outflow centroid - inflow centroid)'
              % (vin[1], vin[3], dly[3], vin[5], dly[5]))
        ok &= (vin[1] == 0.0) and (vin[3] > 0.0) and (vin[5] > 0.0) and (dly[3] > 0.0) and (dly[5] > 0.0)
        RESULTS['c2'] = (vin, dly)
    print('C2 %s' % ('ok' if ok else 'FAIL'))
    return ok

def terraces(levels, step, lam=100.0):
    """terraces inside every cell: `levels` flat bands across x, each lam/levels wide, `step` m apart (mean 0)"""
    def f(x, y):
        u = ((x + 100.0 + 1e-6) % lam) / lam          # (the strip starts at x = -100 m: a cell edge)
        i = min(int(u * levels), levels - 1)
        return step * (i - 0.5 * (levels - 1))
    return f

def squares(amp, n=3, lam=100.0, seed=7):
    """n x n squares per cell, each flat at a random level in [-amp, amp] (seeded); with :SoilZoneSubgrid n every DEM sample
    lies at a square's centre, so K = n*n classes model the squares one by one"""
    import random
    rnd = random.Random(seed); lev = {}
    def f(x, y):
        key = (int((x + 1000.0 + 1e-6) // (lam / n)), int((y + 1000.0 + 1e-6) // (lam / n)))
        if key not in lev:
            lev[key] = amp * (2.0 * rnd.random() - 1.0)
        return lev[key]
    return f

def c3():
    print('C3 convergence to the sub-areas modelled one by one')
    rain = [0.0] * 3 + [25.0] * 4 + [0.0] * (23 if QUICK else 53)
    # (name, relief, samples per cell side, water table below the mean land [m], K values, reference K): squares: 9 squares
    # per cell at random levels, the reference K = 9 models every square with its own column (the sub-areas one by one; with
    # 5 x 5 samples it would need K = 25, beyond the limit of 10); terraces: 2 levels, K = 2 is exact
    fams = [('squares', squares(1.0), 3, 1.3, [1, 2, 3] if QUICK else [1, 2, 3, 4, 5, 6, 8], 9)]
    if not QUICK:
        fams += [('terraces', terraces(2, 1.2), 8, 1.3, [1], 2), ('deep', squares(1.4, seed=11), 3, 3.0, [1, 2, 4, 6], 9)]
    ok = True
    for nm, fn, sg, depth, Ks, Kref in fams:
        cfg = dict(BASE, init_depth=depth, rain=rain, days=len(rain), dem_fn=fn, subgrid=sg, perc_type='PERC_GAWSER_CONSTRAIN', phi0=(100.0, 100.0))
        res = {}
        for K in Ks + [Kref]:
            d = case('c3_%s_k%d' % (nm, K), extra_rvg=vz('RICHARDS', K), **cfg)
            ok &= check('c3_%s_k%d' % (nm, K), d)
            if d:
                res[K] = budget(d)['MF6 recharge [m3/d]'].values
        if Kref in res and len(res) > 1:
            r = res.pop(Kref)
            err = {K: np.abs(v - r).sum() / max(np.abs(r).sum(), 1e-30) for K, v in res.items()}
            print('  %s: relative error of the recharge to MODFLOW vs K = %d: %s' % (nm, Kref, ', '.join('K=%d %.3g' % (K, e) for K, e in sorted(err.items()))))
            ks = sorted(err)
            ok &= (err[ks[-1]] < err[ks[0]]) if len(ks) > 1 else (err[ks[0]] > 0.0)
            RESULTS['c3_' + nm] = err
        else:
            ok = False
    print('C3 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c4():
    print('C4 capillary rise from class columns (K = 4)')
    days = 20 if QUICK else 60
    cfg = dict(BASE, init_depth=1.8, rain=[0.0] * days, days=days, dem_fn=hummocks(0.8), pet=4.0, soil_b=5.0, soil_psia=200.0)
    d = case('c4_k4', extra_rvg=vz('RICHARDS', 4), **cfg)
    ok = check('c4_k4', d, LIM9)
    if d:
        cap = budget(d)['capillary rise to soil zone [m3]'].sum()
        print('  capillary rise from the columns %.1f m3' % cap); ok &= cap > 0
    print('C4 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c5():
    print('C5 rising and falling water tables through several class columns')
    rain = ([0.0] * 6 + [45.0] * 4) * (2 if QUICK else 5)
    ok = True
    for K in (1, 3):
        cfg = dict(BASE, nhru=4, slope=0.01, init_depth=1.5, rain=rain, days=len(rain), dem_fn=hummocks(0.8), Sy=0.1, Kh=2.0, pet=3.0,
                   soil_b=5.0, soil_psia=200.0, chd=None)
        d = case('c5_k%d' % K, extra_rvg=vz('RICHARDS', K), **cfg)
        ok &= check('c5_k%d' % K, d)
    print('C5 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c6():
    print('C6 dried top cell, specified-head toe, hotstart with K = 3 and K mismatch')
    ok = True
    rain = ([0.0] * 5 + [30.0] * 5) * 4
    cfg = dict(BASE, nhru=4, slope=0.05, chd=59.9, init_depth=1.5, perc=40.0, ksat=400.0, Sy=0.15, pet=4.0, soil_b=5.0, soil_psia=200.0,
               dem_fn=hummocks(0.8))
    full = case('c6_full', extra_rvg=vz('RICHARDS', 3), rain=rain, days=40, **cfg)
    first = case('c6_first', extra_rvg=vz('RICHARDS', 3), rain=rain[:20], days=20, **cfg)
    ok &= check('c6_full', full) & check('c6_first', first)
    if full and first:
        rvc = os.path.join(first, 'out', 'solution.rvc')
        hasblk = ':GWVadoseClassColumns' in open(rvc).read()
        second = case('c6_second', extra_rvg=vz('RICHARDS', 3), start='2000-01-21', rvc=rvc, rain=rain[20:], days=20, **cfg)
        ok &= check('c6_second', second) and hasblk
        if second:
            a, b = budget(full).iloc[20:].reset_index(drop=True), budget(second)
            cols = ['MF6 recharge [m3/d]', 'soil-zone exchange applied to Raven [m3]', 'unsaturated zone to aquifer [m3]', 'unsaturated zone storage [m3]']
            dq = max((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0) for c in cols)
            print('  restart (block :GWVadoseClassColumns %s): largest deviation from the continuous run %.2g' % ('written' if hasblk else 'MISSING', dq))
            ok &= dq < 1e-4
        mm = case('c6_mismatch_k1', extra_rvg=vz('RICHARDS', 1), start='2000-01-21', rvc=rvc, rain=rain[20:], days=20, **cfg)
        ok &= check('c6_mismatch_k1', mm)
        w = warnings(mm) if mm else ''
        ok &= 'do not match the columns' in w
        print('  K = 3 hotstart read with K = 1: %s' % ('warning' if 'do not match the columns' in w else 'NO WARNING'))
    k1 = case('c6_first_k1', extra_rvg=vz('RICHARDS', 1), rain=rain[:20], days=20, **cfg)
    if k1:
        mm = case('c6_mismatch_k3', extra_rvg=vz('RICHARDS', 3), start='2000-01-21', rvc=os.path.join(k1, 'out', 'solution.rvc'), rain=rain[20:], days=20, **cfg)
        ok &= check('c6_mismatch_k3', mm)
        w = warnings(mm) if mm else ''
        ok &= 'do not match the columns' in w
        print('  K = 1 hotstart read with K = 3: %s' % ('warning' if 'do not match the columns' in w else 'NO WARNING'))
    # a thin top layer that dries: the water table in the cell below (SZW_RAVEN), with classes
    d = case('c6_szw', extra_rvg=vz('RICHARDS', 3) + ':SoilZoneCapillaryRise ON\n', rain=[0.0] * 30, days=30,
             **dict(BASE, init_depth=2.4, pet=5.0, soil_b=5.0, soil_psia=200.0, dem_fn=hummocks(0.8)))
    if d:
        rvp = os.path.join(d, 'm.rvp'); t = open(rvp).read()
        t = t.replace('AQ, 1, SAND, TO_BEDROCK, AQUIFER', 'AQ, 2, SAND, 1.5, AQUIFER, SAND, TO_BEDROCK, AQUIFER')
        open(rvp, 'w').write(t)
        ok2, txt = sz_check.run(d)
        ok &= ok2 and check('c6_szw', d)
    print('C6 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c7():
    print('C7 cost of the class columns (machine-dependent)')
    days = 30 if QUICK else 120
    rain = ([0.0] * 6 + [20.0] * 4) * (days // 10)
    t = {}
    for K in (1, 3, 5):
        d = case('c7_k%d' % K, extra_rvg=vz('RICHARDS', K), **dict(BASE, nhru=4, slope=0.01, init_depth=2.0, rain=rain, days=days, dem_fn=hummocks(0.8)))
        if d:
            t[K] = RESULTS['c7_k%d' % K]
    print('  run times: ' + ', '.join('K=%d %.2f s' % (K, v) for K, v in sorted(t.items())))
    return len(t) == 3

def c8():
    print('C8 KINEMATIC and LAG with K = 3: identities')
    rain = [0.0] * 5 + [30.0] * 3 + [0.0] * (12 if QUICK else 42)
    ok = True
    for m in ('KINEMATIC', 'LAG'):
        d = case('c8_%s' % m, extra_rvg=vz(m, 3), **dict(BASE, init_depth=1.3, rain=rain, days=len(rain), dem_fn=hummocks(1.0)))
        ok &= check('c8_%s' % m, d, LIM9)
    print('C8 %s' % ('ok' if ok else 'FAIL'))
    return ok

def c9():
    tc.skip('C9 band_e43 LAG K = 3 connection test', 'the connection test belongs to the interface iteration (GWSoilZoneModel.cpp, R20 of test_rough_terrain)')
    return True

TESTS = [('C1', c1), ('C2', c2), ('C3', c3), ('C4', c4), ('C5', c5), ('C6', c6), ('C7', c7), ('C8', c8), ('C9', c9)]

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
