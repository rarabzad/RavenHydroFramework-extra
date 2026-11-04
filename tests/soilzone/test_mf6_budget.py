"""MODFLOW's budget as Raven books it.

B1  a steady existing model without STO6, :SoilZone PHYSICAL, converged: Raven's residual is MODFLOW's (storage 0; the
    residual sum includes the soil-zone terms: before, the balance error was the whole MF6 recharge, 50 %); B1a no
    "storage flows not accessible ... inferred" warning for such a model, and the S_y 0.2 warning; B1b the same model with
    OUTER_MAXIMUM 3: Raven's residual equals the list file's IN - OUT on every step, and the outer-iteration warning names
    "OUTER_MAXIMUM 3 in the model's IMS file (MODFLOW's MXITER)".
B2  the gross flow is MODFLOW's TOTAL IN + TOTAL OUT (every entry's inflow and outflow apart; a well taking 1e4 m3/d resupplied
    by a specified head gave 1 m3/d with signed package sums): a CONCEPTUAL existing model with a well and OUTER_MAXIMUM 2:
    100 x residual / "MF6 balance error [%]" equals the list file's TOTAL IN + TOTAL OUT on the steps with a residual.
B3  the far-head warning quotes GWBudget's percentage: checked in test_confined_wet W7c/W9, where far heads occur (the B2 run
    holds none; B3 is reported here as passed by reference).
B4  an hourly run: the per-step warnings are dated by the end of the step with its time, as GWBudget.csv ("in the step ending
    2000-01-01 01:00").
B5  an existing model without NEWTON whose specified head (layer 2) lies under a dry top cell: recharge MODFLOW does not apply
    there is booked, the warning names "column(s) whose highest active cell is a specified head", and so does the run total.
B6  :SoilZoneClasses 3 (Raven's wetness classes) on the sibling-column case of test_robustness R20: no round-off is booked as
    negative recharge not held.
B7  tools_audit.py counts both guard warnings: "(MODFLOW unconverged): ... of discharge to Raven withheld for MODFLOW's
    negative residual" (CONCEPTUAL, B2) and "of discharge to Raven
    withheld" (:SoilZone PHYSICAL, robustness R13_b1-like case).
B8  without :SoilZone PHYSICAL, steps MODFLOW does not converge: only MODFLOW's negative
    residual is withheld from the discharge to Raven, nothing else is lost. The CB checker's case (4 HRUs of 400 m, slope
    0.02, 30 mm/d for 5 days then dry, PERC_CONSTANT 20 mm/d, water table 0.2 m deep, CONCEPTUAL,
    :SolverMaxOuterIterations 2: the first 10 steps unconverged; and 1: every step, for the limit of ten warnings): every
    GWBudget row's residual, recharge + storage release
    - seepage to Raven - MF6 balance error, equals max(-balance error, 0) on unconverged steps and 0 on the others; its
    sum over the run equals the run total "discharge withheld" in GWModelSummary.txt; at most ten guard warnings, the
    tenth saying further ones are suppressed. (The earlier cap at the step's inflow left out the storage release: row
    residual 15284 m3/d against a balance error of -1039 m3/d on step 1, 21653 m3 lost unbooked over 10 steps.)
"""
import os, sys, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pandas as pd
import sz_models, sz_check
import test_confined_wet as CW

W = sz_check.tc.work('soilzone', 'mf6budget')
CW.W = W
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')

def lst_budget(d):
    """per time step of the working copy's list file: (TOTAL IN, TOTAL OUT, IN - OUT) rates [model units]"""
    t = open(os.path.join(d, 'out', 'mf6', 'gwf.lst')).read()
    tin = [float(x) for x in re.findall(r'TOTAL IN =\s*\S+\s+TOTAL IN =\s*(\S+)', t)]
    tout = [float(x) for x in re.findall(r'TOTAL OUT =\s*\S+\s+TOTAL OUT =\s*(\S+)', t)]
    io = [float(x) for x in re.findall(r'IN - OUT =\s*\S+\s+IN - OUT =\s*(\S+)', t)]
    return tin, tout, io

def limit(n):
    def edit(m):
        p = os.path.join(m, 'sim.ims'); t = open(p).read(); open(p, 'w').write(re.sub(r'OUTER_MAXIMUM\s+\d+', 'OUTER_MAXIMUM %d' % n, t))
    return edit

