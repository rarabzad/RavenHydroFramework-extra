"""Rough-terrain stress suite of the soil-zone coupling (cases from rough_models.py; manual, "Verification on rough
terrain").

Every case is drawn from a seed (rough_models.gen_spec; every fourth seed an existing MODFLOW model, rough_ext.py) and run
once per unsaturated-zone method. Checks on every run:
  run       the run completes, or stops with one of the justified messages in STOPS (reported, not a failure)
  finite    no NaN or Inf in any output table, no non-finite head, no HDRY head in an active cell under NEWTON
  ident     sz_check identities at round-off (sz_check.ID_LIMITS): rch_identity, sz_identity, vz_identity, mf6_err_rel,
            raven_mb, and no soil-zone shortfall on a step whose interface converged
  layers    (generated models) TOP, BOTM and IDOMAIN that MODFLOW read equal an independent construction from the DEM,
            the bedrock raster and the profiles (manual, "Building the layers": top = land - overlap-weighted D, clipping
            at bedrock, 0.5 m minimum, pass-through cells)
  base      the soil-zone base of every HRU equals the overlap-weighted cell land surface (5x5 DEM samples, Raven's
            bilinear rule) less its D (existing models: the top of the top active cell)
  satfrac   with :SoilZoneVadose NONE, the saturated fraction of every HRU equals an independent sub-grid closure (the
            cell's DEM samples less D, none below 1 mm above the top cell's bottom, smoothed over d_s) at a head between the top
            cells' heads at the start and at the end of the step, on every step whose interface converged (0.02); being
            a closure of the heads it is monotone in the water table of each cell. With a column method the difference
            is only reported (the reported F of a link whose column carries the step is not the one that rejected)
  physics   0 <= F <= 1; soil water within [0, capacity]; rejected recharge and overflow >= 0; with :SoilZoneVadose
            NONE the rejected recharge at most the HRU's recharge (custom output Between:SOIL[1].And.GROUNDWATER), only
            where F > 0 and equal to F times the recharge on HRUs over one cell; with a column method (whose columns give
            water stored in earlier steps back to the soil zone where the water table reaches the base) all rejected
            recharge of a step at most the step's recharge plus the columns' storage at its start (GWBudget)
  heads     with a column method, no water table more than EXF above the highest land sample of its cell, unless the
            NONE run of the same case already lifts it to within 1 m of that height (none_exf)
  conv      steps on which MODFLOW or the interface did not converge (counted; a failure beyond MAXNC per cent)
Diagnostics: largest water table above the highest land sample of a cell (exfiltration), outer iterations, run time.
Regression cases (minimal repros of the problems the suite found, rough_cases/*.json and one flat case) run first, each
with its own checks besides the above (REG: the saturated-fraction limit RFTOL of R20 for any method; R6, R11-R13 and
R19 must complete); KNOWN lists the open ones by case and KNOWN_PATTERNS by kind (one: interface unconverged where land
lies below the top cell's bottom); a run is XFAIL only when every failure it has, its regression case's own included, is
a known one (a known case that fails otherwise is FAIL; one that passes is XPASS, a note).
A stop is justified (STOPS, or MODFLOW 6 alone): an outcrop case; an existing model without NEWTON; or a diverged solve
(non-finite heads, or a head far outside the model on an unconverged step) that MODFLOW 6 repeats on its own: the run's
MODFLOW model without Raven's packages, with drains at the top of every column as the only outlet and no recharge, run
through libmf6 for the run's duration, gives non-finite heads or changes a head by more than 1e6 m within its outer
iterations (mf6_alone_diverges). A column held 1 mm above its bottom (drained) is only reported.

Usage: python3 test_rough_terrain.py [--quick | --full] [--methods NONE,RICHARDS] [--vzclasses K] [--seeds a-b]
           [--family gen|ext|both] [--keep] [--case SEED[:method] | --case xSEED[:method] (existing, e.g. x43) | --case file.json[:method]]
           (file.json: a stored case, rough_cases/*.json, or a run folder's case.json; a column method replayed alone is
           preceded by the case's NONE run, whose water table its own is compared with, as in the seed loop; a stored
           regression case applies its own checks; the exit status is the run's)
           [--noreg]
  default  regression cases + 400 seeds x NONE and RICHARDS (about 10 minutes on one core); --quick 40 seeds (also with
           RAVEN_TEST_QUICK=1), --full 1500 seeds
  --make-cases rewrites rough_cases/*.json from their seeds and overrides (CASE_SOURCES)
"""
import os, sys, json, math, time, shutil, argparse, re, traceback, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import rough_models as rm, sz_check
from sz_models import ll, xy

W = sz_check.tc.work('soilzone', 'rough')
LIM = dict(getattr(sz_check, 'ID_LIMITS', {'rch_identity': 5e-9, 'sz_identity': 1e-8, 'vz_identity': 1e-8, 'mf6_err_rel': 1e-5,
                                            'raven_mb_mm': 1e-5, 'shortfall': 1e-6, 'neg_unheld': 1e-6}))
for _k in ('iface_not_conv', 'mf6_not_conv'): LIM.pop(_k, None)   # (counted by conv, not identities)
# (the standard limits: recharge identity 5e-9, soil-zone and unsaturated-zone identities 1e-8)
# justified stops: (regex of Raven's message, why, condition on the case)
STOPS = [(r'does not overlap any active groundwater cell', 'bedrock reaches the model top under a whole HRU (outcrop case)',
          lambda S: S.get('outcrop', False)),
         (r'needs an existing model that uses the Newton-Raphson formulation', 'existing model without NEWTON (required with :SoilZone PHYSICAL)',
          lambda S: S['family'] == 'ext' and not S['ext']['newton'])]
DIVERGED = r'heads are not finite|lies far outside the model'
MAXNC = 5.0         # [%] steps MODFLOW / the interface may leave unconverged before the case fails
FTOL = {'NONE': 0.02}   # saturated fraction against the independent closure on converged steps (other methods: reported only,
                        # the reported F of a link whose column carries the step is the connection's, not the rejecting one)
EXF = 5.0           # [m] water table above the highest land sample of its cell (column methods; more than 1 m above NONE's)
EXF_NONE = 1.0      # [m] allowance above the NONE run's largest
GEO_TOL = 1e-6      # [m] layers and bases against the independent construction (MODFLOW's files carry 10 digits)
KNOWN = {}          # open problems by case name
KNOWN_PATTERNS = [  # (what, regex of a failure, condition on the run's result)
    ('interface unconverged where land lies below the top cell\'s bottom', r'^unconverged steps: interface',
     lambda r: r.get('deep_links', False))]
