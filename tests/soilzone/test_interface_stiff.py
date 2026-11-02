"""Stiff soil-zone interfaces (docs/design/soil_zone_stiff_interface.md; manual, "Solving soil and aquifer together").

S1  a top aquifer layer of very low vertical conductivity (K_v 0.5 mm/d, the soil-aquifer conductance tiny) under a wet
    spell after a deep start (3 m) that lifts the water table into the soil: the top cell is confined above its top, so
    the recharge (1 - F)R is a valve of very high gain. MODFLOW gets the rejection as a head-dependent term (slope
    R F'(h_c)); before, the interface failed on 5 to 45 of 63 steps with 170 to 350 outer iterations per step (NONE,
    LAG, specified head; with RICHARDS and KINEMATIC the columns carry most of the recharge and the case was easy).
    AFTER and LAGGED timing, :SoilZoneVadose NONE, RICHARDS, KINEMATIC and LAG, depth classes (classes without a column
    reject with their own fraction, inside the same term), and a specified head at the toe. The column runs start 1.5 m
    deep (0.5 m below the soil-zone base): from 3 m the columns carried the spell and the water table stayed 1.3 to 1.5 m
    below the base (F = 0 throughout, the term never active); now it reaches the soil (F up to 1),
    the columns vanish under it and their water and the classes without a column are rejected through the term. Checked:
    largest F > 0.5 and column inflow > 100 m3 (so that the columns carry the start of the spell).
S2  a top layer of S_y 0.02 under :SoilZoneSubgrid 1 (one base point per cell) with water rising into a soil drying
    under PET: the exchange has a kink at the base (nothing rises below it), across which the linear boundary
    overshot and the iteration cycled; it is given to MODFLOW as a drain ending at the base. AFTER and LAGGED, NONE
    (water table 0.5 m into the soil at the start) and RICHARDS (1.5 m deep at the start, 0.5 m below the base: the
    columns take the first rain, vanish as the water table rises into the soil, and the kink regime follows; the run
    must have column inflow, so that it is not the NONE run again).
S3  explicit coupling (:SoilZoneIteration 0) over a thin top layer (0.8 m) on a 3 % egg-crate slope draining to a
    specified head: under NEWTON the head of the dried top cell falls below its bottom (4.8 m on day 1). The supply limit
    of the boundary MODFLOW keeps must hold down to the lowest head the cell can reach (the bottom of the column's lowest
    active cell); limited down to the top cell's bottom only, MODFLOW took 8453 m3/d from a column on day 1, 4.8e3 m3 of
    soil-zone shortfall with every method. NONE, RICHARDS, KINEMATIC, LAG; shortfall 0.
S4  S3 with a tiny interface budget (:SoilZoneIteration 1 and 2, NONE and RICHARDS): the last update the budget allows
    (with :SoilZoneIteration 1 the first update after MODFLOW has converged, with 2 the second) is supply-limited, with the
    rejection's linear term active on wet links. Line and term together may not take more than the column holds down to
    the lowest head the cell can reach (the term was capped down to the top cell's bottom only and on
    top of the line's cap; with the checker's instrumentation the base build's last updates could take up to 792 m3/d
    beyond a column's free water at that head; no step of these runs reaches that head, so the shortfall was 0 on both
    builds). Raven reports the largest such take in GWModelSummary.txt ("supply-limited updates"), which must be 0
    (within 1e-6 m3/d). The runs with a budget of 1 and RICHARDS with 2 must make supply-limited updates
    (1120, 1120 and 40); NONE with a budget of 2 makes none, so its take check is vacuous there and the run
    checks the identities and the shortfall only. What the count does and does not show: it counts every link of every
    supply-limited update, whether or not the limit lowered that link's slope (1120 = 56 steps x 20 links: every step's
    last update), so a non-zero count shows that the limited update was made, not that the limit acted. With NONE the
    interface converges on that update in every step (no unconverged interface step), and the runs with budgets 1 and 2
    give identical outputs (v3m11: every CSV byte-identical): the limit does not change this case's result, and the NONE
    run with a budget of 1 checks only that the supply-limited update keeps the identities, makes no shortfall and
    reports no take beyond the free water; the test prints whether the two NONE runs' outputs are identical (reported,
    not checked: a change there is not a failure). Checks: the identities, no shortfall, that take; the interface may be
    unconverged on some steps (frozen after the budget's updates; on v3m11 RICHARDS 2 steps with a budget of 1 and 1
    with 2, NONE none), which is only reported.
S5  S4's :SoilZoneIteration 1 with a constant percolation of 5 mm/d and PET 5 mm/d from 1 m deep: on the last update the rejection term's slope was capped by its own rejected recharge only; where the free
    water left after the exchange line's take was smaller (the line's own cap then 0) line and term together took up to
    0.35 m3/d more than the column held at the lowest head. The reported take must be 0 (within 1e-6 m3/d), with
    supply-limited updates made.
S6  S3 with an outer-iteration limit of 1 (:SolverMaxOuterIterations 1), :SoilZoneIteration 0 and 1: one outer iteration leaves no interface update, so both are explicit coupling; with :SoilZoneIteration 1 every
    step was reported as an unconverged interface (56 of 56). Checks: the interface converged on every step and the two
    runs' outputs identical (MODFLOW itself is unconverged on such steps, its balance error that of one outer iteration:
    not checked).
S7  outer-iteration limits of 2 and 3 (:SolverMaxOuterIterations) on a quiet hillslope (5 HRUs on a
    5 % slope, no rain, water table 5 m deep): the interface is updated once per step (after the first outer iteration),
    and that update's flow test compared with nothing (the previous total exchange was "infinite"), so every step was
    reported unconverged (10 of 10) and the warning said "a single interface update, no change of the total exchange to
    compare with". Now the single update is compared with the predictor's total exchange. Checks: some steps converged
    (6 of 10 with this build), no warning without a change to compare with, the identities of sz_check (MODFLOW's
    balance error left out: MODFLOW itself does not converge in 2 or 3 outer iterations). The converged steps are the
    ones without any exchange (days 1 to 6: the update leaves the soil levels as the predictor had them); from day 7 the
    aquifer feeds the soil zone (33 to 132 m3/d with a limit of 2, 44 to 130 with 3) and the single update moves the
    soil levels by 0.012 to 0.014 m against the predictor's, more than the head tolerance, so these steps are reported
    unconverged (printed: the converged steps with an exchange). No case was found whose flowing steps
    converge on a single update (tried: shallower water tables, a fixed-head edge, steady initial heads, rain of 2 mm/d:
    soil-level changes of 0.02 to 4.5 m on every step), so S7's count of converged steps rests on the steps without
    exchange. (With a limit of 4 or 5 the interface's
    last update can follow the first outer iteration only if MODFLOW has converged by the second (limit 4) or the third
    (limit 5) outer iteration; when it has not, the step keeps one unverified update and is reported unconverged, as
    before.)
S8  the reason of an unconverged interface: rough-suite case band_e43 (regression R20, test C9) with
    LAG and three depth classes for 67 days, with :SoilZoneIteration 8. On 2000-03-07 the update budget runs out on an
    update whose soil levels and total exchange are within the tolerances but whose connection head lies 2.5 m above
    MODFLOW's head (saturated fraction 0.52 against 0 at the head: the connection test). The warning must name the connection test, its link (HRU and cell) and the two fractions, and say that the
    soil levels and exchange are within the tolerances. The same case with the default budget, where updates follow the
    drops: GWModelSummary.txt's run totals count the drops (connection-test drops) and the drops whose next update in the
    step was the plain one (h_c = h: the link's bracket and last residual dropped.2; before, the
    residual stayed and the next update could form a new bracket with the stale point). Checks: such a warning for the
    step ending 2000-03-07 (the warning is written for the first ten unconverged steps); drops counted, none followed by
    an update with :SoilZoneIteration 8 (the drop is on the last update), all followed by a plain one with the default
    budget; the identities of sz_check.
Checks on every run: the identities of sz_check at round-off (no shortfall), no step with the interface or MODFLOW
unconverged (S4: the interface may be), and (S1, S2) at most ITMAX outer iterations per step on average.
"""
import os, sys, shutil, math, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'stiff')
LIM = dict(sz_check.ID_LIMITS, iface_not_conv=0, mf6_not_conv=0)   # (the standard limits of the identities, no unconverged step)
ITMAX = 12.0
LAGGED = ':SoilZoneExchangeTiming LAGGED\n'
AFTER = ':SoilZoneExchangeTiming AFTER\n'
RAIN = [0.0] * 3 + [20.0] * 30 + [0.0] * 30
S1 = dict(nhru=5, hru_w=200.0, slope=0.02, Kh=1.0, Kv=0.0005, Sy=0.1, init_depth=3.0, aq_thick=10.0, rain=RAIN, days=len(RAIN),
          perc=50.0, ksat=200.0, aq_b=4.0, aq_psia=0.3)
