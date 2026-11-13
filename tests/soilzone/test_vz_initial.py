""":SoilZoneVadoseInitialFlux and the columns' initial state (VI1-VI13).

VI1  steady start: columns started at the steady profile for q carry q from the first step, with the start line in
    GWModelSummary.txt ("unsaturated storage : V m3 at the start") and the columns' balance from step 1; with depth classes
    (K = 3) too, and for KINEMATIC and LAG (gwvz::InitSteadyKinematic, the LAG cascade's S_i = q k_i). Enforced: step-1
    outflow = inflow (1e-6) and a positive start storage; the storage change over the run is printed, not enforced (the
    water table rises under the recharge in this closed model, so the columns shorten). Columns that start at rest fail
    (start storage 0, step-1 outflow below the inflow).
VI2  a hotstart taken before any column exists (water table above the soil-zone base at the end of the first run), the
    second run with the initial flux: the flux is ignored with the warning "... start at rest (their reference profile)",
    no steady profile is put in, identities from step 1.
VI4  columns' balance of step 1 (vz_identity from step 1, start value = previous run's end for a hotstart; a hotstart with
    heads +1 m so every bottom moves up in step 1); a deliberately moved start value must fail the check.
VI5  the steady start is for the flux each column receives, (1 - F) q: 2 HRUs, hummocks +-3 m, the water
    table 3 m deep held by a specified head (F = 0.16), PERC_CONSTANT 2 mm/d, :SoilZoneVadoseInitialFlux 2, K = 1 (and
    K = 3, where the classes with F_c > 0 have no column), RICHARDS, KINEMATIC and LAG: the columns' step-1 outflow equals
    their inflow (1e-6), the saturated share rejected. (Started for q, the columns would drain 120.0 m3 against an inflow
    of 100.8 m3 on step 1: an artificial recharge pulse.)
VI6  a RICHARDS column that cannot carry q: K_VERT 1 mm/d under :SoilZoneVadoseInitialFlux 2: the column
    starts at its backed-up steady profile for the flux it passes (warning "cannot carry the flux"); step 1: storage
    unchanged (1e-9 of the storage), outflow = inflow = K_VERT A, the rest rejected. (The profile for q would have
    positive pressure up to the top: step 1 would drain 0.8 m3 of it, outflow 40.27 against 40.00 m3.)
VI7  a restart without columns from a file that holds them: the combinations.py column case (negative recharge, 3 depth
    classes, LAG) run 4 days writes :GWVadoseClassColumns and :GWVadoseColumnTops; restarted with :SoilZoneVadose NONE
    the run warns that the columns' water is dropped and names the volume, and GWModelSummary.txt reports it ('hotstart
    columns unused'): the volume equals the first run's final 'unsaturated zone storage' (1e-6).
VI8  a restart whose columns have other tops: the same case with RICHARDS, written with :SoilZoneSubgrid 5 and restarted
    with :SoilZoneSubgrid 8. Lines whose column top differs by more than 1 mm do not match (the warning names the column
    top); the restart starts with no more unsaturated water than the file holds (columns of other tops given the written
    water would start with 18.2 m3 from 7.4 m3 written). Restarted with :SoilZoneSubgrid 5 the columns are read and start with the written water (1e-9).
VI9  a restart with another :SoilZoneVadose method: the combinations.py column case (K = 1) written by RICHARDS and read by
    KINEMATIC, and written by KINEMATIC and read by RICHARDS. The methods count the water from different reference profiles
    (the file's :GWVadoseColumns line names the method that wrote it), so the columns start at rest (start storage 0), the
    warning names the writing method and the volume, and the run total 'hotstart columns unused' equals the first run's
    final 'unsaturated zone storage' (5e-6). Read as the contents of the other method, the columns would start with
    +3,669 or -3,628 m3 from 3.7 or 491 m3 written. RICHARDS read by LAG (the same reference) starts with the written water
    (1e-9).
VI10 hotstart lines that match no column: the column case (LAG, K = 1, :SoilZoneVadoseInitialFlux 30) run 4 days, restarted
    with a :SpecifiedHeadBoundary over HRU 1's cells (no exchange link there, so no column): the warning gives the lines
    not used and their volume, the run total 'hotstart columns unused' gives them, and the restart's start storage plus
    that volume equals the file's water (:GWVadoseColumnTops, 1e-6).
VI11 columns of a generated model's cells held as specified heads at the start (a :BoundaryHead series, held on days 1-3;
    the column case, LAG, K = 1, :SoilZoneVadoseInitialFlux 30): no column is built on them, so the start storage equals
    that of the same case with a fixed :SpecifiedHeadBoundary (1e-9), and the first step ends no column on them (its
    recharge onto CHD cells equals the second held step's, 1e-6; columns built there would ship their initial-flux
    profile, about 120 m3, to the specified heads in step 1).
VI12 an existing model's own specified heads (stress periods 3-5, the cells of HRU 1) under the column case (KINEMATIC,
    K = 3): a run restarted on day 4 rebuilds those columns at rest and the first step ends them again; such columns hold
    no water and are not counted: the run total 'columns over specified heads' of the first part (days 1-3) plus that of
    the restarted part equals the continuous run's, columns and volume (1e-6).
VI13 a restart on the day before a :BoundaryHead series holds a generated model's cells again (the column case with CHD, SWX
    and ET; the EDGE series below the aquifer on days 1-3, so columns form on its cells, and near the ground from day 4;
    :SoilZoneVadoseInitialFlux 30; LAG with K = 1, and KINEMATIC with K = 3 and LAGGED timing): the run restarted from day 3's
    solution.rvc builds those columns from its lines and ends them in its first step, their water to the specified heads,
    as the continuous run does: GWBudget.csv from day 4 equals the continuous run's (1e-9), and no hotstart line is unused.
"""
import os, sys, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd

