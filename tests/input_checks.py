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
  N17 an HRU mesh (:GridType HRU_MESH, 4 HRUs of 5 x 5 km, :GridCellSize 500) with a short :GridRefinement LINES line of
      0.1 m (100 m meant) stops before the mesh is built: "... too slow to build" (the HRU boundaries take seeds at the
      finest line size); N18 the same with 2 m is built within the time limit (about 65,000 cells per layer).
  N24 a regular grid (400 x 300 km, :GridCellSize 2000) refined around 60 short lines (:GridRefinement LINES 100): the
      estimate counts the cells the 2:1 smoothing adds (2,918 columns by 2,161 rows, 6.3 million cells per layer, against
      4.8 million without it), so it stops before the grid is built, advising larger refinement sizes, QUADTREE or HRU_MESH.
  Each case runs under a 3 GB address-space limit and a 120 s time limit, so a build that tries to allocate the grid
  fails the check instead of exhausting the machine; a stop must not be a crash ("terminate called", bad_alloc).
Boundary polygons (the 4-HRU strip of sz_models with :SpecifiedHeadBoundary EDGE, 100 m cells):
  N19 polygon A over the last two cell columns, then A with a polygon B over the last column, then A twice: every file
      selects A's four cells (overlapping features and parts of a MultiPolygon add up; they do not cancel).
Numbers of the .rvp aquifer tables (each stops, naming the table, the row and the token):
  N20 :AquiferClasses K_HORIZ "1O" (letter O), N21 SPEC_YIELD "O.2", N22 an :AquiferProfiles thickness "3m", N23 an
      :AquiferProfileParameters value "2.O".
HRU polygons without area (the 2-HRU strip of sz_models, CONCEPTUAL, 1 day):
  N27 unused features with an empty Polygon (HRU_ID 98) and a ring of one point (HRU_ID 99): the run completes (the IDs
      are left out; the model does not use them);
  N28 HRU 1's Polygon empty: the run stops, "HRU 1 has an AQUIFER_PROFILE but no polygon in hru.geojson (GeoJSON file
      hru.geojson, feature 1 (HRU_ID 1): it has no polygon (its coordinates are empty))".
Units of the series (the subbasin-52 grid model with its 5,000 m3/d pumping well, testconfig.grid_base):
  U1 the rates given as m3/s (-0.0578704) and U2 as L/s (-57.8704): GWBudget.csv "wells specified" is -5,000 m3/d, as with
     m3/d (U0);
  U3 ":WellFlowRate 1 ft3/s" and U4 ":BoundaryHead EDGE ft" stop: "units ... are not supported".
River lines (the routed one-subbasin strip of combinations.py, :RiverGeometry river.geojson SUBID):
  N25 a second line whose SUBID (99) is no subbasin of the model: the run completes with the cells of the first line, and
      a warning names the line left out ("1 line of the river file ... names no subbasin of the model ... (ID 99)");
  N26 the only line has SUBID 99: the run stops, "no line of the river file ... has a subbasin of the model".
