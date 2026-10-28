"""The MODFLOW 6 version guard of Raven (CMF6Engine::CheckVersion in src/MF6Engine.cpp).

A stand-in library (mf6version_stub.c, compiled here) reports any version string through get_version (environment
variable STUB_MF6_VERSION) and fails in initialize, so each run stops right after the guard. For every string:
  - older than MF6_MIN_VERSION 6.5.0 -> the run stops with "the MODFLOW 6 library ... is version ...; the coupling needs
    MODFLOW 6 6.5.0 or newer (tested with 6.8.1)" (6.4.4, 6.4.99, "6", "6..9", "-1.0")
  - any other version than MF6_TESTED_VERSION 6.8.1 -> exactly one warning in Raven_errors.txt (6.9.0, 6.10.0, 6.5,
    6.5.0rc1, 99999999999.0.0), the run goes on (to the stand-in's failing initialize)
  - a version that cannot be read -> one warning quoting it ("abc", "v6.8.1"); an empty version and a
    library without get_version -> one warning
  - 6.8.1 and the same with blanks or suffixes (" 6.8.1", "6.8.1-dev", "6.8.1+abc.dirty", "6.08.01") -> no warning
Then a real 2-day run with the configured library (if any): completes, no version warning.
"""
import os, sys, re, shutil, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import testconfig as tc

W = tc.work('mf6version')
shutil.rmtree(W, ignore_errors=True); os.makedirs(W)
ok = True


def check(label, cond, detail=''):
    global ok
    print('%-66s %s %s' % (label, 'ok' if cond else 'FAIL', detail), flush=True); ok &= bool(cond)


here = os.path.dirname(os.path.abspath(__file__))
cc = shutil.which('cc') or shutil.which('gcc')
stub = os.path.join(W, 'libmf6_stub.so'); nover = os.path.join(W, 'libmf6_noversion.so')
for out, extra in ((stub, []), (nover, ['-DNO_GET_VERSION'])):
    r = subprocess.run([cc, '-shared', '-fPIC', '-o', out, os.path.join(here, 'mf6version_stub.c')] + extra, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('cannot compile mf6version_stub.c: ' + r.stderr)

case = tc.copy_case(tc.LIARD, os.path.join(W, 'case'), duration=2)
tc.sb52(case)                                        # the small groundwater model: the guard runs within seconds
GUARD = re.compile(r'MODFLOW 6 library .*(is version|does not report its version|reports a version that cannot be read)')


def run(lib, version, tag):
    out = 'out_%s' % tag
    os.makedirs(os.path.join(case, out), exist_ok=True)
    env = dict(tc.ENV); env['RAVEN_MF6_LIB'] = lib
    if version is not None:
        env['STUB_MF6_VERSION'] = version
    r = subprocess.run([tc.RAVEN, 'Liard', '-o', out + '/'], cwd=case, capture_output=True, text=True, env=env, timeout=1800)
    msg = (re.findall(r'Exiting Gracefully: (.*)', r.stdout + r.stderr) or ['(no exit message, rc %d)' % r.returncode])[-1]
    err = os.path.join(case, out, 'Raven_errors.txt')
    warns = [l for l in open(err).read().split('\n') if l.startswith('WARNING') and GUARD.search(l)] if os.path.exists(err) else []
    return msg, warns


REFUSED = ['6.4.4', '6.4.99', '6', '6..9', '-1.0']
WARNED = ['6.9.0', '6.10.0', '6.5', '6.5.0rc1', '99999999999.0.0']
UNREADABLE = ['abc', 'v6.8.1']
SILENT = ['6.8.1', ' 6.8.1', '6.8.1-dev', '6.8.1+abc.dirty', '6.08.01']
if os.environ.get('RAVEN_TEST_QUICK') == '1':
    REFUSED, WARNED, SILENT = ['6.4.4', '-1.0'], ['6.9.0', '6.10.0'], ['6.8.1', '6.8.1+abc.dirty']

n = 0
for v in REFUSED:
    n += 1; msg, warns = run(stub, v, n)
    check('version %-18r refused' % v, ('is version %s; the coupling needs MODFLOW 6 6.5.0 or newer (tested with 6.8.1)' % v) in msg,
          msg[:110])
for v in WARNED:
    n += 1; msg, warns = run(stub, v, n)
    check('version %-18r one warning, run goes on' % v, len(warns) == 1 and ('is version %s;' % v) in warns[0]
          and 'tested with MODFLOW 6 6.8.1' in warns[0] and 'initialize failed' in msg, (warns or [msg])[0][:110])
for v in UNREADABLE:
    n += 1; msg, warns = run(stub, v, n)
    check('version %-18r one warning quoting it' % v, len(warns) == 1 and ('cannot be read ("%s")' % v) in warns[0]
          and 'initialize failed' in msg, (warns or [msg])[0][:110])
n += 1; msg, warns = run(stub, '', n)
check('empty version: one warning', len(warns) == 1 and 'does not report its version' in warns[0] and 'initialize failed' in msg,
      (warns or [msg])[0][:110])
n += 1; msg, warns = run(nover, None, n)
check('no get_version: one warning', len(warns) == 1 and 'no get_version' in warns[0] and 'initialize failed' in msg,
      (warns or [msg])[0][:110])
for v in SILENT:
    n += 1; msg, warns = run(stub, v, n)
    check('version %-18r accepted without a warning' % v, not warns and 'initialize failed' in msg, (warns or [msg])[0][:110])

if tc.MF6LIB and os.path.exists(tc.MF6LIB):
    msg, warns = run(os.path.abspath(tc.MF6LIB), None, 'real')
    check('real library (%s): 2-day run completes, no version warning' % os.path.basename(tc.MF6LIB),
          'Successful' in msg and not warns, (warns or [msg])[0][:110])
else:
    tc.skip('real-library run', 'no MODFLOW 6 library configured')

print('version guard checks: %s' % ('ALL PASSED' if ok else 'FAILED'))
sys.exit(0 if ok else 1)
