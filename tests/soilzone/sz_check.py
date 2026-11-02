"""Shared run and check helpers of the soil-zone tests.

run(d) runs Raven in folder d; checks(d) returns a dict of the identities of plan §7 (all must be ~0):
  mf6_err_rel      max |MODFLOW balance error| [m3/d] / max Raven recharge [m3/d] (a percentage of the gross aquifer flow
                   is meaningless when nearly all recharge is rejected and the aquifer flow is tiny)
  raven_mb_mm      max |Raven's water-balance error - (GROUNDWATER store - its initial value)| / max(1, store) [-]:
                   Raven counts the end-of-step GROUNDWATER pass-through store both as storage and as outflow, so its
                   MB error equals the change of that store (WatershedStorage.csv carries 6 significant digits, hence
                   the relative form)
  rch_identity     max |Raven recharge - MF6 recharge - rejected - CHD - delay change (- column inflow + column outflow)|
                   / (sum of the magnitudes of those terms, at least 1 m3), per step
  sz_identity      max |soil-zone exchange applied to Raven - rejected - (aquifer to soil - soil to aquifer)*dt - shortfall
                   - capillary rise (from the unsaturated columns and from the water table)|
                   / (sum of the magnitudes of those terms, at least 1 m3), per step
  shortfall        total soil-zone shortfall [m3]
  vz_identity      (:SoilZoneVadose RICHARDS) max |storage change - inflow + capillary rise + outflow| of the unsaturated
                   columns / max(1 m3, flows), from the first step when GWModelSummary.txt gives the storage at the start
                   (vz_start; res['vz_step1']), else from the second (the recharge identity then includes the columns)
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

def vz_start(d):
    """the unsaturated columns' storage at the start of the run [m3] (GWModelSummary.txt: "unsaturated storage   : V m3 at
    the start"), or None (no such line: no columns, or a build older than )"""
    import re
    f = os.path.join(d, 'out', 'GWModelSummary.txt')
    if not os.path.exists(f): return None
    m = re.search(r'^\s*unsaturated storage\s*:\s*(\S+) m3 at the start', open(f).read(), re.M)
    return float(m.group(1)) if m else None

