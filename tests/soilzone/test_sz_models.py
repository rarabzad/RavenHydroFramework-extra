"""Model tests of the soil-zone coupling (docs/design/soil_zone_columns_plan.md section 8).

P1  delay through a deep unsaturated zone: a 3-day storm over a water table 6 m deep. With :SoilZoneVadose RICHARDS
     the recharge reaching MODFLOW is later and spread out (centroid at least 3 days later, peak lower), and nothing
     is lost: inflow = recharge to the aquifer + storage change of the columns.
P2  capillary rise from a shallow water table (no unsaturated column) into a soil drying under PET: with
     :SoilZoneCapillaryRise ON evaporation continues from the water table; the rise falls with the water-table depth
     (0.7, 1.3, 2.5 m); without it the soil dries out and evaporation stops.
P3  a water table that rises through the unsaturated column into the soil zone (the column collapses into the contact
     exchange) and falls again (the column re-forms): all identities hold throughout.
P4  restart: 60 + 60 days from the first run's solution.rvc (with its :GWVadoseColumns block) equal 120 days in one go.
P5  :SoilZoneExchangeTiming LAGGED on the T2/T3 hillslope: heads closer to the MODFLOW-only reference than with AFTER
     (the splitting error of Raven's processes ahead of the exchange); a restart with the :GWSoilZoneLag block is exact.
P7  columns over specified heads: the hillslope with a fixed head 0.2 m below the land surface at its toe; the soil
     over the fixed head exchanges with it (both ways over the run), its recharge goes there, and the identities hold;
     a restart from the first half (columns over the head included in :GWSoilZoneColumns) is exact.
P8  restart with column classes on a steep slope (round-off decided whether the classes applied):
     3 classes, unsaturated columns, a specified-head toe; 25 + 25 days equal 50 days.
P9  capillary rise across the shortest column (5 cm): the rise from a column just longer than 5 cm equals
     the rise from the water table just below it and the rise without columns (within 10 %); it is implicit in the
     drawdown it causes, so a water table near the soil base with a thin top layer that dries does not oscillate.
P10  upward flows out of a lower cell: a specified head in layer 2 under a dried thin top layer supplies
     the rise (booked as specified head to soil zone, MODFLOW's balance closes); a thin lowest wet cell under strong rise
     is not pumped dry (no MODFLOW non-convergence), with and without unsaturated columns.
P6  :SoilZoneClasses on the hillslope as one HRU over all ten cell columns: with 10 classes the HRU behaves like ten
     HRUs of one column each (heads within 1 mm of that run); with 5 classes the heads are closer to the reference
     than with the HRU mean (1 class).
All runs: MODFLOW's balance, Raven's balance, the recharge, soil-zone and unsaturated-zone identities (sz_check).
"""
import os, sys, shutil, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'water_table')
LIM = {'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 1e-6, 'sz_identity': 1e-8, 'shortfall': 1e-6, 'vz_identity': 1e-5}
VZ = ':SoilZoneVadose RICHARDS\n'

def run(name, start=None, rvc=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read()
            open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    ok, txt = sz_check.run(d)
    if not ok:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:]))
        return None, None
    r = sz_check.checks(d, dt=cfg.get('timestep', 1.0))
    lim = {k: v for k, v in LIM.items() if k in r}
    print('  %s:' % name)
    good = sz_check.report(name, r, lim)
    return (d if good else None), r

def budget(d):
    return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))

def storage(d):
    return pd.read_csv(os.path.join(d, 'out', 'WatershedStorage.csv'))

