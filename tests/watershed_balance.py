"""Raven's own water balance in coupled runs (WatershedStorage.csv 'MB Error [mm]').

The GROUNDWATER store is a pass-through in a coupled run: Raven's processes fill it during a step, the coupling hands its
contents to MODFLOW, and the next step empties it. Raven's balance counts its water as storage at the end of the step and
as outflow (or, negative, as input) when the next step empties it, so the MB error is Raven's true balance error. Each
case requires the store to hold water ('Deep Groundwater [mm]' at least 1 mm on some step, or below -0.1 mm for negative
recharge), so that counting it twice (as storage and as outflow in the same step) would show as an MB error of that size.

WB1  CONCEPTUAL, 4 HRUs, percolation into GROUNDWATER, 20 days: |MB error| <= 1e-6 mm on every step.
WB2  :SoilZone PHYSICAL, the same model: the same limit.
WB3  negative recharge (:Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER, GR4J_X2 40 mm/d takes water out of GROUNDWATER):
     the same limit, with the store negative on some step.
WB4  a hotstart: WB1 run 10 days, then 10 days from its solution.rvc, whose GROUNDWATER holds the last step's recharge
     (5 mm), with percolation of 2 mm/d: the restarted run's |MB error| <= 1e-6 mm (the store read from the .rvc is booked
     when the first step empties it; left unbooked, with the new step's store counted twice, the error would be 2 - 5 mm).
WB5  a disabled HRU: WB1's model with HRU 4 in a subbasin of its own, disabled (:DisableHRUGroup), and GROUNDWATER 5 mm
     for HRU 4 in the .rvc, which it keeps, a disabled HRU not being simulated: |MB error| <= 1e-6 mm (Raven's storage
     leaves disabled HRUs out, and so must the booking of the store; counted, the error would grow by 1.25 mm a step).
     (A disabled HRU is not coupled, so a coupled hotstart file does not fit such a set-up: its grid differs.)
WB6  a cold start whose .rvc sets GROUNDWATER (5 mm, :UniformInitialConditions): the first step empties the store before any
     exchange, so MODFLOW never receives it; Raven warns (Raven_errors.txt names GROUNDWATER and :GWHeads), books it as
     leaving Raven in the first step (Cum. Outflow of step 1 at least 5 mm) and its |MB error| <= 1e-6 mm.
River losses (a losing river: RIVERBED_K 20 m/d, the water table 6 m below the land, 40 mm/d of rain on days 1-3):
WB7  a loss taken from a reach's inflow: two subbasins, the lower one losing and fed by a 0.02 m3/s
     :BasinInflowHydrograph, so the loss is taken from the inflow on every step. Raven's channel storage and outflow take a
     change of inflow half in the step and half in the next, and so does Raven's balance: |MB error| <= 1e-6 mm on every
     step, with a take on at least 5 steps, and the run total 'river take in transit' is half the last step's take
     (:GWRiverTake; the summary's 6 digits); a run restarted on day 5 (a take day) from the first part's solution.rvc
     (:GWRiverTake) has |MB error| <= 1e-6 mm and the continuous run's hydrographs (1e-9 relative), and the same restart
     with a step of -1 or 0 on the :GWRiverTake header stops ("the time step of the takes must be positive"); each member of a 2-member
     Monte Carlo ensemble equals the single run (GWBudget.csv, Hydrographs.csv: 1e-12 relative) and has |MB error| <= 1e-6 mm.
WB8  a headwater reach (one subbasin, no inflow) with a 10-day in-catchment unit hydrograph (ROUTE_TRI_CONVOLUTION): on the
     dry days the loss is taken from the reach's outflow, so the loss carried at the end of the run is at most 1 % of
     MODFLOW's river leakage, and the outflow is lower than in the same model without the river by the loss applied
     (summed over the run, within 1 %); |MB error| <= 1e-6 mm; a run restarted on day 6 (a day whose loss came from the
     outflow) has the continuous run's hydrographs and channel storage (1e-9 relative).
WB9  the same reach with :CatchmentRoute ROUTE_DUMP: the reach stops flowing on day 4, whose loss it can no longer
     supply; that loss is carried and reported: a warning in Raven_errors.txt and the run total 'river loss carried' in
     GWModelSummary.txt, equal to the last value of 'river loss carried to next step' in GWBudget.csv (1e-6 relative).
WB10 every channel routing method (MUSKINGUM and MUSKINGUM_CUNGE over a 300 km reach; STORAGECOEFF, ROUTE_HYDROLOGIC,
     DIFFUSIVE_WAVE and PLUG_FLOW over 30 km): SB2 losing (bed conductivity 200 m/d), fed only by a 0.05 m3/s inflow on
     days 1-5 (no rain, so no lateral flow), then 35 dry days of recession, so the loss is taken from the inflow and then
     from the reach's outflow. Against the same run without the river: the volume that left the watershed is lower by
     exactly the loss taken (0.5 m3 + 1e-5, the file's digits), and the channel storage at the end is the same (1e-5 of
     the take, the water still in transit at the end of the 300 km reaches: the methods that keep the outflow as their state route the channel's own water as without the take).
     Also with an irrigation demand of 0.003 m3/s on SB2, the run without the river given the irrigation the river run
     delivered, so both withdraw the same (Raven's own irrigation withdrawal lowers its routing state with these methods;
     the take adds nothing to that). WB10 also checks the run total 'river take in transit': given (half of :GWRiverTake)
     when above 1e-6 m3, not given for the round-off takes of a reach that has stopped flowing.
WB11 a reach whose outflow is set from outside the routing: both subbasins ROUTE_EXTERNAL, a live file (:ReadLiveFile)
     setting SB1's outflow to 0 and SB2's to 0.02 m3/s every step, no rain and no inflow, so SB2's loss is taken from the
     outflow the live file set: the outflow delivered at the end of each step is that outflow less the step's take
     (hydrograph: the mean of the two, against the run without the river; 0.01 m3 + 1e-4 per step), the channel storage
     ends as in the run without the river (1e-6 of the takes; added back to the set outflow, the last take would hide the
     take from the flows and lower the channel storage by it every step), and Raven warns that the outflow was set from
     outside the routing.
WB12 ensemble members start from the first run's routing memory: the two-subbasin losing reach (30 km, bed conductivity
     200 m/d, ROUTE_DUMP) with ROUTE_HYDROLOGIC, ROUTE_STORAGECOEFF and ROUTE_TVD, which read the local outflow, with and
     without groundwater; each member of a 2-member Monte Carlo ensemble equals the single run (Hydrographs.csv, and
     GWBudget.csv with groundwater): exactly without groundwater, 1e-12 relative with it; and an irrigated reach
     (0.003 m3/s, ROUTE_HYDROLOGIC, ROUTE_TRI_CONVOLUTION) whose members also equal the single run in Demands.csv (its
     deliveries and returns from the first row; the demands from the second row, the first row's being the demand
     objects' value before the first step).
WB13 a restart with another :TimeStep right after a take: the WB10 reach (inflow 0.05 m3/s on days 1-5, no rain),
     ROUTE_HYDROLOGIC and ROUTE_STORAGECOEFF, :TimeStep 0.5 then 1 and 1 then 0.25, restarted after day 5 (the last take
     from the outflow) and after day 3 (from the inflow), with the same pair of runs without the river: over both parts
     the outflow leaving the watershed is lower by the leakage MODFLOW received less the loss carried at the end (0.5 m3
     + 1e-5, the file's digits), the channel storage ends the same (1e-5 of the leakage), and |MB error| <= 1e-6 mm.
WB14 a restart with a longer :TimeStep right after takes from the reach's inflow, where Raven averages the reach's inflow
     history to the longer step (ROUTE_DIFFUSIVE_WAVE; the WB13 reach, restarted after day 3): :TimeStep 0.5 then 1,
     0.25 then 1, and 0.25, then 0.5 for half a day, then 1 (the second restart averages a take of the 0.5-day part with
     the 0.25-day takes before it); restarted after day 4: 0.1, then 0.2 for one step, then 1, and 1, then 0.2 for one
     step, then 1 (Raven rescales only the entries of the lateral-inflow history length); with the same runs without the
     river: in every part the MB error exceeds the run's without the river by at most 1e-6 mm on every step (the runs
     without the river carry Raven's own error of the rescaling, up to 2.2 mm here), and the leakage MODFLOW received less the
     loss carried at the end equals the lower outflow plus the lower channel storage at the end (0.5 m3 + 1e-5). With
     RAVEN_EXE_REF: a restart (0.5 then 1) from a solution.rvc the reference build wrote, without :GWRiverInflowTakes, has
     an MB error no larger than the reference build's own restart from it.

Usage: python3 watershed_balance.py   (needs RAVEN_MF6_LIB; about a minute)
"""
import os, sys, re, shutil, json, subprocess, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'soilzone')); sys.path.insert(0, HERE)
import testconfig as tc
import sz_models, sz_check
import numpy as np, pandas as pd

