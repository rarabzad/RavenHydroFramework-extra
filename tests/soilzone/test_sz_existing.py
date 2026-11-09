"""The soil zone with an existing MODFLOW 6 model, and columns over specified heads (manual, "The soil zone and the
water table" and "Coupling an existing MODFLOW 6 model").

X1  round trip: the T2/T3 hillslope run with :SoilZone PHYSICAL; its MODFLOW model (without Raven's packages) is then
    coupled as an existing model (:MF6Simulation) with the same soil zone. Flows agree within the interface
    tolerances (relative 1e-3), and every identity holds.
X2  the same with the existing model converted to feet and seconds (unit factors of heads, conductances and rates).
X4  a specified-head toe with capillary rise off.
X3  the same with a specified-head toe (columns over specified heads; in the existing model they become specified
    heads through its own CHD package), unsaturated columns (:SoilZoneAquiferClass) and three column classes.
X5  outputs of the x3 runs: no rejection where the saturated fraction is 0; run totals at the end of GWModelSummary.txt.
X6  start-up stops: an existing model without NEWTON (required with :SoilZone PHYSICAL); a MODFLOW 6 input error (CG with
    NEWTON) reported from MODFLOW's list file.
X7  specific yield of an existing model: the x1 model with a confined STO package (ICONVERT 0, no
    SY: MODFLOW holds SY 0) keeps its SY, floored at 0.01 for the release limits and the columns, with a warning naming
    the floor; the x1 model without STO assumes 0.2, the warning naming the soil-zone checks, release limits and columns.
X8  a steady existing model (the x7 model without STO) with :SoilZoneAquiferClass: the class's SPEC_YIELD (0.1) replaces
    the 0.2 (warning naming it; the Sy/drainable-porosity range of GWModelSummary.txt halves; identities hold); a class
    without SPEC_YIELD keeps 0.2 (the outputs of the x7 run without a class, byte for byte); with RAVEN_EXE_REF the x7 run
    without a class is byte-identical to the reference build (otherwise SKIP).
Quick mode (RAVEN_TEST_QUICK=1): the round trips X1-X4 (and X5-X7, which use their runs) cover the first 120 days of the
hillslope's rain instead of all 300; the checks are the same.
"""
import os, sys, shutil, re, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check
from test_hillslope import CFG, RAIN

W = sz_check.tc.work('soilzone', 'sz_existing')
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
SHORT = dict(days=120, rain=RAIN[:120]) if QUICK else {}   # (quick mode: the round trips' length)
LIM = dict(sz_check.ID_LIMITS)   # (the standard limits of the identities: recharge 5e-9, soil zone and unsaturated zone 1e-8)
COLS = ['MF6 recharge [m3/d]', 'soil zone to aquifer [m3/d]', 'aquifer to soil zone [m3/d]', 'rejected recharge [m3]',
        'soil-zone exchange applied to Raven [m3]', 'storage release [m3/d]']

