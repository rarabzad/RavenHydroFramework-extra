"""Tests of :SoilZoneVadose LAG {t_m} {N}, the linear storage cascade (docs/design/soil_zone_lag.md; manual
Section sec:szvadoselag).

U   unit tests (vadose_lag_unit.cpp against GWVadose.cpp and GWVadoseLag.cpp): travel time per metre (eq. lagtm, also
    Ks < q_r), mass balance to round-off over random columns/materials/layering/fluxes/steps, no content above ths, nodes
    below equilibrium, inactive-column contract (rejects), tiny residence times (N = 200, LAG 1e-6: substep count clamped
    to [1, 50] before the int cast), steady start S_i = min(q k_i, Smax_i), Erlang response of equal reservoirs, N_eff of
    the grid; then the impulse responses of grid columns (one material, sand over loam) against the exact convolution of
    the exponentials (matrix exponential of the cascade, computed here) and the mean travel time sum k_i (= t_m L).
L1  storm over a deep water table (6 m; P1 of test_sz_models.py): NONE, RICHARDS, LAG 2, LAG 4 and LAG (derived t_m): the
    recharge reaching MODFLOW is later and lower with LAG, more so with a longer travel time; identities at round-off.
L2  a water table rising through the columns into the soil zone and falling again (P3 with LAG): columns collapse and
    re-form; identities hold throughout.
L3  layered aquifer: the column crosses SAND (3 m) over a FINE class of the same conductivity but larger specific yield
    (derived t_m 18 against 10.3 d/m) on a sloping hillslope; each node uses its own material's travel time (the recharge
    arrives later than over SAND alone); identities.
L4  hotstart continuity: 60 + 60 days from the first run's solution.rvc (:GWVadoseColumns) equal 120 days in one go.
L5  existing-model round trip (as X1 of test_sz_models_ext.py) with LAG: the generated model's MODFLOW files coupled as an
    existing model give the same flows (relative 1e-3) and identities.
L6  the cell-room release cap of a rising water table (VZStep): one flat HRU, Sy 0.02
    well below the drainable porosity (0.078), LAG 1000 (columns full to theta_s by :SoilZoneVadoseInitialFlux 10, so the
    inflow passes straight through and the column's loss of storage is its release), 5 mm/d from 6 m deep: the water table
    rises about 2 m per step into a nearly full top cell. A rising water table releases at most min(int Sy dz over the
    rise, int Sy dz over [h, min(z_b, z_top)]), the second being the room the top cell has left above the water table.
    Checked: on every step the column survives its release (storage loss) is at most S_y A (z_top - h) for the head h it
    started from, and on at least one step that room is what limits it (release within 0.1 % of it; without the room cap that step releases 2269 m3 against a room of 1626 m3); identities.
S   speed: run times of NONE, LAG and RICHARDS on the same case (and the cost per column step from U).
B   byte-identity of NONE, RICHARDS and CONCEPTUAL runs (b_hill_none, b_hill_ric, b_conceptual: the T2/T3 hillslope,
    RICHARDS with a deep water table) against RAVEN_EXE_REF, the build of the commit before your change ; out/*.csv and solution.rvc compared byte for byte except the diagnostic column
    `interface change [m]`. Without RAVEN_EXE_REF B prints SKIP (never "ok").
Identities use the standard limits (sz_check.STD_LIMITS); vz_identity is scaled by the
step's flows and the two storages whose difference it takes (GWBudget.csv carries 10 significant digits: a column store
of 1e4 m3 is rounded to 1e-5 m3).
Quick mode (RAVEN_TEST_QUICK=1): shorter S and only b_hill_ric in B.
"""
import os, sys, shutil, re, time, datetime, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check
from test_hillslope import CFG

tc = sz_check.tc
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
W = tc.work('soilzone', 'vz_lag')
REF = getattr(tc, 'REF', None)
if REF is None:
    REF = os.environ.get('RAVEN_EXE_REF', '') or os.environ.get('RAVEN_REF_EXE', '')   # (RAVEN_REF_EXE: the name once used)
