"""Runs the whole verification suite and writes one report.

    python3 run_all.py            # everything (needs the MODFLOW 6 library; about an hour on one core)
    python3 run_all.py --nolib    # only the checks that do not need the MODFLOW 6 library (a few minutes)
    python3 run_all.py --quick    # everything in quick mode: smaller randomized rounds, and every script runs with
                                  # RAVEN_TEST_QUICK=1 (its smallest cases; the rough-terrain suite 40 seeds, the
                                  # Liard soil-zone run T7 30 days instead of 365)
    python3 run_all.py --only thiem,edge    # selected steps (names as in the report)

The USGS example-model steps need the MODFLOW 6 examples (mf6examples.zip from
https://github.com/MODFLOW-ORG/modflow6-examples/releases): export RAVEN_USGS_EXAMPLES=/path/to/mf6examples.zip

Settings come from testconfig.py (RAVEN_SRC, RAVEN_EXE, RAVEN_MF6_LIB, RAVEN_TEST_WORK). The report is written to
<scratch>/run_all_report.md, the full output of every step to <scratch>/run_all_logs/. The exit code is the number of
failed steps.

Mode: --quick (or RAVEN_TEST_QUICK=1 in the environment) sets RAVEN_TEST_QUICK=1 for every step; otherwise every step runs
with RAVEN_TEST_QUICK=0, its full mode, also when the variable is set to something else outside. The full mode runs the
rough-terrain suite as the manual reports it (regression cases + 400 seeds x NONE, RICHARDS, KINEMATIC and LAG, 1,620
runs) and again with three depth classes (--vzclasses 3).

Skipped checks: a script reports a check it could not make as one line "SKIP <what>: <why>" (testconfig.skip); each step
counts them, the report shows "PASS (k skipped)" and lists the lines, and the console summary gives the total. (Without
RAVEN_EXE_REF the byte-identity checks against a reference build are skipped this way.)

Each step is judged by what its script prints: a step passes when the script finishes without error and its own pass
criterion holds (all cases pass, all random set-ups pass, residuals and restart deviations within the manual's limits).
Steps that only report numbers for the manual (Thiem slopes, Liard grid table) pass when every run finishes and is
checked; their numbers are copied into the report for comparison with the manual.
"""
import os, sys, re, json, time, subprocess, glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc   # noqa: E402

NOLIB = '--nolib' in sys.argv
QUICK = ('--quick' in sys.argv) or (os.environ.get('RAVEN_TEST_QUICK', '') == '1')   # quick mode: --quick or RAVEN_TEST_QUICK=1
ONLY = None
for i, a in enumerate(sys.argv):
    if a == '--only' and i + 1 < len(sys.argv):
        ONLY = set(sys.argv[i + 1].split(','))

tc.ENV['RAVEN_TEST_QUICK'] = '1' if QUICK else '0'     # every step in the same mode
LOGS = os.path.join(tc.WORK, 'run_all_logs')
os.makedirs(LOGS, exist_ok=True)
PY = sys.executable
ROOT = tc.SRC   # Raven's source files (the unit tests compile some of them)


def sh(cmd, cwd=HERE, timeout=None):
    """runs a command; returns (return code, combined output)"""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=tc.ENV, timeout=timeout,
                           shell=isinstance(cmd, str))
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired as ex:
        out = (ex.stdout or b'')
        out = out.decode() if isinstance(out, bytes) else out
        return -9, out + '\n(timeout after %d s)' % timeout


# ---- pass criteria: each takes the output text and returns (passed, one-line summary) ----
def last_line(pat):
    def judge(out):
        m = re.findall(pat, out)
        return (bool(m), m[-1] if m else 'expected line not found: ' + pat)
    return judge


def n_of_n(pat):
    """'<k> of <n> ...' with k == n"""
    def judge(out):
        m = re.findall(pat, out)
        if not m:
            return False, 'summary line not found'
        k, n = map(int, m[-1][:2])
        return k == n, '%d of %d' % (k, n)
    return judge


def zero_failed(out):
    m = re.findall(r'(\d+) cases, (\d+) checks, (\d+) failed', out)
    if not m:
        return False, 'summary line not found'
    c, k, f = map(int, m[-1])
    return f == 0, '%d cases, %d checks, %d failed' % (c, k, f)


