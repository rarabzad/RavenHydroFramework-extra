"""Option combinations: small synthetic coupled models run across a matrix of options, every water identity checked, and
every exchange and stress a case names required to move water.

Each case is a strip of HRUs (sz_models.make_case: 4 HRUs of 200 x 200 m on a 0.01 slope, 100 m cells, wet days then dry
days) with some of these options (heights are taken at each feature's own place on the slope):
  exchanges  et   water-table ET (EXTINCTION_DEPTH 6 m, PET 30 mm/d, more than the soil's own evaporation meets)
             riv  a river along the strip (:RiverGeometry, a channel routed by Raven)
             swx  :SurfaceWaterExchange on DEPRESSION (ABST_FILL, DEP_MAX 50 mm)
             res  a reservoir with seepage (:ReservoirExchange): on HRU 1, its crest 0.5 m and its stage 0.3 m above the
                  ground of its cells, it loses water to the aquifer; with chd (and no dry top cells) a pit lake on the
                  outlet HRU, half over the specified-head cells, its stage 0.5 m below the specified head: it gains water
             wel  a pumping well (150 m3/d) screened 3 to 10 m below the ground of HRU 2
             ghb  a general-head boundary on the upslope cells, 2.5 m below their ground
             chd  a specified head on the downslope cells, 2 m below their ground
  stresses   dry  a 1 m top layer above the water table at the start (dry top cells; without NEWTON inactive)
             neg  negative recharge (PERC_GR4JEXCH from SOIL[1] to GROUNDWATER, GR4J_X2 40 mm/d)
             rise a specified head 0.3 m below the ground at the outlet and wet columns (:SoilZoneVadoseInitialFlux): the
                  water table rises through the unsaturated columns, which vanish
             bhs  :BoundaryHead series on the specified head (LAYERS TOP) and the GHB: 0.5 m below the ground on days 1-3,
                  3 m below it on days 4-6, then 0.5 m again, so cells are switched off and on
             bho  a :BoundaryHead series on the specified head that lies below the aquifer's bottom on days 4-6: every cell
                  of the boundary is switched off, and its columns take recharge, soil-zone and store water as ordinary ones
             reschd  (existing twins) a CHD package of the model's own on the 4 cells under the lake in stress periods 3-5
                  (one period per day): the lake's seepage on those days goes to its sliver of another HRU's cell only
  soil zone  CONCEPTUAL, or :SoilZone PHYSICAL with :SoilZoneVadose NONE / RICHARDS / KINEMATIC / LAG and 1 or 3 depth
             classes
  model      gen (Raven builds the model), ext (the generated model coupled as an existing model, NEWTON), ext_n0 (the
             same without NEWTON; CONCEPTUAL only), ext_ft (the existing model converted to feet and seconds); every case
             runs every model it can (ext_n0 only under CONCEPTUAL)
For an existing model, Raven's own packages of the generated model are taken out (Raven adds them again); its river,
well and head boundaries stay as the model's own packages (the river with a stage 0.5 m above its bed and a conductance of
50 m2/d, the well pumping 150 m3/d), also in feet and seconds.

Checks on every run (sz_check.checks and the Liard audit tool):
  MODFLOW balance (converged steps) and cumulative residual; Raven's balance; the recharge identity; the soil-zone
  identity; the unsaturated-column identity; no soil-zone shortfall; the river books (applied = net MODFLOW river flow
  - carry change + reservoir corrections); the surface-store books (applied = net exchange); the reservoir books (sent(t)
  = awaiting(t-1); sent = delivered - gain not supplied + not delivered); seepage returned = MODFLOW seepage; the run
  totals of GWModelSummary.txt (recharge not applied, reservoir seepage not delivered) equal their GWBudget.csv columns;
  no HDRY (|x| >= 1e20) and no NaN in GWBudget.csv, GWHRUState.csv, GWSoilExchange.csv and WatershedStorage.csv; with
  :SoilZone PHYSICAL no groundwater discharge into the surface stores on a step on which every HRU's water table is below
  its ground; "Successful Simulation". Unconverged MODFLOW steps are reported, not failed (their residual is booked).
Every run requires the flow of each exchange and stress its case names (needs(); each run's line lists the volumes moved),
at least FLOOR (half) of the volume recorded for that run in combinations_floors.json (--record writes the volumes of the
runs made; a quick and a full set), so that an exchange the coupling scales down fails as one it drops:
  et water-table ET; riv river leakage or discharge; swx surface-store leakage or discharge; res, losing lake: seepage sent
  and delivered to the aquifer (also with the model's own specified heads under it on some days, reschd), gaining lake:
  seepage sent and taken from the aquifer; wel the well's pumping; ghb, chd the boundary's flow (in an
  existing model the river, well and boundaries are the model's own packages: their volumes in MODFLOW's budget; in an
  existing model without NEWTON with dry top cells, which MODFLOW takes out of its solve, the stores, the lake and the
  river must exchange nothing, the books holding); dry a
  water table below the top layer at the start; neg a negative recharge; rise the columns vanish; columns an unsaturated
  inflow; bhs cell-steps switched off (GWModelSummary.txt) and a CHD flow on every step; bho cell-steps switched off, no
  CHD flow and nothing booked onto CHD cells on days 4-6, a CHD flow on days 1-3; reschd seepage returned on the day the
  specified heads start and none piled into the sliver on their other days (at most 1e-3 of the seepage before).
  A result whose cause lies outside the coupling is reported as KNOWN (listed with its reason), not failed: Raven's
  balance error equal to a reservoir's own routing balance error (ReservoirMassBalance.csv) of at most KNOWN_RES_TOL times
  the lake's area on each step, on steps whose stage lies within KNOWN_RES_CREST of the weir crest; any other balance
  error fails. A self-test runs first (also alone with --selftest): an unbooked 5,000 m3 added to a lake's routing error,
  and a small one away from the crest, must fail; the same small one at the crest is KNOWN.

Quick mode (RAVEN_TEST_QUICK=1): runs of 8 days (a few minutes). Full mode: dry top cells with negative recharge, negative
recharge in the moving-water group, 15 days each, and half-day steps.
Usage: python3 combinations.py [--list] [--only NAME,...] [--selftest] [--record]   (prints 'option combinations: N runs, 0 failed')"""
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