def shift_heads(rvc, dh, out):
    """copy of a solution.rvc with every :GWHeads value moved by dh [m]"""
    L = open(rvc).read().split('\n'); o = []; inb = False
    for l in L:
        if l.startswith(':EndGWHeads'): inb = False
        if inb and l.strip(): l = '  ' + ' '.join('%.12g' % (float(v) + dh) for v in l.split())
        if l.startswith(':GWHeads'): inb = True
        o.append(l)
    open(out, 'w').write('\n'.join(o)); return out
import sz_models, sz_check

tc = sz_check.tc
W = tc.work('soilzone', 'vz_initial')
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')
LIM = dict(sz_check.STD_LIMITS); LIM['vz_identity'] = 1e-8
BASE = dict(nhru=1, hru_w=200.0, width=200.0, cell=100.0, subgrid=5, perc=2.0, ksat=500.0, Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3,
            smooth=0.2, aq_thick=20.0)

def case(name, extra, rvc=None, start=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, extra_rvg=extra, **cfg)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read()
            open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    ok, txt = sz_check.run(d)
    if not ok:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:])); return None
    return d

def check(name, d):
    if d is None: return False
    r = sz_check.checks(d)
    print('  %s: (columns checked from step %d)' % (name, 1 if r.get('vz_step1') else 2))
    return sz_check.report(name, r, {k: v for k, v in LIM.items() if k in r}) and bool(r.get('vz_step1'))

def budget(d): return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
def errs(d):
    f = os.path.join(d, 'out', 'Raven_errors.txt'); return open(f).read() if os.path.exists(f) else ''