def no_word(word, summary_pat=None):
    def judge(out):
        bad = [l for l in out.split('\n') if word in l]
        s = re.findall(summary_pat, out)[-1] if summary_pat and re.findall(summary_pat, out) else ''
        return (not bad, ('%d lines with %s' % (len(bad), word)) if bad else ('no %s %s' % (word, s)).strip())
    return judge


def small_numbers(pat, limit, what):
    """every number captured by pat must be below limit"""
    def judge(out):
        v = [abs(float(x)) for x in re.findall(pat, out)]
        if not v:
            return False, 'no %s found' % what
        return max(v) < limit, '%d %s, largest %.1e (limit %.0e)' % (len(v), what, max(v), limit)
    return judge


def fuzz_json(paths_fn):
    """all randomized set-ups of the given results files must pass (restart comparisons included)"""
    def judge(out):
        P = paths_fn(); R = []
        for p in P:
            if not os.path.exists(p):
                return False, 'no results file ' + p
            R += json.load(open(p))
        k = sum(1 for r in R if str(r.get('pass')) == 'True')   # stored as JSON true or as the text 'True'
        nr = sum(1 for r in R if 'hotstart_dev' in r or r.get('restart'))
        return k == len(R) and len(R) > 0, '%d of %d set-ups pass, %d with a restart (%s)' % (
            k, len(R), nr, ', '.join(os.path.basename(p) for p in P))
    return judge


def thiem_judge(out):
    # every run must be checked (no failed steps); slopes are reported for the manual's Thiem table. Grids whose cells
    # are larger than the fitting window (regular 1000 m: four cells > 3 km) have no cells to fit and are not judged.
    fails = re.findall(r'failed (\d+)', out)
    fits = [l for l in out.split('\n') if 'slope error' in l]
    fitted = [l for l in fits if 'cells used 0' not in l]
    ok = bool(fitted) and all(f == '0' for f in fails)
    return ok, '%d grids fitted (%d with no cells in the window), %d runs with failed steps' % (
        len(fitted), len(fits) - len(fitted), sum(1 for f in fails if f != '0'))