def nosto(lim=None):
    def edit(m):
        p = os.path.join(m, 'gwf.oc'); t = open(p).read(); open(p, 'w').write(t.replace('PRINT BUDGET LAST', 'PRINT BUDGET ALL'))
        nam = open(os.path.join(m, 'gwf.nam')).read(); open(os.path.join(m, 'gwf.nam'), 'w').write(re.sub(r'(?im)^\s*STO6.*$', '', nam))
        if lim: limit(lim)(m)
    return edit

HILL = dict(nhru=5, hru_w=200.0, slope=0.01, rain=[8.0] * 6 + [0.0] * 6, days=12, init_depth=1.0, aq_thick=10.0, chd=89.0)

def b1():
    print('B1 a steady existing model without STO6')
    ok = True
    e, good, txt = CW.run_ext('b1_nosto', HILL, edit=nosto())
    if not good: return False
    r = sz_check.checks(e); err = sz_check.errors(e)
    g = r['mf6_err_rel'] <= 1e-5 and 'storage flows not accessible' not in err and '0.2 is assumed' in err
    print('  B1/B1a: balance error / recharge %.2g, "inferred" warning %s, S_y 0.2 warning %s -> %s'
          % (r['mf6_err_rel'], 'WRITTEN' if 'storage flows not accessible' in err else 'none', 'present' if '0.2 is assumed' in err else 'MISSING', 'ok' if g else 'FAIL'))
    ok &= g
    e, good, txt = CW.run_ext('b1b_nosto_mx3', HILL, edit=nosto(3))
    if not good: return False
    b = sz_check.outputs(e)[0]; tin, tout, io = lst_budget(e); err = sz_check.errors(e)
    n = min(len(b), len(io))
    dev = max(abs(b['MF6 balance error [m3/d]'].iloc[i] - io[i]) / max(tin[i] + tout[i], 1.0) for i in range(n)) if n else 1.0
    w = "OUTER_MAXIMUM 3 in the model's IMS file (MODFLOW's MXITER)" in err
    g = n == len(b) and dev < 1e-5 and w
    print('  B1b: %d steps, Raven residual vs list IN - OUT: largest difference %.2g of the gross flow; outer-iteration warning %s; withheld %.1f m3 -> %s'
          % (n, dev, 'present' if w else 'MISSING', b['seepage and soil inflow withheld [m3]'].sum(), 'ok' if g else 'FAIL'))
    return ok & g

FARC = dict(CW.FAR, physical=False)
FARC.pop('chd', None); FARC['chd'] = CW.FAR['chd']

def b2():
    print('B2 the gross flow is MODFLOW\'s TOTAL IN + TOTAL OUT; B3 far-head warnings quote GWBudget; B7 guard count (CONCEPTUAL)')
    fm = CW.far_model(rate=-2000.0, limit=2)
    def edit(m):
        fm(m); p = os.path.join(m, 'gwf.oc'); t = open(p).read(); open(p, 'w').write(t.replace('PRINT BUDGET LAST', 'PRINT BUDGET ALL'))
    e, good, txt = CW.run_ext('b2_conc_mx2', FARC, edit=edit)
    if not good: return False
    b = sz_check.outputs(e)[0]; tin, tout, io = lst_budget(e)
    rows = [(i, 100.0 * b['MF6 balance error [m3/d]'].iloc[i] / b['MF6 balance error [%]'].iloc[i], tin[i] + tout[i])
            for i in range(min(len(b), len(tin))) if abs(b['MF6 balance error [m3/d]'].iloc[i]) > 1e-2 and b['MF6 balance error [%]'].iloc[i] != 0]
    dev = max([abs(g_ - l) / l for _, g_, l in rows] or [0.0])
    g = len(rows) > 1 and dev < 1e-4
    print('  B2: %d steps with a residual, gross flow vs TOTAL IN + TOTAL OUT largest relative difference %.2g (e.g. %.1f vs %.1f m3/d) -> %s'
          % (len(rows), dev, rows[0][1] if rows else 0, rows[0][2] if rows else 0, 'ok' if g else 'FAIL'))
    g3 = True   # (B3: this run holds no far head; the check runs on W7c, test_confined_wet, where the warnings are)
    a = sz_check.tc.audit.audit(e); err = sz_check.errors(e)
    n = err.count('(MODFLOW unconverged): discharge returned to Raven limited') + len(re.findall(r'\(MODFLOW unconverged\): \S+ m3 of discharge to Raven withheld', err))
    g7 = n > 0 and a.get('unconverged-guard warnings') == n
    print('  B7 (CONCEPTUAL): %d guard warnings, tools_audit counts %s -> %s' % (n, a.get('unconverged-guard warnings'), 'ok' if g7 else 'FAIL'))
    return g and g3 and g7

