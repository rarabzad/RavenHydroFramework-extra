"""Recharge of an HRU lying partly over specified-head cells (manual, "Recharge"): each linked cell receives the recharge
of its own overlap with the HRU, and the share over the specified heads goes to them ('recharge onto CHD cells'), so the
rule is continuous in the overlap.

Set-up: 4 HRUs of 200 x 200 m in a row on a 1 % slope, 20 mm/d of rain, 10 mm/d of percolation, 10 days; a
:SpecifiedHeadBoundary (93 m) covers the last two cell columns, which are all of HRU 4. In the second run HRU 4's polygon
reaches 0.05 m into HRU 3's last cells: a sliver of 10 m2 of its 40,000 m2.

BR1  CONCEPTUAL: with the sliver, the recharge onto the specified heads is the run without the sliver's times
     (1 - 10/40,000) (1e-6 relative), MODFLOW's recharge grows by the sliver's share only, and the seepage to Raven and
     HRU 3's head stay within 1 % and 1 mm of the run without the sliver (a sliver that took all of HRU 4's recharge would
     raise the seepage several times); the recharge identity holds in both runs.
BR2  the same under :SoilZone PHYSICAL, where the soil zone's recharge is shared over all the HRU's links, those over the
     specified heads included (by the columns' free water): the recharge onto the specified heads within 1 % and HRU 3's
     head within 1 mm of the run without the sliver; the recharge identity holds (soil-zone HRUs have no seepage drain).
BR3  :SoilZone PHYSICAL with HRU 4 without soil (a profile with no horizons; its ponded rain flushed to GROUNDWATER, so it
     recharges without a soil zone, and its recharge is shared by overlap): the recharge onto the specified heads as in
     BR1 (1e-6; MODFLOW's recharge also moves with the other HRUs' rejected recharge); HRU 3's head within 2 cm (the soil-less HRU keeps a seepage drain, also on the
     sliver's cell, which drains some seepage there; a sliver taking all of HRU 4's recharge raises the head 0.43 m).

Usage: python3 boundary_recharge.py   (needs RAVEN_MF6_LIB; seconds)
"""
import os, sys, json, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, 'soilzone')); sys.path.insert(0, HERE)
import testconfig as tc
import sz_models, sz_check
import pandas as pd

tc.need_mf6()
W = os.path.dirname(tc.work('boundary_recharge', 'x'))
NH, HW, CELL = 4, 200.0, 100.0
L = NH * HW; XS, YS = -0.5 * L, -0.5 * HW
SLIVER = 0.05
results = []


def build(name, sliver, physical, soilless=False):
    d = os.path.join(W, name); shutil.rmtree(d, ignore_errors=True)
    sz_models.make_case(d, nhru=NH, hru_w=HW, width=HW, cell=CELL, slope=0.01, z0=100.0, rain=20.0, days=10, init_depth=1.5, Kh=10.0, Kv=1.0,
                        aq_thick=10.0, Sy=0.1, perc=10.0, physical=physical, chd=93.0)
    if soilless:   # HRU 4 without soil (a profile with no horizons): its ponded rain is flushed to GROUNDWATER, its recharge
        def sub(f, a, b):     # (no soil zone under :SoilZone PHYSICAL)
            p = os.path.join(d, f); x = open(p).read(); assert a in x, (f, a); open(p, 'w').write(x.replace(a, b))
        sub('m.rvp', ':SoilProfiles\n', ':SoilProfiles\n  ROCKP, 0\n')
        h = open(os.path.join(d, 'm.rvh')).read().split('\n')
        for i, l in enumerate(h):
            if l.startswith('  4, '): h[i] = l.replace('SOILP', 'ROCKP')
        open(os.path.join(d, 'm.rvh'), 'w').write('\n'.join(h) + '\n:HRUGroup Rock\n  4\n:EndHRUGroup\n')
        sub('m.rvi', '  :Infiltration', '  :Flush RAVEN_DEFAULT PONDED_WATER GROUNDWATER\n  :-->Conditional HRU_GROUP IS Rock\n  :Infiltration')
        sub('m.rvi', ':HydrologicProcesses', ':DefineHRUGroups Rock\n:HydrologicProcesses')
    g = json.load(open(os.path.join(d, 'hru.geojson')))
    x0, x1 = XS + 3 * HW - sliver, XS + 4 * HW
    g['features'][3]['geometry']['coordinates'] = [[sz_models.ll(x0, YS), sz_models.ll(x1, YS), sz_models.ll(x1, YS + HW), sz_models.ll(x0, YS + HW), sz_models.ll(x0, YS)]]
    json.dump(g, open(os.path.join(d, 'hru.geojson'), 'w'))
    xe = XS + L - 1.75 * CELL   # the specified head over the last two cell columns (HRU 4)
    ring = [sz_models.ll(xe, YS - HW), sz_models.ll(XS + L + HW, YS - HW), sz_models.ll(XS + L + HW, YS + 2 * HW), sz_models.ll(xe, YS + 2 * HW), sz_models.ll(xe, YS - HW)]
    json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]},
              open(os.path.join(d, 'edge.geojson'), 'w'))
    ok, txt = sz_check.run(d)
    return d if ok else None, txt


