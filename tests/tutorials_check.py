"""Reruns the Raven-MODFLOW 6 tutorials (docs/tutorials/build_tutorials.py --check) and fails if any number quoted in the
tutorials, any output excerpt or diff shown in them, or any tutorial file differs from the committed ones.

    python3 tutorials_check.py [--quick]

Quick mode (--quick, or RAVEN_TEST_QUICK=1 as run_all.py --quick sets it) skips the 20-year Liard run of tutorial 1 and
the DDS calibration of tutorial 6: their committed values are kept, and the validation of the committed best parameter
set is rerun (about 10 minutes on two cores). Full mode also reruns those (about an hour more); the calibration needs an
OSTRICH executable in RAVEN_OSTRICH, otherwise it is checked as in quick mode and reported as SKIP.
Tutorial 1 runs the release package's installation check and Liard example: give the unpacked package (Raven_MF6_linux)
in RAVEN_PACKAGE, otherwise tutorial 1 is reported as SKIP and tutorials 2-6 are checked.
RAVEN_TUT_TOOLS names the tools folder of RavenHydroFramework-extra to use (make_prt.py, plot_soilzone.py; default:
../tools of this repository). Run times quoted in the tutorials are not compared. The last line is 'tutorials check: PASS' or 'tutorials check: FAIL'.
"""
import os, sys, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc

BUILD = os.path.join(tc.REPO, 'docs', 'tutorials', 'build_tutorials.py')


def main():
    tc.need_mf6()
    quick = '--quick' in sys.argv or os.environ.get('RAVEN_TEST_QUICK') == '1'
    pkg = os.environ.get('RAVEN_PACKAGE', '')
    ost = os.environ.get('RAVEN_OSTRICH', '')
    only = ['t1', 't2', 't3', 't4', 't5', 't6']
    if not (pkg and os.path.exists(os.path.join(pkg, 'bin'))):
        tc.skip('tutorial 1 (installation check, Liard example)', 'RAVEN_PACKAGE does not name the unpacked release package')
        only.remove('t1'); pkg = ''
    if not quick and not (ost and os.path.exists(ost)):
        tc.skip('tutorial 6 DDS calibration rerun', 'RAVEN_OSTRICH does not name an OSTRICH executable (committed record checked)')
    work = os.path.dirname(tc.work('tutorials', 'x'))
    argv = [sys.executable, BUILD, '--check', '--raven', tc.RAVEN, '--mf6lib', tc.MF6LIB, '--work', work, '--only', ','.join(only)]
    if pkg:
        argv += ['--package', pkg]
    if os.environ.get('RAVEN_TUT_TOOLS'):
        argv += ['--tools', os.environ['RAVEN_TUT_TOOLS']]
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