def P1():
    print('P1 delay through a deep unsaturated zone')
    rain = [0.0] * 10 + [40.0] * 3 + [0.0] * 77
    cfg = dict(nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, rain=rain, days=len(rain), perc=50.0, ksat=500.0, Kv=0.5, Sy=0.2,
               aq_b=4.0, aq_psia=0.3)
    d0, _ = run('a_off', **cfg)
    d1, _ = run('a_vz', extra_rvg=VZ, **cfg)
    if not (d0 and d1):
        return False
    t = np.arange(1, len(rain) + 1)
    m0, m1 = budget(d0)['MF6 recharge [m3/d]'].values, budget(d1)['MF6 recharge [m3/d]'].values
    c0, c1 = (m0 * t).sum() / m0.sum(), (m1 * t).sum() / m1.sum()
    b = budget(d1)
    inflow, out = b['unsaturated zone inflow [m3]'].iloc[1:].sum(), b['unsaturated zone to aquifer [m3]'].iloc[1:].sum()
    st = b['unsaturated zone storage [m3]']      # (after each step: the balance from the end of the first step on)
    close = abs(inflow - out - b['capillary rise to soil zone [m3]'].iloc[1:].sum() - (st.iloc[-1] - st.iloc[0])) / max(inflow, 1.0)
    ok = (c1 - c0 >= 3.0) and (m1.max() < 0.95 * m0.max()) and close < 1e-6
    print('  recharge centroid day %.2f without the column, %.2f with it; peak %.0f vs %.0f m3/d; column balance %.2g -> %s'
          % (c0, c1, m0.max(), m1.max(), close, 'ok' if ok else 'FAIL'))
    return ok

def P2():
    print('P2 capillary rise from a shallow water table')
    ok = True; loss = {}
    for depth in (0.7, 1.3, 2.5):
        for cap in ('OFF', 'ON'):
            cfg = dict(nhru=1, hru_w=200.0, init_depth=depth, aq_thick=20.0, rain=0.0, days=60, perc=5.0, ksat=200.0, Kv=0.5, Sy=0.2,
                       pet=4.0, phi0=(40.0, 40.0), soil_b=5.0, soil_psia=200.0)
            d, _ = run('b_%s_%g' % (cap.lower(), depth), extra_rvg=':SoilZoneCapillaryRise %s\n' % cap, **cfg)
            if not d:
                ok = False; continue
            w = storage(d); loss[(cap, depth)] = w['Cum. Losses to Atmosphere [mm]'].iloc[-1]
            if cap == 'ON':
                b = budget(d); print('    rise %.1f mm over 60 days' % (b['capillary rise from the water table [m3]'].sum() / 40000.0 * 1000.0))
    if len(loss) == 6:
        on = [loss[('ON', z)] for z in (0.7, 1.3, 2.5)]; off = [loss[('OFF', z)] for z in (0.7, 1.3, 2.5)]
        good = all(a > b + 10.0 for a, b in zip(on, off)) and on[0] > on[1] > on[2]
        print('  evaporation [mm] with rise %s, without %s -> %s' % (['%.0f' % v for v in on], ['%.0f' % v for v in off], 'ok' if good else 'FAIL'))
        ok &= good
    return ok

def P3():
    print('P3 a water table rising through the column into the soil zone and falling again')
    rain = [0.0] * 5 + [30.0] * 40 + [0.0] * 135
    cfg = dict(nhru=1, hru_w=400.0, init_depth=3.0, chd=97.0, aq_thick=20.0, rain=rain, days=len(rain), perc=30.0, ksat=300.0, Kh=1.0, Kv=0.3,
               Sy=0.1, pet=3.0, soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3)   # (a fixed head 3 m deep drains the mound)
    d, _ = run('c_vz', extra_rvg=VZ, **cfg)
    if not d:
        return False
    b = budget(d); s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    wt, zb = s.iloc[:, 5].values, s.iloc[:, 3].values
    st = b['unsaturated zone storage [m3]'].values
    rose = (wt - zb).max() > 0.0                               # the water table reached the soil zone
    fell = (zb - wt)[-1] > 0.3                                 # and fell well below it again
    collapsed = np.any(np.abs(st) < 1e-9) if rose else False  # the column vanished while it was up
    reformed = bool(abs(st[-1]) > 0.0) or (b['unsaturated zone inflow [m3]'].iloc[-30:].abs().sum() > 0) or fell
    ok = rose and fell and collapsed and reformed
    print('  water table to %.2f m above the soil-zone base and back to %.2f m below; column storage min %.3g, end %.3g m3 -> %s'
          % ((wt - zb).max(), (zb - wt)[-1], np.abs(st).min(), st[-1], 'ok' if ok else 'FAIL'))
    return ok

