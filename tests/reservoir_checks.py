"""Reservoir seepage (:ReservoirExchange) on lakes whose cells cannot all take it, under :SoilZone PHYSICAL, and gains
MODFLOW does not supply. The cases are the strips of combinations.py (4 HRUs of 200 x 200 m, 100 m cells) with the lake's
crest 0.5 m and its stage 0.3 m above the ground of its HRU, so that it loses water to the aquifer.

R1 an existing model whose own CHD package holds the 4 cells under the lake (HRU 1) at 97 m in stress periods 3-5 (one
   period per day). Raven also links the lake HRU to a fifth cell, of HRU 2, that it overlaps by a sliver (about 0.06 m2
   of 40,000 m2). While the 4 cells are specified heads the lake seeps only through the sliver's share of its bed: the
   seepage delivered on those days is at most 1e-4 of the seepage before them (it was the lake's whole seepage, 4.5 times
   its earlier value, at the sliver's level). On the day the cells become specified heads the seepage computed the day
   before for the whole bed is returned ('reservoir seepage not delivered by MODFLOW' = sent). With the sliver cell also a
   specified head (R1b) the seepage on those days differs from R1 by less than 1 m3/d: the result does not jump with a
   sliver. Every identity of combinations.check_run holds. A restart from the solution.rvc of day 4 (R1c, inside the
   specified-head period) gives the continuous run's reservoir and aquifer columns (1e-6).
R2 a generated model whose lake (HRU 4) lies half over the cells of a :SpecifiedHeadBoundary: the lake's seepage constant
   is scaled by the half of its bed left (0.50 against 1.00), so the cells left get the seepage of their own share of the
   bed. The water table lies below the lake's bed there, so the seepage is k F (mean stage - bed) and F is measured.
R3 :SoilZone PHYSICAL against CONCEPTUAL, generated and existing: a lake on the ground of a soil-zone HRU has its bed on the
   ground (as surface stores), not at the soil-zone base D below it: the same seepage on day 2 as the CONCEPTUAL run of the
   same model (1e-6; it was 3.25 times the CONCEPTUAL value).
R4 a lake 4 m below the ground over dry top cells (combinations.py's CONC_NONE_res_dry, the lake lowered): its gain is computed but MODFLOW
   does not supply it; GWModelSummary.txt has the run total 'reservoir gain not supplied' (equal to its GWBudget.csv
   column) and Raven_errors.txt a warning.
Quick mode (RAVEN_TEST_QUICK=1): 8-day runs (15 days in the full mode, where R1 also runs in feet and seconds).
Usage: python3 reservoir_checks.py      (prints 'reservoir checks: ALL PASSED')"""
import os, sys, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'soilzone'))
import numpy as np, pandas as pd
import combinations as C

W = os.path.dirname(C.tc.work('reservoir_checks', 'x'))
QUICK = C.QUICK


def spec(nm):
    for s, m in C.matrix():
        if C.name(s) == nm: return s
    raise SystemExit('no case ' + nm)


def at_ground(d, s, zg=None):
    """the lake's crest and stage above the ground of its HRU (at the HRU's centre, world x; or above zg)"""
    kl = C.NHRU if 'chd' in s['x'] else 1
    if zg is None: zg = C.land(C.XS + (kl - 0.5) * C.HW)
    p = os.path.join(d, 'm.rvh'); t = open(p).read()
    t = re.sub(r':AbsoluteCrestHeight \S+', ':AbsoluteCrestHeight %.3f' % (zg + 0.5), t)
    t = re.sub(r':SeepageParameters 0.02 \S+', ':SeepageParameters 0.02 %.3f' % (zg - 2.0), t); open(p, 'w').write(t)
    p = os.path.join(d, 'm.rvc'); t = open(p).read(); open(p, 'w').write(re.sub(r':InitialReservoirStage 1 \S+', ':InitialReservoirStage 1 %.3f' % (zg + 0.3), t))
    return zg


