"""HS1 / HS2: hillslope with the water table rising into the soil zone and out of the land surface, then
falling again (James Craig's second drawing: a water table crossing sloping soil layers).

Ten HRUs (one cell column each, two rows) on a 0.5 % slope over a closed 20 m aquifer. Rain 10 mm/d for 150 days,
then none for 150 days. Percolation drains only water above field capacity (PERC_GAWSER_CONSTRAIN), so a soil
zone that is not connected to the water table passes the rain through and keeps no free water.
  wetting (HS1): the water table reaches the soil base first at the toe, the saturated zone spreads upslope, the
                soil fills and water leaves through the land surface (overflow), first at the toe;
  drying  (HS2): the saturated zone drains back into the aquifer: on the upslope HRUs that connected during the rain
                (HRUs 2-7) the saturated fraction falls to 0 by day 300 and the overflow stops when the rain does; the
                aquifer is closed, so the water still draining from upslope seeps out at the toe: the HRUs whose water
                table stays above their soil-zone base (8-10) stay saturated, and the toe, whose water table stays above
                its land, overflows in a recession (no rise after day 160) until the end, as the MODFLOW-only reference's
                land-surface drain does (both about 174 m3/d on day 300). Checked: every HRU that connected and whose
                reference head ends below its soil-zone base ends with F < 1e-6 (and at least five such HRUs), every HRU
                whose reference head ends above it with F > 0.999; on day 300 no overflow where the water table lies
                below the land and overflow where it lies above; the outflow after day 160 does not rise; the saturated
                HRUs (F > 0.5) fall from at least 8 at the end of the rain to at most 4. (HRU 1 never connects, and
                the reference keeps overflow on the toe after the rain, so "overflow stops" holds upslope only.)
  --selftest    the HS2 checks on altered results (an upslope HRU left saturated, upslope overflow after the rain, a
                rising recession, a connected-HRU list that is empty) must fail.
The coupled run is compared with a MODFLOW-only model in which the soil zone is a MODFLOW layer (sz_reference); with
daily steps they differ by the splitting error of Raven's processes ahead of the exchange (see test_dynamics DY1).
The balance identities (sz_check) must close in every step.
Quick mode (RAVEN_TEST_QUICK=1) runs the same 300-day case: the drying checks need the whole wet and dry season, and
the run with its MODFLOW-only reference takes about ten seconds.
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check, sz_reference

W = sz_check.tc.work('soilzone', 'hillslope')
RAIN = [10.0] * 150 + [0.0] * 150
CFG = dict(nhru=10, hru_w=100.0, width=200.0, cell=100.0, slope=0.005, Kh=50.0, Kv=1.0, ksat=1000.0, perc=1000.0,
           perc_type='PERC_GAWSER_CONSTRAIN', rain=RAIN, days=len(RAIN), subgrid=1, smooth=0.02, H0=0.5, H1=0.5,
           n=0.4, sfc=0.5)

def t3_checks(F, ovf, wt, land, base, head_ref_end, out_c, tconn):
    """the drying checks (HS2) on the per-HRU daily series (nt x nh): returns {name: (passed, detail)}"""
    nh = F.shape[1]; c = {}
    drained = [k for k in range(nh) if tconn[k] < 10**6 and head_ref_end[k] < base[k] - 0.05]
    wet = [k for k in range(nh) if head_ref_end[k] > base[k] + 0.05]
    c['upslope_disconnects'] = (len(drained) >= 5 and all(F[-1, k] < 1e-6 for k in drained),
                                'HRUs %s connected and drain: F at the end %s' % ([k + 1 for k in drained], [round(float(F[-1, k]), 6) for k in drained]))
    c['toe_stays_saturated'] = (len(wet) >= 1 and all(F[-1, k] > 0.999 for k in wet),
                                'HRUs %s stay above their base: F at the end %s' % ([k + 1 for k in wet], [round(float(F[-1, k]), 4) for k in wet]))
    below = [k for k in range(nh) if wt[-1, k] < land[k] - 0.01]; above = [k for k in range(nh) if wt[-1, k] > land[k] + 0.01]
    c['overflow_stops_where_below_land'] = (len(below) >= 5 and all(ovf[-1, k] == 0.0 for k in below) and all(ovf[-1, k] > 0.0 for k in above),
                                            'water table below the land on HRUs %s (overflow on day 300 %s), above on %s (overflow %s)'
                                            % ([k + 1 for k in below], [float(ovf[-1, k]) for k in below], [k + 1 for k in above], [round(float(ovf[-1, k]), 2) for k in above]))
    last = [int(np.nonzero(ovf[:, k] > 0)[0].max()) + 1 if (ovf[:, k] > 0).any() else 0 for k in range(nh)]
    up = [k for k in drained if last[k] > 0]
    c['upslope_overflow_stops_with_rain'] = (len(up) >= 3 and all(last[k] <= 151 for k in up), 'last overflow day of HRUs %s: %s' % ([k + 1 for k in up], [last[k] for k in up]))
    rec = out_c[160:]
    c['recession'] = (bool(np.all(np.diff(rec) <= 1e-6 * max(rec.max(), 1.0))), 'outflow day 161 %.1f, day 300 %.1f m3/d' % (rec[0], rec[-1]))
    n150 = int((F[149] > 0.5).sum()); n300 = int((F[-1] > 0.5).sum())
    c['saturated_area_shrinks'] = (n150 >= 8 and n300 <= 4, 'saturated HRUs on day 150: %d, day 300: %d' % (n150, n300))
    return c

def selftest(F, ovf, wt, land, base, href, out_c, tconn, drained):
    """each alteration must make the HS2 checks fail"""
    alts = []
    F1 = F.copy(); F1[-1, drained[0]] = 1.0; alts.append(('an upslope HRU left saturated', (F1, ovf, out_c, tconn)))
    o2 = ovf.copy(); o2[-1, drained[1]] = 0.5; alts.append(('upslope overflow on day 300', (F, o2, out_c, tconn)))
    q3 = out_c.copy(); q3[250:] += 5.0 * np.arange(len(q3) - 250); alts.append(('a rising recession', (F, ovf, q3, tconn)))
    alts.append(('no HRU connected', (F, ovf, out_c, [10**6] * len(tconn))))
    ok = True
    for what, (f, o, q, tc_) in alts:
        bad = [k for k, (g, _) in t3_checks(f, o, wt, land, base, href, q, tc_).items() if not g]
        print('  selftest %-32s -> %s' % (what, ('fails (%s): ok' % ', '.join(bad)) if bad else 'PASSES: the checks miss it'))
        ok &= bool(bad)
    return ok

def main():
    print('HS1/HS2: %s mode (the same 300-day case in both)' % ('quick' if os.environ.get('RAVEN_TEST_QUICK', '') == '1' else 'full'))
    d = os.path.join(W, 'coupled'); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **CFG)
    ok, txt = sz_check.run(d)
    print('HS1/HS2 hillslope: coupled run %s' % ('ok' if ok else 'FAILED'))
    if not ok:
        print(txt[-3000:]); return False
    b, s, w = sz_check.outputs(d)
    res = sz_check.checks(d)
    good = sz_check.report('hillslope', res, dict(sz_check.STD_LIMITS))
    # --- reference
    rd = os.path.join(W, 'reference'); shutil.rmtree(rd, ignore_errors=True)
    ref = sz_reference.build(d, rd, RAIN, CFG['H0'], CFG['H1'], CFG['n'], CFG['sfc'], CFG['ksat'], sz_check.tc.MF6LIB)
    nt = ref['aquifer'].shape[0]
    wt_ref = ref['aquifer'].mean(axis=1)                   # (nt, ncol): aquifer head per column
    soil_ref = ref['soil'].mean(axis=1)                    # level in the soil layer (meaningful where saturated)
    top = ref['top'].mean(axis=0); land = ref['land'].mean(axis=0)
    nh = CFG['nhru']
    head_ref_end = ref['aquifer'][-1].mean(axis=0)          # reference aquifer head per column on the last day
    wt = np.zeros((nt, nh)); hs = np.zeros((nt, nh)); F = np.zeros((nt, nh)); ovf = np.zeros((nt, nh))
    for k in range(nh):
        x = s[s['HRU_ID'] == k + 1].sort_values('time [d]')
        wt[:, k] = x['water table [m]'].values[:nt]; hs[:, k] = x['soil water level [m]'].values[:nt]
        F[:, k] = x['saturated fraction [-]'].values[:nt]; ovf[:, k] = x['overflow [mm]'].values[:nt]
    dwt = np.abs(wt - wt_ref)
    res['max_head_diff_m'] = float(dwt.max())
    res['mean_head_diff_m'] = float(dwt.mean())
    sat = (F > 0.999) & (soil_ref > top[None, :] + 0.02)
    res['max_soil_level_diff_m'] = float(np.abs(hs - soil_ref)[sat].max()) if sat.any() else float('nan')
    # saturation excess leaving the land surface: coupled = soil-zone overflow + rain that could not infiltrate
    # (Raven's infiltration sends it to SURFACE_WATER and on to the outlet); reference = drain at the land surface
    q = pd.read_csv(os.path.join(d, 'out', 'Hydrographs.csv'))
    qcol = [c for c in q.columns if c.startswith('box') and 'obs' not in c][0]
    out_c = q[qcol].values[1:nt + 1] * 86400.0           # m3/d (first row is the start time)
    cum_c = np.cumsum(out_c); cum_r = np.cumsum(ref['drn'][:nt])
    res['outflow_total_coupled_m3'] = float(cum_c[-1]); res['outflow_total_reference_m3'] = float(cum_r[-1])
    res['outflow_total_rel_diff'] = float(abs(cum_c[-1] - cum_r[-1]) / max(cum_r[-1], 1e-9))
    res['outflow_max_cum_diff_rel'] = float(np.abs(cum_c - cum_r).max() / max(cum_r[-1], 1e-9))
    on_c = int(np.argmax(out_c > 1.0)) + 1 if (out_c > 1.0).any() else -1
    on_r = int(np.argmax(ref['drn'][:nt] > 1.0)) + 1 if (ref['drn'][:nt] > 1.0).any() else -1
    res['overflow_onset_day_coupled'] = on_c; res['overflow_onset_day_reference'] = on_r
    # physical behaviour
    tconn = [int(np.argmax(F[:, k] > 0.5)) + 1 if (F[:, k] > 0.5).any() else 10**6 for k in range(nh)]
    res['connect_day_by_hru'] = tconn
    res['toe_connects_first'] = bool(tconn[-1] == min(tconn) or tconn[-2] == min(tconn))
    tov = [int(np.argmax(ovf[:, k] > 0)) + 1 if (ovf[:, k] > 0).any() else 10**6 for k in range(nh)]
    res['overflow_day_by_hru'] = tov
    res['overflow_starts_at_toe'] = bool(min(tov) < 10**6 and np.argmin(tov) >= nh - 2)
    t3 = t3_checks(F, ovf, wt, land, top, head_ref_end, out_c, tconn)
    for k, (g, det) in t3.items():
        res[k] = g
    res['reference_drain_day300_m3d'] = float(ref['drn'][nt - 1]); res['coupled_outflow_day300_m3d'] = float(out_c[-1])
    for k in ('max_head_diff_m', 'mean_head_diff_m', 'max_soil_level_diff_m', 'outflow_total_coupled_m3',
              'outflow_total_reference_m3', 'outflow_total_rel_diff', 'outflow_max_cum_diff_rel',
              'overflow_onset_day_coupled', 'overflow_onset_day_reference', 'connect_day_by_hru', 'toe_connects_first',
              'overflow_day_by_hru', 'overflow_starts_at_toe', 'reference_drain_day300_m3d', 'coupled_outflow_day300_m3d'):
        print('  %-30s %s' % (k, res[k]))
    for k, (g, det) in t3.items():
        print('  HS2 %-32s %-4s %s' % (k, 'ok' if g else 'FAIL', det))
    # daily steps: a first-order splitting error remains (test_dynamics DY1 shows it vanishing with the step)
    lim = {'max_head_diff_m': 0.08, 'mean_head_diff_m': 0.02, 'max_soil_level_diff_m': 0.10,
           'outflow_total_rel_diff': 0.002, 'outflow_max_cum_diff_rel': 0.005}
    good &= sz_check.report('hillslope vs MODFLOW-only reference', res, lim)
    good &= abs(on_c - on_r) <= 3
    for k in ['toe_connects_first', 'overflow_starts_at_toe'] + list(t3):
        good &= res[k]
    if '--selftest' in sys.argv:
        drained = [k for k in range(nh) if tconn[k] < 10**6 and head_ref_end[k] < top[k] - 0.05]
        good &= selftest(F, ovf, wt, land, top, head_ref_end, out_c, tconn, drained)
    print('HS1/HS2 hillslope: %s' % ('PASS' if good else 'FAIL'))
    return bool(good)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