LIM = dict(getattr(sz_check, 'STD_LIMITS', {}))
LIM.update({'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 5e-9, 'sz_identity': 1e-8, 'shortfall': 1e-6,
            'vz_identity': 1e-8})
DIAG = list(getattr(sz_check, 'DIAGNOSTIC_COLUMNS', ['interface change [m]']))
SKIPS = []
STORM = [0.0] * 10 + [40.0] * 3 + [0.0] * 77
STORM_CFG = dict(nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, rain=STORM, days=len(STORM), perc=50.0, ksat=500.0,
                 Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3)


def skip(what, why):
    if hasattr(tc, 'skip'):
        tc.skip(what, why)
    else:
        print('SKIP %s: %s' % (what, why))
    SKIPS.append(what)


def vz_identity(d):
    """column balance per step from the second step: |dS - in + cap + out| / max(1 m3, |in| + |out| + |cap| + |S0| + |S1|)"""
    b = budget(d)
    if 'unsaturated zone storage [m3]' not in b:
        return None
    s = b['unsaturated zone storage [m3]']
    i, o, c = b['unsaturated zone inflow [m3]'], b['unsaturated zone to aquifer [m3]'], b['capillary rise to soil zone [m3]']
    r = (s.diff() - i + c + o)[1:]
    sc = (i.abs() + o.abs() + c.abs() + s.abs() + s.shift().abs())[1:].clip(lower=1.0)
    return float((r.abs() / sc).max()) if len(r) else 0.0


def check(d, name, dt=1.0):
    r = sz_check.checks(d, dt=dt)
    v = vz_identity(d)
    if v is not None:
        r['vz_identity'] = v
    print('  %s:' % name)
    return sz_check.report(name, r, {k: x for k, x in LIM.items() if k in r}), r


def run(name, exe=None, rvp_edit=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg)
    if rvp_edit:
        p = os.path.join(d, 'm.rvp'); t = rvp_edit(open(p).read()); open(p, 'w').write(t)
    if exe:
        r = subprocess.run([exe, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=3600)
        ok, txt = 'Successful Simulation' in r.stdout + r.stderr, r.stdout + r.stderr
    else:
        ok, txt = sz_check.run(d)
    if not ok:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:]))
        return None
    return d


def budget(d):
    return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))


def centroid(d):
    m = budget(d)['MF6 recharge [m3/d]'].values; t = np.arange(1, len(m) + 1)
    return (m * t).sum() / m.sum(), m.max()


# ------------------------------------------------------------------------------------------------------------------
def test_u():
    print('U unit tests (vadose_lag_unit.cpp)')
    os.makedirs(W, exist_ok=True)
    exe, imp = os.path.join(W, 'vadose_lag_unit'), os.path.join(W, 'lag_impulse.txt')
    c = subprocess.run('g++ -O2 -std=c++11 -I%s %s %s/GWVadose.cpp %s/GWVadoseLag.cpp -o %s'
                       % (tc.SRC, os.path.join(HERE, 'vadose_lag_unit.cpp'), tc.SRC, tc.SRC, exe), shell=True, capture_output=True, text=True)
    if c.returncode:
        print('  compile FAILED\n' + c.stderr[-2000:]); return False
    r = subprocess.run([exe, imp], capture_output=True, text=True)
    print('\n'.join('  ' + l.strip() for l in r.stdout.strip().split('\n')))
    ok = (r.returncode == 0) and re.search(r'LAG unit tests: \d+ checks, 0 failed', r.stdout) is not None
    for l in r.stdout.split('\n'):
        if l.strip().startswith('SKIP'):
            SKIPS.append(l.strip()[5:])
    # impulse responses against the exact convolution of the exponentials (linear cascade dS/dt = A S)
    from scipy.linalg import expm
    lines = open(imp).read().split('\n'); i = 0
    while i < len(lines) and lines[i].startswith('CASE'):
        _, name, n, dt, V, nst = lines[i].split(); n, dt, V, nst = int(n), float(dt), float(V), int(nst)
        k = np.array([float(x) for x in lines[i + 1].split()[1:]]); q = np.array([float(x) for x in lines[i + 2].split()[1:]]); i += 3
        A = np.diag(-1.0 / k) + np.diag(1.0 / k[:-1], -1)
        E = expm(A * dt); S = np.zeros(n); S[0] = V; cum = []
        for _ in range(nst):
            S = E @ S; cum.append(V - S.sum())
        cum = np.array(cum) / V; got = np.cumsum(q) / V
        err = np.abs(got - cum).max()
        t = (np.arange(nst) + 0.5) * dt; mean = (t * q).sum() / q.sum(); want = k.sum()
        good = err < 0.02 and abs(mean - want) < max(0.02 * want, 0.5 * dt) and abs(got[-1] - 1.0) < 1e-3
        ok &= good
        print('  impulse %-20s N=%2d dt=%.2g d: largest difference of the cumulative response from the exact cascade %.4f; '
              'mean travel time %.3f d (sum k %.3f d, N_eff %.2f) -> %s'
              % (name, n, dt, err, mean, want, k.sum() ** 2 / (k ** 2).sum(), 'ok' if good else 'FAIL'))
    return ok