def lake_chd(e, cells, a, b, feet):
    """the existing model e: one stress period per day and a CHD package of its own on the given cells in periods a..b-1"""
    m = re.search(r':MF6Simulation (\S+)/mfsim.nam', open(os.path.join(e, 'm.rvg')).read()).group(1)
    td = [os.path.join(m, f) for f in os.listdir(m) if f.endswith('.tdis')][0]
    open(td, 'w').write('BEGIN OPTIONS\n  TIME_UNITS %s\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NPER %d\nEND DIMENSIONS\n\nBEGIN PERIODDATA\n' % ('SECONDS' if feet else 'DAYS', C.DAYS)
                        + ('  86400.0 1 1.0\n' if feet else '  1.0 1 1.0\n') * C.DAYS + 'END PERIODDATA\n')
    f = 3.280839895 if feet else 1.0
    open(os.path.join(m, 'lake.chd'), 'w').write('BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN DIMENSIONS\n  MAXBOUND 5\nEND DIMENSIONS\nBEGIN PERIOD %d\n' % a
                                                  + ''.join('  %s %r\n' % (c, 97.0 * f) for c in cells) + 'END PERIOD\nBEGIN PERIOD %d\nEND PERIOD\n' % b)
    p = os.path.join(m, 'gwf.nam'); t = open(p).read(); open(p, 'w').write(t.replace('END PACKAGES', '  CHD6 lake.chd CHD_LAKE\nEND PACKAGES'))


def gwb(d):
    return pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))