tc.need_mf6()
W = os.path.dirname(tc.work('watershed_balance', 'x'))
LIM = 1e-6
RAIN = [8.0, 0.0, 15.0, 0.0, 4.0] * 4
BASE = dict(nhru=4, hru_w=200.0, slope=0.02, rain=RAIN, days=20, init_depth=1.5, perc=5.0)
results = []


def disable_hru4(d):
    """HRU 4 into a subbasin 2 of its own, which is disabled with it"""
    p = os.path.join(d, 'm.rvh'); h = open(p).read()
    h = h.replace('  1, box, -1, NONE, ZERO-, 1\n', '  1, box, -1, NONE, ZERO-, 1\n  2, box2, -1, NONE, ZERO-, 0\n')
    h = '\n'.join(re.sub(r'^(  4, [^,]+, [^,]+, [^,]+, [^,]+, )1,', r'\g<1>2,', l) for l in h.split('\n'))
    open(p, 'w').write(h + '\n:HRUGroup Off\n  4\n:EndHRUGroup\n')
    open(os.path.join(d, 'm.rvp'), 'a').write('\n:AvgAnnualRunoff 300\n')
    p = os.path.join(d, 'm.rvi'); t = open(p).read()
    open(p, 'w').write(t.replace(':HydrologicProcesses', ':DefineHRUGroups Off\n:DisableHRUGroup Off\n:HydrologicProcesses', 1))


def case(name, start=None, rvc=None, post=None, **cfg):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **cfg)
    if post:
        post(d)
    if start:
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(d, f); t = open(p).read(); open(p, 'w').write(t.replace('2000-01-01 00:00:00', start + ' 00:00:00'))
    if rvc:
        shutil.copy(rvc, os.path.join(d, 'm.rvc'))
    ok, txt = sz_check.run(d)
    return d if ok else None, txt


def judge(label, d, txt, need_neg=False):
    if d is None:
        results.append((label, False)); print('%-70s FAIL (the run failed: %s)' % (label, txt.strip().split('\n')[-1][:120])); return
    w = pd.read_csv(os.path.join(d, 'out', 'WatershedStorage.csv')); w.columns = [c.strip() for c in w.columns]
    mb, g = w['MB Error [mm]'], w['Deep Groundwater [mm]']
    held = (g.min() < -0.1) if need_neg else (g.max() >= 1.0)
    good = held and mb.abs().max() <= LIM
    results.append((label, good))
    print('%-70s %s  (largest |MB error| %.2g mm; GROUNDWATER store %.3g to %.3g mm)' % (label, 'ok' if good else 'FAIL', mb.abs().max(), g.min(), g.max()))


d, t = case('wb1', physical=False, **BASE); judge('WB1 CONCEPTUAL: MB error at round-off', d, t)
d, t = case('wb2', physical=True, **BASE); judge('WB2 :SoilZone PHYSICAL: MB error at round-off', d, t)
d, t = case('wb3', physical=False, extra_proc='  :Percolation PERC_GR4JEXCH SOIL[1] GROUNDWATER\n',
            extra_soil={'GR4J_X2': 40.0, 'GR4J_X3': 150.0}, **dict(BASE, perc=1.0))
judge('WB3 negative recharge: MB error at round-off', d, t, need_neg=True)
a, t = case('wb4_first', physical=False, **dict(BASE, days=10, rain=RAIN[:10]))
if a is None:
    judge('WB4 hotstart', None, t)
else:
    rvc = os.path.join(a, 'out', 'solution.rvc')
    tab = open(rvc).read().split(':HRUStateVariableTable')[1].split(':EndHRUStateVariableTable')[0].strip().split('\n')
    hdr = [x.strip() for x in tab[0].split(',')]; i = hdr.index('GROUNDWATER')
    gw = max(float(r.split(',')[i]) for r in tab[2:] if r.strip())
    print('  (the .rvc of the first part holds GROUNDWATER up to %.3g mm)' % gw)
    b, t = case('wb4_second', start='2000-01-11', rvc=rvc, physical=False, **dict(BASE, days=10, rain=RAIN[10:], perc=2.0))
    if gw <= 0.0:
        results.append(('WB4', False)); print('WB4 FAIL: the .rvc holds no GROUNDWATER (precondition)')
    else:
        judge('WB4 hotstart from a .rvc holding GROUNDWATER: MB error at round-off', b, t)

def wb5_post(d):
    disable_hru4(d)
    open(os.path.join(d, 'm.rvc'), 'a').write('\n:HRUStateVariableTable\n  :Attributes,GROUNDWATER\n  :Units,mm\n  4,5.0\n:EndHRUStateVariableTable\n')


