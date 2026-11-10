"""converts a MODFLOW 6 model in metres and days into feet and seconds (DIS, NPF, STO, IC, TDIS and the CHD, GHB, RIV, WEL and
DRN lists): python3 mf6_to_feet.py SOURCE_FOLDER DESTINATION_FOLDER. It stops with a message for a model it cannot convert
whole: a DISV or DISU grid, another package that holds lengths or rates (EVT, RCH, MAW, LAK, SFR, UZF, CSUB, HFB, MVR), or a
list value given as a time-series name"""
import flopy, sys, os, shutil, numpy as np
src,dst=sys.argv[1],sys.argv[2]; L=3.280839895; T=86400.0
shutil.rmtree(dst,ignore_errors=True)
sim=flopy.mf6.MFSimulation.load(sim_ws=src,verbosity_level=0)
sim.set_sim_path(dst)
td=sim.tdis; pd_=td.perioddata.get_data(); pd_['perlen']*=T; td.perioddata.set_data(pd_); td.time_units.set_data('seconds')
gwf=sim.get_model(list(sim.model_names)[0])
def stop(msg):
    sys.stderr.write('mf6_to_feet: %s\n' % msg); sys.exit(2)
types=[p.package_type for p in gwf.packagelist]
for g in ('disv','disu'):
    if g in types: stop('the model has a %s grid; only a DIS grid (layers, rows and columns) is converted' % g.upper())
other=sorted(set(types)&{'evt','evta','rch','rcha','maw','lak','sfr','uzf','csub','hfb','mvr'})
if other: stop('the model has %s, whose lengths or rates this tool does not convert' % ', '.join(x.upper() for x in other))
dis=gwf.dis; dis.length_units.set_data('feet')
for a in ('delr','delc','top','botm'):
    v=getattr(dis,a); v.set_data(v.get_data()*L)
for a in ('xorigin','yorigin'):
    v=getattr(dis,a); 
    if v.get_data() is not None: v.set_data(v.get_data()*L)
npf=gwf.npf
for a in ('k','k22','k33'):
    v=getattr(npf,a)
    if v.has_data(): v.set_data(v.get_data()*L/T)
sto=gwf.get_package('sto')
if sto is not None: sto.ss.set_data(sto.ss.get_data()/L)
gwf.ic.strt.set_data(gwf.ic.strt.get_data()*L)
# list packages: (field, factor) of each converted value; a field read as whole numbers (heads such as 94) becomes float
FIELDS={'chd':(('head',L),),'ghb':(('bhead',L),('cond',L*L/T)),'riv':(('stage',L),('cond',L*L/T),('rbot',L)),'wel':(('q',L**3/T),),
        'drn':(('elev',L),('cond',L*L/T))}
for p in gwf.packagelist:
    if p.package_type in FIELDS:
        spd=p.stress_period_data.get_data()
        for k in spd:
            r=spd[k]
            if r is None: continue
            conv=dict(FIELDS[p.package_type])
            for n in conv:
                try: np.asarray(r[n],dtype=np.float64)
                except (ValueError,TypeError):
                    stop('%s (%s), stress period %d: a %s value is a time-series name (%s); give the values in the list'
                         % (p.package_type.upper(),p.filename,k+1,n,[x for x in r[n] if isinstance(x,str)][:1]))
            r=r.astype([(n,(np.float64 if n in conv else r.dtype[n])) for n in r.dtype.names])
            for n,f in conv.items(): r[n]=r[n]*f
            spd[k]=r
        p.stress_period_data.set_data(spd)
ims=sim.get_package('ims') if hasattr(sim,'get_package') else None
sim.write_simulation(silent=True)
print('written',dst)
