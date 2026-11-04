""":WriteGWBudgetFile: MODFLOW's budget file, porosity and offline particle tracking (tools/make_prt.py), on the Liard example
with one pumping well.

Checks:
  B1  the run writes mf6/gwf.cbc and mf6/gwf.porosity; FloPy reads the budget file; it holds FLOW-JA-FACE, DATA-SPDIS,
      DATA-SAT and the flows of every package at every saved step
  B2  per package and saved step, the budget file's totals equal GWBudget.csv (RCH_RAVEN, DRN_RAVEN, RIV_RAVEN, WEL_RAVEN,
      storage) within 1e-6
  B3  gwf.porosity holds, in every active cell, the POROSITY of the aquifer class of that cell (classes told apart by K)
  B4  the same run without the option: the solution is the same (GWBudget.csv, heads identical) and the option changes
      only gwf.nam, gwf.npf and gwf.oc of the mf6 folder (and adds gwf.cbc, gwf.porosity); with RAVEN_EXE_REF the run
      without the option is identical to the reference build (outputs and mf6 folder)
  B5  make_prt.py builds a PRT simulation (8 particles around the well) and runs it through the MODFLOW 6 library,
      forward and backward: every particle is tracked and moves (travel times > 0), and each backward track runs against
      its forward track
  B6  :WriteGWBudgetFile with an existing model stops (the model keeps its own output control)
Quick mode (RAVEN_TEST_QUICK=1): 10 days; full mode 60 days.
Usage: python3 budget_file.py     (prints 'budget file checks: ALL PASSED')"""
import os, sys, re, json, shutil, subprocess, filecmp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testconfig as tc
import numpy as np, pandas as pd
import flopy
from shapely.geometry import shape

tc.need_mf6()
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 10 if QUICK else 60
ok_all = True


def check(name, ok, info=''):
    global ok_all
    ok_all &= bool(ok)
    print('  %-66s %s %s' % (name, 'ok' if ok else 'FAIL', info), flush=True)


def setup(d, option=True):
    tc.copy_case(tc.LIARD, d, duration=DAYS)
    rvh = open(d + '/Liard.rvh').read()
    hdr = [l for l in rvh.split('\n') if ':Attributes' in l and 'AQUIFER_PROFILE' in l][0].replace(',', ' ').split()[1:]
    ib, ia, ie, iar = (hdr.index(k) + 1 for k in ('BASIN_ID', 'AQUIFER_PROFILE', 'ELEVATION', 'AREA'))
    rows = [l.replace(',', ' ').split() for l in rvh.split(':HRUs')[1].split(':EndHRUs')[0].split('\n')]
    cand = sorted([r for r in rows if r and r[0].isdigit() and r[ib] == '52' and r[ia] != '[NONE]'], key=lambda r: -float(r[iar]))
    wid, wel = int(cand[0][0]), float(cand[0][ie])
    geo = [f for f in json.load(open(d + '/Liard_HRUs_standin.geojson'))['features'] if int(f['properties']['HRU_ID']) == wid][0]
    pt = shape(geo['geometry']).representative_point()
    g = open(d + '/Liard.rvg').read()
    g = re.sub(r':HeadSaveFrequency\s+\S+', ':HeadSaveFrequency  1', g)
    g += '\n:Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n  1, PW_1, %.5f, %.5f, %.1f, %.1f\n:EndWells\n' % (pt.y, pt.x, wel - 5, wel - 25)
    if option:
        g += ':WriteGWBudgetFile\n'
    open(d + '/Liard.rvg', 'w').write(g)
    n = DAYS + 2
    open(d + '/Liard.rvt', 'a').write('\n:WellFlowRate 1 m3/d\n  1985-10-01 00:00:00 1.0 %d\n' % n + '  -20000.0\n' * n + ':EndWellFlowRate\n')
    return d


