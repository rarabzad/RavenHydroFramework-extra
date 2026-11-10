""":SoilZoneVadoseInitialFlux and the columns' initial state (I1-I6).

I1  steady start: columns started at the steady profile for q carry q from the first step, with the start line in
    GWModelSummary.txt ("unsaturated storage : V m3 at the start") and the columns' balance from step 1; with depth classes
    (K = 3) too, and for KINEMATIC and LAG (gwvz::InitSteadyKinematic, the LAG cascade's S_i = q k_i). Enforced: step-1
    outflow = inflow (1e-6) and a positive start storage; the storage change over the run is printed, not enforced (the
    water table rises under the recharge in this closed model, so the columns shorten). A build whose steady start is a
    stub ("not available in this build") gives SKIP.
I2  a hotstart taken before any column exists (water table above the soil-zone base at the end of the first run), the
    second run with the initial flux: the flux is ignored with the warning "... start at rest (their reference profile)",
    no steady profile is put in, identities from step 1.
I4  columns' balance of step 1 (vz_identity from step 1, start value = previous run's end for a hotstart; a hotstart with
    heads +1 m so every bottom moves up in step 1); a deliberately moved start value must fail the check.
I5  the steady start is for the flux each column receives, (1 - F) q: 2 HRUs, hummocks +-3 m, the water
    table 3 m deep held by a specified head (F = 0.16), PERC_CONSTANT 2 mm/d, :SoilZoneVadoseInitialFlux 2, K = 1 (and
    K = 3, where the classes with F_c > 0 have no column), RICHARDS, KINEMATIC and LAG: the columns' step-1 outflow equals
    their inflow (1e-6), the saturated share rejected. (Started for q, the columns drained 120.0 m3 against an inflow of
    100.8 m3 on step 1: an artificial recharge pulse.)
I6  a RICHARDS column that cannot carry q: K_VERT 1 mm/d under :SoilZoneVadoseInitialFlux 2: the column
    starts at its backed-up steady profile for the flux it passes (warning "cannot carry the flux"); step 1: storage
    unchanged (1e-9 of the storage), outflow = inflow = K_VERT A, the rest rejected. (The profile for q had positive
    pressure up to the top: step 1 drained 0.8 m3 of it, outflow 40.27 against 40.00 m3.)
I7  a restart without columns from a file that holds them: the combinations.py column case (negative recharge, 3 depth
    classes, LAG) run 4 days writes :GWVadoseClassColumns and :GWVadoseColumnTops; restarted with :SoilZoneVadose NONE
    the run warns that the columns' water is dropped and names the volume, and GWModelSummary.txt reports it ('hotstart
    columns unused'): the volume equals the first run's final 'unsaturated zone storage' (1e-6). (It was dropped silently:
    507 m3.)
I8  a restart whose columns have other tops: the same case with RICHARDS, written with :SoilZoneSubgrid 5 and restarted
    with :SoilZoneSubgrid 8. Lines whose column top differs by more than 1 mm do not match (the warning names the column
    top); the restart starts with no more unsaturated water than the file holds (it started with 18.2 m3 from 7.4 m3
    written). Restarted with :SoilZoneSubgrid 5 the columns are read and start with the written water (1e-9).
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
if not hasattr(tc, 'skip'):
    tc.skip = lambda what, why: print('SKIP %s: %s' % (what, why))
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
    print('I1 steady start')
    days = 10 if QUICK else 30
    ok = True
    for meth, K in (('RICHARDS', 1), ('RICHARDS', 3), ('KINEMATIC', 1), ('LAG', 1)):
        ex = ':SoilZoneVadose %s\n:SoilZoneVadoseClasses %d\n:SoilZoneVadoseInitialFlux 2\n' % (meth, K)
        cfg = dict(BASE, init_depth=6.0, rain=[0.0] * days, days=days, phi0=(200.0, 200.0))
        if K > 1:
            cfg['dem_fn'] = lambda x, y: 0.8 * np.sin(2 * np.pi * (x + 25.0) / 100.0) * np.sin(2 * np.pi * (y + 25.0) / 100.0); cfg['dem_res'] = 400
        d = case('i1_%s_k%d' % (meth, K), ex, **cfg)
        if d and ('not available in this build' in errs(d)):
            tc.skip('I1 %s steady start' % meth, 'the method\'s steady start is a stub until its solver is merged (columns start at rest)')
            ok &= check('i1_%s_k%d' % (meth, K), d); continue
        good = check('i1_%s_k%d' % (meth, K), d)
        if d:
            b = budget(d); qin = b['unsaturated zone inflow [m3]'].iloc[0]; qout = b['unsaturated zone to aquifer [m3]'].iloc[0]
            s0 = sz_check.vz_start(d); s = b['unsaturated zone storage [m3]']
            rel = abs(qout - qin) / max(qin, 1e-9); dst = abs(s.iloc[-1] - s0) / max(abs(s0), 1e-9)
            print('    step 1: inflow %.3f m3, outflow %.3f m3 (%.2g); storage %.3f -> %.3f m3 (%.2g)' % (qin, qout, rel, s0, s.iloc[-1], dst))
            good &= (qin > 0) and rel < 1e-6 and s0 > 0     # (later steps: the water table rises under the recharge, no outlet)
        ok &= good
    print('I1 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i2():
    print('I2 hotstart taken before any column exists: the initial flux is ignored')
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
    print('I2 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i4():
    print('I4 columns\' balance of step 1 (start line, hotstart, bottoms moving up in step 1)')
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
    print('I4 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i5():
    print('I5 steady start for the flux the columns receive, (1 - F) q')
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
    print('I5 %s' % ('ok' if ok else 'FAIL'))
    return ok

def i6():
    print('I6 RICHARDS steady start beyond the column\'s capacity: the backed-up steady profile')
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
    print('I6 %s' % ('ok' if ok else 'FAIL'))
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
    print('I7 restart with :SoilZoneVadose NONE from a file with columns')
    a, b, ok = restart_pair('i7', 'LAG', 3, 4, lambda t: t.replace(':SoilZoneVadose LAG', ':SoilZoneVadose NONE'))
    if not ok: print('  runs FAILED'); return False
    v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); e = errs(b)
    m = re.search(r'hotstart columns unused: (\d+) unsaturated columns of the hotstart file, (\S+) m3', sz_check.summary(b))   # (6 significant digits)
    good = v0 > 0.0 and m is not None and abs(float(m.group(2)) - v0) <= 5e-6 * v0 and 'is dropped' in e and ':SoilZoneVadose NONE' in e
    print('  first run ends with %.3f m3 in its columns; restart: warning %s, run total %s -> %s'
          % (v0, 'present' if 'is dropped' in e else 'MISSING', ('%s lines, %s m3' % (m.group(1), m.group(2))) if m else 'MISSING', 'ok' if good else 'FAIL'))
    return good

def i8():
    print('I8 restart whose columns have other tops (:SoilZoneSubgrid)')
    a, b, ok = restart_pair('i8', 'RICHARDS', 3, 4, lambda t: t.replace(':SoilZoneSubgrid 5', ':SoilZoneSubgrid 8'))
    a2, b2, ok2 = restart_pair('i8s', 'RICHARDS', 3, 4)
    if not (ok and ok2): print('  runs FAILED'); return False
    v0 = float(budget(a)['unsaturated zone storage [m3]'].iloc[-1]); s1 = sz_check.vz_start(b); s2 = sz_check.vz_start(b2); e = errs(b)
    good = v0 > 0.0 and s1 is not None and s1 <= v0 * (1.0 + 1e-9) and 'another column top' in e and s2 is not None and abs(s2 - v0) <= 1e-9 * v0
    print('  written %.4f m3; restart with :SoilZoneSubgrid 8 starts with %.4f m3 (warning %s); with :SoilZoneSubgrid 5 %.6f m3 -> %s'
          % (v0, s1 if s1 is not None else float('nan'), 'present' if 'another column top' in e else 'MISSING', s2 if s2 is not None else float('nan'), 'ok' if good else 'FAIL'))
    return good

def main():
    tc.need_mf6()
    res = {'I1': i1(), 'I2': i2(), 'I4': i4(), 'I5': i5(), 'I6': i6(), 'I7': i7(), 'I8': i8()}
    print('results: ' + ', '.join('%s %s' % (k, 'ok' if v else 'FAIL') for k, v in res.items()))
    good = all(res.values())
    print('initial-state tests: ALL PASSED' if good else 'initial-state tests: FAILED')
    return 0 if good else 1

if __name__ == '__main__':
    sys.exit(main())
