"""Input forms of existing models on later starts: TDIS period data in an OPEN/CLOSE file, and a well package driven by a
time series (TS6) on a restart. On the synthetic Liard model of make_ext_model.py (metres/days, linked through :MF6CRS).

  tdis_openclose  the model's TDIS period rows moved to an OPEN/CLOSE file: a run starting 34 days after the model's time
                  zero (stress periods dropped and renumbered) gives the same working-copy TDIS and the same GWBudget.csv,
                  byte for byte, as the model with its rows inline
  ts6_restart     the wells' rates given by a TS6 time series (linear interpolation between half-monthly values): a
                  continuous run against a run restarted from solution.rvc between two entries of the series (the
                  restart shifts the series' times, keeping the earlier ones as negative times); the well flows change
                  over time and the restarted run follows the continuous one
  mvr_openclose   a water mover (wells to a lake) whose period rows sit in an OPEN/CLOSE file and include a mover from a
                  package Raven takes over: the rows are written into the working copy without that mover, and the run
                  equals the one with the rows inline, byte for byte, with exact accounts
  tas6_refused    a time-array series (TAS6) still stops a later start
Quick mode (RAVEN_TEST_QUICK=1): 50 days, restart at day 23; full mode 120 days, restart at day 53.
Usage: python3 ext_inputs.py     (prints 'existing-model input forms: ALL PASSED')"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import testconfig as tc
import shutil, subprocess, re, datetime, filecmp, math
import pandas as pd

tc.need_mf6(); X = tc.ext_models(); ENV = tc.ENV
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS, SPLIT = (50, 23) if QUICK else (120, 53)
W = os.path.dirname(tc.work('ext_inputs', 'x'))
ok_all = True


def check(name, ok, info=''):
    global ok_all
    ok_all &= bool(ok)
    print('  %-66s %s %s' % (name, 'ok' if ok else 'FAIL', info), flush=True)


def model(name, edit):
    md = W + '/m_' + name
    shutil.rmtree(md, ignore_errors=True); shutil.copytree(X + '/md', md); edit(md)
    return md


def run(d, md, start, days, rvc=None):
    subprocess.run([sys.executable, tc.SETUP_EXT, d, md], capture_output=True, check=True)
    t = open(d + '/Liard.rvi').read()
    t = re.sub(r':StartDate\s+\S+\s+\S+', ':StartDate %s 00:00:00' % start, t); t = re.sub(r':Duration\s+\S+', ':Duration %d' % days, t)
    open(d + '/Liard.rvi', 'w').write(t)
    g = open(d + '/Liard.rvg').read(); open(d + '/Liard.rvg', 'w').write(re.sub(r':MF6GridFile.*', ':MF6CRS            EPSG:32610', g))
    if rvc:
        shutil.copy(rvc, d + '/Liard.rvc')
    r = subprocess.run([tc.RAVEN, 'Liard', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=ENV, timeout=3600)
    return (re.findall(r'Exiting Gracefully: (.*)', r.stdout + r.stderr) or ['(no exit message; rc %d)' % r.returncode])[-1]


def budget(d):
    return pd.read_csv(d + '/out/GWBudget.csv').rename(columns=lambda c: c.strip()).dropna(subset=['Raven recharge [m3/d]']).reset_index(drop=True)


day = lambda k: (datetime.date(1985, 10, 1) + datetime.timedelta(days=k)).isoformat()

# ---- TDIS period data in an OPEN/CLOSE file
print('tdis_openclose: start 34 days after the model\'s time zero, 20 days', flush=True)
def tdis_oc(md):
    t = open(md + '/ext.tdis').read()
    i = t.lower().find('begin perioddata'); j = t.lower().find('end perioddata')
    body = t[t.find('\n', i) + 1:j]
    open(md + '/tdis_periods.txt', 'w').write('# period length, steps, multiplier\n' + body)
    open(md + '/ext.tdis', 'w').write(t[:t.find('\n', i) + 1] + '  OPEN/CLOSE  tdis_periods.txt\n' + t[j:])
m_oc = model('tdis_oc', tdis_oc)
a, b = W + '/oc_inline', W + '/oc_file'
ra = run(a, X + '/md', day(34), 20); rb = run(b, m_oc, day(34), 20)
check('both runs', 'Successful' in ra and 'Successful' in rb, (ra + ' / ' + rb)[:120])
if 'Successful' in ra and 'Successful' in rb:
    check('working-copy TDIS identical', filecmp.cmp(a + '/out/mf6/ext.tdis', b + '/out/mf6/ext.tdis', shallow=False))
    check('GWBudget.csv identical', filecmp.cmp(a + '/out/GWBudget.csv', b + '/out/GWBudget.csv', shallow=False))
for x in (a, b, m_oc): shutil.rmtree(x, ignore_errors=True)

# ---- water mover whose period data sit in an OPEN/CLOSE file and name a package Raven takes over
print('mvr_openclose: WEL_PUMPS -> lake (LAK6) by the mover, plus a mover row from RCH_MODEL (taken over), 20 days', flush=True)
def mvr(md, external):
    import flopy
    dis = flopy.mf6.MFSimulation.load(sim_ws=md, verbosity_level=0, load_only=['dis']).get_model().dis
    w = open(md + '/gwf_liard.wel').read()
    r, c = [int(x) for x in re.findall(r'BEGIN period\s+1\s*\n(.*?)END period', w, flags=re.S | re.I)[0].split()[1:3]]
    top = float(dis.top.array[r - 1, c - 1])
    open(md + '/gwf_liard.wel', 'w').write(w.replace('BEGIN options\n', 'BEGIN options\n  MOVER\n', 1))
    open(md + '/gwf.lak', 'w').write('BEGIN OPTIONS\n  MOVER\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NLAKES 1\n  NOUTLETS 0\nEND DIMENSIONS\n\n'
                                     'BEGIN PACKAGEDATA\n  1 %.3f 1\nEND PACKAGEDATA\n\nBEGIN CONNECTIONDATA\n  1 1 1 %d %d VERTICAL 0.001 0.0 0.0 0.0 0.0\nEND CONNECTIONDATA\n\n'
                                     'BEGIN PERIOD 1\n  1 STATUS ACTIVE\nEND PERIOD\n' % (top + 0.5, r, c))
    rows = '  WEL_PUMPS 1 LAK_1 1 FACTOR 0.5\n  RCH_MODEL 1 LAK_1 1 FACTOR 1.0\n'
    if external:
        open(md + '/mvr_period1.txt', 'w').write(rows); rows = '  OPEN/CLOSE  mvr_period1.txt\n'
    open(md + '/gwf.mvr', 'w').write('BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  MAXMVR 2\n  MAXPACKAGES 3\nEND DIMENSIONS\n\n'
                                     'BEGIN PACKAGES\n  WEL_PUMPS\n  LAK_1\n  RCH_MODEL\nEND PACKAGES\n\nBEGIN PERIOD 1\n' + rows + 'END PERIOD\n')
    n = open(md + '/gwf_liard.nam').read()
    open(md + '/gwf_liard.nam', 'w').write(n.replace('  OC6  gwf_liard.oc  oc\n', '  OC6  gwf_liard.oc  oc\n  LAK6  gwf.lak  LAK_1\n  MVR6  gwf.mvr  MVR\n'))
m_in = model('mvr_inline', lambda md: mvr(md, False)); m_ex = model('mvr_file', lambda md: mvr(md, True))
a, b = W + '/mvr_inline', W + '/mvr_file'
ra = run(a, m_in, day(0), 20); rb = run(b, m_ex, day(0), 20)
check('both runs', 'Successful' in ra and 'Successful' in rb, (ra + ' / ' + rb)[:150])
if 'Successful' in ra and 'Successful' in rb:
    wc = open(b + '/out/mf6/gwf.mvr').read()
    check('working copy: the OPEN/CLOSE rows inline, the taken-over mover removed', 'WEL_PUMPS 1 LAK_1 1' in wc and 'RCH_MODEL 1' not in wc.split('BEGIN PERIOD')[1],
          '%d movers removed' % (1 if 'movers from or to' in open(b + '/out/GWModelSummary.txt').read() else 0))
    check('GWBudget.csv identical to the inline mover', filecmp.cmp(a + '/out/GWBudget.csv', b + '/out/GWBudget.csv', shallow=False))
    A = tc.audit.audit(b + '/out'); mv = budget(b)['other model packages [m3/d]']
    check('identities with the mover and the lake', abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']) < 1e-9 and abs(A['MF6 cumulative residual / gross flow']) < 1e-7 and A['unconverged steps'] == 0,
          '%.1e %.1e %d' % (A['recharge: (Raven - MF6 - dStore - toCHD)/Raven'], A['MF6 cumulative residual / gross flow'], A['unconverged steps']))
for x in (a, b, m_in, m_ex): shutil.rmtree(x, ignore_errors=True)

# ---- wells driven by a TS6 time series, restarted between two of its entries
print('ts6_restart: %d days, restart at day %d' % (DAYS, SPLIT), flush=True)
def ts6(md):
    t = open(md + '/gwf_liard.wel').read()
    cells = re.findall(r'BEGIN period\s+1\s*\n(.*?)END period', t, flags=re.S | re.I)[0].strip().split('\n')
    cells = [' '.join(c.split()[:3]) for c in cells]
    head = t[:re.search(r'BEGIN period', t, flags=re.I).start()].replace('BEGIN options\n', 'BEGIN options\n  TS6  FILEIN  wel.ts\n')
    open(md + '/gwf_liard.wel', 'w').write(head + 'BEGIN period  1\n' + ''.join('  %s  q%d\n' % (c, k + 1) for k, c in enumerate(cells)) + 'END period  1\n')
    rows = ''.join('  %.2f  %.3f  %.3f\n' % (15.25 * k, -6000 - 4000 * math.sin(k / 3.0), -2000 - 1500 * math.cos(k / 2.0)) for k in range(55))
    open(md + '/wel.ts', 'w').write('BEGIN ATTRIBUTES\n  NAMES q1 q2\n  METHODS LINEAR LINEAR\nEND ATTRIBUTES\n\nBEGIN TIMESERIES\n' + rows + 'END TIMESERIES\n')
m_ts = model('ts6', ts6)
c, r1, r2 = W + '/ts_cont', W + '/ts_a', W + '/ts_b'
rc = run(c, m_ts, day(0), DAYS); check('continuous run', 'Successful' in rc, rc[:120])
r = run(r1, m_ts, day(0), SPLIT); check('first part', 'Successful' in r, r[:120])
r = run(r2, m_ts, day(SPLIT), DAYS - SPLIT, rvc=r1 + '/out/solution.rvc') if 'Successful' in r else 'not run'
check('restarted part (time series shifted, not refused)', 'Successful' in r, r[:150])
if 'Successful' in rc and 'Successful' in r:
    ts = open(r2 + '/out/mf6/wel.ts').read()
    times = [float(l.split()[0]) for l in ts.split('BEGIN TIMESERIES')[1].split('END TIMESERIES')[0].strip().split('\n')]
    check('working-copy series shifted by %d d, earlier times negative' % SPLIT, abs(times[0] + SPLIT) < 1e-9 and abs(times[1] - (15.25 - SPLIT)) < 1e-9, '%s ...' % times[:3])
    check('summary reports the shifted series', 'TS6 files shifted' in open(r2 + '/out/GWModelSummary.txt').read())
    C, B = budget(c), budget(r2); m = C.merge(B, on='date', suffixes=('_c', '_r'))
    w = C['other model packages [m3/d]']
    check('well flows follow the series (change over the run)', w.max() - w.min() > 1000, 'range %.0f m3/d' % (w.max() - w.min()))
    cols = ['seepage to Raven [m3/d]', 'storage release [m3/d]', 'MF6 recharge [m3/d]', 'other model packages [m3/d]', 'aquifer discharge to rivers [m3/d]']
    dev = max(((m[x + '_c'] - m[x + '_r']).abs() / (m[x + '_c'].abs().max() + 1e3)).max() for x in cols)
    check('restarted run = continuous run (%d days)' % len(m), len(m) == DAYS - SPLIT and dev < 1e-4, 'max deviation %.1e' % dev)
    A = tc.audit.audit(r2 + '/out')
    check('restarted run: recharge identity, residual', abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']) < 1e-9 and abs(A['MF6 cumulative residual / gross flow']) < 1e-7,
          '%.1e %.1e' % (A['recharge: (Raven - MF6 - dStore - toCHD)/Raven'], A['MF6 cumulative residual / gross flow']))
for x in (c, r1, r2): shutil.rmtree(x, ignore_errors=True)

# ---- TAS6 still refused on a later start
print('tas6_refused', flush=True)
def tas6(md):
    t = open(md + '/gwf_liard.ghb').read(); open(md + '/gwf_liard.ghb', 'w').write(re.sub(r'(BEGIN options\s*\n)', r'\1  TAS6  FILEIN  ghb.tas\n', t, count=1, flags=re.I))
m_tas = model('tas6', tas6)
d = W + '/tas'; r = run(d, m_tas, day(34), 2)
check('later start with TAS6 stops', 'TAS6' in r and ':MF6StartDate' in r, r[:150])
for x in (d, m_tas, m_ts): shutil.rmtree(x, ignore_errors=True)
print('existing-model input forms: %s' % ('ALL PASSED' if ok_all else 'FAILED'))