def i1():
    print('VI1 steady start')
    days = 10 if QUICK else 30
    ok = True
    for meth, K in (('RICHARDS', 1), ('RICHARDS', 3), ('KINEMATIC', 1), ('LAG', 1)):
        ex = ':SoilZoneVadose %s\n:SoilZoneVadoseClasses %d\n:SoilZoneVadoseInitialFlux 2\n' % (meth, K)
        cfg = dict(BASE, init_depth=6.0, rain=[0.0] * days, days=days, phi0=(200.0, 200.0))
        if K > 1:
            cfg['dem_fn'] = lambda x, y: 0.8 * np.sin(2 * np.pi * (x + 25.0) / 100.0) * np.sin(2 * np.pi * (y + 25.0) / 100.0); cfg['dem_res'] = 400
        d = case('i1_%s_k%d' % (meth, K), ex, **cfg)
        good = check('i1_%s_k%d' % (meth, K), d)
        if d:
            b = budget(d); qin = b['unsaturated zone inflow [m3]'].iloc[0]; qout = b['unsaturated zone to aquifer [m3]'].iloc[0]
            s0 = sz_check.vz_start(d); s = b['unsaturated zone storage [m3]']
            rel = abs(qout - qin) / max(qin, 1e-9); dst = abs(s.iloc[-1] - s0) / max(abs(s0), 1e-9)
            print('    step 1: inflow %.3f m3, outflow %.3f m3 (%.2g); storage %.3f -> %.3f m3 (%.2g)' % (qin, qout, rel, s0, s.iloc[-1], dst))
            good &= (qin > 0) and rel < 1e-6 and s0 > 0     # (later steps: the water table rises under the recharge, no outlet)
        ok &= good
    print('VI1 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i2():
    print('VI2 hotstart taken before any column exists: the initial flux is ignored')
    ex = ':SoilZoneVadose RICHARDS\n:SoilZoneVadoseInitialFlux 2\n'
    first = case('i2_first', ex, **dict(BASE, init_depth=0.5, rain=[0.0] * 5, days=5))
    ok = check('i2_first', first)
    if first:
        rvc = os.path.join(first, 'out', 'solution.rvc'); blk = ':GWVadoseColumns' in open(rvc).read()
        # the second run: water table lowered by moving the heads 3 m down (columns form at once, but the hotstart has none)
        p2 = shift_heads(rvc, -3.0, os.path.join(W, 'i2_low.rvc'))
        sec = case('i2_second', ex, rvc=p2, start='2000-01-06', **dict(BASE, init_depth=0.5, rain=[0.0] * 5, days=5))
        ok &= check('i2_second', sec)
        if sec:
            w = errs(sec); s0 = sz_check.vz_start(sec)
            good = ('ignored' in w) and ('at rest (their reference profile)' in w) and (s0 is not None) and abs(s0) < 1e-9
            print('    first run wrote %s block; second run: warning %s, storage at the start %s m3 -> %s'
                  % ('a' if blk else 'no', 'present' if 'at rest (their reference profile)' in w else 'MISSING', s0, 'ok' if good else 'FAIL'))
            ok &= good
    print('VI2 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i4():
    print('VI4 columns\' balance of step 1 (start line, hotstart, bottoms moving up in step 1)')
    ex = ':SoilZoneVadose RICHARDS\n:SoilZoneVadoseInitialFlux 2\n'
    rain = [0.0] * 3 + [20.0] * 3 + [0.0] * 4
    cfg = dict(BASE, init_depth=4.0, rain=rain, days=len(rain), perc_type='PERC_GAWSER_CONSTRAIN', perc=50.0)
    a = case('i4_a', ex, **cfg); ok = check('i4_a', a)
    if a:
        rvc = os.path.join(a, 'out', 'solution.rvc')
        b = case('i4_hot', ex, rvc=rvc, start='2000-01-11', **cfg); ok &= check('i4_hot', b)
        if b:
            end = budget(a)['unsaturated zone storage [m3]'].iloc[-1]; s0 = sz_check.vz_start(b)
            good = abs(s0 - end) <= 1e-9 * max(abs(end), 1.0)
            print('    start value %.10g m3, previous run\'s end %.10g m3 -> %s' % (s0, end, 'ok' if good else 'FAIL')); ok &= good
        p2 = shift_heads(rvc, 1.0, os.path.join(W, 'i4_up.rvc'))
        c = case('i4_up', ex, rvc=p2, start='2000-01-11', **cfg); ok &= check('i4_up', c)
        if c:
            sm = os.path.join(c, 'out', 'GWModelSummary.txt'); t = open(sm).read(); s0 = sz_check.vz_start(c)
            fl = budget(c)['unsaturated zone to aquifer [m3]'].iloc[0]
            moved = s0 + max(1e-3 * abs(fl), 0.24)
            open(sm, 'w').write(re.sub(r'(unsaturated storage\s*:\s*)\S+', lambda m: m.group(1) + '%.15g' % moved, t))
            v = sz_check.checks(c)['vz_identity']
            print('    step-1 release to the aquifer %.1f m3; a start value moved by %.3g m3 gives vz_identity %.2g -> %s'
                  % (fl, moved - s0, v, 'fails as it must (limit 1e-8)' if v > 1e-5 else 'NOT DETECTED'))
            ok &= v > 1e-5
    print('VI4 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i5():
    print('VI5 steady start for the flux the columns receive, (1 - F) q')
    ok = True
    dem = lambda x, y: 3.0 * np.sin(2 * np.pi * (x + 25.0) / 100.0) * np.sin(2 * np.pi * (y + 25.0) / 100.0)
    for meth, K in (('RICHARDS', 1), ('KINEMATIC', 1), ('LAG', 1)) + ((() if QUICK else (('RICHARDS', 3), ('KINEMATIC', 3), ('LAG', 3)))):
        ex = ':SoilZoneVadose %s\n:SoilZoneVadoseInitialFlux 2\n:SoilZoneVadoseClasses %d\n' % (meth, K)
        cfg = dict(BASE, init_depth=3.0, chd=97.0, Kh=200.0, nhru=2, rain=[0.0] * 3, days=3, phi0=(200.0, 200.0), dem_fn=dem, dem_res=400)
        name = 'i5_%s_k%d' % (meth, K); d = case(name, ex, **cfg)
        good = check(name, d)
        if d:
            b = budget(d); qin = b['unsaturated zone inflow [m3]'].iloc[0]; qout = b['unsaturated zone to aquifer [m3]'].iloc[0]
            rej = b['rejected recharge [m3]'].iloc[0]; rel = abs(qout - qin) / max(qin, 1e-9)
            print('    %s K=%d step 1: inflow %.4f m3, outflow %.4f m3 (%.2g), rejected %.3f m3' % (meth, K, qin, qout, rel, rej))
            good &= qin > 0 and rel < 1e-6 and (K > 1 or rej > 0)
        ok &= good
    print('VI5 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i6():
    print('VI6 RICHARDS steady start beyond the column\'s capacity: the backed-up steady profile')
    ex = ':SoilZoneVadose RICHARDS\n:SoilZoneVadoseInitialFlux 2\n'
    cfg = dict(BASE, init_depth=3.0, Kv=0.001, rain=[0.0] * 3, days=3, phi0=(200.0, 200.0))
    d = case('i6_backed', ex, **cfg); ok = check('i6_backed', d)
    if d:
        b = budget(d); s0 = sz_check.vz_start(d); s1 = b['unsaturated zone storage [m3]'].iloc[0]
        qin = b['unsaturated zone inflow [m3]'].iloc[0]; qout = b['unsaturated zone to aquifer [m3]'].iloc[0]; rej = b['rejected recharge [m3]'].iloc[0]
        A = BASE['hru_w'] * BASE['width']; f = 0.001 * A; q = 0.002 * A               # [m3] over the 1-day step
        w = 'cannot carry the flux of :SoilZoneVadoseInitialFlux' in errs(d)
        good = (s0 is not None and abs(s1 - s0) <= 1e-9 * abs(s0) + 1e-6 and abs(qout - f) <= 1e-6 * f and abs(qin - f) <= 1e-6 * f
                and abs(rej - (q - f)) <= 1e-6 * q and w)
        print('    step 1: storage %.6f -> %.6f m3, inflow %.6f, outflow %.6f m3 (K_VERT A = %.1f), rejected %.6f m3 (want %.1f); warning %s -> %s'
              % (s0 or 0.0, s1, qin, qout, f, rej, q - f, 'present' if w else 'MISSING', 'ok' if good else 'FAIL'))
        ok &= good
    print('VI6 %s' % ('ok' if ok else 'FAIL'))
    return ok

def restart_pair(name, m, K, n1, second_rvg=None):
    """the combinations.py column case (negative recharge) with method m and K classes: n1 days, then restarted (the rest of
    the run) from its solution.rvc with second_rvg(text) applied to the .rvg; returns (first, second, ok)"""
    sys.path.insert(0, os.path.dirname(HERE))
    import combinations as C
    s = dict(sz='PHYS', vz=m, K=K, x={'swx', 'et'}, st={'neg'}, dt=1.0)
    def mk(tag, dur, start):
        d = os.path.join(W, name + tag); shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **C.cfg_of(s)); C.options(d, s)
        p = os.path.join(d, 'm.rvi'); t = re.sub(r':Duration \d+', ':Duration %d' % dur, open(p).read())
        if start: t = t.replace(':StartDate 2000-01-01', ':StartDate ' + start)
        open(p, 'w').write(t)
        return d
    a = mk('_first', n1, None); oka = 'Successful Simulation' in C.run(a)
    b = mk('_second', C.DAYS - n1, '2000-01-%02d' % (n1 + 1))
    if not oka: return a, b, False
    shutil.copy(os.path.join(a, 'out', 'solution.rvc'), os.path.join(b, 'm.rvc'))
    if second_rvg:
        p = os.path.join(b, 'm.rvg'); t = second_rvg(open(p).read()); open(p, 'w').write(t)
    return a, b, 'Successful Simulation' in C.run(b)

def i7():
    print('VI7 restart with :SoilZoneVadose NONE from a file with columns')
    a, b, ok = restart_pair('i7', 'LAG', 3, 4, lambda t: t.replace(':SoilZoneVadose LAG', ':SoilZoneVadose NONE'))
    if not ok: print('  runs FAILED'); return False
    v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); e = errs(b)
    m = re.search(r'hotstart columns unused: (\d+) unsaturated columns of the hotstart file, (\S+) m3', sz_check.summary(b))   # (6 significant digits)
    good = v0 > 0.0 and m is not None and abs(float(m.group(2)) - v0) <= 5e-6 * v0 and 'is dropped' in e and ':SoilZoneVadose NONE' in e
    print('  first run ends with %.3f m3 in its columns; restart: warning %s, run total %s -> %s'
          % (v0, 'present' if 'is dropped' in e else 'MISSING', ('%s lines, %s m3' % (m.group(1), m.group(2))) if m else 'MISSING', 'ok' if good else 'FAIL'))
    return good

def i8():
    print('VI8 restart whose columns have other tops (:SoilZoneSubgrid)')
    a, b, ok = restart_pair('i8', 'RICHARDS', 3, 4, lambda t: t.replace(':SoilZoneSubgrid 5', ':SoilZoneSubgrid 8'))
    a2, b2, ok2 = restart_pair('i8s', 'RICHARDS', 3, 4)
    if not (ok and ok2): print('  runs FAILED'); return False
    v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); s1 = sz_check.vz_start(b); s2 = sz_check.vz_start(b2); e = errs(b)
    good = v0 > 0.0 and s1 is not None and s1 <= v0 * (1.0 + 1e-9) and 'another column top' in e and s2 is not None and abs(s2 - v0) <= 1e-9 * v0
    print('  written %.4f m3; restart with :SoilZoneSubgrid 8 starts with %.4f m3 (warning %s); with :SoilZoneSubgrid 5 %.6f m3 -> %s'
          % (v0, s1 if s1 is not None else float('nan'), 'present' if 'another column top' in e else 'MISSING', s2 if s2 is not None else float('nan'), 'ok' if good else 'FAIL'))
    return good

def restart_ms(name, m1, m2, K, n1, extra='', st=None, post2=None):
    """the combinations.py column case written by method m1 (n1 days) and restarted with method m2"""
    sys.path.insert(0, os.path.dirname(HERE))
    import combinations as C
    def mk(tag, m, dur, start):
        s = dict(sz='PHYS', vz=m, K=K, x={'swx', 'et'} if st is None else set(), st=set(st or ()), dt=1.0)
        d = os.path.join(W, name + tag); shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **C.cfg_of(s)); C.options(d, s)
        if extra: open(os.path.join(d, 'm.rvg'), 'a').write(extra)
        p = os.path.join(d, 'm.rvi'); x = re.sub(r':Duration \d+', ':Duration %d' % dur, open(p).read())
        if start: x = x.replace(':StartDate 2000-01-01', ':StartDate ' + start)
        open(p, 'w').write(x)
        return d, C
    a, C = mk('_first', m1, n1, None); oka = 'Successful Simulation' in C.run(a)
    b, _ = mk('_second', m2, C.DAYS - n1, '2000-01-%02d' % (n1 + 1))
    if not oka: return a, b, False
    shutil.copy(os.path.join(a, 'out', 'solution.rvc'), os.path.join(b, 'm.rvc'))
    if post2: post2(b, C)
    return a, b, 'Successful Simulation' in C.run(b)