c, t = case('wb5_disabled', post=wb5_post, physical=False, **BASE)
if c is not None:
    v = open(os.path.join(c, 'out', 'solution.rvc')).read().split(':HRUStateVariableTable')[1].split(':EndHRUStateVariableTable')[0].strip().split('\n')
    i = [x.strip() for x in v[0].split(',')].index('GROUNDWATER')
    g4 = [float(r.split(',')[i]) for r in v[2:] if r.strip() and r.split(',')[0].strip() == '4']
    if not (g4 and g4[0] == 5.0):
        results.append(('WB5', False)); print('WB5 FAIL: the disabled HRU does not keep its GROUNDWATER (precondition): %s' % g4); c = False
if c is not False:
    judge('WB5 a disabled HRU holding GROUNDWATER: MB error at round-off', c, t)

c, t = case('wb6_cold_gw', post=lambda d: open(os.path.join(d, 'm.rvc'), 'a').write('\n:UniformInitialConditions GROUNDWATER 5.0\n'),
            physical=False, **BASE)
if c is not None:
    err = open(os.path.join(c, 'out', 'Raven_errors.txt')).read()
    w = pd.read_csv(os.path.join(c, 'out', 'WatershedStorage.csv')); w.columns = [x.strip() for x in w.columns]
    warned = 'initial conditions set GROUNDWATER' in err and ':GWHeads' in err
    out1 = float(w['Cum. Outflow [mm]'].iloc[1]); mbx = float(w['MB Error [mm]'].abs().max())
    good = warned and out1 >= 5.0 and mbx <= LIM
    results.append(('WB6', good))
    print('%-70s %s  (warning %s; step 1 Cum. Outflow %.3g mm; largest |MB error| %.2g mm)'
          % ('WB6 cold start with GROUNDWATER in the .rvc: warned and booked', 'ok' if good else 'FAIL', 'given' if warned else 'MISSING', out1, mbx))
else:
    judge('WB6 cold start with GROUNDWATER in the .rvc', None, t)


# ---- river losses ------------------------------------------------------------------------------------------------------
RCFG = dict(nhru=4, hru_w=200.0, width=200.0, cell=100.0, slope=0.01, z0=100.0, init_depth=6.0, Kh=10.0, Kv=1.0, aq_thick=12.0,
            Sy=0.1, perc=10.0, physical=False)
CHAN = (':ChannelProfile CHAN\n  :Bedslope 0.01\n  :SurveyPoints\n    0 2.0\n    2 0\n    8 0\n    10 2.0\n  :EndSurveyPoints\n'
        '  :RoughnessZones\n    0 0.035\n  :EndRoughnessZones\n:EndChannelProfile\n')


def sub(p, a, b):
    t = open(p).read(); assert a in t, (p, a); open(p, 'w').write(t.replace(a, b))


def river_case(d, days, upstream, croute='ROUTE_TRI_CONVOLUTION', river=True, route='ROUTE_DIFFUSIVE_WAVE', reach=0.8, rain=None, qin=None,
               rbk=20.0, irr=None):
    """the losing-river set-up; upstream: two subbasins (SB1 -> SB2, SB2 losing, with an inflow hydrograph: qin [m3/s]
    per day, default 0.02 throughout), else one headwater subbasin; route the channel routing, reach the reach length
    [km]; rain [mm/d] per day (default 40 on days 1-3); irr an irrigation demand on SB2 [m3/s]"""
    shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, rain=rain if rain is not None else [40.0] * 3 + [0.0] * (days - 3), days=days, **RCFG)
    rvh, rvi, rvp, rvg = (os.path.join(d, 'm.' + e) for e in ('rvh', 'rvi', 'rvp', 'rvg'))
    L = RCFG['nhru'] * RCFG['hru_w']; XS = -0.5 * L
    if upstream:
        sub(rvh, '  1, box, -1, NONE, ZERO-, 1', '  1, up, 2, CHAN, %g, 1\n  2, down, -1, CHAN, %g, 1' % (reach, reach))
        h = open(rvh).read().split('\n')
        for i, l in enumerate(h):
            w = [x.strip() for x in l.split(',')]
            if len(w) > 10 and w[0] in ('3', '4'):
                w[5] = '2'; h[i] = '  ' + ', '.join(w)
        open(rvh, 'w').write('\n'.join(h) + '\n:SubBasinProperties\n  :Parameters, Q_REFERENCE\n  :Units, m3/s\n  1, 0.05\n  2, 0.05\n:EndSubBasinProperties\n')
        line, sbid = [sz_models.ll(XS + 0.5 * L + 20.0, 0.0), sz_models.ll(XS + L - 20.0, 0.0)], 2
        q = list(qin) + [0.0] * (days + 5 - len(qin)) if qin is not None else [0.02] * (days + 5)
        open(os.path.join(d, 'm.rvt'), 'a').write('\n:BasinInflowHydrograph 2\n  2000-01-01 00:00:00 1.0 %d\n' % len(q) + ''.join('  %g\n' % x for x in q)
                                                  + ':EndBasinInflowHydrograph\n')
        if irr is not None:   # (a demand [m3/s], or a series of daily demands)
            v = list(irr) + [0.0] * (days + 5 - len(irr)) if isinstance(irr, (list, tuple)) else [irr] * (days + 5)
            open(os.path.join(d, 'm.rvt'), 'a').write('\n:IrrigationDemand 2\n  2000-01-01 00:00:00 1.0 %d\n' % len(v) + ''.join('  %.17g\n' % x for x in v)
                                                      + ':EndIrrigationDemand\n')
            open(os.path.join(d, 'm.rvi'), 'a').write(':WriteDemandFile\n')
        open(rvp, 'a').write(':AvgAnnualRunoff 300\n')
    else:
        sub(rvh, '  1, box, -1, NONE, ZERO-, 1', '  1, box, -1, CHAN, 0.8, 1')
        open(rvh, 'a').write('\n:SubBasinProperties\n  :Parameters, Q_REFERENCE, TIME_TO_PEAK, TIME_CONC\n  :Units, m3/s, d, d\n  1, 0.05, 2.0, 10.0\n:EndSubBasinProperties\n')
        line, sbid = [sz_models.ll(XS + 20.0, 0.0), sz_models.ll(XS + L - 20.0, 0.0)], 1
    sub(rvi, ':Routing ROUTE_NONE', ':Routing ' + route)
    sub(rvi, ':CatchmentRoute ROUTE_DUMP', ':CatchmentRoute ' + croute)
    open(rvp, 'a').write(CHAN)
    sub(rvp, ':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0', ':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.6')
    sub(rvp, ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH',
        ':Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH, RIVERBED_K, RIVERBED_THICKNESS')
    sub(rvp, '  :Units, m, m, 1/d, m\n', '  :Units, m, m, 1/d, m, m/d, m\n')
    t = open(rvp).read(); i = t.find('\n  AQ, ', t.find('RIVERBED_THICKNESS')); j = t.find('\n', i + 1)
    open(rvp, 'w').write(t[:j] + ', %g, 1.0' % rbk + t[j:])
    if river:
        json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"SUBID": sbid}, "geometry": {"type": "LineString", "coordinates": line}}]},
                  open(os.path.join(d, 'river.geojson'), 'w'))
        open(rvg, 'a').write(':RiverGeometry river.geojson SUBID\n')
    return d