def roundtrip(name, extra='', feet=False, **over):
    cfg = dict(CFG); cfg.update(over); cfg['extra_rvg'] = extra
    g = os.path.join(W, name + '_gen'); shutil.rmtree(g, ignore_errors=True); sz_models.make_case(g, **cfg)
    ok, txt = sz_check.run(g)
    if not ok:
        print('  %s: generated run FAILED\n%s' % (name, txt[-1500:])); return False
    m = os.path.join(W, name + '_model'); shutil.rmtree(m, ignore_errors=True); shutil.copytree(os.path.join(g, 'out', 'mf6'), m)
    for f in ('gwf.rch', 'gwf.drn', 'gwf.szx', 'gwf.szq', 'gwf.szd', 'linkage.cache', 'mfsim.lst', 'gwf.lst', 'gwf.hds', 'gwf.cbc'):
        if os.path.exists(os.path.join(m, f)): os.remove(os.path.join(m, f))
    nam = open(os.path.join(m, 'gwf.nam')).read()
    open(os.path.join(m, 'gwf.nam'), 'w').write('\n'.join(l for l in nam.split('\n') if not re.search('RCH_RAVEN|DRN_RAVEN|SZX_RAVEN|SZQ_RAVEN|SZD_RAVEN|SZW_RAVEN', l)))
    if feet:
        subprocess.run([sys.executable, os.path.join(HERE, 'mf6_to_feet.py'), m, m + '_ft'], check=True, capture_output=True); m = m + '_ft'
    e = os.path.join(W, name + '_ext'); shutil.rmtree(e, ignore_errors=True); sz_models.make_case(e, **cfg)
    shutil.copy(os.path.join(g, 'out', 'mf6', 'grid_cells.geojson'), os.path.join(e, 'cells.geojson'))
    rvg = open(os.path.join(e, 'm.rvg')).read()
    rvg = '\n'.join(l for l in rvg.split('\n') if not l.startswith((':GridCellSize', ':SolverHeadTolerance', ':SpecifiedHeadBoundary')))
    rvg += '\n:MF6Simulation %s/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:SeepageToRaven ON\n' % m
    open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
    ok, txt = sz_check.run(e)
    if not ok:
        print('  %s: existing-model run FAILED\n%s' % (name, txt[-2500:])); return False
    good = True
    for d, lab in ((g, 'generated'), (e, 'existing')):
        r = sz_check.checks(d); print('  %s %s:' % (name, lab))
        good &= sz_check.report(lab, r, {k: v for k, v in LIM.items() if k in r})
    a, b = pd.read_csv(os.path.join(g, 'out', 'GWBudget.csv')), pd.read_csv(os.path.join(e, 'out', 'GWBudget.csv'))
    cols = COLS + ([c for c in ('soil zone to specified heads [m3/d]', 'specified heads to soil zone [m3/d]', 'unsaturated zone inflow [m3]') if c in a and c in b])
    worst = max((a[c] - b[c]).abs().max() / max(a[c].abs().max(), 1.0) for c in cols)
    ok2 = worst < 1e-3
    print('  %s: largest relative difference of the flows, generated vs existing model %.2e -> %s' % (name, worst, 'ok' if ok2 else 'FAIL'))
    return good and ok2

def outputs_x3():
    """X5, on the x3 runs (unsaturated columns, a specified-head toe): GWSoilExchange.csv
    rejects recharge only where the HRU's saturated fraction is positive (the fraction is over all the HRU's columns, those
    over specified heads included, as the rejected recharge), and GWModelSummary.txt ends with the run totals, the
    unsaturated columns' substeps counted (they were written at the start, always 0)"""
    good = True
    for lab in ('gen', 'ext'):
        o = os.path.join(W, 'x3_' + lab, 'out')
        s = pd.read_csv(os.path.join(o, 'GWSoilExchange.csv'))
        bad = s[(s['rejected recharge [mm]'] > 1e-9) & (s['saturated fraction [-]'] <= 0.0)]
        summ = open(os.path.join(o, 'GWModelSummary.txt')).read()
        m = re.search(r'Run totals \(end of run\)[\s\S]*unsaturated columns\s*:\s*(\d+) substeps', summ)
        ok = bad.empty and bool(m) and int(m.group(1)) > 0
        print('  X5 %s: rows with rejection and F = 0: %d; run totals with %s substeps -> %s'
              % (lab, len(bad), m.group(1) if m else 'no', 'ok' if ok else 'FAIL'))
        good &= ok
    return good

def stops_x6():
    """X6: the x1 existing model without NEWTON stops at start-up with :SoilZone PHYSICAL
    (NEWTON required); with NEWTON and CG instead of BICGSTAB MODFLOW 6 stops inside its library while reading the model
    (an input error, exit code 2) and Raven reports MODFLOW's error report"""
    m0, e0 = os.path.join(W, 'x1_model'), os.path.join(W, 'x1_ext')
    good = True
    for case in ('nonewton', 'cg'):
        m, e = os.path.join(W, 'x6_%s_model' % case), os.path.join(W, 'x6_%s_ext' % case)
        for a, b in ((m0, m), (e0, e)): shutil.rmtree(b, ignore_errors=True); shutil.copytree(a, b, ignore=shutil.ignore_patterns('out'))
        if case == 'nonewton':
            nam = open(os.path.join(m, 'gwf.nam')).read(); open(os.path.join(m, 'gwf.nam'), 'w').write(re.sub(r'(?m)^\s*NEWTON.*$', '', nam))
        else:
            for f in os.listdir(m):
                if f.lower().endswith('.ims'):
                    t = open(os.path.join(m, f)).read(); open(os.path.join(m, f), 'w').write(re.sub(r'(?i)LINEAR_ACCELERATION\s+\S+', 'LINEAR_ACCELERATION CG', t))
        rvg = open(os.path.join(e, 'm.rvg')).read().replace(m0 + '/mfsim.nam', m + '/mfsim.nam'); open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
        ok, txt = sz_check.run(e)
        err = open(os.path.join(e, 'out', 'Raven_errors.txt')).read() if os.path.exists(os.path.join(e, 'out', 'Raven_errors.txt')) else ''
        want = 'needs an existing model that uses the Newton-Raphson formulation' if case == 'nonewton' else 'MODFLOW 6 stopped the run during initialize'
        ok2 = (not ok) and (want in err) and ('Exiting Gracefully: ' in txt) and (case == 'nonewton' or 'BICGSTAB' in err)
        print('  X6 %s: %s -> %s' % (case, (re.findall(r'ERROR    : (.*)', err) or ['no error message'])[-1][:160], 'ok' if ok2 else 'FAIL'))
        good &= ok2
    return good