def unused(d):
    m = re.search(r'hotstart columns unused: (\d+) unsaturated columns of the hotstart file, (\S+) m3', sz_check.summary(d))
    return (int(m.group(1)), float(m.group(2))) if m else None

def i9():
    print('VI9 a restart with another :SoilZoneVadose method')
    ok = True
    for m1, m2 in (('RICHARDS', 'KINEMATIC'), ('KINEMATIC', 'RICHARDS')):
        a, b, good = restart_ms('i9_%s_%s' % (m1[:3].lower(), m2[:3].lower()), m1, m2, 1, 4, st=())
        if not good: print('  %s -> %s: runs FAILED' % (m1, m2)); ok = False; continue
        v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); s0 = sz_check.vz_start(b); e = errs(b); u = unused(b)
        g = v0 > 0.0 and s0 is not None and abs(s0) <= 1e-9 and ':SoilZoneVadose %s' % m1 in e and 'is dropped' in e and u is not None and abs(u[1] - v0) <= 5e-6 * v0
        print('  written by %s (%.3f m3), read by %s: starts with %s m3, warning %s, run total %s -> %s' % (m1, v0, m2, s0, 'present' if 'is dropped' in e else 'MISSING',
              ('%d lines, %g m3' % u) if u else 'MISSING', 'ok' if g else 'FAIL'))
        ok &= g
    a, b, good = restart_ms('i9_ric_lag', 'RICHARDS', 'LAG', 1, 4, st=())
    if not good: print('  RICHARDS -> LAG: runs FAILED'); return False
    v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); s0 = sz_check.vz_start(b)
    g = s0 is not None and abs(s0 - v0) <= 1e-9 * max(v0, 1.0) and unused(b) is None
    print('  written by RICHARDS (%.4f m3), read by LAG: starts with %.4f m3 -> %s' % (v0, s0 if s0 is not None else float('nan'), 'ok' if g else 'FAIL'))
    return ok and g