def test_l1():
    print('L1 storm over a deep water table (6 m): NONE, RICHARDS, LAG 2, LAG 4, LAG (derived)')
    runs = [('l1_none', ''), ('l1_ric', ':SoilZoneVadose RICHARDS\n'), ('l1_lag2', ':SoilZoneVadose LAG 2\n'),
            ('l1_lag4', ':SoilZoneVadose LAG 4\n'), ('l1_lag0', ':SoilZoneVadose LAG\n')]
    res, ok = {}, True
    for name, vz in runs:
        d = run(name, extra_rvg=vz, **STORM_CFG)
        if not d:
            return False
        good, _ = check(d, name); ok &= good
        res[name] = centroid(d)
    c0 = res['l1_none'][0]
    for name, _ in runs:
        print('  %-8s recharge centroid day %6.2f (%+6.2f d), peak %5.0f m3/d' % (name, res[name][0], res[name][0] - c0, res[name][1]))
    d2, d4, dd = (res[n][0] - c0 for n in ('l1_lag2', 'l1_lag4', 'l1_lag0'))
    good = (5.0 < d2 < d4 < dd) and d2 >= 6.0 and dd >= 25.0 and all(res[n][1] < 0.8 * res['l1_none'][1] for n in ('l1_lag2', 'l1_lag4', 'l1_lag0'))
    print('  delays %+.1f / %+.1f / %+.1f d (LAG 2 / LAG 4 / derived), longer with the travel time, peaks lower -> %s'
          % (d2, d4, dd, 'ok' if good else 'FAIL'))
    return ok and good


def test_l2():
    print('L2 a water table rising through the columns into the soil zone and falling again (LAG 2)')
    rain = [0.0] * 5 + [30.0] * 40 + [0.0] * 135
    cfg = dict(nhru=1, hru_w=400.0, init_depth=3.0, chd=97.0, aq_thick=20.0, rain=rain, days=len(rain), perc=30.0, ksat=300.0, Kh=1.0,
               Kv=0.3, Sy=0.1, pet=3.0, soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3)
    d = run('l2_lag', extra_rvg=':SoilZoneVadose LAG 2\n', **cfg)
    if not d:
        return False
    ok, _ = check(d, 'l2_lag')
    b = budget(d); s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    wt, zb = s.iloc[:, 5].values, s.iloc[:, 3].values
    st = b['unsaturated zone storage [m3]'].values
    rose, fell = (wt - zb).max() > 0.0, (zb - wt)[-1] > 0.3
    collapsed = bool(np.any(np.abs(st) < 1e-9)) if rose else False
    good = rose and fell and collapsed
    print('  water table to %.2f m above the soil-zone base and back to %.2f m below; column storage min %.3g, end %.3g m3 -> %s'
          % ((wt - zb).max(), (zb - wt)[-1], np.abs(st).min(), st[-1], 'ok' if good else 'FAIL'))
    return ok and good