def restart_parts(d, days, rday):
    """the first rday days and the rest from the first part's solution.rvc; returns (first, second) folders or None"""
    p1, p2 = d + '_p1', d + '_p2'
    for x in (p1, p2):
        shutil.rmtree(x, ignore_errors=True); shutil.copytree(d, x, ignore=shutil.ignore_patterns('out'))
    sub(os.path.join(p1, 'm.rvi'), ':Duration %d' % days, ':Duration %d' % rday)
    ok1, _ = sz_check.run(p1)
    sub(os.path.join(p2, 'm.rvi'), ':Duration %d' % days, ':Duration %d' % (days - rday))
    sub(os.path.join(p2, 'm.rvi'), ':StartDate 2000-01-01', ':StartDate 2000-01-%02d' % (rday + 1))
    if not ok1:
        return None
    shutil.copy(os.path.join(p1, 'out', 'solution.rvc'), os.path.join(p2, 'm.rvc'))
    ok2, _ = sz_check.run(p2)
    return (p1, p2) if ok2 else None


def csv(d, f):
    x = pd.read_csv(os.path.join(d, 'out', f)); x.columns = [c.strip() for c in x.columns]
    return x


def rel_dev(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    return float(np.max(np.abs(a - b) / np.maximum(np.abs(a), 1e-12))) if len(a) == len(b) and len(a) else float('inf')


def flows(d):
    h = csv(d, 'Hydrographs.csv')
    return h[[c for c in h.columns if c.endswith('[m3/s]') and 'precip' not in c.lower()]].values.ravel()


# WB7: a loss taken from the reach's inflow
DAYS7 = 12
d7 = river_case(os.path.join(W, 'wb7_inflow_take'), DAYS7, upstream=True)
ok7, txt7 = sz_check.run(d7)
if not ok7:
    results.append(('WB7', False)); print('WB7 FAIL (the run failed: %s)' % txt7.strip().split('\n')[-1][:120])
else:
    b, w = csv(d7, 'GWBudget.csv'), csv(d7, 'WatershedStorage.csv')
    ntake = int((b['river exchange applied to Raven [m3]'] < -1e-6).sum()); mbx = float(w['MB Error [mm]'].abs().max())
    m = re.search(r':GWRiverTake[^\n]*\n([\s\S]*?):EndGWRiverTake', open(os.path.join(d7, 'out', 'solution.rvc')).read())
    half = 0.5 * sum(float(x) for l in m.group(1).strip().split('\n') for x in l.split(',')[1:3]) if m else 0.0
    mt = re.search(r'river take in transit\s*: (\S+) m3', open(os.path.join(d7, 'out', 'GWModelSummary.txt')).read())
    g1 = ntake >= 5 and mbx <= LIM and half > 1e-6 and mt is not None and abs(float(mt.group(1)) - half) <= 5e-6 * half
    print('%-70s %s  (loss taken on %d steps; largest |MB error| %.2g mm; take in transit %s m3, half of the last step: %.6g)' % (
          'WB7 river loss taken from the inflow: MB error at round-off', 'ok' if g1 else 'FAIL', ntake, mbx, mt.group(1) if mt else 'MISSING', half))
    parts = restart_parts(d7, DAYS7, 5)
    if parts is None:
        g2 = False; print('WB7 restart FAIL (a run failed)')
    else:
        rvc = open(os.path.join(parts[0], 'out', 'solution.rvc')).read(); w2 = csv(parts[1], 'WatershedStorage.csv')
        fc, fr = flows(d7), flows(parts[1]); n2 = len(fr)
        dq = rel_dev(fc[-n2:], fr); mb2 = float(w2['MB Error [mm]'].abs().max())
        g2 = ':GWRiverTake' in rvc and mb2 <= LIM and dq <= 1e-9
        print('%-70s %s  (:GWRiverTake %s; largest |MB error| %.2g mm; hydrographs %.1e)' % ('WB7 restart on a take day: MB error at round-off, the same flows', 'ok' if g2 else 'FAIL',
              'written' if ':GWRiverTake' in rvc else 'MISSING', mb2, dq))
        # the time step on the :GWRiverTake header: a step that is not positive stops with the step's message
        for v in ('-1', '0'):
            q = parts[1] + '_dt'; shutil.rmtree(q, ignore_errors=True); shutil.copytree(parts[1], q, ignore=shutil.ignore_patterns('out'))
            t = open(os.path.join(q, 'm.rvc')).read(); open(os.path.join(q, 'm.rvc'), 'w').write(re.sub(r':GWRiverTake \S+', ':GWRiverTake ' + v, t, count=1))
            okq, txq = sz_check.run(q); e = os.path.join(q, 'out', 'Raven_errors.txt'); txq += open(e).read() if os.path.exists(e) else ''
            gq = (not okq) and 'the time step of the takes must be positive' in txq
            g2 = g2 and gq
            print('%-70s %s' % ('WB7 :GWRiverTake %s (the step of the takes) stops with the step message' % v, 'ok' if gq else 'FAIL'))
    e = d7 + '_ens'; shutil.rmtree(e, ignore_errors=True); shutil.copytree(d7, e, ignore=shutil.ignore_patterns('out'))
    open(os.path.join(e, 'm.rvi'), 'a').write('\n:EnsembleMode ENSEMBLE_MONTECARLO 2\n')
    open(os.path.join(e, 'm.rve'), 'w').write(':OutputDirectoryFormat ./ens_*/\n:ParameterDistributions\n  HYDRAUL_COND SOIL SOIL 100 DIST_UNIFORM 100 100\n:EndParameterDistributions\n')
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=e, capture_output=True, text=True, env=tc.ENV)
    devs, mbs = [], []          # (WatershedStorage.csv: only the MB error; in ensemble mode base Raven reports other channel
    for m in (1, 2):            #  and rivulet storages than in a single run, also without groundwater)
        o = os.path.join(e, 'ens_%d' % m)
        if not os.path.exists(os.path.join(o, 'GWBudget.csv')):
            devs.append(float('inf')); continue
        for f in ('GWBudget.csv', 'Hydrographs.csv'):
            A = csv(d7, f); B = pd.read_csv(os.path.join(o, f)); B.columns = [c.strip() for c in B.columns]
            devs.append(max(float(tc.max_diff(A[c], B[c], max(float(A[c].abs().max()), 1e-9))) for c in A.columns if pd.api.types.is_numeric_dtype(A[c])))
        B = pd.read_csv(os.path.join(o, 'WatershedStorage.csv')); B.columns = [c.strip() for c in B.columns]
        mbs.append(float(B['MB Error [mm]'].abs().max()))
    g3 = 'Successful' in r.stdout + r.stderr and max(devs) <= 1e-12 and max(mbs + [float('inf')] * (len(mbs) < 2)) <= LIM
    print('%-70s %s  (largest relative difference %.1e; largest |MB error| of the members %.2g mm)' % ('WB7 2-member ensemble: each member equals the single run', 'ok' if g3 else 'FAIL',
          max(devs), max(mbs) if mbs else float('inf')))
    results.append(('WB7', g1 and g2 and g3))