def sy_x7():
    """X7: warnings for a specific yield the model does not give (no STO: 0.2) or gives
    below 0.01 (ICONVERT 0 with SY 0: floored at 0.01); every identity holds"""
    m0, e0 = os.path.join(W, 'x1_model'), os.path.join(W, 'x1_ext')
    good = True
    for case in ('confined', 'nosto'):
        m, e = os.path.join(W, 'x7_%s_model' % case), os.path.join(W, 'x7_%s_ext' % case)
        for a, b in ((m0, m), (e0, e)): shutil.rmtree(b, ignore_errors=True); shutil.copytree(a, b, ignore=shutil.ignore_patterns('out'))
        nam = open(os.path.join(m, 'gwf.nam')).read()
        sto = re.search(r'(?im)^\s*STO6\s+(\S+)', nam).group(1)
        if case == 'confined':
            open(os.path.join(m, sto), 'w').write('BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN GRIDDATA\n  ICONVERT\n    CONSTANT 0\n'
                                                '  SS\n    CONSTANT 1e-5\nEND GRIDDATA\nBEGIN PERIOD 1\n  TRANSIENT\nEND PERIOD\n')
            want = 'below 0.01 in'
        else:
            open(os.path.join(m, 'gwf.nam'), 'w').write(re.sub(r'(?im)^\s*STO6.*$', '', nam))
            want = '0.2 is assumed for the soil-zone checks, the release limits and the unsaturated columns'
        rvg = open(os.path.join(e, 'm.rvg')).read().replace(m0 + '/mfsim.nam', m + '/mfsim.nam'); open(os.path.join(e, 'm.rvg'), 'w').write(rvg)
        ok, txt = sz_check.run(e)
        err = open(os.path.join(e, 'out', 'Raven_errors.txt')).read() if os.path.exists(os.path.join(e, 'out', 'Raven_errors.txt')) else ''
        ok2 = ok and want in err
        print('  X7 %s: run %s, warning %s -> %s' % (case, 'completed' if ok else 'FAILED', 'present' if want in err else 'missing', 'ok' if ok2 else 'FAIL'))
        if ok:
            r = sz_check.checks(e); ok2 &= sz_check.report('x7 ' + case, r, {k: v for k, v in LIM.items() if k in r})
        good &= ok2
    return good

def sy_ratio(d):
    m = re.search(r'Sy/drainable porosity (\S+) to (\S+)', open(os.path.join(d, 'out', 'GWModelSummary.txt')).read())
    return (float(m.group(1)), float(m.group(2))) if m else None

def same_outputs(a, b, skip=('GWModelSummary.txt', 'Raven_errors.txt')):
    import filecmp
    pa, pb = os.path.join(a, 'out'), os.path.join(b, 'out')
    return [f for f in sorted(os.listdir(pa)) if not os.path.isdir(os.path.join(pa, f)) and f not in skip
            and not (os.path.exists(os.path.join(pb, f)) and filecmp.cmp(os.path.join(pa, f), os.path.join(pb, f), shallow=False))]

