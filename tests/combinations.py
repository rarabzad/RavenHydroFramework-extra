"""Option combinations: small synthetic coupled models run across a matrix of options, every water identity checked.

Each case is a strip of HRUs (sz_models.make_case: 4 HRUs of 200 x 200 m on a 0.01 slope, 100 m cells, wet days then dry
days) with some of these options:
  exchanges  et   water-table ET (EXTINCTION_DEPTH 3 m, PET 5 mm/d)
             riv  a river along the strip (:RiverGeometry, a channel routed by Raven)
             swx  :SurfaceWaterExchange on DEPRESSION (ABST_FILL, DEP_MAX 50 mm)
             res  a reservoir with seepage (:ReservoirExchange) on HRU 1, or with chd on the outlet HRU (half over the
                  specified-head cells)
             wel  a pumping well (:Wells, :WellFlowRate)
             ghb  a general-head boundary on the upslope cells
             chd  a specified head on the downslope cells
             resg the reservoir with its crest and stage above the ground of its HRU (with chd: of its cells that are not
                  specified heads), so it loses water to the aquifer
             etw  water-table ET from a water table within the extinction depth (dry soil, no rain: the PET is unmet)
  stresses   dry  a 1 m top layer above the water table at the start (dry top cells; without NEWTON inactive)
             neg  negative recharge (PERC_GR4JEXCH from SOIL[1] to GROUNDWATER, GR4J_X2 20 mm/d)
             rise a specified head 0.3 m below the ground at the outlet and wet columns (:SoilZoneVadoseInitialFlux): the
                  water table rises through the unsaturated columns, which vanish
             bhs  :BoundaryHead series on the specified head (LAYERS TOP) and the GHB: 0.5 m below the ground on days 1-3,
                  3 m below it on days 4-6, then 0.5 m again, so cells are switched off and on
             reschd  (existing twins) a CHD package of the model's own on the 4 cells under the lake in stress periods 3-5
                  (one period per day): the lake's seepage on those days goes to its sliver of another HRU's cell only
  soil zone  CONCEPTUAL, or :SoilZone PHYSICAL with :SoilZoneVadose NONE / RICHARDS / KINEMATIC / LAG and 1 or 3 depth
             classes
  model      gen (Raven builds the model), ext (the generated model coupled as an existing model, NEWTON), ext_n0 (the
             same without NEWTON; CONCEPTUAL only), ext_ft (the existing model converted to feet and seconds)
For an existing model, Raven's own packages of the generated model are taken out (Raven adds them again), its river,
well and head boundaries stay as the model's own packages, and the feet/seconds copy keeps only the specified heads.

Checks on every run (sz_check.checks and the Liard audit tool):
  MODFLOW balance (converged steps) and cumulative residual; Raven's balance; the recharge identity; the soil-zone
  identity; the unsaturated-column identity; no soil-zone shortfall; the river books (applied = net MODFLOW river flow
  - carry change + reservoir corrections); the surface-store books (applied = net exchange); the reservoir books (sent(t)
  = awaiting(t-1); sent = delivered - gain not supplied + not delivered); seepage returned = MODFLOW seepage; the run
  totals of GWModelSummary.txt (recharge not applied, reservoir seepage not delivered) equal their GWBudget.csv columns;
  no HDRY (|x| >= 1e20) and no NaN in GWBudget.csv, GWHRUState.csv, GWSoilExchange.csv and WatershedStorage.csv; with
  :SoilZone PHYSICAL no groundwater discharge into the surface stores on a step on which every HRU's water table is below
  its ground; "Successful Simulation". Unconverged MODFLOW steps are reported, not failed (their residual is booked).
  The moving-water group requires the flow it is meant to move: resg seepage delivered to the aquifer (> 1 m3/d), reschd
  seepage returned on the day the specified heads start and none piled into the sliver on their other days (at most
  1e-3 of the seepage before), bhs cell-steps switched off (GWModelSummary.txt) and a non-zero CHD flow on every step,
  etw water-table ET (> 0).
  A result whose cause lies outside the coupling is reported as KNOWN (listed with its reason), not failed: Raven's
  balance error equal to a reservoir's own routing balance error (ReservoirMassBalance.csv).

Quick mode (RAVEN_TEST_QUICK=1): 260 runs of 8 days (about a minute). Full mode: dry top cells with negative recharge
and the feet/seconds twin of every case added, negative recharge in the moving-water group, 15 days each, and half-day
steps (398 runs, a few minutes).
Usage: python3 combinations.py [--list] [--only NAME,...]   (prints 'option combinations: N runs, 0 failed')"""
import os, sys, shutil, re, subprocess, json, itertools, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'soilzone'))
import testconfig as tc
import numpy as np, pandas as pd
import sz_models, sz_check

QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 8 if QUICK else 15
W = os.path.dirname(tc.work('combinations', 'x'))
NHRU, HW, CELL, SLOPE, Z0 = 4, 200.0, 100.0, 0.01, 100.0
L = NHRU * HW
XS, YS = -0.5 * L, -0.5 * HW
FEET = os.path.join(HERE, 'soilzone', 'mf6_to_feet.py')


def land(x):
    return Z0 - SLOPE * (x - XS)


def polygon(fn, x0, x1):
    ring = [sz_models.ll(x0, YS - HW), sz_models.ll(x1, YS - HW), sz_models.ll(x1, YS + 2 * HW), sz_models.ll(x0, YS + 2 * HW), sz_models.ll(x0, YS - HW)]
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]}, open(fn, 'w'))


def sub(p, a, b, count=1):
    t = open(p).read(); assert a in t, (p, a); open(p, 'w').write(t.replace(a, b, count))


def cfg_of(s):
    """sz_models.make_case arguments of case spec s"""
    wet = [20.0] * 3 + [0.0] * (DAYS - 3)
    c = dict(timestep=s.get('dt', 1.0), nhru=NHRU, hru_w=HW, width=HW, cell=CELL, slope=SLOPE, z0=Z0, rain=wet, days=DAYS, init_depth=1.5, Kh=10.0, Kv=1.0,
             aq_thick=10.0, Sy=0.1, perc=10.0, physical=(s['sz'] != 'CONC'))
    if 'et' in s['x'] or 'etw' in s['x']:
        c['pet'] = 5.0
    if 'etw' in s['x']:
        c['rain'] = [0.0] * DAYS; c['phi0'] = (0.0, 0.0)
    if 'chd' in s['x']:
        c['chd'] = land(L - 0.5 * CELL) - (0.3 if 'rise' in s['st'] else 2.0)   # (at the outlet's cells: 2 m below the ground; 'rise' 0.3 m)
    if 'dry' in s['st']:
        c['top'] = 1.0; c['init_depth'] = 1.0 + 1.0 + 1.5   # (soil zone 1 m, top layer 1 m, water table 1.5 m below the top layer)
    if 'neg' in s['st']:
        c['extra_proc'] = '  :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER\n'; c['extra_soil'] = {'GR4J_X2': 20.0, 'GR4J_X3': 150.0}
    if s['vz'] != 'NONE':
        c['aq_b'] = 4.0; c['aq_psia'] = 0.3
        c['extra_rvg'] = ':SoilZoneVadose %s\n' % s['vz'] + (':SoilZoneVadoseClasses %d\n' % s['K'] if s['K'] > 1 else '')
        if s['K'] > 1:
            c['dem_fn'] = lambda x, y: 0.3 * np.sin(2 * np.pi * x / 100.0) * np.sin(2 * np.pi * y / 100.0); c['dem_res'] = 400
        if 'rise' in s['st']:
            c['extra_rvg'] += ':SoilZoneVadoseInitialFlux 30\n'; c['Kh'] = 1000.0; c['Sy'] = 0.02; c['init_depth'] = 1.4; c['phi0'] = (100.0, 190.0)
            c['slope'] = 0.0; c['chd'] = Z0 - 0.3   # (flat: the specified head raises the water table under every HRU)
    return c