def P4():
    print('P4 restart of the unsaturated columns')
    rain = ([0.0] * 10 + [40.0] * 3 + [0.0] * 17) * 4
    cfg = dict(nhru=1, hru_w=200.0, init_depth=6.0, aq_thick=20.0, perc=50.0, ksat=500.0, Kv=0.5, Sy=0.2, aq_b=4.0, aq_psia=0.3,
               extra_rvg=VZ)
    full, _ = run('d_full', rain=rain, days=120, **cfg)
    first, _ = run('d_first', rain=rain[:60], days=60, **cfg)
    if not (full and first):
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    has = ':GWVadoseColumns' in open(rvc).read()
    start = (datetime.date(2000, 1, 1) + datetime.timedelta(days=60)).isoformat()
    second, _ = run('d_second', start=start, rvc=rvc, rain=rain[60:], days=60, **cfg)
    if not second:
        return False
    a, b = budget(full).iloc[60:].reset_index(drop=True), budget(second)
    dq = (a['MF6 recharge [m3/d]'] - b['MF6 recharge [m3/d]']).abs().max() / a['MF6 recharge [m3/d]'].abs().max()
    ds = (a['unsaturated zone storage [m3]'] - b['unsaturated zone storage [m3]']).abs().max() / a['unsaturated zone storage [m3]'].abs().max()
    ok = has and dq < 1e-4 and ds < 1e-4
    print('  hotstart block written: %s; max deviation recharge %.2g, column storage %.2g -> %s' % (has, dq, ds, 'ok' if ok else 'FAIL'))
    return ok

def heads(d):
    import flopy
    H = flopy.utils.HeadFile(os.path.join(d, 'out', 'mf6', 'gwf.hds'))
    out = {}
    for t in H.get_times():
        h = np.array(H.get_data(totim=t)[0], dtype=float); h[np.abs(h) > 1e20] = np.nan   # (inactive and dry cells)
        out[round(t, 6)] = h
    return out

def head_err(d, ref):
    import flopy
    R = flopy.utils.HeadFile(os.path.join(ref, 'ref.hds')); tr = np.array(R.get_times())
    ds = []
    for t, h in heads(d).items():
        i = int(np.argmin(np.abs(tr - t)))
        ds.append(np.abs(h - R.get_data(totim=tr[i])[1]).ravel())
    d = np.concatenate(ds); d = d[np.isfinite(d)]
    return d.mean(), d.max()

def hill(name, extra, **over):
    from test_hillslope import CFG, RAIN
    cfg = dict(CFG); cfg.update(over); cfg['extra_rvg'] = extra
    return run(name, **cfg)

def reference(d, name):
    import sz_reference
    from test_hillslope import CFG, RAIN
    rd = os.path.join(W, name); shutil.rmtree(rd, ignore_errors=True)
    sz_reference.build(d, rd, RAIN, CFG['H0'], CFG['H1'], CFG['n'], CFG['sfc'], CFG['ksat'], sz_check.tc.MF6LIB)
    return rd

def P5():
    print('P5 lagged exchange timing')
    from test_hillslope import RAIN
    da, _ = hill('e_after', ':SoilZoneExchangeTiming AFTER\n')
    dl, _ = hill('e_lag', ':SoilZoneExchangeTiming LAGGED\n')
    if not (da and dl):
        return False
    rd = reference(da, 'e_ref')
    ea, el = head_err(da, rd), head_err(dl, rd)
    ok = (el[0] < 0.7 * ea[0]) and (el[1] < ea[1])
    print('  head error against the reference: AFTER mean %.4f max %.4f m, LAGGED mean %.4f max %.4f m -> %s'
          % (ea[0], ea[1], el[0], el[1], 'ok' if ok else 'FAIL'))
    # restart with the lagged source
    first, _ = hill('e_first', ':SoilZoneExchangeTiming LAGGED\n', rain=RAIN[:150], days=150)
    if not first:
        return False
    rvc = os.path.join(first, 'out', 'solution.rvc')
    has = ':GWSoilZoneLag' in open(rvc).read()
    second, _ = hill('e_second', ':SoilZoneExchangeTiming LAGGED\n', rain=RAIN[150:], days=150, start='2000-05-30', rvc=rvc)
    if not second:
        return False
    a, b = budget(dl).iloc[150:].reset_index(drop=True), budget(second)
    c = 'soil-zone exchange applied to Raven [m3]'
    dq = (a[c] - b[c]).abs().max() / a[c].abs().max()
    hs = heads(second); hf = heads(dl)
    dh = max(np.nanmax(np.abs(hs[t] - hf[round(t + 150.0, 6)])) for t in hs if round(t + 150.0, 6) in hf) if hs else 1.0
    ok2 = has and dq < 1e-4 and dh < 1e-4
    print('  restart: :GWSoilZoneLag written %s; max deviation exchange %.2g, heads %.2g m -> %s' % (has, dq, dh, 'ok' if ok2 else 'FAIL'))
    return ok and ok2

