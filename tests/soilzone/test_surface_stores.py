"""Surface stores (:SurfaceWaterExchange on DEPRESSION) of HRUs with :SoilZone PHYSICAL: the store sits on the ground, above
the soil zone, so the bed and the stage datum of its exchange are the ground (soil-zone base + thickness), not the model top.

Set-up (the manual's example combination): 5 HRUs of 200 x 200 m on a 0.01 slope, soil zone 1.0 m (SOIL[0], SOIL[1]),
:Abstraction ABST_FILL PONDED_WATER DEPRESSION (DEP_MAX 50 mm), :SurfaceWaterExchange DEPRESSION All LEAKANCE 0.05, rain
30 mm/d for 6 days then dry, water table 0.6 m below the ground at the start, 20 days.
SW1 generated model, specified head 89 m at the outlet (below the ground): the water table rises into the soil zone but
   stays at most a few cm above the ground. On every day on which every HRU's water table is below its ground (saturated
   fraction below 1) the aquifer gives the stores nothing; the depressions leak to the aquifer; identities at round-off.
   (With the bed at the soil-zone base, 1 m below the ground, the aquifer would fill the depressions while the soil zone is
   still unsaturated.) The stores' bed in gwf.swx is the ground of their HRUs: the model top + the soil-zone thickness.
SW2 the same coupled as an existing model (the generated MODFLOW files without Raven's packages): the same discharge and
   leakage within 1e-4 of their largest value; bed in raven.swx at the ground.
SW3 control: specified head 92 m at the outlet, above the ground of the last cells: the aquifer discharges into the
   depressions there (discharge > 0); identities.
SW4 restart of SW3: 10 days, then 10 days from its solution.rvc. Groundwater discharge fills a depression above DEP_MAX
   (the precondition is checked: a DEPRESSION above 50 mm in the solution.rvc); the restart keeps it (the store of a
   :SurfaceWaterExchange is not clipped to its maximum when the .rvc is read: a clip would lose 583 m3), so the watershed's
   Depression on day 11 and the discharge into the stores on days 12-20 equal the continuous SW3 run (1e-6).
Quick mode (RAVEN_TEST_QUICK=1): the same cases (each run takes seconds).
Usage: python3 test_surface_stores.py      (prints 'surface-store tests: ALL PASSED')"""
import os, sys, shutil, re
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, pandas as pd
import sz_models, sz_check

W = sz_check.tc.work('soilzone', 'surface_stores')
CFG = dict(nhru=5, hru_w=200.0, slope=0.01, rain=[30.0] * 6 + [0.0] * 14, days=20, init_depth=0.6, aq_thick=10.0, chd=89.0, Kv=0.3, Sy=0.1)
D = 1.0   # soil-zone thickness H0 + H1 [m]


def stores(d):
    p = os.path.join(d, 'm.rvi'); t = open(p).read()
    open(p, 'w').write(t.replace('  :Infiltration', '  :Abstraction ABST_FILL PONDED_WATER DEPRESSION\n  :Infiltration'))
    p = os.path.join(d, 'm.rvp'); t = open(p).read()
    open(p, 'w').write(t.replace(':Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0',
                                 ':Parameters, PARTITION_COEFF, DEP_MAX, ABST_PERCENT\n  :Units, none, mm, none\n  [DEFAULT], 0.0, 50, 0.5'))
    open(os.path.join(d, 'm.rvh'), 'a').write('\n:HRUGroup All\n  1,2,3,4,5\n:EndHRUGroup\n')
    open(os.path.join(d, 'm.rvg'), 'a').write('\n:SurfaceWaterExchange DEPRESSION All LEAKANCE 0.05\n')


def drop_raven_pkgs(m):   # (the existing twin: the generated model without Raven's added packages)
    p = os.path.join(m, 'gwf.nam'); nam = open(p).read()
    open(p, 'w').write('\n'.join(l for l in nam.split('\n') if 'SWX_RAVEN' not in l and 'EVT_RAVEN' not in l))