def b4():
    print('B4 an hourly run: warnings dated by the end of the step with its time')
    d, good, txt = CW.run_case('b4_hourly', nhru=5, hru_w=200.0, slope=0.02, rain=24.0, days=1, timestep=1.0 / 24.0, init_depth=0.3,
                               extra_rvg=':SolverMaxOuterIterations 2\n')
    if not good: return False
    err = sz_check.errors(d); b = sz_check.outputs(d)[0]
    dates = re.findall(r'in the step ending (\d{4}-\d\d-\d\d \d\d:\d\d)', err)
    g = len(dates) > 0 and all(x in set(b['date']) for x in dates) and '2000-01-01 01:00' in b['date'].values
    print('  B4: %d dated warnings (first %s), all dates in GWBudget.csv -> %s' % (len(dates), dates[0] if dates else '-', 'ok' if g else 'FAIL'))
    return g

def b5():
    print('B5 without NEWTON: recharge on a column whose highest active cell is a specified head')
    cfg = dict(nhru=5, hru_w=200.0, slope=0.02, top=0.5, rain=5.0, days=6, init_depth=2.0, aq_thick=10.0, physical=False)
    cfg['chd'] = CW.toe(cfg) - 2.0
    def edit(m):
        p = os.path.join(m, 'gwf.chd'); t = open(p).read()
        t = re.sub(r'(?m)^(\s*)1(\s+\d+\s+\d+\s+\S+\s*)$', r'\g<1>2\2', t); open(p, 'w').write(t)
    e, good, txt = CW.run_ext('b5_chd2', cfg, edit=edit, newton=False)
    if not good: return False
    err = sz_check.errors(e); sm = sz_check.summary(e)
    m = re.search(r'(\d+) column\(s\) whose highest active cell is a specified head', err)
    tot = re.search(r'recharge not applied\s*: (\S+) m3 \(columns whose cells were all dry or whose highest active cell is a specified head', sm)
    g = bool(m) and bool(tot) and float(tot.group(1)) > 0
    print('  B5: warning %s; run total %s m3 -> %s' % (m.group(0) if m else 'MISSING', tot.group(1) if tot else 'MISSING', 'ok' if g else 'FAIL'))
    return g

def b6():
    print('B6 :SoilZoneClasses 3: no round-off booked as negative recharge not held')
    GR = {'GR4J_X2': 60.0, 'GR4J_X3': 1.0, 'BASEFLOW_COEFF': 0.5}
    BL = '  :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER\n  :Baseflow BASE_LINEAR SOIL[1] SURFACE_WATER\n  :Baseflow BASE_LINEAR SOIL[0] SURFACE_WATER\n'
    ok = True
    for tim in (('AFTER',) if QUICK else ('AFTER', 'LAGGED')):
        d, good, txt = CW.run_case('b6_sib_cls3_%s' % tim.lower(), nhru=1, hru_w=800.0, width=100.0, aq_thick=2.0, init_depth=1.8, rain=5.0,
                                   days=30, slope=0.02, perc=5.0, extra_proc=BL, extra_soil=GR,
                                   extra_rvg=':SoilZoneClasses 3\n:SoilZoneExchangeTiming %s\n' % tim)
        if not good: ok = False; continue
        nh = sz_check.outputs(d)[0]['negative recharge the soil zone did not hold [m3]']
        tiny = int(((nh > 0) & (nh < 1e-6)).sum())
        print('  B6 %s: not held %.1f m3 on %d steps, of them below 1e-6 m3: %d -> %s' % (tim, nh.sum(), int((nh > 0).sum()), tiny, 'ok' if tiny == 0 else 'FAIL'))
        ok &= tiny == 0 and CW.ident(d, skip=('neg_unheld',))[0]
    return ok