def i10():
    print('VI10 hotstart lines that match no column (a specified head added over HRU 1)')
    ex = ':SoilZoneVadoseInitialFlux 30\n'
    def add_chd(d, C):
        C.polygon(os.path.join(d, 'up.geojson'), C.XS - C.HW, C.XS + 0.75 * C.CELL)
        open(os.path.join(d, 'm.rvg'), 'a').write(':SpecifiedHeadBoundary UP up.geojson HEAD %.2f\n' % (C.land(C.XS + 0.5 * C.CELL) - 2.0))
    a, b, good = restart_ms('i10', 'LAG', 'LAG', 1, 4, extra=ex, st=(), post2=add_chd)
    if not good: print('  runs FAILED'); return False
    r = open(os.path.join(a, 'out', 'solution.rvc')).read()
    blk = re.search(r':GWVadoseColumnTops[^\n]*\n([\s\S]*?):End', r).group(1).strip().split('\n')
    vf = sum(float(l.split(',')[4]) for l in blk); s0 = sz_check.vz_start(b); u = unused(b); e = errs(b)
    g = u is not None and u[0] > 0 and s0 is not None and abs(s0 + u[1] - vf) <= 1e-6 * vf and 'no longer exchange links' in e
    print('  file %d lines, %.4f m3; restart starts with %s m3; not used: %s; warning %s -> %s' % (len(blk), vf, s0, ('%d lines, %g m3' % u) if u else 'MISSING',
          'present' if 'no longer exchange links' in e else 'MISSING', 'ok' if g else 'FAIL'))
    return g