METHODS = rm.METHODS

def _skip(what, why):
    f = getattr(sz_check.tc, 'skip', None)
    if f: f(what, why)
    else: print('SKIP %s: %s' % (what, why))

def smooth(x):
    x = np.clip(x, 0.0, 1.0); return x * x * (3.0 - 2.0 * x)

def closure(h, zbs, ds):
    """saturated fraction of one link at head h (manual eq. of F; independent of Raven's code)"""
    z = np.asarray(zbs)
    return float(np.mean((h > z).astype(float))) if ds <= 0 else float(np.mean(smooth((h - z) / ds)))

# ---------------------------------------------------------------------------------------------------- MODFLOW alone
ALONE = r'''
import sys, numpy as np
from xmipy import XmiWrapper
lib, wd, nmax = sys.argv[1], sys.argv[2], int(sys.argv[3])
mf = XmiWrapper(lib, working_directory=wd); mf.initialize()
x = mf.get_value_ptr(mf.get_var_address('X', 'GWF')); prev = x.copy(); bad = False
try:
    while mf.get_current_time() < mf.get_end_time() and not bad:
        dt = mf.get_time_step(); mf.prepare_time_step(dt); mf.prepare_solve(1)
        for it in range(nmax):
            conv = mf.solve(1)
            if (not np.all(np.isfinite(x))) or np.max(np.abs(x - prev)) > 1e6: bad = True; break
            if conv: break
        mf.finalize_solve(1); mf.finalize_time_step(); prev = x.copy()
except Exception as e:
    bad = True
print('ALONE_DIVERGES' if bad else 'ALONE_OK')
'''

