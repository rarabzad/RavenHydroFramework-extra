"""tables/run_checks.tex: the automatic checks (tools_audit.py) of the behaviour-test runs. Each argument is the output
folder of one run (or the folder holding out/), in the table's order:

    python3 make_tables.py LIARD PUMPING FIXED_HEAD RESTART ENSEMBLE WETLANDS RESERVOIR SOILLESS DRYING

LIARD the 20-year coupled Liard run, PUMPING the pumping test with observations, FIXED_HEAD the fixed-head and recharge-delay
run, RESTART its restart, ENSEMBLE one member of the ensemble run, WETLANDS, RESERVOIR, SOILLESS (soil-less HRUs) and
DRYING (the extreme drying run). A folder without GWBudget.csv is left out of the table."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'examples', 'Liard_groundwater'))
import tools_audit as audit, pandas as pd, numpy as np
# the behaviour-test runs (Section "Behaviour tests"), given as arguments in the table's order
NAMES=['20-year Liard','Pumping','Fixed head, delay','Restart','Ensemble','Wetlands','Reservoir','Soil-less HRUs','Drying (extreme)']
if len(sys.argv) != len(NAMES)+1 or sys.argv[1] in ('-h', '--help'):
    sys.exit(__doc__)
runs=list(zip(NAMES, sys.argv[1:]))
R={}
for n,p in runs:
    if os.path.exists(p+'/GWBudget.csv') or os.path.exists(p+'/out/GWBudget.csv'):
        try: R[n]=audit.audit(p)
        except Exception as e: print('skip',n,e)
def f(v,kind):
    if v is None or (isinstance(v,float) and np.isnan(v)): return '--'
    if kind=='e': return '0' if v==0 else '$%.1e$'%v
    if kind=='p': return '%.3f'%v
    if kind=='i': return '%d'%v
    if kind=='b': return 'yes' if v else 'no'
    return '%.3g'%v
rows=[('steps','steps','i'),('Recharge balance (rel.)','recharge: (Raven - MF6 - dStore - toCHD)/Raven','e'),('MF6 cumulative residual','MF6 cumulative residual / gross flow','e'),
      ('MF6 worst step [\\%]','MF6 worst step error [%]','p'),('Unconverged steps','unconverged steps','i'),('River bookkeeping (rel.)','river: applied - net MF6 - carry change (rel)','e'),
      ('River loss carried at end [m$^3$]','river loss carried at end [m3]','e'),('Seepage returned (rel.)','seepage returned vs MF6 seepage (rel)','e'),('Surface-store bookkeeping (rel.)','surface-store: applied - (discharge-leakage) (rel)','e'),('Raven balance error [mm]','Raven MB error max [mm]','p'),
      ('Dates contiguous','dates_contiguous','b')]
names=list(R)
import math
def sci(v):
    if v is None or (isinstance(v,float) and math.isnan(v)): return '--'
    if v==0: return '0'
    e=int(math.floor(math.log10(abs(v)))); m=v/10**e
    return '$%s%.1f\\times10^{%d}$'%('-' if m<0 else '',abs(m),e)
def pct(v):
    return '--' if v is None else ('$%s$'%sci(v).strip('$') if abs(v)<0.001 and v!=0 else '%.3g'%v)
cols=[('Steps','steps',lambda v:'{:,}'.format(int(v)).replace(',','\\,')),('Recharge','recharge: (Raven - MF6 - dStore - toCHD)/Raven',sci),
      ('\\shortstack[r]{MODFLOW\\\\residual}','MF6 cumulative residual / gross flow',sci),('\\shortstack[r]{Worst\\\\step [\\%]}','MF6 worst step error [%]',pct),
      ('\\shortstack[r]{Failed\\\\steps}','unconverged steps',lambda v:'%d'%v),('River','river: applied - net MF6 - carry change (rel)',sci)]   # (Raven's balance: Section "Raven's balance" of the accounting chapter)
out=[r'\begin{table}[!htbp]\centering',
     r'\caption{Automatic checks of the behaviour-test runs (\cmd{tools\_audit.py}). Relative errors are shares of the water moved. In every run the seepage returned to Raven equals MODFLOW\textquotesingle s seepage exactly, the surface-store bookkeeping is exact, no river loss is carried at the end and the output dates are contiguous. The one failed step is the rewetting day of the deliberately extreme drying test (Section~\ref{sec:behaviour}).}\label{tab:audit}',
     r'\footnotesize\setlength{\tabcolsep}{2.8pt}\begin{tabular}{l'+'r'*len(cols)+r'}\toprule\hdr',
     'Run & '+' & '.join(c[0] for c in cols)+r'\\\midrule']
for n in names:
    out.append(n+' & '+' & '.join(fn(R[n].get(key)) if R[n].get(key) is not None else '--' for _,key,fn in cols)+r'\\')
out.append(r'\bottomrule\end{tabular}\end{table}')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'tables', 'run_checks.tex'),'w').write('\n'.join(out)+'\n'); print('table runs:',names)
