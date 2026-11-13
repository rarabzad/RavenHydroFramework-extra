"""Automated audit of a Raven-MODFLOW 6 coupled run directory (<run>/out)."""
import pandas as pd, numpy as np, sys, os, re
def rd(f):
    d=pd.read_csv(f); d.columns=[c.strip() for c in d.columns]; return d
def audit(run,dt=1.0):
    o=(run+'/') if os.path.exists(run+'/GWBudget.csv') else run+'/out/'; R={}
    b=rd(o+'GWBudget.csv')
    tt=b['time [d]'].dropna().values
    if len(tt)>1: d=abs(tt[1:]-tt[:-1]); dt=float(sorted(d)[len(d)//2])   #(the median step length, also of a run of two steps)
    elif len(tt)==1 and tt[0]>0: dt=float(tt[0])                            #(one step: its end time from the run's start)
    R['steps']=len(b); R['rows_complete']=int(b.notna().all(axis=1).sum())
    b=b.dropna()
    R['time step [d]']=dt; R['dates_contiguous']=bool((abs(b['time [d]'].diff().dropna()-dt)<1e-6).all()) and b['date'].is_unique
    rr=b['Raven recharge [m3/d]'].sum()*dt; mr=b['MF6 recharge [m3/d]'].sum()*dt
    st=b['recharge delay storage [m3]'].iloc[-1] if 'recharge delay storage [m3]' in b else 0.0
    chdv=b['recharge onto CHD cells [m3/d]'] if 'recharge onto CHD cells [m3/d]' in b else 0*b['MF6 recharge [m3/d]']
    s0=(st if False else 0.0)
    rejv=b['rejected recharge [m3]'] if 'rejected recharge [m3]' in b else 0*b['MF6 recharge [m3/d]']   #:SoilZone PHYSICAL: recharge on saturated ground goes back to the soil (also subtracted)
    rej=rejv.sum()
    uzs=(b['unsaturated zone inflow [m3]']-b['unsaturated zone to aquifer [m3]']) if 'unsaturated zone inflow [m3]' in b else 0*b['MF6 recharge [m3/d]']   #(:SoilZoneVadose: recharge crosses the unsaturated columns)
    uz=uzs.sum()
    lostv=b['recharge not applied by MODFLOW [m3/d]']*dt if 'recharge not applied by MODFLOW [m3/d]' in b else 0*b['MF6 recharge [m3/d]']   #existing model without NEWTON
    lost=lostv.sum()
    #the recharge delay store at the start: from GWModelSummary.txt (written when a profile has RECHARGE_DELAY or the
    #hotstart holds a store), 0 when the run has no store; only for a run without that line is it back-computed from step
    #1's own identity, and step 1 is then not checked
    sm=o+'GWModelSummary.txt'; m0=re.search(r'^\s*recharge delay storage\s*:\s*(\S+) m3 at the start',open(sm).read(),re.M) if os.path.exists(sm) else None
    s0checked=True
    if m0: s0=float(m0.group(1))
    elif 'recharge delay storage [m3]' in b and (b['recharge delay storage [m3]']!=0).any():
        s0=b['recharge delay storage [m3]'].iloc[0]-(b['Raven recharge [m3/d]'].iloc[0]-b['MF6 recharge [m3/d]'].iloc[0]-chdv.iloc[0])*dt+rejv.iloc[0]+uzs.iloc[0]+lostv.iloc[0]
        s0checked=False
    R['recharge: (Raven - MF6 - dStore - toCHD)/Raven']=(rr-mr-(st-s0)-chdv.sum()*dt-rej-uz-lost)/max(abs(rr),1)
    if not s0checked: R['recharge: step 1 not checked (start of the delay store back-computed)']=True
    R['recharge delay store at end [m3]']=st
    flows=b['MF6 recharge [m3/d]']+b['storage release [m3/d]']-b['seepage to Raven [m3/d]']+b['river leakage to aquifer [m3/d]']\
          -b['aquifer discharge to rivers [m3/d]']-b['water-table ET [m3/d]']+b['wells actual [m3/d]']+b['GHB [m3/d]']+b['CHD [m3/d]']
    if 'reservoir seepage delivered [m3/d]' in b: flows=flows+b['reservoir seepage delivered [m3/d]']; gross_res=b['reservoir seepage delivered [m3/d]'].abs()
    else: gross_res=0*flows
    if 'surface-store leakage to aquifer [m3/d]' in b: flows=flows+b['surface-store leakage to aquifer [m3/d]']-b['aquifer discharge to surface stores [m3/d]']
    gross=(b['MF6 recharge [m3/d]'].abs()+b['seepage to Raven [m3/d]']+b['river leakage to aquifer [m3/d]']+b['aquifer discharge to rivers [m3/d]']
           +b['water-table ET [m3/d]']+b['wells actual [m3/d]'].abs()+b['GHB [m3/d]'].abs()+b['CHD [m3/d]'].abs()+b['storage release [m3/d]'].abs())
    gross=gross+gross_res
    if 'other model packages [m3/d]' in b: flows=flows+b['other model packages [m3/d]']; gross=gross+b['other model packages [m3/d]'].abs()  #existing-model mode: the model's own packages
    if 'soil zone to aquifer [m3/d]' in b:   #:SoilZone PHYSICAL: soil zone <-> aquifer exchange (SZX_RAVEN)
        flows=flows+b['soil zone to aquifer [m3/d]']-b['aquifer to soil zone [m3/d]']; gross=gross+b['soil zone to aquifer [m3/d]']+b['aquifer to soil zone [m3/d]']
        if 'seepage and soil inflow withheld [m3]' in b:   #seepage and soil inflow are reported after the withholding: MODFLOW took the withheld part too
            flows=flows-b['seepage and soil inflow withheld [m3]']/dt
        for c in ('capillary rise from the water table [m3]','lagged-exchange repayment [m3]'):   #(capillary rise and lagged-exchange repayment: fixed rates out of the aquifer, SZQ_RAVEN)
            if c in b: flows=flows-b[c]/dt; gross=gross+b[c].abs()/dt
        szn=(b['aquifer to soil zone [m3/d]']-b['soil zone to aquifer [m3/d]'])*dt
        for c in ('capillary rise to soil zone [m3]','capillary rise from the water table [m3]','lagged-exchange debt [m3]'):
            if c in b: szn=szn+b[c]
        if 'specified heads to soil zone [m3/d]' in b: szn=szn+(b['specified heads to soil zone [m3/d]']-b['soil zone to specified heads [m3/d]'])*dt
        nh=b['negative recharge the soil zone did not hold [m3]'] if 'negative recharge the soil zone did not hold [m3]' in b else 0.0   #(a negative recharge's cut no store held)
        R['soil zone: applied - rejected - net exchange - shortfall (rel)']=float((b['soil-zone exchange applied to Raven [m3]']-b['rejected recharge [m3]']-szn-b['soil-zone shortfall [m3]']-nh).abs().sum()
            /max((b['soil-zone exchange applied to Raven [m3]'].abs()+b['rejected recharge [m3]'].abs()+szn.abs()).sum(),1))
        if 'unsaturated zone storage [m3]' in b:   #the unsaturated columns' storage balance, from step 1 when the summary gives the start
            sm=(o+'GWModelSummary.txt'); m0=re.search(r'^\s*unsaturated storage\s*:\s*(\S+) m3 at the start',open(sm).read(),re.M) if os.path.exists(sm) else None
            vs=b['unsaturated zone storage [m3]']; dv=vs.diff()
            if m0: dv.iloc[0]=vs.iloc[0]-float(m0.group(1))
            r=(dv-b['unsaturated zone inflow [m3]']+b['capillary rise to soil zone [m3]']+b['unsaturated zone to aquifer [m3]'])[0 if m0 else 1:]
            R['unsaturated columns: storage change - inflow + rise + outflow (rel)']=float(r.abs().sum()/max((b['unsaturated zone inflow [m3]'].abs()+b['unsaturated zone to aquifer [m3]'].abs()).sum(),1))
            R['unsaturated columns: step 1 checked']=bool(m0)
        R['soil zone: shortfall [m3]']=float(b['soil-zone shortfall [m3]'].sum())
        R['soil zone: overflow [m3]']=float(b['soil-zone overflow [m3]'].sum())
        R['soil zone: interface not converged (steps)']=int((b['interface converged']==0).sum())
        R['soil zone: max interface updates']=int(b['interface updates'].max())
    if 'surface-store leakage to aquifer [m3/d]' in b:
        gross=gross+b['surface-store leakage to aquifer [m3/d]']+b['aquifer discharge to surface stores [m3/d]']
        ws=b['surface-store gains withheld [m3]'] if 'surface-store gains withheld [m3]' in b else 0.0   #:SoilZone PHYSICAL guard
        R['surface-store: applied - (discharge-leakage) (rel)']=(b['surface-store exchange applied to Raven [m3]']-(b['aquifer discharge to surface stores [m3/d]']-b['surface-store leakage to aquifer [m3/d]'])*dt+ws).abs().sum()/max((b['surface-store leakage to aquifer [m3/d]']+b['aquifer discharge to surface stores [m3/d]']).sum()*dt,1)
    R['MF6 cumulative residual / gross flow']=flows.sum()/max(gross.sum(),1)   #(m3/d summed over the steps; a run without aquifer flow has only round-off)
    if 'reservoir seepage awaiting delivery [m3]' in b and b['reservoir seepage sent [m3/d]'].abs().sum()>0:
        #reservoir seepage reaches MODFLOW one step later: sent(t)*dt = awaiting(t-1); MODFLOW takes what is sent unless the cell is dry
        import numpy as _np
        tt=b['time [d]'].values; dts=_np.diff(_np.concatenate([[0.0],tt])); sv=b['reservoir seepage sent [m3/d]'].values*dts
        aw=b['reservoir seepage awaiting delivery [m3]'].values; dl=b['reservoir seepage delivered [m3/d]'].values*dts
        R['reservoir: sent(t) - awaiting(t-1) (rel)']=float(_np.max(_np.abs(sv[1:]-aw[:-1]))/max(_np.max(_np.abs(sv)),1e-12)) if len(sv)>1 else 0.0
        R['reservoir: delivered / sent']=float(dl.sum()/sv.sum()) if sv.sum()!=0 else 1.0
        if 'reservoir gain not supplied by MODFLOW [m3]' in b:
            shv=b['reservoir gain not supplied by MODFLOW [m3]'].fillna(0).values   #gains MODFLOW could not supply, taken back from the reach
            udv=b['reservoir seepage not delivered by MODFLOW [m3]'].fillna(0).values if 'reservoir seepage not delivered by MODFLOW [m3]' in b else 0.0*shv   #losses MODFLOW did not take, returned to the reach
            #sent = delivered - gain not supplied + loss not delivered (both MODFLOW could not apply; the reach evens them out)
            R['reservoir: (delivered + not supplied) / sent']=float((dl.sum()-shv.sum()+udv.sum())/sv.sum()) if sv.sum()!=0 else 1.0
            R['reservoir: seepage not delivered [m3]']=float(udv.sum())
    R['MF6 worst step error [%]']=b['MF6 balance error [%]'].abs().max()
    R['unconverged steps']=int((b['converged']==0).sum()); R['max outer iterations']=int(b['outer iterations'].max())
    R['seepage returned vs MF6 seepage (rel)']=abs(b['returned to Raven [m3]'].sum()-b['seepage to Raven [m3/d]'].sum()*dt)/max(b['seepage to Raven [m3/d]'].sum()*dt,1)
    net=(b['aquifer discharge to rivers [m3/d]']-b['river leakage to aquifer [m3/d]']).sum()*dt
    cc='river loss carried to next step [m3]' if 'river loss carried to next step [m3]' in b else 'river loss deficit [m3]'
    if cc.startswith('river loss carried'):
        c=b[cc].fillna(0); cp=c.shift(1).fillna(0); n=(b['aquifer discharge to rivers [m3/d]']-b['river leakage to aquifer [m3/d]'])*dt; ok=b['converged'].astype(int)>=1
        sh=b['reservoir gain not supplied by MODFLOW [m3]'].fillna(0) if 'reservoir gain not supplied by MODFLOW [m3]' in b else 0.0   #taken from the reach in the same step
        wr=b['river gains withheld [m3]'].fillna(0) if 'river gains withheld [m3]' in b else 0.0   #:SoilZone PHYSICAL guard
        ud=b['reservoir seepage not delivered by MODFLOW [m3]'].fillna(0) if 'reservoir seepage not delivered by MODFLOW [m3]' in b else 0.0   #returned to the reach in the same step
        r=(b['river exchange applied to Raven [m3]']-n-c+cp+sh+wr-ud)[ok]; R['river: applied - net MF6 - carry change (rel)']=r.sum()/max(n.abs().sum(),1)
        R['safeguard-limited steps']=int((~ok).sum())
        R['river loss carried at end [m3]']=float(c.iloc[-1]); R['river loss carried max [m3]']=float(c.max())
    else:
        R['river: applied - net MF6 - deficit (rel)']=(b['river exchange applied to Raven [m3]'].sum()-net-b[cc].sum())/max(abs(net),b['river leakage to aquifer [m3/d]'].sum()*dt,1)
        R['river loss deficit [m3]']=b[cc].sum()
    if b['wells specified [m3/d]'].abs().sum()>0:
        R['wells delivered / specified']=b['wells actual [m3/d]'].sum()/b['wells specified [m3/d]'].sum()
    if b['CHD [m3/d]'].abs().sum()>0: R['CHD mean flow [m3/d]']=b['CHD [m3/d]'].mean()
    w=rd(o+'WatershedStorage.csv'); R['Raven MB error max [mm]']=w['MB Error [mm]'].abs().max()
    h=rd(o+'GWHRUState.csv'); H=h[[c for c in h.columns if c.startswith('head_')]].values; D=h[[c for c in h.columns if c.startswith('wtdepth_')]].values
    R['HRU heads finite']=bool(np.isfinite(H).all()); R['max water table above land (HRU mean) [m]']=float(-D.min())
    if os.path.exists(o+'GWHeads.csv'):
        g=rd(o+'GWHeads.csv'); R['GWHeads rows (incl. t=0)']=len(g); R['GWHeads starts at t=0']=bool(g['time [d]'].iloc[0]==0)
    # Raven_errors.txt: in the output folder, or (ensemble members, runs audited from their case folder) next to it
    up=os.path.dirname(o.rstrip('/')); cand=[o+'Raven_errors.txt',up+'/Raven_errors.txt',up+'/out/Raven_errors.txt',up+'/output/Raven_errors.txt']
    ef=[f for f in cand if os.path.exists(f)]
    if ef: e=open(ef[0]).read(); R['unconverged-guard warnings']=e.count('(MODFLOW unconverged): discharge returned to Raven limited')+e.count('of discharge to Raven withheld'); R['ERROR lines']=len(re.findall(r'^ERROR',e,re.M))
    return R
if __name__=='__main__':
    if len(sys.argv)<2: sys.exit('usage: python3 tools_audit.py OUTPUT_FOLDER [OUTPUT_FOLDER ...]')
    for r in sys.argv[1:]:
        if not (os.path.exists(r+'/GWBudget.csv') or os.path.exists(r+'/out/GWBudget.csv')):
            sys.exit('%s: no GWBudget.csv - the run did not finish (see Raven_errors.txt there)' % r)
    rows={r.rstrip('/').split('/')[-1]:audit(r) for r in sys.argv[1:]}
    df=pd.DataFrame(rows); pd.set_option('display.width',250); pd.set_option('display.max_colwidth',60)
    print(df.to_string(float_format=lambda v:'%.3g'%v))
