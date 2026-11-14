"""Tests of :SoilZoneVadose KINEMATIC (gravity-only kinematic wave in the unsaturated columns; manual section
sec:szvadosekw).

K1  unit tests (vadose_kw_unit.cpp against GWVadose.cpp and GWVadoseKW.cpp): mass balance to round-off over random
    fluxes, steps, materials and layering; contents within [ths - Sy, ths]; monotonicity; SPEC_YIELD 0 and POROSITY 0
    guards; the reference ths - Sy in Build/MoveBottom/RelStorage; the capped grid (N <= 18 unchanged); the steady start
    (InitSteadyKinematic, also backed up above a slower layer); analytical kinematic wave (front arrival at
    L (th_q - thr)/q, drainage tail) with grid refinement.
K2  the P1 storm (3 days of 40 mm/d over a water table 6 m deep): recharge centroid and peak with NONE, RICHARDS and
    KINEMATIC; KINEMATIC delays and spreads the recharge (centroid at least 3 days after NONE, peak lower).
K3  a water table rising through the column into the soil zone and falling again (P3): the column collapses and
    re-forms (`after`, part of ok).
K4  layered aquifer, 3 m of sand over clay (Kv 4 mm/d, Sy 0.05), water table 6 m below the soil-zone base in the clay,
    25 mm/d for 20 days: the columns cross the material boundary while the water table rises through the clay and the
    sand to the soil zone (the release across layers); KINEMATIC and RICHARDS (the RICHARDS run is counted, not
    informational); all identities.
K5  hotstart continuity: 60 + 60 days from solution.rvc (:GWVadoseColumns) equal 120 days in one go.
K6  existing-model round trip (test_sz_existing.roundtrip with KINEMATIC and :SoilZoneAquiferClass).
K7  speed: run times of NONE, RICHARDS and KINEMATIC on a hillslope over a deep water table; returns the runs' results, the times are reported only.
K8  byte-identity of NONE, RICHARDS and CONCEPTUAL against the reference build RAVEN_EXE_REF (out/*.csv without the
    diagnostic column `interface change [m]`; solution.rvc the same state, testconfig.rvc_same); SKIP without a reference.
Every run: the standard limits (sz_check.STD_LIMITS, and sz_check's column identity vz_identity 1e-8 from step 1: the
start storage of the columns in GWModelSummary.txt is required, vz_step1_missing).
K9  the leak check: the K2 storm with KINEMATIC passes, and the same outputs with a column leak of 1e-5 and of 1e-4 m3
    per step put into "unsaturated zone storage [m3]" (on the steps above 5,000 m3, 10 significant digits) fail
    the script's checks.
K10 the room left in the top cell: one flat HRU of 200 x 200 m, aquifer SPEC_YIELD 0.2 (POROSITY 0.3, b 4, air entry 0.3 m),
    Kv 0.1 m/d, the water table 1.6 m deep (0.6 m below the soil-zone base, the top cell's top), 90 mm/d for 4 days from a
    steady column (:SoilZoneVadoseInitialFlux 90): in step 2 the rise meets more mobile water than the room the top cell
    has left (1,208 m3 against Sy dh 3,592 m3), so the column is held back by that room, with the warning that names it
    ("than the room left in the top cell above the water table"); all identities.
K11 a column across two aquifer classes (SAND, SPEC_YIELD 0.25, over SILT, 0.05, the boundary 1 m below the 99 m base; the
    water table 2.4 m deep, 90 mm/d): a node straddling the boundary carries the sand's mobile water below it, so the
    release meets Sy dh (4,225 m3) before the room (6,575 m3), and the warning names Sy dh ("than MODFLOW stores for the
    rise (Sy dh)", with the note on aquifer classes), not the room; all identities.
K12 a vanishing column (one flat HRU, SPEC_YIELD 0.2, the water table 1.45 m deep, 90 mm/d then none): the water table rises
    to within 5 cm of the column's base in step 1, so in step 2 the column vanishes and releases at most the room the top
    cell has left (0.2 x 0.0007 m x 40,000 m2 = 5.6 m3; Sy dh would be 3,600 m3, more than the column holds); the rest of
    its water (3,543 m3) goes back to the soil zone as rejected recharge, as GWBudget.csv books it; no release warning (an
    expected event where the water table rises into the soil zone); all identities.
RAVEN_TEST_QUICK=1: shorter K7.
"""
import os, sys, re, shutil, subprocess, time, datetime, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check