def case(tag, label, physical, soilless=False):
    a, ta = build(tag + '_whole', 0.0, physical, soilless)
    b, tb = build(tag + '_sliver', SLIVER, physical, soilless)
    if a is None or b is None:
        results.append((tag, False)); print('%-66s FAIL (a run failed: %s)' % (label, (ta if a is None else tb).strip().split('\n')[-1][:120])); return
    A, B = sz_check.outputs(a)[0].iloc[-1], sz_check.outputs(b)[0].iloc[-1]
    ha, hb = (pd.read_csv(os.path.join(x, 'out', 'GWHRUState.csv'))['head_3 [m]'].iloc[-1] for x in (a, b))
    frac = SLIVER * HW / (HW * HW)
    chd_a, chd_b = A['recharge onto CHD cells [m3/d]'], B['recharge onto CHD cells [m3/d]']
    d_chd = abs(chd_b - chd_a * (1.0 - frac)) / max(chd_a, 1e-9)
    d_mf6 = abs((B['MF6 recharge [m3/d]'] - A['MF6 recharge [m3/d]']) - chd_a * frac) / max(chd_a, 1e-9)
    d_seep = abs(B['seepage to Raven [m3/d]'] - A['seepage to Raven [m3/d]']) / max(abs(A['seepage to Raven [m3/d]']), 1e-9)
    rch = max(sz_check.checks(x)['rch_identity'] for x in (a, b))
    if physical and not soilless:   # (the soil zone's recharge is shared by the columns' free water; its HRUs have no seepage drain)
        good = chd_a > 10.0 and abs(chd_b - chd_a) <= 0.01 * chd_a and abs(hb - ha) <= 1e-3 and rch <= sz_check.ID_LIMITS['rch_identity']
    elif soilless:  # (the soil-less HRU keeps a seepage drain, also on the sliver's cell: seepage and head move with it)
        good = chd_a > 100.0 and d_chd <= 1e-6 and abs(hb - ha) <= 0.02 and rch <= sz_check.ID_LIMITS['rch_identity']
    else:
        good = chd_a > 100.0 and d_chd <= 1e-6 and d_mf6 <= 1e-6 and d_seep <= 0.01 and abs(hb - ha) <= 1e-3 and rch <= sz_check.ID_LIMITS['rch_identity']
    results.append((tag, good))
    print('%-66s %s  (onto CHD %.2f -> %.2f m3/d, seepage %.2f -> %.2f m3/d, HRU 3 head %+.1e m; recharge identity %.1e)'
          % (label, 'ok' if good else 'FAIL', chd_a, chd_b, A['seepage to Raven [m3/d]'], B['seepage to Raven [m3/d]'], hb - ha, rch))


case('br1', 'BR1 CONCEPTUAL: a 10 m2 sliver takes only its own share', physical=False)
case('br2', 'BR2 :SoilZone PHYSICAL: the same', physical=True)
case('br3', 'BR3 :SoilZone PHYSICAL, HRU 4 without soil: the same as BR1', physical=True, soilless=True)
n = sum(1 for _, g in results if g)
print('boundary recharge: %s (%d of %d)' % ('ALL PASSED' if n == len(results) else 'FAILED', n, len(results)))
sys.exit(0 if n == len(results) else 1)