# WB8: a headwater reach; the loss taken from its outflow
DAYS8 = 20
d8 = river_case(os.path.join(W, 'wb8_headwater'), DAYS8, upstream=False)
d8n = river_case(os.path.join(W, 'wb8_headwater_noriver'), DAYS8, upstream=False, river=False)
(ok8, txt8), (ok8n, _) = sz_check.run(d8), sz_check.run(d8n)
if not (ok8 and ok8n):
    results.append(('WB8', False)); print('WB8 FAIL (a run failed: %s)' % txt8.strip().split('\n')[-1][:120])
else:
    b, w = csv(d8, 'GWBudget.csv'), csv(d8, 'WatershedStorage.csv')
    leak = float(b['river leakage to aquifer [m3/d]'].sum()); applied = float(b['river exchange applied to Raven [m3]'].sum())
    carried = float(b['river loss carried to next step [m3]'].iloc[-1])
    q, q0 = flows(d8) * 86400.0, flows(d8n) * 86400.0                 # [m3/d] (daily mean flows: their sum is the volume)
    drop = float((q0 - q).sum()); mbx = float(w['MB Error [mm]'].abs().max())
    g1 = leak > 100.0 and carried <= 0.01 * leak and abs(drop + applied) <= 0.01 * abs(applied) and mbx <= LIM
    print('%-70s %s  (leakage %.1f m3, carried at the end %.2f m3, outflow lower by %.1f m3 for %.1f m3 applied; |MB error| %.2g mm)'
          % ('WB8 headwater reach: the loss taken from its outflow', 'ok' if g1 else 'FAIL', leak, carried, drop, -applied, mbx))
    parts = restart_parts(d8, DAYS8, 6)
    if parts is None:
        g2 = False; print('WB8 restart FAIL (a run failed)')
    else:
        rvc = open(os.path.join(parts[0], 'out', 'solution.rvc')).read()
        fc, fr = flows(d8), flows(parts[1]); n2 = len(fr)
        wc, wr = csv(d8, 'WatershedStorage.csv'), csv(parts[1], 'WatershedStorage.csv')
        ch = [c for c in wc.columns if c.startswith('Channel Storage')]
        dq = rel_dev(fc[-n2:], fr); dch = rel_dev(wc[ch[0]].values[-len(wr):], wr[ch[0]].values) if ch else float('inf')
        g2 = ':GWRiverTake' in rvc and dq <= 1e-9 and dch <= 1e-9
        print('%-70s %s  (:GWRiverTake %s; hydrographs %.1e, channel storage %.1e)' % ('WB8 restart after a take from the outflow: the same flows and channel', 'ok' if g2 else 'FAIL',
              'written' if ':GWRiverTake' in rvc else 'MISSING', dq, dch))
    results.append(('WB8', g1 and g2))

# WB9: a reach that stops flowing: the loss it cannot supply is carried, warned about and in the run totals
d9 = river_case(os.path.join(W, 'wb9_dump'), 12, upstream=False, croute='ROUTE_DUMP')
ok9, txt9 = sz_check.run(d9)
if not ok9:
    results.append(('WB9', False)); print('WB9 FAIL (the run failed: %s)' % txt9.strip().split('\n')[-1][:120])
else:
    b = csv(d9, 'GWBudget.csv'); carried = float(b['river loss carried to next step [m3]'].iloc[-1])
    err = open(os.path.join(d9, 'out', 'Raven_errors.txt')).read(); sm = open(os.path.join(d9, 'out', 'GWModelSummary.txt')).read()
    m = re.search(r'river loss carried\s*: (\S+) m3 at the end of the run', sm)
    tot = float(m.group(1)) if m else None
    warned = 'of river leakage to the aquifer could not be taken from the reaches' in err
    g = carried > 1.0 and warned and tot is not None and abs(tot - carried) <= 1e-6 * carried
    print('%-70s %s  (carried %.3f m3; warning %s; run total %s)' % ('WB9 a loss the reach cannot supply: carried, warned, in the run totals', 'ok' if g else 'FAIL',
          carried, 'given' if warned else 'MISSING', tot))
    results.append(('WB9', g))

# WB10: every routing method; the routing state keeps the outflow before the take
def chan_end(d):
    """the channel storage of every subbasin at the end of the run [m3] (solution.rvc, 17 digits)"""
    return sum(float(x) for x in re.findall(r':ChannelStorage,\s*(\S+)', open(os.path.join(d, 'out', 'solution.rvc')).read()))


def outflow_m3(d):
    """the volume that left the watershed at its outlet and through the irrigation demand [m3] (Cum. Outflow)"""
    return float(csv(d, 'WatershedStorage.csv')['Cum. Outflow [mm]'].iloc[-1]) * 1e-3 * RCFG['nhru'] * RCFG['hru_w'] * RCFG['width']


