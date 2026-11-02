"""Robustness of :SoilZone PHYSICAL (cases found by the code inspections).

R1 stiff flat column: drainable porosity 0.02 against S_y = 0.25 and a high conductance; the water table rises to the
   base and the soil zone fills. The interface and MODFLOW converge on every step in few updates (a connection that
   opened only above the base left MODFLOW's top cell confined there and the iteration cycled).
R2 one HRU over ten cells against ten one-cell HRUs (same hillslope and forcing): rain falls alike on every column
   (overflowing where full), percolation stays in its column, and the recharge leaves the columns as the process takes
   it, so the hillslope's total outflow agrees within 3% and MODFLOW's recharge within a factor 1.6 (sharing recharge
   and gains by area / by room moved water up the slope: outflow -36%, recharge x2.3); R2c the same with constant-rate
   percolation (outflow within 3%, recharge within 20%).
R3 RECHARGE_DELAY with :SoilZone PHYSICAL is refused with a clear message.
R4 a smoothing depth below 0.1 m is reported.
R5 hourly steps with a 0.001 m smoothing depth: the interface is frozen for MODFLOW's last outer iterations, so no step
   ends with a MODFLOW residual.
R6 a steep hillslope (slope 0.1) with 5x5 DEM samples per cell converges on every step.
R7 explicit mode (:SoilZoneIteration 0): the boundary never drains more than a column holds (no shortfall).
R8 a column 1e-6 mm wetter than the others does not attract the HRU's recharge (the heads stay uniform).
R9 hotstart columns that cannot hold the .rvc layer split (wet columns with a full lower layer, Raven's lower layer 50 mm
   wetter): the percolation no column can take stays in the upper layer and is reported in step 1 (layer
   redistribution 50 mm over the HRU).
R10 water rising into a thin soil on a steep, low-storage hillslope with an update budget of 1 and in explicit mode:
   the boundary MODFLOW keeps never takes more from a column than it holds (no shortfall). A slope kept at the secant
   to the end of the contact let the frozen boundary reverse when the head fell and drain empty columns (4100 m3 created with a budget of 1, 7900 m3 in explicit mode).
R11 explicit mode on the R2 hillslope (ten HRUs) gives the iterated run's total outflow within 3%: the kept boundary
   neither reverses nor lifts water from below the contact (a line there was 30-50% off).
R12 explicit mode with 15 outer iterations where water rises into cells that are dry at the head of linearization
   (steep hillslope draining to a specified head near the surface): MODFLOW converges and the outflow is the iterated
   run's within 3% (a drain inactive at that head let MODFLOW's head run away: 10^7 m3/d booked).
R13 a stiff, very low-storage hillslope with an update budget of 1 and 12 outer iterations, on which MODFLOW does not
   converge: neither MODFLOW's residual nor the soil-zone shortfall is handed to Raven, so the outflow stays within 1.5 times the iterated run's (it was
   17 times).
R14 (N1) negative recharge: :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER with GR4J_X2 3 mm/d (Raven's processes take water
   out of GROUNDWATER) on an egg-crate hillslope, NONE and RICHARDS (all methods in the full mode, and three depth classes): it
   is never split by the saturated fraction, all of it goes to MODFLOW; identities and Raven's balance at round-off (a
   negative rejection booked with Fill created water in the soil).
R15 (N2) negative recharge limited by what the top cell can give: a 2 m aquifer 2.5 m deep, 40 dry days, slope 0.03, no
   specified head: the cut goes back to the soil zone (run total "negative recharge cut"); the run completes (before: head
   -10 586 m, "diverged").
R16 (N3) the hand-back of a column's outputs with one depth class follows the link's own fraction:
   a RICHARDS run with negative recharge and rain; identities at round-off.
R17 (N4) not held: the N2 import with the soil drained in the same step by :Baseflow BASE_LINEAR from SOIL[1] and SOIL[0]
   after the import: the cut the soil zone does not hold is booked as "negative recharge the soil zone did not hold" (own
   column, warning, run total), soil-zone shortfall 0, identities; :SoilZoneExchangeTiming AFTER books it too (the process
   after the import, not the lagged timing, is the cause).
R18 (N5) an existing model without NEWTON (CONCEPTUAL) whose cells the negative recharge dries: booked (signed, negative) as
   recharge not applied by MODFLOW, the warning keeps the sign and says the water held by the dried cells is in neither
   balance; R18c the same with confined cells (ICELLTYPE 0): they never dry, MODFLOW applies all of it, nothing booked as
   not applied.
R19 (N7) RICHARDS with three depth classes drawing upflow from a nearly empty top cell (R17 setup): all steps converged, no
   head far outside the model (the column took 16.4 m3/d from a cell that could give 2.6e-9).
R20 (N6) sibling columns: one HRU over 8 cells, BASEFLOW_COEFF 0.5, a 2 m aquifer from 1.8 m deep, 30 days, AFTER and LAGGED:
   "not held" is booked only on steps whose HRU soil zone is empty (the cut is first taken from the HRU's other columns) and no round-off is booked.
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'robustness')

def case(name, **kw):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **kw)
    return d

def outflow(d, dt=1.0):
    import pandas as pd
    hy = pd.read_csv(os.path.join(d, 'out', 'Hydrographs.csv'))
    fc = [x for x in hy.columns if '[m3/s]' in x and 'precip' not in x.lower()]
    return float(hy[fc[0]].iloc[1:].sum() * 86400.0 * dt)

def errors(d):
    p = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(p).read() if os.path.exists(p) else ''

def main():
    res = []
    d = case('R1', nhru=1, n=0.04, sfc=0.5, Sy=0.25, rain=20, perc=20, days=60, init_depth=1.2, ksat=1000, Kv=10)
    ok, _ = sz_check.run(d)
    g = False
    if ok:
        r = sz_check.checks(d); b = sz_check.outputs(d)[0]
        g = r['iface_not_conv'] == 0 and r['mf6_not_conv'] == 0 and r['max_updates'] <= 20 and r['sz_identity'] < 1e-8
        print('  R1: interface not converged %d, MODFLOW not converged %d, max updates %d, max outer iterations %d'
              % (r['iface_not_conv'], r['mf6_not_conv'], r['max_updates'], int(b['outer iterations'].max())))
    res.append(('R1 stiff column converges', g))

    WET = [10.0] * 60 + [0.0] * 60
    hill = dict(width=200.0, cell=100.0, Kh=50.0, Kv=1.0, ksat=1000.0, perc=1000.0, perc_type='PERC_GAWSER_CONSTRAIN',
                rain=WET, days=len(WET), slope=0.01, subgrid=3, smooth=0.2, init_depth=1.0)
    out = {}
    for name, kw in (('R2_one', dict(nhru=1, hru_w=1000.0)), ('R2_ten', dict(nhru=10, hru_w=100.0))):
        c = dict(hill); c.update(kw); d = case(name, **c)
        ok, _ = sz_check.run(d)
        if ok:
            b = sz_check.outputs(d)[0]; r = sz_check.checks(d)
            out[name] = (outflow(d), b['MF6 recharge [m3/d]'].sum(), r['iface_not_conv'])
    g = False
    if len(out) == 2:
        (o1, m1, n1), (o2, m2, n2) = out['R2_one'], out['R2_ten']
        g = abs(o1 - o2) <= 0.03 * o2 and 1 / 1.6 <= m1 / m2 <= 1.6 and n1 == 0 and n2 == 0
        print('  R2: outflow %.0f vs %.0f m3 (%.1f%%), MF6 recharge %.0f vs %.0f m3 (ratio %.2f)'
              % (o1, o2, 100 * (o1 - o2) / o2, m1, m2, m1 / m2))
    res.append(('R2 one HRU over ten cells = ten HRUs', g))
    out = {}
    for name, kw in (('R2c_one', dict(nhru=1, hru_w=1000.0)), ('R2c_ten', dict(nhru=10, hru_w=100.0))):
        c = dict(hill); c.update(kw); c.update(perc_type='PERC_CONSTANT', perc=5.0); d = case(name, **c)
        ok, _ = sz_check.run(d)
        if ok:
            b = sz_check.outputs(d)[0]
            out[name] = (outflow(d), b['MF6 recharge [m3/d]'].sum())
    g = False
    if len(out) == 2:
        (o1, m1), (o2, m2) = out['R2c_one'], out['R2c_ten']
        g = abs(o1 - o2) <= 0.03 * o2 and 1 / 1.2 <= m1 / m2 <= 1.2
        print('  R2c (constant percolation 5 mm/d): outflow %.0f vs %.0f m3 (%.1f%%), MF6 recharge %.0f vs %.0f m3'
              % (o1, o2, 100 * (o1 - o2) / o2, m1, m2))
    res.append(('R2c same with constant-rate percolation', g))

    d = case('R3', days=3)
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    t = t.replace('SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH\n', 'SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH, RECHARGE_DELAY\n')
    t = t.replace('  :Units, m, m, 1/d, m\n', '  :Units, m, m, 1/d, m, d\n')
    lines = t.split('\n'); i = [k for k, l in enumerate(lines) if l.startswith('  AQ, ')][-1]; lines[i] += ', 10'
    open(p, 'w').write('\n'.join(lines))
    ok, txt = sz_check.run(d)
    res.append(('R3 RECHARGE_DELAY refused', (not ok) and 'RECHARGE_DELAY' in (txt + errors(d)) and 'cannot be used with :SoilZone PHYSICAL' in (txt + errors(d))))

    d = case('R4', days=3, smooth=0.01)
    ok, _ = sz_check.run(d)
    res.append(('R4 small smoothing depth reported', ok and 'SEEPAGE_SMOOTHING_DEPTH' in errors(d) and 'almost abruptly' in errors(d)))

    WET = [10.0] * 60 + [0.0] * 60
    hill2 = dict(nhru=10, hru_w=100.0, width=200.0, cell=100.0, Kh=50.0, Kv=1.0, ksat=1000.0, perc=1000.0,
                 perc_type='PERC_GAWSER_CONSTRAIN', slope=0.01, subgrid=3, smooth=0.2)
    c = dict(hill2); c.update(timestep=1 / 24.0, smooth=0.001, subgrid=5, init_depth=0.5, rain=[10.0] * 15 + [0] * 15, days=30)
    d = case('R5', **c); ok, _ = sz_check.run(d)
    g = False
    if ok:
        r = sz_check.checks(d, dt=1 / 24.0)
        g = r['mf6_not_conv'] == 0 and r['mf6_err_rel'] < 1e-5 and r['sz_identity'] < 1e-8 and r['rch_identity'] < 5e-9 and r['shortfall'] < 1e-6
        print('  R5: hourly, smoothing 0.001 m: MODFLOW not converged %d, interface not converged %d, MF6 error %.2g'
              % (r['mf6_not_conv'], r['iface_not_conv'], r['mf6_err_rel']))
    res.append(('R5 no MODFLOW residual left by late updates', g))

    c = dict(hill2); c.update(rain=WET, days=len(WET), subgrid=5, slope=0.1, init_depth=1.0, Kh=5.0)
    d = case('R6', **c); ok, _ = sz_check.run(d)
    g = False
    if ok:
        r = sz_check.checks(d)
        g = r['iface_not_conv'] == 0 and r['mf6_not_conv'] == 0 and r['sz_identity'] < 1e-8
        print('  R6: slope 0.1, 5x5 samples: interface not converged %d, max updates %d' % (r['iface_not_conv'], r['max_updates']))
    res.append(('R6 steep sub-grid hillslope converges', g))

    d = case('R7', nhru=4, hru_w=100.0, n=0.1, Sy=0.2, smooth=0.2, subgrid=3, rain=([20.0] * 10 + [0.0] * 10) * 2, days=40,
             perc=20, ksat=1e4, Kv=10, slope=0.02, init_depth=1.1, chd=100 - 0.02 * 400 - 1.0, iteration=(0, 1e-4, 1e-6),
             extra_rvg=':SolverMaxOuterIterations 20\n')
    ok, _ = sz_check.run(d)
    g = False
    if ok:
        r = sz_check.checks(d)
        g = r['shortfall'] < 1e-6 and r['sz_identity'] < 1e-8
        print('  R7: explicit predictor: shortfall %.3g m3' % r['shortfall'])
    res.append(('R7 explicit mode never drains more than the column holds', g))

    # R8: a column 1e-6 mm wetter than the others must not attract the HRU's recharge
    import re
    c8 = dict(nhru=1, hru_w=400.0, width=200.0, cell=100.0, slope=0.0, Kh=1.0, Kv=1.0, ksat=500.0, perc=1000.0,
              perc_type='PERC_GAWSER_CONSTRAIN', subgrid=3, smooth=0.2, init_depth=5.0, rain=[0.0] * 2, days=2)
    d0 = case('R8_pre', **c8); ok0, _ = sz_check.run(d0)
    g = False
    if ok0:
        rvc = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        blk = re.search(r'(:GWSoilZoneColumns[^\n]*\n)(.*?)(:EndGWSoilZoneColumns)', rvc, re.S)
        rows = [l for l in blk.group(2).split('\n') if l.strip()]
        new = []
        for i, l in enumerate(rows):
            p = [x.strip() for x in l.split(',')]
            p[2] = '%.15f' % (100.0 + (1e-6 if i == 0 else 0.0)); p[3] = '100.0'
            new.append('  ' + ', '.join(p))
        rvc = rvc.replace(blk.group(2), '\n'.join(new) + '\n')
        c8.update(rain=[10.0] * 20, days=20)
        d = case('R8', **c8)
        open(os.path.join(d, 'm.rvc'), 'w').write(rvc)
        for f in ('m.rvi', 'm.rvt'):
            t = open(os.path.join(d, f)).read(); open(os.path.join(d, f), 'w').write(t.replace('2000-01-01 00:00:00', '2000-01-03 00:00:00'))
        open(os.path.join(d, 'm.rvg'), 'a').write(':HeadSaveFrequency 1\n')
        ok, _ = sz_check.run(d)
        if ok:
            import flopy, numpy as np
            hf = flopy.utils.HeadFile(os.path.join(d, 'out', 'mf6', 'gwf.hds')); h = hf.get_data(totim=hf.get_times()[-1]).ravel()
            h = h[np.abs(h) < 1e20]
            g = (h.max() - h.min()) < 0.001
            print('  R8: head spread after 20 days of rain with one column 1e-6 mm wetter: %.2e m' % (h.max() - h.min()))
    res.append(('R8 recharge shares insensitive to round-off', g))

    # R9: hotstart redistribution is reported in the first step
    g = False
    if ok0:
        rvc = open(os.path.join(d0, 'out', 'solution.rvc')).read()
        blk = re.search(r'(:GWSoilZoneColumns[^\n]*\n)(.*?)(:EndGWSoilZoneColumns)', rvc, re.S)
        new = []
        for l in blk.group(2).split('\n'):
            if not l.strip(): continue
            p = [x.strip() for x in l.split(',')]
            v = 200.0 if p[1] in ('6', '7', '8', '9') else (100.0 if p[1] == '0' else 0.0)
            p[2] = p[3] = '%g' % v; new.append('  ' + ', '.join(p))
        rvc = rvc.replace(blk.group(2), '\n'.join(new) + '\n')
        rvc = re.sub(r'(\n  1,(?:[0-9.]+,){5})[0-9.]+,[0-9.]+,', r'\g<1>50.0,150.0,', rvc)
        c9 = dict(c8); c9.update(rain=[0.0] * 3, days=3)
        d = case('R9', **c9)
        open(os.path.join(d, 'm.rvc'), 'w').write(rvc)
        for f in ('m.rvi', 'm.rvt'):
            t = open(os.path.join(d, f)).read(); open(os.path.join(d, f), 'w').write(t.replace('2000-01-01 00:00:00', '2000-01-03 00:00:00'))
        ok, _ = sz_check.run(d)
        if ok:
            b = sz_check.outputs(d)[0]; mv = b['soil-zone layer redistribution [m3]'].values
            A = 400.0 * 200.0
            g = abs(mv[0] - 0.05 * A) < 1e-6 * A and abs(mv[1:]).max() < 1e-9 and sz_check.checks(d)['sz_identity'] < 1e-8
            print('  R9: hotstart layer redistribution in step 1: %.1f m3 (expected %.1f), later steps %.2g m3' % (mv[0], 0.05 * A, abs(mv[1:]).max()))
    res.append(('R9 hotstart redistribution reported in step 1', g))

    B10 = dict(nhru=4, hru_w=100.0, H0=0.1, H1=0.1, n=0.1, sfc=0.3, ksat=1e4, perc=1e3, Sy=0.01, Kh=200.0, Kv=50.0,
               slope=0.05, aq_thick=3.0, init_depth=0.05, smooth=0.3, subgrid=3, days=30, rain=([60.0] * 2 + [0.0] * 8) * 3)
    g = True; msg = []
    for name, it in (('R10_b1', (1, 1e-4, 1e-6)), ('R10_x', (0, 1e-4, 1e-6))):
        c = dict(B10); c.update(iteration=it); d = case(name, **c)
        ok, _ = sz_check.run(d)
        if not ok: g = False; msg.append('%s failed' % name); continue
        r = sz_check.checks(d)
        g = g and r['shortfall'] < 1e-6 and r['sz_identity'] < 1e-8 and r['mf6_not_conv'] == 0
        msg.append('%s shortfall %.3g m3' % (name, r['shortfall']))
    print('  R10: ' + ', '.join(msg))
    res.append(('R10 frozen / explicit boundary never overdraws', g))

    out = {}
    for name, it in (('R11_it', None), ('R11_x', (0, 1e-4, 1e-6))):
        c = dict(hill); c.update(nhru=10, hru_w=100.0)
        if it: c.update(iteration=it)
        d = case(name, **c); ok, _ = sz_check.run(d)
        if ok and sz_check.checks(d)['shortfall'] < 1e-6: out[name] = outflow(d)
    g = len(out) == 2 and abs(out['R11_x'] - out['R11_it']) <= 0.03 * out['R11_it']
    if len(out) == 2:
        print('  R11: explicit outflow %.0f m3 vs iterated %.0f m3 (%.1f%%)' % (out['R11_x'], out['R11_it'], 100 * (out['R11_x'] - out['R11_it']) / out['R11_it']))
    res.append(('R11 explicit mode close to the iterated run', g))

    out = {}; mf = {}
    for name, it, ex in (('R12_it', (100, 1e-4, 1e-6), ''), ('R12_x', (0, 1e-4, 1e-6), ':SolverMaxOuterIterations 15\n')):
        c = dict(B10); c.update(slope=0.1, chd=59.9, iteration=it, extra_rvg=ex)
        d = case(name, **c); ok, _ = sz_check.run(d)
        if ok:
            r = sz_check.checks(d); out[name] = outflow(d); mf[name] = (r['mf6_err_rel'], r['mf6_not_conv'], r['shortfall'])
    g = len(out) == 2 and abs(out['R12_x'] - out['R12_it']) <= 0.03 * out['R12_it'] and mf['R12_x'][0] < 1e-5 and mf['R12_x'][1] == 0 and mf['R12_x'][2] < 1e-6
    if len(out) == 2:
        print('  R12: explicit outflow %.0f m3 vs iterated %.0f m3, MODFLOW error %.2g, not converged %d' % (out['R12_x'], out['R12_it'], mf['R12_x'][0], mf['R12_x'][1]))
    res.append(('R12 explicit discharge zone with dry cells converges', g))

    DRY13 = dict(rain=[0.0] * 15 + [150.0] + [0.0] * 4 + [150.0] + [0.0] * 9, days=30, pet=8.0, init_depth=0.0, phi0=(10.0, 10.0))
    out = {}
    for name, it, ex in (('R13_it', (100, 1e-4, 1e-6), ''), ('R13_b1', (1, 1e-4, 1e-6), ':SolverMaxOuterIterations 12\n')):
        c = dict(B10); c.update(Kv=5000.0, Kh=1000.0, Sy=0.001, iteration=it, extra_rvg=ex, **DRY13)
        d = case(name, **c); ok, _ = sz_check.run(d)
        if ok: out[name] = outflow(d)
    g = len(out) == 2 and out['R13_b1'] <= 1.5 * out['R13_it']
    if len(out) == 2:
        print('  R13: unconverged steps, outflow %.0f m3 vs iterated %.0f m3 (x%.2f)' % (out['R13_b1'], out['R13_it'], out['R13_b1'] / out['R13_it']))
    res.append(('R13 MODFLOW residual not handed to Raven', g))

    # ---- negative recharge (N1-N7 = R14-R20) ------------------------------------------------------------------------
    import re, pandas as pd
    QUICK = os.environ.get('RAVEN_TEST_QUICK', '') not in ('', '0')
    def egg(amp, lam=50.0):
        import math
        return lambda x, y: amp * math.sin(2 * math.pi * x / lam) * math.sin(2 * math.pi * y / lam)
    GR = dict(extra_proc='  :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER\n', extra_soil={'GR4J_X2': 60.0, 'GR4J_X3': 150.0})
    N1 = dict(nhru=5, hru_w=200.0, slope=0.03, rain=[6.0] * 10 + [0.0] * 10 + [12.0] * 10, days=30, init_depth=1.2, perc=1.0,
              ksat=200.0, aq_b=4.0, aq_psia=0.3, demf=egg(0.3), **GR)
    LIM = dict(sz_check.ID_LIMITS)
    def ident(d, lim=LIM, skip=()):
        r = sz_check.checks(d)
        return sz_check.report(os.path.basename(d), r, {k: v for k, v in lim.items() if k in r and k not in skip}), r
    def vz(m, k=1):
        return '' if m == 'NONE' else ':SoilZoneVadose %s\n' % m + (':SoilZoneVadoseClasses %d\n' % k if k > 1 else '')
    g = True
    meths = [('NONE', 1), ('RICHARDS', 1)] if QUICK else [('NONE', 1), ('RICHARDS', 1), ('KINEMATIC', 1), ('LAG', 1), ('RICHARDS', 3), ('LAG', 3)]
    for m, k in meths:
        d = case('R14_%s%d' % (m.lower(), k), extra_rvg=vz(m, k), **N1); ok, txt = sz_check.run(d)
        if not ok: print('  R14 %s: run FAILED\n%s' % (m, txt[-600:])); g = False; continue
        good, r = ident(d); b = sz_check.outputs(d)[0]
        neg = float((b['Raven recharge [m3/d]'] < 0).sum())
        print('  R14 %s K=%d: steps with negative recharge %d' % (m, k, neg)); g &= good and neg > 0
    res.append(('R14 negative recharge: identities at round-off', g))

    DRY2 = dict(nhru=5, hru_w=200.0, aq_thick=2.0, init_depth=2.5, rain=[0.0] * 40, days=40, slope=0.03, perc=0.0, **GR)
    d = case('R15_dry2_none', **DRY2); ok, txt = sz_check.run(d); g = False
    if ok:
        good, r = ident(d)
        m_ = re.search(r'negative recharge cut : ([-0-9.e+]+) m3', sz_check.summary(d))
        cut = float(m_.group(1)) if m_ else 0.0
        g = good and cut > 0
        print('  R15: completes; negative recharge cut %.0f m3' % cut)
    else: print('  R15: run FAILED\n' + txt[-600:])
    res.append(('R15 negative recharge limited by the top cell', g))

    d = case('R16_handback_richards', extra_rvg=vz('RICHARDS'), **dict(N1, rain=15.0, init_depth=1.25)); ok, txt = sz_check.run(d); g = False
    if ok: g, r = ident(d); print('  R16: hand-back with one depth class, identities %s' % ('ok' if g else 'FAIL'))
    else: print('  R16: run FAILED\n' + txt[-600:])
    res.append(('R16 one-class hand-back', g))

    BL = '  :Baseflow BASE_LINEAR SOIL[1] SURFACE_WATER\n  :Baseflow BASE_LINEAR SOIL[0] SURFACE_WATER\n'
    GRX = {'GR4J_X2': 60.0, 'GR4J_X3': 1.0, 'BASEFLOW_COEFF': 0.5}   # (X3 1 mm: the import at its full rate X2 while SOIL[1] holds water)
    DR2 = dict(DRY2, rain=5.0, perc=5.0, extra_proc=GR['extra_proc'] + BL, extra_soil=GRX)
    vols = {}; g = True
    for tim in ('LAGGED', 'AFTER'):
        d = case('R17_drain2_%s' % tim.lower(), extra_rvg=':SoilZoneExchangeTiming %s\n' % tim, **DR2); ok, txt = sz_check.run(d)
        if not ok: print('  R17 %s: run FAILED\n%s' % (tim, txt[-600:])); g = False; continue
        good, r = ident(d, skip=('neg_unheld',))
        b = sz_check.outputs(d)[0]; nh = float(b['negative recharge the soil zone did not hold [m3]'].sum()); vols[tim] = nh
        e = sz_check.errors(d); sm = sz_check.summary(d)
        w = 'was not held by the soil zone' in e and 'moved it on before the coupled exchange' in e and 'negative recharge not held' in sm
        print('  R17 %s: not held %.0f m3, shortfall %.3g m3, warning and run total %s' % (tim, nh, r['shortfall'], 'present' if w else 'MISSING'))
        g &= good and nh > 0 and w
    if len(vols) == 2:
        # (the term is not a LAGGED artefact: AFTER books it too; the volumes differ here, where the soil is drained only in part)
        print('  R17: not held with AFTER %.0f m3, with LAGGED %.0f m3 (both booked: %s)' % (vols['AFTER'], vols['LAGGED'], 'ok' if min(vols.values()) > 0 else 'FAIL'))
        g &= min(vols.values()) > 0
    res.append(('R17 negative recharge not held booked apart', g))

    g = True
    for tag, conf in (('R18', False), ('R18c', True)):
        cfg = dict(DRY2, physical=False, init_depth=1.0, aq_thick=2.0, extra_soil={'GR4J_X2': 60.0, 'GR4J_X3': 150.0},
                   phi0=(200.0, 200.0), **({'aq_layers': [('TO_BEDROCK', 'CONFINED_AQUIFER')]} if conf else {}))
        gd = case(tag + '_gen', **dict(cfg, extra_proc='', extra_soil=None)); ok, txt = sz_check.run(gd)   # (MODFLOW's files)
        if not ok: print('  %s: generated run FAILED\n%s' % (tag, txt[-600:])); g = False; continue
        e = sz_check.ext_case(gd, os.path.join(W, tag + '_ext'), cfg, newton=False); ok, txt = sz_check.run(e)
        if not ok: print('  %s: existing-model run FAILED\n%s' % (tag, txt[-600:])); g = False; continue
        b = sz_check.outputs(e)[0]; lost = float(b['recharge not applied by MODFLOW [m3/d]'].sum())
        err = sz_check.errors(e); good, r = ident(e)
        if not conf:
            w = 'not applied by MODFLOW' in err and 'without MODFLOW supplying it' in err and 'neither water balance' in err
            gg = good and lost < 0 and w
            print('  R18: recharge not applied %.0f m3 (negative), warning %s' % (lost, 'ok' if w else 'MISSING'))
        else:
            w = 'confined cells (ICELLTYPE 0) never dry' in err
            gg = good and lost == 0 and w
            print('  R18c: recharge not applied %.3g m3 (0), warning naming confined cells %s' % (lost, 'ok' if w else 'MISSING'))
        g &= gg
    res.append(('R18 recharge not applied without NEWTON (R18c confined)', g))

    d = case('R19_richards3', extra_rvg=vz('RICHARDS', 3), **dict(DR2, init_depth=1.8)); ok, txt = sz_check.run(d); g = False
    if ok:
        good, r = ident(d, skip=('neg_unheld',)); b = sz_check.outputs(d)[0]
        g = good and r['mf6_not_conv'] == 0 and 'far outside' not in sz_check.errors(d)
        print('  R19: %d steps, MODFLOW unconverged %d, far heads %s' % (len(b), r['mf6_not_conv'], 'none' if 'far outside' not in sz_check.errors(d) else 'REPORTED'))
    else: print('  R19: run FAILED\n' + txt[-600:])
    res.append(('R19 column upflow limited by the source cell', g))

    SIB = dict(nhru=1, hru_w=800.0, width=100.0, aq_thick=2.0, init_depth=1.8, rain=5.0, days=30, slope=0.02, perc=5.0,
               extra_proc=GR['extra_proc'] + BL, extra_soil=GRX)
    g = True
    for tim in (('AFTER',) if QUICK else ('AFTER', 'LAGGED')):
        d = case('R20_sib_%s' % tim.lower(), extra_rvg=':SoilZoneExchangeTiming %s\n' % tim, **SIB); ok, txt = sz_check.run(d)
        if not ok: print('  R20 %s: run FAILED\n%s' % (tim, txt[-600:])); g = False; continue
        good, r = ident(d, skip=('neg_unheld',))
        b, sx, _ = sz_check.outputs(d)
        nh = b['negative recharge the soil zone did not hold [m3]'].values
        left = sx.groupby('time [d]')['soil-zone water [mm]'].sum().values
        held = [left[i] for i in range(min(len(nh), len(left))) if nh[i] > 0]
        tiny = int(((nh > 0) & (nh < 1e-9)).sum())
        gg = good and len(held) > 0 and all(x <= 1e-9 for x in held) and tiny == 0
        print('  R20 %s: not held %.1f m3 on %d steps, largest soil water left on them %.3g mm, round-off bookings %d -> %s'
              % (tim, nh.sum(), len(held), max(held) if held else 0.0, tiny, 'ok' if gg else 'FAIL'))
        g &= gg
    res.append(('R20 not held only where the HRU holds nothing', g))

    for n, g in res:
        print('  %-45s %s' % (n, 'ok' if g else 'FAILED'))
    good = all(g for _, g in res)
    print('robustness tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
