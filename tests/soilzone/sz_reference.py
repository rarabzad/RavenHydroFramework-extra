"""MODFLOW-only reference of a soil-zone test case (HS1).

The soil zone becomes one extra MODFLOW layer on top of the aquifer (both soil layers have the same properties in
the tests): layer 1 = SOIL[0..1] (thickness H0+H1), specific yield = drainable porosity n(1-S_fc), horizontal K ~ 0
(Raven has no lateral flow in the soil), negligible specific storage, vertical K = k_sat (H0+H1)/H1 so that the
half-layer resistance MODFLOW puts between the layer and the aquifer is H1/(2 k_sat), as in the coupled model;
  layer 2 = the aquifer of the coupled model (its top, bottom, K, K33, Ss, Sy and starting heads are read from the
  coupled model's own MODFLOW files, so the geometry is identical);
  recharge = rain, applied to layer 1 (Newton keeps dry cells active, so it passes down to the water table);
  a drain at the land surface (top of layer 1) with a large conductance takes the saturation excess, the
  counterpart of the coupled model's soil-zone overflow.
The vertical conductance between layers 1 and 2 is A/(H1/(2 k_sat) + b/(2 K33)) = C^sz, the coupled model's
soil-aquifer conductance, and the drain conductance is large, so the saturation excess leaves without head loss, as
the coupled model's overflow does. Differences that remain are expected and small: the smoothing ramp of the
saturated fraction, and HRU edges that do not fall exactly on cell edges (sliver links).
"""
import os, re
import numpy as np
import flopy

def _read_array(txt, name, nrow, ncol, nlay=1):
    """INTERNAL or CONSTANT array `name` from a MODFLOW 6 GRIDDATA block (layered not needed: one layer)."""
    m = re.search(r'^\s*%s\b(.*?)(?=^\s*[A-Z][A-Z0-9_]*\s*$|^END)' % name, txt, re.S | re.M)
    body = m.group(1)
    if 'CONSTANT' in body.split('\n')[0] or body.strip().startswith('CONSTANT'):
        v = float(body.split('CONSTANT')[1].split()[0])
        return np.full((nlay, nrow, ncol), v)
    lines = body.strip().split('\n')
    nums = []
    for ln in lines:
        if 'INTERNAL' in ln:
            continue
        nums += [float(x) for x in ln.split()]
    return np.array(nums[:nlay * nrow * ncol]).reshape(nlay, nrow, ncol)