DAYS10 = 40
g10 = True
for route, reach in (('ROUTE_MUSKINGUM', 300), ('ROUTE_MUSKINGUM_CUNGE', 300), ('ROUTE_STORAGECOEFF', 30), ('ROUTE_HYDROLOGIC', 30),
                     ('ROUTE_DIFFUSIVE_WAVE', 30), ('ROUTE_PLUG_FLOW', 30)):
    for irrigated in (False, True):
        kw = dict(upstream=True, route=route, reach=reach, rain=[0.0] * DAYS10, qin=[0.05] * 5, rbk=200.0, croute='ROUTE_DUMP')
        tag = 'wb10_%s%s' % (route.lower(), '_irr' if irrigated else '')
        d1 = river_case(os.path.join(W, tag + '_river'), DAYS10, irr=(0.003 if irrigated else None), **kw)
        ok1, _ = sz_check.run(d1)
        dl = None
        if ok1 and irrigated:   # (the run without the river is given the irrigation the river run delivered, so both runs withdraw the same)
            dl = list(pd.read_csv(os.path.join(d1, 'out', 'Demands.csv'))['down (total del.) [m3/s]'].iloc[1:])
        d0 = river_case(os.path.join(W, tag + '_noriver'), DAYS10, river=False, irr=dl, **kw)
        ok0, _ = sz_check.run(d0)
        if not (ok1 and ok0):
            g10 = False; print('WB10 %s: a run FAILED' % tag); continue
        b = csv(d1, 'GWBudget.csv'); applied = -float(b['river exchange applied to Raven [m3]'].sum())
        drop = outflow_m3(d0) - outflow_m3(d1); dch = chan_end(d1) - chan_end(d0)
        if irrigated:
            dd = abs(pd.read_csv(os.path.join(d0, 'out', 'Demands.csv'))['down (total del.) [m3/s]'].fillna(0.0).iloc[1:].values - np.array(dl)).max()   # (blank: no demand)
        # the run total 'river take in transit' only for more than 1e-6 m3 (half the last step's takes, :GWRiverTake)
        m = re.search(r':GWRiverTake[^\n]*\n([\s\S]*?):EndGWRiverTake', open(os.path.join(d1, 'out', 'solution.rvc')).read())
        half = 0.5 * sum(float(x) for l in m.group(1).strip().split('\n') for x in l.split(',')[1:3]) if m else 0.0
        mt = re.search(r'river take in transit\s*: (\S+) m3', open(os.path.join(d1, 'out', 'GWModelSummary.txt')).read())
        gt = (mt is not None and abs(float(mt.group(1)) - half) <= 5e-6 * half) if half > 1e-6 else (mt is None)
        g = applied > 1000.0 and abs(drop - applied) <= 0.5 + 1e-5 * applied and abs(dch) <= 1e-5 * applied and (not irrigated or dd <= 1e-12) and gt
        g10 &= g
        print('%-70s %s  (taken %.2f m3; outflow lower by %.2f m3; channel storage %+.2g m3%s; take in transit %.3g m3, run total %s)' % ('WB10 %s%s: outflow lower by the take, channel unchanged'
              % (route, ', irrigated' if irrigated else ''), 'ok' if g else 'FAIL', applied, drop, dch, ('; irrigation equal within %.1g m3/s' % dd) if irrigated else '',
              half, mt.group(1) if mt else 'not given'))
results.append(('WB10', g10))

# WB11: an outflow set from outside the routing (ROUTE_EXTERNAL reaches fed by a live file every step)
QOBS, DAYS11 = 0.02, 12
r11 = {}
for riv in (1, 0):
    d = river_case(os.path.join(W, 'wb11_external_%s' % ('river' if riv else 'noriver')), DAYS11, upstream=True, river=bool(riv), route='ROUTE_EXTERNAL',
                   rain=[0.0] * DAYS11, qin=[0.0] * DAYS11, rbk=200.0, croute='ROUTE_DUMP')
    open(os.path.join(d, 'm.rvi'), 'a').write(':ReadLiveFile\n')
    open(os.path.join(d, 'm.rvl'), 'w').write(':SetStreamflow 1 0.0\n:SetStreamflow 2 %g\n' % QOBS)
    ok, _ = sz_check.run(d)
    r11[riv] = d if ok else None
if None in r11.values():
    results.append(('WB11', False)); print('WB11 FAIL (a run failed)')
else:
    b = csv(r11[1], 'GWBudget.csv'); T = -b['river exchange applied to Raven [m3]'].values          # (all from the outflow: no runoff, no inflow)
    h1, h0 = csv(r11[1], 'Hydrographs.csv')['down [m3/s]'].values[1:], csv(r11[0], 'Hydrographs.csv')['down [m3/s]'].values[1:]
    # the hydrograph is the mean of the outflow at the start of the step (the live file's) and at its end (the delivered one)
    dev = float(np.max(np.abs(2.0 * (h0 - h1) * 86400.0 - T)))
    dch = chan_end(r11[1]) - chan_end(r11[0]); err = open(os.path.join(r11[1], 'out', 'Raven_errors.txt')).read()
    g = T.min() > 100.0 and dev <= 0.01 + 1e-4 * T.max() and abs(dch) <= 1e-6 * T.sum() and 'was set from outside Raven' in err
    results.append(('WB11', g))
    print('%-70s %s  (take %.2f m3/d; delivered outflow lower by the take within %.2g m3; channel storage %+.2g m3; warning %s)' % (
          'WB11 outflow set by a live file (ROUTE_EXTERNAL): the take from it', 'ok' if g else 'FAIL', T.mean(), dev, dch, 'given' if 'was set from outside Raven' in err else 'MISSING'))

# WB12: ensemble members start from the first run's routing state (the local outflow and the irrigation and diversion
# memory with the histories), with the routing methods that keep the local outflow as their state
def no_groundwater(d):
    """the same model without the groundwater model: no :GroundwaterModel, no aquifer tables, HRUs without a profile"""
    sub(os.path.join(d, 'm.rvi'), ':GroundwaterModel MODFLOW6\n', '')
    t = open(os.path.join(d, 'm.rvp')).read()
    for a, b in ((':AquiferClasses', ':EndAquiferClasses'), (':AquiferProfiles', ':EndAquiferProfiles'),
                 (':AquiferProfileParameters', ':EndAquiferProfileParameters')):
        i = t.find(a + '\n'); j = t.find(b, i); assert i >= 0 and j > i, a
        t = t[:i] + t[j + len(b) + 1:]
    open(os.path.join(d, 'm.rvp'), 'w').write(t)
    h = open(os.path.join(d, 'm.rvh')).read().split('\n')
    att = [l for l in h if l.strip().startswith(':Attributes') and 'AQUIFER_PROFILE' in l][0]
    col = [x.strip() for x in att.split(',')].index('AQUIFER_PROFILE')   # (the row's ID takes the place of ':Attributes')
    n = 0
    for i, l in enumerate(h):
        w = [x.strip() for x in l.split(',')]
        if len(w) > col and not w[0].startswith(':') and w[col] == 'AQ':
            w[col] = '[NONE]'; h[i] = '  ' + ', '.join(w); n += 1
    assert n > 0, 'no HRU with the aquifer profile AQ'
    open(os.path.join(d, 'm.rvh'), 'w').write('\n'.join(h))


