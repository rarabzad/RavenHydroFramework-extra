# Restarts on every grid type (the manual's "Restarts" paragraph): a 60-day run against 30 days restarted from the first
# 30 days' solution.rvc, on the subbasin-52 model with 3 km cells, a pumping well and half-day steps. A grid passes when all
# three runs finish, the restart deviation (each day's difference relative to the flow + 1000 m3/d) is below 1e-4, the
# continuous run has no unconverged step, and its water accounts are exact (recharge identity, MODFLOW's cumulative
# residual and the river bookkeeping below 1e-8). The last line gives the count; the exit code is 1 unless all pass.
# The same in quick and full mode (RAVEN_TEST_QUICK has no effect).
import os,shutil,subprocess,re,sys,datetime,pandas as pd
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); import testconfig as tc; audit=tc.audit
tc.need_mf6(); B=tc.grid_base(); ENV=tc.ENV; RV=tc.RAVEN
V={'regular (default)':'','rotated + variable spacing':':GridRotation 30\n:GridRefinement RIVERS 1000\n:GridRefinement WELLS 500\n',
   'quadtree':':GridType QUADTREE\n:GridRefinement RIVERS 750\n:GridRefinement WELLS 375\n','HRU mesh':':GridType HRU_MESH\n:GridRefinement RIVERS 1000\n',
   'layers by elevation':':LayerConnection ELEVATION\n'}
def setup(d,extra,start,dur,rvc=None):
    shutil.rmtree(d,ignore_errors=True); shutil.copytree(B,d,ignore=shutil.ignore_patterns('out')); os.makedirs(d+'/out')
    g=open(d+'/Liard.rvg').read(); open(d+'/Liard.rvg','w').write(g+'\n'+extra)
    t=open(d+'/Liard.rvi').read(); t=re.sub(r':StartDate\s+\S+\s+\S+',':StartDate %s 00:00:00'%start,t); t=re.sub(r':Duration\s+\S+',':Duration %d'%dur,t); open(d+'/Liard.rvi','w').write(t)
    if rvc: shutil.copy(rvc,d+'/Liard.rvc')
def run(d):
    r=subprocess.run([RV,'Liard','-o','out/'],cwd=d,capture_output=True,text=True,env=ENV); return 'Successful' in (r.stdout + r.stderr)
t=open(B+'/Liard.rvi').read(); s0=re.search(r':StartDate\s+(\S+)',t).group(1); s0d=datetime.date.fromisoformat(s0); mid=(s0d+datetime.timedelta(days=30)).isoformat()
npass=0
for name,extra in V.items():
    k=re.sub('[^a-z]+','_',name)
    c,a,b=[tc.work('restart','rs_%s_%s'%(k,p)) for p in 'cab']
    setup(c,extra,s0,60); setup(a,extra,s0,30)
    ok=run(c) and run(a)
    if ok: setup(b,extra,mid,30,a+'/out/solution.rvc'); ok=run(b)
    if not ok: print('%-28s FAILED'%name); continue
    C=pd.read_csv(c+'/out/GWBudget.csv').dropna(subset=['Raven recharge [m3/d]']); H=pd.read_csv(b+'/out/GWBudget.csv').dropna(subset=['Raven recharge [m3/d]'])
    m=C.merge(H,on='date',suffixes=('_c','_h'))
    dev=max(((m[x+'_c']-m[x+'_h']).abs()/(m[x+'_c'].abs()+1e3)).max() for x in ['seepage to Raven [m3/d]','storage release [m3/d]','river exchange applied to Raven [m3]','MF6 recharge [m3/d]'])
    A=audit.audit(c+'/out')
    res,rch,riv,nf=A['MF6 cumulative residual / gross flow'],abs(A['recharge: (Raven - MF6 - dStore - toCHD)/Raven']),abs(A['river: applied - net MF6 - carry change (rel)']),A['unconverged steps']
    good=(dev<1e-4) and (nf==0) and (abs(res)<1e-8) and (rch<1e-8) and (riv<1e-8) and len(m)>0
    npass+=good
    print('%-28s restart deviation %.1e (%d days)  residual %.1e  recharge %.0e  river %.0e  failed %s  %s'%(name,dev,len(m),res,rch,riv,nf,'ok' if good else 'FAIL'))
print('restart grids: %d of %d pass'%(npass,len(V)))
sys.exit(0 if npass==len(V) else 1)