S1C = dict(S1, init_depth=1.5)                                  # (the column runs: 0.5 m below the base at the start)
S2 = dict(S1, init_depth=0.5, Kv=0.2, Kh=2.0, Sy=0.02, subgrid=1, slope=0.05, pet=4.0, rain=[0.0] * 3 + [10.0] * 30 + [0.0] * 30)


QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')   # (quick mode: NONE and RICHARDS, fewer variants)
METHODS = ('RICHARDS',) if QUICK else ('RICHARDS', 'KINEMATIC', 'LAG')

def egg(amp, lam=50.0):
    """an egg-crate relief [m] of amplitude amp and wavelength lam [m] (added to the planar DEM)"""
    return lambda x, y: amp * math.sin(2.0 * math.pi * x / lam) * math.sin(2.0 * math.pi * y / lam)

S3 = dict(nhru=5, hru_w=200.0, slope=0.03, Kh=5.0, Kv=0.5, Sy=0.1, chd=60.0, init_depth=0.9, aq_thick=20.0, rain=10.0, days=20,
          perc=20.0, ksat=200.0, aq_b=4.0, aq_psia=0.3, demf=egg(0.5))

def vz(m, k=1):
    return ':SoilZoneVadose %s\n' % m + (':SoilZoneVadoseClasses %d\n' % k if k > 1 else '')