def b7():
    print('B7 tools_audit counts the guard warning of :SoilZone PHYSICAL')
    B10 = dict(nhru=5, hru_w=200.0, slope=0.05, rain=[0.0] * 15 + [150.0] + [0.0] * 4 + [150.0] + [0.0] * 9, days=30, pet=8.0, init_depth=0.0,
               phi0=(10.0, 10.0), Kv=5000.0, Kh=1000.0, Sy=0.001, iteration=(1, 1e-4, 1e-6), extra_rvg=':SolverMaxOuterIterations 12\n')
    d, good, txt = CW.run_case('b7_phys_guard', **B10)
    if not good: return False
    a = sz_check.tc.audit.audit(d); n = sz_check.errors(d).count('of discharge to Raven withheld')
    g = n > 0 and a.get('unconverged-guard warnings') == n
    print('  B7 (PHYSICAL): %d guard warnings, tools_audit counts %s -> %s' % (n, a.get('unconverged-guard warnings'), 'ok' if g else 'FAIL'))
    return g

def b8():
    print('B8 without :SoilZone PHYSICAL, unconverged steps: only MODFLOW\'s negative residual withheld, booked')
    days = 15 if QUICK else 30
    ok = True
    for lim in (2, 1):
        d = os.path.join(W, 'b8_conc_mx%d' % lim); shutil.rmtree(d, ignore_errors=True)
        sz_models.make_case(d, nhru=4, hru_w=400.0, width=400.0, cell=100.0, slope=0.02, rain=[30.0] * 5 + [0.0] * (days - 5), perc=20.0,
                            days=days, init_depth=0.2, physical=False, Kh=5.0, Kv=0.5, extra_rvg=':SolverMaxOuterIterations %d\n' % lim)
        good, txt = sz_check.run(d)
        if not good:
            print('  B8 limit %d: run FAILED\n%s' % (lim, txt[-1500:])); ok = False; continue
        b = sz_check.outputs(d)[0]; err = sz_check.errors(d); sm = sz_check.summary(d)
        others = [c for c in b.columns if c.endswith('[m3/d]') and any(k in c for k in ('river', 'well', 'GHB', 'CHD', 'ET', 'evapo', 'surface-store', 'reservoir'))]
        other = float(b[others].abs().to_numpy().sum()) if others else 0.0
        e = b['MF6 balance error [m3/d]']; unc = b['converged'] == 0
        r = b['MF6 recharge [m3/d]'] + b['storage release [m3/d]'] - b['seepage to Raven [m3/d]'] - e      # [m3/d] the row's residual
        want = (-e).clip(lower=0.0).where(unc, 0.0)
        scale = 1e-8 * (b['MF6 recharge [m3/d]'].abs() + b['storage release [m3/d]'].abs() + b['seepage to Raven [m3/d]'].abs()) + 1e-4
        dev = float(((r - want).abs() - scale).max())
        tot = re.search(r'discharge withheld\s*:\s*(\S+) m3 on (\d+) unconverged steps', sm)
        rows = float((r.where(unc, 0.0) * 1.0).sum())                                                # (daily steps)
        g_tot = (tot is not None) and abs(float(tot.group(1)) - rows) <= 1e-6 * max(rows, 1.0) + 1e-3
        nw = len(re.findall(r'\(MODFLOW unconverged\): \S+ m3 of discharge to Raven withheld', err)) + err.count('discharge returned to Raven limited')
        nwant = int(((e < -1e-6) & unc).sum())
        g_w = (nw == min(nwant, 10)) and ((nwant <= 10) or ('further such warnings suppressed' in err))
        g = int(unc.sum()) >= 5 and other == 0.0 and dev <= 0.0 and g_tot and g_w
        print('  B8 limit %d: %d unconverged steps; step 1: recharge %.1f, storage %.1f, seepage to Raven %.1f, balance error %.1f m3/d, row residual '
              '%.1f m3/d (withheld; want %.1f); largest deviation beyond round-off %.3g m3/d; run total %s m3 (rows %.1f m3); %d guard warnings '
              '(want %d of %d) -> %s'
              % (lim, int(unc.sum()), b['MF6 recharge [m3/d]'].iloc[0], b['storage release [m3/d]'].iloc[0], b['seepage to Raven [m3/d]'].iloc[0], e.iloc[0],
                 r.iloc[0], want.iloc[0], max(dev, 0.0), tot.group(1) if tot else 'MISSING', rows, nw, min(nwant, 10), nwant, 'ok' if g else 'FAIL'))
        ok &= g
    return ok

if __name__ == '__main__':
    names = [a.lower() for a in sys.argv[1:]] or ['b1', 'b2', 'b4', 'b5', 'b6', 'b7', 'b8']
    ok = all([globals()[n]() for n in names])
    print('MODFLOW budget tests: %s' % ('ALL PASSED' if ok else 'FAILED'))
    sys.exit(0 if ok else 1)
