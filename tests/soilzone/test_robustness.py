"""Robustness of :SoilZone PHYSICAL (cases found by the code inspections).

R1 stiff flat column: drainable porosity 0.02 against S_y = 0.25 and a high conductance; the water table rises to the
   base and the soil zone fills. The interface and MODFLOW converge on every step in few updates (a connection that
   opened only above the base left MODFLOW's top cell confined there and the iteration cycled).
R2 one HRU over ten cells against ten one-cell HRUs (same hillslope and forcing): the HRU's recharge leaves the columns
   that hold the free water, so the soil-zone overflow (the hillslope's outflow) agrees within 3% and MODFLOW's recharge
   within a factor 1.6 (sharing recharge by area pumped drainage of the saturated toe up the slope: outflow -36%,
   recharge x2.3).
R3 RECHARGE_DELAY with :SoilZone PHYSICAL is refused with a clear message.
R4 a smoothing depth below 0.05 m is reported.
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'robustness')

def case(name, **kw):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, **kw)
    return d

def errors(d):
    p = os.path.join(d, 'out', 'Raven_errors.txt')
    return open(p).read() if os.path.exists(p) else ''

def main():
    res = []
    d = case('R1', nhru=1, n=0.04, sfc=0.5, Sy=0.25, rain=20, perc=20, days=60, init_depth=1.2, ksat=1000, Kv=10)
    ok, _ = sz_check.run(d)
    g = False
    if ok:
        r = sz_check.checks(d); b = sz_check.outputs(d)[0]
        g = r['iface_not_conv'] == 0 and r['mf6_not_conv'] == 0 and r['max_updates'] <= 20 and r['sz_identity'] < 1e-8
        print('  R1: interface not converged %d, MODFLOW not converged %d, max updates %d, max outer iterations %d'
              % (r['iface_not_conv'], r['mf6_not_conv'], r['max_updates'], int(b['outer iterations'].max())))
    res.append(('R1 stiff column converges', g))

    WET = [10.0] * 60 + [0.0] * 60
    hill = dict(width=200.0, cell=100.0, Kh=50.0, Kv=1.0, ksat=1000.0, perc=1000.0, perc_type='PERC_GAWSER_CONSTRAIN',
                rain=WET, days=len(WET), slope=0.01, subgrid=3, smooth=0.2, init_depth=1.0)
    out = {}
    for name, kw in (('R2_one', dict(nhru=1, hru_w=1000.0)), ('R2_ten', dict(nhru=10, hru_w=100.0))):
        c = dict(hill); c.update(kw); d = case(name, **c)
        ok, _ = sz_check.run(d)
        if ok:
            b = sz_check.outputs(d)[0]; r = sz_check.checks(d)
            out[name] = (b['soil-zone overflow [m3]'].sum(), b['MF6 recharge [m3/d]'].sum(), r['iface_not_conv'])
    g = False
    if len(out) == 2:
        (o1, m1, n1), (o2, m2, n2) = out['R2_one'], out['R2_ten']
        g = abs(o1 - o2) <= 0.03 * o2 and 1 / 1.6 <= m1 / m2 <= 1.6 and n1 == 0 and n2 == 0
        print('  R2: overflow %.0f vs %.0f m3 (%.1f%%), MF6 recharge %.0f vs %.0f m3 (ratio %.2f)'
              % (o1, o2, 100 * (o1 - o2) / o2, m1, m2, m1 / m2))
    res.append(('R2 one HRU over ten cells = ten HRUs', g))

    d = case('R3', days=3)
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    t = t.replace('SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH\n', 'SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH, RECHARGE_DELAY\n')
    t = t.replace('  :Units, m, m, 1/d, m\n', '  :Units, m, m, 1/d, m, d\n')
    lines = t.split('\n'); i = [k for k, l in enumerate(lines) if l.startswith('  AQ, ')][-1]; lines[i] += ', 10'
    open(p, 'w').write('\n'.join(lines))
    ok, txt = sz_check.run(d)
    res.append(('R3 RECHARGE_DELAY refused', (not ok) and 'RECHARGE_DELAY' in (txt + errors(d)) and 'cannot be used with :SoilZone PHYSICAL' in (txt + errors(d))))

    d = case('R4', days=3, smooth=0.01)
    ok, _ = sz_check.run(d)
    res.append(('R4 small smoothing depth reported', ok and 'SEEPAGE_SMOOTHING_DEPTH' in errors(d) and 'below 0.05 m' in errors(d)))

    for n, g in res:
        print('  %-45s %s' % (n, 'ok' if g else 'FAILED'))
    good = all(g for _, g in res)
    print('robustness tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
