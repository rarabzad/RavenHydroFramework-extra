"""Strict reading of the groundwater inputs: numbers in the .rvg file, the units of :WellFlowRate and :BoundaryHead series,
and the package names Raven reserves in an existing model.

    python3 input_checks.py

Numbers in the .rvg file (generated Liard model; each faulty case must stop before any grid is built, naming the command
and the token):
  N1 ":GridCellSize 2,000.0" (the comma splits it into 2 and 000.0) stops: "surplus value '000.0'";
  N2 ":GridCellSize 2km" stops: "'2km' is not a number";
  N3 ":GridCellSize 2" (a plain number, 2 m cells) stops before the grid is allocated: ":GridCellSize 2 m gives about ...
     cells per layer";
  N4 ":GridRefinement RIVERS 5" on the regular grid stops before the grid is allocated: "the :GridRefinement sizes give a
     regular grid of about ...";
  N5 ":GridRefinement RIVERS 1,000" stops: "surplus value '000'";
  N6 a boundary "HEAD H1146" and N7 "HEAD 1146.85m" stop: "'H1146' is not a number" / "'1146.85m' is not a number";
  N8 a boundary "HEAD 1,146.85" stops (the values after the file are not keyword-value pairs);
  N9 ":SolverMaxOuterIterations 50.5" stops: "is not a whole number";
  N10 a :Wells row with LATITUDE "59.2x" stops: ":Wells ... '59.2x' is not a number".
Grid size (one limit, 5 million cells per layer, checked before the grid is built and again after):
  N11 ":GridCellSize 60" (about 5.1 million cells per layer) and N12 ":GridCellSize 50" (7.3 million) stop before the
      grid is built: ":GridCellSize 50 m gives about 7.32e+06 cells per layer ..., more than 5e+06";
  N13 ":GridType QUADTREE" with ":GridRefinement RIVERS 0.1" (0.1 m meant as 100 m: 15 levels) stops before the grid is
      built: "the :GridRefinement sizes (smallest 0.1 m, 15 levels ...) give a quadtree grid of more than 1e+07 cells per
      layer (estimated)" (the estimate refuses a grid only beyond 1.5 times the limit; the build stops at the limit);
  N14 ":GridType QUADTREE" with ":GridRefinement RIVERS 0.5" (12 levels, about 4.6 million cells per layer, more than
      3 GB) stops with a message naming :GridRefinement and the estimated cells per layer, not a crash (std::bad_alloc);
  N15 200 copies of one line (:GridRefinement LINES 0.1 on the 4-HRU strip of sz_models) and N16 20 adjacent squares of 30 m
      (POLYGONS 0.5) are built (N15: about 47,000 cells per layer, as one line): the estimate counts each square once,
      however many features touch it.
  Each case runs under a 3 GB address-space limit and a 120 s time limit, so a build that tries to allocate the grid
  fails the check instead of exhausting the machine; a stop must not be a crash ("terminate called", bad_alloc).
Units of the series (the subbasin-52 grid model with its 5,000 m3/d pumping well, testconfig.grid_base):
  U1 the rates given as m3/s (-0.0578704) and U2 as L/s (-57.8704): GWBudget.csv "wells specified" is -5,000 m3/d, as with
     m3/d (U0);
  U3 ":WellFlowRate 1 ft3/s" and U4 ":BoundaryHead EDGE ft" stop: "units ... are not supported".
Reserved package names (the existing-model example):
  RN1 a model package named DRN_RAVEN (the GHB package renamed) stops with Raven's message ("a name Raven reserves for
     the packages it adds"), not MODFLOW's "Package name already exists";
  RN2 a recharge package named RCH_RAVEN that Raven takes over (:RavenTakesOver RCH_RAVEN) runs.
Quick mode (RAVEN_TEST_QUICK=1): the runs U0-U2 and RN2 last 2 days; full mode: 10 days.
"""
import os, re, sys, json, shutil, subprocess
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc   # noqa: E402

tc.need_mf6()
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 2 if QUICK else 10
W = os.path.dirname(tc.work('input_checks', 'x'))
fails = 0


