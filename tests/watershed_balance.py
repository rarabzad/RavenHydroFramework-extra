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

Usage: python3 watershed_balance.py   (needs RAVEN_MF6_LIB; seconds)
"""
import os, sys, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'soilzone')); sys.path.insert(0, HERE)
import testconfig as tc
import sz_models, sz_check
import pandas as pd

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

n = sum(1 for _, g in results if g)
print('watershed balance: %s (%d of %d)' % ('ALL PASSED' if n == len(results) else 'FAILED', n, len(results)))
sys.exit(0 if n == len(results) else 1)