def r1(res):
    s = spec('CONC_NONE_res_plain'); base = os.path.join(W, 'R1')
    g = C.generated(os.path.join(base, 'gen'), s); at_ground(g, s)
    txt = C.run(g); bad, _ = C.check_run(g, txt)
    if bad:
        print('  R1: generated run FAILED: %s' % bad); res.append(('R1', False)); return
    four = ['1 2 2', '1 3 2', '1 2 3', '1 3 3']
    out = {}
    for tag, cells, mod in (('all', four, 'ext'), ('all5', four + ['1 3 4'], 'ext')) + ((('ft', four, 'ext_ft'),) if not QUICK else ()):
        e = os.path.join(base, tag)
        C.existing(g, e, s, feet=(mod == 'ext_ft')); at_ground(e, s); lake_chd(e, cells, 3, 6, mod == 'ext_ft')
        txt = C.run(e); bad, info = C.check_run(e, txt)
        out[tag] = (e, bad)
    good = True
    e, bad = out['all']
    if bad:
        print('  R1: run FAILED: %s' % bad); res.append(('R1 lake cells specified heads: no piling into a sliver', False)); return
    b = gwb(e); dl = b['reservoir seepage delivered [m3/d]'].values; sent = b['reservoir seepage sent [m3/d]'].values
    nd = b['reservoir seepage not delivered by MODFLOW [m3]'].values
    before = dl[1]; chd = dl[3:5]; trans_ok = abs(nd[2] - sent[2]) <= 1e-3 * max(sent[2], 1.0) and sent[2] > 0.0
    g1 = before > 0.0 and bool((np.abs(chd) <= 1e-4 * before).all()) and trans_ok
    print('  R1: seepage delivered before the specified heads %.1f m3/d, on their days %s m3/d; day they start: sent %.1f, returned %.1f m3 -> %s'
          % (before, ', '.join('%.4g' % x for x in dl[2:5]), sent[2], nd[2], 'ok' if g1 else 'FAIL'))
    res.append(('R1 lake cells specified heads: seepage of the sliver\'s share only, the rest returned', g1))
    e5, bad5 = out['all5']
    g2 = not bad5
    if g2:
        d5 = gwb(e5)['reservoir seepage delivered [m3/d]'].values; dd = float(np.abs(d5[2:5] - dl[2:5]).max())
        g2 = dd < 1.0
        print('  R1b: the sliver cell a specified head too: seepage on those days %s m3/d, %.3g m3/d from R1 -> %s' % (', '.join('%.4g' % x for x in d5[2:5]), dd, 'ok' if g2 else 'FAIL'))
    else:
        print('  R1b: run FAILED: %s' % bad5)
    res.append(('R1b no jump with a sliver', g2))
    if 'ft' in out:
        ef, badf = out['ft']
        g3 = not badf
        if g3:
            bf = gwb(ef); dev = C.tc.max_diff(bf['reservoir seepage delivered [m3/d]'], b['reservoir seepage delivered [m3/d]'], max(b['reservoir seepage delivered [m3/d]'].abs().max(), 1.0))
            g3 = dev < 1e-5
            print('  R1 feet/seconds: seepage within %.2g of the metres/days run -> %s' % (dev, 'ok' if g3 else 'FAIL'))
        else:
            print('  R1 feet/seconds: run FAILED: %s' % badf)
        res.append(('R1 in feet and seconds', g3))
    # R1c: restart inside the specified-head period
    p1, p2 = e + '_p1', e + '_p2'
    for q in (p1, p2): shutil.rmtree(q, ignore_errors=True); shutil.copytree(e, q, ignore=shutil.ignore_patterns('out'))
    k = 4
    t = open(os.path.join(p1, 'm.rvi')).read(); open(os.path.join(p1, 'm.rvi'), 'w').write(re.sub(r':Duration \S+', ':Duration %d' % k, t))
    txt1 = C.run(p1)
    t = open(os.path.join(p2, 'm.rvi')).read(); t = re.sub(r':Duration \S+', ':Duration %d' % (C.DAYS - k), t)
    open(os.path.join(p2, 'm.rvi'), 'w').write(re.sub(r':StartDate \S+', ':StartDate 2000-01-%02d' % (1 + k), t))
    g4 = 'Successful Simulation' in txt1
    if g4:
        shutil.copy(os.path.join(p1, 'out', 'solution.rvc'), os.path.join(p2, 'm.rvc'))
        g4 = 'Successful Simulation' in C.run(p2)
    if g4:
        a = b.set_index('date'); c = gwb(p2).set_index('date'); a = a.loc[c.index]
        cols = [x for x in c.columns if ('reservoir' in x or x in ('storage release [m3/d]', 'other model packages [m3/d]', 'seepage to Raven [m3/d]'))]
        dev = max(C.tc.max_diff(a[x], c[x], max(a[x].abs().max(), 1.0)) for x in cols)
        g4 = dev < 1e-6
        print('  R1c: restart on day %d (specified heads under the lake): reservoir and aquifer columns within %.2g of the continuous run -> %s' % (k + 1, dev, 'ok' if g4 else 'FAIL'))
    else:
        print('  R1c: restart runs FAILED')
    res.append(('R1c restart inside the specified-head period', g4))


def r2(res):
    s = spec('CONC_NONE_chd-et-res-swx_plain'); s = dict(s, x={'res', 'chd'})
    zg = C.land(C.XS + C.L - 1.5 * C.CELL)   # (the ground of the lake's cells left: the column next to the specified heads)
    d = C.generated(os.path.join(W, 'R2'), s); at_ground(d, s, zg)
    txt = C.run(d); bad, _ = C.check_run(d, txt)
    if bad:
        print('  R2: run FAILED: %s' % bad); res.append(('R2', False)); return
    b = gwb(d); st = pd.read_csv(os.path.join(d, 'out', 'ReservoirStages.csv')); col = [c for c in st.columns if c not in ('time', 'date', 'hour', 'precip [mm/day]')][0]
    stage = st[col].values   # (row 0: the start; row n: end of step n)
    V = b['reservoir seepage awaiting delivery [m3]'].values   # (step n: computed in step n's routing)
    wt = pd.read_csv(os.path.join(d, 'out', 'GWHRUState.csv'))['head_4 [m]'].values
    F = [V[n] / (0.02 * 86400.0 * (0.5 * (stage[n + 1] + stage[n]) - zg)) for n in range(1, 4)]
    g = bool(all(abs(f - 0.5) < 0.02 for f in F)) and float(wt.max()) < zg
    print('  R2: lake half over a specified-head boundary: seepage constant used %s of its own (water table %.2f m below the bed) -> %s'
          % (', '.join('%.3f' % f for f in F), zg - float(wt.max()), 'ok' if g else 'FAIL'))
    res.append(('R2 generated lake over specified heads: constant scaled by the bed left', g))