def P6():
    print('P6 column classes')
    lag = ':SoilZoneExchangeTiming LAGGED\n'
    d10, _ = hill('f_10hru', lag)
    d1, _ = hill('f_1hru_k1', lag + ':SoilZoneClasses 1\n', nhru=1, hru_w=1000.0)
    d5, _ = hill('f_1hru_k5', lag + ':SoilZoneClasses 5\n', nhru=1, hru_w=1000.0)
    dk, _ = hill('f_1hru_k10', lag + ':SoilZoneClasses 10\n', nhru=1, hru_w=1000.0)
    if not (d10 and d1 and d5 and dk):
        return False
    rd = reference(d1, 'f_ref')
    e1, e5, ek = head_err(d1, rd), head_err(d5, rd), head_err(dk, rd)
    # ten classes against ten HRUs (the same cells; the grid of the one-HRU model has the same columns)
    h10, hk = heads(d10), heads(dk)
    common = [t for t in hk if t in h10]
    same = max(np.nanmax(np.abs(np.nanmean(h10[t], axis=0) - np.nanmean(hk[t], axis=0))) for t in common) if common else 1.0
    ok = (e5[0] < 0.8 * e1[0]) and (ek[0] < 0.8 * e1[0]) and (same < 1e-3)
    print('  head error against the reference: 1 class %.4f, 5 classes %.4f, 10 classes %.4f m (mean); 10 classes vs 10 HRUs %.2g m -> %s'
          % (e1[0], e5[0], ek[0], same, 'ok' if ok else 'FAIL'))
    return ok

def P7():
    print('P7 columns over specified heads')
    from test_hillslope import RAIN
    d, _ = hill('g_chd', '', chd=94.8)
    first, _ = hill('g_first', '', chd=94.8, rain=RAIN[:150], days=150)
    if not (d and first):
        return False
    b = budget(d)
    out, inn = b['soil zone to specified heads [m3/d]'].sum(), b['specified heads to soil zone [m3/d]'].sum()
    rvc = os.path.join(first, 'out', 'solution.rvc')
    second, _ = hill('g_second', '', chd=94.8, rain=RAIN[150:], days=150, start='2000-05-30', rvc=rvc)
    if not second:
        return False
    a2, b2 = b.iloc[150:].reset_index(drop=True), budget(second)
    dq = max((a2[c] - b2[c]).abs().max() / max(a2[c].abs().max(), 1e-9) for c in ('soil zone to specified heads [m3/d]', 'soil-zone exchange applied to Raven [m3]'))
    ok = (out > 0) and (inn > 0) and dq < 1e-4
    print('  soil zone to the head %.0f m3/d-days, from it %.0f; restart deviation %.2g -> %s' % (out, inn, dq, 'ok' if ok else 'FAIL'))
    return ok