def mf6_alone_diverges(d):
    """MODFLOW 6 alone on the run's model: without Raven's packages, drains at the top of every column (leakance 1/d) as the
    only outlet, no recharge, for the run's duration: True when its heads become non-finite or move more than 1e6 m"""
    import flopy
    src = os.path.join(d, 'out', 'mf6'); a = os.path.join(d, 'alone'); shutil.rmtree(a, ignore_errors=True); shutil.copytree(src, a)
    nam = open(os.path.join(a, 'gwf.nam')).read()
    keep = [l for l in nam.split('\n') if not re.search(r'RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN|raven\.(rch|drn|szx|szq|szd|szw)', l)]
    g = flopy.mf6.utils.MfGrdFile(os.path.join(a, 'gwf.dis.grb'))
    idm = np.array(g.modelgrid.idomain).reshape(-1); top = np.array(g.top).reshape(-1); bot = np.array(g.bot).reshape(-1)
    ncpl = len(top); nlay = len(bot) // ncpl; idm = idm.reshape(nlay, ncpl); bot = bot.reshape(nlay, ncpl)
    rows = []
    for ic in range(ncpl):
        act = np.where(idm[:, ic] > 0)[0]
        if not len(act): continue
        l = act[0]; zt = top[ic] if l == 0 else bot[l - 1, ic]
        cid = ('%d %d %d' % (l + 1, ic // g.modelgrid.ncol + 1, ic % g.modelgrid.ncol + 1)) if g.grid_type == 'DIS' else '%d %d' % (l + 1, ic + 1)
        rows.append('  %s %.10f %.6g' % (cid, zt, 1.0 * 1e4))
    open(os.path.join(a, 'alone.drn'), 'w').write('BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  MAXBOUND %d\nEND DIMENSIONS\n\nBEGIN PERIOD 1\n%s\nEND PERIOD\n' % (len(rows), '\n'.join(rows)))
    out = []
    for l in keep:
        if l.strip().upper() == 'END PACKAGES': out.append('  DRN6  alone.drn  DRN_ALONE')
        out.append(l)
    open(os.path.join(a, 'gwf.nam'), 'w').write('\n'.join(out))
    ims = open(os.path.join(a, 'sim.ims')).read(); m = re.search(r'OUTER_MAXIMUM\s+(\d+)', ims, re.I); nmax = int(m.group(1)) if m else 100
    r = subprocess.run([sys.executable, '-c', ALONE, sz_check.tc.MF6LIB, a, str(nmax)], capture_output=True, text=True, timeout=1800)
    return 'ALONE_DIVERGES' in r.stdout

# ---------------------------------------------------------------------------------------------------- one run
def _links(S, meta, G):
    """per HRU: [(cell, overlap area)] of its soil-zone exchange links (active columns, no specified head at the top)"""
    chd = set(meta.get('chd_cells', [])) if S['family'] == 'gen' else set()
    out = []
    for k in range(len(meta['polys'])):
        out.append([(ic, A) for ic, A in G['ov'][k].items() if G['top_node'][ic] >= 0 and ic not in chd])
    return out

def _chd_links(S, meta, G):
    """per HRU: [(cell, overlap area)] of its links on specified-head cells (generated cases). GWSoilExchange.csv's saturated
    fraction includes these columns at the fixed head (rule: the fraction goes with the rejected recharge, which
    includes them), so the closure includes them the same way"""
    chd = set(meta.get('chd_cells', [])) if S['family'] == 'gen' else set()
    return [[(ic, A) for ic, A in G['ov'][k].items() if G['top_node'][ic] >= 0 and ic in chd] for k in range(len(meta['polys']))]

def _ext_geometry(d, S, meta):
    """the geometry of an existing model as written (rough_ext.py), with the DEM samples Raven takes in each cell"""
    from shapely.geometry import Polygon
    E = meta['ext']; dem = rm.Raster(os.path.join(d, 'dem.asc'))
    rings = E['rings']; ncpl = len(rings); top = np.array(E['top']); botm = np.array(E['botm']); idm = np.array(E['idomain'])
    cellP = [Polygon(r) for r in rings]; polys = [Polygon(p) for p in meta['polys']]
    ov = [dict() for _ in polys]
    for k, p in enumerate(polys):
        for ic in range(ncpl):
            if p.intersects(cellP[ic]):
                A = p.intersection(cellP[ic]).area
                if A > 1e-6: ov[k][ic] = A
    samples, high = {}, {}
    rect = S['ext']['dis'] == 'DIS'
    for ic in range(ncpl):
        b = cellP[ic].bounds
        pts5 = rm.sample_points(b[0], b[2], b[1], b[3], 5, None if rect else rings[ic])
        lo, la = rm.ll_np([p[0] for p in pts5], [p[1] for p in pts5]); v5 = dem.sample(lo, la); v5 = v5[np.isfinite(v5)]
        s = []
        if S['subgrid'] > 1:
            pts = rm.sample_points(b[0], b[2], b[1], b[3], S['subgrid'], None if rect else rings[ic])
            lo, la = rm.ll_np([p[0] for p in pts], [p[1] for p in pts]); s = list(dem.sample(lo, la)); s = [x for x in s if np.isfinite(x)]
        samples[ic] = s if s else None
        high[ic] = max(list(v5) + s) if (len(v5) or s) else top[ic]
    cov = np.zeros(ncpl)
    for k in range(len(polys)):
        for ic, A in ov[k].items(): cov[ic] += A
    covered = [cov[ic] >= S['min_cover'] * cellP[ic].area for ic in range(ncpl)]   # (:MinCellCoverage applies to existing models too)
    return dict(ncpl=ncpl, ov=ov, top=top, botm=botm, idomain=idm, samples=samples, high=high, nlay=botm.shape[0], covered=covered)

def run_case(name, S, method='NONE', vz_classes=1, keep=False, none_exf=None, days=None, extra_rvg=''):
    """builds, runs and checks one case; returns the result dict (status by decide())"""
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    res = dict(name=name, method=method, fails=[], notes=[], family=S['family'], seed=S.get('seed'), case=S.get('case_name'))
    try:
        meta = rm.build(d, S, method, vz_classes, extra_rvg=extra_rvg, days=days)
        t0 = time.time(); ok, txt = sz_check.run(d); res['time'] = time.time() - t0
        if not ok:
            m = re.search(r'Exiting Gracefully: (.*)', txt); msg = m.group(1).strip() if m else txt[-300:]
            res['stop'] = msg
            for rx, why, cond in STOPS:
                if re.search(rx, msg) and cond(S):
                    res['stopped'] = why; break
            else:
                if re.search(DIVERGED, msg):
                    if mf6_alone_diverges(d):
                        res['stopped'] = 'a diverged solve that MODFLOW 6 alone repeats'; res['alone'] = True
                    else:
                        res['fails'].append('run stopped (MODFLOW 6 alone does not diverge): %s' % msg)
                else:
                    res['fails'].append('run stopped: %s' % msg)
            return decide(res, keep, d)
        check(d, S, meta, res, none_exf)
    except Exception:
        res['fails'].append('exception: ' + traceback.format_exc().strip().split('\n')[-1]); res['trace'] = traceback.format_exc()
    return decide(res, keep, d)

def decide(res, keep=False, d=None):
    """status: PASS, STOP (justified), XFAIL (every failure a known one), XPASS (a known case that passed), FAIL"""
    known = KNOWN.get('%s_%s' % (res.get('case') or res['name'], res['method']))
    if not res['fails']:
        res['status'] = 'STOP' if res.get('stopped') else ('XPASS' if known else 'PASS')
    else:
        def is_known(f):
            if f.startswith('shortfall'): return False          # (a shortfall on a converged step is a defect: never known)
            if known and re.search(known, f): return True
            return any(re.search(rx, f) and cond(res) for _, rx, cond in KNOWN_PATTERNS)
        res['status'] = 'XFAIL' if all(is_known(f) for f in res['fails']) else 'FAIL'
    res['ok'] = res['status'] != 'FAIL'
    if d and not keep and res['ok']: shutil.rmtree(d, ignore_errors=True)
    return res

def check(d, S, meta, res, none_exf):
    import flopy
    F = res['fails']; method = res['method']
    o = os.path.join(d, 'out')
    b, s, w = sz_check.outputs(d)
    res['steps'] = len(b); res['outer'] = int(b['outer iterations'].sum())
    # finite
    for f in sorted(os.listdir(o)):
        if f.endswith('.csv'):
            if re.search(r'(^|,)\s*[-+]?(nan|inf|infinity)\s*(,|$)', open(os.path.join(o, f)).read(), re.I | re.M):
                F.append('non-finite values in %s' % f)
    # identities
    r = sz_check.checks(d); res['ident'] = {k: r[k] for k in LIM if k in r}
    for k, lim in LIM.items():
        if k in r and not (r[k] <= lim): F.append('identity %s %.3g (limit %g)' % (k, r[k], lim))
    ic_ = b['interface converged'] != 0; mc_ = b['converged'] != 0
    sh = b['soil-zone shortfall [m3]']
    if (sh[ic_].abs() > 1e-6).any(): F.append('shortfall %.3g m3 on a step whose interface converged' % sh[ic_].abs().max())
    # conv
    res['mf6_nc'] = int((~mc_).sum()); res['iface_nc'] = int((~ic_).sum())
    if 100.0 * res['iface_nc'] / max(len(b), 1) > MAXNC: F.append('unconverged steps: interface on %d of %d' % (res['iface_nc'], len(b)))
    if 100.0 * res['mf6_nc'] / max(len(b), 1) > MAXNC: F.append('unconverged steps: MODFLOW on %d of %d' % (res['mf6_nc'], len(b)))
    if 'drained' in open(os.path.join(o, 'GWModelSummary.txt')).read():
        m = re.search(r'drained columns[^\n]*', open(os.path.join(o, 'GWModelSummary.txt')).read())
        if m and re.search(r'[1-9]', m.group(0)): res['notes'].append(m.group(0).strip())
    # geometry
    g = flopy.mf6.utils.MfGrdFile(os.path.join(o, 'mf6', 'gwf.dis.grb')); mg = g.modelgrid
    top = np.array(g.top, float).reshape(-1); ncpl = len(top); bot = np.array(g.bot, float).reshape(-1, ncpl); nlay = bot.shape[0]
    idm = np.array(mg.idomain).reshape(nlay, ncpl)
    if S['family'] == 'gen':
        G = rm.geometry(d, S, meta, grid=(mg.xoffset, mg.yoffset, mg.nrow, mg.ncol))
        act = np.array([G['prof'][i] >= 0 for i in range(ncpl)])
        if not np.array_equal(act, (idm != 0).any(axis=0)): F.append('layers: active columns differ from the independent construction')
        a2 = act & (idm != 0).any(axis=0)
        res['layers_err'] = float(max(np.abs(top - G['top'])[a2].max(initial=0.0), np.abs(bot - G['botm'])[:, a2].max(initial=0.0)))
        nid = int((idm[:, a2] != G['idomain'][:, a2]).sum())
        if res['layers_err'] > GEO_TOL or nid: F.append('layers: TOP/BOTM up to %.3g m, %d IDOMAIN values differ from the independent construction' % (res['layers_err'], nid))
        G['top_node'] = [int(np.argmax(idm[:, ic] > 0)) if (idm[:, ic] > 0).any() else -1 for ic in range(ncpl)]
        newton = True
    else:
        G = _ext_geometry(d, S, meta)
        G['top_node'] = [int(np.argmax(idm[:, ic] > 0)) if ((idm[:, ic] > 0).any() and G['covered'][ic]) else -1 for ic in range(ncpl)]
        newton = S['ext']['newton']
    tn = G['top_node']
    def ztop(ic):
        return top[ic] if tn[ic] == 0 else bot[tn[ic] - 1, ic]
    links = _links(S, meta, G)
    flinks = [L + C for L, C in zip(links, _chd_links(S, meta, G))]   # (the saturated fraction's links: specified heads included, X5)
    Dk = meta['Dk']
    # base
    if s is not None:
        s0 = s[s['time [d]'] == s['time [d]'].min()].set_index('HRU_ID')
        berr = 0.0
        for k, L in enumerate(links):
            if not L or (k + 1) not in s0.index: continue
            A = sum(a for _, a in L)
            zb = sum(a * ((G['land'][ic] - Dk[k]) if S['family'] == 'gen' else ztop(ic)) for ic, a in L) / A
            berr = max(berr, abs(zb - s0.loc[k + 1, 'soil-zone base [m]']))
        res['base_err'] = berr
        if berr > GEO_TOL: F.append('base: soil-zone base differs from the independent construction by %.3g m' % berr)
    # link closures
    zbs = {}
    deep = False
    for k, L in enumerate(flinks):
        for ic, a in L:
            bl = bot[tn[ic], ic]
            if S['family'] == 'gen':
                z = np.array(G['samples'][ic]) - Dk[k]
            else:
                smp = G['samples'][ic]
                z = np.array([ztop(ic)]) if not smp else ztop(ic) + (np.array(smp) - np.mean(smp))
            if (z < bl + 1e-3).any(): deep = True
            zbs[(k, ic)] = np.maximum(z, bl + 1e-3)
    res['deep_links'] = deep
    # heads
    hf = flopy.utils.HeadFile(os.path.join(o, 'mf6', 'gwf.hds'))
    times = hf.get_times(); H = {round(t, 6): hf.get_data(totim=t).reshape(nlay, ncpl) for t in times}
    exf = -1e30; nonf = False; hdry = False
    for t, h in H.items():
        for ic in range(ncpl):
            if tn[ic] < 0: continue
            hv = h[idm[:, ic] > 0, ic]
            if not np.all(np.isfinite(hv)): nonf = True; continue
            if (np.abs(hv) > 1e29).any():
                hdry = True; hv = hv[np.abs(hv) < 1e29]
                if not len(hv): continue
            exf = max(exf, float(hv.max()) - G['high'][ic])
    if nonf: F.append('non-finite heads')
    if hdry and newton: F.append('HDRY head in an active cell under NEWTON')
    res['exfil_max'] = exf
    if method != 'NONE' and exf > EXF and (none_exf is None or exf > none_exf + EXF_NONE):
        F.append('water table %.1f m above the highest land sample of a cell' % exf + ('' if none_exf is None else ' (NONE: %.1f m)' % none_exf))
    # starting heads (as built: land/top less INITIAL_HEAD_DEPTH, at least 0.1 m above the lowest active bottom)
    h0 = np.zeros(ncpl)
    for ic in range(ncpl):
        if tn[ic] < 0: continue
        low = bot[np.where(idm[:, ic] > 0)[0][-1], ic]
        h0[ic] = max((G['land'][ic] if S['family'] == 'gen' else top[ic]) - S['init_depth'], low + 0.1)
    # satfrac and physics
    if s is not None:
        bconv = dict(zip(b['time [d]'].round(6), ic_ & mc_))
        rch = None
        cf = [f for f in os.listdir(o) if f.upper().startswith('BETWEEN_SOIL[1]_AND_GROUNDWATER')]
        if cf:
            c = pd.read_csv(os.path.join(o, cf[0]), header=None, skiprows=2)
            hdr = pd.read_csv(os.path.join(o, cf[0]), header=None, nrows=1).iloc[0].tolist()
            ids = [int(float(x)) for x in hdr[2:] if str(x) not in ('nan', '')]
            cum = {round(float(row[0]), 6): np.array([float(x) for x in row[2:2 + len(ids)]]) for _, row in c.iterrows()}
            rch, last = {}, np.zeros(len(ids))   # (the custom output holds the running total [mm]: the step's recharge is its change)
            rtol = {}
            for t in sorted(cum): rch[t] = dict(zip(ids, cum[t] - last)); rtol[t] = dict(zip(ids, 1e-5 * np.abs(cum[t]) + 1e-6)); last = cum[t]
        one = {k: (len(L) == 1 and abs(sum(a for _, a in L) - meta['areas'][k]) < 1e-6 * meta['areas'][k]) for k, L in enumerate(links)}
        chd_hru = set()
        if S['family'] == 'gen':
            for k in range(len(links)):
                if any(ic in set(meta.get('chd_cells', [])) for ic in G['ov'][k]): chd_hru.add(k)
        else:
            cc = set(ic for _, ic in meta['ext'].get('chd_cells', []))
            for k in range(len(links)):
                if any(ic in cc for ic in G['ov'][k]): chd_hru.add(k)
        ferr, fbad, wbad, negs, rej_over, rej_eq, rej_nof = 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
        tprev = None
        for t in sorted(s['time [d]'].unique()):
            tt = round(float(t), 6); rows = s[s['time [d]'] == t].set_index('HRU_ID')
            hs = H.get(round(tprev, 6)) if tprev is not None else None; he = H.get(tt)
            for k, L in enumerate(links):
                if (k + 1) not in rows.index: continue
                row = rows.loc[k + 1]; Fr = row['saturated fraction [-]']
                fbad = max(fbad, -Fr, Fr - 1.0)
                wbad = max(wbad, -row['soil-zone water [mm]'], row['soil-zone water [mm]'] - row['soil-zone capacity [mm]'] * (1 + 1e-9))
                negs = max(negs, -row['rejected recharge [mm]'], -row['overflow [mm]'])
                if L and he is not None and bconv.get(tt, False):
                    LF = flinks[k]   # (with the columns over specified heads at the fixed head, as Raven reports F: X5)
                    A = sum(a for _, a in LF); lo = hi = 0.0
                    for ic, a in LF:
                        h1 = he[tn[ic], ic]; h0c = hs[tn[ic], ic] if hs is not None else h0[ic]
                        f0, f1 = closure(h0c, zbs[(k, ic)], S['ds']), closure(h1, zbs[(k, ic)], S['ds'])
                        lo += a * min(f0, f1); hi += a * max(f0, f1)
                    lo /= A; hi /= A
                    if max(lo - Fr, Fr - hi) > ferr: ferr = max(lo - Fr, Fr - hi); res['F_where'] = 'day %g HRU %d: F %.4f, closure %.4f-%.4f' % (t, k + 1, Fr, lo, hi)
                if method == 'NONE' and rch is not None and k not in chd_hru:
                    R = rch.get(tt, {}).get(k + 1); rj = row['rejected recharge [mm]']
                    if R is not None:
                        tl = rtol[tt][k + 1]   # (6 significant digits of the running total)
                        rej_over = max(rej_over, rj - max(R, 0.0) - tl)
                        if rj > 1e-9 and Fr <= 0.0: rej_nof = max(rej_nof, rj)
                        if one[k] and R > 0: rej_eq = max(rej_eq, abs(rj - Fr * R) - tl)
            tprev = float(t)
        res['F_err'] = max(ferr, 0.0)
        if fbad > 1e-12: F.append('saturated fraction outside [0, 1] by %.3g' % fbad)
        if wbad > 1e-6: F.append('soil water outside [0, capacity] by %.3g mm' % wbad)
        if negs > 1e-9: F.append('negative rejected recharge or overflow (%.3g mm)' % negs)
        if method in FTOL and res['F_err'] > FTOL[method]: F.append('saturated fraction differs from the closure by %.4f (limit %g; %s)' % (res['F_err'], FTOL[method], res.get('F_where')))
        if rej_over > 0: F.append('rejected recharge exceeds the HRU recharge by up to %.3g mm' % rej_over)
        if rej_nof > 0: F.append('rejected recharge %.3g mm on an HRU with no saturated fraction' % rej_nof)
        if rej_eq > 0: F.append('rejected recharge differs from F x recharge on one-cell HRUs by up to %.3g mm' % rej_eq)
        if method != 'NONE' and 'unsaturated zone storage [m3]' in b:
            st = b['unsaturated zone storage [m3]'].shift(1)
            v0 = getattr(sz_check, 'vz_start', lambda d: None)(d)
            st.iloc[0] = v0 if v0 is not None else np.nan
            lim = b['Raven recharge [m3/d]'] + st
            ex = (b['rejected recharge [m3]'] - lim - 1e-9 * lim.abs() - 1e-6)[st.notna()]
            if len(ex) and ex.max() > 0: F.append('rejected recharge exceeds the recharge plus the columns\' storage by %.3g m3' % ex.max())

# ---------------------------------------------------------------------------------------------------- regression cases
CASES = os.path.join(HERE, 'rough_cases')

def load_case(name):
    S = json.load(open(os.path.join(CASES, name + '.json'))); return S.get('spec', S)

# (name, stored case, method, what it holds)
REG = [
    ('R1_flat_rejection', None, 'NONE', 'rejection follows the converged head on flat cells (an interface that passed as converged with the saturated fraction of an earlier iterate rejected 15 % of the recharge where the closure gives at most 5 %)'),
    ('R2_rejection_g93', 'rejection_g93', 'NONE', 'rejected recharge only where saturated, F x recharge on one-cell HRUs (a wet start under heavy rain)'),
    ('R3_deep_samples_g44', 'deep_samples_g44', 'RICHARDS', 'DEM samples whose base lies below the top cell\'s bottom (relief larger than the top layer)'),
    ('R4_disv_e4', 'disv_e4', 'NONE', 'an existing DISV model with irregular cells, pass-through and inactive cells'),
    ('R5_dryisolated_e351', 'dryisolated_e351', 'RICHARDS', 'dried top cells over a wet lower cell (upward flows through SZW_RAVEN)'),
    ('R6_drained_e363', 'drained_e363', 'RICHARDS', 'drained columns kept 1 mm above their bottoms: must complete'),
    ('R7_lowkv_e25', 'lowkv_e25', 'RICHARDS', 'a slowly permeable top cell (Kv 3.6 mm/d) under rain: head-dependent rejection'),
    ('R8_lowkv_g21', 'lowkv_g21', 'NONE', 'the same on a generated model'),
    ('R9_lowsy_e367', 'lowsy_e367', 'RICHARDS', 'a small specific yield (0.02): the water table jumps through the base'),
    ('R10_lowsy_g334', 'lowsy_g334', 'NONE', 'the same on a generated model'),
    ('R11_drained_e106', 'drained_e106', 'LAG', 'a drained column under a dry spell: must complete'),
    ('R12_mf6dry_e9', 'mf6dry_e9', 'RICHARDS', 'top cells MODFLOW dries (the drained-column stop): must complete'),
    ('R13_mf6dry_e9_kw', 'mf6dry_e9', 'KINEMATIC', 'the same with KINEMATIC: must complete'),
    ('R14_vzrelease_e87', 'vzrelease_e87', 'RICHARDS', 'columns give stored water back where the water table reaches the base'),
    ('R15_lowkv_g57', 'lowkv_g57', 'RICHARDS', 'a slowly permeable steep slope (Kv 3.6 mm/d, 30 %): column lift bounded by NONE\'s'),
    ('R16_vzrelease_g5', 'vzrelease_g5', 'LAG', 'the release with LAG'),
    ('R17_nonewton_e14', 'nonewton_e14', 'NONE', 'an existing model without NEWTON: the justified stop'),
    ('R18_mf6dry_g36', 'mf6dry_g36', 'NONE', 'a solve that may diverge: completes, or stops only where MODFLOW 6 alone repeats it'),
    ('R19_lagdiv_g350', 'lagdiv_g350', 'LAG', 'the LAG divergence: must complete'),
    ('R20_band_e43', 'band_e43', 'LAG', 'no sub-grid base in the 1 mm below the lowest drain level (top cell bottom + 1 mm): the saturated fraction follows the closure within RFTOL for any method'),
]
MUST_COMPLETE = {'R6_drained_e363', 'R11_drained_e106', 'R12_mf6dry_e9', 'R13_mf6dry_e9_kw', 'R19_lagdiv_g350'}
RFTOL = {'R20_band_e43': 0.004}   # (regression cases whose saturated fraction is checked against the closure on converged steps, any method)
REG_OF = {c: (n, m) for n, c, m, _ in REG if c}

# how each stored case is made (regenerate with --make-cases): seed, family, overrides of the generated spec
CASE_SOURCES = {
    'band_e43': (43, 'ext', {'ext.th.0': 0.6, 'relief': 'D*2.5', 'subgrid': 9, 'ext.newton': True, 'ext.top_off': 0.0}),
    'deep_samples_g44': (44, 'gen', {'relief': 'D*4', 'subgrid': 9, 'profiles.0.0.1': 0.6, 'outcrop': False}),
    'disv_e4': (4, 'ext', {'ext.dis': 'DISV', 'ext.perturb': 0.15, 'ext.inactive': 0.08, 'ext.newton': True}),
    'drained_e106': (106, 'ext', {'init_depth': 12.0, 'rain': 'x0.2', 'ext.newton': True}),
    'drained_e363': (363, 'ext', {'init_depth': 10.0, 'rain': 'x0.3', 'ext.newton': True}),
    'dryisolated_e351': (351, 'ext', {'ext.nlay': 2, 'ext.th': [0.6, 6.0], 'ext.tilt': [0.0, 0.3], 'ext.lcls': 'top2', 'init_depth': 4.0, 'pet': 3.0, 'ext.newton': True}),
    'lagdiv_g350': (350, 'gen', {'outcrop': False}),
    'lowkv_e25': (25, 'ext', {'top_kv': 0.0036, 'ext.newton': True}),
    'lowkv_g21': (21, 'gen', {'top_kv': 0.0036, 'outcrop': False}),
    'lowkv_g57': (57, 'gen', {'top_kv': 0.0036, 'slope': 0.3, 'outcrop': False}),
    'lowsy_e367': (367, 'ext', {'top_sy': 0.02, 'ext.newton': True}),
    'lowsy_g334': (334, 'gen', {'top_sy': 0.02, 'outcrop': False}),
    'mf6dry_e9': (9, 'ext', {'ext.nlay': 2, 'ext.th': [0.6, 4.0], 'ext.tilt': [0.0, 0.0], 'ext.lcls': 'top2', 'init_depth': 0.5, 'pet': 4.0, 'rain': 'x0', 'ext.newton': True}),
    'mf6dry_g36': (36, 'gen', {'init_depth': 0.5, 'pet': 4.0, 'rain': 'x0.1', 'outcrop': False}),
    'nonewton_e14': (14, 'ext', {'ext.newton': False}),
    'rejection_g93': (93, 'gen', {'init_depth': 0.2, 'rain': 'x2', 'outcrop': False}),
    'vzrelease_e87': (87, 'ext', {'init_depth': 6.0, 'rain': 'x1.5', 'ext.newton': True}),
    'vzrelease_g5': (5, 'gen', {'init_depth': 6.0, 'rain': 'x1.5', 'outcrop': False}),
}

def make_case_spec(name):
    """the stored spec of a regression case: gen_spec(seed, family) with the overrides of CASE_SOURCES"""
    seed, fam, ov = CASE_SOURCES[name]
    S = rm.gen_spec(seed, fam); D = max(sum(x) for x in S['soils'])
    for k, v in ov.items():
        if k == 'relief':
            f = float(v.split('*')[1]) * D; r = f / max(S['relief'], 1e-9); S['relief'] = f
            for t in S['land']['terms']:
                if t[0] in ('wave', 'bump', 'bowl'): t[-1 if t[0] != 'wave' else 1] *= r
                elif t[0] in ('cliff', 'ridge'): t[3] *= r
            if not S['land']['terms']: S['land']['terms'] = [['wave', f * 0.5, 2 * math.pi / (3 * S['cell']), 0.0, 0.0]]
        elif k == 'rain':
            S['rain'] = [round(x * float(v[1:]), 2) for x in S['rain']]
        elif k == 'slope':
            S['slope'] = S['land']['slope'] = v
        elif k in ('top_kv', 'top_sy'):
            cname = S['ext']['lcls'][0] if fam == 'ext' else S['profiles'][0][0][0]
            for c in S['classes']:
                if c['name'] == cname:
                    if k == 'top_kv': c['Kv'] = v
                    else: c['Sy'] = v; c['por'] = max(c['por'], v + 0.05)
        elif k == 'ext.lcls' and v == 'top2':
            S['ext']['lcls'] = (S['ext']['lcls'] + [S['classes'][-1]['name']] * 3)[:S['ext']['nlay']]
        else:
            p = k.split('.'); o = S
            for q in p[:-1]: o = o[int(q)] if isinstance(o, list) else o[q]
            o[int(p[-1]) if isinstance(o, list) else p[-1]] = v
    if fam == 'ext':
        E = S['ext']; n = E['nlay']
        E['th'] = (E['th'] + [2.0] * 3)[:n]; E['tilt'] = (E['tilt'] + [0.0] * 3)[:n]; E['lcls'] = (E['lcls'] + [E['lcls'][-1]] * 3)[:n]
        E['confined'] = E['confined'] and n > 1
    S['case_name'] = name
    return S

def make_cases():
    os.makedirs(CASES, exist_ok=True)
    for name in sorted(CASE_SOURCES):
        S = make_case_spec(name); d = os.path.join(W, 'mk_' + name); shutil.rmtree(d, ignore_errors=True)
        meta = rm.build(d, S, REG_OF[name][1]); shutil.rmtree(d, ignore_errors=True)
        seed, fam, ov = CASE_SOURCES[name]
        json.dump(dict(spec=S, meta=meta, origin=dict(seed=seed, family=fam, overrides=ov,
                  how='rough_models.gen_spec(%d, %r) of the generator with the overrides above (test_rough_terrain.py --make-cases)' % (seed, fam))),
                  open(os.path.join(CASES, name + '.json'), 'w'), indent=0)
        print('wrote rough_cases/%s.json' % name)

def flat_rejection(keep=False):
    """R1: rejection follows the converged head on flat cells (the P3 configuration without unsaturated columns): an
    interface that passed as converged with the saturated fraction of an earlier iterate rejected 15 % of the recharge
    where the closure at the step's heads gives at most 5 %"""
    import sz_models, flopy
    rain = [0.0] * 5 + [30.0] * 40 + [0.0] * 135
    d = os.path.join(W, 'R1_flat'); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=1, hru_w=400.0, init_depth=3.0, chd=97.0, aq_thick=20.0, rain=rain, days=len(rain), perc=30.0, ksat=300.0,
                        Kh=1.0, Kv=0.3, Sy=0.1, pet=3.0, soil_b=5.0, soil_psia=200.0, aq_b=4.0, aq_psia=0.3, extra_rvg=':HeadSaveFrequency 1\n')
    t0 = time.time(); ok, txt = sz_check.run(d)
    res = dict(name='R1_flat_rejection', fails=[], notes=[], method='NONE', family='flat', time=time.time() - t0)
    if not ok: res['fails'].append('run failed'); return decide(res, keep, d)
    r = sz_check.checks(d); res['ident'] = {k: r[k] for k in LIM if k in r}
    for k, lim in LIM.items():
        if k in r and not (r[k] <= lim): res['fails'].append('identity %s %.3g' % (k, r[k]))
    o = os.path.join(d, 'out'); s = pd.read_csv(o + '/GWSoilExchange.csv'); b = pd.read_csv(o + '/GWBudget.csv')
    g = flopy.mf6.utils.MfGrdFile(o + '/mf6/gwf.dis.grb'); idm = np.array(g.modelgrid.idomain).reshape(-1)
    hf = flopy.utils.HeadFile(o + '/mf6/gwf.hds'); H = {round(t, 6): hf.get_data(totim=t).reshape(-1) for t in hf.get_times()}
    ic = dict(zip(b['time [d]'].round(6), b['interface converged'] != 0)); worst = 0.0
    rr = dict(zip(b['time [d]'].round(6), b['Raven recharge [m3/d]'] - b['recharge onto CHD cells [m3/d]']))   # (the share onto the specified-head toe is not rejected by F)
    rj = dict(zip(b['time [d]'].round(6), b['rejected recharge [m3]']))
    res['steps'] = len(b); res['outer'] = int(b['outer iterations'].sum()); res['iface_nc'] = int((b['interface converged'] == 0).sum()); res['mf6_nc'] = int((b['converged'] == 0).sum())
    prev = None
    for _, row in s.iterrows():
        t = round(row['time [d]'], 6)
        if ic.get(t) and rr.get(t, 0) > 1.0 and prev is not None:
            zb = row['soil-zone base [m]']; ds = 0.5   # (flat: one base per cell; make_case's smoothing depth)
            hs = [H[prev][i] for i in range(len(idm)) if idm[i] > 0]; he = [H[t][i] for i in range(len(idm)) if idm[i] > 0]
            fmax = max(closure(h, [zb], ds) for h in hs + he)
            worst = max(worst, rj[t] / rr[t] - fmax)
        prev = t
    res['F_err'] = max(worst, 0.0)
    if worst > 0.02: res['fails'].append('rejected share exceeds the closure at the step\'s heads by %.3f' % worst)
    return decide(res, keep, d)

def regression_checks(res, rname):
    """the regression case's own checks, added after run_case; the status is decided again (any extra failure -> FAIL)"""
    if rname in MUST_COMPLETE and (res.get('stop') is not None):
        res['fails'].append('%s must complete; it stopped: %s' % (rname, res['stop']))
    if rname in RFTOL:
        if 'F_err' not in res: res['fails'].append('%s: no saturated-fraction comparison' % rname)
        elif res['F_err'] > RFTOL[rname]: res['fails'].append('%s: saturated fraction differs from the closure by %.4f (limit %g)' % (rname, res['F_err'], RFTOL[rname]))
    return decide(res)

def run_regression(vz_classes=1, keep=False, only=None, methods=METHODS):
    """runs the regression cases (only: their names; every named case must run) with their own checks"""
    out = []
    for rname, case, meth, what in REG:
        if only is not None and rname not in only: continue
        if meth not in methods and only is None:
            _skip(rname, 'method %s not in --methods' % meth); continue
        if case is None:
            r = flat_rejection(keep)
        else:
            S = load_case(case); S['case_name'] = case
            ne = None
            if meth != 'NONE':
                r0 = run_case(rname + '_NONE', S, 'NONE', vz_classes, keep=False); ne = r0.get('exfil_max')
            r = run_case(rname, S, meth, vz_classes, keep, none_exf=ne)
        r['reg'] = rname
        r = regression_checks(r, rname)
        report(r); out.append(r)
    if only is not None and len(out) != len(only):
        raise SystemExit('run_regression: %d of the %d named cases ran (unknown names: %s)' % (len(out), len(only), sorted(set(only) - set(r['reg'] for r in out))))
    return out

# ---------------------------------------------------------------------------------------------------- reporting
def report(r, verbose=True):
    tag = r['status']
    line = '  %-5s %-28s %-9s' % (tag, r.get('reg') or r['name'], r['method'])
    if r.get('stopped'): line += ' stopped (justified: %s)' % r['stopped']
    else:
        line += ' steps %s outer %s nc %s/%s Ferr %s exf %s %.2fs' % (r.get('steps'), r.get('outer'), r.get('mf6_nc'), r.get('iface_nc'),
                                                                   ('%.4f' % r['F_err']) if 'F_err' in r else '-', ('%.1f' % r['exfil_max']) if 'exfil_max' in r else '-', r.get('time', 0))
    if verbose or tag != 'PASS': print(line, flush=True)
    for f in r['fails']: print('        %s' % f, flush=True)
    for n in r['notes']: print('        note: %s' % n, flush=True)
    if r.get('trace') and tag == 'FAIL': print(r['trace'])

def summary(results, methods):
    print('\nsummary')
    for m in methods:
        R = [r for r in results if r['method'] == m]
        if not R: continue
        done = [r for r in R if not r.get('stop')]; stops = [r for r in R if r.get('stopped')]
        print('  %-9s %d runs: %d completed, %d justified stops, %d known failures, %d failures; steps %d; unconverged steps interface %d, MODFLOW %d; outer iterations per step %.2f; mean run time %.2f s'
              % (m, len(R), len(done), len(stops), sum(r['status'] == 'XFAIL' for r in R), sum(r['status'] == 'FAIL' for r in R),
                 sum(r.get('steps', 0) for r in done), sum(r.get('iface_nc', 0) for r in done), sum(r.get('mf6_nc', 0) for r in done),
                 sum(r.get('outer', 0) for r in done) / max(sum(r.get('steps', 0) for r in done), 1), np.mean([r.get('time', 0) for r in R]) if R else 0))
        if stops: print('  %-9s justified stops: %s' % (m, ', '.join('%s (%s)' % (r.get('reg') or r['name'], r['stopped']) for r in stops)))
        hi = [r for r in done if r.get('exfil_max', -1e9) > 5.0]
        if hi:
            big = max(hi, key=lambda r: r['exfil_max'])
            print('  %-9s runs with the water table > 5 m above the land: %d, largest %.1f m (%s)' % (m, len(hi), big['exfil_max'], big['name']))
        fe = [r['F_err'] for r in done if 'F_err' in r]
        if fe: print('  %-9s saturated fraction vs closure on converged steps: largest %.4f (%s)' % (m, max(fe), 'checked' if m in FTOL else 'reported'))
    done = [r for r in results if not r.get('stop') and r.get('ident')]
    mx = {}
    for r in done:
        for k, v in r['ident'].items(): mx[k] = max(mx.get(k, 0.0), v)
    lay = max([r.get('layers_err', 0.0) for r in done] + [0.0]); bas = max([r.get('base_err', 0.0) for r in done] + [0.0])
    print('  largest over %d completed runs (regression cases included): %s; layers %.3g m, bases %.3g m'
          % (len(done), ', '.join('%s %.3g' % (k, mx[k]) for k in sorted(mx)), lay, bas))
    al = [r for r in results if r.get('alone')]
    print('  stops MODFLOW 6 alone repeats: %s' % (', '.join('%s %s' % (r['name'], r['method']) for r in al) or 'none'))
    ex = set(r['seed'] for r in results if r['family'] == 'ext' and not r.get('reg'))
    nn = set(r['seed'] for r in results if r['family'] == 'ext' and not r.get('reg') and r.get('newton') is False)
    print('  existing models: %d, %d without NEWTON' % (len(ex), len(nn)))

# ---------------------------------------------------------------------------------------------------- main
def parse_case(c, vz_classes):
    """--case SEED[:method] | xSEED[:method] | file.json[:method] -> (name, S, method or None, regression name or None)"""
    meth = None
    if ':' in c and c.rsplit(':', 1)[1].upper() in METHODS:
        c, meth = c.rsplit(':', 1); meth = meth.upper()
    if c.endswith('.json'):
        p = c if os.path.exists(c) else os.path.join(CASES, os.path.basename(c))
        S = json.load(open(p)); S = S.get('spec', S)        # ({spec, meta} of rough_cases/ or a run folder's case.json)
        base = os.path.splitext(os.path.basename(p))[0]
        reg = REG_OF.get(base) if os.path.dirname(os.path.abspath(p)) == os.path.abspath(CASES) else None
        if reg: S['case_name'] = base
        return (reg[0] if reg else base), S, meth or (reg[1] if reg else None), (reg[0] if reg else None)
    if c.startswith('x'):
        sd = int(c[1:]); return 'e%d' % sd, rm.gen_spec(sd, 'ext'), meth, None
    sd = int(c); fam = rm.family_of(sd); return '%s%d' % (fam[0], sd), rm.gen_spec(sd, fam), meth, None

def selftest():
    """the XFAIL rule on constructed results: a known-pattern failure alone is XFAIL; with a regression
    case's own failure added after run_case, FAIL; a shortfall is never XFAIL"""
    base = dict(name='c', method='LAG', notes=[], family='ext', deep_links=True)
    a = decide(dict(base, fails=['unconverged steps: interface on 9 of 60']))
    b = dict(base, fails=['unconverged steps: interface on 9 of 60'], F_err=0.51); decide(b); b = regression_checks(b, 'R20_band_e43')
    c = decide(dict(base, fails=['shortfall 3 m3 on a step whose interface converged']))
    d = decide(dict(base, fails=['unconverged steps: interface on 9 of 60'], deep_links=False))
    ok = (a['status'], b['status'], c['status'], d['status']) == ('XFAIL', 'FAIL', 'FAIL', 'FAIL')
    print('selftest: known pattern alone %s; with R20\'s own failure %s; shortfall %s; pattern without its condition %s -> %s'
          % (a['status'], b['status'], c['status'], d['status'], 'ok' if ok else 'FAIL'))
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quick', action='store_true'); ap.add_argument('--full', action='store_true')
    ap.add_argument('--methods', default='NONE,RICHARDS'); ap.add_argument('--vzclasses', type=int, default=1)
    ap.add_argument('--seeds', default=None); ap.add_argument('--family', default='both'); ap.add_argument('--keep', action='store_true')
    ap.add_argument('--case', default=None); ap.add_argument('--noreg', action='store_true'); ap.add_argument('--make-cases', action='store_true'); ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.make_cases: make_cases(); return 0
    if a.selftest: return 0 if selftest() else 1
    sz_check.tc.need_mf6()
    methods = [m.strip().upper() for m in a.methods.split(',') if m.strip()]
    for m in methods:
        if m not in METHODS: raise SystemExit('unknown method %s' % m)
    K = a.vzclasses
    if a.case:
        name, S, meth, reg = parse_case(a.case, K)
        ms = [meth] if meth else methods
        res = []; ne = None
        if any(m != 'NONE' for m in ms) and 'NONE' not in ms: ms = ['NONE'] + ms     # (the NONE run's water table, none_exf)
        for m in ms:
            r = run_case('case_%s_%s' % (name, m), S, m, K, keep=True, none_exf=ne if m != 'NONE' else None)
            if m == 'NONE': ne = r.get('exfil_max')
            if reg: r['reg'] = reg; r = regression_checks(r, reg)
            report(r); res.append(r)
        nf = sum(r['status'] == 'FAIL' for r in res)
        print('rough terrain: %d runs, %d failed' % (len(res), nf))
        return 1 if nf else 0
    quick = a.quick or os.environ.get('RAVEN_TEST_QUICK') == '1'
    n = 40 if quick else (1500 if a.full else 400)
    if a.seeds:
        lo, hi = (int(x) for x in a.seeds.split('-')) if '-' in a.seeds else (int(a.seeds), int(a.seeds)); seeds = range(lo, hi + 1)
    else:
        seeds = range(1, n + 1)
    t0 = time.time(); results = []
    print('rough-terrain suite: methods %s, %d depth class(es), seeds %s, family %s; %s' % (','.join(methods), K, ('%d-%d' % (seeds[0], seeds[-1])) if len(seeds) else 'none', a.family, sz_check.tc.RAVEN))
    if not a.noreg:
        print('regression cases'); results += run_regression(K, a.keep, methods=methods)
    print('seeds')
    for sd in seeds:
        fam = rm.family_of(sd)
        if a.family != 'both' and fam != a.family: continue
        S = rm.gen_spec(sd, fam); name = '%s%d' % (fam[0], sd); ne = None
        for m in methods:
            r = run_case('%s_%s' % (name, m), S, m, K, a.keep, none_exf=ne if m != 'NONE' else None)
            r['newton'] = S['ext']['newton'] if fam == 'ext' else True
            if m == 'NONE': ne = r.get('exfil_max')
            report(r, verbose=False); results.append(r)
    summary(results, methods)
    nf = sum(r['status'] == 'FAIL' for r in results); nk = sum(r['status'] == 'XFAIL' for r in results)
    print('  run time %.0f s' % (time.time() - t0))
    print('rough terrain: %d runs, %d failed%s' % (len(results), nf, (', %d known' % nk) if nk else ''))
    return 1 if nf else 0

if __name__ == '__main__':
    sys.exit(main())