def ensemble_devs(d, files):
    """runs d as a 2-member Monte Carlo ensemble; returns (largest relative difference of each member's files from the
    single run's, per member), or None when the ensemble failed"""
    e = d + '_ens'; shutil.rmtree(e, ignore_errors=True); shutil.copytree(d, e, ignore=shutil.ignore_patterns('out'))
    open(os.path.join(e, 'm.rvi'), 'a').write('\n:EnsembleMode ENSEMBLE_MONTECARLO 2\n')
    open(os.path.join(e, 'm.rve'), 'w').write(':OutputDirectoryFormat ./ens_*/\n:ParameterDistributions\n  HYDRAUL_COND SOIL SOIL 100 DIST_UNIFORM 100 100\n:EndParameterDistributions\n')
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=e, capture_output=True, text=True, env=tc.ENV)
    if 'Successful' not in r.stdout + r.stderr:
        return None
    devs = []
    for m in (1, 2):
        dv = 0.0
        for f in files:
            A = csv(d, f); B = pd.read_csv(os.path.join(e, 'ens_%d' % m, f)); B.columns = [c.strip() for c in B.columns]
            if f == 'Demands.csv':   # (the demand columns of the first row are the demand objects' last value, written before the
                for c in [c for c in A.columns if 'dem.' in c or '(demand)' in c]:   #  first step computes it: output, not state)
                    B.loc[0, c] = A.loc[0, c]
            dv = max([dv] + [float(tc.max_diff(A[c], B[c], max(float(A[c].abs().max()), 1e-9))) for c in A.columns if pd.api.types.is_numeric_dtype(A[c])])
        devs.append(dv)
    return devs


g12 = True
for route in ('ROUTE_HYDROLOGIC', 'ROUTE_STORAGECOEFF', 'ROUTE_TVD'):
    for gw in (False, True):
        tag = '%s %s' % (route, 'with groundwater' if gw else 'without groundwater')
        d = river_case(os.path.join(W, 'wb12_%s_%s' % (route.lower(), 'gw' if gw else 'nogw')), 12, upstream=True, route=route,
                       croute='ROUTE_DUMP', reach=30.0, rbk=200.0)
        if not gw:
            no_groundwater(d)
        ok, txt = sz_check.run(d)
        if not ok and route == 'ROUTE_TVD':   # (Raven stops TVD routing for some reaches; then there is nothing to compare)
            tc.skip('WB12 ' + tag, 'the single run stops: ' + txt.strip().split('\n')[-1][:100]); continue
        devs = ensemble_devs(d, ('Hydrographs.csv', 'GWBudget.csv') if gw else ('Hydrographs.csv',)) if ok else None
        g = devs is not None and max(devs) <= (1e-12 if gw else 0.0)
        g12 = g12 and g
        print('%-70s %s  (members against the single run: %s)' % ('WB12 %s: each member equals the single run' % tag, 'ok' if g else 'FAIL',
              'a run FAILED' if devs is None else ', '.join('%.1e' % x for x in devs)))
# (an irrigated reach: each demand's delivered flow is memory too; Demands.csv's first row is the start of the run)
d = river_case(os.path.join(W, 'wb12_irrigated'), 12, upstream=True, route='ROUTE_HYDROLOGIC', croute='ROUTE_TRI_CONVOLUTION', reach=30.0, rbk=200.0, irr=0.003)
ok, txt = sz_check.run(d)
devs = ensemble_devs(d, ('Hydrographs.csv', 'GWBudget.csv', 'Demands.csv')) if ok else None
g = devs is not None and max(devs) <= 1e-12
g12 = g12 and g
print('%-70s %s  (members against the single run: %s)' % ('WB12 ROUTE_HYDROLOGIC, irrigated: each member equals the single run, demands too', 'ok' if g else 'FAIL',
      'a run FAILED' if devs is None else ', '.join('%.1e' % x for x in devs)))
results.append(('WB12', g12))

# WB13: a restart with another :TimeStep right after a river loss was taken from the reach's outflow
def leak_m3(d):
    """the river leakage MODFLOW received over the run [m3]"""
    b = csv(d, 'GWBudget.csv'); dt = float(re.search(r':TimeStep\s+(\S+)', open(os.path.join(d, 'm.rvi')).read()).group(1))
    return float(b['river leakage to aquifer [m3/d]'].sum()) * dt


def step_restart(d, days, rday, dt1, dt2):
    """the first rday days with :TimeStep dt1 and the rest, from the first part's solution.rvc, with dt2; returns the parts or None"""
    p1, p2 = d + '_p1', d + '_p2'
    for x in (p1, p2):
        shutil.rmtree(x, ignore_errors=True); shutil.copytree(d, x, ignore=shutil.ignore_patterns('out'))
    sub(os.path.join(p1, 'm.rvi'), ':Duration %d\n:TimeStep 1\n' % days, ':Duration %d\n:TimeStep %g\n' % (rday, dt1))
    sub(os.path.join(p2, 'm.rvi'), ':Duration %d\n:TimeStep 1\n' % days, ':Duration %d\n:TimeStep %g\n' % (days - rday, dt2))
    sub(os.path.join(p2, 'm.rvi'), ':StartDate 2000-01-01', ':StartDate 2000-01-%02d' % (rday + 1))
    if not sz_check.run(p1)[0]:
        return None
    shutil.copy(os.path.join(p1, 'out', 'solution.rvc'), os.path.join(p2, 'm.rvc'))
    return (p1, p2) if sz_check.run(p2)[0] else None


DAYS13 = 30
g13 = True
for route in ('ROUTE_HYDROLOGIC', 'ROUTE_STORAGECOEFF'):
    for dt1, dt2, rday in ((0.5, 1.0, 5), (1.0, 0.25, 5), (0.5, 1.0, 3), (1.0, 0.25, 3)):
        kw = dict(upstream=True, route=route, reach=30.0, rain=[0.0] * DAYS13, qin=[0.05] * 5, rbk=200.0, croute='ROUTE_DUMP')
        tag = 'wb13_%s_%g_%g_%d' % (route.lower(), dt1, dt2, rday)
        parts = [step_restart(river_case(os.path.join(W, tag + ('_river' if riv else '_noriver')), DAYS13, river=riv, **kw), DAYS13, rday, dt1, dt2)
                 for riv in (True, False)]
        if None in parts:
            g13 = False; print('WB13 %s: a run FAILED' % tag); continue
        (r1, r2), (n1, n2) = parts
        take = re.search(r':GWRiverTake[^\n]*\n\s*2, ([^,\s]+), ([^,\s]+)', open(os.path.join(r1, 'out', 'solution.rvc')).read())
        leak = leak_m3(r1) + leak_m3(r2) - float(csv(r2, 'GWBudget.csv')['river loss carried to next step [m3]'].iloc[-1])
        drop = outflow_m3(n1) + outflow_m3(n2) - outflow_m3(r1) - outflow_m3(r2)
        dch = chan_end(r2) - chan_end(n2)
        mb = max(float(csv(x, 'WatershedStorage.csv')['MB Error [mm]'].abs().max()) for x in (r1, r2, n1, n2))
        g = take is not None and float(take.group(1)) + float(take.group(2)) > 100.0 and leak > 1000.0 and abs(drop - leak) <= 0.5 + 1e-5 * leak and abs(dch) <= 1e-5 * leak and mb <= LIM
        g13 &= g
        print('%-70s %s  (last take from the inflow %s, from the outflow %s m3; leakage %.2f m3; outflow lower by %.2f m3; channel storage %+.2g m3; MB %.2g mm)' % (
              'WB13 %s, :TimeStep %g then %g from day %d: outflow lower by the leakage' % (route, dt1, dt2, rday + 1), 'ok' if g else 'FAIL',
              take.group(1)[:8] if take else '-', take.group(2)[:8] if take else '-', leak, drop, dch, mb))