def layered(t):
    t = t.replace('AQ, 1, SAND, TO_BEDROCK, AQUIFER', 'AQ, 2, SAND, 3.0, AQUIFER, FINE, TO_BEDROCK, AQUIFER')
    m = re.search(r'\n  SAND, ([^\n]*)\n:EndAquiferClasses', t)
    v = [x.strip() for x in m.group(1).split(',')]
    v[3], v[4] = '0.35', '0.45'   # SPEC_YIELD, POROSITY: the same conductivity and retention exponent, a larger Sy (t_m 18 against 10.3 d/m)
    return t.replace(m.group(0), '\n  SAND, %s\n  FINE, %s\n:EndAquiferClasses' % (m.group(1), ', '.join(v)))


def test_l3():
    print('L3 layered aquifer on a slope: SAND (3 m) over FINE, derived travel times')
    cfg = dict(STORM_CFG, nhru=4, hru_w=100.0, slope=0.01, init_depth=6.0, extra_rvg=':SoilZoneVadose LAG\n')
    d1 = run('l3_sand', **cfg)
    d2 = run('l3_layered', rvp_edit=layered, **cfg)
    if not (d1 and d2):
        return False
    ok1, _ = check(d1, 'l3_sand'); ok2, _ = check(d2, 'l3_layered')
    c1, c2 = centroid(d1)[0], centroid(d2)[0]
    summ = open(os.path.join(d2, 'out', 'GWModelSummary.txt')).read() if os.path.exists(os.path.join(d2, 'out', 'GWModelSummary.txt')) else ''
    good = c2 > c1 + 1.0
    print('  recharge centroid day %.2f over SAND, %.2f with the slower FINE below 3 m -> %s' % (c1, c2, 'ok' if good else 'FAIL'))
    return ok1 and ok2 and good


def test_l4():
    print('L4 hotstart continuity: 60 + 60 days equal 120 days (LAG 2)')
    rain = ([0.0] * 10 + [40.0] * 3 + [0.0] * 17) * 4
    cfg = dict(nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, perc=50.0, ksat=500.0, Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3,
               extra_rvg=':SoilZoneVadose LAG 2\n')
    full = run('l4_full', rain=rain, days=120, **cfg)
    first = run('l4_first', rain=rain[:60], days=60, **cfg)
    if not (full and first):
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    has = ':GWVadoseColumns' in open(rvc).read()
    d = os.path.join(W, 'l4_second'); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, rain=rain[60:], days=60, **cfg)
    for f in ('m.rvi', 'm.rvt'):
        p = os.path.join(d, f); t = open(p).read().replace('2000-01-01 00:00:00', '2000-03-01 00:00:00'); open(p, 'w').write(t)
    shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    ok, txt = sz_check.run(d)
    if not ok:
        print('  l4_second: run FAILED\n' + txt[-1500:]); return False
    good, _ = check(full, 'l4_full')
    a, b = budget(full).iloc[60:].reset_index(drop=True), budget(d)
    cols = [c for c in a.columns if c in b.columns and c not in ('time [d]', 'date') + tuple(DIAG) and a[c].dtype != object]
    dev = max(float((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0)) for c in cols)
    good2 = has and dev < 1e-6
    print('  :GWVadoseColumns written %s; largest relative deviation of %d GWBudget.csv columns %.2g -> %s'
          % (has, len(cols), dev, 'ok' if good2 else 'FAIL'))
    return good and good2