def checks(d, dt=1.0):
    b, s, w = outputs(d)
    res = {}
    res['mf6_err_rel'] = float(b['MF6 balance error [m3/d]'].abs().max() / max(b['Raven recharge [m3/d]'].abs().max(), 1.0))   # (1 m3/d floor: dry spells)
    mb = [c for c in w.columns if 'MB Error' in c]
    gw = [c for c in w.columns if 'Deep Groundwater' in c]
    g = (w[gw[0]] - w[gw[0]].iloc[0]) if gw else 0.0
    res['raven_mb_mm'] = float(((w[mb[0]] - g).abs() / np.maximum(1.0, np.abs(w[gw[0]] if gw else 0.0))).max()) if mb else float('nan')
    rr = b['Raven recharge [m3/d]'] * dt
    dl = b['recharge delay storage [m3]'].diff().fillna(b['recharge delay storage [m3]'])
    rej = b['rejected recharge [m3]'] if 'rejected recharge [m3]' in b else 0.0
    ident = rr - b['MF6 recharge [m3/d]'] * dt - rej - b['recharge onto CHD cells [m3/d]'] * dt - dl
    if 'recharge not applied by MODFLOW [m3/d]' in b:   # existing model without NEWTON
        ident = ident - b['recharge not applied by MODFLOW [m3/d]'] * dt
    if 'unsaturated zone inflow [m3]' in b:   # :SoilZoneVadose RICHARDS: recharge passes through the unsaturated columns
        ident = ident - b['unsaturated zone inflow [m3]'] + b['unsaturated zone to aquifer [m3]']
        vzs = b['unsaturated zone storage [m3]']
        s0 = vz_start(d)   # storage at the start (from step 1 when Raven writes it, until then from step 2)
        res['vz_step1'] = s0 is not None
        ds = vzs.diff(); sp = vzs.shift()
        if s0 is not None: ds.iloc[0] = vzs.iloc[0] - s0; sp.iloc[0] = s0
        vin, vout, vcap = b['unsaturated zone inflow [m3]'], b['unsaturated zone to aquifer [m3]'], b['capillary rise to soil zone [m3]']
        vzr = ds - vin + vcap + vout
        # scale: the step's flows plus the two storages (GWBudget.csv carries 10 significant digits: a store of 1e4 m3 is known
        # to ~1e-6 m3 only, so its rounding must not fail the identity; kin/lag design notes)
        sc = (vin.abs() + vout.abs() + vcap.abs() + vzs.abs() + sp.abs()).clip(lower=1.0)
        k0 = 0 if s0 is not None else 1
        res['vz_identity'] = float((vzr.abs() / sc)[k0:].max()) if len(vzr) > k0 else 0.0
    gross = rr.abs() + (b['MF6 recharge [m3/d]'] * dt).abs() + (rej.abs() if hasattr(rej, 'abs') else 0.0) + (b['recharge onto CHD cells [m3/d]'] * dt).abs() + dl.abs()
    if 'unsaturated zone inflow [m3]' in b: gross = gross + b['unsaturated zone inflow [m3]'].abs() + b['unsaturated zone to aquifer [m3]'].abs()
    res['rch_identity'] = float((ident.abs() / gross.clip(lower=1.0)).max())   # (by the terms' magnitudes, at least 1 m3: dry steps have no recharge)
    if 'soil-zone exchange applied to Raven [m3]' in b:
        sz = b['soil-zone exchange applied to Raven [m3]'] - rej - (b['aquifer to soil zone [m3/d]'] - b['soil zone to aquifer [m3/d]']) * dt - b['soil-zone shortfall [m3]']
        if 'capillary rise to soil zone [m3]' in b: sz = sz - b['capillary rise to soil zone [m3]']
        wt = b['capillary rise from the water table [m3]'] if 'capillary rise from the water table [m3]' in b else 0.0
        sz = sz - wt   # rise from the water table (taken from the aquifer through SZQ_RAVEN, booked apart from the contact exchange)
        nh = b['negative recharge the soil zone did not hold [m3]'] if 'negative recharge the soil zone did not hold [m3]' in b else 0.0
        sz = sz - nh   # (a cut of a negative recharge the soil zone did not hold: not taken from it)
        res['neg_unheld'] = float(nh.sum()) if hasattr(nh, 'sum') else 0.0
        if 'soil zone to specified heads [m3/d]' in b:   # columns over specified heads (no MODFLOW boundary)
            sz = sz - (b['specified heads to soil zone [m3/d]'] - b['soil zone to specified heads [m3/d]']) * dt
        if 'lagged-exchange debt [m3]' in b:   # LAGGED: lagged source the processes used beyond the exchange (repaid by the aquifer later)
            sz = sz - b['lagged-exchange debt [m3]']
            res['lag_debt_open'] = float(b['lagged-exchange debt [m3]'].sum() - b['lagged-exchange repayment [m3]'].sum())
        scale = (b['soil-zone exchange applied to Raven [m3]'].abs() + rej.abs() + (b['aquifer to soil zone [m3/d]']
                 + b['soil zone to aquifer [m3/d]']) * dt + wt + (nh.abs() if hasattr(nh, 'abs') else 0.0)).clip(lower=1.0)
        res['sz_identity'] = float((sz.abs() / scale).max())   # relative: the CSV carries 10 significant digits
        res['shortfall'] = float(b['soil-zone shortfall [m3]'].sum())
        res['iface_not_conv'] = int((b['interface converged'] == 0).sum())
        res['max_updates'] = int(b['interface updates'].max())
    res['mf6_not_conv'] = int((b['converged'] == 0).sum())
    return res

def report(name, res, limits):
    ok = True
    for k, lim in limits.items():
        if k not in res:   # (not in this run: no columns, no soil zone)
            continue
        v = res[k]
        good = (v <= lim)
        ok &= bool(good)
        print('  %-34s %-12.3g %s (limit %g)' % (k, v, 'ok' if good else 'FAIL', lim))
    return ok