def r3(res):
    q = {}
    for nm in ('PHYS_NONE_res_plain', 'CONC_NONE_res_plain'):
        s = spec(nm); g = C.generated(os.path.join(W, 'R3', nm, 'gen'), s); at_ground(g, s)
        txt = C.run(g); bad, _ = C.check_run(g, txt); q[(nm, 'gen')] = (bad, g)
        if not bad:
            e = os.path.join(W, 'R3', nm, 'ext'); C.existing(g, e, s); at_ground(e, s)
            txt = C.run(e); bad, _ = C.check_run(e, txt); q[(nm, 'ext')] = (bad, e)
    fails = [k for k, v in q.items() if v[0]]
    if fails or len(q) < 4:
        print('  R3: runs FAILED: %s' % [(k, q[k][0]) for k in fails]); res.append(('R3', False)); return
    v = {k: float(gwb(d)['reservoir seepage sent [m3/d]'].values[1]) for k, (bad, d) in q.items()}
    ref = v[('CONC_NONE_res_plain', 'gen')]
    dev = max(abs(v[('PHYS_NONE_res_plain', m)] - v[('CONC_NONE_res_plain', m)]) / v[('CONC_NONE_res_plain', m)] for m in ('gen', 'ext'))
    g = dev < 1e-6 and ref > 0.0
    print('  R3: seepage on day 2, CONCEPTUAL %.1f m3/d; PHYSICAL %.1f (generated), %.1f (existing) m3/d, within %.2g of CONCEPTUAL -> %s'
          % (ref, v[('PHYS_NONE_res_plain', 'gen')], v[('PHYS_NONE_res_plain', 'ext')], dev, 'ok' if g else 'FAIL'))
    res.append(('R3 lake bed on the ground under :SoilZone PHYSICAL', g))


def r4(res):
    s = spec('CONC_NONE_res_dry'); d = C.generated(os.path.join(W, 'R4'), s)
    at_ground(d, s, C.land(C.XS + 0.5 * C.HW) - 4.0)   # (4 m below the ground: the lake gains from the water table in layer 2)
    txt = C.run(d); bad, _ = C.check_run(d, txt)
    if bad:
        print('  R4: run FAILED: %s' % bad); res.append(('R4', False)); return
    tot = float(gwb(d)['reservoir gain not supplied by MODFLOW [m3]'].sum())
    m = re.search(r'reservoir gain not supplied:\s*(\S+) m3', open(os.path.join(d, 'out', 'GWModelSummary.txt')).read())
    err = open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
    g = tot > 0.0 and m is not None and abs(float(m.group(1)) - tot) <= 1e-5 * tot and 'of reservoir gain was not supplied by MODFLOW' in err
    print('  R4: gain not supplied %.1f m3 in GWBudget.csv; run total %s; warning %s -> %s'
          % (tot, m.group(1) if m else 'MISSING', 'present' if 'of reservoir gain was not supplied' in err else 'MISSING', 'ok' if g else 'FAIL'))
    res.append(('R4 unsupplied reservoir gain: warning and run total', g))


def main():
    res = []
    for f in (r1, r2, r3, r4):
        f(res)
    for n, g in res:
        print('  %-80s %s' % (n, 'ok' if g else 'FAILED'))
    good = len(res) == (6 if QUICK else 7) and all(g for _, g in res)
    print('reservoir checks: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