def cap_excess(d):
    """GWModelSummary.txt run totals: (supply-limited link updates, largest take beyond the free water [m3/d]), or None"""
    t = open(os.path.join(d, 'out', 'GWModelSummary.txt')).read()
    m = re.search(r'supply-limited updates: (\d+) link updates; largest take .* water ([-0-9.e+]+) m3/d', t)
    return (int(m.group(1)), float(m.group(2))) if m else None

def run(name, extra='', need_vz=False, top=None, itmax=ITMAX, need_F=False, need_cap=False, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, extra_rvg=extra, top=top, **cfg)
    good, txt = sz_check.run(d)
    if not good:
        print('  %s: run FAILED\n%s' % (name, txt[-800:])); return False
    b = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
    r = sz_check.checks(d)
    ok = sz_check.report(name, r, {k: v for k, v in LIM.items() if k in r})
    it = float(b['outer iterations'].mean())
    g = it <= itmax
    if itmax < 1e8:
        print('  %-34s %-12.3g %s (limit %g)' % ('outer iterations per step', it, 'ok' if g else 'FAIL', itmax))
    ok &= g
    if need_vz:
        v = float(b['unsaturated zone inflow [m3]'].sum()) if 'unsaturated zone inflow [m3]' in b else 0.0
        print('  %-34s %-12.4g %s (at least 100)' % ('column inflow [m3]', v, 'ok' if v > 100 else 'FAIL')); ok &= v > 100
    if need_F:
        s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv')); F = float(s['saturated fraction [-]'].max())
        print('  %-34s %-12.4g %s (above 0.5)' % ('largest saturated fraction', F, 'ok' if F > 0.5 else 'FAIL')); ok &= F > 0.5
    if need_cap:
        c = cap_excess(d)
        g = (c is not None) and (c[1] <= 1e-6) and ((need_cap != 'updates') or c[0] > 0)
        print('  %-34s %s %s' % ('supply-limited updates, take', c, 'ok' if g else 'FAIL')); ok &= g
    return ok

def s1():
    print('S1 low-Kv top layer: the rejection as a head-dependent term')
    ok = True
    for tim in ((LAGGED,) if QUICK else (AFTER, LAGGED)):
        t = 'after' if tim == AFTER else 'lagged'
        ok &= run('s1_%s_none' % t, tim, need_F=True, **S1)
        for m in METHODS:
            ok &= run('s1_%s_%s' % (t, m.lower()), tim + vz(m), need_vz=True, need_F=True, **S1C)
        if not QUICK:
            ok &= run('s1_%s_richards_k3' % t, tim + vz('RICHARDS', 3), need_vz=True, need_F=True, **S1C)
            ok &= run('s1_%s_chd' % t, tim, need_F=True, **dict(S1, chd=88.5))
    return ok

