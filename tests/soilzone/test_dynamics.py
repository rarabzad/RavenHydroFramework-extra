"""T4 / T5 / sub-grid (plan §9.2) on the T2/T3 hillslope (test_hillslope.CFG).

T4  time step: 1 d, 6 h and 1 h, each against the MODFLOW-only reference run with the same step. Raven's own
    processes (infiltration, percolation) act before the exchange in each step, so the coupled model differs from the
    monolithic reference by a first-order splitting error (rain on a full soil runs off in Raven although the
    exchange drains the soil later in the same step). The error must shrink with the step (mean error 1 d > 6 h > 1 h,
    hourly mean below 3 mm); the balances close at every step size and the interface converges in every step.
T5  stiffness: a thin, conductive soil-aquifer contact (C^sz/A ~ 9.5 /d against S_d = 0.2: dt/t_c ~ 48 for 1-day
    steps). The iterated interface converges in a few updates and matches the reference as closely as the soft case;
    one pass without iteration (`:SoilZoneIteration 0 ...`) is less accurate. Both runs conserve water exactly.
SG  sub-grid saturated fraction (`:SoilZoneSubgrid 5`, ramp 0.5 m) on the same slope: F changes smoothly instead of
    cell by cell, the balances close and the totals stay close to the reference.
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check, sz_reference
from test_hillslope import CFG, RAIN

W = sz_check.tc.work('soilzone', 'dynamics')

def daily(d, nh, days):
    """per-HRU daily water table, soil level, saturated fraction; daily surface outflow [m3/d]"""
    s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    t = s['time [d]'].values
    s = s[np.abs(t - np.round(t)) < 1e-6]
    out = {}
    for col, key in (('water table [m]', 'wt'), ('soil water level [m]', 'hs'), ('saturated fraction [-]', 'F')):
        a = np.zeros((days, nh))
        for k in range(nh):
            x = s[s['HRU_ID'] == k + 1].sort_values('time [d]')
            a[:, k] = x[col].values[:days]
        out[key] = a
    q = pd.read_csv(os.path.join(d, 'out', 'Hydrographs.csv'))
    qcol = [c for c in q.columns if c.startswith('box') and 'obs' not in c][0]
    tq = q['time'].values if 'time' in q else np.arange(len(q))
    vol = q[qcol].values[1:] * 86400.0 * np.diff(tq)          # m3 per step
    out['cumout'] = np.array([vol[tq[1:] <= day + 1e-9].sum() for day in range(1, days + 1)])
    return out

def run_case(name, **kw):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    cfg = dict(CFG); cfg.update(kw)
    sz_models.make_case(d, **cfg)
    ok, txt = sz_check.run(d)
    if not ok:
        print('%s: run FAILED\n%s' % (name, txt[-2000:]))
        return None, None
    res = sz_check.checks(d, dt=cfg.get('timestep', 1.0))
    return d, res

def compare(a, b, days):
    return dict(max_head_diff_m=float(np.abs(a['wt'] - b['wt']).max()),
                cum_out_rel_diff=float(abs(a['cumout'][-1] - b['cumout'][-1]) / max(abs(b['cumout'][-1]), 1e-9)))

def main():
    nh, days = CFG['nhru'], len(RAIN)
    ok_all = True
    # ---------------- T4: time step, each against the reference with the same step
    runs, errs = {}, {}
    for name, dt, nstp in (('dt_1d', 1.0, 1), ('dt_6h', 0.25, 4), ('dt_1h', 1.0 / 24.0, 24)):
        d, res = run_case(name, timestep=dt)
        if d is None:
            ok_all = False; continue
        runs[name] = daily(d, nh, days)
        print('T4 %s:' % name)
        ok_all &= sz_check.report(name, res, dict(sz_check.STD_LIMITS))
        rd = os.path.join(W, 'ref_' + name); shutil.rmtree(rd, ignore_errors=True)
        ref = sz_reference.build(d, rd, RAIN, CFG['H0'], CFG['H1'], CFG['n'], CFG['sfc'], CFG['ksat'],
                                 sz_check.tc.MF6LIB, nstp=nstp)
        e = np.abs(runs[name]['wt'] - ref['aquifer'].mean(axis=1))
        errs[name] = dict(max=float(e.max()), mean=float(e.mean()),
                          out=float(abs(runs[name]['cumout'][-1] - ref['drn'].sum()) / ref['drn'].sum()))
        print('  vs reference (same step): max %.4f m, mean %.4f m, total outflow %.2e' % (errs[name]['max'], errs[name]['mean'], errs[name]['out']))
    if len(errs) == 3:
        good = errs['dt_1d']['mean'] > errs['dt_6h']['mean'] > errs['dt_1h']['mean'] and errs['dt_1h']['mean'] < 0.003 \
            and errs['dt_1h']['max'] < 0.05 and max(e['out'] for e in errs.values()) < 1e-3
        print('T4 time step convergence to the reference: %s' % ('PASS' if good else 'FAIL')); ok_all &= good
    # ---------------- T5: stiffness, explicit vs iterated
    stiff = dict(Kv=100.0, ksat=10000.0)
    d_it, r_it = run_case('stiff_iterated', **stiff)
    d_ex, r_ex = run_case('stiff_explicit', iteration=(0, 1e-4, 1e-6), **stiff)
    if d_it and d_ex:
        rd = os.path.join(W, 'stiff_reference'); shutil.rmtree(rd, ignore_errors=True)
        ref = sz_reference.build(d_it, rd, RAIN, CFG['H0'], CFG['H1'], CFG['n'], CFG['sfc'], stiff['ksat'],
                                 sz_check.tc.MF6LIB)
        R = dict(wt=ref['aquifer'].mean(axis=1), cumout=np.cumsum(ref['drn']))   # daily, like the coupled runs
        a_it, a_ex = daily(d_it, nh, days), daily(d_ex, nh, days)
        e_it, e_ex = compare(a_it, R, days), compare(a_ex, R, days)
        print('T5 iterated: %s, interface updates max %d' % (e_it, r_it['max_updates']))
        print('T5 one pass: %s' % e_ex)
        lim_ex = dict(sz_check.STD_LIMITS); lim_ex.pop('iface_not_conv')     # one pass is "not converged" by design
        good = sz_check.report('stiff_iterated', r_it, dict(sz_check.STD_LIMITS))
        good &= sz_check.report('stiff_explicit (conservation only)', r_ex, lim_ex)
        good &= e_it['max_head_diff_m'] < 0.08 and e_it['cum_out_rel_diff'] < 0.002 and r_it['max_updates'] <= 15
        good &= e_it['max_head_diff_m'] <= e_ex['max_head_diff_m'] + 1e-6
        print('T5 stiffness: %s' % ('PASS' if good else 'FAIL')); ok_all &= good
    # ---------------- sub-grid saturated fraction
    d_sg, r_sg = run_case('subgrid5', subgrid=5, smooth=0.5)
    if d_sg:
        a_sg = daily(d_sg, nh, days)
        base = runs.get('dt_1d')                                          # same model, 1x1 samples
        jump = lambda a: float(np.abs(np.diff(a['F'], axis=0)).max())
        print('subgrid 5: largest daily change of F %.3f (1x1 samples: %.3f)' % (jump(a_sg), jump(base) if base else float('nan')))
        good = sz_check.report('subgrid5', r_sg, dict(sz_check.STD_LIMITS))
        if base:
            c = compare(a_sg, base, days); print('  vs 1x1 samples: %s' % c)
            good &= jump(a_sg) < jump(base) and c['cum_out_rel_diff'] < 0.05
        print('sub-grid: %s' % ('PASS' if good else 'FAIL')); ok_all &= good
    print('dynamics tests: %s' % ('ALL PASSED' if ok_all else 'FAILED'))
    return ok_all

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