Time discretization of an existing model, read as MODFLOW 6 reads it (the existing-model example; TDIS PERIODDATA):
  E1 the first two period lengths written with Fortran exponents (10.0D-1, 0.31d2), a "//" comment line and a "!" comment
     line among the rows, and a comma between the values: the run completes and the working copy's TDIS holds the
     periods 1 d and DAYS - 1 d (MODFLOW 6 reads 10.0D-1 as 1);
  E2 a period length "1.0x" stops: "the length of stress period 1 in ... is '1.0x', which is not a number";
  E3 NPER 25 with 24 rows stops: "gives NPER 25 but 24 stress periods in PERIODDATA";
  E4 the forms mf6 6.8.1 also reads (checked against the mf6 program): a repeat count "2*1.0" (1 d), a slash "31.0/"
     and an exponent letter without digits "30.0e": the run completes with the periods 1 d and DAYS - 1 d;
  E5 period numbers "BEGIN period 0.2D1" and "BEGIN period 3/" in the well package (2 and 3 for MODFLOW 6), Raven
     starting a day after the model's time zero (period 1 dropped): the run completes and the working copy's well package
     starts with period 2's rates (-3000) as its period 1;
  E6 the river package's AUXILIARY line with a comment after the name ("auxiliary SUBBASIN # id": three auxiliary
     variables for MODFLOW, which reads every word of that line) and two more values on every river row: the run
     completes with GWBudget.csv and Hydrographs.csv identical to the unmodified model's (the subbasin ID is read with
     MODFLOW's stride of three values), and no file fort.* is left in the folder Raven runs in (every query to MODFLOW's
     memory is made while the model is initialised);
  E7 the name-file rows "WEL6 w0.wel W0" (one well at rate 0) and then "WEL6 gwf_liard.wel" without a name: MODFLOW 6
     names the second WEL-2 (its place among the WEL rows, named or not), and so does Raven: GWModelSummary.txt lists
     WEL-2 among the packages in balance, the working copy's row names it WEL-2, and GWBudget.csv's MF6 balance error stays
     below 1 m3/d (the 8000 m3/d of pumping booked);
  E8 two recharge rows without a name, "RCH6 gwf_liard.rcha" (RCH-1, :RavenTakesOver) and "RCH6 r2.rcha" (RCH-2,
     :KeepPackages): the working copy's row of the kept package names it RCH-2 (the removed row would otherwise make it
     MODFLOW's RCH-1), RCH-2 is in the balance, and the MF6 balance error stays below 1 m3/d;
  E9 the river package's OPTIONS with "auxiliary SUBBASIN" and then "auxiliary ZONE": MODFLOW 6 keeps the first line, and
     so does Raven (the names from MODFLOW's memory): the run completes with a warning on the second line, GWBudget.csv and
     Hydrographs.csv identical to the unmodified model's, and no fort.* file;
  E10 "auxiliary ZONE" and then "auxiliary SUBBASIN", with a ZONE value 7 before the subbasin ID on every row: SUBBASIN is
     no auxiliary variable for MODFLOW 6, so the run stops ("has no auxiliary variable SUBBASIN (MODFLOW 6 reads the
     auxiliary variables ZONE, from the first AUXILIARY line)") instead of mapping every river cell to subbasin 7;
  E11 a period length of -5 stops: "a stress period cannot be shorter than 0";
  E12 the model name file with CRLF line ends (RCH_MODEL and EVT_MODEL taken over): the run completes (the rows Raven
      comments out keep their line end, so MODFLOW finds no isolated carriage return).
  E13 the name file's RCH and EVT rows in an OPEN/CLOSE file of its PACKAGES block (MODFLOW 6 reads such a file in place
      of the line): taken over as when written inline (the working copy holds the rows, commented out), GWBudget.csv
      and Hydrographs.csv identical to the unmodified model's;
  E14 the same without :RavenTakesOver stops ("would add recharge or evapotranspiration beside Raven's") instead of
      running the model's recharge and ET beside Raven's, outside its books;
  E15 the MODELS and SOLUTIONGROUP blocks of mfsim.nam, each through an OPEN/CLOSE file (MODFLOW 6 reads both): results
      identical to the unmodified model's;
  E17 an :OverlapWeights cell number of 4294967297 (2^32 + 1, which a cut to int reads as cell 1) and E18 one of 20
      digits (beyond the long long range) stop, naming the number;
  E19 the OPTIONS block of the name file (SAVE_FLOWS, NEWTON) and of mfsim.nam each starting with OPEN/CLOSE (MODFLOW 6
      reads both): results identical to the unmodified model's (NEWTON found; CONTINUE written after the OPEN/CLOSE line);
  E20 OPEN/CLOSE as a later row of the PACKAGES block stops (MODFLOW 6 reads it only as a block's first line);
  E21 an OPEN/CLOSE file named by its absolute path: results identical to the unmodified model's;
  E22 an :OverlapWeights cell number of -20 digits stops ("out of range"); E23 a row of weight 0 with cell number
      4294967297 is skipped (the run completes);
  E16 loose solver tolerances (OUTER_DVCLOSE and INNER_DVCLOSE 10 m, inner_rclose 1e8): a converged step with an MF6
      balance error above 1 % of the gross flow gives a warning (once a run).
A model across the antimeridian:
  AM1 two HRUs whose shared edge lies on longitude 180 (the .rvh and GeoJSON longitudes within +-180, a DEM in
     longitude/latitude across 180, a specified head on the downslope edge, 3 days): the same active cells and the same
     recharge, storage and CHD flows (relative 1e-6) as the same model at longitude 0, and no DEM column without a value.
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

# HRU mesh with a refinement size meant in other units (the 4 HRUs of 5 x 5 km, 500 m cells, one short line)
def mesh_case(name, size):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=4, hru_w=5000.0, width=5000.0, cell=500.0, physical=False, days=1)
    xs = -10000.0
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "LineString", "coordinates":
               [list(sz_models.ll(xs + 100, 0)), list(sz_models.ll(xs + 600, 50))]}}]}, open(os.path.join(d, 'line.geojson'), 'w'))
    open(os.path.join(d, 'm.rvg'), 'a').write('\n:GridType HRU_MESH\n:GridRefinement LINES line.geojson %s\n' % size)
    try:
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=120, preexec_fn=limits)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        out = '(not finished after 120 s)'
    e = os.path.join(d, 'out', 'Raven_errors.txt'); out += open(e, errors='replace').read() if os.path.exists(e) else ''
    s = os.path.join(d, 'out', 'GWModelSummary.txt'); g = re.findall(r'HRU mesh, 1 layers x (\d+) cells', open(s).read()) if os.path.exists(s) else []
    shutil.rmtree(d, ignore_errors=True)
    return ('Successful Simulation' in out), (int(g[0]) if g else 0), out
ok, n, out = mesh_case('n17', '0.1')
line = (re.findall(r'.*too slow to build.*', out) or [''])[0].strip()
report('N17 HRU mesh, :GridRefinement LINES 0.1 stops before the mesh is built', (not ok) and bool(line), (line or out.strip().split('\n')[-1])[:170])
ok, n, out = mesh_case('n18', '2')
report('N18 HRU mesh, :GridRefinement LINES 2 is built within 120 s', ok and n > 10000, '%d cells per layer %s' % (n, '' if ok else out.strip().split('\n')[-1][:120]))