def report(name, ok, detail=''):
    global fails
    print('%-74s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def limits():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (3 << 30, 3 << 30))


def run(d, days=None):
    """runs Raven (3 GB address space, 120 s at most for a stop case); returns (successful, message text)"""
    if days is not None:
        p = os.path.join(d, 'Liard.rvi'); t = open(p).read()
        open(p, 'w').write(re.sub(r':Duration\s+\S+(\s+\d\d:\d\d:\d\d)?', ':Duration %d' % days, t, count=1))
    os.makedirs(os.path.join(d, 'out'), exist_ok=True)
    try:
        r = subprocess.run([tc.RAVEN, 'Liard', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV,
                           timeout=600 if days and days > 1 else 120, preexec_fn=limits)
        out = r.stdout + r.stderr; rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = '(timeout)', -9
    e = os.path.join(d, 'out', 'Raven_errors.txt')
    out += open(e, errors='replace').read() if os.path.exists(e) else ''
    return ('Successful' in out), out + '\n(return code %s)' % rc


def edit(d, fn, old, new, regex=False):
    p = os.path.join(d, fn); t = open(p).read()
    if regex:
        t2, n = re.subn(old, new, t, count=1); assert n == 1, (fn, old); t = t2
    else:
        assert old in t, (fn, old); t = t.replace(old, new, 1)
    open(p, 'w').write(t)


def stops(name, d, want):
    ok, out = run(d, 1)
    line = (re.findall(r'.*' + re.escape(want) + r'.*', out) or [''])[0].strip()
    report(name, (not ok) and bool(line), ('stopped: ' + line[:150]) if line else 'did not stop with "%s": %s' % (
        want, (re.findall(r'(?:ERROR|Exiting Gracefully|terminate|what\(\)).*', out) or [out.strip().split('\n')[-1]])[-1][:150]))


# ---- numbers in the .rvg file (generated Liard model) ----
def liard(name):
    return tc.copy_case(tc.LIARD, os.path.join(W, name))


GB = ':GeneralHeadBoundary   GHB1 boundary_line.geojson HEAD %s CONDUCTANCE 5000.0 LAYERS TOP\n'
N = [('N1 :GridCellSize 2,000.0 stops (surplus value)', [(r':GridCellSize\s+\S+', ':GridCellSize 2,000.0')], "surplus value '000.0'"),
     ('N2 :GridCellSize 2km stops (not a number)', [(r':GridCellSize\s+\S+', ':GridCellSize 2km')], "'2km' is not a number"),
     ('N3 :GridCellSize 2 stops before the grid is built', [(r':GridCellSize\s+\S+', ':GridCellSize 2')], ':GridCellSize 2 m gives about'),
     ('N4 :GridRefinement RIVERS 5 stops before the grid is built', [], 'the :GridRefinement sizes give a regular grid of about', ':GridRefinement RIVERS 5\n'),
     ('N5 :GridRefinement RIVERS 1,000 stops (surplus value)', [], "surplus value '000'", ':GridRefinement RIVERS 1,000\n'),
     ('N6 boundary HEAD H1146 stops (not a number)', [], "'H1146' is not a number", GB % 'H1146'),
     ('N7 boundary HEAD 1146.85m stops (not a number)', [], "'1146.85m' is not a number", GB % '1146.85m'),
     ('N8 boundary HEAD 1,146.85 stops (values not in pairs)', [], 'must come in keyword-value pairs', GB % '1,146.85'),
     ('N9 :SolverMaxOuterIterations 50.5 stops (not a whole number)', [], "'50.5' is not a whole number", ':SolverMaxOuterIterations 50.5\n'),
     ('N10 :Wells row with LATITUDE 59.2x stops (not a number)', [], ":Wells in", ':Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, '
      'SCREEN_TOP, SCREEN_BOT\n  1, PW_1, 59.2x, -125.3, 1000, 990\n:EndWells\n')]
for case in N:
    name, edits, want = case[:3]
    d = liard('n%d' % N.index(case))
    for a, b in edits:
        edit(d, 'Liard.rvg', a, b, regex=True)
    if len(case) > 3:
        open(os.path.join(d, 'Liard.rvg'), 'a').write('\n' + case[3])
    stops(name, d, want)
    if 'N10' in name:   # (the message names the token as well)
        ok, out = run(d, 1); report('N10 the message names the token', "'59.2x' is not a number" in out)
    shutil.rmtree(d, ignore_errors=True)

# ---- grid size ----
QT = ':GridType QUADTREE\n:GridRefinement RIVERS %s\n'
for name, cs, extra, want in (('N11 :GridCellSize 60 stops before the grid is built', '60', '', ':GridCellSize 60 m gives about 5.08e+06 cells per layer'),
                              ('N12 :GridCellSize 50 stops before the grid is built', '50', '', ':GridCellSize 50 m gives about 7.32e+06 cells per layer'),
                              ('N13 quadtree :GridRefinement RIVERS 0.1 stops before the grid is built', None, QT % '0.1', 'give a quadtree grid of more than 1e+07 cells per layer (estimated)'),
                              ('N14 quadtree :GridRefinement RIVERS 0.5 stops with the estimated size, not a crash', None, QT % '0.5', 'cells per layer, from :GridRefinement')):
    d = liard('g_' + name.split()[0])
    if cs: edit(d, 'Liard.rvg', r':GridCellSize\s+\S+', ':GridCellSize ' + cs, regex=True)
    if extra: open(os.path.join(d, 'Liard.rvg'), 'a').write('\n' + extra)
    ok, out = run(d, 1)
    line = (re.findall(r'.*' + re.escape(want) + r'.*', out) or [''])[0].strip()
    crash = re.findall(r'terminate called|bad_alloc|Segmentation', out)
    if 'N14' in name and not line:   # (where the grid fits in the memory, the estimate stops it before the build)
        line = (re.findall(r'.*give a quadtree grid of.*', out) or [''])[0].strip()
    good = (not ok) and bool(line) and not crash and ('more than 5e+06' in line or 'N14' in name)
    report(name, good, ('stopped: ' + line[:170]) if line else 'did not stop with "%s": %s' % (want, (crash or [out.strip().split('\n')[-1]])[-1][:150]))
    shutil.rmtree(d, ignore_errors=True)

# quadtree estimate: overlapping and adjacent features count each square once (the 4-HRU strip of sz_models, 100 m cells)
sys.path.insert(0, os.path.join(HERE, 'soilzone')); import sz_models   # noqa: E402
def strip_qt(name, feats, cmd, size):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=4, hru_w=200.0, width=200.0, cell=100.0, physical=False, days=1, rain=1.0)
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(d, 'ref.geojson'), 'w'))
    open(os.path.join(d, 'm.rvg'), 'a').write('\n:GridType QUADTREE\n:GridRefinement %s ref.geojson %g\n' % (cmd, size))
    try:
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600, preexec_fn=limits)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        out = '(timeout)'
    s = os.path.join(d, 'out', 'GWModelSummary.txt'); g = re.findall(r'quadtree, 1 layers x (\d+) cells', open(s).read()) if os.path.exists(s) else []
    shutil.rmtree(d, ignore_errors=True)
    return ('Successful Simulation' in out), (int(g[0]) if g else 0), (re.findall(r'(?:ERROR|terminate).*', out) or [''])[-1]
