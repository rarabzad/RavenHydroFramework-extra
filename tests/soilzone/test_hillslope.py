"""T2 / T3 (plan §9.2): hillslope with the water table rising into the soil zone and out of the land surface, then
falling again (James Craig's second drawing: a water table crossing sloping soil layers).

Ten HRUs (one cell column each, two rows) on a 0.5 % slope over a closed 20 m aquifer. Rain 10 mm/d for 150 days,
then none for 150 days. Percolation drains only water above field capacity (PERC_GAWSER_CONSTRAIN), so a soil
zone that is not connected to the water table passes the rain through and keeps no free water.
  wetting (T2): the water table reaches the soil base first at the toe, the saturated zone spreads upslope, the
                soil fills and water leaves through the land surface (overflow), first at the toe;
  drying  (T3): the saturated zone drains back into the aquifer, overflow stops, saturated fractions fall to 0.
The coupled run is compared with a MODFLOW-only model in which the soil zone is a MODFLOW layer (sz_reference); with
daily steps they differ by the splitting error of Raven's processes ahead of the exchange (see test_dynamics T4).
Balance identities of plan §7 must close in every step.
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

def main():
    d = os.path.join(W, 'coupled'); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **CFG)
    ok, txt = sz_check.run(d)
    print('T2/T3 hillslope: coupled run %s' % ('ok' if ok else 'FAILED'))
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
    res['overflow_stops_after_rain'] = bool(ovf[-30:].sum() == 0.0)
    res['upslope_disconnects'] = bool(F[-1, 0] < 1e-6 and F[:150, :].max() > 0.999)
    for k in ('max_head_diff_m', 'mean_head_diff_m', 'max_soil_level_diff_m', 'outflow_total_coupled_m3',
              'outflow_total_reference_m3', 'outflow_total_rel_diff', 'outflow_max_cum_diff_rel',
              'overflow_onset_day_coupled', 'overflow_onset_day_reference', 'connect_day_by_hru', 'toe_connects_first',
              'overflow_day_by_hru', 'overflow_starts_at_toe', 'overflow_stops_after_rain', 'upslope_disconnects'):
        print('  %-30s %s' % (k, res[k]))
    # daily steps: a first-order splitting error remains (test_dynamics T4 shows it vanishing with the step)
    lim = {'max_head_diff_m': 0.08, 'mean_head_diff_m': 0.02, 'max_soil_level_diff_m': 0.10,
           'outflow_total_rel_diff': 0.002, 'outflow_max_cum_diff_rel': 0.005}
    good &= sz_check.report('hillslope vs MODFLOW-only reference', res, lim)
    good &= abs(on_c - on_r) <= 3
    for k in ('toe_connects_first', 'overflow_starts_at_toe', 'upslope_disconnects'):
        good &= res[k]
    print('T2/T3 hillslope: %s' % ('PASS' if good else 'FAIL'))
    return bool(good)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