def options(d, s, ext=False):
    """the option edits of spec s on case folder d (made by make_case); ext: the existing-model twin (no rivers, wells or
    head boundaries of Raven's: they are the model's own packages)"""
    rvi, rvh, rvp, rvt, rvg, rvc = (os.path.join(d, 'm.' + e) for e in ('rvi', 'rvh', 'rvp', 'rvt', 'rvg', 'rvc'))
    xp = []   # aquifer profile parameters added
    if 'et' in s['x'] or 'etw' in s['x']:
        xp.append(('EXTINCTION_DEPTH', 'm', 3.0)); sub(rvi, ':Evaporation PET_CONSTANT', ':Evaporation PET_DATA')
    if 'riv' in s['x'] and not ext:
        xp += [('RIVERBED_K', 'm/d', 5.0), ('RIVERBED_THICKNESS', 'm', 1.0)]
    if xp:
        sub(rvp, ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH',
            ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH' + ''.join(', ' + a for a, _, _ in xp))
        sub(rvp, '  :Units, m, m, 1/d, m\n  AQ, ', '  :Units, m, m, 1/d, m' + ''.join(', ' + u for _, u, _ in xp) + '\n  AQ, ')
        t = open(rvp).read(); i = t.find('\n  AQ, ', t.find('SEEPAGE_SMOOTHING_DEPTH')); j = t.find('\n', i + 1)
        open(rvp, 'w').write(t[:j] + ''.join(', %g' % v for _, _, v in xp) + t[j:])
    if 'riv' in s['x'] or 'res' in s['x'] or 'resg' in s['x']:   # a routed channel
        sub(rvh, '  1, box, -1, NONE, ZERO-, 1', '  1, box, -1, CHAN, 0.8, 1')
        sub(rvi, ':Routing ROUTE_NONE', ':Routing ROUTE_DIFFUSIVE_WAVE')
        open(rvh, 'a').write('\n:SubBasinProperties\n  :Parameters, Q_REFERENCE\n  :Units, m3/s\n  1, 0.05\n:EndSubBasinProperties\n')
        open(rvp, 'a').write(':ChannelProfile CHAN\n  :Bedslope 0.01\n  :SurveyPoints\n    0 2.0\n    2 0\n    8 0\n    10 2.0\n  :EndSurveyPoints\n'
                             '  :RoughnessZones\n    0 0.035\n  :EndRoughnessZones\n:EndChannelProfile\n')
    if 'riv' in s['x'] and not ext:
        line = [sz_models.ll(XS + 20.0, 0.0), sz_models.ll(XS + L - 20.0, 0.0)]
        json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"SUBID": 1}, "geometry": {"type": "LineString", "coordinates": line}}]},
                  open(os.path.join(d, 'river.geojson'), 'w'))
        open(rvg, 'a').write(':RiverGeometry river.geojson SUBID\n')
    pc = '0.3' if 'riv' in s['x'] else '0.0'   # (runoff: a river with flow)
    if 'swx' in s['x']:
        sub(rvi, '  :Infiltration', '  :Abstraction ABST_FILL PONDED_WATER DEPRESSION\n  :Infiltration')
        sub(rvp, ':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0',
            ':Parameters, PARTITION_COEFF, DEP_MAX, ABST_PERCENT\n  :Units, none, mm, none\n  [DEFAULT], %s, 50, 0.5' % pc)
        open(rvh, 'a').write('\n:HRUGroup All\n  ' + ','.join(str(k + 1) for k in range(NHRU)) + '\n:EndHRUGroup\n')
        open(rvg, 'a').write(':SurfaceWaterExchange DEPRESSION All LEAKANCE 0.05\n')
    else:
        sub(rvp, ':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0', ':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], %s' % pc)
    if 'res' in s['x'] or 'resg' in s['x']:
        kl = NHRU if 'chd' in s['x'] else 1   # (with the specified head: the lake on the outlet HRU, half over specified-head cells)
        z1 = land((kl - 0.5) * HW) if 'resg' not in s['x'] else land(XS + (kl - 0.5) * HW if kl == 1 else XS + L - 1.5 * CELL)   # (resg: at the ground of its
                                                                                                                       #  cells, not the specified heads')
        open(rvh, 'a').write('\n:Reservoir Lake\n  :SubBasinID 1\n  :HRUID %d\n  :Type RESROUTE_STANDARD\n  :WeirCoefficient 0.6\n  :CrestWidth 5.0\n'
                             '  :MaxDepth 3.0\n  :LakeArea %g\n  :AbsoluteCrestHeight %.3f\n  :SeepageParameters 0.02 %.3f\n:EndReservoir\n' % (kl, HW * HW, z1 + 0.5, z1 - 2.0))
        open(rvc, 'a').write('\n:InitialReservoirStage 1 %.3f\n:InitialReservoirFlow 1 0.0\n' % (z1 + 0.3))
        open(rvg, 'a').write(':ReservoirExchange\n')
        open(rvi, 'a').write(':WriteReservoirMBFile\n')   # (the reservoir's own balance: KNOWN below)
    if 'wel' in s['x'] and not ext:
        lon, lat = sz_models.ll(XS + 1.5 * HW, 0.0)
        top = land(1.5 * HW) - 1.0
        open(rvg, 'a').write(':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n  1, PW_1, %.7f, %.7f, %.2f, %.2f\n:EndWells\n'
                             % (lat, lon, top - 2.0, top - 9.0))
        open(rvt, 'a').write('\n:WellFlowRate 1 m3/d\n  2000-01-01 00:00:00 1.0 %d\n' % DAYS + '  -150\n' * DAYS + ':EndWellFlowRate\n')
    if 'ghb' in s['x'] and not ext:
        polygon(os.path.join(d, 'ghb.geojson'), XS - HW, XS + 0.75 * CELL)
        open(rvg, 'a').write(':GeneralHeadBoundary GHB1 ghb.geojson HEAD %.2f CONDUCTANCE 200 LAYERS TOP\n' % (land(0.0) - 2.5))
    if 'bhs' in s['st'] and not ext:   # boundary heads that cross the bottom of the top layer: cells switched off and on
        t = open(rvg).read(); t = re.sub(r'(:SpecifiedHeadBoundary EDGE edge.geojson HEAD \S+)', r'\1 LAYERS TOP', t); open(rvg, 'w').write(t)
        for nm, xg in (('EDGE', XS + L - 0.5 * CELL), ('GHB1', XS + 0.5 * CELL)):
            if nm == 'GHB1' and 'ghb' not in s['x']: continue
            g = land(xg); v = [g - 0.5] * 3 + [g - 3.0] * 3 + [g - 0.5] * (DAYS - 6)
            open(rvt, 'a').write('\n:BoundaryHead %s m\n  2000-01-01 00:00:00 1.0 %d\n' % (nm, DAYS) + ''.join('  %.3f\n' % x for x in v) + ':EndBoundaryHead\n')


