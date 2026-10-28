"""Shared run and check helpers of the soil-zone tests.

run(d) runs Raven in folder d; checks(d) returns a dict of the identities of plan §7 (all must be ~0):
  mf6_err_rel      max |MODFLOW balance error| [m3/d] / max Raven recharge [m3/d] (a percentage of the gross aquifer flow
                   is meaningless when nearly all recharge is rejected and the aquifer flow is tiny)
  raven_mb_mm      max |Raven's water-balance error - (GROUNDWATER store - its initial value)| / max(1, store) [-]:
                   Raven counts the end-of-step GROUNDWATER pass-through store both as storage and as outflow, so its
                   MB error equals the change of that store (WatershedStorage.csv carries 6 significant digits, hence
                   the relative form)
  rch_identity     max |Raven recharge - MF6 recharge - rejected - CHD - delay change| / Raven recharge (per step)
  sz_identity      max |soil-zone exchange applied to Raven - rejected - (aquifer to soil - soil to aquifer)*dt - shortfall
                   - capillary rise (from the unsaturated columns and from the water table)|
                   / (sum of the magnitudes of those terms, at least 1 m3), per step
  shortfall        total soil-zone shortfall [m3]
  vz_identity      (:SoilZoneVadose RICHARDS) max |storage change - inflow + capillary rise + outflow| of the unsaturated
                   columns / max(1 m3, flows), from the second step (the recharge identity then includes the columns)
"""
import os, sys, subprocess
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import testconfig as tc  # noqa: E402

def run(d, name='m', timeout=3600):
    r = subprocess.run([tc.RAVEN, name, '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=timeout)
    txt = r.stdout + r.stderr
    ok = 'Successful Simulation' in txt
    return ok, txt

def outputs(d):
    o = os.path.join(d, 'out')
    b = pd.read_csv(os.path.join(o, 'GWBudget.csv'))
    s = pd.read_csv(os.path.join(o, 'GWSoilExchange.csv')) if os.path.exists(os.path.join(o, 'GWSoilExchange.csv')) else None
    w = pd.read_csv(os.path.join(o, 'WatershedStorage.csv'))
    return b, s, w

def checks(d, dt=1.0):
    b, s, w = outputs(d)
    res = {}
    res['mf6_err_rel'] = float(b['MF6 balance error [m3/d]'].abs().max() / max(b['Raven recharge [m3/d]'].abs().max(), 1e-9))
    mb = [c for c in w.columns if 'MB Error' in c]
    gw = [c for c in w.columns if 'Deep Groundwater' in c]
    g = (w[gw[0]] - w[gw[0]].iloc[0]) if gw else 0.0
    res['raven_mb_mm'] = float(((w[mb[0]] - g).abs() / np.maximum(1.0, np.abs(w[gw[0]] if gw else 0.0))).max()) if mb else float('nan')
    rr = b['Raven recharge [m3/d]'] * dt
    dl = b['recharge delay storage [m3]'].diff().fillna(b['recharge delay storage [m3]'])
    rej = b['rejected recharge [m3]'] if 'rejected recharge [m3]' in b else 0.0
    ident = rr - b['MF6 recharge [m3/d]'] * dt - rej - b['recharge onto CHD cells [m3/d]'] * dt - dl
    if 'unsaturated zone inflow [m3]' in b:   # :SoilZoneVadose RICHARDS: recharge passes through the unsaturated columns
        ident = ident - b['unsaturated zone inflow [m3]'] + b['unsaturated zone to aquifer [m3]']
        vzs = b['unsaturated zone storage [m3]']
        vzr = (vzs.diff() - b['unsaturated zone inflow [m3]'] + b['capillary rise to soil zone [m3]'] + b['unsaturated zone to aquifer [m3]'])[1:]
        res['vz_identity'] = float((vzr.abs() / (b['unsaturated zone inflow [m3]'].abs() + b['unsaturated zone to aquifer [m3]'].abs() + vzs.abs() * 1e-9).clip(lower=1.0)[1:]).max()) if len(vzr) else 0.0
    res['rch_identity'] = float((ident.abs() / rr.abs().clip(lower=1e-9)).max())
    if 'soil-zone exchange applied to Raven [m3]' in b:
        sz = b['soil-zone exchange applied to Raven [m3]'] - rej - (b['aquifer to soil zone [m3/d]'] - b['soil zone to aquifer [m3/d]']) * dt - b['soil-zone shortfall [m3]']
        if 'capillary rise to soil zone [m3]' in b: sz = sz - b['capillary rise to soil zone [m3]']
        wt = b['capillary rise from the water table [m3]'] if 'capillary rise from the water table [m3]' in b else 0.0
        sz = sz - wt   # rise from the water table (taken from the aquifer through SZQ_RAVEN, booked apart from the contact exchange)
        if 'soil zone to specified heads [m3/d]' in b:   # columns over specified heads (no MODFLOW boundary)
            sz = sz - (b['specified heads to soil zone [m3/d]'] - b['soil zone to specified heads [m3/d]']) * dt
        if 'lagged-exchange debt [m3]' in b:   # LAGGED: lagged source the processes used beyond the exchange (repaid by the aquifer later)
            sz = sz - b['lagged-exchange debt [m3]']
            res['lag_debt_open'] = float(b['lagged-exchange debt [m3]'].sum() - b['lagged-exchange repayment [m3]'].sum())
        scale = (b['soil-zone exchange applied to Raven [m3]'].abs() + rej.abs() + (b['aquifer to soil zone [m3/d]']
                 + b['soil zone to aquifer [m3/d]']) * dt + wt).clip(lower=1.0)
        res['sz_identity'] = float((sz.abs() / scale).max())   # relative: the CSV carries 10 significant digits
        res['shortfall'] = float(b['soil-zone shortfall [m3]'].sum())
        res['iface_not_conv'] = int((b['interface converged'] == 0).sum())
        res['max_updates'] = int(b['interface updates'].max())
    res['mf6_not_conv'] = int((b['converged'] == 0).sum())
    return res

def report(name, res, limits):
    ok = True
    for k, lim in limits.items():
        v = res.get(k, float('nan'))
        good = (v <= lim)
        ok &= bool(good)
        print('  %-34s %-12.3g %s (limit %g)' % (k, v, 'ok' if good else 'FAIL', lim))
    return ok

STD_LIMITS = {'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 5e-9, 'sz_identity': 1e-8, 'shortfall': 1e-6,
              'iface_not_conv': 0, 'mf6_not_conv': 0}