def build(coupled_dir, ref_dir, rain_mm, H0, H1, n, sfc, ksat_mm, mf6lib, drn_cond_per_m2=1000.0, nstp=1):
    mf = os.path.join(coupled_dir, 'out', 'mf6')
    dis = open(os.path.join(mf, 'gwf.dis')).read()
    nrow = int(re.search(r'NROW\s+(\d+)', dis).group(1)); ncol = int(re.search(r'NCOL\s+(\d+)', dis).group(1))
    delr = float(re.search(r'DELR\s+CONSTANT\s+([0-9.eE+-]+)', dis).group(1))
    delc = float(re.search(r'DELC\s+CONSTANT\s+([0-9.eE+-]+)', dis).group(1))
    top = _read_array(dis, 'TOP', nrow, ncol)[0]
    bot = _read_array(dis, 'BOTM', nrow, ncol)[0]
    npf = open(os.path.join(mf, 'gwf.npf')).read(); sto = open(os.path.join(mf, 'gwf.sto')).read()
    K = _read_array(npf, 'K', nrow, ncol)[0]; K33 = _read_array(npf, 'K33', nrow, ncol)[0]
    Ss = _read_array(sto, 'SS', nrow, ncol)[0]; Sy = _read_array(sto, 'SY', nrow, ncol)[0]
    strt = _read_array(open(os.path.join(mf, 'gwf.ic')).read(), 'STRT', nrow, ncol)[0]
    idom = _read_array(dis, 'IDOMAIN', nrow, ncol)[0].astype(int)
    act = [(i, j) for i in range(nrow) for j in range(ncol) if idom[i, j] > 0]
    D = H0 + H1
    land = top + D
    sd = n * (1 - sfc); ks = ksat_mm / 1000.0
    os.makedirs(ref_dir, exist_ok=True)
    sim = flopy.mf6.MFSimulation(sim_name='ref', sim_ws=ref_dir, exe_name='mf6', verbosity_level=0)
    # daily stress periods (rain may change every day)
    flopy.mf6.ModflowTdis(sim, time_units='DAYS', nper=len(rain_mm), perioddata=[(1.0, nstp, 1.0)] * len(rain_mm))
    flopy.mf6.ModflowIms(sim, complexity='COMPLEX', outer_dvclose=1e-7, outer_maximum=500, inner_maximum=500,
                         inner_dvclose=1e-8, rcloserecord=1e-3, linear_acceleration='BICGSTAB',
                         under_relaxation='DBD', backtracking_number=20)
    gwf = flopy.mf6.ModflowGwf(sim, modelname='ref', newtonoptions='NEWTON', save_flows=True)
    flopy.mf6.ModflowGwfdis(gwf, nlay=2, nrow=nrow, ncol=ncol, delr=delr, delc=delc, top=land, botm=[top, bot],
                            idomain=[idom, idom])
    flopy.mf6.ModflowGwfnpf(gwf, icelltype=1, k=[np.full_like(K, 1e-6), K],
                            k33=[np.full_like(K, ks * D / H1), K33], save_flows=True)
    flopy.mf6.ModflowGwfsto(gwf, iconvert=1, ss=[np.full_like(Ss, 1e-10), Ss],
                            sy=[np.full_like(Sy, sd), Sy], transient=True)
    flopy.mf6.ModflowGwfic(gwf, strt=[strt, strt])
    rch = {}
    for p, r in enumerate(rain_mm):
        rch[p] = [((0, i, j), r / 1000.0) for (i, j) in act]
    flopy.mf6.ModflowGwfrch(gwf, stress_period_data=rch, fixed_cell=True, save_flows=True)
    flopy.mf6.ModflowGwfdrn(gwf, stress_period_data={0: [((0, i, j), land[i, j], drn_cond_per_m2 * delr * delc)
                                                          for (i, j) in act]}, save_flows=True)
    flopy.mf6.ModflowGwfoc(gwf, head_filerecord='ref.hds', budget_filerecord='ref.cbc',
                           saverecord=[('HEAD', 'ALL'), ('BUDGET', 'ALL')])
    sim.write_simulation(silent=True)
    # run through the same library the coupled model used (no mf6 executable needed)
    from xmipy import XmiWrapper
    cwd = os.getcwd(); os.chdir(ref_dir)
    try:
        m = XmiWrapper(mf6lib); m.initialize()
        while m.get_current_time() < m.get_end_time():
            m.update()
        m.finalize()
    finally:
        os.chdir(cwd)
    hds = flopy.utils.HeadFile(os.path.join(ref_dir, 'ref.hds'))
    cbc = flopy.utils.CellBudgetFile(os.path.join(ref_dir, 'ref.cbc'), precision='double')
    days = [t for t in hds.get_times() if abs(t - round(t)) < 1e-6]              # end of each day
    heads = np.array([hds.get_data(totim=t) for t in days])                    # (nt, 2, nrow, ncol)
    tb = np.array(cbc.get_times())
    q = np.array([-sum(rec['q'].sum() for rec in cbc.get_data(text='DRN', totim=t)) for t in tb])   # m3/d per step
    dtb = np.diff(np.concatenate([[0.0], tb]))
    drn = np.array([(q * dtb)[(tb > d - 1 + 1e-9) & (tb <= d + 1e-9)].sum() for d in range(1, len(rain_mm) + 1)])  # m3 per day
    # the bounding box of the active cells (the coupled grid may carry an inactive margin)
    rows = sorted(set(i for i, j in act)); cols = sorted(set(j for i, j in act))
    box = np.ix_(rows, cols)
    sub = lambda a: a[(slice(None),) + box] if a.ndim == 3 else a[box]
    return dict(soil=sub(heads[:, 0]), aquifer=sub(heads[:, 1]), drn=drn, land=sub(land), top=sub(top),
                nrow=len(rows), ncol=len(cols), sd=sd, area=delr * delc)
