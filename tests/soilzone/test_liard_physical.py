"""T7 (plan §9.2): the Liard example with :SoilZone PHYSICAL SOIL[0] SOIL[1].

The example's recharge comes from FAST_RESERVOIR (a 100 m conceptual store), which cannot be a soil zone. The variant
lets the aquifer HRUs percolate SOIL[0] -> SOIL[1] (VADOSE) -> GROUNDWATER instead (PERC_GAWSER) and gives the soil
classes a saturated conductivity; everything else (snow, glaciers, lakes, wetlands, rivers, 85 coupled HRUs on a
2 km grid over a DEM) is the example as it is. A year from 1985-10-01 covers the snowmelt rise of the water table.
The example's soils have a small drainable porosity n(1-S_fc) ~ 0.02 against the aquifer's S_y = 0.25 (the
storage-consistency warning is expected), which makes the interface stiff: a hard case for the iteration.
Checks: the run finishes, MODFLOW and the interface converge in every step, the audit identities close (recharge,
MODFLOW residual, soil-zone exchange), no shortfall, and the soil zone takes part (rejection, exchange both ways).
"""
import os, sys, re, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
import testconfig as tc
audit = tc.audit

def make(d, days):
    tc.copy_case(tc.LIARD, d, duration=days)
    p = os.path.join(d, 'Liard.rvi'); t = open(p).read()
    old = re.search(r'  :Percolation\s+PERC_CONSTANT\s+FAST_RESERVOIR\s+GROUNDWATER\s*\n\s*:-->Conditional HRU_GROUP IS AquiferHRUs\s*\n', t)
    assert old, 'Liard.rvi: FAST_RESERVOIR -> GROUNDWATER percolation not found'
    new = ('  :Percolation           PERC_GAWSER        SOIL[0]          VADOSE_RESERVOIR\n'
           '    :-->Conditional HRU_GROUP IS AquiferHRUs\n'
           '  :Percolation           PERC_GAWSER        VADOSE_RESERVOIR GROUNDWATER\n'
           '    :-->Conditional HRU_GROUP IS AquiferHRUs\n')
    t = t[:old.start()] + new + t[old.end():]
    open(p, 'w').write(t)
    p = os.path.join(d, 'Liard.rvp')
    open(p, 'a').write('\n# soil-zone variant (tests/soilzone/test_liard_physical.py)\n:SoilParameterList\n'
                       '  :Parameters, HYDRAUL_COND, MAX_PERC_RATE\n  :Units, mm_per_d, mm_per_d\n'
                       '  TOPSOIL, 200, 20\n  TOPSOIL2, 200, 10\n  TOP_WETLAND, 50, 10\n  VADOSE, 100, 5\n:EndSoilParameterList\n')
    p = os.path.join(d, 'Liard.rvg')
    open(p, 'a').write('\n:SoilZone PHYSICAL SOIL[0] SOIL[1]\n:SoilZoneSubgrid 5\n')
    return d

def main(days=365):
    tc.need_mf6()
    d = make(tc.work('soilzone', 'liard_physical'), days)
    msg = tc.run(d)
    print('T7 Liard physical (%d days): %s' % (days, msg))
    if 'Successful' not in msg:
        print(open(os.path.join(d, 'out', 'Raven_errors.txt')).read()[-3000:]); return False
    A = audit.audit(os.path.join(d, 'out'))
    b = pd.read_csv(os.path.join(d, 'out', 'GWBudget.csv'))
    s = pd.read_csv(os.path.join(d, 'out', 'GWSoilExchange.csv'))
    err = open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
    keys = ['recharge: (Raven - MF6 - dStore - toCHD)/Raven', 'MF6 cumulative residual / gross flow',
            'soil zone: applied - rejected - net exchange - shortfall (rel)', 'soil zone: shortfall [m3]',
            'soil zone: overflow [m3]', 'soil zone: interface not converged (steps)', 'soil zone: max interface updates',
            'unconverged steps', 'max outer iterations', 'river: applied - net MF6 - carry change (rel)', 'ERROR lines']
    for k in keys:
        print('  %-62s %s' % (k, A.get(k)))
    up = s['soil zone to aquifer [m3/d]'].sum(); dn = s['aquifer to soil zone [m3/d]'].sum()
    rej = b['rejected recharge [m3]'].sum(); hrus = s.loc[s['saturated fraction [-]'] > 0.2, 'HRU_ID'].nunique()
    print('  soil zone -> aquifer %.3g m3, aquifer -> soil zone %.3g m3, rejected recharge %.3g m3, HRUs ever >20%% saturated: %d of %d'
          % (up, dn, rej, hrus, s['HRU_ID'].nunique()))
    print('  storage-consistency warning: %s' % ('drainable porosity' in err))
    good = abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']) < 1e-9 and abs(A['MF6 cumulative residual / gross flow']) < 1e-7 \
        and A['soil zone: applied - rejected - net exchange - shortfall (rel)'] < 1e-8 and A['soil zone: shortfall [m3]'] < 1e-6 \
        and A['soil zone: interface not converged (steps)'] == 0 and A['unconverged steps'] == 0 and A.get('ERROR lines', 0) == 0 \
        and dn > 0 and up > 0 and rej > 0 and hrus > 0
    print('T7 Liard physical: %s' % ('PASS' if good else 'FAIL'))
    return bool(good)

if __name__ == '__main__':
    sys.exit(0 if main(int(sys.argv[1]) if len(sys.argv) > 1 else 365) else 1)