W = os.path.dirname(tc.work('budget_file', 'x'))
a = setup(W + '/with'); m = tc.run(a)
print('B1 run with :WriteGWBudgetFile, %d days: %s' % (DAYS, m))
check('B1 run', 'Successful' in m, m[:100])
cbf = a + '/out/mf6/gwf.cbc'
check('B1 gwf.cbc and gwf.porosity written', os.path.exists(cbf) and os.path.exists(a + '/out/mf6/gwf.porosity'))
b = pd.read_csv(a + '/out/GWBudget.csv').rename(columns=lambda c: c.strip()).dropna(subset=['Raven recharge [m3/d]'])
if os.path.exists(cbf):
    cb = flopy.utils.CellBudgetFile(cbf, precision='double')
    names = set(x.decode().strip() for x in cb.get_unique_record_names())
    pk2 = set(h['paknam2'].decode().strip().upper() for h in cb.recordarray)
    times = cb.get_times()
    need = {'FLOW-JA-FACE', 'DATA-SPDIS', 'DATA-SAT', 'STO-SS', 'STO-SY'}
    check('B1 FLOW-JA-FACE, DATA-SPDIS, DATA-SAT, STO-SS, STO-SY present', need <= names, ', '.join(sorted(names)))
    check('B1 RCH_RAVEN, DRN_RAVEN, RIV_RAVEN, WEL_RAVEN present', {'RCH_RAVEN', 'DRN_RAVEN', 'RIV_RAVEN', 'WEL_RAVEN'} <= pk2, ', '.join(sorted(pk2)))
    check('B1 flows saved every step', len(times) == DAYS, '%d saved times' % len(times))
    # B2 package totals against GWBudget.csv
    ours = {'RCH_RAVEN': lambda r: r['MF6 recharge [m3/d]'], 'DRN_RAVEN': lambda r: -r['seepage to Raven [m3/d]'],
            'RIV_RAVEN': lambda r: r['river leakage to aquifer [m3/d]'] - r['aquifer discharge to rivers [m3/d]'], 'WEL_RAVEN': lambda r: r['wells actual [m3/d]']}
    worst = {k: 0.0 for k in list(ours) + ['STORAGE']}; n = 0
    for idx, h in enumerate(cb.recordarray):
        t = h['totim']; row = b[(b['time [d]'] - t).abs() < 1e-6]
        if row.empty:
            continue
        nm = h['text'].decode().strip(); pk = h['paknam2'].decode().strip().upper()
        if pk in ours:
            q = cb.get_record(idx)['q'].sum(); o = ours[pk](row).iloc[0]
            worst[pk] = max(worst[pk], abs(q - o) / max(abs(o), 1.0)); n += 1
    for t in times:
        row = b[(b['time [d]'] - t).abs() < 1e-6]
        s = sum(cb.get_data(text=x, totim=t)[0].sum() for x in ('STO-SS', 'STO-SY'))   # + : release from storage into the cells
        o = row['storage release [m3/d]'].iloc[0]; worst['STORAGE'] = max(worst['STORAGE'], abs(s - o) / max(abs(o), 1.0))
    for k, v in worst.items():
        check('B2 budget file %s = GWBudget.csv' % k, v < 1e-6, '%.1e' % v)
# B3 porosity
P = flopy.mf6.MFSimulation.load(sim_ws=a + '/out/mf6', verbosity_level=0, load_only=['dis', 'npf']).get_model()
K = np.array(P.npf.k.array).ravel(); idom = np.array(P.dis.idomain.array).ravel()
txt = open(a + '/out/mf6/gwf.porosity').read()
vals = []
for blk in re.findall(r'INTERNAL[^\n]*\n(.*?)(?=\n\s*(?:INTERNAL|CONSTANT|END|POROSITY|LAYERED|$))', txt, flags=re.S):
    vals += [float(x) for x in blk.split()]