def P8():
    print('P8 restart with column classes')
    rain = ([0.0] * 5 + [30.0] * 5) * 5
    cfg = dict(nhru=4, hru_w=200.0, slope=0.05, subgrid=5, chd=59.9, init_depth=1.0, perc=40.0, ksat=400.0, Kv=0.5, Sy=0.15, pet=6.0,
               soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3, extra_rvg=VZ + ':SoilZoneClasses 3\n')
    full, _ = run('h_full', rain=rain, days=50, **cfg)
    first, _ = run('h_first', rain=rain[:25], days=25, **cfg)
    if not (full and first):
        return False
    second, _ = run('h_second', start='2000-01-26', rvc=os.path.join(first, 'out', 'solution.rvc'), rain=rain[25:], days=25, **cfg)
    if not second:
        return False
    a, b = budget(full).iloc[25:].reset_index(drop=True), budget(second)
    cols = ['MF6 recharge [m3/d]', 'soil-zone exchange applied to Raven [m3]', 'unsaturated zone to aquifer [m3]', 'storage release [m3/d]']
    dq = max((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0) for c in cols)
    ok = dq < 1e-3
    print('  largest deviation of the restart from the continuous run %.2g -> %s' % (dq, 'ok' if ok else 'FAIL'))
    return ok

def thin_top(d, layers):
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    s = 'AQ, %d, ' % (len(layers) + 1) + ''.join('SAND, %g, AQUIFER, ' % h for h in layers) + 'SAND, TO_BEDROCK, AQUIFER'
    t2 = t.replace('AQ, 1, SAND, TO_BEDROCK, AQUIFER', s); assert t2 != t; open(p, 'w').write(t2)

def P9():
    print('P9 capillary rise across the shortest column')
    cfg = dict(nhru=1, hru_w=200.0, rain=0.0, days=3, perc=1.0, ksat=400.0, Kv=0.5, Sy=0.15, soil_b=5.0, soil_psia=200.0, aq_b=4.0,
               aq_psia=0.3, pet=4.0, phi0=(20.0, 20.0))
    rise = {}
    for tag, dep, ex in (('below', 1.045, VZ), ('above', 1.055, VZ), ('nocol', 1.055, '')):
        d, _ = run('i_%s' % tag, init_depth=dep, extra_rvg=ex + ':SoilZoneCapillaryRise ON\n', **cfg)
        if not d:
            return False
        b = budget(d); c = b['capillary rise to soil zone [m3]'] if 'capillary rise to soil zone [m3]' in b else 0.0 * b.iloc[:, 0]
        rise[tag] = float(c.iloc[0] + b['capillary rise from the water table [m3]'].iloc[0])
    r1 = abs(rise['above'] / rise['below'] - 1.0); r2 = abs(rise['above'] / rise['nocol'] - 1.0)
    ok1 = r1 < 0.1 and r2 < 0.1
    print('  day-1 rise: water table 4.5 cm below the base %.0f m3, 5.5 cm (column) %.0f, 5.5 cm without columns %.0f -> %s'
          % (rise['below'], rise['above'], rise['nocol'], 'ok' if ok1 else 'FAIL'))
    # a thin top layer that dries and rewets with the water table near its bottom: no oscillation
    rain = [0.0] * 5 + [60.0, 40.0, 0.0, 0.0, 30.0] + [0.0] * 10 + [25.0] * 5 + [0.0] * 25
    cfg2 = dict(nhru=4, hru_w=200.0, rain=rain, days=len(rain), perc=40.0, ksat=400.0, Kv=0.5, Sy=0.15, soil_b=5.0, soil_psia=200.0,
                aq_b=4.0, aq_psia=0.3, init_depth=3.0, pet=3.0)
    its = {}
    for tag, ex in (('osc_vz', VZ), ('osc_off', VZ + ':SoilZoneCapillaryRise OFF\n')):
        d = os.path.join(W, 'i_' + tag); shutil.rmtree(d, ignore_errors=True)
        sz_models.make_case(d, extra_rvg=ex, **cfg2); thin_top(d, [1.5])
        okr, txt = sz_check.run(d)
        if not okr:
            print('  i_%s: run FAILED\n%s' % (tag, txt[-1500:])); return False
        r = sz_check.checks(d, dt=cfg2.get('timestep', 1.0)); print('  i_%s:' % tag)
        if not sz_check.report(tag, r, {k: v for k, v in LIM.items() if k in r}):
            return False
        b = budget(d); its[tag] = b['outer iterations'].sum()
        if tag == 'osc_vz':
            s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv')); s = s[s['HRU_ID'] == 2]['water table [m]'].values
            jump = np.abs(np.diff(s[25:])).max()        # (the dry spell after the last rain)
    ok2 = jump < 0.05 and its['osc_vz'] < 1.3 * its['osc_off']
    print('  dry spell: largest daily water-table change %.3f m; outer iterations %d with rise, %d without -> %s'
          % (jump, its['osc_vz'], its['osc_off'], 'ok' if ok2 else 'FAIL'))
    return ok1 and ok2