def s2():
    print('S2 S_y 0.02, one base point per cell: the kink drain')
    ok = True
    for tim in ((LAGGED,) if QUICK else (AFTER, LAGGED)):
        t = 'after' if tim == AFTER else 'lagged'
        ok &= run('s2_%s_none' % t, tim, **S2)
        ok &= run('s2_%s_richards' % t, tim + vz('RICHARDS'), need_vz=True, **dict(S2, init_depth=1.5))
    return ok

def s3():
    print('S3 explicit coupling over a thin top layer: supply limit down to the lowest active cell bottom')
    global LIM
    keep = LIM; LIM = dict(sz_check.ID_LIMITS, mf6_not_conv=0)
    try:
        ok = True
        for m in ('NONE',) + METHODS:
            ok &= run('s3_%s' % m.lower(), ':SoilZoneIteration 0\n' + (vz(m) if m != 'NONE' else ''), top=0.8, itmax=1e9, **S3)
        return ok
    finally:
        LIM = keep

def s4():
    print('S4 a tiny interface budget: the supply-limited last update, line and term within the free water')
    global LIM
    keep = LIM; LIM = dict(sz_check.ID_LIMITS, mf6_not_conv=0)
    ok = True
    try:
        for m in ('NONE', 'RICHARDS'):
            a, b = os.path.join(W, 's4_it1_%s' % m.lower()), os.path.join(W, 's4_it2_%s' % m.lower())
            ex = vz(m) if m != 'NONE' else ''
            ok &= run('s4_it1_%s' % m.lower(), ':SoilZoneIteration 1\n' + ex, top=0.8, itmax=1e9, need_cap='updates', **S3)
            ok &= run('s4_it2_%s' % m.lower(), ':SoilZoneIteration 2\n' + ex, top=0.8, itmax=1e9,
                      need_cap=('updates' if m != 'NONE' else True), **S3)
            if not (os.path.exists(os.path.join(a, 'out', 'GWBudget.csv')) and os.path.exists(os.path.join(b, 'out', 'GWBudget.csv'))):
                continue
            diff = sz_check.same_outputs(a, b)
            nu = [int((pd.read_csv(os.path.join(x, 'out', 'GWBudget.csv'))['interface converged'] == 0).sum()) for x in (a, b)]
            print('  S4 %s: interface unconverged on %d / %d steps with budgets 1 / 2; outputs %s (reported, not checked)'
                  % (m, nu[0], nu[1], 'identical' if not diff else 'differ (%s)' % ', '.join(diff)))
    finally:
        LIM = keep
    return ok

def s5():
    print('S5 the last update\'s rejection term within the free water the exchange line leaves')
    global LIM
    keep = LIM; LIM = dict(sz_check.ID_LIMITS, mf6_not_conv=0)
    try:
        return run('s5_iter1', ':SoilZoneIteration 1\n', top=0.8, itmax=1e9, need_cap='updates',
                   **dict(S3, perc_type='PERC_CONSTANT', perc=5.0, pet=5.0, init_depth=1.0))
    finally:
        LIM = keep

def s6():
    print('S6 an outer-iteration limit of 1 is explicit coupling')
    global LIM
    keep = LIM; LIM = dict({k: v for k, v in sz_check.ID_LIMITS.items() if k != 'mf6_err_rel'}, iface_not_conv=0)
    try:
        ok = True
        for it in (0, 1):
            ok &= run('s6_it%d' % it, ':SoilZoneIteration %d\n:SolverMaxOuterIterations 1\n' % it, top=0.8, itmax=1e9, **S3)
    finally:
        LIM = keep
    bad = sz_check.same_outputs(os.path.join(W, 's6_it0'), os.path.join(W, 's6_it1'), skip=())
    print('  S6: outputs of :SoilZoneIteration 0 and 1 identical: %s' % ('ok' if not bad else 'FAIL (%s)' % ', '.join(bad)))
    return ok and not bad

