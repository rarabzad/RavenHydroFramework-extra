import flopy, sys, os, shutil, numpy as np
src,dst=sys.argv[1],sys.argv[2]; L=3.280839895; T=86400.0
shutil.rmtree(dst,ignore_errors=True)
sim=flopy.mf6.MFSimulation.load(sim_ws=src,verbosity_level=0)
sim.set_sim_path(dst)
td=sim.tdis; pd_=td.perioddata.get_data(); pd_['perlen']*=T; td.perioddata.set_data(pd_); td.time_units.set_data('seconds')
gwf=sim.get_model(list(sim.model_names)[0])
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
for p in gwf.packagelist:
    if p.package_type=='chd':
        spd=p.stress_period_data.get_data()
        for k in spd: spd[k]['head']*=L
        p.stress_period_data.set_data(spd)
ims=sim.get_package('ims') if hasattr(sim,'get_package') else None
sim.write_simulation(silent=True)
print('written',dst)