def i11():
    print('VI11 no columns on a generated model\'s cells held as specified heads at the start')
    sys.path.insert(0, os.path.dirname(HERE))
    import combinations as C
    res = {}
    for tag, st in (('series', {'bhs'}), ('fixed', set())):
        s = dict(sz='PHYS', vz='LAG', K=1, x={'chd', 'swx'}, st=st, dt=1.0)
        d = os.path.join(W, 'i11_' + tag); shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **C.cfg_of(s)); C.options(d, s)
        open(os.path.join(d, 'm.rvg'), 'a').write(':SoilZoneVadoseInitialFlux 30\n')
        if 'Successful Simulation' not in C.run(d): print('  %s: run FAILED' % tag); return False
        res[tag] = (sz_check.vz_start(d), budget(d)['recharge onto CHD cells [m3/d]'].values)
    (s1, c1), (s2, _) = res['series'], res['fixed']
    g = s1 is not None and s2 is not None and s2 > 0 and abs(s1 - s2) <= 1e-9 * s2 and abs(c1[0] - c1[1]) <= 1e-6 * max(abs(c1[1]), 1.0)
    print('  start storage %.4f (series held) against %.4f m3 (fixed head); recharge onto CHD cells on days 1 and 2 (both held) %.4f, %.4f m3/d -> %s'
          % (s1, s2, c1[0], c1[1], 'ok' if g else 'FAIL'))
    return g

