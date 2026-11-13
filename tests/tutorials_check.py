"""Reruns the Raven-MODFLOW 6 workshops (docs/tutorials/build_tutorials.py --check) and fails if any number quoted in the
workshops, any output excerpt or diff shown in them, any model file, helper script, preamble copy or bin/README.txt
differs from the committed ones, or if a workshop's committed tex/ no longer compiles standalone without LaTeX warnings.

    python3 tutorials_check.py [--quick]

Quick mode (--quick, or RAVEN_TEST_QUICK=1 as run_all.py --quick sets it) skips the 20-year Liard run of workshop 1 and
the DDS calibration of workshop 6: their committed values are kept, and the validation of the committed best parameter
set is rerun (about 10 minutes on two cores). Full mode also reruns those (about an hour more); the calibration needs an
OSTRICH executable in RAVEN_OSTRICH, otherwise it is checked as in quick mode and reported as SKIP.
Workshop 1 ships cmake/RavenMF6InstallCheck.py of the Raven checkout (RAVEN_SRC); the copy is compared with it.
RAVEN_TUT_TOOLS names the tools folder of RavenHydroFramework-extra to use (make_prt.py, plot_soilzone.py; default:
../tools of this repository). Without pdflatex, the LaTeX compile is skipped (reported as SKIP). Run times quoted in the
workshops are not compared. The last line is 'tutorials check: PASS' or 'tutorials check: FAIL'.
"""
import os, shutil, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc

BUILD = os.path.join(tc.REPO, 'docs', 'tutorials', 'build_tutorials.py')


def main():
    tc.need_mf6()
    quick = '--quick' in sys.argv or os.environ.get('RAVEN_TEST_QUICK') == '1'
    ost = os.environ.get('RAVEN_OSTRICH', '')
    if not quick and not (ost and os.path.exists(ost)):
        tc.skip('workshop 6 DDS calibration rerun', 'RAVEN_OSTRICH does not name an OSTRICH executable (committed record checked)')
    work = os.path.dirname(tc.work('tutorials', 'x'))
    argv = [sys.executable, BUILD, '--check', '--raven', tc.RAVEN, '--mf6', tc.MF6LIB, '--work', work]
    if os.path.exists(os.path.join(tc.RAVEN_ROOT, 'cmake', 'RavenMF6InstallCheck.py')):
        argv += ['--raven-src', tc.RAVEN_ROOT]
    if os.environ.get('RAVEN_TUT_TOOLS'):
        argv += ['--tools', os.environ['RAVEN_TUT_TOOLS']]
    if not shutil.which('pdflatex'):
        tc.skip('LaTeX compile of the workshops', 'pdflatex not found')
        argv += ['--no-pdf']
    if quick:
        argv += ['--quick']
    elif ost and os.path.exists(ost):
        argv += ['--ostrich', ost]
    print('running: ' + ' '.join(argv), flush=True)
    r = subprocess.run(argv, env=tc.ENV)
    print('tutorials check: %s' % ('PASS' if r.returncode == 0 else 'FAIL'))
    sys.exit(r.returncode)


if __name__ == '__main__':
    main()
