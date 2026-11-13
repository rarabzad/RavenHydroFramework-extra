"""Shared settings for the test scripts: where Raven, its source, the MODFLOW 6 library, the examples and the scratch
folder are.

Every test script imports this module. The tests live in the RavenHydroFramework-extra repository; Raven itself (with the MODFLOW 6
coupling) is a separate checkout of RavenHydroFramework. By default the two sit side by side:

    <folder>/RavenHydroFramework         Raven source, built with CMake (build/) or make (src/)
    <folder>/RavenHydroFramework-extra   this repository

Otherwise set:

    export RAVEN_SRC=/path/to/RavenHydroFramework   # Raven checkout (its src/ is used by the unit tests)
    export RAVEN_EXE=/path/to/Raven.exe             # default: the built Raven in that checkout
    export RAVEN_MF6_LIB=/path/to/libmf6.so         # default: lib/mf6 of either repository, or next to Raven
    export RAVEN_TEST_WORK=/path/to/scratch         # default: tests/_work (created)

The Liard examples in examples/ are the base cases; each test copies them into the scratch folder and edits the copy.
"""
import math, os, sys, shutil, subprocess, re

TESTS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS)                                        # the RavenHydroFramework-extra repository
RAVEN_ROOT = os.path.abspath(os.environ.get('RAVEN_SRC', os.path.join(os.path.dirname(REPO), 'RavenHydroFramework')))
if os.path.basename(RAVEN_ROOT) == 'src' and os.path.exists(os.path.join(RAVEN_ROOT, 'RavenMain.cpp')):
    RAVEN_ROOT = os.path.dirname(RAVEN_ROOT)                         # RAVEN_SRC may also point at src/ itself
SRC = os.path.join(RAVEN_ROOT, 'src')                                # Raven's source files


def _default_raven():
    for c in (os.path.join(RAVEN_ROOT, 'build', 'Raven'), os.path.join(RAVEN_ROOT, 'build', 'Release', 'Raven.exe'),
              os.path.join(RAVEN_ROOT, 'build', 'Raven.exe'), os.path.join(SRC, 'Raven.exe'),
              os.path.join(SRC, 'x64', 'Release', 'Raven.exe')):
        if os.path.exists(c):
            return c
    return os.path.join(RAVEN_ROOT, 'build', 'Raven')


RAVEN = os.path.abspath(os.environ.get('RAVEN_EXE', _default_raven()))
REF = os.environ.get('RAVEN_EXE_REF', '')                            # reference build of the byte-identity checks ('' = skipped)
if not REF and os.environ.get('RAVEN_REF_EXE'):                      # (RAVEN_REF_EXE is accepted as another name for it)
    REF = os.environ['RAVEN_REF_EXE']
    print('testconfig: RAVEN_REF_EXE is read as RAVEN_EXE_REF; please use RAVEN_EXE_REF')
REF = os.path.abspath(REF) if REF else ''
MF6LIB = os.environ.get('RAVEN_MF6_LIB', '')
if not MF6LIB:   # the library fetched by tools/get_mf6.py, where Raven itself also finds it
    for _d in (os.path.dirname(RAVEN), os.path.join(RAVEN_ROOT, 'lib', 'mf6'), os.path.join(REPO, 'lib', 'mf6')):
        for _n in ('libmf6.so', 'libmf6.dylib', 'libmf6.dll'):
            if not MF6LIB and os.path.exists(os.path.join(_d, _n)):
                MF6LIB = os.path.join(_d, _n)
LIARD = os.path.join(REPO, 'examples', 'Liard_groundwater')           # Raven builds the groundwater model
EXISTING = os.path.join(REPO, 'examples', 'Liard_existing_model')     # Raven couples an existing MODFLOW 6 model
WORK = os.path.abspath(os.environ.get('RAVEN_TEST_WORK', os.path.join(TESTS, '_work')))
os.makedirs(WORK, exist_ok=True)

ENV = dict(os.environ)
if MF6LIB:
    ENV['RAVEN_MF6_LIB'] = os.path.abspath(MF6LIB)

sys.path.insert(0, LIARD)
import tools_audit as audit   # noqa: E402  (the audit tool shipped with the example)