def test_l5():
    print('L5 existing-model round trip with LAG (as X1 of test_sz_models_ext.py)')
    cfg = dict(CFG); cfg.update(init_depth=3.0, aq_b=4.0, aq_psia=0.3, extra_rvg=':SoilZoneVadose LAG 2\n:SoilZoneAquiferClass SAND\n')
    g = run('l5_gen', **cfg)
    if not g:
        return False
    m = os.path.join(W, 'l5_model'); shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in ('gwf.rch', 'gwf.drn', 'gwf.szx', 'gwf.szq', 'gwf.szd', 'linkage.cache', 'mfsim.lst', 'gwf.lst', 'gwf.hds', 'gwf.cbc'):
        if os.path.exists(os.path.join(m, f)):
            os.remove(os.path.join(m, f))
    nam = open(os.path.join(m, 'gwf.nam')).read()
    open(os.path.join(m, 'gwf.nam'), 'w').write('\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN', l)))
    e = os.path.join(W, 'l5_ext'); shutil.rmtree(e, ignore_errors=True); sz_models.make_case(e, **cfg)
    shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
    rvg = open(os.path.join(e, 'm.rvg')).read()
    rvg = '\n'.join(l for l in rvg.split('\n') if not l.startswith((':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary')))
    rvg += '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m
    open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
    ok, txt = sz_check.run(e)
    if not ok:
        print('  l5_ext: existing-model run FAILED\n' + txt[-2500:]); return False
    good1, _ = check(g, 'l5 generated'); good2, _ = check(e, 'l5 existing')
    a, b = budget(g), budget(e)
    cols = ['MF6 recharge [m3/d]', 'soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]', 'rejected recharge [m3]',
            'soil-zone exchange applied to Raven [m3]', 'storage release [m3/d]', 'unsaturated zone inflow [m3]', 'unsaturated zone to aquifer [m3]']
    worst = max((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0) for c in cols if c in a and c in b)
    good3 = worst < 1e-3
    print('  largest relative difference of the flows, generated vs existing model %.2e -> %s' % (worst, 'ok' if good3 else 'FAIL'))
    return good1 and good2 and good3


def test_s():
    print('S speed: NONE, LAG and RICHARDS on a 20-HRU hillslope (400 cells, 5x5 DEM samples) over a 6 m deep water table')
    days = 120 if QUICK else 365
    rain = (STORM * 5)[:days]
    cfg = dict(CFG); cfg.update(nhru=20, width=2000.0, subgrid=5, smooth=0.2, rain=rain, days=days, init_depth=6.0, aq_b=4.0,
                                aq_psia=0.3, aq_thick=20.0)
    times, ok = {}, True
    for name, vz in (('NONE', ''), ('LAG', ':SoilZoneVadose LAG\n'), ('RICHARDS', ':SoilZoneVadose RICHARDS\n')):
        t0 = time.time(); d = run('s_' + name.lower(), extra_rvg=vz, **cfg); times[name] = time.time() - t0
        if not d:
            return False
        good, _ = check(d, 's_' + name.lower()); ok &= good
        print('  %-8s %6.2f s for %d days (400 columns)' % (name, times[name], days))
    print('  LAG adds %.2f s, RICHARDS %.2f s to the NONE run (column step, water-table following and interface together)' % (times['LAG'] - times['NONE'], times['RICHARDS'] - times['NONE']))
    return ok


def same_csv(a, b):
    """byte-identical, apart from the diagnostic columns; returns (equal, note)"""
    ta, tb = open(a).read(), open(b).read()
    if ta == tb:
        return True, ''
    la, lb = ta.split('\n'), tb.split('\n')
    if len(la) != len(lb):
        return False, 'line count %d vs %d' % (len(la), len(lb))
    hdr = la[0].split(',')
    if lb[0] != la[0]:
        return False, 'header differs'
    skipc = [i for i, h in enumerate(hdr) if h.strip() in DIAG]
    for x, y in zip(la[1:], lb[1:]):
        if x == y:
            continue
        fx, fy = x.split(','), y.split(',')
        if len(fx) != len(fy) or any(fx[i] != fy[i] for i in range(len(fx)) if i not in skipc):
            return False, 'first difference: %s | %s' % (x[:120], y[:120])
    return True, '(differs only in %s)' % ', '.join(DIAG)


