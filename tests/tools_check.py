"""The helper tools and the comparison rules the tests rely on.

    python3 tools_check.py          (prints 'tool checks: ALL PASSED')

TC1 examples/Liard_groundwater/tools_audit.py on runs of one, two and three steps (sz_models, CONCEPTUAL, 4 HRUs): it
   finishes, takes the step as 1 day, and finds the recharge identity and MODFLOW's cumulative residual below 1e-8.
TC2 soilzone/mf6_to_feet.py on a generated model whose specified heads are whole numbers (HEAD 94: gwf.chd holds "94"),
   with a general-head boundary, a river, a well and a drain: it finishes, and the converted heads, river stages, bottoms,
   conductances and rates are (within 1e-8, flopy's written digits) the metre/day values times 3.280839895 (lengths), 3.280839895^2/86400 (conductances) and
   3.280839895^3/86400 (rates). A model it cannot convert whole stops with a message (no traceback): a well rate given as
   a time-series name, a recharge package, a DISV grid.
TC3 testconfig.max_diff, the comparison of an ensemble member or a restarted run with the single or continuous run: equal
   values give 0, a value that is NaN (or infinite) in one run and not in the other an infinite difference (a comparison
   then fails), NaN in both (an empty observation column) no difference.
TC4 testconfig.restart_verdict: a restart comparison fails when the continuous run (or the restarted run) has unconverged
   steps or inexact accounts, or the deviation is NaN.
TC5 testconfig.rvc_same, the comparison of solution.rvc with a reference build's: values written with 5 decimals and with 17
   significant digits are the same state when they agree to the 5 decimals; a value that differs in the 5th decimal, a
   whole number written as 200 against 199.6, a changed word, two 17-digit heads 1e-13 m apart, or a :GWVadoseColumnTops
   value that differs when both files hold the block are not; 481.457924970300 (12 decimals) and 481.4579249703005 (17
   digits), two roundings of one value 5.1e-13 apart, are; a block only one file holds is left out.
TC6 tools_audit checks the recharge identity on step 1: with 500 m3/d added to step 1's "recharge onto CHD cells" of the
   two-step run of TC1 (a copy of its output) the identity is off by more than 1e-6; with a recharge delay store
   (RECHARGE_DELAY 3 d, 3 steps) the store at the start is read from GWModelSummary.txt, the identity holds below 1e-8
   with step 1 checked, and the same step-1 change is found there too.
TC7 make_handover.found_note: HANDOVER.md's 1A-replace paragraph names the public branch's commits the kit does not hold
   only when the public check found them (their IDs and subjects), and says nothing about them otherwise.
Without the MODFLOW 6 library TC1, TC2 and TC6 print SKIP.
"""
import os, sys, re, shutil, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'soilzone'))
import numpy as np, pandas as pd
import testconfig as tc

W = os.path.dirname(tc.work('tools_check', 'x'))
fails = 0