def sy_x8():
    """X8: a steady existing model (no STO) takes SPEC_YIELD of :SoilZoneAquiferClass when the class gives it"""
    e0 = os.path.join(W, 'x7_nosto_ext'); r0 = sy_ratio(e0)
    if r0 is None:
        print('  X8: the x7 run without STO is missing -> FAIL'); return False
    good = True
    for case, cls, want in (('class', '  SYCLASS, 50, 1, 1.0E-5, 0.1, 0.3\n', 'SPEC_YIELD 0.1 of :SoilZoneAquiferClass SYCLASS is used for the soil-zone checks'),
                            ('nosy', None, '0.2 is assumed for the soil-zone checks, the release limits and the unsaturated columns')):
        e = os.path.join(W, 'x8_%s_ext' % case); shutil.rmtree(e, ignore_errors=True); shutil.copytree(e0, e, ignore=shutil.ignore_patterns('out'))
        rvp = open(os.path.join(e, 'm.rvp')).read()
        if cls:
            rvp = rvp.replace(':EndAquiferClasses', cls.rstrip('\n') + '\n:EndAquiferClasses', 1)
        else:    # a second block whose class has no SPEC_YIELD
            rvp = rvp.replace(':EndAquiferClasses\n', ':EndAquiferClasses\n:AquiferClasses\n  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, POROSITY\n'
                              '  :Units, m/d, m/d, 1/m, none\n  NOSY, 50, 1, 1.0E-5, 0.3\n:EndAquiferClasses\n', 1)
        open(os.path.join(e, 'm.rvp'), 'w').write(rvp)
        open(os.path.join(e, 'm.rvg'), 'a').write('\n:SoilZoneAquiferClass %s\n' % ('SYCLASS' if cls else 'NOSY'))
        ok, txt = sz_check.run(e)
        err = open(os.path.join(e, 'out', 'Raven_errors.txt')).read() if os.path.exists(os.path.join(e, 'out', 'Raven_errors.txt')) else ''
        r = sy_ratio(e) if ok else None
        if cls:
            ok2 = ok and want in err and r is not None and abs(r[0] - 0.5 * r0[0]) < 1e-3 * r0[0] and abs(r[1] - 0.5 * r0[1]) < 1e-3 * r0[1]
            detail = 'Sy/drainable porosity %s (without the class %s)' % (r, r0)
        else:
            diffs = same_outputs(e0, e) if ok else ['(run failed)']
            ok2 = ok and want in err and r == r0 and not diffs
            detail = 'Sy/drainable porosity %s; outputs %s' % (r, 'identical to x7' if not diffs else 'differ: ' + ', '.join(diffs))
        print('  X8 %s: run %s, warning %s, %s -> %s' % (case, 'completed' if ok else 'FAILED', 'present' if want in err else 'missing', detail, 'ok' if ok2 else 'FAIL'))
        if ok:
            rr = sz_check.checks(e); ok2 &= sz_check.report('x8 ' + case, rr, {k: v for k, v in LIM.items() if k in rr})
        good &= ok2
    if sz_check.tc.REF:   # the run without a class, reference build
        e = os.path.join(W, 'x8_ref_ext'); shutil.rmtree(e, ignore_errors=True); shutil.copytree(e0, e, ignore=shutil.ignore_patterns('out'))
        os.makedirs(os.path.join(e, 'out'), exist_ok=True)
        subprocess.run([sz_check.tc.REF, 'm', '-o', 'out/'], cwd=e, capture_output=True, text=True, env=sz_check.tc.ENV)
        diffs = same_outputs(e0, e); ok2 = not diffs
        print('  X8 reference: x7 run without a class against RAVEN_EXE_REF: %s -> %s' % ('identical' if ok2 else 'differ: ' + ', '.join(diffs), 'ok' if ok2 else 'FAIL'))
        good &= ok2
    else:
        sz_check.tc.skip('X8: x7 run without a class against the reference build')
    return good

def main():
    res = [roundtrip('x1', **SHORT),
           roundtrip('x2', feet=True, **SHORT),
           roundtrip('x3', ':SoilZoneVadose RICHARDS\n:SoilZoneAquiferClass SAND\n:SoilZoneClasses 3\n',
                     chd=94.8, aq_b=4.0, aq_psia=0.3, init_depth=3.0, soil_b=5.0, soil_psia=200.0, pet=2.0, **SHORT),
           roundtrip('x4', ':SoilZoneCapillaryRise OFF\n', chd=94.8, **SHORT)]   # (capillary arrays sized with the rise off)
    res += [outputs_x3(), stops_x6(), sy_x7(), sy_x8()]
    print('soil-zone existing-model tests: %s' % ('ALL PASSED' if all(res) else 'FAILED (%d of %d)' % (res.count(False), len(res))))
    return all(res)

if __name__ == '__main__':
    sys.exit(0 if main() else 1)