line = lambda y, i: {"type": "Feature", "properties": {"ID": i + 1}, "geometry": {"type": "LineString", "coordinates": [sz_models.ll(-380.0, y), sz_models.ll(380.0, y)]}}
ok, n, msg = strip_qt('n15', [line(0.0, i) for i in range(200)], 'LINES', 0.1)
report('N15 200 copies of one line, :GridRefinement LINES 0.1, are built as one line', ok and 0 < n < 100000, '%d cells per layer %s' % (n, msg[:150]))
sq = lambda x0, s, i: {"type": "Feature", "properties": {"ID": i + 1}, "geometry": {"type": "Polygon", "coordinates": [[sz_models.ll(*p) for p in
      ((x0, -s / 2), (x0 + s, -s / 2), (x0 + s, s / 2), (x0, s / 2), (x0, -s / 2))]]}}
ok, n, msg = strip_qt('n16', [sq(-350.0 + 30.0 * i, 30.0, i) for i in range(20)], 'POLYGONS', 0.5)
report('N16 20 adjacent squares, :GridRefinement POLYGONS 0.5, are built', ok and n > 0, '%d cells per layer %s' % (n, msg[:150]))

# ---- units of :WellFlowRate and :BoundaryHead ----
B = tc.grid_base()


def units_case(name, units, value):
    d = os.path.join(W, name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(B, d, ignore=shutil.ignore_patterns('out', 'ready'))
    t = open(os.path.join(d, 'Liard.rvt')).read()
    assert ':WellFlowRate 1 m3/d' in t and '  -5000.0\n' in t
    t = t.replace(':WellFlowRate 1 m3/d', ':WellFlowRate 1 %s' % units).replace('  -5000.0\n', '  %s\n' % value)
    open(os.path.join(d, 'Liard.rvt'), 'w').write(t)
    return d


def wells_specified(d):
    b = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv')).dropna(subset=['wells specified [m3/d]'])
    return b['wells specified [m3/d]'].values


for name, units, value in (('U0 m3/d', 'm3/d', '-5000.0'), ('U1 m3/s', 'm3/s', '%.15g' % (-5000.0 / 86400)),
                           ('U2 L/s', 'L/s', '%.15g' % (-5000.0 / 86.4))):
    d = units_case('u_' + units.replace('/', '_'), units, value)
    ok, out = run(d, DAYS)
    if not ok:
        report('%s: the run completes' % name, False, out.strip().split('\n')[-1][:150]); continue
    q = wells_specified(d)
    report('%s: GWBudget.csv "wells specified" is -5,000 m3/d on every step' % name, len(q) > 0 and abs(q + 5000.0).max() < 1e-6,
           '%d steps, %.6f to %.6f m3/d' % (len(q), q.min(), q.max()))
    shutil.rmtree(d, ignore_errors=True)
d = units_case('u_ft3s', 'ft3/s', '-1.766')
stops('U3 :WellFlowRate 1 ft3/s stops (units not supported)', d, 'units ft3/s are not supported')
shutil.rmtree(d, ignore_errors=True)
d = units_case('u_head_ft', 'm3/d', '-5000.0')
open(os.path.join(d, 'Liard.rvt'), 'a').write('\n:BoundaryHead EDGE ft\n  1985-10-01 00:00:00 1.0 3\n  3000.0\n  3000.0\n  3000.0\n:EndBoundaryHead\n')
stops('U4 :BoundaryHead EDGE ft stops (units not supported)', d, 'units ft are not supported')
shutil.rmtree(d, ignore_errors=True)

# ---- names Raven reserves (existing model) ----
if not os.path.exists(os.path.join(W, 'Liard_groundwater')):    # (the example reads its forcing from ../Liard_groundwater)
    try: os.symlink(tc.LIARD, os.path.join(W, 'Liard_groundwater'))
    except OSError: shutil.copytree(tc.LIARD, os.path.join(W, 'Liard_groundwater'))
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'r1'))
edit(d, 'model/gwf_liard.nam', 'GHB6  gwf_liard.ghb  ghb_outlet', 'GHB6  gwf_liard.ghb  drn_raven')
stops('RN1 a model package named DRN_RAVEN stops with Raven\'s message', d, 'a name Raven reserves for the packages it adds')
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'r2'))
edit(d, 'model/gwf_liard.nam', 'RCH6  gwf_liard.rcha  rch_model', 'RCH6  gwf_liard.rcha  rch_raven')
edit(d, 'Liard.rvg', ':RavenTakesOver    RCH_MODEL EVT_MODEL', ':RavenTakesOver    RCH_RAVEN EVT_MODEL')
ok, out = run(d, DAYS)
report('RN2 a recharge package named RCH_RAVEN that Raven takes over runs (%d days)' % DAYS, ok, '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)

print('input checks: ALL PASSED' if fails == 0 else 'input checks: %d FAILED' % fails)
sys.exit(1 if fails else 0)