STD_LIMITS = {'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 5e-9, 'sz_identity': 1e-8, 'shortfall': 1e-6,
              'neg_unheld': 1e-6, 'iface_not_conv': 0, 'mf6_not_conv': 0}
# the identities alone (no convergence counts), the standard limits of every soil-zone test
ID_LIMITS = {'mf6_err_rel': 1e-5, 'raven_mb_mm': 1e-5, 'rch_identity': 5e-9, 'sz_identity': 1e-8, 'vz_identity': 1e-8,
             'shortfall': 1e-6, 'neg_unheld': 1e-6}
DIAGNOSTIC_COLUMNS = ('interface change [m]',)
ADDED_COLUMNS = ('negative recharge the soil zone did not hold [m3]', 'recharge not applied by MODFLOW [m3/d]')

def same_file(a, b, skip=DIAGNOSTIC_COLUMNS, added=()):
    """CSV/rvc files a and b hold the same values (columns in skip left out; columns in added may be in a only)"""
    if not os.path.exists(b): return False
    if a.endswith('.csv'):
        try:
            x, y = pd.read_csv(a), pd.read_csv(b)
        except Exception:
            return open(a, 'rb').read() == open(b, 'rb').read()
        cx = [c for c in x.columns if c not in skip and c not in added]
        cy = [c for c in y.columns if c not in skip and c not in added]
        if cx != cy or len(x) != len(y): return False
        return x[cx].astype(str).equals(y[cy].astype(str))
    return open(a, 'rb').read() == open(b, 'rb').read()

def same_outputs(a, b, skip=DIAGNOSTIC_COLUMNS, added=()):
    """the out/*.csv and out/*.rvc files of run folder a that differ in run folder b (an empty list: the same results);
    the run log and summary carry dates and paths and are not compared; the diagnostic columns (skip) are left out of the
    CSV comparison (DIAGNOSTIC_COLUMNS)"""
    bad = []
    for f in sorted(os.listdir(os.path.join(a, 'out'))):
        if f.endswith('.csv') or f.endswith('.rvc'):
            if not same_file(os.path.join(a, 'out', f), os.path.join(b, 'out', f), skip, added):
                bad.append(f)
    return bad

def ext_case(g, e, cfg, newton=True, model_edit=None):
    """an existing-model case e from the generated run g (made with sz_models.make_case(**cfg) and run): g's MODFLOW model
    without Raven's packages (optionally without NEWTON; model_edit(folder) may change it further) coupled by
    :MF6Simulation with the same HRUs and soil zone (as test_sz_models_ext.roundtrip). Returns e (not run)"""
    import re, shutil, sz_models
    m = e + '_model'; shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in ('gwf.rch', 'gwf.drn', 'gwf.szx', 'gwf.szq', 'gwf.szd', 'gwf.szw', 'linkage.cache', 'mfsim.lst', 'gwf.lst', 'gwf.hds', 'gwf.cbc'):
        if os.path.exists(os.path.join(m, f)): os.remove(os.path.join(m, f))
    nam = open(os.path.join(m, 'gwf.nam')).read()
    nam = '\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN', l))
    if not newton:
        nam = re.sub(r'(?m)^\s*NEWTON.*$', '', nam)
    open(os.path.join(m, 'gwf.nam'), 'w').write(nam)
    if model_edit: model_edit(m)
    shutil.rmtree(e, ignore_errors=True); sz_models.make_case(e, **cfg)
    shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
    rvg = open(os.path.join(e, 'm.rvg')).read()
    drop = (':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary', ':SolverMaxOuterIterations') + (() if cfg.get('physical', True) else (':LandSurface',))
    rvg = '\n'.join(l for l in rvg.split('\n') if not l.startswith(drop))
    rvg += '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m
    open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
    return e

def errors(d):
    p = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(p).read() if os.path.exists(p) else ''

def summary(d):
    p = os.path.join(d, 'out', 'GWModelSummary.txt')
    return open(p).read() if os.path.exists(p) else ''