results.append(('WB13', g13))

# WB14: a restart with a longer :TimeStep right after takes from the reach's inflow, with a routing method whose inflow
# history Raven averages to the longer step (ROUTE_DIFFUSIVE_WAVE)
def run_with(exe, d):
    r = subprocess.run([exe, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV)
    return 'Successful Simulation' in r.stdout + r.stderr


def chain_restart(d, days, parts, first_exe=None):
    """runs d in parts [(days, :TimeStep)], each from the last part's solution.rvc (the first part with first_exe if
    given); returns the part folders or None"""
    out, t0, prev = [], 0.0, None
    for i, (n, dt) in enumerate(parts):
        p = d + '_p%d' % (i + 1); shutil.rmtree(p, ignore_errors=True); shutil.copytree(d, p, ignore=shutil.ignore_patterns('out'))
        start = datetime.datetime(2000, 1, 1) + datetime.timedelta(days=t0)
        sub(os.path.join(p, 'm.rvi'), ':StartDate 2000-01-01 00:00:00\n:Duration %d\n:TimeStep 1\n' % days,
            ':StartDate %s\n:Duration %g\n:TimeStep %g\n' % (start.strftime('%Y-%m-%d %H:%M:%S'), n, dt))
        if prev:
            shutil.copy(os.path.join(prev, 'out', 'solution.rvc'), os.path.join(p, 'm.rvc'))
        if not ((first_exe and i == 0 and run_with(first_exe, p)) or ((not first_exe or i > 0) and sz_check.run(p)[0])):
            return None
        out.append(p); prev = p; t0 += n
    return out


g14 = True
def mb_dev(R, N):
    """largest |MB error| of the river runs beyond the same runs' without the river (step by step), and the largest of the
    runs without the river (Raven's own: CSubBasin::SetQinHist reads past the end of the history when a step grows)"""
    dv = mn = 0.0
    for r, n in zip(R, N):
        a, b = csv(r, 'WatershedStorage.csv')['MB Error [mm]'].astype(float), csv(n, 'WatershedStorage.csv')['MB Error [mm]'].astype(float)
        dv = max(dv, float((a - b).abs().max()) if len(a) == len(b) else float('inf')); mn = max(mn, float(b.abs().max()))
    return dv, mn


for parts in (((3, 0.5), (27, 1.0)), ((3, 0.25), (27, 1.0)), ((3, 0.25), (0.5, 0.5), (26.5, 1.0)),
              ((4, 0.1), (0.2, 0.2), (25.8, 1.0)), ((4, 1.0), (0.2, 0.2), (25.8, 1.0))):
    kw = dict(upstream=True, route='ROUTE_DIFFUSIVE_WAVE', reach=30.0, rain=[0.0] * DAYS13, qin=[0.05] * 5, rbk=200.0, croute='ROUTE_DUMP')
    tag = 'wb14_' + '_'.join('%g' % dt for _, dt in parts)
    runs = [chain_restart(river_case(os.path.join(W, tag + ('_river' if riv else '_noriver')), DAYS13, river=riv, **kw), DAYS13, parts)
            for riv in (True, False)]
    label = 'WB14 ROUTE_DIFFUSIVE_WAVE, :TimeStep %s: the takes leave the books exactly' % ' then '.join('%g' % dt for _, dt in parts)
    if None in runs:
        g14 = False; print('%-70s FAIL  (a run FAILED)' % label); continue
    R, N = runs
    sol = open(os.path.join(R[-2], 'out', 'solution.rvc')).read()
    take = re.search(r':GWRiverTake[^\n]*\n\s*2, ([^,\s]+), ([^,\s]+)', sol)
    leak = sum(leak_m3(x) for x in R) - float(csv(R[-1], 'GWBudget.csv')['river loss carried to next step [m3]'].iloc[-1])
    drop = sum(outflow_m3(x) for x in N) - sum(outflow_m3(x) for x in R)
    dch = chan_end(R[-1]) - chan_end(N[-1])
    mb, mbn = mb_dev(R, N)
    # (the restart re-routes the averaged inflow history, so the take still in the channel at the end differs from a
    # continuous run's: the leakage is the lower outflow plus the lower channel storage)
    g = take is not None and float(take.group(1)) > 10.0 and leak > 1000.0 and abs(drop - dch - leak) <= 0.5 + 1e-5 * leak and mb <= LIM
    g14 &= g
    print('%-70s %s  (last take from the inflow %s m3; leakage %.2f m3; outflow lower by %.2f m3, channel storage %+.2f m3; MB beyond the run without the river %.2g mm (its own %.2g))' % (
          label, 'ok' if g else 'FAIL', take.group(1)[:8] if take else '-', leak, drop, dch, mb, mbn))
# a restart from a solution.rvc written by the reference build (no :GWRiverInflowTakes): the earlier takes are taken as equal
# to the last one, so the restart is no worse than the reference build's own restart from that file
if tc.REF:
    kw = dict(upstream=True, route='ROUTE_DIFFUSIVE_WAVE', reach=30.0, rain=[0.0] * DAYS13, qin=[0.05] * 5, rbk=200.0, croute='ROUTE_DUMP')
    R = chain_restart(river_case(os.path.join(W, 'wb14_oldfile'), DAYS13, **kw), DAYS13, ((3, 0.5), (27, 1.0)), first_exe=tc.REF)
    mbn = mbr = float('nan')
    g = R is not None and ':GWRiverInflowTakes' not in open(os.path.join(R[0], 'out', 'solution.rvc')).read()
    if g:
        p2r = R[1] + '_ref'; shutil.rmtree(p2r, ignore_errors=True); shutil.copytree(R[1], p2r, ignore=shutil.ignore_patterns('out'))
        g = run_with(tc.REF, p2r)
    if g:
        mbn, mbr = (float(csv(x, 'WatershedStorage.csv')['MB Error [mm]'].abs().max()) for x in (R[1], p2r))
        g = mbn <= mbr + 1e-9
    g14 &= g
    print('%-70s %s  (%s)' % ('WB14 restart from a reference-build solution.rvc (:TimeStep 0.5 then 1)', 'ok' if g else 'FAIL',
          'MB this build %.4g mm, reference build %.4g mm' % (mbn, mbr) if R is not None else 'a run FAILED'))
else:
    tc.skip('WB14 restart from a reference-build solution.rvc')
results.append(('WB14', g14))

n = sum(1 for _, g in results if g)
print('watershed balance: %s (%d of %d)' % ('ALL PASSED' if n == len(results) else 'FAILED', n, len(results)))
sys.exit(0 if n == len(results) else 1)
