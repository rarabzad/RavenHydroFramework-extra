"""Water-table ET, surface-water exchange and reservoir exchange with an existing MODFLOW 6 model (EVT_RAVEN, SWX_RAVEN,
RES_RAVEN added to the model by Raven), on the synthetic Liard model of make_ext_model.py.

Cases (metres/days model md, feet/seconds model fs, linked through :MF6CRS):
  et        EXTINCTION_DEPTH 2 m on both aquifer profiles (the model's EVT taken over): water-table ET > 0 and, every day,
            at most the PET left unmet by Raven on the coupled HRUs (custom outputs PET and AET by HRU); identities; the
            saved flows of EVT_RAVEN, RCH_RAVEN and DRN_RAVEN in MODFLOW's budget file and list file equal GWBudget.csv
  et_ft     the same on the feet/seconds model: the exchange columns (recharge, water-table ET, surface-store and
            reservoir exchange) equal to the et case within 1e-6 of each column's largest value, every column within 1e-4
            (the two MODFLOW solves stop at the same tolerance, not at the same digits: single steps differ more)
  keep_evt  EXTINCTION_DEPTH 2 m while the model keeps its EVT package (:KeepPackages): must stop
  all       et + :SurfaceWaterExchange SOIL[0] AquiferHRUs + a 50 km2 reservoir with seepage (:ReservoirExchange) on the
            largest coupled HRU of subbasin 52: SWX and RES flows non-zero, identities (surface stores, reservoir
            sent/awaiting/delivered), budget file and list file of SWX_RAVEN and RES_RAVEN
  all_ft    the same on the feet/seconds model, equal to all
  restart   all, restarted half-way from solution.rvc (heads, :GWReservoirSeepage in transit): equal to the continuous run
  plain     (with RAVEN_EXE_REF) the coupled case without these options: outputs and the mf6 folder identical to the
            reference build
Dry and specified-head cells under the exchanges (the md model edited with flopy; 6 days, 15 in the full mode):
  et_dry    the model without NEWTON, layer 1 made 4 m thick, heads 5 m deep (in layer 2), EXTINCTION_DEPTH 6 m: MODFLOW
            moves the ET of each dry top cell to the cell below; GWBudget.csv's water-table ET is MODFLOW's (budget file,
            every step), positive and finite, the MODFLOW balance error stays at round-off, no output holds HDRY or NaN
  res_chd   the reservoir case with a CHD the model keeps on every cell under the lake from stress period 2: no seepage is
            sent to the specified heads; what MODFLOW did not take is returned to the reservoir's subbasin and booked
            ("reservoir seepage not delivered by MODFLOW", warning, run total): sent = delivered - gain not supplied + not
            delivered, the river books include it, Raven's balance holds
  res_chd2  the same with 2 of those cells specified heads: from the step after they become specified heads only the
            lake's bed over the other cells exchanges water and all of it is delivered (delivered = sent); on that step the
            share of the seepage computed for the 2 cells is returned (not delivered), and only on that step
  res_dry   the reservoir case on the model without NEWTON with heads 25 m deep (the lake's top cells dry): the reservoir
            books hold (sent = delivered - gain not supplied + not delivered), no output holds HDRY or NaN
Quick mode (RAVEN_TEST_QUICK=1): 31 days and no et_ft; full mode 120 days.
Usage: python3 ext_exchanges.py      (prints 'existing-model exchanges: ALL PASSED' when every check holds)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import testconfig as tc
import shutil, subprocess, re, json, datetime, filecmp
import numpy as np, pandas as pd
import flopy
from pyproj import Geod
from shapely.geometry import shape

tc.need_mf6(); X = tc.ext_models(); ENV = tc.ENV
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 31 if QUICK else 120
W = tc.work('ext_exchanges', 'x'); W = os.path.dirname(W)
ok_all = True


def check(name, ok, info=''):
    global ok_all
    ok_all &= bool(ok)
    print('  %-62s %s %s' % (name, 'ok' if ok else 'FAIL', info), flush=True)


def lake_hru(d):
    rvh = open(d + '/Liard.rvh').read()
    hdr = [l for l in rvh.split('\n') if ':Attributes' in l and 'AQUIFER_PROFILE' in l][0].replace(',', ' ').split()[1:]
    ib, ia, ie, iar = (hdr.index(k) + 1 for k in ('BASIN_ID', 'AQUIFER_PROFILE', 'ELEVATION', 'AREA'))
    rows = [l.replace(',', ' ').split() for l in rvh.split(':HRUs')[1].split(':EndHRUs')[0].split('\n')]
    r = max([r for r in rows if r and r[0].isdigit() and r[ib] == '52' and r[ia] != '[NONE]'], key=lambda r: float(r[iar]))
    return int(r[0]), float(r[ie])


def prep(d, units='md', days=DAYS, et=False, swx=False, res=False, keep_evt=False, start='1985-10-01', rvc=None, exe=None, model=None, ed=2.0):
    subprocess.run([sys.executable, tc.SETUP_EXT, d, model or (X + '/' + units)], capture_output=True, check=True)
    t = open(d + '/Liard.rvi').read()
    t = re.sub(r':StartDate\s+\S+\s+\S+', ':StartDate %s 00:00:00' % start, t); t = re.sub(r':Duration\s+\S+', ':Duration %d' % days, t)
    if et:
        t += '\n:CustomOutput DAILY AVERAGE PET BY_HRU\n:CustomOutput DAILY AVERAGE AET BY_HRU\n'
    open(d + '/Liard.rvi', 'w').write(t)
    g = open(d + '/Liard.rvg').read(); g = re.sub(r':MF6GridFile.*', ':MF6CRS            EPSG:32610', g)
    if keep_evt:
        g = g.replace(':RavenTakesOver    RCH_MODEL EVT_MODEL', ':RavenTakesOver    RCH_MODEL\n:KeepPackages      EVT_MODEL')
    if swx:
        g += ':SurfaceWaterExchange SOIL[0] AquiferHRUs LEAKANCE 0.001\n'   # (the example's wetland HRUs are not coupled)
    if res:
        g += ':ReservoirExchange\n'
    open(d + '/Liard.rvg', 'w').write(g)
    if et or keep_evt:
        p = open(d + '/Liard.rvp').read()
        p = p.replace('INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SOIL_ZONE_DEPTH',
                      'INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SOIL_ZONE_DEPTH, EXTINCTION_DEPTH')
        i = p.find('INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH'); j = p.find(':EndAquiferProfileParameters', i); L = p[i:j].split('\n')
        L = [l + (', m' if l.strip().startswith(':Units') else ', %g' % ed if l.strip().split(',')[0] in ('VALLEY_ALLUVIUM', 'UPLAND_TILL') else '') for l in L]
        p = p[:i] + '\n'.join(L) + p[j:]
        assert p.count(', %g' % ed) >= 2, 'rvp edit failed'
        open(d + '/Liard.rvp', 'w').write(p)
    if res:
        lid, elev = lake_hru(d)
        open(d + '/Liard.rvh', 'a').write(
            '\n:Reservoir TestLake\n  :SubBasinID 52\n  :HRUID %d\n  :Type RESROUTE_STANDARD\n  :WeirCoefficient 0.6\n'
            '  :CrestWidth 20.0\n  :MaxDepth 8.0\n  :LakeArea 5.0E7\n  :AbsoluteCrestHeight %.2f\n  :SeepageParameters 0.05 %.2f\n'
            ':EndReservoir\n' % (lid, elev, elev - 5))
        if rvc is None:
            open(d + '/Liard.rvc', 'a').write('\n:InitialReservoirStage 52 %.2f\n:InitialReservoirFlow 52 0.0\n' % elev)
    if rvc:
        shutil.copy(rvc, d + '/Liard.rvc')
    r = subprocess.run([exe or tc.RAVEN, 'Liard', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=ENV, timeout=3600)
    return (re.findall(r'Exiting Gracefully: (.*)', r.stdout + r.stderr) or ['(no exit message; rc %d)' % r.returncode])[-1]


def budget(d):
    return pd.read_csv(d + '/out/GWBudget.csv').rename(columns=lambda c: c.strip()).dropna(subset=['Raven recharge [m3/d]']).reset_index(drop=True)


def units(d):
    fs = 'feet' in open(d + '/out/mf6/gwf_liard.dis').read().lower()
    return (3.280839895 if fs else 1.0), (86400.0 if fs else 1.0)


OURS = {'RCH_RAVEN': lambda b: b['MF6 recharge [m3/d]'], 'DRN_RAVEN': lambda b: -b['seepage to Raven [m3/d]'],
        'EVT_RAVEN': lambda b: -b['water-table ET [m3/d]'],
        'SWX_RAVEN': lambda b: b['surface-store leakage to aquifer [m3/d]'] - b['aquifer discharge to surface stores [m3/d]'],
        'RES_RAVEN': lambda b: b['reservoir seepage delivered [m3/d]']}


def cbc_check(d, pkgs):
    """MODFLOW's saved flows (budget file, every saved time) against GWBudget.csv: {package: (worst relative, records)}"""
    fl, ft = units(d)
    cb = flopy.utils.CellBudgetFile(d + '/out/mf6/gwf_liard.cbc', precision='double'); b = budget(d); R = {}
    for idx, h in enumerate(cb.recordarray):
        pk = h['paknam2'].decode().strip().upper()
        if pk not in pkgs:
            continue
        q = cb.get_record(idx)['q'].sum() * ft / fl ** 3
        row = b[(b['time [d]'] - h['totim'] / ft).abs() < 1e-6]
        if row.empty:
            continue
        ours = OURS[pk](row).iloc[0]; w, n = R.get(pk, (0.0, 0))
        R[pk] = (max(w, abs(q - ours) / max(abs(ours), 1.0)), n + 1)
    return R