def gaining(s):
    """the case's lake is a pit lake fed by the specified head (else a lake on HRU 1 losing water)"""
    return 'chd' in s['x'] and 'dry' not in s['st']


def chd_head(s):
    """the specified head at the outlet [m]"""
    return land(XS + L - 0.5 * CELL) - (0.3 if 'rise' in s['st'] else 2.0)


def cfg_of(s):
    """sz_models.make_case arguments of case spec s"""
    wet = [20.0] * 3 + [0.0] * (DAYS - 3)
    c = dict(timestep=s.get('dt', 1.0), nhru=NHRU, hru_w=HW, width=HW, cell=CELL, slope=SLOPE, z0=Z0, rain=wet, days=DAYS, init_depth=1.5, Kh=10.0, Kv=1.0,
             aq_thick=10.0, Sy=0.1, perc=10.0, physical=(s['sz'] != 'CONC'))
    if 'et' in s['x']:
        c['pet'] = 30.0
    if 'chd' in s['x']:
        c['chd'] = chd_head(s)
    if 'dry' in s['st']:
        c['top'] = 1.0; c['init_depth'] = 1.0 + 1.0 + 1.5   # (soil zone 1 m, top layer 1 m, water table 1.5 m below the top layer)
    if 'neg' in s['st']:
        c['extra_proc'] = '  :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER\n'; c['extra_soil'] = {'GR4J_X2': 40.0, 'GR4J_X3': 150.0}
    if s['vz'] != 'NONE':
        c['aq_b'] = 4.0; c['aq_psia'] = 0.3
        c['extra_rvg'] = ':SoilZoneVadose %s\n' % s['vz'] + (':SoilZoneVadoseClasses %d\n' % s['K'] if s['K'] > 1 else '')
        if s['K'] > 1:
            c['dem_fn'] = lambda x, y: 0.3 * np.sin(2 * np.pi * x / 100.0) * np.sin(2 * np.pi * y / 100.0); c['dem_res'] = 400
        if 'rise' in s['st']:
            c['extra_rvg'] += ':SoilZoneVadoseInitialFlux 30\n'; c['Kh'] = 1000.0; c['Sy'] = 0.02; c['init_depth'] = 1.4; c['phi0'] = (100.0, 190.0)
            c['slope'] = 0.0; c['chd'] = Z0 - 0.3   # (flat: the specified head raises the water table under every HRU)
    return c


def lake(s):
    """(HRU of the lake, crest, initial stage) [m]"""
    if gaining(s):
        h = chd_head(s) if 'rise' not in s['st'] else Z0 - 0.3
        return NHRU, h - 0.3, h - 0.5
    g = land(XS + 0.5 * HW)
    return 1, g + 0.5, g + 0.3