def test_b():
    print('B byte-identity of NONE, RICHARDS and CONCEPTUAL against the reference build')
    if not REF or not os.path.exists(REF):
        skip('B byte-identity (test_vz_lag.py)', 'no reference build (set RAVEN_EXE_REF to the build of the commit before your change)')
        return True
    cases = [('b_hill_ric', dict(CFG, init_depth=3.0, aq_b=4.0, aq_psia=0.3, extra_rvg=':SoilZoneVadose RICHARDS\n'))]
    if not QUICK:
        cases = [('b_hill_none', dict(CFG)), ('b_conceptual', dict(CFG, physical=False))] + cases
    ok = True
    for name, cfg in cases:
        d1 = run(name + '_new', **cfg); d2 = run(name + '_ref', exe=REF, **cfg)
        if not (d1 and d2):
            ok = False; continue
        files = sorted(f for f in os.listdir(os.path.join(d1, 'out')) if f.endswith('.csv') or f == 'solution.rvc')
        bad = []
        for f in files:
            pb = os.path.join(d2, 'out', f)
            if not os.path.exists(pb):
                bad.append(f + ' (missing in the reference)'); continue
            eq, note = same_csv(os.path.join(d1, 'out', f), pb)
            if not eq:
                bad.append('%s: %s' % (f, note))
        good = not bad
        ok &= good
        print('  %-13s %d files (out/*.csv, solution.rvc) byte-identical%s -> %s' % (name, len(files), '' if good else ': ' + '; '.join(bad), 'ok' if good else 'FAIL'))
    return ok


def test_l6():
    print('L6 a water table rising into a nearly full top cell releases at most the room the cell has left (LAG 1000, Sy 0.02)')
    Sy, A = 0.02, 200.0 * 200.0
    d = run('l6_room', nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, rain=5.0, perc=20.0, days=6, Sy=Sy, Kv=0.5,
            aq_b=4.0, aq_psia=0.3, extra_rvg=':SoilZoneVadose LAG 1000\n:SoilZoneVadoseInitialFlux 10\n')
    if not d:
        return False
    ok, _ = check(d, 'l6_room')
    b = budget(d); s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    wt, zb = s['water table [m]'].values, s['soil-zone base [m]'].values        # (flat land: the top cell's top is the base)
    st = b['unsaturated zone storage [m3]'].values
    rel = (b['unsaturated zone to aquifer [m3]'] - b['unsaturated zone inflow [m3]']).values   # (full columns pass their inflow on)
    worst, bound = 0.0, 0
    for n in range(1, len(b)):
        if not (st[n] > 0.0):
            continue                                                             # (the column vanished: rule (ii) instead)
        room = Sy * A * max(zb[n] - wt[n - 1], 0.0)
        worst = max(worst, rel[n] - room)
        if room > 1.0 and rel[n] > 0.999 * room:
            bound += 1
        print('    step %d: head %.3f m, room %.1f m3, release %.1f m3' % (n + 1, wt[n - 1], room, rel[n]))
    good = worst <= 1e-6 * A and bound >= 1
    print('  release beyond the room at most %.3g m3; steps limited by the room %d (at least 1) -> %s' % (worst, bound, 'ok' if good else 'FAIL'))
    return ok and good

def main():
    tc.need_mf6() if hasattr(tc, 'need_mf6') else None
    res = {}
    for name, f in (('U', test_u), ('L1', test_l1), ('L2', test_l2), ('L3', test_l3), ('L4', test_l4), ('L5', test_l5), ('L6', test_l6), ('S', test_s), ('B', test_b)):
        t0 = time.time()
        try:
            res[name] = bool(f())
        except Exception as ex:   # (a crash is a failure, with its reason)
            import traceback; traceback.print_exc(); res[name] = False
        print('  [%s %s, %.0f s]' % (name, 'ok' if res[name] else 'FAIL', time.time() - t0))
    bad = [k for k, v in res.items() if not v]
    if SKIPS:
        print('skipped: ' + '; '.join(SKIPS))
    print('LAG tests: %s' % ('ALL PASSED' if not bad else 'FAILED (%s)' % ', '.join(bad)))
    return not bad


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