def bed_above_top(d, fname, model_ws):
    """(smallest, largest) height of the stores' bed above the model top of its cell [m]: the soil-zone thickness D when the
    bed is the ground (every HRU here has a soil zone of thickness D)"""
    import flopy
    sim = flopy.mf6.MFSimulation.load(sim_ws=model_ws, verbosity_level=0, load_only=['dis'])
    top = sim.get_model(sim.model_names[0]).dis.top.array
    txt = open(os.path.join(d, 'out', 'mf6', fname)).read().split('BEGIN PERIOD')[1].split('END PERIOD')[0]
    rows = [l.split() for l in txt.strip().split('\n')[1:] if l.strip() and not l.strip().startswith('#')]
    h = [float(r[3]) - top[int(r[1]) - 1, int(r[2]) - 1] for r in rows]
    return min(h), max(h)


def day_checks(d):
    b, sx, _ = sz_check.outputs(d)
    wt_rel = (sx['water table [m]'] - sx['soil-zone base [m]'] - D).groupby(sx['date']).max().reindex(b['date']).values
    below = wt_rel < 0.0
    dis = b['aquifer discharge to surface stores [m3/d]'].values
    leak = b['surface-store leakage to aquifer [m3/d]'].values
    return below, dis, leak


def main():
    res = []
    g = os.path.join(W, 'SW1_gen'); shutil.rmtree(g, ignore_errors=True); sz_models.make_case(g, **CFG); stores(g)
    ok, txt = sz_check.run(g)
    if not ok:
        print('  SW1: run FAILED\n' + txt[-800:]); res.append(('SW1 generated', False))
    else:
        r = sz_check.checks(g); good = sz_check.report('SW1', r, sz_check.ID_LIMITS)
        below, dis, leak = day_checks(g)
        b0, b1 = bed_above_top(g, 'gwf.swx', os.path.join(g, 'out', 'mf6'))
        nb = int(below.sum()); dmax = float(dis[below].max()) if nb else 0.0
        gg = good and nb > 0 and dmax == 0.0 and leak.sum() > 0 and abs(b0 - D) < 1e-6 and abs(b1 - D) < 1e-6
        print('  SW1: %d days with every water table below the ground, discharge to the stores on them at most %.4g m3/d; '
              'leakage %.0f m3; store beds %.6f..%.6f m above the model top (soil zone %g m) -> %s' % (nb, dmax, leak.sum(), b0, b1, D, 'ok' if gg else 'FAIL'))
        res.append(('SW1 generated: no discharge into stores while the soil zone is unsaturated', gg))
        e = sz_check.ext_case(g, os.path.join(W, 'SW2_ext'), CFG, model_edit=drop_raven_pkgs); stores(e)
        ok, txt = sz_check.run(e)
        if not ok:
            print('  SW2: run FAILED\n' + txt[-800:]); res.append(('SW2 existing', False))
        else:
            r = sz_check.checks(e); good = sz_check.report('SW2', r, sz_check.ID_LIMITS)
            be, de, le = day_checks(e)
            b0, b1 = bed_above_top(e, 'raven.swx', e + '_model')
            sc = max(np.abs(leak).max(), np.abs(dis).max(), 1.0)
            dev = max(np.abs(de - dis).max(), np.abs(le - leak).max()) / sc
            gg = good and dev < 1e-4 and float(de[be].max() if be.sum() else 0.0) == 0.0 and abs(b0 - D) < 1e-6 and abs(b1 - D) < 1e-6
            print('  SW2: discharge and leakage against SW1 within %.2g of the largest; store beds %.6f..%.6f m above the model top -> %s'
                  % (dev, b0, b1, 'ok' if gg else 'FAIL'))
            res.append(('SW2 existing model: the same', gg))
    c = os.path.join(W, 'SW3_wet'); shutil.rmtree(c, ignore_errors=True); sz_models.make_case(c, **dict(CFG, chd=92.0)); stores(c)
    ok, txt = sz_check.run(c)
    if not ok:
        print('  SW3: run FAILED\n' + txt[-800:]); res.append(('SW3 control', False))
    else:
        r = sz_check.checks(c); good = sz_check.report('SW3', r, sz_check.ID_LIMITS)
        below, dis, leak = day_checks(c)
        gg = good and dis.sum() > 0 and (dis[below].max() if below.sum() else 0.0) == 0.0
        print('  SW3: discharge into the stores %.0f m3 (water table above the ground at the outlet) -> %s' % (dis.sum(), 'ok' if gg else 'FAIL'))
        res.append(('SW3 control: discharge where the water table is above the ground', gg))
        # SW4: restart from day 10 of SW3
        a = os.path.join(W, 'SW4_first'); shutil.rmtree(a, ignore_errors=True); sz_models.make_case(a, **dict(CFG, chd=92.0, days=10, rain=CFG['rain'][:10])); stores(a)
        ok1, _ = sz_check.run(a)
        b = os.path.join(W, 'SW4_second'); shutil.rmtree(b, ignore_errors=True); sz_models.make_case(b, **dict(CFG, chd=92.0, days=10, rain=CFG['rain'][10:])); stores(b)
        for f in ('m.rvi', 'm.rvt'):
            p = os.path.join(b, f); t = open(p).read(); open(p, 'w').write(t.replace('2000-01-01 00:00:00', '2000-01-11 00:00:00'))
        gg = ok1
        if ok1:
            rvc = os.path.join(a, 'out', 'solution.rvc'); shutil.copy(rvc, os.path.join(b, 'm.rvc'))
            t = open(rvc).read(); tab = t.split(':HRUStateVariableTable')[1].split(':EndHRUStateVariableTable')[0].strip().split('\n')
            i = tab[0].split(',').index('DEPRESSION'); dep = max(float(r.split(',')[i]) for r in tab[2:])
            ok2, _ = sz_check.run(b); gg = ok2 and dep > 50.0
            if ok2:
                wc = pd.read_csv(os.path.join(c, 'out', 'WatershedStorage.csv')); wc.columns = [x.strip() for x in wc.columns]
                wr = pd.read_csv(os.path.join(b, 'out', 'WatershedStorage.csv')); wr.columns = [x.strip() for x in wr.columns]
                d0 = abs(float(wc.loc[wc['date'] == '2000-01-11', 'Depression [mm]'].iloc[0]) - float(wr.loc[wr['date'] == '2000-01-11', 'Depression [mm]'].iloc[0]))
                k = 'aquifer discharge to surface stores [m3/d]'
                bc = pd.read_csv(os.path.join(c, 'out', 'GWBudget.csv')).set_index('date'); br = pd.read_csv(os.path.join(b, 'out', 'GWBudget.csv')).set_index('date')
                dq = sz_check.tc.max_diff(bc.loc[br.index, k], br[k], max(bc[k].abs().max(), 1.0))
                gg = gg and d0 < 1e-6 and dq < 1e-6
                print('  SW4: restart on day 11 with a store at %.2f mm (DEP_MAX 50): Depression %.2g mm from the continuous run, discharge into the stores within %.2g -> %s'
                      % (dep, d0, dq, 'ok' if gg else 'FAIL'))
            else:
                print('  SW4: restarted run FAILED')
        else:
            print('  SW4: first run FAILED')
        res.append(('SW4 restart keeps a store filled above its maximum by groundwater', gg))
    for n, ok in res:
        print('  %-72s %s' % (n, 'ok' if ok else 'FAILED'))
    good = len(res) == 4 and all(ok for _, ok in res)
    print('surface-store tests: %s' % ('ALL PASSED' if good else 'FAILED'))
    return good


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