def generated(d, s):
    shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **cfg_of(s)); options(d, s)
    return d


def existing(g, e, s, newton=True, feet=False):
    """the existing-model twin e of generated run g (run first)"""
    m = e + '_model'; shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in os.listdir(m):
        if f.endswith(('.lst', '.hds', '.cbc', '.cache', '.rch', '.drn', '.szx', '.szq', '.szd', '.szw', '.evt', '.swx', '.res')) or f == 'mfsim.stdout':
            os.remove(os.path.join(m, f))
    drop = 'RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN|EVT_RAVEN|SWX_RAVEN|RES_RAVEN' + ('|RIV_RAVEN|WEL_RAVEN|GHB_RAVEN' if feet else '')
    nam = open(os.path.join(m, 'gwf.nam')).read()
    nam = '\n'.join(l for l in nam.split('\n') if not re.search(drop, l))
    if not newton:
        nam = re.sub(r'(?m)^\s*NEWTON.*$', '', nam)
    open(os.path.join(m, 'gwf.nam'), 'w').write(nam)
    if feet:
        r = subprocess.run([sys.executable, FEET, m, m + '_ft'], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError('mf6_to_feet: ' + r.stderr[-400:])
        shutil.rmtree(m, ignore_errors=True); m = m + '_ft'
    shutil.rmtree(e, ignore_errors=True); sz_models.make_case(e, **cfg_of(s)); options(e, s, ext=True)
    shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
    rvg = os.path.join(e, 'm.rvg'); t = open(rvg).read()
    keep = [l for l in t.split('\n') if not l.startswith((':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary', ':GeneralHeadBoundary')
                                                         + (() if s['sz'] != 'CONC' else (':LandSurface',)))]
    open(rvg, 'w').write('\n'.join(keep) + '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m)
    if 'reschd' in s['st']:   # the model's own specified heads on the lake's 4 cells (HRU 1) in stress periods 3-5, one period per day
        td = [os.path.join(m, f) for f in os.listdir(m) if f.endswith('.tdis')][0]
        open(td, 'w').write('BEGIN OPTIONS\n  TIME_UNITS %s\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NPER %d\nEND DIMENSIONS\n\nBEGIN PERIODDATA\n' % ('SECONDS' if feet else 'DAYS', DAYS)
                            + ('  86400.0 1 1.0\n' if feet else '  1.0 1 1.0\n') * DAYS + 'END PERIODDATA\n')
        f = 3.280839895 if feet else 1.0
        open(os.path.join(m, 'lake.chd'), 'w').write('BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN DIMENSIONS\n  MAXBOUND 4\nEND DIMENSIONS\nBEGIN PERIOD 3\n'
                                                      + ''.join('  %s %r\n' % (c, (land(XS + 0.5 * HW) - 2.0) * f) for c in ('1 2 2', '1 3 2', '1 2 3', '1 3 3')) + 'END PERIOD\nBEGIN PERIOD 6\nEND PERIOD\n')
        p = os.path.join(m, 'gwf.nam'); t = open(p).read(); open(p, 'w').write(t.replace('END PACKAGES', '  CHD6 lake.chd CHD_LAKE\nEND PACKAGES'))
    return e


ID = dict(sz_check.ID_LIMITS); ID.pop('mf6_err_rel')   # (MODFLOW's balance: on converged steps, below)


def check_run(d, txt, need=()):
    """every identity of run folder d: (list of failures, info); need: flows the case must move (moving-water group)"""
    bad = []
    if 'Successful Simulation' not in txt:
        m = re.findall(r'Exiting Gracefully: (.*)', txt) or re.findall(r'ERROR[^\n]*', txt)
        return ['run: ' + ((m[-1] if m else txt[-300:]).strip()[:200])], ''
    o = os.path.join(d, 'out')
    tt = pd.read_csv(os.path.join(o, 'GWBudget.csv'))['time [d]']
    r = sz_check.checks(d, dt=float(tt.iloc[0]) if len(tt) else 1.0)   # (the step: half-day cases)
    for k, lim in ID.items():
        if k in r and not (r[k] <= lim):
            bad.append('%s %.3g' % (k, r[k]))
    rm = os.path.join(o, 'ReservoirMassBalance.csv')
    if any(x.startswith('raven_mb_mm') for x in bad) and os.path.exists(rm):   # Raven's balance error = the reservoir's own MB error?
        w = pd.read_csv(os.path.join(o, 'WatershedStorage.csv')); w.columns = [c.strip() for c in w.columns]
        res_mm = (w['MB Error [mm]'] - (w['Deep Groundwater [mm]'] - w['Deep Groundwater [mm]'].iloc[0])).values
        rmb = pd.read_csv(rm); col = [c for c in rmb.columns if 'MB error' in c]
        cum = np.cumsum(rmb[col].fillna(0.0).sum(axis=1).values) / (NHRU * HW * HW) * 1000.0   # [mm] (the lake's balance error, sign: lost)
        n = min(len(cum), len(res_mm))
        if n and np.abs(res_mm[:n] + cum[:n]).max() < 1e-4 + 1e-6 * np.abs(cum).max():
            bad = [('raven_mb_mm (= the reservoir routing balance error, %.3g m3)' % float(-cum[n - 1] * NHRU * HW * HW / 1000.0)) if x.startswith('raven_mb_mm') else x for x in bad]
    b = pd.read_csv(os.path.join(o, 'GWBudget.csv'))
    ok = b['converged'] == 1
    rr = max(b['Raven recharge [m3/d]'].abs().max(), 1.0)
    e = float((b['MF6 balance error [m3/d]'][ok].abs() / max(b['storage release [m3/d]'].abs().max(), rr)).max()) if ok.any() else 0.0
    if e > 1e-5: bad.append('MF6 balance (converged steps) %.3g' % e)
    sxf = os.path.join(o, 'GWSoilExchange.csv')
    if os.path.exists(sxf) and 'aquifer discharge to surface stores [m3/d]' in b:   # physics: a store on the ground above the soil zone
        sx = pd.read_csv(sxf)                                                       # gets no groundwater while every water table is below the ground
        above = (sx['water table [m]'] - sx['soil-zone base [m]'] - 1.0).groupby(sx['date']).max().reindex(b['date']).values   # (soil zone H0 + H1 = 1 m)
        q = b['aquifer discharge to surface stores [m3/d]'].values[above < 0.0]
        if q.size and q.max() > 0.0: bad.append('discharge into surface stores below the ground %.3g m3/d' % q.max())
    A = tc.audit.audit(o)
    k = 'MF6 cumulative residual / gross flow'
    if k in A and abs(A[k]) > 1e-6 and ok.all(): bad.append('%s %.3g' % (k, A[k]))
    if not A.get('HRU heads finite', True): bad.append('HRU heads not finite')
    # per-step books, each relative to the sum of its terms' magnitudes (at least 1 m3: GWBudget.csv carries 10 digits)
    dt = b['time [d]'].diff().fillna(b['time [d]'].iloc[0]).values
    g = lambda c: b[c].fillna(0.0).values if c in b else np.zeros(len(b))
    def ident(label, terms, mask=None):
        r = sum(terms); sc = np.maximum(sum(np.abs(t) for t in terms), 1.0); v = np.abs(r) / sc
        if mask is not None: v = v[mask]
        if v.size and v.max() > 1e-8: bad.append('%s %.3g' % (label, v.max()))
    nriv = (g('aquifer discharge to rivers [m3/d]') - g('river leakage to aquifer [m3/d]')) * dt
    c = g('river loss carried to next step [m3]'); cp = np.concatenate([[0.0], c[:-1]])
    ident('river books', [g('river exchange applied to Raven [m3]'), -nriv, -c, cp, g('reservoir gain not supplied by MODFLOW [m3]'),
                          g('river gains withheld [m3]'), -g('reservoir seepage not delivered by MODFLOW [m3]')], mask=ok.values)
    ident('surface-store books', [g('surface-store exchange applied to Raven [m3]'),
                                  -(g('aquifer discharge to surface stores [m3/d]') - g('surface-store leakage to aquifer [m3/d]')) * dt, g('surface-store gains withheld [m3]')])
    sv = g('reservoir seepage sent [m3/d]') * dt
    ident('reservoir sent(t) = awaiting(t-1)', [sv[1:], -g('reservoir seepage awaiting delivery [m3]')[:-1]])
    ident('reservoir sent = delivered - gain not supplied + not delivered', [sv, -g('reservoir seepage delivered [m3/d]') * dt,
                                                                              g('reservoir gain not supplied by MODFLOW [m3]'), -g('reservoir seepage not delivered by MODFLOW [m3]')])
    ident('seepage returned = MODFLOW seepage', [g('returned to Raven [m3]'), -g('seepage to Raven [m3/d]') * dt], mask=ok.values)
    s = open(os.path.join(o, 'GWModelSummary.txt')).read()
    for col, pat, f in (('recharge not applied by MODFLOW [m3/d]', r'recharge not applied\s*:\s*(\S+) m3', 1.0),
                        ('reservoir seepage not delivered by MODFLOW [m3]', r'reservoir seepage not delivered:\s*(\S+) m3', 0.0)):
        if col in b:
            m = re.search(pat, s); dt = b['time [d]'].diff().fillna(b['time [d]'].iloc[0]).values
            tot = float((b[col].values * (dt if f else 1.0)).sum())
            if m is None or abs(float(m.group(1)) - tot) > 1e-5 * max(abs(tot), 1.0):
                bad.append('run total of %s: %s against %.6g' % (col, m.group(1) if m else 'missing', tot))
    for f in sorted(os.listdir(o)):
        if f.endswith('.csv') and (f.startswith('GW') or f == 'WatershedStorage.csv'):
            t = pd.read_csv(os.path.join(o, f), low_memory=False)
            v = t.select_dtypes(include=[np.number]).values.astype(float)
            if v.size and (np.isnan(v).any() or np.abs(v).max() >= 1e20):
                bad.append('%s: %d NaN, largest %.3g' % (f, int(np.isnan(v).sum()), np.nanmax(np.abs(v))))
            obj = [c for c in t.columns if t[c].dtype == object and c not in ('date', 'HRU_ID')]
            if any(t[c].astype(str).str.contains('nan|inf', case=False).any() for c in obj):
                bad.append('%s: nan/inf text' % f)
    g2 = lambda c: b[c].fillna(0.0).values if c in b else np.zeros(len(b))
    if 'resg' in need and not (g2('reservoir seepage delivered [m3/d]').max() > 1.0):
        bad.append('required: reservoir seepage delivered to the aquifer, at most %.3g m3/d' % g2('reservoir seepage delivered [m3/d]').max())
    if 'reschd' in need:
        dl, nd = g2('reservoir seepage delivered [m3/d]'), g2('reservoir seepage not delivered by MODFLOW [m3]')
        if not (len(dl) >= 5 and nd[2] > 1.0 and np.abs(dl[3:5]).max() <= 1e-3 * max(abs(dl[1]), 1.0)):
            bad.append('required: seepage returned on day 3 (%.3g m3) and none piled into the sliver on days 4-5 (%.3g m3/d)' % (nd[2] if len(nd) > 2 else 0, np.abs(dl[3:5]).max() if len(dl) >= 5 else 0))
    if 'bhs' in need:
        m = re.search(r'head boundaries off\s*:\s*(\d+)', s)
        if not (m and int(m.group(1)) > 0 and (np.abs(g2('CHD [m3/d]')) > 0.0).all()):
            bad.append('required: boundary cells switched off (%s) and a CHD flow on every step' % (m.group(1) if m else 'no count'))
    if 'etw' in need and not (np.abs(g2('water-table ET [m3/d]')).sum() > 0.0):
        bad.append('required: water-table ET')
    info = 'MF6 unconverged %d' % int((~ok).sum())
    for c, lab in (('water-table ET [m3/d]', 'ET'), ('aquifer discharge to rivers [m3/d]', 'riv out'), ('river leakage to aquifer [m3/d]', 'riv in'),
                   ('surface-store leakage to aquifer [m3/d]', 'swx in'), ('aquifer discharge to surface stores [m3/d]', 'swx out'),
                   ('reservoir seepage delivered [m3/d]', 'res'), ('wells actual [m3/d]', 'wel'), ('GHB [m3/d]', 'ghb'), ('CHD [m3/d]', 'chd'),
                   ('recharge not applied by MODFLOW [m3/d]', 'rch lost'), ('reservoir seepage not delivered by MODFLOW [m3]', 'res undeliv')):
        if c in b and b[c].abs().sum() > 0: info += ', %s %.3g' % (lab, b[c].abs().sum())
    if 'unsaturated zone inflow [m3]' in b:
        info += ', vz in %.3g (negative on %d steps)' % (b['unsaturated zone inflow [m3]'].sum(), int((b['unsaturated zone inflow [m3]'] < 0).sum()))
    return bad, info


def run(d):
    try:
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=1800)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 'timeout'


def name(s):
    return '%s_%s%s_%s_%s%s' % (s['sz'], s['vz'], s['K'] if s['vz'] != 'NONE' else '', '-'.join(sorted(s['x'])) or 'nox', '-'.join(sorted(s['st'])) or 'plain',
                               '' if s.get('dt', 1.0) == 1.0 else '_dt%g' % s['dt'])


def matrix():
    """the cases: (spec, models)"""
    ALL = ('et', 'riv', 'swx', 'res', 'wel', 'ghb', 'chd')
    C = []
    # exchange group: every exchange together and each alone, under plain, dry-top-cell and negative-recharge conditions
    # (and both: full mode), CONCEPTUAL and PHYSICAL; the specified heads lie under every exchange's cells at the outlet
    xs = [ALL] + [(x,) for x in ALL] + [('et', 'swx', 'res', 'chd')]
    sts = [set(), {'dry'}, {'neg'}] + ([] if QUICK else [{'dry', 'neg'}])
    for x, st, sz in itertools.product(xs, sts, ('CONC', 'PHYS')):
        s = dict(sz=sz, vz='NONE', K=1, x=set(x), st=set(st), dt=1.0)
        models = ['gen', 'ext'] + (['ext_n0'] if sz == 'CONC' else []) + (['ext_ft'] if (len(x) > 1 or not QUICK) else [])
        C.append((s, models))
    # column group: PHYSICAL with unsaturated columns, 1 or 3 depth classes, negative recharge, rising water tables (the
    # columns vanish), dry top cells
    vzs = [(m, k) for m in ('RICHARDS', 'KINEMATIC', 'LAG') for k in (1, 3)]
    sts = [set(), {'neg'}, {'rise'}, {'rise', 'neg'}, {'dry'}, {'dry', 'neg'}]
    for (m, k), st in itertools.product(vzs, sts):
        x = {'swx', 'et'} | ({'chd'} if ('rise' in st or 'dry' in st) else set())
        models = ['gen', 'ext'] + (['ext_ft'] if (not QUICK or k == 3) else [])
        C.append((dict(sz='PHYS', vz=m, K=k, x=x, st=set(st), dt=1.0), models))
    # moving-water group: cases that must move water through the exchange they test (check_run's need)
    mw = [('CONC', {'resg'}, set(), ['gen', 'ext', 'ext_n0', 'ext_ft']), ('PHYS', {'resg'}, set(), ['gen', 'ext', 'ext_ft']),
          ('CONC', {'resg'}, {'reschd'}, ['gen', 'ext', 'ext_n0', 'ext_ft']), ('PHYS', {'resg'}, {'reschd'}, ['gen', 'ext']),
          ('CONC', {'chd'}, {'bhs', 'dry'}, ['gen']), ('PHYS', {'chd'}, {'bhs', 'dry'}, ['gen']), ('CONC', {'chd', 'ghb'}, {'bhs', 'dry'}, ['gen']),
          ('CONC', {'etw'}, set(), ['gen', 'ext', 'ext_n0']), ('PHYS', {'etw'}, set(), ['gen', 'ext', 'ext_ft']),
          ('PHYS', {'etw', 'resg', 'chd', 'swx'}, {'bhs', 'dry'}, ['gen'])]
    if not QUICK:
        mw += [('CONC', {'resg'}, {'neg'}, ['gen', 'ext', 'ext_ft']), ('PHYS', {'etw'}, {'neg'}, ['gen', 'ext']), ('PHYS', {'chd', 'ghb'}, {'bhs', 'dry', 'neg'}, ['gen'])]
    for sz, x, st, models in mw:
        C.append((dict(sz=sz, vz='NONE', K=1, x=set(x), st=set(st), dt=1.0), models))
    if not QUICK:   # half-day steps
        for sz, m, k in (('CONC', 'NONE', 1), ('PHYS', 'NONE', 1), ('PHYS', 'RICHARDS', 3), ('PHYS', 'LAG', 1)):
            C.append((dict(sz=sz, vz=m, K=k, x=set(ALL) if m == 'NONE' else {'swx', 'et', 'chd'}, st={'neg', 'rise'} if m != 'NONE' else {'neg'}, dt=0.5),
                      ['gen', 'ext'] + (['ext_n0'] if sz == 'CONC' else [])))
    return C


# results known to fail for a reason outside the coupling's books, reported apart (case-name pattern, check prefix, reason)
KNOWN = [(r'res', 'raven_mb_mm (= the reservoir routing balance error',
          "Raven's balance error equals the lake's own routing balance error (ReservoirMassBalance.csv 'MB error', a few m3 on the steps "
          "its stage falls back below the weir crest while groundwater feeds it): Raven's reservoir routine stops its stage iteration at a "
          "0.1 mm change next to the kink of the weir curve, and base Raven gives the same without groundwater; the coupling's books hold")]


def main():
    only = None
    if '--only' in sys.argv:
        only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    C = matrix()
    if '--list' in sys.argv:
        for s, models in C: print('%-66s %s' % (name(s), ' '.join(models)))
        print('%d cases, %d runs' % (len(C), sum(len(m) for _, m in C))); return True
    nrun = 0; t0 = time.time(); fails = []; known = []

    def report(nm, mod, bad, info):
        kn = [b for b in bad if any(re.search(p, nm) and b.startswith(c) for p, c, _ in KNOWN)]
        real = [b for b in bad if b not in kn]
        print('%-66s %-7s %s  %s' % (nm, mod, ('ok' if not real else 'FAIL: ' + '; '.join(real)) + ('' if not kn else ' (KNOWN: ' + '; '.join(kn) + ')'), info), flush=True)
        if real: fails.append(nm + ' ' + mod)
        if kn: known.append(nm + ' ' + mod)
        return not real

    for s, models in C:
        nm = name(s)
        if only and nm not in only: continue
        g = generated(os.path.join(W, nm, 'gen'), s)
        txt = run(g); nrun += 1
        need = [k for k in ('resg', 'etw') if k in s['x']] + [k for k in ('bhs',) if k in s['st']]
        okg = report(nm, 'gen', *check_run(g, txt, need))
        if 'Successful Simulation' not in txt:
            continue
        for mod in models[1:]:
            e = os.path.join(W, nm, mod)
            try:
                existing(g, e, s, newton=(mod != 'ext_n0'), feet=(mod == 'ext_ft'))
                txt = run(e); res = check_run(e, txt, [k for k in need if k != 'bhs'] + (['reschd'] if 'reschd' in s['st'] else []))
            except Exception as ex:
                res = (['set-up: %s' % str(ex)[:200]], '')
            nrun += 1
            if report(nm, mod, *res):
                shutil.rmtree(e, ignore_errors=True); shutil.rmtree(e + '_model', ignore_errors=True)
            shutil.rmtree(e + '_model_ft', ignore_errors=True)
        if not any(f.startswith(nm + ' ') for f in fails): shutil.rmtree(os.path.join(W, nm), ignore_errors=True)
    for f in fails: print('  failed: ' + f)
    for p, c, why in KNOWN:
        k = [x for x in known if re.search(p, x.split(' ')[0])]
        if k: print('  known (%d runs, %s): %s' % (len(k), c, why))
    print('option combinations: %d runs, %d failed, %d known (%.0f s)' % (nrun, len(fails), len(known), time.time() - t0))
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