def need_mf6():
    """stop with a clear message when the MODFLOW 6 library is not configured"""
    if not MF6LIB or not os.path.exists(MF6LIB):
        sys.exit('MODFLOW 6 library not found: run  python tools/get_mf6.py  in RavenHydroFramework-extra, or set RAVEN_MF6_LIB to libmf6.so / libmf6.dll / libmf6.dylib')
    if not os.path.exists(RAVEN):
        sys.exit('Raven not found at %s: build RavenHydroFramework beside this repository, or set RAVEN_SRC or RAVEN_EXE' % RAVEN)


def skip(what, why='RAVEN_EXE_REF not set'):
    """reports a check that was not made: one line 'SKIP <what>: <why>' (run_all.py counts these lines), never 'ok'"""
    print('SKIP %s: %s' % (what, why))


def max_diff(a, b, scale=1.0):
    """largest |a - b| / scale of two runs' values (pandas Series or DataFrames, or arrays, of equal size; scale a number
    or an array of the same size). A value that is NaN (empty) or infinite in one run and not in the other is an infinite
    difference, so a comparison of an ensemble member or a restarted run never passes on values one of them lacks; empty
    in both (an observation column without data) is no difference."""
    import numpy as np
    a = np.asarray(a, dtype=float).ravel(); b = np.asarray(b, dtype=float).ravel()
    if a.shape != b.shape:
        return float('inf')
    na, nb = np.isnan(a), np.isnan(b); fa, fb = np.isfinite(a), np.isfinite(b)
    if (na != nb).any() or (fa != fb).any() or (a[~fa & ~na] != b[~fb & ~nb]).any():
        return float('inf')
    s = np.broadcast_to(np.asarray(scale, dtype=float).ravel() if np.ndim(scale) else np.asarray(scale, dtype=float), a.shape)
    d = np.abs(a[fa] - b[fa]) / s[fa]
    return float(d.max()) if d.size else 0.0


def _ulp(tok):
    """the unit of the last digit a number was written with (1e-5 for '127.90182', 1e-21 for '1.2345678901234567e-05'; 0 for
    a whole number written without a decimal point, which a writer of significant digits gives exactly)"""
    m = re.match(r'^[-+]?(\d*)(\.?)(\d*)(?:[eE]([-+]?\d+))?$', tok)
    if not m or (not m.group(2) and m.group(4) is None): return 0.0
    return 10.0 ** ((int(m.group(4)) if m.group(4) else 0) - len(m.group(3)))


def rvc_same(a, b):
    """two solution.rvc files hold the same state: the same text apart from the numbers; two numbers written with the same
    number of decimals must be the same, others may differ by the two roundings of one value (half a unit of the last digit
    of each, and a unit of a double for each number read back: a coupled run writes its states with 17 significant digits,
    a run without groundwater with fewer); the
    :GWVadoseColumnTops block
    (written with the unsaturated columns) is compared when both files hold it and left out when only one does; the
    method named on a :GWVadoseColumns or :GWVadoseClassColumns line is compared when both files name one"""
    if not (os.path.exists(a) and os.path.exists(b)): return False
    ta, tb = open(a).read(), open(b).read()
    meth = re.compile(r'^(:GWVadose(?:Class)?Columns) (RICHARDS|KINEMATIC|LAG)\b', re.M)
    if bool(meth.search(ta)) != bool(meth.search(tb)): ta, tb = meth.sub(r'\1', ta), meth.sub(r'\1', tb)
    tops = re.compile(r':GWVadoseColumnTops[^\n]*\n.*?:EndGWVadoseColumnTops\n', re.S)
    if bool(tops.search(ta)) != bool(tops.search(tb)): ta, tb = tops.sub('', ta), tops.sub('', tb)
    if ta == tb: return True
    sa, sb = re.split(r'([\s,]+)', ta), re.split(r'([\s,]+)', tb)
    if len(sa) != len(sb): return False
    for x, y in zip(sa, sb):
        if x == y: continue
        try:
            fx, fy = float(x), float(y)
        except ValueError:
            return False
        ux, uy = _ulp(x), _ulp(y)   # (two roundings of one value: each within half its last digit, and the two
                                    # numbers read back within a unit of a double each)
        if (ux == uy) or not (abs(fx - fy) <= 0.5 * (ux + uy) + 2.0 * math.ulp(max(abs(fx), abs(fy)))):
            return False
    return True