def options(d, s, ext=False):
    """the option edits of spec s on case folder d (made by make_case); ext: the existing-model twin (no rivers, wells or
    head boundaries of Raven's: they are the model's own packages)"""
    rvi, rvh, rvp, rvt, rvg, rvc = (os.path.join(d, 'm.' + e) for e in ('rvi', 'rvh', 'rvp', 'rvt', 'rvg', 'rvc'))
    xp = []   # aquifer profile parameters added
    if 'et' in s['x']:
        xp.append(('EXTINCTION_DEPTH', 'm', 6.0)); sub(rvi, ':Evaporation PET_CONSTANT', ':Evaporation PET_DATA')
    if 'riv' in s['x'] and not ext:
        xp += [('RIVERBED_K', 'm/d', 5.0), ('RIVERBED_THICKNESS', 'm', 1.0)]
    if xp:
        sub(rvp, ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH',
            ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH' + ''.join(', ' + a for a, _, _ in xp))
        sub(rvp, '  :Units, m, m, 1/d, m\n  AQ, ', '  :Units, m, m, 1/d, m' + ''.join(', ' + u for _, u, _ in xp) + '\n  AQ, ')
        t = open(rvp).read(); i = t.find('\n  AQ, ', t.find('SEEPAGE_SMOOTHING_DEPTH')); j = t.find('\n', i + 1)
        open(rvp, 'w').write(t[:j] + ''.join(', %g' % v for _, _, v in xp) + t[j:])
    if 'riv' in s['x'] or 'res' in s['x']:   # a routed channel
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
    if 'res' in s['x']:
        kl, crest, stage = lake(s)
        open(rvh, 'a').write('\n:Reservoir Lake\n  :SubBasinID 1\n  :HRUID %d\n  :Type RESROUTE_STANDARD\n  :WeirCoefficient 0.6\n  :CrestWidth 5.0\n'
                             '  :MaxDepth 3.0\n  :LakeArea %g\n  :AbsoluteCrestHeight %.3f\n  :SeepageParameters 0.02 %.3f\n:EndReservoir\n' % (kl, HW * HW, crest, crest - 2.5))
        open(rvc, 'a').write('\n:InitialReservoirStage 1 %.3f\n:InitialReservoirFlow 1 0.0\n' % stage)
        open(rvg, 'a').write(':ReservoirExchange\n')
        open(rvi, 'a').write(':WriteReservoirMBFile\n')   # (the reservoir's own balance: KNOWN below)
    if 'wel' in s['x'] and not ext:
        lon, lat = sz_models.ll(XS + 1.5 * HW, 0.0)
        top = land(XS + 1.5 * HW) - 1.0
        open(rvg, 'a').write(':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n  1, PW_1, %.7f, %.7f, %.2f, %.2f\n:EndWells\n'
                             % (lat, lon, top - 2.0, top - 9.0))
        open(rvt, 'a').write('\n:WellFlowRate 1 m3/d\n  2000-01-01 00:00:00 1.0 %d\n' % DAYS + '  -150\n' * DAYS + ':EndWellFlowRate\n')
    if 'ghb' in s['x'] and not ext:
        polygon(os.path.join(d, 'ghb.geojson'), XS - HW, XS + 0.75 * CELL)
        open(rvg, 'a').write(':GeneralHeadBoundary GHB1 ghb.geojson HEAD %.2f CONDUCTANCE 200 LAYERS TOP\n' % (land(XS + 0.5 * CELL) - 2.5))
    if ('bhs' in s['st'] or 'bho' in s['st']) and not ext:   # boundary heads that cross the bottom of a cell: cells switched off and on
        t = open(rvg).read(); t = re.sub(r'(:SpecifiedHeadBoundary EDGE edge.geojson HEAD \S+)', r'\1 LAYERS TOP', t); open(rvg, 'w').write(t)
        for nm, xg in (('EDGE', XS + L - 0.5 * CELL), ('GHB1', XS + 0.5 * CELL)):
            if nm == 'GHB1' and ('ghb' not in s['x'] or 'bho' in s['st']): continue
            g = land(xg); low = g - 3.0 if 'bhs' in s['st'] else g - 30.0   # (bho: below the aquifer's bottom, every cell off)
            v = [g - 0.5] * 3 + [low] * 3 + [g - 0.5] * (DAYS - 6)
            open(rvt, 'a').write('\n:BoundaryHead %s m\n  2000-01-01 00:00:00 1.0 %d\n' % (nm, DAYS) + ''.join('  %.3f\n' % x for x in v) + ':EndBoundaryHead\n')


def generated(d, s):
    shutil.rmtree(d, ignore_errors=True); sz_models.make_case(d, **cfg_of(s)); options(d, s)
    return d


def own_packages(m):
    """the generated model's river and well, kept as the model's own packages: a stage 0.5 m above the river bed and a
    conductance of 50 m2/d, and the well's pumping (Raven set them every step; the files hold placeholders)"""
    for f, fix in (('gwf.riv', lambda w: w[:3] + ['%.8f' % (float(w[5]) + 0.5), '50.0', w[5]]), ('gwf.wel', lambda w: w[:3] + ['-150.0'])):
        p = os.path.join(m, f)
        if not os.path.exists(p): continue
        out, inper = [], False
        for l in open(p).read().split('\n'):
            w = l.split()
            if w[:1] == ['BEGIN'] and w[1:2] == ['PERIOD']: inper = True
            elif w[:1] == ['END']: inper = False
            elif inper and len(w) >= 4 and not l.strip().startswith('#'): l = '  ' + ' '.join(fix(w))
            out.append(l)
        open(p, 'w').write('\n'.join(out))


def existing(g, e, s, newton=True, feet=False):
    """the existing-model twin e of generated run g (run first)"""
    m = e + '_model'; shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in os.listdir(m):
        if f.endswith(('.lst', '.hds', '.cbc', '.cache', '.rch', '.drn', '.szx', '.szq', '.szd', '.szw', '.evt', '.swx', '.res')) or f == 'mfsim.stdout':
            os.remove(os.path.join(m, f))
    own_packages(m)
    drop = 'RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN|EVT_RAVEN|SWX_RAVEN|RES_RAVEN'
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


def package_volumes(d):
    """MODFLOW's cumulative volumes in and out of each package at the end of the run (the last budget of its list file):
    {package name: in + out} [model units]"""
    md = os.path.join(d, 'out', 'mf6'); v = {}
    for f in sorted(os.listdir(md)) if os.path.isdir(md) else []:
        if not f.endswith('.lst') or f == 'mfsim.lst': continue
        txt = open(os.path.join(md, f), errors='replace').read()
        k = txt.rfind('VOLUME BUDGET FOR ENTIRE MODEL')
        if k < 0: continue
        for l in txt[k:].split('\n')[1:200]:
            m = re.match(r'\s*\S+\s*=\s*([-0-9.Ee+]+)\s+\S+\s*=\s*[-0-9.Ee+]+\s+(\S+)\s*$', l)
            if m: v[m.group(2)] = v.get(m.group(2), 0.0) + abs(float(m.group(1)))
            if 'PERCENT DIFFERENCE' in l: break
    return v


def needs(s, mod):
    """the exchanges and stresses run mod of case s must move water through (check_run)"""
    gen = (mod == 'gen'); n = []
    off = (mod == 'ext_n0') and ('dry' in s['st'])   # (without NEWTON the dry top cells are inactive: no exchange there)
    if 'et' in s['x']: n.append('et')
    if 'swx' in s['x']: n.append('swx_none' if off else 'swx')
    if 'res' in s['x']: n.append('res_none' if off else ('res_gain' if gaining(s) else 'res_loss'))
    for k in ('riv', 'wel', 'ghb', 'chd'):
        if k in s['x']: n.append(k if gen else ('riv_none' if (off and k == 'riv') else k + '_pkg'))
    for k in ('dry', 'neg', 'rise'):
        if k in s['st']: n.append(k)
    if s['vz'] != 'NONE': n.append('columns')
    if gen: n += [k for k in ('bhs', 'bho') if k in s['st']]
    elif 'reschd' in s['st']: n.append('reschd')
    return n


ID = dict(sz_check.ID_LIMITS); ID.pop('mf6_err_rel')   # (MODFLOW's balance: on converged steps, below)
KNOWN_RES_TOL = 2.5e-4    # [m] largest routing balance error of the lake on one step excused as KNOWN, per m2 of lake (Raven's
                          # reservoir routine stops its stage iteration at a change of 0.1 mm, with its relaxation)
KNOWN_RES_CREST = 0.005   # [m] on steps whose stage lies at most this far from the weir crest


def lake_error_known(d):
    """Raven's balance error (WatershedStorage.csv) is the lake's own routing balance error (ReservoirMassBalance.csv)
    within 1e-4 mm, that error is at most KNOWN_RES_TOL x lake area on every step, and every step with an error has its
    stage within KNOWN_RES_CREST of the weir crest: (excused, total error [m3], why not)"""
    o = os.path.join(d, 'out'); rm = os.path.join(o, 'ReservoirMassBalance.csv')
    if not os.path.exists(rm): return False, 0.0, 'no reservoir balance file'
    w = pd.read_csv(os.path.join(o, 'WatershedStorage.csv')); w.columns = [c.strip() for c in w.columns]
    res_mm = (w['MB Error [mm]'] - (w['Deep Groundwater [mm]'] - w['Deep Groundwater [mm]'].iloc[0])).values
    rmb = pd.read_csv(rm); col = [c for c in rmb.columns if 'MB error' in c]; stc = [c for c in rmb.columns if 'stage' in c]
    err = rmb[col].fillna(0.0).sum(axis=1).values   # [m3] per step
    cum = np.cumsum(err) / (NHRU * HW * HW) * 1000.0   # [mm] (the lake's balance error, sign: lost)
    n = min(len(cum), len(res_mm)); tot = float(-cum[n - 1] * NHRU * HW * HW / 1000.0) if n else 0.0
    if not (n and np.abs(res_mm[:n] + cum[:n]).max() < 1e-4 + 1e-6 * np.abs(cum).max()):
        return False, tot, "Raven's balance error is not the lake's own routing error"
    rvh = open(os.path.join(d, 'm.rvh')).read()
    crest = float(re.search(r':AbsoluteCrestHeight\s+(\S+)', rvh).group(1)); area = float(re.search(r':LakeArea\s+(\S+)', rvh).group(1))
    big = np.abs(err) > 1e-6
    if (np.abs(err) > KNOWN_RES_TOL * area).any():
        return False, tot, 'the lake\'s routing error reaches %.3g m3 on one step, more than %.3g m3' % (np.abs(err).max(), KNOWN_RES_TOL * area)
    if stc and big.any():
        st = rmb[stc[0]].values
        far = np.abs(st[big] - crest) > KNOWN_RES_CREST
        if far.any():
            return False, tot, 'the lake\'s routing error is %.3g m3 on a step whose stage lies %.3g m from the weir crest' % (np.abs(err[big][far]).max(), np.abs(st[big][far] - crest).max())
    return True, tot, ''


FLOORS = os.path.join(HERE, 'combinations_floors.json')
FLOOR = 0.5       # a run's volume of each exchange or stress must be at least this fraction of the volume recorded for it
LAST_VOLS = {}    # (the volumes of the last check_run, by needs() key: what --record writes)


def load_floors():
    """the recorded volumes {mode: {'case model': {key: m3}}} (mode quick or full)"""
    try:
        return json.load(open(FLOORS))
    except (OSError, ValueError):
        return {}


def check_run(d, txt, need=(), floors=None):
    """every identity of run folder d: (list of failures, info); need: the exchanges and stresses the run must move water
    through (needs()); floors: the volumes recorded for this run {key: m3}, of which it must move at least FLOOR (None:
    only some water)"""
    bad = []; LAST_VOLS.clear()
    if 'Successful Simulation' not in txt:
        m = re.findall(r'Exiting Gracefully: (.*)', txt) or re.findall(r'ERROR[^\n]*', txt)
        return ['run: ' + ((m[-1] if m else txt[-300:]).strip()[:200])], ''
    o = os.path.join(d, 'out')
    tt = pd.read_csv(os.path.join(o, 'GWBudget.csv'))['time [d]']
    r = sz_check.checks(d, dt=float(tt.iloc[0]) if len(tt) else 1.0)   # (the step: half-day cases)
    for k, lim in ID.items():
        if k in r and not (r[k] <= lim):
            bad.append('%s %.3g' % (k, r[k]))
    if any(x.startswith('raven_mb_mm') for x in bad):   # Raven's balance error = the reservoir's own MB error, small, at the crest?
        ok, tot, why = lake_error_known(d)
        bad = [(('raven_mb_mm (= the reservoir routing balance error, %.3g m3)' % tot) if ok else (x + ' (' + why + ')')) if x.startswith('raven_mb_mm') else x for x in bad]
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
            m = re.search(pat, s)
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
    # the water each named exchange and stress moved [m3 over the run]; none moved: the case does not test it
    vol = lambda c: float((np.abs(g(c)) * dt).sum())
    moved, req = [], []
    def need_flow(key, label, v, ok_, fv=None):
        moved.append('%s %.3g' % (label, v))
        if fv is not None:   # (a volume: at least FLOOR of the one recorded for the run)
            LAST_VOLS[key] = float(fv)
            if floors is not None:
                f0 = floors.get(key)
                if f0 is None: ok_ = False; label += ': no volume recorded'
                elif not (fv >= FLOOR * f0): ok_ = False; label += ': %.3g, less than %g of the %.3g recorded' % (fv, FLOOR, f0)
        if not ok_: req.append('required: %s (%s)' % (key, label))
    pv = None
    for key in need:
        if key == 'et': v = vol('water-table ET [m3/d]'); need_flow(key, 'ET', v, v > 0.0, v)
        elif key in ('swx', 'swx_none'):
            v = vol('surface-store leakage to aquifer [m3/d]') + vol('aquifer discharge to surface stores [m3/d]'); need_flow(key, 'stores', v, (v > 0.0) == (key == 'swx'), v if key == 'swx' else None)
        elif key == 'res_none':
            v = vol('reservoir seepage sent [m3/d]') + vol('reservoir seepage delivered [m3/d]'); need_flow(key, 'lake (inactive cells)', v, v < 1e-6)
        elif key == 'riv_none':
            if pv is None: pv = package_volumes(d)
            v = pv.get('RIV_RAVEN', 0.0); need_flow(key, 'RIV_RAVEN (inactive cells)', v, v == 0.0)
        elif key == 'riv':
            v = vol('river leakage to aquifer [m3/d]') + vol('aquifer discharge to rivers [m3/d]'); need_flow(key, 'river', v, v > 0.0, v)
        elif key == 'wel': v = vol('wells actual [m3/d]'); need_flow(key, 'well', v, v > 0.0, v)
        elif key == 'ghb': v = vol('GHB [m3/d]'); need_flow(key, 'GHB', v, v > 0.0, v)
        elif key == 'chd': v = vol('CHD [m3/d]'); need_flow(key, 'CHD', v, v > 0.0, v)
        elif key.endswith('_pkg'):   # an existing model's own package: its volumes in MODFLOW's budget
            if pv is None: pv = package_volumes(d)
            nm = key[:-4].upper() + '_RAVEN'; v = pv.get(nm, 0.0); need_flow(key, nm, v, v > 0.0, v)
        elif key in ('res_loss', 'res_gain'):
            sent, dl = g('reservoir seepage sent [m3/d]') * dt, g('reservoir seepage delivered [m3/d]') * dt
            nd = g('reservoir seepage not delivered by MODFLOW [m3]')
            if key == 'res_loss':   # (delivered on the days the lake's cells can take it: also with the model's own
                                    # specified heads on some days, reschd)
                v = float(dl[dl > 0].sum())
                need_flow(key, 'lake loss sent/delivered/returned', float(sent[sent > 0].sum()), sent.max() > 1.0 and dl.max() > 1.0, v)
                moved[-1] += '/%.3g/%.3g' % (v, float(nd.sum()))
            else:
                v = float(-dl[dl < 0].sum())
                need_flow(key, 'lake gain sent/delivered', float(-sent[sent < 0].sum()), sent.min() < -1.0 and dl.min() < -1.0, v)
                moved[-1] += '/%.3g' % v
        elif key == 'neg': v = float(-(np.minimum(g('Raven recharge [m3/d]'), 0.0) * dt).sum()); need_flow(key, 'negative recharge', v, v > 0.0, v)
        elif key == 'columns': v = float(np.abs(g('unsaturated zone inflow [m3]')).sum()); need_flow(key, 'unsaturated inflow', v, v > 0.0, v)
        elif key == 'rise':
            us = g('unsaturated zone storage [m3]')
            need_flow(key, 'unsaturated storage largest/last', float(us.max()) if us.size else 0.0, us.size > 0 and us.max() > 0.0 and us[-1] <= 0.01 * us.max(),
                      float(us.max()) if us.size else 0.0)
            moved[-1] += '/%.3g' % (us[-1] if us.size else 0.0)
        elif key == 'dry':
            h = pd.read_csv(os.path.join(o, 'GWHRUState.csv')); wd = [c for c in h.columns if c.startswith('wtdepth_')]
            thr = 1.0 + (1.0 if 'soil zone to aquifer [m3/d]' in b else 0.0)   # (top layer 1 m, below a soil zone of 1 m)
            v = float(h[wd].iloc[0].max()) if wd and len(h) else 0.0; need_flow(key, 'water-table depth at the start', v, v > thr)
        elif key == 'reschd':
            dl, nd = g('reservoir seepage delivered [m3/d]'), g('reservoir seepage not delivered by MODFLOW [m3]')
            ok_ = len(dl) >= 5 and nd[2] > 1.0 and np.abs(dl[3:5]).max() <= 1e-3 * max(abs(dl[1]), 1.0)
            need_flow(key, 'seepage returned day 3', float(nd[2]) if len(nd) > 2 else 0.0, ok_, float(nd[2]) if len(nd) > 2 else 0.0)
        elif key in ('bhs', 'bho'):
            m = re.search(r'head boundaries off\s*:\s*(\d+)', s); noff = int(m.group(1)) if m else 0; q = np.abs(g('CHD [m3/d]'))
            if key == 'bhs': ok_ = noff > 0 and (q > 0.0).all()
            else:
                onto = np.abs(g('recharge onto CHD cells [m3/d]')) + np.abs(g('soil zone to specified heads [m3/d]')) + np.abs(g('specified heads to soil zone [m3/d]'))
                ok_ = noff > 0 and len(q) >= 6 and (q[:3] > 0.0).all() and q[3:6].max() == 0.0 and onto[3:6].max() == 0.0
            need_flow(key, 'cell-steps off', noff, ok_)
    bad += req
    info = 'MF6 unconverged %d' % int((~ok).sum()) + (('; moved: ' + ', '.join(moved)) if moved else '')
    if 'unsaturated zone inflow [m3]' in b:
        info += '; unsaturated inflow negative on %d steps' % int((b['unsaturated zone inflow [m3]'] < 0).sum())
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


def models_of(sz):
    """every model a case runs: generated, existing (NEWTON), existing without NEWTON (CONCEPTUAL), feet and seconds"""
    return ['gen', 'ext'] + (['ext_n0'] if sz == 'CONC' else []) + ['ext_ft']


def matrix():
    """the cases: (spec, models)"""
    ALL = ('et', 'riv', 'swx', 'res', 'wel', 'ghb', 'chd')
    C = []
    # exchange group: every exchange together and each alone, under plain conditions, dry top cells and negative recharge
    # (and both: full mode), CONCEPTUAL and PHYSICAL; the specified heads lie under every exchange's cells at the outlet
    xs = [ALL] + [(x,) for x in ALL] + [('et', 'swx', 'res', 'chd')]
    sts = [set(), {'dry'}, {'neg'}] + ([] if QUICK else [{'dry', 'neg'}])
    for x, st, sz in itertools.product(xs, sts, ('CONC', 'PHYS')):
        C.append((dict(sz=sz, vz='NONE', K=1, x=set(x), st=set(st), dt=1.0), models_of(sz)))
    # column group: PHYSICAL with unsaturated columns, 1 or 3 depth classes, negative recharge, rising water tables (the
    # columns vanish), dry top cells
    vzs = [(m, k) for m in ('RICHARDS', 'KINEMATIC', 'LAG') for k in (1, 3)]
    sts = [set(), {'neg'}, {'rise'}, {'rise', 'neg'}, {'dry'}, {'dry', 'neg'}]
    for (m, k), st in itertools.product(vzs, sts):
        x = ({'swx'} if 'rise' in st else {'swx', 'et'}) | ({'chd'} if ('rise' in st or 'dry' in st) else set())   # (a rising water table
                                                                                                                   # keeps the soil wet: no PET left)
        C.append((dict(sz='PHYS', vz=m, K=k, x=x, st=set(st), dt=1.0), models_of('PHYS')))
    # boundary group: :BoundaryHead series that switch cells off and on (generated models: the series are Raven's), and an
    # existing model's own specified heads switching on under a lake
    mw = [('CONC', 'NONE', {'res'}, {'reschd'}), ('PHYS', 'NONE', {'res'}, {'reschd'}),
          ('CONC', 'NONE', {'chd'}, {'bhs', 'dry'}), ('PHYS', 'NONE', {'chd'}, {'bhs', 'dry'}), ('CONC', 'NONE', {'chd', 'ghb'}, {'bhs', 'dry'}),
          ('PHYS', 'NONE', {'et', 'res', 'chd', 'swx'}, {'bhs', 'dry'}),
          ('CONC', 'NONE', {'chd', 'res'}, {'bho'}), ('PHYS', 'NONE', {'chd', 'swx', 'et'}, {'bho'}), ('PHYS', 'LAG', {'chd', 'swx', 'et'}, {'bho'})]
    if not QUICK:
        mw += [('CONC', 'NONE', {'res'}, {'neg', 'reschd'}), ('PHYS', 'NONE', {'chd', 'ghb'}, {'bhs', 'dry', 'neg'}), ('PHYS', 'RICHARDS', {'chd', 'swx', 'et'}, {'bho', 'neg'})]
    for sz, vz, x, st in mw:
        models = ['gen'] if ('bhs' in st or 'bho' in st) else models_of(sz)
        C.append((dict(sz=sz, vz=vz, K=1, x=set(x), st=set(st), dt=1.0), models))
    if not QUICK:   # half-day steps
        for sz, m, k in (('CONC', 'NONE', 1), ('PHYS', 'NONE', 1), ('PHYS', 'RICHARDS', 3), ('PHYS', 'LAG', 1)):
            C.append((dict(sz=sz, vz=m, K=k, x=set(ALL) if m == 'NONE' else {'swx', 'chd'}, st={'neg', 'rise'} if m != 'NONE' else {'neg'}, dt=0.5),
                      models_of(sz)))
    return C


# results known to fail for a reason outside the coupling's books, reported apart (case-name pattern, check prefix, reason)
KNOWN = [(r'res', 'raven_mb_mm (= the reservoir routing balance error',
          "Raven's balance error equals the lake's own routing balance error (ReservoirMassBalance.csv 'MB error', at most %g m3 per m2 "
          "of lake on a step, on steps whose stage lies within %g m of the weir crest): Raven's reservoir routine stops its stage "
          "iteration at a 0.1 mm change next to the kink of the weir curve, and base Raven gives the same without groundwater; the "
          "coupling's books hold" % (KNOWN_RES_TOL, KNOWN_RES_CREST))]


def classify(nm, bad):
    """(real failures, known results) of check_run's list for case nm"""
    kn = [b for b in bad if any(re.search(p, nm) and b.startswith(c) for p, c, _ in KNOWN)]
    return [b for b in bad if b not in kn], kn


def selftest():
    """the KNOWN exception excuses only a lake's own small routing error at its weir crest: a run's outputs with an unbooked
    5,000 m3 added to the lake's routing error (and to Raven's balance error, so the two still agree) must fail, as must a
    small one on a step away from the crest; the same small one on a step at the crest is KNOWN"""
    s = dict(sz='CONC', vz='NONE', K=1, x={'res'}, st=set(), dt=1.0); nm = name(s)
    g = generated(os.path.join(W, 'selftest', 'gen'), s); txt = run(g)
    if 'Successful Simulation' not in txt:
        print('self-test: the run FAILED'); return False
    _, kl_crest, _ = lake(s); good = True
    for label, E, step, at_crest, want in (('an unbooked 5,000 m3', 5000.0, 4, False, 'FAIL'), ('an unbooked 2 m3 away from the crest', 2.0, 4, False, 'FAIL'),
                                           ('an unbooked 2 m3 at the crest', 2.0, 4, True, 'KNOWN')):
        d = os.path.join(W, 'selftest', 'inj'); shutil.rmtree(d, ignore_errors=True); shutil.copytree(g, d)
        o = os.path.join(d, 'out')
        rm = pd.read_csv(os.path.join(o, 'ReservoirMassBalance.csv')); ce = [c for c in rm.columns if 'MB error' in c][0]; cs = [c for c in rm.columns if 'stage' in c][0]
        rm[ce] = rm[ce].astype(float); rm[cs] = rm[cs].astype(float); rm.loc[step, ce] += E
        if at_crest: rm.loc[step, cs] = kl_crest
        else: rm.loc[step, cs] = kl_crest - 0.3
        rm.to_csv(os.path.join(o, 'ReservoirMassBalance.csv'), index=False)
        p = os.path.join(o, 'WatershedStorage.csv'); w = pd.read_csv(p); mc = [c for c in w.columns if c.strip() == 'MB Error [mm]'][0]
        w[mc] = w[mc].astype(float); w.loc[step:, mc] -= E / (NHRU * HW * HW) * 1000.0
        w.to_csv(p, index=False)
        bad, _ = check_run(d, txt)
        real, kn = classify(nm, bad)
        got = 'FAIL' if real else ('KNOWN' if kn else 'ok')
        print('self-test: %-44s -> %-5s (%s)  %s' % (label, got, '; '.join(real or kn)[:150], 'ok' if got == want else 'FAILED, expected ' + want), flush=True)
        good &= (got == want)
    shutil.rmtree(os.path.join(W, 'selftest'), ignore_errors=True)
    return good


def main():
    only = None
    if '--only' in sys.argv:
        only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    C = matrix()
    if '--list' in sys.argv:
        for s, models in C: print('%-66s %s' % (name(s), ' '.join(models)))
        print('%d cases, %d runs' % (len(C), sum(len(m) for _, m in C))); return True
    t0 = time.time(); fails = []; known = []
    st_ok = selftest()
    if '--selftest' in sys.argv:
        print('option combinations self-test: %s' % ('PASS' if st_ok else 'FAIL')); return st_ok
    if not st_ok: fails.append('self-test')
    nrun = 0; info_txt = ['']
    mode = 'quick' if QUICK else 'full'
    record = '--record' in sys.argv; allf = load_floors(); fl = allf.get(mode, {})
    rec = {} if record else None
    fl_of = lambda nm, mod: None if record else fl.get('%s %s' % (nm, mod), {})

    def report(nm, mod, bad, info):
        if rec is not None and 'Successful Simulation' in info_txt[0]: rec['%s %s' % (nm, mod)] = {k: float('%.6g' % v) for k, v in LAST_VOLS.items()}
        real, kn = classify(nm, bad)
        print('%-66s %-7s %s  %s' % (nm, mod, ('ok' if not real else 'FAIL: ' + '; '.join(real)) + ('' if not kn else ' (KNOWN: ' + '; '.join(kn) + ')'), info), flush=True)
        if real: fails.append(nm + ' ' + mod)
        if kn: known.append(nm + ' ' + mod)
        return not real

    for s, models in C:
        nm = name(s)
        if only and nm not in only: continue
        g = generated(os.path.join(W, nm, 'gen'), s)
        txt = run(g); nrun += 1; info_txt[0] = txt
        report(nm, 'gen', *check_run(g, txt, needs(s, 'gen'), fl_of(nm, 'gen')))
        if 'Successful Simulation' not in txt:
            continue
        for mod in models[1:]:
            e = os.path.join(W, nm, mod)
            try:
                existing(g, e, s, newton=(mod != 'ext_n0'), feet=(mod == 'ext_ft'))
                txt = run(e); info_txt[0] = txt; res = check_run(e, txt, needs(s, mod), fl_of(nm, mod))
            except Exception as ex:
                res = (['set-up: %s' % str(ex)[:200]], ''); info_txt[0] = ''
            nrun += 1
            if report(nm, mod, *res):
                shutil.rmtree(e, ignore_errors=True); shutil.rmtree(e + '_model', ignore_errors=True)
            shutil.rmtree(e + '_model_ft', ignore_errors=True)
        if not any(f.startswith(nm + ' ') for f in fails): shutil.rmtree(os.path.join(W, nm), ignore_errors=True)
    if record:   # (the volumes of this run's cases replace those recorded for them)
        allf.setdefault(mode, {}).update(rec)
        json.dump(allf, open(FLOORS, 'w'), indent=0, sort_keys=True); print('recorded the volumes of %d runs (%s mode) in %s' % (len(rec), mode, FLOORS))
    for f in fails: print('  failed: ' + f)
    for p, c, why in KNOWN:
        k = [x for x in known if re.search(p, x.split(' ')[0])]
        if k: print('  known (%d runs, %s): %s' % (len(k), c, why))
    print('option combinations: %d runs, %d failed, %d known (%.0f s)' % (nrun, len(fails), len(known), time.time() - t0))
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