# regular grid refined around 60 short lines: the size counted with the 2:1 smoothing, before the grid is built
d = os.path.join(W, 'n24'); shutil.rmtree(d, ignore_errors=True)
sz_models.make_case(d, nhru=4, hru_w=100000.0, width=300000.0, cell=2000.0, physical=False, days=1, rain=1.0)
json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": i + 1}, "geometry": {"type": "LineString", "coordinates": [
    list(sz_models.ll(-195000 + i * 6500, -143000 + (i * 7919) % 280000)), list(sz_models.ll(-193500 + i * 6500, -141800 + (i * 7919) % 280000))]}} for i in range(60)]},
    open(os.path.join(d, 'lines.geojson'), 'w'))
open(os.path.join(d, 'm.rvg'), 'a').write('\n:GridRefinement LINES lines.geojson 100\n')
try:
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=120, preexec_fn=limits); out = r.stdout + r.stderr
except subprocess.TimeoutExpired:
    out = '(not finished after 120 s)'
e = os.path.join(d, 'out', 'Raven_errors.txt'); out += open(e, errors='replace').read() if os.path.exists(e) else ''
shutil.rmtree(d, ignore_errors=True)
m = re.search(r'the :GridRefinement sizes give a regular grid of about (\S+) cells per layer \((\d+) columns by (\d+) rows\)[^\n]*QUADTREE or HRU_MESH', out)
crash = re.findall(r'terminate called|bad_alloc|Segmentation|not enough memory', out)
report('N24 regular grid, 60 lines refined to 100 m: stops before the build, smoothing counted', m is not None and int(m.group(2)) * int(m.group(3)) > 5e6 and not crash,
       ('%s x %s cells' % (m.group(2), m.group(3))) if m else (re.findall(r'ERROR.*', out) or [out.strip().split('\n')[-1]])[0][:170])


# ---- boundary polygons: overlapping features add up
def chd_cells(name, feats, multi=False):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=4, days=1, physical=False, chd=95.0)
    rings = lambda r: [[list(sz_models.ll(*p)) for p in r]]
    fs = ([{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "MultiPolygon", "coordinates": [rings(r) for r in feats]}}] if multi else
          [{"type": "Feature", "properties": {"ID": i + 1}, "geometry": {"type": "Polygon", "coordinates": rings(r)}} for i, r in enumerate(feats)])
    json.dump({"type": "FeatureCollection", "features": fs}, open(os.path.join(d, 'edge.geojson'), 'w'))
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600)
    p = os.path.join(d, 'out', 'mf6', 'gwf.chd')
    cells = sorted(' '.join(l.split()[:3]) for l in open(p).read().split('BEGIN PERIOD')[1].split('END PERIOD')[0].split('\n')[1:] if l.strip()) if os.path.exists(p) else []
    shutil.rmtree(d, ignore_errors=True)
    return ('Successful Simulation' in r.stdout + r.stderr), cells
A = [(225.0, -300.0), (600.0, -300.0), (600.0, 300.0), (225.0, 300.0), (225.0, -300.0)]   # the last two cell columns
B = [(325.0, -300.0), (600.0, -300.0), (600.0, 300.0), (325.0, 300.0), (325.0, -300.0)]   # the last one
res = {k: chd_cells('n19_' + k, f, k == 'multi') for k, f in (('a', [A]), ('ab', [A, B]), ('aa', [A, A]), ('multi', [A, B]))}
ref = res['a'][1]
report('N19 overlapping boundary polygons (A+B, A twice, MultiPolygon A+B) select the cells of A', all(v[0] for v in res.values()) and len(ref) >= 4 and
       all(v[1] == ref for v in res.values()), '; '.join('%s: %d cells' % (k, len(v[1])) for k, v in res.items()))


# ---- numbers of the .rvp aquifer tables
def rvp_case(name, old, new, want):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=2, days=1, physical=False, top=3.0)
    edit(d, 'm.rvp', old, new, regex=True)
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600)
    e = os.path.join(d, 'out', 'Raven_errors.txt'); out = r.stdout + r.stderr + (open(e, errors='replace').read() if os.path.exists(e) else '')
    line = (re.findall(r'.*' + re.escape(want) + r'.*', out) or [''])[0].strip()
    shutil.rmtree(d, ignore_errors=True)
    return ('Successful Simulation' not in out) and bool(line), (line or out.strip().split('\n')[-1])[:170]
for name, old, new, want in (('N20 :AquiferClasses K_HORIZ 1O stops', r'(\n  SAND, )\S+?,', r'\g<1>1O,', "row SAND: K_HORIZ '1O' is not a number"),
                             ('N21 :AquiferClasses SPEC_YIELD O.2 stops', r'(\n  SAND, [^,]+, [^,]+, [^,]+, )[^,]+,', r'\g<1>O.2,', "row SAND: SPEC_YIELD 'O.2' is not a number"),
                             ('N22 :AquiferProfiles thickness 3m stops', r'AQ, 2, SAND, 3, AQUIFER', 'AQ, 2, SAND, 3m, AQUIFER', "the thickness of layer 1 (or TO_BEDROCK) '3m' is not a number"),
                             ('N23 :AquiferProfileParameters value 2.O stops', r'(:Units, m, m, 1/d, m\n  AQ, )[^,]+,', r'\g<1>2.O,', "row AQ: INITIAL_HEAD_DEPTH '2.O' is not a number")):
    ok, msg = rvp_case(name.split()[0].lower(), old, new, want)
    report(name, ok, msg)