# ---- the steps: (name, needs MODFLOW, command, pass criterion, timeout [s]) ----
# the USGS example models (mf6examples.zip of the MODFLOW 6 examples, or its unpacked folder): set RAVEN_USGS_EXAMPLES
USGS = os.environ.get('RAVEN_USGS_EXAMPLES', '')
FZ = [('3', '8')] if QUICK else [('11', '24'), ('21', '24'), ('22', '24')]     # (seed, set-ups) of the grid rounds
FZL = [('12', '4')] if QUICK else [('12', '12'), ('13', '12')]                  # rounds with a reservoir and lake refinement
FE = ('5', '6') if QUICK else ('5', '20')
cxx = 'g++ -std=c++11 -O2 -I%s' % ROOT
STEPS = [
    ('gridtest', False, '%s gridtest.cpp %s/GWGrid.cpp %s/GWGeometry.cpp -o %s/gridtest && %s/gridtest'
     % (cxx, ROOT, ROOT, LOGS, LOGS), last_line(r'ALL PASSED: 0 failures'), 600),
    ('geomtest', False, '%s geomtest.cpp %s/GWGeometry.cpp -o geomtest && %s geomtest_check.py'
     % (cxx, ROOT, PY), last_line(r'ALL PASSED'), 600),
    ('crs', False, 'cd existing && %s crstest.cpp %s/GWGeometry.cpp -o crstest && %s crs_check.py'
     % (cxx, ROOT, PY), small_numbers(r'worst ([0-9.e+-]+) m', 1e-3, 'worst position difference [m]'), 600),
    ('crs_inputs_nolib', False, [PY, 'crs_inputs.py', '--nolib'], last_line(r'crs inputs: ALL PASSED'), 600),
    ('crs_inputs', True, [PY, 'crs_inputs.py'], last_line(r'crs inputs: ALL PASSED'), 1800),
    ('dry_start', True, [PY, 'dry_start.py'], last_line(r'dry-start checks: ALL PASSED'), 1800),
    ('mf6files', False, [PY, 'mf6files_check.py'], zero_failed, 3600),
    ('mf6lib_unit', False, [PY, 'mf6lib_check.py', '--unit'], last_line(r'library unit checks: ALL PASSED'), 600),
    ('mf6lib', True, [PY, 'mf6lib_check.py'], last_line(r'library checks: ALL PASSED'), 1800),
    ('mf6version', False, [PY, 'mf6version_check.py'], last_line(r'version guard checks: ALL PASSED'), 1800),
    ('cmake', False, [PY, 'cmake_checks.py', '--src', tc.RAVEN_ROOT], last_line(r'cmake checks: ALL PASSED.*'), 1800),
    ('edge_nolib', False, [PY, 'edge.py', '--nolib'], n_of_n(r'(\d+) of (\d+) cases pass'), 3600),
    ('edge', True, [PY, 'edge.py'], n_of_n(r'(\d+) of (\d+) cases pass'), 4 * 3600),
    ('thiem', True, '%s thiem/run_thiem.py && %s thiem/fit_thiem.py' % (PY, PY), thiem_judge, 6 * 3600),
    ('restart', True, [PY, 'restart_test.py'], small_numbers(r'restart deviation ([0-9.e+-]+)', 1e-4, 'restart deviations'), 4 * 3600),
    ('lake', True, [PY, 'lake_test.py'], no_word('FAIL'), 4 * 3600),
    ('liard_grids', True, [PY, 'liard_grids.py'], no_word('FAILED', r'results in .*'), 6 * 3600),
    ('behaviour', True, [PY, 'behaviour_check.py'], last_line(r'behaviour checks: ALL PASSED'), 3 * 3600),
    ('budget_xcheck', True, lambda: [PY, 'budget_xcheck.py'] + sorted(glob.glob(os.path.join(tc.WORK, 'liard_grids', '*', 'out'))
                                    + glob.glob(os.path.join(tc.WORK, 'lake', '*', 'out')) + glob.glob(os.path.join(tc.WORK, 'behaviour', 'reservoir', 'out'))),
     small_numbers(r'WORST relative difference .*: ([0-9.e+-]+)', 1e-6, 'worst differences'), 1800),
    ('fuzz_grids', True, ' && '.join('%s fuzz_grids.py %s %s' % (PY, s, n) for s, n in FZ),
     fuzz_json(lambda: [os.path.join(tc.WORK, 'fuzz', 'results_%s.json' % s) for s, _ in FZ]), 12 * 3600),
    ('fuzz_lakes', True, ' && '.join('%s fuzz_grids.py %s %s lakes' % (PY, s, n) for s, n in FZL),
     fuzz_json(lambda: [os.path.join(tc.WORK, 'fuzz', 'results_%s_lakes.json' % s) for s, _ in FZL]), 12 * 3600),
    ('ext_guards', True, [PY, 'existing/guards.py'], n_of_n(r'(\d+) of (\d+) behave as required'), 3 * 3600),
    ('ext_roundtrip', True, [PY, 'existing/roundtrip.py'],
     small_numbers(r'max relative difference ([0-9.e+-]+)', 1e-4, 'round-trip differences'), 3 * 3600),
    ('ext_restart', True, [PY, 'existing/restart_ext.py'],
     small_numbers(r'max deviation ([0-9.e+-]+)', 1e-4, 'restart deviations'), 3 * 3600),
    ('ext_exchanges', True, [PY, 'existing/ext_exchanges.py'], last_line(r'existing-model exchanges: ALL PASSED'), 3 * 3600),
    ('ext_inputs', True, [PY, 'existing/ext_inputs.py'], last_line(r'existing-model input forms: ALL PASSED'), 3 * 3600),
    ('budget_file', True, [PY, 'budget_file.py'], last_line(r'budget file checks: ALL PASSED'), 3600),
    ('usgs_sagehen', True, lambda: [PY, 'existing/usgs_sagehen.py', USGS], last_line(r'Sagehen checks: ALL PASSED'), 6 * 3600),
    ('usgs_capture', True, lambda: [PY, 'existing/usgs_capture.py', USGS], last_line(r'capture checks: ALL PASSED'), 3 * 3600),
    ('ext_fuzz', True, [PY, 'existing/fuzz_ext.py', FE[0], FE[1]],
     fuzz_json(lambda: [os.path.join(tc.WORK, 'extmodel', 'fz_results_%s.json' % FE[0])]), 12 * 3600),
    # :SoilZone PHYSICAL (docs/design/soil_zone_coupling_plan.md section 9)
    ('soilzone_unit', False, '%s soilzone/soilzone_unit.cpp %s/GWSoilZone.cpp -o %s/soilzone_unit && %s/soilzone_unit'
     % (cxx, ROOT, LOGS, LOGS), last_line(r'soil-zone unit tests: \d+ checks, 0 failed'), 600),
    ('soilzone_check_selftest', False, [PY, 'soilzone/sz_check.py'], last_line(r'vz_identity self-test: .* -> ok'), 300),
    ('soilzone_spike', True, [PY, 'soilzone/spike_xmi.py'], last_line(r'spike: ALL PASSED'), 1800),
    ('soilzone_column', True, [PY, 'soilzone/test_column.py'], last_line(r'column tests: ALL PASSED'), 1800),
    ('soilzone_hillslope', True, [PY, 'soilzone/test_hillslope.py', '--selftest'], last_line(r'T2/T3 hillslope: PASS'), 1800),
    ('soilzone_dynamics', True, [PY, 'soilzone/test_dynamics.py'], last_line(r'dynamics tests: ALL PASSED'), 3600),
    ('soilzone_restart', True, [PY, 'soilzone/test_restart.py'], last_line(r'restart test: PASS'), 1800),
    ('soilzone_inputs', True, [PY, 'soilzone/test_inputs.py'], last_line(r'input tests: ALL PASSED'), 1800),
    ('soilzone_robustness', True, [PY, 'soilzone/test_robustness.py'], last_line(r'robustness tests: ALL PASSED'), 3600),
    ('soilzone_interface_stiff', True, [PY, 'soilzone/test_interface_stiff.py'], last_line(r'stiff interface tests: ALL PASSED'), 3600),
    ('soilzone_confined_wet', True, [PY, 'soilzone/test_confined_wet.py'], last_line(r'confined-cell tests: ALL PASSED'), 3600),
    ('soilzone_columns_mf6', True, [PY, 'soilzone/test_columns_mf6.py'], last_line(r'columns and MODFLOW side: ALL PASSED'), 1800),
    ('soilzone_mf6_budget', True, [PY, 'soilzone/test_mf6_budget.py'], last_line(r'MODFLOW budget tests: ALL PASSED'), 3600),
    # unsaturated columns, capillary rise (docs/design/soil_zone_columns_plan.md section 8)
    ('soilzone_vadose_unit', False, '%s soilzone/vadose_unit.cpp %s/GWVadose.cpp -o %s/vadose_unit && %s/vadose_unit %s/vadose_drain.txt && %s soilzone/vadose_ref.py %s/vadose_drain.txt'
     % (cxx, ROOT, LOGS, LOGS, LOGS, PY, LOGS), last_line(r'vadose reference: PASS'), 900),
    ('soilzone_models', True, [PY, 'soilzone/test_sz_models.py'], last_line(r'soil-zone model tests: ALL PASSED'), 3600),
    # :SoilZoneVadose KINEMATIC (docs/design/soil_zone_kinematic.md)
    ('soilzone_vz_kinematic', True, [PY, 'soilzone/test_vz_kinematic.py'], last_line(r'kinematic tests: ALL PASSED'), 3600),
    ('soilzone_vz_lag', True, [PY, 'soilzone/test_vz_lag.py'], last_line(r'LAG tests: ALL PASSED'), 1800),
    ('soilzone_vz_classes', True, [PY, 'soilzone/test_vz_classes.py'], last_line(r'vz classes tests: ALL PASSED'), 3600),
    ('soilzone_vz_initial', True, [PY, 'soilzone/test_vz_initial.py'], last_line(r'initial-state tests: ALL PASSED'), 3600),
    ('soilzone_rough_terrain', True, [PY, 'soilzone/test_rough_terrain.py'] + (['--quick'] if QUICK else []) + ['--methods', 'NONE,RICHARDS,KINEMATIC,LAG'],
     last_line(r'rough terrain: \d+ runs, 0 failed'), 4 * 3600),
    ('soilzone_rough_terrain_k3', True, [PY, 'soilzone/test_rough_terrain.py'] + (['--quick'] if QUICK else []) + ['--methods', 'NONE,RICHARDS,KINEMATIC,LAG', '--vzclasses', '3'],
     last_line(r'rough terrain: \d+ runs, 0 failed'), 4 * 3600),
    ('soilzone_models_ext', True, [PY, 'soilzone/test_sz_models_ext.py'], last_line(r'soil-zone existing-model tests: ALL PASSED'), 3600),
    ('soilzone_liard', True, [PY, 'soilzone/test_liard_physical.py'] + ([] if QUICK else ['365']), last_line(r'T7 Liard physical: PASS'), 4 * 3600),
]