tc = sz_check.tc
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
W = tc.work('soilzone', 'vz_kinematic')
LIM = dict(sz_check.STD_LIMITS); LIM['vz_identity'] = 1e-8; LIM['vz_step1_missing'] = 0
KW = ':SoilZoneVadose KINEMATIC\n'
RI = ':SoilZoneVadose RICHARDS\n'
REF = os.environ.get('RAVEN_EXE_REF', os.environ.get('RAVEN_REF_EXE', ''))
DIAG = ['interface change [m]']
TIMES = {}

def run(name, start=None, rvc=None, edit=None, exe=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read()
            open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    if edit:
        edit(d)
    t0 = time.time()
    if exe:
        r = subprocess.run([exe, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=3600)
        ok, txt = 'Successful Simulation' in r.stdout + r.stderr, r.stdout + r.stderr
    else:
        ok, txt = sz_check.run(d)
    TIMES[name] = time.time() - t0
    if not ok:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:]))
        return None
    if exe:
        return d
    print('  %s (%.1f s):' % (name, TIMES[name]))
    return d if check(d, name, cfg.get('timestep', 1.0)) else None

def check(d, name, dt=1.0):
    """the standard limits on run folder d (every run of this script)"""
    r = sz_check.checks(d, dt=dt)
    if 'vz_identity' in r:   # sz_check's column identity, from step 1 (the start storage of GWModelSummary.txt required)
        r['vz_step1_missing'] = 0 if r.get('vz_step1') else 1
    return sz_check.report(name, r, {k: v for k, v in LIM.items() if k in r})

def budget(d):
    return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))

def k1():
    print('K1 unit tests of the kinematic column')
    os.makedirs(W, exist_ok=True)   # (a fresh work folder: K1 runs first)
    exe = os.path.join(W, 'vadose_kw_unit')
    src = tc.SRC
    c = subprocess.run(['g++', '-O2', '-std=c++11', '-I' + src, os.path.join(HERE, 'vadose_kw_unit.cpp'), os.path.join(src, 'GWVadose.cpp'),
                        os.path.join(src, 'GWVadoseKW.cpp'), '-o', exe], capture_output=True, text=True)
    if c.returncode:
        print('  compile FAILED\n' + c.stderr[-2000:]); return False
    r = subprocess.run([exe, os.path.join(W, 'kw_wave.txt')], capture_output=True, text=True, timeout=1800)
    print('\n'.join('  ' + l for l in r.stdout.strip().split('\n')))
    ok = (r.returncode == 0) and ('checks, 0 failed' in r.stdout)
    print('  -> %s' % ('ok' if ok else 'FAIL'))
    return ok

V2A = dict(nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, perc=50.0, ksat=500.0, Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3)
RAIN_A = [0.0] * 10 + [40.0] * 3 + [0.0] * 77

def centroid_excess(d, i0, base):
    m = np.maximum(budget(d)['MF6 recharge [m3/d]'].values[i0:i0 + 60] - base, 0.0)   #(the storm's excess over 60 days)
    t = np.arange(len(m)) + 1.0
    return (m * t).sum() / m.sum(), m.max()