por = np.array(vals)
cls = {50.0: 0.30, 0.001: 0.40, 10.0: 0.35, 0.2: 0.30}   # K_HORIZ -> POROSITY of the example's aquifer classes
exp = np.array([cls.get(round(k, 6), np.nan) for k in K])
act = idom > 0
okp = (len(por) == len(K)) and np.all(np.abs(por[act] - exp[act]) < 1e-12)
check('B3 gwf.porosity = POROSITY of each active cell\'s class', okp, '%d values, %d active cells' % (len(por), int(act.sum())))
# B4 without the option
c = setup(W + '/without', option=False); m2 = tc.run(c)
check('B4 run without the option', 'Successful' in m2, m2[:100])
same = filecmp.cmp(a + '/out/GWBudget.csv', c + '/out/GWBudget.csv', shallow=False) and filecmp.cmp(a + '/out/mf6/gwf.hds', c + '/out/mf6/gwf.hds', shallow=False)
check('B4 the same solution (GWBudget.csv, gwf.hds identical)', same)
fa, fc = set(os.listdir(a + '/out/mf6')), set(os.listdir(c + '/out/mf6'))
skip = lambda f: f.endswith('.lst') or f.endswith('.cache') or f == 'mfsim.stdout'
changed = sorted(f for f in fa & fc if not skip(f) and not filecmp.cmp(a + '/out/mf6/' + f, c + '/out/mf6/' + f, shallow=False))
check('B4 the option changes only gwf.nam, gwf.npf, gwf.oc', changed == ['gwf.nam', 'gwf.npf', 'gwf.oc'], ', '.join(changed))
check('B4 the option adds only gwf.cbc and gwf.porosity', sorted(fa - fc) == ['gwf.cbc', 'gwf.porosity'] and not (fc - fa), ', '.join(sorted(fa - fc)))
if tc.REF:
    r = setup(W + '/ref', option=False); env = dict(tc.ENV)
    rr = subprocess.run([tc.REF, 'Liard', '-o', 'out/'], cwd=r, capture_output=True, text=True, env=env)
    diffs = []
    for sub in ('out', 'out/mf6'):
        for f in sorted(os.listdir(r + '/' + sub)):
            p, q = c + '/' + sub + '/' + f, r + '/' + sub + '/' + f
            if os.path.isdir(q) or skip(f) or f in ('Raven_errors.txt', 'GWModelSummary.txt'):
                continue
            if not os.path.exists(p) or not filecmp.cmp(p, q, shallow=False): diffs.append(sub + '/' + f)
    flt = lambda f, base: [l.replace(base, 'X') for l in open(f, errors='replace') if not re.search(r'Build date|BuildDate|HRU/grid linkage|time|library|Version', l, re.I)]
    for f in ('Raven_errors.txt', 'GWModelSummary.txt'):
        if flt(c + '/out/' + f, c) != flt(r + '/out/' + f, r): diffs.append(f)
    check('B4 without the option identical to the reference build', 'Successful' in rr.stdout + rr.stderr and not diffs, ', '.join(diffs))
    shutil.rmtree(r, ignore_errors=True)
else:
    tc.skip('B4 run without the option against the reference build')
shutil.rmtree(c, ignore_errors=True)
# B5 particle tracking
MP = os.path.join(tc.REPO, 'tools', 'make_prt.py')
disp = {}
for mode in ('forward', 'backward'):
    shutil.rmtree(a + '/out/prt', ignore_errors=True)
    r = subprocess.run([sys.executable, MP, a + '/out', '--run', tc.MF6LIB] + (['--backward'] if mode == 'backward' else []), capture_output=True, text=True, timeout=1800)
    ep = a + '/out/prt/endpoints.csv'
    okr = r.returncode == 0 and os.path.exists(ep)
    check('B5 make_prt.py %s: PRT run through the library' % mode, okr, (r.stdout + r.stderr).strip().split('\n')[-1][:160])
    if not okr: print(r.stdout + r.stderr)
    if okr:
        E = pd.read_csv(ep)
        dist = np.hypot(E['x1'] - E['x0'], E['y1'] - E['y0']) + np.abs(E['z1'] - E['z0'])
        check('B5 %s: 8 particles tracked, all moved, travel times > 0' % mode, len(E) == 8 and (E['travel_time_d'] > 0).all() and (dist > 0).all(),
              'travel times %.3g-%.3g d, distances %.3g-%.3g m' % (E['travel_time_d'].min(), E['travel_time_d'].max(), dist.min(), dist.max()))
        disp[mode] = np.stack([E['x1'] - E['x0'], E['y1'] - E['y0']], axis=1)
if len(disp) == 2:   # backward tracking reverses the flow field: each particle moves the other way
    dot = (disp['forward'] * disp['backward']).sum(axis=1)
    check('B5 backward tracks run against the forward ones (8 particles)', (dot < 0).all(), 'cosines %.3f to %.3f' % tuple(
        (dot / np.maximum(np.hypot(*disp['forward'].T) * np.hypot(*disp['backward'].T), 1e-30))[[0, -1]]))
# B6 existing model
if not os.path.exists(W + '/Liard_groundwater'): os.symlink(tc.LIARD, W + '/Liard_groundwater')   # (the example reads ../Liard_groundwater/data_forcing)
e = tc.copy_case(tc.EXISTING, W + '/existing', duration=2)
open(e + '/Liard.rvg', 'a').write('\n:WriteGWBudgetFile\n')
m3 = tc.run(e)
check('B6 existing model: :WriteGWBudgetFile stops', ':WriteGWBudgetFile' in m3 and 'existing model' in m3, m3[:140])
shutil.rmtree(e, ignore_errors=True)
if ok_all: shutil.rmtree(W + '/with', ignore_errors=True)
print('budget file checks: %s' % ('ALL PASSED' if ok_all else 'FAILED'))
