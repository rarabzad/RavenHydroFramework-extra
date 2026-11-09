"""Spike Q1-Q3: what MODFLOW 6 does with package values changed
between outer iterations through XMI.

Q1: does writing the named input arrays (GHB BHEAD/COND, RCH RECHARGE) between solve() calls reach the solver
    (HCOF/RHS of the next iteration), or only writing BOUND?
Q2: are the package coefficients recomputed every outer iteration?
Q3: is a solve() after a converged solve() a normal iteration (no error, still converged, same heads)?

usage: python3 spike_xmi.py [LIBMF6 WORKDIR]   (default: the library and scratch folder of testconfig.py)
Quick mode (RAVEN_TEST_QUICK=1) and full mode run the same case: one time step of a 3 x 3 cell model is already the
smallest that answers Q1-Q3 (about a second).
"""
import os, sys, shutil
import numpy as np
import flopy
from xmipy import XmiWrapper

if len(sys.argv) >= 3:
    lib, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
else:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import testconfig as tc
    lib, work = os.path.abspath(tc.MF6LIB), tc.work('soilzone', 'spike')
shutil.rmtree(work, ignore_errors=True); os.makedirs(work)
print('spike: %s mode (the same single-step case in both)' % ('quick' if os.environ.get('RAVEN_TEST_QUICK', '') == '1' else 'full'))

sim = flopy.mf6.MFSimulation(sim_name='spk', sim_ws=work, exe_name='mf6')
flopy.mf6.ModflowTdis(sim, nper=1, perioddata=[(1.0, 1, 1.0)])
flopy.mf6.ModflowIms(sim, outer_maximum=50, inner_maximum=100, outer_dvclose=1e-8, inner_dvclose=1e-10,
                     linear_acceleration='BICGSTAB')
gwf = flopy.mf6.ModflowGwf(sim, modelname='m', newtonoptions='NEWTON')
flopy.mf6.ModflowGwfdis(gwf, nlay=1, nrow=3, ncol=3, delr=100.0, delc=100.0, top=10.0, botm=0.0)
flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=1.0)
flopy.mf6.ModflowGwfic(gwf, strt=5.0)
flopy.mf6.ModflowGwfsto(gwf, iconvert=1, sy=0.2, ss=1e-5, transient={0: True})
flopy.mf6.ModflowGwfghb(gwf, pname='SZX', maxbound=1, stress_period_data={0: [((0, 1, 1), 6.0, 100.0)]})
flopy.mf6.ModflowGwfrch(gwf, pname='RCH', maxbound=1, stress_period_data={0: [((0, 0, 0), 0.001)]})
sim.write_simulation(silent=True)

os.chdir(work)
mf = XmiWrapper(lib)
mf.initialize()
ver = mf.get_version() if hasattr(mf, 'get_version') else '?'
def addr(pkg, var):
    return mf.get_var_address(var, 'M', pkg)
def has(a):
    try:
        mf.get_var_rank(a); return True
    except Exception:
        return False
mf.prepare_time_step(1.0)
mf.prepare_solve(1)
names = {v: addr('SZX', v) for v in ('BHEAD', 'COND', 'BOUND', 'HCOF', 'RHS')}
avail = {v: has(a) for v, a in names.items()}
print('MODFLOW', ver, 'GHB vars available:', avail)
hcof = mf.get_value_ptr(names['HCOF']); rhs = mf.get_value_ptr(names['RHS'])
bound = mf.get_value_ptr(names['BOUND'])
OK = []
conv = mf.solve(1)
print('iter1  HCOF %.3f RHS %.3f  BOUND %s' % (hcof[0], rhs[0], bound.ravel()[:2]))

# Q1a: write the named input arrays only
if avail['BHEAD']:
    bh = mf.get_value_ptr(names['BHEAD']); cd = mf.get_value_ptr(names['COND'])
    bh[0] = 9.0; cd[0] = 50.0
    conv = mf.solve(1)
    print('iter2 after BHEAD/COND=9/50: HCOF %.3f RHS %.3f  BOUND %s  -> input arrays %s' % (
        hcof[0], rhs[0], bound.ravel()[:2], 'REACH the solver' if abs(hcof[0] + 50) < 1e-9 else 'do NOT reach the solver'))
    OK.append(abs(hcof[0] + 50) < 1e-9)
# Q1b: write BOUND (only meaningful for MODFLOW < 6.5, where no named input arrays exist)
if not avail['BHEAD']:
    b = bound.reshape(-1)
    b[0] = 7.0; b[1] = 25.0
    conv = mf.solve(1)
    ok_bound = abs(hcof[0] + 25) < 1e-9 and abs(rhs[0] + 25 * 7.0) < 1e-6
    print('iter3 after BOUND=7/25: HCOF %.3f RHS %.3f -> BOUND %s' % (hcof[0], rhs[0], 'REACHES the solver' if ok_bound else 'does NOT reach the solver'))
    OK.append(ok_bound)
else:
    bh[0] = 7.0; cd[0] = 25.0
    conv = mf.solve(1)
    print('Q2 coefficients recomputed each outer iteration: %s' % (abs(hcof[0] + 25) < 1e-9 and abs(rhs[0] + 175.0) < 1e-6))
    OK.append(abs(hcof[0] + 25) < 1e-9 and abs(rhs[0] + 175.0) < 1e-6)
# RCH: RECHARGE vs BOUND
ra = addr('RCH', 'RECHARGE'); rb = addr('RCH', 'BOUND'); rr = addr('RCH', 'RHS')
rrhs = mf.get_value_ptr(rr)
if has(ra):
    mf.get_value_ptr(ra)[0] = 0.002
    mf.solve(1)
    print('RCH RECHARGE=0.002 -> RHS %.3f (%s)' % (rrhs[0], 'reaches' if abs(rrhs[0] + 0.002 * 1e4) < 1e-9 else 'does NOT reach'))
    OK.append(abs(rrhs[0] + 0.002 * 1e4) < 1e-9)

# Q3: iterate to convergence, then solve again
for it in range(50):
    conv = mf.solve(1)
    if conv: break
x = mf.get_value_ptr(mf.get_var_address('X', 'M')).copy()
conv2 = mf.solve(1)
x2 = mf.get_value_ptr(mf.get_var_address('X', 'M')).copy()
print('Q3 converged=%s; solve after convergence: converged=%s, max head change %.2e' % (conv, conv2, np.abs(x2 - x).max()))
OK.append(bool(conv) and bool(conv2) and np.abs(x2 - x).max() < 1e-6)
mf.finalize_solve(1); mf.finalize_time_step(); mf.finalize()
print('spike: %s' % ('ALL PASSED' if all(OK) and len(OK) >= 3 else 'FAILED %s' % OK))