def same_output(a, b):
    """an output file of two runs is the same: byte for byte, solution.rvc by rvc_same"""
    import filecmp
    if not (os.path.exists(a) and os.path.exists(b)): return False
    if a.endswith('.rvc'): return rvc_same(a, b)
    return filecmp.cmp(a, b, shallow=False)


def restart_verdict(dev, restarted, continuous, complete=True):
    """a restart comparison passes: deviation below 1e-4 (NaN or infinite fails), every row compared (complete), and both
    the restarted and the continuous run (their tools_audit.audit results) without unconverged steps and with exact
    accounts (recharge identity and MODFLOW's cumulative residual below 1e-8)"""
    ok = bool(complete) and (dev < 1e-4)
    for A in (restarted, continuous):
        ok = ok and A.get('unconverged steps', 1) == 0 and abs(A.get('recharge: (Raven - MF6 - dStore - toCHD)/Raven', 1.0)) < 1e-8 \
            and abs(A.get('MF6 cumulative residual / gross flow', 1.0)) < 1e-8
    return bool(ok)


def work(*parts):
    """a path inside the scratch folder (parent folders created)"""
    p = os.path.join(WORK, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def copy_case(src, dest, duration=None):
    """fresh copy of an example folder (without outputs); optionally a shorter :Duration [d]"""
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('out', 'output', '__pycache__', '*.gwcache'))
    if duration is not None:
        rvi = os.path.join(dest, 'Liard.rvi')
        t = open(rvi).read()
        t = re.sub(r':Duration\s+\S+', ':Duration %s' % duration, t)
        open(rvi, 'w').write(t)
    return dest