def i12():
    print('VI12 an existing model\'s own specified heads: columns ended over them counted once across a restart')
    sys.path.insert(0, os.path.dirname(HERE))
    import combinations as C
    s = dict(sz='PHYS', vz='KINEMATIC', K=3, x={'swx', 'et'}, st={'reschd'}, dt=1.0)
    g0 = os.path.join(W, 'i12_gen'); shutil.rmtree(g0, ignore_errors=True); sz_models.make_case(g0, **C.cfg_of(s)); C.options(g0, s)
    if 'Successful Simulation' not in C.run(g0): print('  generated twin FAILED'); return False
    def mk(tag, start=None, dur=None, rvc=None):
        e = os.path.join(W, 'i12' + tag); shutil.rmtree(e, ignore_errors=True); C.existing(g0, e, s)
        open(os.path.join(e, 'm.rvg'), 'a').write(':SoilZoneAquiferClass SAND\n')
        p = os.path.join(e, 'm.rvi'); x = open(p).read()
        if dur: x = re.sub(r':Duration \d+', ':Duration %d' % dur, x)
        if start: x = x.replace(':StartDate 2000-01-01', ':StartDate ' + start)
        open(p, 'w').write(x)
        if rvc: shutil.copy(rvc, os.path.join(e, 'm.rvc'))
        return e if 'Successful Simulation' in C.run(e) else None
    def ended(d):
        m = re.search(r'columns over specified heads: (\d+) unsaturated columns ended on cells that were specified heads, their water \((\S+) m3', sz_check.summary(d))
        return (int(m.group(1)), float(m.group(2))) if m else None
    f = mk('_full'); a = mk('_a', dur=3)
    b = mk('_b', start='2000-01-04', dur=C.DAYS - 3, rvc=os.path.join(a, 'out', 'solution.rvc')) if a else None
    if not (f and a and b): print('  runs FAILED'); return False
    nf, na, nb = ended(f), ended(a), ended(b)
    g = None not in (nf, na, nb) and nf[0] > 0 and na[0] + nb[0] == nf[0] and abs(na[1] + nb[1] - nf[1]) <= 1e-6 * max(abs(nf[1]), 1.0)
    print('  continuous %s; first part %s + restarted part %s -> %s' % (nf, na, nb, 'ok' if g else 'FAIL'))
    return g