have_lib = bool(tc.MF6LIB) and os.path.exists(tc.MF6LIB)
if not NOLIB and not have_lib:
    print('RAVEN_MF6_LIB is not set to the MODFLOW 6 library: running only the checks that do not need it (--nolib).')
    NOLIB = True
if not os.path.exists(tc.RAVEN):
    sys.exit('Raven not found at %s: build RavenHydroFramework beside this repository, or set RAVEN_SRC or RAVEN_EXE' % tc.RAVEN)

rows = []
t_all = time.time()
for name, needs_lib, cmd, judge, timeout in STEPS:
    if ONLY and name not in ONLY:
        continue
    if needs_lib and NOLIB:
        rows.append((name, 'skipped', 0, 'needs the MODFLOW 6 library', ''))
        continue
    if name.startswith('usgs') and not USGS:
        rows.append((name, 'skipped', 0, 'set RAVEN_USGS_EXAMPLES to mf6examples.zip (MODFLOW 6 examples)', ''))
        continue
    print('%-14s ...' % name, end=' ', flush=True)
    t0 = time.time()
    rc, out = sh(cmd() if callable(cmd) else cmd, timeout=timeout)
    dt = time.time() - t0
    open(os.path.join(LOGS, name + '.txt'), 'w').write(out)
    ok, summary = judge(out)
    if rc != 0:
        ok, summary = False, 'exit code %d; %s' % (rc, summary)
    skips = [l.strip() for l in out.split('\n') if l.strip().startswith('SKIP ')]     # testconfig.skip lines
    status = ('PASS' if ok else 'FAIL') + (' (%d skipped)' % len(skips) if skips else '')
    print('%s  %s  (%.0f s)' % (status, summary, dt), flush=True)
    tail = '\n'.join([l for l in out.strip().split('\n') if 'Warning' not in l and 'warn(' not in l][-25:])
    if skips:
        tail = 'skipped checks:\n' + '\n'.join('  ' + s for s in skips) + '\n---\n' + tail
    rows.append((name, status, dt, summary, tail))