def report(name, ok, detail=''):
    global fails
    print('%-78s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def t1_t2():
    import sz_models
    L, T = 3.280839895, 86400.0
    for n in (1, 2, 3):
        d = os.path.join(W, 't1_%d' % n); shutil.rmtree(d, ignore_errors=True)
        sz_models.make_case(d, nhru=4, slope=0.01, days=n, physical=False, chd=94.0)
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV)
        if 'Successful Simulation' not in r.stdout + r.stderr:
            report('TC1 tools_audit on a run of %d step(s)' % n, False, 'the run FAILED'); continue
        try:
            A = tc.audit.audit(os.path.join(d, 'out')); err = ''
        except Exception as ex:
            A, err = {}, '%s: %s' % (type(ex).__name__, ex)
        good = not err and A.get('time step [d]') == 1.0 and A.get('steps') == n and abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']) < 1e-8 \
            and abs(A['MF6 cumulative residual / gross flow']) < 1e-8
        report('TC1 tools_audit on a run of %d step(s)' % n, good, err or 'step %s d, recharge identity %.1e, residual %.1e' % (
            A.get('time step [d]'), A['recharge: (Raven - MF6 - dStore - toCHD)/Raven'], A['MF6 cumulative residual / gross flow']))
    # TC6: the recharge identity includes step 1
    def mutate(out_dir, name):
        m = os.path.join(W, name); shutil.rmtree(m, ignore_errors=True); shutil.copytree(out_dir, m, ignore=shutil.ignore_patterns('mf6'))
        p = os.path.join(m, 'GWBudget.csv'); L = open(p).read().split('\n'); h = [c.strip() for c in L[0].split(',')]
        i = h.index('recharge onto CHD cells [m3/d]'); v = L[1].split(','); v[i] = repr(float(v[i]) + 500.0); L[1] = ','.join(v)
        open(p, 'w').write('\n'.join(L)); return m
    key = 'recharge: (Raven - MF6 - dStore - toCHD)/Raven'
    m = mutate(os.path.join(W, 't1_2', 'out'), 't6_mut')
    A = tc.audit.audit(m); shutil.rmtree(m, ignore_errors=True)
    report('TC6 tools_audit: 500 m3/d more onto CHD cells on step 1 is found', abs(A[key]) > 1e-6 and not any('step 1 not checked' in k for k in A), 'recharge identity %.1e' % A[key])
    d = os.path.join(W, 't6_delay'); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=4, slope=0.01, days=3, physical=False, chd=94.0)
    p = os.path.join(d, 'm.rvp'); s = open(p).read()
    s = re.sub(r'(:AquiferProfileParameters\n  :Attributes, [^\n]*)\n  :Units, ([^\n]*)\n  AQ, ([^\n]*)\n', r'\1, RECHARGE_DELAY\n  :Units, \2, d\n  AQ, \3, 3.0\n', s)
    open(p, 'w').write(s)
    r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV)
    if 'Successful Simulation' not in r.stdout + r.stderr or 'RECHARGE_DELAY' not in s:
        report('TC6 tools_audit with a recharge delay store', False, 'the run FAILED')
    else:
        A = tc.audit.audit(os.path.join(d, 'out')); st = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
        st.columns = [c.strip() for c in st.columns]
        used = (st['recharge delay storage [m3]'] != 0).any()
        report('TC6 tools_audit with a recharge delay store: step 1 checked, identity exact', used and not any('step 1 not checked' in k for k in A) and abs(A[key]) < 1e-8,
               'store used %s, recharge identity %.1e' % (used, A[key]))
        m = mutate(os.path.join(d, 'out'), 't6_delay_mut'); shutil.copy(os.path.join(d, 'out', 'GWModelSummary.txt'), m)
        A = tc.audit.audit(m); shutil.rmtree(m, ignore_errors=True)
        report('TC6 tools_audit with a recharge delay store: the step-1 change is found', abs(A[key]) > 1e-6, 'recharge identity %.1e' % A[key])
    # TC2: whole-number heads (and the other list packages) in feet and seconds
    d = os.path.join(W, 't1_2'); m = os.path.join(d, 'out', 'mf6')
    if not os.path.exists(os.path.join(m, 'gwf.chd')):
        report('TC2 mf6_to_feet with whole-number heads', False, 'no generated model'); return
    src = os.path.join(W, 't2_m'); shutil.rmtree(src, ignore_errors=True); shutil.copytree(m, src)
    for f in os.listdir(src):
        if f.endswith(('.lst', '.hds', '.cache', '.rch', '.drn', '.evt')) or f == 'mfsim.stdout': os.remove(os.path.join(src, f))
    nam = open(os.path.join(src, 'gwf.nam')).read()
    nam = '\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|EVT_RAVEN', l))
    nam = nam.replace('END PACKAGES', '  GHB6  t2.ghb  GHB_T2\n  RIV6  t2.riv  RIV_T2\n  WEL6  t2.wel  WEL_T2\n  DRN6  t2.drn  DRN_T2\nEND PACKAGES')
    open(os.path.join(src, 'gwf.nam'), 'w').write(nam)
    chd = open(os.path.join(src, 'gwf.chd')).read()
    cell = re.findall(r'(?m)^\s+(\d+ \d+ \d+)\s+(\S+)\s*$', chd)
    whole = bool(cell) and all(re.match(r'^-?\d+$', h) for _, h in cell)
    c0 = cell[0][0] if cell else '1 2 2'
    body = 'BEGIN OPTIONS\nEND OPTIONS\nBEGIN DIMENSIONS\n  MAXBOUND 1\nEND DIMENSIONS\nBEGIN PERIOD 1\n  %s %s\nEND PERIOD\n'
    open(os.path.join(src, 't2.ghb'), 'w').write(body % ('1 2 3', '95 200'))
    open(os.path.join(src, 't2.riv'), 'w').write(body % ('1 2 4', '96 50 95'))
    open(os.path.join(src, 't2.wel'), 'w').write(body % ('1 2 5', '-150'))
    open(os.path.join(src, 't2.drn'), 'w').write(body % ('1 2 6', '94.5 300'))
    dst = os.path.join(W, 't2_ft'); shutil.rmtree(dst, ignore_errors=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'soilzone', 'mf6_to_feet.py'), src, dst], capture_output=True, text=True)
    if r.returncode != 0:
        report('TC2 mf6_to_feet with whole-number heads (gwf.chd "%s")' % (cell[0][1] if cell else '?'), False, r.stderr.strip().split('\n')[-1][:150]); return
    def first(f):
        t = open(os.path.join(dst, f)).read().split('BEGIN period')[-1] if 'BEGIN period' in open(os.path.join(dst, f)).read() else open(os.path.join(dst, f)).read().split('BEGIN PERIOD')[-1]
        return [float(x) for x in t.split('\n')[1].split()[3:]]
    got = {'chd': first('gwf.chd'), 'ghb': first('t2.ghb'), 'riv': first('t2.riv'), 'wel': first('t2.wel'), 'drn': first('t2.drn')}
    want = {'chd': [float(cell[0][1]) * L], 'ghb': [95 * L, 200 * L * L / T], 'riv': [96 * L, 50 * L * L / T, 95 * L], 'wel': [-150 * L ** 3 / T],
            'drn': [94.5 * L, 300 * L * L / T]}
    dev = max(abs(g - w) / abs(w) for k in want for g, w in zip(got[k], want[k])) if all(len(got[k]) == len(want[k]) for k in want) else float('inf')
    report('TC2 mf6_to_feet with whole-number heads (gwf.chd "%s") and GHB, RIV, WEL, DRN' % cell[0][1], whole and dev < 1e-8,
           'heads whole numbers: %s; converted values within %.1e' % (whole, dev))
    # TC2: models the tool cannot convert whole stop with a message (no traceback)
    def stops(name, prep, want):
        s2 = os.path.join(W, 't2_' + name); shutil.rmtree(s2, ignore_errors=True); shutil.copytree(src, s2); prep(s2)
        d2 = s2 + '_ft'; shutil.rmtree(d2, ignore_errors=True)
        r = subprocess.run([sys.executable, os.path.join(HERE, 'soilzone', 'mf6_to_feet.py'), s2, d2], capture_output=True, text=True)
        last = r.stderr.strip().split('\n')[-1] if r.stderr.strip() else ''
        report('TC2 mf6_to_feet stops: %s' % name, r.returncode != 0 and last.startswith('mf6_to_feet:') and want in last, last[:150])
        shutil.rmtree(s2, ignore_errors=True); shutil.rmtree(d2, ignore_errors=True)
    def ts(s2):
        open(os.path.join(s2, 't2.wel'), 'w').write(body.replace('BEGIN OPTIONS\n', 'BEGIN OPTIONS\n  TS6 FILEIN t2.ts\n') % ('1 2 5', 'pump'))
        open(os.path.join(s2, 't2.ts'), 'w').write('BEGIN ATTRIBUTES\n  NAME pump\n  METHOD STEPWISE\nEND ATTRIBUTES\nBEGIN TIMESERIES\n  0.0 -150\n  100.0 -150\nEND TIMESERIES\n')
    def rch(s2):
        p2 = os.path.join(s2, 'gwf.nam'); n2 = open(p2).read(); open(p2, 'w').write(n2.replace('END PACKAGES', '  RCH6  t2.rch  RCH_T2\nEND PACKAGES'))
        open(os.path.join(s2, 't2.rch'), 'w').write(body % ('1 2 5', '0.001'))
    def disv(s2):
        import flopy
        for f in os.listdir(s2): os.remove(os.path.join(s2, f))
        sim = flopy.mf6.MFSimulation(sim_ws=s2, verbosity_level=0); flopy.mf6.ModflowTdis(sim); flopy.mf6.ModflowIms(sim)
        g = flopy.mf6.ModflowGwf(sim, modelname='gwf')
        flopy.mf6.ModflowGwfdisv(g, nlay=1, ncpl=1, nvert=4, top=10.0, botm=[0.0], vertices=[[0, 0.0, 0.0], [1, 1.0, 0.0], [2, 1.0, 1.0], [3, 0.0, 1.0]],
                                 cell2d=[[0, 0.5, 0.5, 4, 0, 3, 2, 1]])
        flopy.mf6.ModflowGwfnpf(g); flopy.mf6.ModflowGwfic(g, strt=5.0); sim.write_simulation(silent=True)
    stops('a well rate given as a time-series name', ts, 'time-series name')
    stops('a recharge package', rch, 'RCH')
    stops('a DISV grid', disv, 'DISV')


