"""Start-up diagnostic for layers that start completely dry (a generated model).

The Liard example with INITIAL_HEAD_DEPTH 25 m in the VALLEY_ALLUVIUM profile (gravel 15 m, clay till 5 m, confined sand
to bedrock): the initial water table lies below the clay till, so layer 2 (clay till, only in valley columns) starts dry
in every active cell, while layer 1 keeps wet upland-till cells and layer 3 is confined. Checks:
  D1  one warning naming layer 2 (and no other layer) and the remedies, and the line "dry at the start" in
      GWModelSummary.txt;
  D2  the same model with :GWInitialization STEADY_STATE: no warning (the steady-state period sets the heads);
  D3  the example as shipped (INITIAL_HEAD_DEPTH 3 m): no warning and no summary line; with RAVEN_EXE_REF its outputs,
      Raven_errors.txt and GWModelSummary.txt included (dates, paths and timings aside; solution.rvc the same state,
      testconfig.rvc_same), equal the reference build's (otherwise SKIP).
Runs of 2 days, in quick and full mode alike.
"""
import os, sys, re, shutil, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc   # noqa: E402

tc.need_mf6()
W = os.path.join(tc.WORK, 'dry_start')
fails = 0
WARN = 'starts dry: the initial head is at or below the bottom of all its'


def report(name, ok, detail=''):
    global fails
    print('%-64s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def case(name, depth=None, steady=False, exe=None):
    d = os.path.join(W, name)
    if os.path.exists(d):
        shutil.rmtree(d)
    shutil.copytree(tc.LIARD, d, ignore=shutil.ignore_patterns('out', '__pycache__', '*.gwcache'))
    p = os.path.join(d, 'Liard.rvi'); t = open(p).read()
    open(p, 'w').write(re.sub(r':Duration[ \t]+\S+([ \t]+\S+)?', ':Duration 2', t, count=1))
    if depth is not None:
        p = os.path.join(d, 'Liard.rvp'); t = open(p, newline='').read()
        t2 = re.sub(r'(VALLEY_ALLUVIUM,\s*)3\.0(,\s*60\.0)', r'\g<1>%.1f\2' % depth, t, count=1)
        assert t2 != t
        open(p, 'w', newline='').write(t2)
    if steady:
        open(os.path.join(d, 'Liard.rvg'), 'a').write('\n:GWInitialization STEADY_STATE 0.45\n')
    os.makedirs(os.path.join(d, 'out'))
    r = subprocess.run([exe or tc.RAVEN, 'Liard', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV)
    ok = 'Successful' in r.stdout + r.stderr
    rd = lambda f: open(os.path.join(d, 'out', f), errors='replace').read() if os.path.exists(os.path.join(d, 'out', f)) else ''
    return d, ok, rd('Raven_errors.txt'), rd('GWModelSummary.txt')


d, ok, err, summ = case('deep', depth=25.0)
w = [l for l in err.split('\n') if WARN in l]
report('D1 run with INITIAL_HEAD_DEPTH 25 m', ok)
report('D1 one warning, naming layer 2 and the remedies', len(w) == 1 and 'layer 2 starts dry' in w[0] and ':GWInitialization STEADY_STATE' in w[0]
       and 'INITIAL_HEAD_DEPTH' in w[0], (w[0].strip()[:140] if w else 'no warning'))
m = re.search(r'dry at the start\s*:\s*(.*)', summ)
report('D1 summary line "dry at the start"', bool(m) and m.group(1).startswith('layer 2 ('), m.group(1) if m else 'missing')
d, ok, err, summ = case('deep_steady', depth=25.0, steady=True)
report('D2 the same with :GWInitialization STEADY_STATE: no warning', ok and WARN not in err and 'dry at the start' not in summ)
d, ok, err, summ = case('shipped')
report('D3 the example as shipped: no warning, no summary line', ok and WARN not in err and 'dry at the start' not in summ)
if tc.REF:
    dr, okr, errr, summr = case('shipped_ref', exe=tc.REF)
    skip = re.compile(r'Build date|MODFLOW 6 files|HRU/grid linkage|Simulation time|elapsed', re.I)
    diffs = []
    for f in sorted(os.listdir(os.path.join(d, 'out'))):
        pa, pb = os.path.join(d, 'out', f), os.path.join(dr, 'out', f)
        if os.path.isdir(pa):
            continue
        if not os.path.exists(pb):
            diffs.append(f); continue
        if f.endswith('.rvc'):
            if not tc.rvc_same(pa, pb): diffs.append(f)
            continue
        la = [l for l in open(pa, 'rb').read().decode(errors='replace').split('\n') if not skip.search(l)]
        lb = [l for l in open(pb, 'rb').read().decode(errors='replace').split('\n') if not skip.search(l)]
        if la != lb:
            diffs.append(f)
    report('D3 outputs equal to RAVEN_EXE_REF (Raven_errors.txt, summary included)', okr and not diffs, ', '.join(diffs))
else:
    tc.skip('D3 shipped example against the reference build')
print('dry-start checks: ALL PASSED' if fails == 0 else 'dry-start checks: %d FAILED' % fails)
sys.exit(1 if fails else 0)