def i13():
    print('VI13 a restart on the day before a :BoundaryHead series holds a generated model\'s cells again')
    sys.path.insert(0, os.path.dirname(HERE))
    import combinations as C
    ok = True
    for m, K, extra in (('LAG', 1, ''), ('KINEMATIC', 3, ':SoilZoneExchangeTiming LAGGED\n')):
        s = dict(sz='PHYS', vz=m, K=K, x={'chd', 'swx', 'et'}, st={'bho'}, dt=1.0)
        def mk(tag, dur, start):
            d = os.path.join(W, 'i13_%s%d%s' % (m, K, tag)); shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **C.cfg_of(s)); C.options(d, s)
            p = os.path.join(d, 'm.rvt'); t = open(p).read()   # (the EDGE series below the aquifer on days 1-3, then near the ground)
            mm = re.search(r':BoundaryHead EDGE m\n  \S+ \S+ 1.0 (\d+)\n((?:  \S+\n)+):EndBoundaryHead', t)
            v = [float(x) for x in mm.group(2).split()]
            open(p, 'w').write(t.replace(mm.group(2), ''.join('  %.3f\n' % x for x in [min(v)] * 3 + [max(v)] * (len(v) - 3))))
            open(os.path.join(d, 'm.rvg'), 'a').write(':SoilZoneVadoseInitialFlux 30\n' + extra)
            p = os.path.join(d, 'm.rvi'); x = re.sub(r':Duration \d+', ':Duration %d' % dur, open(p).read())
            if start: x = x.replace(':StartDate 2000-01-01', ':StartDate ' + start)
            open(p, 'w').write(x)
            return d
        f, a = mk('_full', C.DAYS, None), mk('_first', 3, None)
        b = mk('_second', C.DAYS - 3, '2000-01-04')
        if not ('Successful Simulation' in C.run(f) and 'Successful Simulation' in C.run(a)): print('  %s: runs FAILED' % m); return False
        shutil.copy(os.path.join(a, 'out', 'solution.rvc'), os.path.join(b, 'm.rvc'))
        if 'Successful Simulation' not in C.run(b): print('  %s: restart FAILED' % m); return False
        A, B = budget(f).iloc[3:].reset_index(drop=True), budget(b)
        cols = [c for c in A.columns if pd.api.types.is_numeric_dtype(A[c]) and not c.startswith('time')]
        dev = max(float(tc.max_diff(A[c], B[c], max(float(A[c].abs().max()), 1.0))) for c in cols)
        c4 = 'recharge onto CHD cells [m3/d]'
        g = len(A) == len(B) and dev <= 1e-9 and unused(b) is None and float(A[c4].iloc[0]) > 0.0
        ok &= g
        print('  %s, K = %d: day 4 recharge onto CHD cells %.4f (continuous) / %.4f m3/d (restart); GWBudget.csv from day 4 %.1e; unused lines %s -> %s'
              % (m, K, A[c4].iloc[0], B[c4].iloc[0], dev, unused(b), 'ok' if g else 'FAIL'))
    return ok

def main():
    tc.need_mf6()
    res = {'VI1': i1(), 'VI2': i2(), 'VI4': i4(), 'VI5': i5(), 'VI6': i6(), 'VI7': i7(), 'VI8': i8(), 'VI9': i9(), 'VI10': i10(), 'VI11': i11(), 'VI12': i12(),
           'VI13': i13()}
    print('results: ' + ', '.join('%s %s' % (k, 'ok' if v else 'FAIL') for k, v in res.items()))
    good = all(res.values())
    print('initial-state tests: ALL PASSED' if good else 'initial-state tests: FAILED')
    return 0 if good else 1

if __name__ == '__main__':
    sys.exit(main())