def run(case, name='Liard', out='out', timeout=3600):
    """runs Raven in a case folder; returns the last 'Exiting Gracefully' message (or a crash note)"""
    os.makedirs(os.path.join(case, out), exist_ok=True)
    try:
        r = subprocess.run([RAVEN, name, '-o', out + '/'], cwd=case, capture_output=True, text=True, env=ENV, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'timeout'
    m = re.findall(r'Exiting Gracefully: (.*)', r.stdout + r.stderr)
    return m[-1] if m else '(no exit message; return code %d)' % r.returncode


def ext_models():
    """the synthetic 'existing' MODFLOW 6 models (metres/days in md/, feet/seconds in fs/, overlap weights in
    md/weights.rvg), built on first use into the scratch folder; returns that folder"""
    X = os.path.join(WORK, 'extmodel'); here = os.path.join(TESTS, 'existing')
    for units, sub in (('meters_days', 'md'), ('feet_seconds', 'fs')):
        if not os.path.exists(os.path.join(X, sub, 'mfsim.nam')):
            subprocess.run([sys.executable, os.path.join(here, 'make_ext_model.py'), os.path.join(X, sub), units], check=True)
    if not os.path.exists(os.path.join(X, 'md', 'weights.rvg')):
        subprocess.run([sys.executable, os.path.join(here, 'make_weights.py'), os.path.join(X, 'md'), os.path.join(X, 'md', 'weights.rvg')], check=True)
    return X

SETUP_EXT = os.path.join(TESTS, 'existing', 'setup_case.py')   # a Liard case coupled to one of those models


def liard_rvp_template():
    """the example's Liard.rvp with the calibrated aquifer values as placeholders (par_K_gravel, par_Sy_gravel,
    par_K_till), as the randomized tests expect"""
    t = open(os.path.join(LIARD, 'Liard.rvp')).read()
    t, n1 = re.subn(r'(\n\s*GRAVEL,\s*)50\.0(,\s*\S+,\s*\S+,\s*)0\.25', r'\1par_K_gravel\2par_Sy_gravel', t)
    t, n2 = re.subn(r'(\n\s*UPLAND_TILL,\s*)0\.2(,)', r'\1par_K_till\2', t)
    if n1 != 1 or n2 != 1:
        sys.exit('testconfig: the aquifer classes of %s/Liard.rvp are not the expected ones' % LIARD)
    return t


def quadtree_cells():
    """cell polygons of a quadtree grid of the Liard example (refined along the rivers), for imported-grid tests;
    made on first use by a one-day run and kept in the scratch folder"""
    f = os.path.join(WORK, 'qt_cells.geojson')
    if not os.path.exists(f):
        need_mf6()
        d = copy_case(LIARD, os.path.join(WORK, 'qt_cells_run'), duration=1)
        g = open(os.path.join(d, 'Liard.rvg')).read() + '\n:GridType QUADTREE\n:GridRefinement RIVERS 1000\n'
        open(os.path.join(d, 'Liard.rvg'), 'w').write(g)
        msg = run(d)
        if 'Successful' not in msg:
            sys.exit('testconfig: the quadtree run for qt_cells.geojson failed: ' + msg)
        shutil.copy(os.path.join(d, 'out', 'mf6', 'grid_cells.geojson'), f)
    return f


def sb52(d):
    """restricts the groundwater model of a copied Liard case to subbasin 52 (545 columns at 2 km): the smaller model of
    the grid, restart, lake and randomized tests (HRUs of the other subbasins get AQUIFER_PROFILE [NONE])"""
    p = os.path.join(d, 'Liard.rvh'); t = open(p).read()
    head, rest = t.split(':HRUs', 1); body, tail = rest.split(':EndHRUs', 1)
    lines = body.split('\n'); hdr = [l for l in lines if ':Attributes' in l][0].replace(',', ' ').split()[1:]
    ib, ia = hdr.index('BASIN_ID') + 1, hdr.index('AQUIFER_PROFILE') + 1
    out = []
    for l in lines:
        c = [x.strip() for x in l.split(',')]
        if len(c) > ia and c[0].isdigit() and c[ib] != '52':
            c[ia] = '[NONE]'; l = ', '.join(c)
        out.append(l)
    open(p, 'w').write(head + ':HRUs' + '\n'.join(out) + ':EndHRUs' + tail)
    return d


def grid_base():
    """base case of the grid tests (lake, restarts): the Liard example with groundwater under subbasin 52 only, 3 km
    cells, half-day time steps and a pumping well (5000 m3/d) and monitoring well; made once in the scratch folder"""
    d = os.path.join(WORK, 'grid_base')
    if os.path.exists(os.path.join(d, 'ready')):
        return d
    copy_case(LIARD, d); sb52(d)
    g = open(os.path.join(d, 'Liard.rvg')).read()
    g = re.sub(r':GridCellSize\s+\S+', ':GridCellSize       3000.0', g)
    # a pumping well and a monitoring well 250 m east of it, in the second-largest coupled HRU of subbasin 52
    import json
    from shapely.geometry import shape
    rvh = open(os.path.join(d, 'Liard.rvh')).read()
    hdr = [l for l in rvh.split('\n') if ':Attributes' in l and 'AQUIFER_PROFILE' in l][0].replace(',', ' ').split()[1:]
    ib, ia, ie, iar = hdr.index('BASIN_ID') + 1, hdr.index('AQUIFER_PROFILE') + 1, hdr.index('ELEVATION') + 1, hdr.index('AREA') + 1
    rows = [l.replace(',', ' ').split() for l in rvh.split(':HRUs')[1].split(':EndHRUs')[0].split('\n')]
    cand = sorted([r for r in rows if r and r[0].isdigit() and r[ib] == '52' and r[ia] != '[NONE]'], key=lambda r: -float(r[iar]))
    hid, el = int(cand[1][0]), float(cand[1][ie])
    geo = [f for f in json.load(open(os.path.join(d, 'Liard_HRUs_standin.geojson')))['features'] if int(f['properties']['HRU_ID']) == hid][0]
    pt = shape(geo['geometry']).representative_point()
    g += ('\n:Wells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT\n  1, PW_1, %.5f, %.5f, %.1f, %.1f\n:EndWells\n'
          ':ObservationWells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_ELEV\n  101, OW_NEAR, %.5f, %.5f, %.1f\n:EndObservationWells\n'
          % (pt.y, pt.x, el - 5, el - 25, pt.y, pt.x + 0.0044, el - 15))
    open(os.path.join(d, 'Liard.rvg'), 'w').write(g)
    t = open(os.path.join(d, 'Liard.rvi')).read()
    t = re.sub(r':TimeStep\s+\S+', ':TimeStep           12:00:00', t)
    open(os.path.join(d, 'Liard.rvi'), 'w').write(t)
    n = 7306   # daily values for the whole 20-year example (Raven time-series intervals must divide a day)
    open(os.path.join(d, 'Liard.rvt'), 'a').write('\n:WellFlowRate 1 m3/d\n  1985-10-01 00:00:00 1.0 %d\n' % n + '  -5000.0\n' * n + ':EndWellFlowRate\n')
    open(os.path.join(d, 'ready'), 'w').write('')
    return d