# ---- HRU polygons without area ----
def hru_poly_case(name, change):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=2, days=1, physical=False, top=3.0)
    p = os.path.join(d, 'hru.geojson'); g = json.load(open(p)); change(g['features']); json.dump(g, open(p, 'w'))
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600)
    e = os.path.join(d, 'out', 'Raven_errors.txt'); out = r.stdout + r.stderr + (open(e, errors='replace').read() if os.path.exists(e) else '')
    shutil.rmtree(d, ignore_errors=True)
    return ('Successful Simulation' in out), out


def extra_feats(f):
    sq = f[0]['geometry']['coordinates'][0]
    f.append({"type": "Feature", "properties": {"HRU_ID": 98}, "geometry": {"type": "Polygon", "coordinates": []}})
    f.append({"type": "Feature", "properties": {"HRU_ID": 99}, "geometry": {"type": "Polygon", "coordinates": [[sq[0], sq[0], sq[0]]]}})
ok, out = hru_poly_case('n27', extra_feats)
report('N27 unused features without area (an empty Polygon, a ring of one point) are left out', ok, '' if ok else out.strip().split('\n')[-1][:150])
ok, out = hru_poly_case('n28', lambda f: f[0]['geometry'].update(coordinates=[]))
want = 'HRU 1 has an AQUIFER_PROFILE but no polygon in hru.geojson (GeoJSON file hru.geojson, feature 1 (HRU_ID 1): it has no polygon'
line = (re.findall(r'.*' + re.escape(want) + r'.*', out) or [''])[0].strip()
report('N28 an HRU whose only polygon is empty stops, naming the feature', (not ok) and bool(line), line[:170] if line else out.strip().split('\n')[-1][:150])

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

# ---- river lines whose subbasin ID is not in the model ----
import combinations as CB   # noqa: E402
RS = dict(sz='CONC', vz='NONE', K=1, x={'riv'}, st=set(), dt=1.0)


def riv_cells(d):
    p = os.path.join(d, 'out', 'mf6', 'gwf.riv')
    return sorted(' '.join(l.split()[:3]) for l in open(p).read().split('BEGIN PERIOD')[1].split('END PERIOD')[0].split('\n')[1:] if l.strip()) if os.path.exists(p) else []


def riv_case(name, ids):
    d = CB.generated(os.path.join(W, name), RS)
    sub_rvi = os.path.join(d, 'm.rvi'); tt = open(sub_rvi).read(); open(sub_rvi, 'w').write(re.sub(r':Duration\s+\S+', ':Duration 1', tt, count=1))
    g = json.load(open(os.path.join(d, 'river.geojson'))); f0 = g['features'][0]
    g['features'] = [dict(f0, properties={'SUBID': i}) for i in ids]
    json.dump(g, open(os.path.join(d, 'river.geojson'), 'w'))
    try:
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600); out = r.stdout + r.stderr; rc = r.returncode
    except subprocess.TimeoutExpired:
        out, rc = '(timeout)', -9
    e = os.path.join(d, 'out', 'Raven_errors.txt'); out += open(e, errors='replace').read() if os.path.exists(e) else ''
    return d, ('Successful Simulation' in out), out + '\n(return code %s)' % rc
d1, ok1, _ = riv_case('n25_ref', [1])
c1 = riv_cells(d1)
d2, ok2, out2 = riv_case('n25', [1, 99])
c2 = riv_cells(d2)
wl = (re.findall(r'.*names no subbasin of the model.*', out2) or [''])[0].strip()
report('N25 a river line of an unknown subbasin (99) is left out with a warning', ok1 and ok2 and len(c1) > 0 and c2 == c1 and '(ID 99)' in wl,
       '%d river cells (one line alone: %d); %s' % (len(c2), len(c1), wl[:120] if wl else 'no warning; ' + out2.strip().split('\n')[-1][:100]))
d3, ok3, out3 = riv_case('n26', [99])
wl = (re.findall(r'.*no line of the river file.*', out3) or [''])[0].strip()
report('N26 a river file whose only line has an unknown subbasin stops', (not ok3) and bool(wl), wl[:150] if wl else out3.strip().split('\n')[-1][:150])
for x in (d1, d2, d3):
    shutil.rmtree(x, ignore_errors=True)

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

# ---- the existing model's time discretization, read as MODFLOW 6 reads it ----
def tdis_case(name, rows):
    d = tc.copy_case(tc.EXISTING, os.path.join(W, name))
    p = os.path.join(d, 'model', 'ext.tdis'); tt = open(p).read()
    i = tt.index('BEGIN perioddata\n') + len('BEGIN perioddata\n'); j = tt.index('END perioddata')
    old = tt[i:j].split('\n')[:-1]
    open(p, 'w').write(tt[:i] + ''.join(l + '\n' for l in rows(old)) + tt[j:])
    return d