def list_check(d, pkgs):
    """the list file's last volume budget, package by package, against the last line of GWBudget.csv"""
    fl, ft = units(d); txt = open(d + '/out/mf6/gwf_liard.lst').read(); k = txt.rfind('VOLUME BUDGET FOR ENTIRE MODEL')
    if k < 0:
        return {}
    blk = txt[k:txt.find('TOTAL OUT', k) + 200]; rates = {}; side = None
    for l in blk.split('\n'):
        s = l.strip()
        if s.startswith('IN:'): side = 0
        elif s.startswith('OUT:'): side = 1
        m = re.match(r'\s*\S+\s*=\s*[-\d.Ee+]+\s+\S+\s*=\s*([-\d.Ee+]+)\s+(\S+)\s*$', l)
        if m and side is not None and 'TOTAL' not in l:
            r = rates.setdefault(m.group(2).upper(), [0.0, 0.0]); r[side] += float(m.group(1))
    tt = re.findall(r'VOLUME BUDGET FOR ENTIRE MODEL AT END OF TIME STEP\s+(\d+), STRESS PERIOD\s+(\d+)', txt[k - 10:k + 200])
    b = budget(d).iloc[-1]; R = {}
    for pk in pkgs:
        if pk in rates:
            mf = (rates[pk][0] - rates[pk][1]) * ft / fl ** 3; ours = OURS[pk](b); R[pk] = abs(mf - ours) / max(abs(ours), 1.0)
    return R