def k2():
    print('K2 storm over a water table 6 m deep (P1): NONE, RICHARDS, KINEMATIC')
    ok = True
    #(a) the P1 case as it is: columns start at rest, KINEMATIC at the drained content ths - Sy (they soak up the storm)
    t = np.arange(1, len(RAIN_A) + 1); cen = {}; tot = {}
    for lab, ex in (('none', ''), ('ric', RI), ('kw', KW)):
        d = run('k2_' + lab, extra_rvg=ex, rain=RAIN_A, days=len(RAIN_A), **V2A)
        if not d:
            ok = False; continue
        m = budget(d)['MF6 recharge [m3/d]'].values
        cen[lab] = (m * t).sum() / m.sum(); tot[lab] = m.sum()
    if len(cen) == 3:
        print('  (a) start at rest: recharge centroid delay RICHARDS %.1f d, KINEMATIC %.1f d (KINEMATIC delivered %.0f of %.0f m3 in 90 days:'
              ' its columns start at ths - Sy and soak up the storm)' % (cen['ric'] - cen['none'], cen['kw'] - cen['none'], tot['kw'], tot['none']))
    #(b) the same storm after 400 days of 2 mm/d (columns wetted to their steady profile): delay of the storm's excess
    warm = 400; rain = [2.0] * warm + [40.0] * 3 + [2.0] * 147
    ce = {}; pk = {}; cfg = dict(V2A, hru_w=400.0, chd=94.0)   #(a fixed head at the toe keeps the water table about 6 m deep)
    for lab, ex in (('none', ''), ('ric', RI), ('kw', KW)):
        d = run('k2b_' + lab, extra_rvg=ex, rain=rain, days=len(rain), **cfg)
        if not d:
            ok = False; continue
        base = budget(d)['MF6 recharge [m3/d]'].values[warm - 1]
        ce[lab], pk[lab] = centroid_excess(d, warm, base)
        sx = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
        print('    %s: water table %.2f m below the soil-zone base before the storm' % (lab, (sx.iloc[:, 3] - sx.iloc[:, 5]).values[(warm - 1) * len(sx) // len(rain)]))
    if len(ce) == 3:
        dr, dk = ce['ric'] - ce['none'], ce['kw'] - ce['none']
        good = dk >= 3.0 and dk > dr and pk['kw'] < 0.95 * pk['none']
        print('  (b) after 400 days of 2 mm/d: centroid delay of the storm RICHARDS %.1f d, KINEMATIC %.1f d; peak excess NONE %.0f,'
              ' RICHARDS %.0f, KINEMATIC %.0f m3/d -> %s' % (dr, dk, pk['none'], pk['ric'], pk['kw'], 'ok' if good else 'FAIL'))
        ok &= good
    return ok

def k3():
    print('K3 water table rising through the column into the soil zone and falling again (P3), KINEMATIC')
    rain = [0.0] * 5 + [30.0] * 40 + [0.0] * 135
    cfg = dict(nhru=1, hru_w=400.0, init_depth=3.0, chd=97.0, aq_thick=20.0, rain=rain, days=len(rain), perc=30.0, ksat=300.0, Kh=1.0, Kv=0.3,
               Sy=0.1, pet=3.0, soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3)
    d = run('k3_kw', extra_rvg=KW, **cfg)
    if not d:
        return False
    b = budget(d); s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    wt, zb = s.iloc[:, 5].values, s.iloc[:, 3].values
    st = b['unsaturated zone storage [m3]'].values; inflow = b['unsaturated zone inflow [m3]'].values
    rose = (wt - zb).max() > 0.0
    fell = (zb - wt)[-1] > 0.3
    iup = int(np.argmax(wt - zb))
    collapsed = bool(rose and np.any(np.abs(st[:iup + 1]) < 1e-9) and np.any(np.abs(st[:iup]) > 1.0))
    after = bool(np.any(np.abs(st[iup:]) > 1e-6) or np.any(inflow[iup:] > 0.0))   # the column re-formed under the falling water table
    ok = rose and fell and collapsed and after
    print('  water table to %.2f m above the soil-zone base, back to %.2f m below; column storage max %.0f m3, gone %s, re-formed %s -> %s'
          % ((wt - zb).max(), (zb - wt)[-1], np.abs(st).max(), collapsed, after, 'ok' if ok else 'FAIL'))
    return ok

def sand_over_clay(d):
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    a = t.index(':AquiferClasses'); b = t.index(':AquiferProfileParameters')
    t = t[:a] + (':AquiferClasses\n  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY, CLAPP_B, AIR_ENTRY_PRESSURE\n'
                 '  :Units, m/d, m/d, 1/m, none, none, none, m\n  SAND, 10, 0.5, 1.0E-5, 0.2, 0.35, 4, 0.2\n'
                 '  CLAY, 5, 0.004, 1.0E-5, 0.05, 0.45, 10, 0.5\n:EndAquiferClasses\n'
                 ':AquiferProfiles\n  AQ, 2, SAND, 3.0, AQUIFER, CLAY, TO_BEDROCK, AQUIFER\n:EndAquiferProfiles\n') + t[b:]
    open(p, 'w').write(t)

def k4():
    print('K4 layered aquifer: 3 m of sand over clay, columns crossing both (KINEMATIC; RICHARDS counted)')
    rain = [0.0] * 5 + [25.0] * 20 + [0.0] * 95
    cfg = dict(nhru=1, hru_w=400.0, init_depth=7.0, chd=93.0, aq_thick=20.0, rain=rain, days=len(rain), perc=30.0, ksat=300.0, Kv=0.5, Sy=0.2)
    ok = True; res = {}
    for lab, ex in (('kw', KW), ('ric', RI)):
        d = run('k4_' + lab, extra_rvg=ex, edit=sand_over_clay, **cfg)
        if not d:
            ok = False; continue
        b = budget(d)
        sx = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv')); dep = (sx.iloc[:, 3] - sx.iloc[:, 5]).values
        res[lab] = (b['unsaturated zone inflow [m3]'].sum(), b['unsaturated zone to aquifer [m3]'].sum(), b['unsaturated zone storage [m3]'].max(),
                    b['rejected recharge [m3]'].sum(), dep.min(), dep.max())
        print('  %s: column inflow %.0f m3, to the aquifer %.0f m3, largest column storage %.0f m3, rejected %.0f m3; water table %.2f to %.2f m'
              ' below the soil-zone base' % ((lab,) + res[lab]))
    if 'kw' in res:
        good = res['kw'][0] > 100.0 and res['kw'][2] > 0.0
        print('  KINEMATIC columns carried the recharge through the clay -> %s' % ('ok' if good else 'FAIL'))
        ok &= good
    return ok

def k5():
    print('K5 hotstart continuity: 60 + 60 days equal 120 days (KINEMATIC)')
    rain = ([0.0] * 10 + [40.0] * 3 + [0.0] * 17) * 4
    cfg = dict(V2A, extra_rvg=KW)
    full = run('k5_full', rain=rain, days=120, **cfg)
    first = run('k5_first', rain=rain[:60], days=60, **cfg)
    if not (full and first):
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    has = ':GWVadoseColumns' in open(rvc).read()
    second = run('k5_second', start='2000-03-01', rvc=rvc, rain=rain[60:], days=60, **cfg)
    if not second:
        return False
    a, b = budget(full).iloc[60:].reset_index(drop=True), budget(second)
    cols = [c for c in a.columns if c in b.columns and a[c].dtype.kind == 'f' and c not in DIAG and 'time' not in c]
    dev = max(((a[c] - b[c]).abs() / max(a[c].abs().max(), 1.0)).max() for c in cols)
    ok = has and dev < 1e-6
    print('  :GWVadoseColumns written %s; largest relative deviation of the restart %.2g -> %s' % (has, dev, 'ok' if ok else 'FAIL'))
    return ok

def k6():
    print('K6 existing-model round trip with KINEMATIC columns')
    import test_sz_existing
    test_sz_existing.W = W
    ok = test_sz_existing.roundtrip('k6', KW + ':SoilZoneAquiferClass SAND\n', aq_b=4.0, aq_psia=0.3, init_depth=3.0)
    for lab in ('gen', 'ext'):   # the standard limits (roundtrip reports its own, looser ones)
        d = os.path.join(W, 'k6_' + lab)
        if os.path.exists(os.path.join(d, 'out', 'GWBudget.csv')):
            r = sz_check.checks(d); r['vz_step1_missing'] = 0 if r.get('vz_step1') else 1; print('  k6 %s, standard limits:' % lab)
            ok &= sz_check.report(lab, r, {k: v for k, v in LIM.items() if k in r})
    return ok

def k7():
    print('K7 speed: hillslope of %d HRUs over a water table 5 m deep' % (4 if QUICK else 10))
    n = 4 if QUICK else 10; days = 60 if QUICK else 180
    rain = ([0.0] * 7 + [15.0] * 3) * (days // 10)
    cfg = dict(nhru=n, hru_w=100.0, slope=0.005, init_depth=5.0, aq_thick=20.0, rain=rain, days=days, perc=30.0, ksat=300.0, Kv=0.5, Sy=0.2,
               aq_b=4.0, aq_psia=0.3, chd=94.0)
    res = []
    for lab, ex in (('none', ''), ('ric', RI), ('kw', KW)):
        d = run('k7_' + lab, extra_rvg=ex, **cfg)
        res.append(d is not None)
    print('  run times NONE %.1f s, RICHARDS %.1f s, KINEMATIC %.1f s (machine-dependent; reported only) -> %s'
          % (TIMES.get('k7_none', 0), TIMES.get('k7_ric', 0), TIMES.get('k7_kw', 0), 'ok' if all(res) else 'FAIL'))
    return all(res)

def same_outputs(a, b):
    worst = []
    for f in sorted(glob.glob(os.path.join(a, 'out', '*.csv'))) + [os.path.join(a, 'out', 'solution.rvc')]:
        g = os.path.join(b, 'out', os.path.basename(f))
        if not os.path.exists(g):
            worst.append(os.path.basename(f) + ' missing'); continue
        if f.endswith('.csv'):
            x, y = pd.read_csv(f), pd.read_csv(g)
            x = x[[c for c in x.columns if c not in DIAG]]; y = y[[c for c in y.columns if c not in DIAG]]
            if not x.equals(y):
                worst.append(os.path.basename(f))
        elif not tc.rvc_same(f, g):   # (solution.rvc: the same state to the digits either file holds, the column tops when both files hold them)
            worst.append(os.path.basename(f))
    return worst

def k8():
    print('K8 byte-identity of NONE, RICHARDS and CONCEPTUAL against the reference build')
    if not REF or not os.path.exists(REF):
        print('SKIP K8 byte-identity: no reference build (set RAVEN_EXE_REF)')
        return True
    rain = [0.0] * 5 + [30.0] * 20 + [0.0] * 35
    cases = [('none', dict(V2A, rain=RAIN_A[:60], days=60, extra_rvg='')),
             ('ric', dict(V2A, rain=RAIN_A[:60], days=60, extra_rvg=RI)),
             ('ric_c', dict(nhru=1, hru_w=400.0, init_depth=3.0, chd=97.0, aq_thick=20.0, rain=rain, days=60, perc=30.0, ksat=300.0, Kh=1.0,
                            Kv=0.3, Sy=0.1, pet=3.0, soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3, extra_rvg=RI)),
             ('conceptual', dict(V2A, rain=RAIN_A[:60], days=60, physical=False))]
    ok = True
    for lab, cfg in cases:
        a = run('k8_%s_new' % lab, exe=tc.RAVEN, **cfg); b = run('k8_%s_ref' % lab, exe=REF, **cfg)
        if not (a and b):
            ok = False; continue
        diff = same_outputs(a, b)
        print('  %s: %s' % (lab, 'byte-identical' if not diff else 'DIFFERENT: ' + ', '.join(diff)))
        ok &= not diff
    return ok

def k9():
    print('K9 the checks of this script see a column leak (the P1 storm, KINEMATIC; GWBudget.csv altered)')
    d = run('k9', extra_rvg=KW, rain=RAIN_A, days=len(RAIN_A), **V2A)
    if not d:
        return False
    ok = True
    for leak in (1e-5, 1e-4):
        n = sz_check.leak_copy(d, os.path.join(W, 'k9_leak'), leak)
        print('  leak %g m3 per step on %d steps:' % (leak, n))
        caught = not check(os.path.join(W, 'k9_leak'), 'k9 leak %g' % leak)
        print('  -> %s' % ('caught (ok)' if caught else 'NOT caught: FAIL'))
        ok &= caught and n >= 5
    return ok

def k10():
    print('K10 a water table rising fast into a nearly full top cell: KINEMATIC held back by the room left in it, with a warning')
    q = 90.0
    d = run('k10', extra_rvg=KW + ':SoilZoneVadoseInitialFlux %g\n' % q, nhru=1, slope=0.0, Sy=0.2, aq_b=4.0, aq_psia=0.3, aq_thick=30.0,
            init_depth=1.6, rain=[q] * 4, perc=1000.0, phi0=(0.0, 0.0), days=4, Kh=1.0, Kv=0.1)
    if not d:
        return False
    e = open(os.path.join(d, 'out', 'Raven_errors.txt'), errors='replace').read()
    warned = 'than the room left in the top cell above the water table' in e
    print('  room-limit warning: %s' % ('written (ok)' if warned else 'MISSING: FAIL'))
    return warned

def k11():
    print('K11 a column across two aquifer classes: the release meets Sy dh before the room, and the warning names Sy dh')
    q = 90.0
    def silt(d):
        p = os.path.join(d, 'm.rvp'); t = open(p).read()
        t = t.replace(':EndAquiferClasses', '  SILT, 1, 0.1, 1.0E-5, 0.05, 0.3, 4, 0.3\n:EndAquiferClasses')
        t = re.sub(r'(AQ, 2, SAND, [0-9.]+, AQUIFER, )SAND', r'\1SILT', t)
        open(p, 'w').write(t)
    d = run('k11', edit=silt, extra_rvg=KW + ':SoilZoneVadoseInitialFlux %g\n' % q, nhru=1, slope=0.0, Sy=0.25, aq_b=4.0, aq_psia=0.3, aq_thick=30.0,
            init_depth=2.4, rain=[q] * 3, perc=1000.0, phi0=(0.0, 0.0), days=3, Kh=1.0, Kv=0.1, top=1.0)
    if not d:
        return False
    e = open(os.path.join(d, 'out', 'Raven_errors.txt'), errors='replace').read()
    w = [l for l in e.split('\n') if 'a rising water table met more' in l]
    good = len(w) == 1 and 'than MODFLOW stores for the rise (Sy dh)' in w[0] and 'crosses aquifer classes' in w[0] and 'room left in the top cell' not in w[0]
    print('  warning: %s -> %s' % (w[0][:300] if w else 'none', 'ok' if good else 'FAIL'))
    return good

def k12():
    print('K12 a vanishing column: released at most the room, the rest back to the soil zone as rejected recharge')
    def run_m(meth):
        return run('k12_' + meth.lower(), extra_rvg=':SoilZoneVadose %s\n:SoilZoneVadoseInitialFlux 90\n' % meth, nhru=1, slope=0.0, Sy=0.2, aq_b=4.0, aq_psia=0.3,
                   aq_thick=30.0, init_depth=1.45, rain=[90.0, 0.0, 0.0], perc=1000.0, phi0=(0.0, 0.0), days=3, Kh=1.0, Kv=0.1)
    ok = True
    for meth in ('KINEMATIC', 'RICHARDS'):
        d = run_m(meth)
        if not d:
            ok = False; continue
        b = budget(d); e = open(os.path.join(d, 'out', 'Raven_errors.txt'), errors='replace').read()
        st0, rel, rej = b['unsaturated zone storage [m3]'][0], b['unsaturated zone to aquifer [m3]'][1], b['rejected recharge [m3]'][1]
        good = 0.0 < rel <= 0.2 * 0.05 * 40000.0 and abs(rel + rej - st0) < 1e-6 * st0 and st0 > 10.0 * rel and 'a rising water table met more' not in e
        print('  %s: column %.1f m3 at the end of step 1; step 2 released %.3f m3 (at most the room), handed back %.2f m3 -> %s' % (meth, st0, rel, rej, 'ok' if good else 'FAIL'))
        ok &= good
    return ok

def main():
    res = {}
    for k, f in (('K1', k1), ('K2', k2), ('K3', k3), ('K4', k4), ('K5', k5), ('K6', k6), ('K7', k7), ('K8', k8), ('K9', k9), ('K10', k10), ('K11', k11), ('K12', k12)):
        try:
            res[k] = bool(f())
        except Exception as e:   # (a crash of one test is that test's failure)
            print('  %s crashed: %r' % (k, e)); res[k] = False
    bad = [k for k, v in res.items() if not v]
    print('kinematic tests: %s' % ('ALL PASSED' if not bad else 'FAILED (%s)' % ', '.join(bad)))
    return not bad

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
