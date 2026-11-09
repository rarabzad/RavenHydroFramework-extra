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
  vz_identity      (:SoilZoneVadose RICHARDS, KINEMATIC, LAG) max |storage change - inflow + capillary rise + outflow| of
                   the unsaturated columns, less the rounding of its five values in GWBudget.csv (half a unit in the
                   10th significant digit of each, csv_rounding), / max(1 m3, flows), per step, from the first step when
                   GWModelSummary.txt gives the storage at the start (vz_start; res['vz_step1']), else from the second
                   (the recharge identity then includes the columns). The scale leaves out the storages: added in full,
                   they would let 2e-4 m3 per step through on a 1e4 m3 store where the CSV resolves 1e-6 m3.
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
    the start"), or None (no such line: no columns)"""
    import re
    f = os.path.join(d, 'out', 'GWModelSummary.txt')
    if not os.path.exists(f): return None
    m = re.search(r'^\s*unsaturated storage\s*:\s*(\S+) m3 at the start', open(f).read(), re.M)
    return float(m.group(1)) if m else None

def csv_rounding(x):
    """half a unit in the 10th significant digit of each value (the rounding of GWBudget.csv's numbers) [same units]"""
    a = np.abs(np.asarray(x, dtype=float))
    with np.errstate(divide='ignore'):
        e = np.where(a > 0, np.floor(np.log10(np.where(a > 0, a, 1.0))), -np.inf)
    return 0.5 * np.power(10.0, e - 9)


def vz_identity(vzs, s0, vin, vout, vcap):
    """the unsaturated-zone identity (docstring above) of the storage after each step vzs, the storage at the start s0
    (None: from the second step), and the step volumes in, out and capillary rise [m3] (pandas Series)"""
    ds = vzs.diff(); sp = vzs.shift()
    if s0 is not None: ds.iloc[0] = vzs.iloc[0] - s0; sp.iloc[0] = s0
    vzr = ds - vin + vcap + vout
    # scale: the step's flows (at least 1 m3); the residual less the CSV rounding of its five values (10 significant
    # digits: a store of 12800 m3 is written to 1e-5 m3)
    sc = (vin.abs() + vout.abs() + vcap.abs()).clip(lower=1.0).values
    rnd = csv_rounding(vzs) + csv_rounding(sp.fillna(0.0)) + csv_rounding(vin) + csv_rounding(vout) + csv_rounding(vcap)
    if s0 is not None: rnd[0] = rnd[0] - csv_rounding([s0])[0]      # (the start's storage comes with 15 digits)
    k0 = 0 if s0 is not None else 1
    v = np.clip(np.abs(vzr.values) - rnd, 0.0, None) / sc
    return float(v[k0:].max()) if len(v) > k0 else 0.0


def selftest_vz_identity():
    """the unsaturated-zone identity on synthetic columns (a 9776 m3 store, 220 m3 in and out per step, written with 10
    significant digits as GWBudget.csv does): exact books pass (CSV rounding only), a leak of 1e-4 m3 per step fails (a
    scale with the storages added in full would let it pass). Prints one line; returns True when both hold"""
    n = 60; vin = pd.Series(np.full(n, 220.0) + 13.7 * np.sin(np.arange(n))); vout = vin.shift().fillna(200.0); vcap = pd.Series(np.zeros(n))
    s = 9776.123456789 + np.cumsum(vin - vout - vcap)
    r10 = lambda x: pd.Series([float('%.10g' % v) for v in x])
    exact = vz_identity(r10(s), 9776.123456789, r10(vin), r10(vout), r10(vcap))
    leak = vz_identity(r10(s - 1e-4 * np.arange(1, n + 1)), 9776.123456789, r10(vin), r10(vout), r10(vcap))
    s10 = r10(s - 1e-4 * np.arange(1, n + 1)); ds = s10.diff(); sp = s10.shift(); ds.iloc[0] = s10.iloc[0] - 9776.123456789; sp.iloc[0] = 9776.123456789
    scaled = float(((ds - vin + vcap + vout).abs() / (vin.abs() + vout.abs() + vcap.abs() + s10.abs() + sp.abs()).clip(lower=1.0)).max())
    ok = exact <= 1e-8 and leak > 1e-8
    print('vz_identity self-test: exact books %.2g, a 1e-4 m3/step leak %.2g (a storage-scaled form would give %.2g) -> %s'
          % (exact, leak, scaled, 'ok' if ok else 'FAIL'))
    return ok


def leak_copy(d, dst, leak, smin=5000.0):
    """copies run folder d to dst with a column leak put into GWBudget.csv: on every step whose 'unsaturated zone
    storage [m3]' exceeds smin (large stores, where a storage-scaled identity is loosest) leak m3 are lost, so the
    storage written for that step and every later one is lower by the leaks so far (written with 10 significant digits,
    as Raven writes it; the other values keep their text). Returns the number of leaking steps"""
    import shutil
    shutil.rmtree(dst, ignore_errors=True); shutil.copytree(d, dst)
    p = os.path.join(dst, 'out', 'GWBudget.csv')
    lines = open(p).read().split('\n')
    hdr = [h.strip() for h in lines[0].split(',')]
    k = hdr.index('unsaturated zone storage [m3]')
    n = 0
    for i in range(1, len(lines)):
        f = lines[i].split(',')
        if len(f) <= k: continue
        v = float(f[k])
        if v > smin:
            n += 1
        if n > 0:
            f[k] = '%.10g' % (v - leak * n)
            lines[i] = ','.join(f)
    open(p, 'w').write('\n'.join(lines))
    return n


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
        s0 = vz_start(d)   # storage at the start (from step 1 when Raven writes it)
        res['vz_step1'] = s0 is not None
        ds = vzs.diff(); sp = vzs.shift()
        if s0 is not None: ds.iloc[0] = vzs.iloc[0] - s0; sp.iloc[0] = s0
        vin, vout, vcap = b['unsaturated zone inflow [m3]'], b['unsaturated zone to aquifer [m3]'], b['capillary rise to soil zone [m3]']
        res['vz_identity'] = vz_identity(vzs, s0, vin, vout, vcap)
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
    :MF6Simulation with the same HRUs and soil zone (as test_sz_existing.roundtrip). Returns e (not run)"""
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

def rvc_text(p):
    """the text of a solution.rvc without its :GWVadoseColumnTops block (the columns' tops and water, written since the
    restart match checks the tops): byte-identity checks against a reference build that does not write it compare the rest"""
    import re
    return re.sub(r':GWVadoseColumnTops[^\n]*\n.*?:EndGWVadoseColumnTops\n', '', open(p).read(), flags=re.S)

def errors(d):
    p = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(p).read() if os.path.exists(p) else ''

def summary(d):
    p = os.path.join(d, 'out', 'GWModelSummary.txt')
    return open(p).read() if os.path.exists(p) else ''


if __name__ == '__main__':
    sys.exit(0 if selftest_vz_identity() else 1)