def identities(d, swx=False, res=False, river=True):
    A = tc.audit.audit(d + '/out')
    check('recharge identity', abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']) < 1e-9, '%.1e' % A['recharge: (Raven - MF6 - dStore - toCHD)/Raven'])
    check('MODFLOW cumulative residual / gross flow', abs(A['MF6 cumulative residual / gross flow']) < 1e-7, '%.1e' % A['MF6 cumulative residual / gross flow'])
    if river: check('river: applied - net MF6 - carry change', abs(A['river: applied - net MF6 - carry change (rel)']) < 1e-9, '%.1e' % A['river: applied - net MF6 - carry change (rel)'])
    check('seepage returned = MODFLOW seepage', abs(A['seepage returned vs MF6 seepage (rel)']) < 1e-9, '%.1e' % A['seepage returned vs MF6 seepage (rel)'])
    check('no unconverged steps', A['unconverged steps'] == 0, str(A['unconverged steps']))
    if swx:
        v = A['surface-store: applied - (discharge-leakage) (rel)']; check('surface stores: applied = net exchange', abs(v) < 1e-9, '%.1e' % v)
    if res:
        v = A['reservoir: sent(t) - awaiting(t-1) (rel)']; check('reservoir: sent(t) = awaiting(t-1)', abs(v) < 1e-8, '%.1e' % v)
        v = A['reservoir: (delivered + not supplied) / sent'] - 1 if 'reservoir: (delivered + not supplied) / sent' in A else A['reservoir: delivered / sent'] - 1
        check('reservoir: (delivered + not supplied) = sent', abs(v) < 1e-9, '%.1e' % v)
    return A


def mf6_checks(d, pkgs):
    R = cbc_check(d, pkgs)
    for pk in pkgs:
        w, n = R.get(pk, (float('nan'), 0))
        check('budget file %s = GWBudget.csv (%d saved times)' % (pk, n), n > 0 and w < 1e-6, '%.1e' % w)
    L = list_check(d, pkgs)
    if L:
        for pk in pkgs:
            check('list file %s = GWBudget.csv (last step)' % pk, pk in L and L[pk] < 1e-5, '%.1e' % L.get(pk, float('nan')))   # (the list file prints 7 digits)
    else:
        tc.skip('list-file budgets of %s' % os.path.basename(d), 'the model prints no volume budget')


def unmet_pet(d):
    """per day: sum over coupled HRUs of polygon area x max(PET - AET, 0) [m3/d] (an upper bound of water-table ET)"""
    geod = Geod(ellps='WGS84'); A = {}
    for f in json.load(open(d + '/Liard_HRUs_standin.geojson'))['features']:
        A[int(f['properties']['HRU_ID'])] = abs(geod.geometry_area_perimeter(shape(f['geometry']))[0])
    rvh = open(d + '/Liard.rvh').read()
    hdr = [l for l in rvh.split('\n') if ':Attributes' in l and 'AQUIFER_PROFILE' in l][0].replace(',', ' ').split()[1:]
    ia = hdr.index('AQUIFER_PROFILE') + 1
    cpl = [int(r[0]) for r in (l.replace(',', ' ').split() for l in rvh.split(':HRUs')[1].split(':EndHRUs')[0].split('\n')) if r and r[0].isdigit() and r[ia] != '[NONE]']
    def rd(var):
        f = [x for x in os.listdir(d + '/out') if x.endswith('.csv') and var in x and 'ByHRU' in x and 'Daily' in x][0]
        t = pd.read_csv(d + '/out/' + f, header=0, skiprows=[1])   # (row 1: HRU IDs, row 2: 'time,day,mean,...')
        return t
    P, E = rd('PET'), rd('AET')
    cols = {}
    for c in P.columns:
        m = re.match(r'\s*(\d+)', str(c))
        if m and int(m.group(1)) in A and int(m.group(1)) in cpl: cols[c] = int(m.group(1))
    tot = np.zeros(len(P))
    for c, k in cols.items():
        tot += A[k] * np.maximum(pd.to_numeric(P[c], errors='coerce').values - pd.to_numeric(E[c], errors='coerce').values, 0.0) / 1000.0
    return tot, len(cols)


XCOLS = ['MF6 recharge [m3/d]', 'water-table ET [m3/d]', 'surface-store leakage to aquifer [m3/d]', 'aquifer discharge to surface stores [m3/d]',
         'surface-store exchange applied to Raven [m3]', 'reservoir seepage sent [m3/d]', 'reservoir seepage delivered [m3/d]']


def compare(a, b, label, tol, only=None):
    A, B = budget(a), budget(b)
    cols = [c for c in A.columns if '[m3' in c and c in B.columns and (only is None or c in only)]
    devs = {c: ((A[c] - B[c]).abs() / (A[c].abs().max() + 1e3)).max() for c in cols}; c = max(devs, key=devs.get); dev = devs[c]
    check(label, len(A) == len(B) and dev < tol, 'max deviation %.1e (limit %.0e, %d columns; largest: %s)' % (dev, tol, len(cols), c))
    return dev


# ---- et: water-table ET with the model's EVT taken over
print('et: EXTINCTION_DEPTH 2 m, metres/days model, %d days' % DAYS, flush=True)
d = W + '/et'; msg = prep(d, et=True); check('run', 'Successful' in msg, msg[:120])
if 'Successful' in msg:
    b = budget(d); evt = b['water-table ET [m3/d]'].values
    check('water-table ET > 0 (total m3)', evt.sum() > 0, '%.4g' % (evt.sum()))
    up, nh = unmet_pet(d)
    n = min(len(up), len(evt)); ratio = np.max(evt[:n] / np.maximum(up[:n], 1e-9))
    check('water-table ET <= unmet PET of the coupled HRUs, every day', nh > 0 and np.all(evt[:n] <= up[:n] * (1 + 1e-3) + 1e-6), 'largest ratio %.3f over %d HRUs' % (ratio, nh))
    s = open(d + '/out/GWModelSummary.txt').read(); check('summary names EVT_RAVEN', 'EVT_RAVEN' in s)
    nam = open(d + '/out/mf6/gwf_liard.nam').read(); check('name file: EVT_MODEL out, EVT_RAVEN in', '# ' in nam and 'raven.evt  EVT_RAVEN' in nam)
    identities(d); mf6_checks(d, ['RCH_RAVEN', 'DRN_RAVEN', 'EVT_RAVEN'])
if not QUICK:
    print('et_ft: the same on the feet/seconds model', flush=True)
    f = W + '/et_ft'; msg = prep(f, units='fs', et=True); check('run', 'Successful' in msg, msg[:120])
    if 'Successful' in msg:
        identities(f); mf6_checks(f, ['RCH_RAVEN', 'DRN_RAVEN', 'EVT_RAVEN']); compare(d, f, 'exchange columns equal to the metres/days run', 1e-6, XCOLS); compare(d, f, 'every GWBudget.csv column equal to the metres/days run', 1e-4)
        shutil.rmtree(f, ignore_errors=True)

# ---- keep_evt: double counting refused
print('keep_evt: EXTINCTION_DEPTH 2 m with the model EVT kept', flush=True)
g = W + '/keep_evt'; msg = prep(g, days=2, keep_evt=True)
check('stops: water-table ET counted twice', 'counted twice' in msg and 'EVT_MODEL' in msg, msg[:150])
shutil.rmtree(g, ignore_errors=True)

# ---- all: ET + surface-water exchange + reservoir
print('all: ET + :SurfaceWaterExchange + :ReservoirExchange, metres/days model, %d days' % DAYS, flush=True)
a = W + '/all'; msg = prep(a, et=True, swx=True, res=True); check('run', 'Successful' in msg, msg[:120])
if 'Successful' in msg:
    b = budget(a)
    sw = (b['surface-store leakage to aquifer [m3/d]'] + b['aquifer discharge to surface stores [m3/d]']).abs().sum()
    check('surface-store exchange non-zero (gross m3)', sw > 0, '%.4g' % sw)
    rs = b['reservoir seepage delivered [m3/d]'].abs().sum(); check('reservoir seepage delivered non-zero (m3)', rs > 0, '%.4g' % rs)
    s = open(a + '/out/GWModelSummary.txt').read(); check('summary names SWX_RAVEN and RES_RAVEN', 'SWX_RAVEN' in s and 'RES_RAVEN' in s)
    identities(a, swx=True, res=True); mf6_checks(a, ['EVT_RAVEN', 'SWX_RAVEN', 'RES_RAVEN'])
    print('all_ft: the same on the feet/seconds model', flush=True)
    f = W + '/all_ft'; msg = prep(f, units='fs', et=True, swx=True, res=True); check('run', 'Successful' in msg, msg[:120])
    if 'Successful' in msg:
        identities(f, swx=True, res=True); mf6_checks(f, ['EVT_RAVEN', 'SWX_RAVEN', 'RES_RAVEN']); compare(a, f, 'exchange columns equal to the metres/days run', 1e-6, XCOLS); compare(a, f, 'every GWBudget.csv column equal to the metres/days run', 1e-4)
    shutil.rmtree(f, ignore_errors=True)
    # ---- restart half-way
    k = DAYS // 2; print('restart: all, split at day %d' % k, flush=True)
    r1 = W + '/rs_a'; r2 = W + '/rs_b'
    m1 = prep(r1, days=k, et=True, swx=True, res=True)
    start = (datetime.date(1985, 10, 1) + datetime.timedelta(days=k)).isoformat()
    sol = open(r1 + '/out/solution.rvc').read() if 'Successful' in m1 else ''
    check('first part writes the reservoir seepage in transit', ':GWReservoirSeepage' in sol)
    m2 = prep(r2, days=DAYS - k, et=True, swx=True, res=True, start=start, rvc=r1 + '/out/solution.rvc') if sol else 'not run'
    check('both parts run', 'Successful' in m1 and 'Successful' in m2, (m1 + ' / ' + m2)[:120])
    if 'Successful' in m2:
        C = budget(a); B = budget(r2); m = C.merge(B, on='date', suffixes=('_c', '_r'))
        cols = ['seepage to Raven [m3/d]', 'storage release [m3/d]', 'MF6 recharge [m3/d]', 'water-table ET [m3/d]', 'surface-store leakage to aquifer [m3/d]',
                'aquifer discharge to surface stores [m3/d]', 'reservoir seepage delivered [m3/d]', 'other model packages [m3/d]']
        dev = max(((m[c + '_c'] - m[c + '_r']).abs() / (m[c + '_c'].abs().max() + 1e3)).max() for c in cols)
        check('restarted run = continuous run (%d days)' % len(m), len(m) == DAYS - k and dev < 1e-4, 'max deviation %.1e' % dev)
        identities(r2, swx=True, res=True, river=False)   # (the audit starts the river carry at 0, not at the hotstart's)
    shutil.rmtree(r1, ignore_errors=True); shutil.rmtree(r2, ignore_errors=True)

# ---- dry and specified-head cells
DDAYS = 6 if QUICK else 15


def model_copy(name, newton=True, thin=None, depth=None, chd=None):
    """a copy of the md model: without NEWTON, layer 1 `thin` m thick, initial heads `depth` m below the top, a CHD package
    (CHD_LAKE) on the cells `chd` [(lay, row, col)] from stress period 2, 10 m below the top"""
    M = W + '/model_' + name; shutil.rmtree(M, ignore_errors=True); shutil.copytree(X + '/md', M)
    if not newton:
        p = M + '/gwf_liard.nam'; nam = open(p).read(); open(p, 'w').write(re.sub(r'\n\s*NEWTON[^\n]*', '', nam))
    sim = flopy.mf6.MFSimulation.load(sim_ws=M, verbosity_level=0); g = sim.get_model('gwf_liard'); top = g.dis.top.array
    if thin:
        b = g.dis.botm.array; b[0] = top - thin; g.dis.botm.set_data(b); g.dis.write()
    if depth:
        g.ic.strt.set_data(np.repeat((top - depth)[None], g.dis.nlay.get_data(), axis=0)); g.ic.write()
    if chd:
        flopy.mf6.ModflowGwfchd(g, pname='CHD_LAKE', stress_period_data={1: [[c, float(top[c[1], c[2]] - 10.0)] for c in chd]}, save_flows=True)
        sim.write_simulation(silent=True)
    return M


def no_hdry(d):
    """every number in the groundwater CSV outputs and WatershedStorage.csv is finite and below 1e20 in magnitude (no HDRY,
    no NaN)"""
    bad = []
    for f in sorted(os.listdir(d + '/out')):
        if not (f.endswith('.csv') and (f.startswith('GW') or f == 'WatershedStorage.csv')):
            continue
        t = pd.read_csv(d + '/out/' + f, low_memory=False)
        v = t.apply(pd.to_numeric, errors='coerce').values.astype(float)
        x = v[~np.isnan(v)]
        nn = int(np.isnan(t.select_dtypes(include=[np.number]).values.astype(float)).sum())
        if nn or (x.size and np.abs(x).max() >= 1e20):
            bad.append('%s (%d NaN, largest %.3g)' % (f, nn, np.abs(x).max() if x.size else 0.0))
    check('no HDRY or NaN in the CSV outputs', not bad, ', '.join(bad)[:150])


def lake_cells(d):
    """(lay, row, col) of the RES_RAVEN entries of a run (0-based)"""
    txt = open(d + '/out/mf6/raven.res').read().split('BEGIN PERIOD')[1].split('END PERIOD')[0]
    return [tuple(int(x) - 1 for x in l.split()[:3]) for l in txt.strip().split('\n')[1:] if l.strip()]


print('et_dry: model without NEWTON, layer 1 4 m thick, heads 5 m deep, EXTINCTION_DEPTH 6 m, %d days' % DDAYS, flush=True)
M = model_copy('n0_thin', newton=False, thin=4.0, depth=5.0)
d = W + '/et_dry'; msg = prep(d, days=DDAYS, et=True, model=M, ed=6.0); check('run', 'Successful' in msg, msg[:120])
if 'Successful' in msg:
    b = budget(d); evt = b['water-table ET [m3/d]'].values
    check('water-table ET finite and > 0 on every step', np.all(np.isfinite(evt)) and np.all(evt > 0), 'from %.4g to %.4g m3/d' % (evt.min(), evt.max()))
    err = b['MF6 balance error [m3/d]'].abs().max()
    check('MODFLOW balance error at round-off', err < 1e-6 * max(np.abs(evt).max(), 1.0), '%.2g m3/d' % err)
    R = cbc_check(d, ['EVT_RAVEN']); w, n = R.get('EVT_RAVEN', (float('nan'), 0))
    check('budget file EVT_RAVEN = GWBudget.csv water-table ET (%d saved steps)' % n, n > 0 and w < 1e-6, '%.1e' % w)
    no_hdry(d)
    shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(M, ignore_errors=True)

print('res_chd: reservoir over cells that become specified heads, %d days' % DDAYS, flush=True)
r0 = W + '/res_cells'; msg = prep(r0, days=2, res=True); cells = lake_cells(r0) if 'Successful' in msg else []
check('lake cells found', len(cells) >= 3, str(cells)); shutil.rmtree(r0, ignore_errors=True)
for tag, cc in (('res_chd', cells), ('res_chd2', cells[:2])):
    if not cells:
        break
    M = model_copy(tag, chd=cc)
    d = W + '/' + tag; msg = prep(d, days=DDAYS, res=True, model=M); check('%s: run' % tag, 'Successful' in msg, msg[:120])
    if 'Successful' in msg:
        b = budget(d); sent = b['reservoir seepage sent [m3/d]'].sum(); dl = b['reservoir seepage delivered [m3/d]'].sum()
        ud = b['reservoir seepage not delivered by MODFLOW [m3]'].sum() if 'reservoir seepage not delivered by MODFLOW [m3]' in b else 0.0
        A = identities(d, res=True)
        if tag == 'res_chd':
            e = open(d + '/out/Raven_errors.txt').read(); s = open(d + '/out/GWModelSummary.txt').read()
            m = re.search(r'reservoir seepage not delivered: (\S+) m3', s)
            check('res_chd: seepage not delivered booked, warned, run total = its column', ud > 0 and 'not delivered by MODFLOW' in e and m is not None
                  and abs(float(m.group(1)) - ud) <= 1e-5 * ud, 'not delivered %.4g m3 of %.4g sent' % (ud, sent))
        else:
            sv = b['reservoir seepage sent [m3/d]'].values; dv = b['reservoir seepage delivered [m3/d]'].values
            uv = b['reservoir seepage not delivered by MODFLOW [m3]'].values if 'reservoir seepage not delivered by MODFLOW [m3]' in b else np.zeros(len(b))
            k = np.nonzero(uv > 0.0)[0]; rest = np.ones(len(b), bool); rest[k] = False
            g = sent > 0 and len(k) == 1 and bool((np.abs(dv - sv)[rest] <= 1e-6 * np.abs(sv).max()).all()) and 0.0 < uv[k[0]] < sv[k[0]]
            check('res_chd2: the other cells take the seepage of their share of the bed (delivered = sent), the 2 cells\' share returned once', g,
                  'delivered %.6g of %.6g m3/d; returned %.3g m3 on %d step(s)' % (dl, sent, ud, len(k)))
        no_hdry(d)
        shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(M, ignore_errors=True)

print('res_dry: reservoir on the model without NEWTON whose top cells are dry, %d days' % DDAYS, flush=True)
M = model_copy('n0_deep', newton=False, depth=25.0)
d = W + '/res_dry'; msg = prep(d, days=DDAYS, res=True, model=M); check('res_dry: run', 'Successful' in msg, msg[:120])
if 'Successful' in msg:
    identities(d, res=True); no_hdry(d)
    shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(M, ignore_errors=True)

# ---- plain: without the options, identical to the reference build
if tc.REF:
    print('plain: no water-table ET, surface-water or reservoir exchange, against the reference build', flush=True)
    p1, p2 = W + '/plain_new', W + '/plain_ref'
    m1 = prep(p1, days=10); m2 = prep(p2, days=10, exe=tc.REF)
    diffs = []
    for sub in ('out', 'out/mf6'):
        for fn in sorted(os.listdir(p2 + '/' + sub)):
            fa, fb = p1 + '/' + sub + '/' + fn, p2 + '/' + sub + '/' + fn
            if os.path.isdir(fb) or fn.endswith('.lst') or fn.endswith('.cache') or fn in ('Raven_errors.txt', 'GWModelSummary.txt', 'mfsim.stdout'):
                continue
            if not os.path.exists(fa) or not filecmp.cmp(fa, fb, shallow=False): diffs.append(sub + '/' + fn)
        extra = set(os.listdir(p1 + '/' + sub)) - set(os.listdir(p2 + '/' + sub))
        diffs += [sub + '/' + x + ' (extra)' for x in extra]
    flt = lambda f: [l.replace(p1, 'X').replace(p2, 'X') for l in open(f, errors='replace') if not re.search(r'Build date|BuildDate|HRU/grid linkage|time|library|Version', l, re.I)]
    for fn in ('Raven_errors.txt', 'GWModelSummary.txt'):
        if flt(p1 + '/out/' + fn) != flt(p2 + '/out/' + fn): diffs.append(fn)
    check('outputs and mf6 folder identical to the reference build', 'Successful' in m1 and 'Successful' in m2 and not diffs, ', '.join(diffs)[:150])
    shutil.rmtree(p1, ignore_errors=True); shutil.rmtree(p2, ignore_errors=True)
else:
    tc.skip('plain run against the reference build')
for x in ('et', 'all'):
    shutil.rmtree(W + '/' + x, ignore_errors=True)
print('existing-model exchanges: %s' % ('ALL PASSED' if ok_all else 'FAILED'))