def t3_t5():
    n = float('nan'); a = pd.Series([1.0, 2.0, 3.0])
    cases = (('equal values', a, a.copy(), 0.0), ('NaN in one run', a, pd.Series([1.0, n, 3.0]), float('inf')),
             ('NaN in the other run', pd.Series([n, 2.0, 3.0]), a, float('inf')), ('NaN in both runs', pd.Series([1.0, n]), pd.Series([1.0, n]), 0.0),
             ('a difference of 0.5', a, pd.Series([1.0, 2.5, 3.0]), 0.5), ('infinite in one run', a, pd.Series([1.0, np.inf, 3.0]), float('inf')))
    for name, x, y, want in cases:
        v = tc.max_diff(x, y)
        report('TC3 max_diff, %s' % name, v == want, '%s (want %s)' % (v, want))
    report('TC3 a NaN difference fails a comparison (v < 1e-4)', not (tc.max_diff(a, pd.Series([1.0, n, 3.0])) < 1e-4))
    good = {'unconverged steps': 0, 'recharge: (Raven - MF6 - dStore - toCHD)/Raven': 0.0, 'MF6 cumulative residual / gross flow': 1e-12}
    unc = dict(good, **{'unconverged steps': 3})
    for name, args, want in (('all good', (1e-6, good, good), True), ('the continuous run with unconverged steps', (1e-6, good, unc), False),
                             ('the restarted run with unconverged steps', (1e-6, unc, good), False), ('a NaN deviation', (n, good, good), False),
                             ('rows missing', (1e-6, good, good, False), False)):
        report('TC4 restart_verdict, %s' % name, tc.restart_verdict(*args) == want)
    p, q = os.path.join(W, 't5_a.rvc'), os.path.join(W, 't5_b.rvc')
    ref = ':HRUStateVariableTable\n  :Attributes,SOIL[0],SOIL[1]\n  1,127.90182,200.00000\n:EndHRUStateVariableTable\n:GWHeads 1 1 2\n  98.0999047411 97.5\n:EndGWHeads\n'
    for name, new, want in (('17 digits against 5 decimals', ref.replace('127.90182,200.00000', '127.90181815439453,200').replace('98.0999047411', '98.099904741067192'), True),
                            ('a difference in the 5th decimal', ref.replace('127.90182', '127.90171815439453'), False),
                            ('200 against 199.6', ref.replace('200.00000', '199.6'), False),
                            ('a changed word', ref.replace('SOIL[1]', 'SOIL[2]'), False)):
        open(p, 'w').write(ref); open(q, 'w').write(new)
        report('TC5 rvc_same, %s' % name, tc.rvc_same(p, q) == want)
    full = ref.replace('98.0999047411', '98.099904741067192')
    tops = ':GWVadoseColumnTops\n  1, 1, 1, 99.012345678901234, 0.25\n:EndGWVadoseColumnTops\n'
    for name, a_, b_, want in (('two 17-digit heads 1e-13 m apart', full, full.replace('98.099904741067192', '98.099904741067292'), False),
                               ('481.457924970300 against 481.4579249703005 (two roundings of one value)', full.replace('97.5', '481.457924970300'),
                                full.replace('97.5', '481.4579249703005'), True),
                               ('column tops in both files, the same', full + tops, full + tops, True),
                               ('column tops in both files, a top 1e-13 m apart', full + tops, full + tops.replace('99.012345678901234', '99.012345678901334'), False),
                               ('column tops in one file only', full + tops, full, True)):
        open(p, 'w').write(a_); open(q, 'w').write(b_)
        report('TC5 rvc_same, %s' % name, tc.rvc_same(p, q) == want)


def t7():
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools'))
    import make_handover as mh
    one = mh.found_note([('e03243d5' + '0' * 32, 'Upload the coupling')])
    many = mh.found_note([('%040x' % i, 'commit %d' % i) for i in range(5)])
    report('TC7 make_handover: no public commits found, nothing said about them', mh.found_note([]) == '')
    report('TC7 make_handover: the found commit is named by its ID and subject', '`e03243d5` "Upload the coupling"' in one and '1 commit,' in one, one)
    report('TC7 make_handover: five found commits, three named and the count', '5 commits' in many and 'and 2 more' in many, many[:120])


def main():
    if tc.MF6LIB and os.path.exists(tc.MF6LIB) and os.path.exists(tc.RAVEN):
        t1_t2()
    else:
        tc.skip('TC1, TC2 and TC6 (runs)', 'RAVEN_MF6_LIB not set')
    t3_t5()
    t7()
    print('tool checks: %s' % ('ALL PASSED' if fails == 0 else '%d FAILED' % fails))
    return fails == 0


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