# with --only, the report keeps the earlier results of the steps not run this time (each row shows when it ran)
RES = os.path.join(tc.WORK, 'run_all_results.json')
now = time.strftime('%Y-%m-%d %H:%M')
rows = [tuple(r) + (now,) for r in rows]                      # this run's steps
if ONLY and os.path.exists(RES):
    old = {r[0]: tuple(r) for r in json.load(open(RES))}
    new = {r[0]: r for r in rows}
    rows = [new.get(n, old.get(n)) for n in [s[0] for s in STEPS] if n in new or n in old]
json.dump([list(r) for r in rows], open(RES, 'w'), indent=1)
rep = os.path.join(tc.WORK, 'run_all_report.md')
with open(rep, 'w') as f:
    f.write('# Verification report\n\n')
    f.write('- Raven: `%s`\n- MODFLOW 6 library: `%s`\n- scratch folder: `%s`\n- date: %s\n- mode: %s\n\n' % (
        tc.RAVEN, tc.MF6LIB if have_lib else '(not used)', tc.WORK, time.strftime('%Y-%m-%d %H:%M'),
        'no library' if NOLIB else ('quick' if QUICK else 'full')))
    f.write('| Step | Result | Time [s] | Summary | Run |\n|---|---|---|---|---|\n')
    for name, status, dt, summary, _, when in rows:
        f.write('| %s | %s | %.0f | %s | %s |\n' % (name, status, dt, summary.replace('|', '/'), when))
    f.write('\nTotal time %.0f s. Full output of each step: `%s/<step>.txt`.\n' % (time.time() - t_all, LOGS))
    f.write('\nNumbers reported in the manual come from: `thiem` (Table "Thiem test"), `liard_grids` (Table "The Liard '
            'model on each grid"), `restart`, `lake` and the randomized steps (chapter "Verification").\n')
    for name, status, dt, summary, tail, when in rows:
        if tail:
            f.write('\n## %s (%s)\n\n```\n%s\n```\n' % (name, status, tail))
nskip = sum(int(re.findall(r'\((\d+) skipped\)', r[1])[0]) for r in rows if 'skipped)' in r[1])
print('steps: %d passed, %d failed, %d not run; %d checks skipped inside passing or failing steps'
      % (sum(1 for r in rows if r[1].startswith('PASS')), sum(1 for r in rows if r[1].startswith('FAIL')),
         sum(1 for r in rows if r[1] == 'skipped'), nskip))
print('report:', rep)
sys.exit(sum(1 for r in rows if r[1].startswith('FAIL')))