def periods(d):
    p = os.path.join(d, 'out', 'mf6', 'ext.tdis')
    if not os.path.exists(p): return []
    m = re.search(r'BEGIN PERIODDATA(.*?)END PERIODDATA', open(p).read(), re.S)   # (the rewritten file; none when the run stopped first)
    return [float(l.split()[0]) for l in m.group(1).split('\n') if l.strip()] if m else []


d = tdis_case('e1', lambda r: ['  // stress periods: one day, then the months', '      10.0D-1  1       1.00000000', '  ! October', '      0.31d2,  31,  1.0'] + r[2:])
ok, out = run(d, DAYS)
pl = periods(d)
report('E1 period lengths 10.0D-1 and 0.31d2 with // and ! comment rows are read as MODFLOW reads them', ok and pl == [1.0, float(DAYS - 1)],
       'working-copy periods %s' % pl if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = tdis_case('e2', lambda r: ['      1.0x  1       1.00000000'] + r[1:])
stops('E2 a period length 1.0x stops', d, "is '1.0x', which is not a number")
shutil.rmtree(d, ignore_errors=True)
d = tdis_case('e3', lambda r: r[:-1])
stops('E3 NPER 25 with 24 period rows stops', d, 'gives NPER 25 but 24 stress periods in PERIODDATA')
shutil.rmtree(d, ignore_errors=True)
d = tdis_case('e4', lambda r: ['      2*1.0  1  1.0', '      31.0/  31  1.0', '      30.0e  30  1.0'] + r[3:])
ok, out = run(d, DAYS)
pl = periods(d)
report('E4 period lengths 2*1.0, 31.0/ and 30.0e are read as MODFLOW reads them', ok and pl == [1.0, float(DAYS - 1)],
       'working-copy periods %s' % pl if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e5'))
edit(d, 'model/gwf_liard.wel', 'BEGIN period  2\n', 'BEGIN period  0.2D1\n')
edit(d, 'model/gwf_liard.wel', 'BEGIN period  3\n', 'BEGIN period  3/\n')
edit(d, 'Liard.rvi', ':StartDate          1985-10-01', ':StartDate          1985-10-02')
ok, out = run(d, DAYS)
p = os.path.join(d, 'out', 'mf6', 'gwf_liard.wel'); wl = open(p).read() if os.path.exists(p) else ''
m = re.search(r'BEGIN PERIOD 1[^\n]*\n(.*?)END PERIOD', wl, re.S)
report('E5 period numbers 0.2D1 and 3/ are read as MODFLOW reads them (start a day after time zero)', ok and m is not None and '-3.00000000E+03' in m.group(1),
       ('new period 1: %s' % ' | '.join(m.group(1).split('\n')[:2]) if m else 'no renumbered period 1') if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)

res = {}
for k in ('e6_ref', 'e6'):
    d = tc.copy_case(tc.EXISTING, os.path.join(W, k))
    if k == 'e6':
        p = os.path.join(d, 'model', 'gwf_liard.riv'); tt = open(p).read()
        tt = tt.replace('  auxiliary  SUBBASIN\n', '  auxiliary  SUBBASIN   # id\n')
        tt = re.sub(r'(?m)^(  \d+ \d+ \d+ \S+ \S+ \S+ \S+)$', r'\1  0  0', tt)
        open(p, 'w').write(tt)
    res[k] = (run(d, DAYS), d)
def same(a, b):
    return all(open(os.path.join(a, 'out', f), 'rb').read() == open(os.path.join(b, 'out', f), 'rb').read() for f in ('GWBudget.csv', 'Hydrographs.csv'))


def strays(d):   # (files a query to a finalised MODFLOW library leaves in the folder Raven runs in)
    return [f for f in os.listdir(d) if f.startswith('fort.')] + [f for f in os.listdir(os.path.join(d, 'out')) if f.startswith('fort.')]


okb = all(v[0][0] for v in res.values()) and same(res['e6_ref'][1], res['e6'][1]) and not strays(res['e6'][1])
report('E6 AUXILIARY SUBBASIN # id (three auxiliary variables, as MODFLOW reads them) maps the rivers as without the comment', okb,
       ('stray files %s' % strays(res['e6'][1]) if strays(res['e6'][1]) else '') if all(v[0][0] for v in res.values()) else res['e6'][0][1].strip().split('\n')[-1][:150])
shutil.rmtree(res['e6'][1], ignore_errors=True)


def budget_err(d):
    p = os.path.join(d, 'out', 'GWBudget.csv')
    if not os.path.exists(p): return None
    b = pd.read_csv(p); c = [k for k in b.columns if k.startswith('MF6 balance error [m3/d]')][0]
    return float(b[c].abs().max())


def in_balance(d):
    p = os.path.join(d, 'out', 'GWModelSummary.txt')
    m = re.search(r'packages in balance\s*:(.*)', open(p).read()) if os.path.exists(p) else None
    return m.group(1).split() if m else []


def mf6_row(d, fname):
    p = os.path.join(d, 'out', 'mf6', 'gwf_liard.nam')
    return [l.split() for l in open(p) if len(l.split()) >= 2 and l.split()[1] == fname and not l.lstrip().startswith('#')] if os.path.exists(p) else []


# ---- unnamed packages: named as MODFLOW 6 names them ----
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e7'))
edit(d, 'model/gwf_liard.nam', 'WEL6  gwf_liard.wel  wel_pumps', 'WEL6  w0.wel  W0\n  WEL6  gwf_liard.wel')
open(os.path.join(d, 'model', 'w0.wel'), 'w').write('BEGIN options\nEND options\n\nBEGIN dimensions\n  MAXBOUND  1\nEND dimensions\n\n'
                                                  'BEGIN period  1\n  3 63 76 0.0\nEND period  1\n')
ok, out = run(d, DAYS)
e, bal, row = budget_err(d), in_balance(d), mf6_row(d, 'gwf_liard.wel')
report('E7 an unnamed WEL row after a named one is WEL-2, as for MODFLOW, and in the balance', ok and 'WEL-2' in bal and e is not None and e < 1.0
       and bool(row) and row[0][2:3] == ['WEL-2'], ('in balance: %s; max |MF6 balance error| %s m3/d; working-copy row %s' % (' '.join(bal), e, row)) if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e8'))
edit(d, 'model/gwf_liard.nam', 'RCH6  gwf_liard.rcha  rch_model', 'RCH6  gwf_liard.rcha\n  RCH6  r2.rcha')
shutil.copy(os.path.join(d, 'model', 'gwf_liard.rcha'), os.path.join(d, 'model', 'r2.rcha'))
edit(d, 'model/r2.rcha', 'CONSTANT  4.00000000E-04', 'CONSTANT  1.00000000E-04')
edit(d, 'Liard.rvg', ':RavenTakesOver    RCH_MODEL EVT_MODEL', ':RavenTakesOver    RCH-1 EVT_MODEL\n:KeepPackages      RCH-2')
ok, out = run(d, DAYS)
e, bal, row = budget_err(d), in_balance(d), mf6_row(d, 'r2.rcha')
report('E8 a kept unnamed RCH after a taken-over one stays RCH-2 in the working copy, in the balance', ok and 'RCH-2' in bal and e is not None and e < 1.0
       and bool(row) and row[0][2:3] == ['RCH-2'], ('in balance: %s; max |MF6 balance error| %s m3/d; working-copy row %s' % (' '.join(bal), e, row)) if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)

# ---- two AUXILIARY lines in the stream package: MODFLOW 6 keeps the first ----
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e9'))
edit(d, 'model/gwf_liard.riv', '  auxiliary  SUBBASIN\n', '  auxiliary  SUBBASIN\n  auxiliary  ZONE\n')
ok, out = run(d, DAYS)
warned = 'has 2 AUXILIARY lines' in out or 'has 2 AUXILIARY lines' in (open(os.path.join(d, 'out', 'Raven_errors.txt')).read() if os.path.exists(os.path.join(d, 'out', 'Raven_errors.txt')) else '')
report('E9 AUXILIARY SUBBASIN, then AUXILIARY ZONE: the first line is used, as by MODFLOW, with a warning', ok and warned and same(res['e6_ref'][1], d) and not strays(d),
       ('warning %s, stray files %s' % (warned, strays(d))) if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e10'))
p = os.path.join(d, 'model', 'gwf_liard.riv'); tt = open(p).read()
tt = tt.replace('  auxiliary  SUBBASIN\n', '  auxiliary  ZONE\n  auxiliary  SUBBASIN\n')
tt = re.sub(r'(?m)^(  \d+ \d+ \d+ \S+ \S+ \S+) (\S+)$', r'\1 7 \2', tt)
open(p, 'w').write(tt)
stops('E10 AUXILIARY ZONE, then AUXILIARY SUBBASIN stops (SUBBASIN is no auxiliary variable for MODFLOW)', d,
      'has no auxiliary variable SUBBASIN (MODFLOW 6 reads the auxiliary variables ZONE, from the first AUXILIARY line)')
shutil.rmtree(d, ignore_errors=True)
# ---- OPEN/CLOSE in the name files (MODFLOW 6 reads the rows of the file in place of the OPEN/CLOSE line)
def oc_case(name):
    d = tc.copy_case(tc.EXISTING, os.path.join(W, name))
    edit(d, 'model/gwf_liard.nam', '  RCH6  gwf_liard.rcha  rch_model\n', '')
    edit(d, 'model/gwf_liard.nam', '  EVT6  gwf_liard.evta  evt_model\n', '')
    edit(d, 'model/gwf_liard.nam', 'BEGIN packages\n', 'BEGIN packages\n  OPEN/CLOSE  pk.txt\n')
    open(os.path.join(d, 'model', 'pk.txt'), 'w').write('# recharge and ET\n  RCH6  gwf_liard.rcha  rch_model\n  EVT6  gwf_liard.evta  evt_model\n')
    return d
d = oc_case('e13')
ok, out = run(d, DAYS)
rows = [r[0] for r in mf6_row(d, 'gwf_liard.rcha') + mf6_row(d, 'gwf_liard.evta')]
nam = open(os.path.join(d, 'out', 'mf6', 'gwf_liard.nam')).read() if os.path.exists(os.path.join(d, 'out', 'mf6', 'gwf_liard.nam')) else ''
okc = ok and same(res['e6_ref'][1], d) and not rows and re.search(r'(?m)^#\s+RCH6\s+gwf_liard.rcha\s+rch_model\s+# taken over by Raven', nam) is not None \
    and in_balance(d) == in_balance(res['e6_ref'][1])
report('E13 RCH and EVT rows in an OPEN/CLOSE file of the PACKAGES block are taken over as when written inline', okc,
       ('in balance: %s; active rows %s' % (' '.join(in_balance(d)), rows)) if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = oc_case('e14')
edit(d, 'Liard.rvg', ':RavenTakesOver    RCH_MODEL EVT_MODEL', '')
stops('E14 the same without :RavenTakesOver stops (the model\'s RCH would run beside Raven\'s)', d,
      'package RCH_MODEL would add recharge or evapotranspiration beside Raven\'s')
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e15'))
edit(d, 'model/mfsim.nam', '  gwf6  gwf_liard.nam  gwf_liard\n', '  OPEN/CLOSE  models.txt\n')
open(os.path.join(d, 'model', 'models.txt'), 'w').write('  gwf6  gwf_liard.nam  gwf_liard\n')
edit(d, 'model/mfsim.nam', '  ims6  ext.ims  gwf_liard\n', '  OPEN/CLOSE  solution.txt\n')
open(os.path.join(d, 'model', 'solution.txt'), 'w').write('  ims6  ext.ims  gwf_liard\n')
ok, out = run(d, DAYS)
report('E15 the MODELS and SOLUTIONGROUP blocks of mfsim.nam through OPEN/CLOSE files run as written inline', ok and same(res['e6_ref'][1], d),
       '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e19'))
edit(d, 'model/gwf_liard.nam', 'BEGIN options\n  SAVE_FLOWS\n  NEWTON\n', 'BEGIN options\n  OPEN/CLOSE  options.txt\n')
open(os.path.join(d, 'model', 'options.txt'), 'w').write('  SAVE_FLOWS\n  NEWTON\n')
edit(d, 'model/mfsim.nam', 'BEGIN options\n', 'BEGIN options\n  OPEN/CLOSE  simoptions.txt\n')
open(os.path.join(d, 'model', 'simoptions.txt'), 'w').write('  MEMORY_PRINT_OPTION  summary\n')
ok, out = run(d, DAYS)
report('E19 the OPTIONS blocks of the name file (NEWTON) and of mfsim.nam starting with OPEN/CLOSE run as written inline', ok and same(res['e6_ref'][1], d),
       '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
d = oc_case('e20')
edit(d, 'model/gwf_liard.nam', 'BEGIN packages\n  OPEN/CLOSE  pk.txt\n', 'BEGIN packages\n')
edit(d, 'model/gwf_liard.nam', '  OC6  gwf_liard.oc  oc\n', '  OC6  gwf_liard.oc  oc\n  OPEN/CLOSE  pk.txt\n')
stops('E20 OPEN/CLOSE after the first row of the PACKAGES block stops, as MODFLOW 6 refuses it', d, 'has OPEN/CLOSE after its first line')
shutil.rmtree(d, ignore_errors=True)
d = oc_case('e21')
edit(d, 'model/gwf_liard.nam', '  OPEN/CLOSE  pk.txt\n', '  OPEN/CLOSE  %s\n' % os.path.join(d, 'model', 'pk.txt'))
ok, out = run(d, DAYS)
report('E21 an OPEN/CLOSE file named by its absolute path is read', ok and same(res['e6_ref'][1], d), '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
# ---- :OverlapWeights cell numbers beyond the int range
def ow_case(name, cell):
    d = tc.copy_case(tc.EXISTING, os.path.join(W, name))
    blk = open(os.path.join(d, 'overlap_weights_alternative.rvg')).read()
    blk = re.sub(r'(?m)^  2736 3867 ', '  2736 %s ' % cell, blk, count=1)
    t = open(os.path.join(d, 'Liard.rvg')).read()
    t = '\n'.join(l for l in t.split('\n') if not re.match(r'\s*:(MF6CRS|HRUGeometry)\b', l)) + '\n' + blk
    open(os.path.join(d, 'Liard.rvg'), 'w').write(t)
    return d
d = ow_case('e17', '4294967297')
stops('E17 an :OverlapWeights cell number of 4294967297 (2^32 + 1) stops instead of being read as cell 1', d, 'the cell number 4294967297 is not between 1 and')
shutil.rmtree(d, ignore_errors=True)
d = ow_case('e18', '99999999999999999999')
stops('E18 an :OverlapWeights cell number of 20 digits stops', d, "'99999999999999999999' is out of range")
shutil.rmtree(d, ignore_errors=True)
d = ow_case('e22', '-99999999999999999999')
stops('E22 an :OverlapWeights cell number of -20 digits stops as out of range', d, "'-99999999999999999999' is out of range (beyond -9223372036854775808)")
shutil.rmtree(d, ignore_errors=True)
d = ow_case('e23', '4294967297')
edit(d, 'Liard.rvg', '  2736 4294967297 0.0725014080', '  2736 4294967297 0.0')
ok, out = run(d, 1)
report('E23 an :OverlapWeights row of weight 0 is skipped, whatever its cell number', ok, '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
# ---- a converged step with a large MF6 balance error is reported
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e16'))
edit(d, 'model/ext.ims', 'OUTER_DVCLOSE  1.00000000E-05', 'OUTER_DVCLOSE  10.0')
edit(d, 'model/ext.ims', 'INNER_DVCLOSE  1.00000000E-06', 'INNER_DVCLOSE  10.0')
edit(d, 'model/ext.ims', 'inner_rclose       1.00000000  strict', 'inner_rclose       1.0E+08')
ok, out = run(d, DAYS)
e = budget_err(d); warned = 'MODFLOW converged with a balance error of' in out
report('E16 a converged step with an MF6 balance error above 1 % of the gross flow gives a warning (loose solver tolerances)', ok and warned,
       'max |MF6 balance error| %s m3/d; warning %s' % (e, warned) if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)
shutil.rmtree(res['e6_ref'][1], ignore_errors=True)
d = tdis_case('e11', lambda r: ['      -5.0  1       1.00000000'] + r[1:])
stops('E11 a negative period length stops', d, 'a stress period cannot be shorter than 0')
shutil.rmtree(d, ignore_errors=True)
d = tc.copy_case(tc.EXISTING, os.path.join(W, 'e12'))
p = os.path.join(d, 'model', 'gwf_liard.nam'); b = open(p, 'rb').read(); open(p, 'wb').write(b.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
ok, out = run(d, DAYS)
report('E12 a name file with CRLF line ends and packages Raven takes over runs', ok, '' if ok else out.strip().split('\n')[-1][:150])
shutil.rmtree(d, ignore_errors=True)

# ---- a model across the antimeridian: the same model as at longitude 0
sys.path.insert(0, os.path.join(HERE, 'soilzone'))
import math
import sz_models   # noqa: E402


def am_case(name, lon0, wrap):
    """two HRUs of 400 m x 400 m whose shared edge lies on longitude lon0 + 0 (on 180 when lon0 is 180), a specified head on
    the downslope edge, 3 days; wrap: every longitude written within +-180 (as GDAL, QGIS and Raven's .rvh take them)"""
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.LAT0, sz_models.LON0 = -16.8, lon0
    sz_models._P0, sz_models._L0 = math.radians(sz_models.LAT0), math.radians(sz_models.LON0)
    sz_models.make_case(d, nhru=2, hru_w=400, width=400, cell=100, slope=0.01, physical=False, days=3, chd=95.0)
    if wrap:
        for fn in ('hru.geojson', 'edge.geojson'):
            g = json.load(open(os.path.join(d, fn)))
            for f in g['features']:
                ring = f['geometry']['coordinates'][0]
                if min(p[0] for p in ring) >= 180 - 1e-12:
                    f['geometry']['coordinates'][0] = [[p[0] - 360, p[1]] for p in ring]
            json.dump(g, open(os.path.join(d, fn), 'w'))
        t = open(os.path.join(d, 'm.rvh')).read()
        t = re.sub(r'(?m)^(  \d+, [^,]+, [^,]+, [^,]+, )([-\d.]+)', lambda m: m.group(1) + '%.6f' % (float(m.group(2)) - 360 if float(m.group(2)) > 180 else float(m.group(2))), t)
        open(os.path.join(d, 'm.rvh'), 'w').write(t)
    os.makedirs(os.path.join(d, 'out'), exist_ok=True)
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600)
    out = r.stdout + r.stderr
    e = os.path.join(d, 'out', 'Raven_errors.txt'); out += open(e, errors='replace').read() if os.path.exists(e) else ''
    sm = open(os.path.join(d, 'out', 'GWModelSummary.txt')).read() if os.path.exists(os.path.join(d, 'out', 'GWModelSummary.txt')) else ''
    b = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv')) if os.path.exists(os.path.join(d, 'out', 'GWBudget.csv')) else None
    act = re.search(r'active cells\s*:\s*(\d+)', sm)
    return 'Successful' in out, out, (int(act.group(1)) if act else -1), b


a_ok, a_out, a_act, a_b = am_case('a1', 180.0, True)
r_ok, r_out, r_act, r_b = am_case('a1_ref', 0.0, False)
dev = max(abs(a_b[k] - r_b[k]).max() / max(abs(r_b[k]).max(), 1.0) for k in ('MF6 recharge [m3/d]', 'storage release [m3/d]', 'CHD [m3/d]')) if (a_b is not None and r_b is not None) else 1.0
report('AM1 a model across the antimeridian (longitudes within +-180) is the same model as at longitude 0', a_ok and r_ok and a_act == r_act and dev < 1e-6 and 'gives no value' not in a_out,
       'active cells %d (at longitude 0: %d); largest relative difference of recharge, storage and CHD flows %.1e%s' % (a_act, r_act, dev, '; DEM without values' if 'gives no value' in a_out else ''))
for k in ('a1', 'a1_ref'):
    shutil.rmtree(os.path.join(W, k), ignore_errors=True)

print('input checks: ALL PASSED' if fails == 0 else 'input checks: %d FAILED' % fails)
sys.exit(1 if fails else 0)