def s7():
    print('S7 a single interface update per step (outer-iteration limits 2 and 3) is compared with the predictor')
    ok = True
    for mx in (2, 3):
        d = os.path.join(W, 's7_mx%d' % mx); shutil.rmtree(d, ignore_errors=True)
        sz_models.make_case(d, nhru=5, hru_w=200.0, width=200.0, cell=100.0, slope=0.05, rain=0.0, perc=0.0, days=10,
                            init_depth=5.0, aq_thick=20.0, extra_rvg=':SolverMaxOuterIterations %d\n' % mx)
        good, txt = sz_check.run(d)
        if not good:
            print('  S7 (limit %d): run FAILED\n%s' % (mx, txt[-600:])); ok = False; continue
        b = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
        e = open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
        nconv = int((b['interface converged'] == 1).sum()); single = 'no change of the total exchange to compare with' in e
        flow = (b['aquifer to soil zone [m3/d]'].abs() + b['soil zone to aquifer [m3/d]'].abs()) > 0.0
        nflow = int(((b['interface converged'] == 1) & flow).sum())
        g = nconv >= 1 and not single
        print('  S7 (limit %d): interface converged on %d of %d steps (at least 1; of them with an exchange: %d, reported), warning without a change to compare with: %s -> %s'
              % (mx, nconv, len(b), nflow, 'WRITTEN' if single else 'none', 'ok' if g else 'FAIL'))
        r = sz_check.checks(d)
        ok &= sz_check.report('S7 (limit %d)' % mx, r, {k: v for k, v in sz_check.ID_LIMITS.items() if k in r and k != 'mf6_err_rel'}) and g
    return ok

def s8():
    print('S8 the warning of an interface left unconverged by the connection test names that test and its link; the update after a drop is plain')
    try:
        import test_rough_terrain as T, rough_models as rm
        S = T.load_case('band_e43')
    except Exception as x:   # (the rough-terrain suite and its stored cases are not part of this test)
        sz_check.tc.skip('S8', 'rough-terrain suite (test_rough_terrain.py, rough_cases/band_e43.json) not available: %s' % x)
        return True
    if QUICK:
        sz_check.tc.skip('S8', 'quick mode (67-day LAG run with three depth classes)')
        return True
    ok = True
    for tag, extra in (('it8', ':SoilZoneIteration 8\n'), ('default', '')):
        d = os.path.join(W, 's8_band_e43_' + tag); shutil.rmtree(d, ignore_errors=True)
        rm.build(d, S, 'LAG', 3, days=67, extra_rvg=extra)
        good, txt = sz_check.run(d, timeout=1800)
        if not good:
            print('  S8 (%s): run FAILED\n%s' % (tag, txt[-600:])); ok = False; continue
        summ = open(os.path.join(d, 'out', 'GWModelSummary.txt')).read()
        m = re.search(r'connection-test drops : (\d+) link updates on (\d+) steps .*; next update plain on (\d+),', summ)
        nd, ns, npl = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (None, None, None)
        if tag == 'it8':
            e = open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
            w = [l for l in e.split('\n') if 'soil-zone interface did not converge in the step ending 2000-03-07' in l]
            m = re.search(r"connection head ([-0-9.e+]+) m from MODFLOW's head at HRU (\d+) in cell \(([^)]*)\) \(saturated fraction ([-0-9.e+]+) against ([-0-9.e+]+)", w[0]) if w else None
            g = bool(m) and 'are within the tolerances' in w[0] and float(m.group(1)) > 0.5 and abs(float(m.group(4)) - float(m.group(5))) > 1e-6
            print('  S8 (it8): warning for 2000-03-07: %s -> %s' % (w[0].split('(', 1)[1][:260] if w else 'none', 'ok' if g else 'FAIL'))
            # (the drop is on the budget's last update: no update follows it)
            g2 = nd is not None and nd > 0 and npl == 0
        else:
            g = True
            # (with the default budget an update follows every drop, and it is the plain one: the link's bracket and its
            # last residual are dropped)
            g2 = nd is not None and nd > 0 and npl == nd
        print('  S8 (%s): connection-test drops %s on %s steps, next update plain on %s -> %s' % (tag, nd, ns, npl, 'ok' if g2 else 'FAIL'))
        r = sz_check.checks(d)
        ok &= sz_check.report('S8 (%s)' % tag, r, {k: v for k, v in sz_check.ID_LIMITS.items() if k in r}) and g and g2
    return ok

if __name__ == '__main__':
    if len(sys.argv) > 1:                       # (only the named tests, e.g. S5 S6)
        ok = all([globals()[a.lower()]() for a in sys.argv[1:]])
        print('stiff interface tests: %s' % ('ALL PASSED' if ok else 'FAILED'))
        sys.exit(0 if ok else 1)
    ok = s1() & s2() & s3() & s4() & s5() & s6() & s7() & s8()
    print('stiff interface tests: %s' % ('ALL PASSED' if ok else 'FAILED'))
    sys.exit(0 if ok else 1)