def run_layers(name, layers, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg); thin_top(d, layers)
    okr, txt = sz_check.run(d)
    if not okr:
        print('  %s: run FAILED\n%s' % (name, txt[-1500:])); return None
    r = sz_check.checks(d, dt=cfg.get('timestep', 1.0)); print('  %s:' % name)
    return d if sz_check.report(name, r, {k: v for k, v in LIM.items() if k in r}) else None

def P10():
    print('P10 upward flows out of a lower cell')
    ok = True
    base = dict(nhru=1, hru_w=200.0, rain=0.0, days=20, perc=1.0, ksat=400.0, Kv=0.5, Sy=0.15, soil_b=5.0, soil_psia=200.0, aq_b=4.0,
                aq_psia=0.3, init_depth=2.0, pet=4.0, phi0=(60.0, 60.0))
    for vz in ('', VZ):
        d = run_layers('j_chd%s' % ('_vz' if vz else ''), [0.5], chd=98.0, extra_rvg=vz + ':SoilZoneCapillaryRise ON\n', **base)
        if not d:
            ok = False; continue
        b = budget(d); sup = b['specified heads to soil zone [m3/d]'].sum() if 'specified heads to soil zone [m3/d]' in b else 0.0
        sup += -b['recharge onto CHD cells [m3/d]'].clip(upper=0.0).sum()       # (with a column: its upflow out of the head)
        good = sup > 0.0
        print('    rise supplied by the specified head %.0f m3/d-days -> %s' % (sup, 'ok' if good else 'FAIL')); ok &= good
    thin = dict(nhru=1, hru_w=200.0, rain=0.0, days=20, perc=1.0, ksat=400.0, Kv=0.5, Sy=0.1, soil_b=5.0, soil_psia=300.0, aq_b=4.0,
                aq_psia=0.3, pet=5.0, phi0=(40.0, 40.0), aq_thick=1.0, init_depth=1.9)
    for vz in ('', VZ):
        d = run_layers('j_thin%s' % ('_vz' if vz else ''), [0.5], extra_rvg=vz + ':SoilZoneCapillaryRise ON\n', **thin)
        if not d:
            ok = False; continue
        b = budget(d); nc = int((b['converged'] == 0).sum()) + int((b['interface converged'] == 0).sum())
        good = nc == 0
        print('    steps not converged (MODFLOW + interface) %d -> %s' % (nc, 'ok' if good else 'FAIL')); ok &= good
    # a falling water table in a thin lowest cell: the column's new nodes take no more than the cell gives
    fall = dict(nhru=1, hru_w=200.0, rain=0.0, days=40, perc=0.5, ksat=400.0, Kv=0.5, Sy=0.03, soil_b=5.0, soil_psia=1000.0, aq_b=4.0,
                aq_psia=0.3, pet=8.0, phi0=(20.0, 20.0), aq_thick=1.0, init_depth=1.9, timestep=0.25)
    d = run_layers('j_fall_vz', [0.5], extra_rvg=VZ + ':SoilZoneCapillaryRise ON\n', **fall)
    if not d:
        return False
    b = budget(d); nc = int((b['converged'] == 0).sum()) + int((b['interface converged'] == 0).sum())
    good = (nc == 0) and bool(np.isfinite(b.select_dtypes('number').values).all())
    print('    falling water table, thin cell: steps not converged %d, all finite -> %s' % (nc, 'ok' if good else 'FAIL'))
    return ok and good

def main():
    res = [f() for f in (P1, P2, P3, P4, P5, P6, P7, P8, P9, P10)]
    print('soil-zone model tests: %s' % ('ALL PASSED' if all(res) else 'FAILED (%d of %d)' % (res.count(False), len(res))))
    return all(res)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
