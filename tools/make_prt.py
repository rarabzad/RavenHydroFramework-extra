# Copyright (c) 2026 Rezgar Arabzadeh -- Raven-MODFLOW 6 groundwater coupling
# SPDX-License-Identifier: Artistic-2.0
"""Offline particle tracking (MODFLOW 6 PRT) on the flows of a coupled Raven run.

The run must use :WriteGWBudgetFile (Raven then writes mf6/gwf.cbc with every package's flows, the specific discharge
and the saturation, and mf6/gwf.porosity with the porosity of every cell) and a regular or quadtree grid (PRT needs DIS
or DISV; HRU meshes, imported grids and :LayerConnection ELEVATION use DISU). For tracking through time, save the flows
every step (:HeadSaveFrequency 1); with a coarser frequency PRT stops at the first step without saved flows.

    python3 make_prt.py OUTPUT_FOLDER [--backward] [--points FILE] [--radius F] [--run LIBMF6]

  OUTPUT_FOLDER  Raven's output folder (holds mf6/)
  --backward     track backwards in time (capture zones: where the water reaching each release point came from); the
                 head and budget files are reversed into OUTPUT_FOLDER/prt/ with FloPy
  --points FILE  release points, a CSV with columns name,layer,x,y,z (layer from 1, coordinates of the MODFLOW grid as in
                 mf6/gwf.dis(v), z an elevation in m). Default: 8 points around the centre of each well cell of Raven's
                 :Wells (WEL_RAVEN in mf6/gwf.wel), at the cell's middle elevation. Coordinates include the grid's XORIGIN,
                 YORIGIN and ANGROT (Raven's grid frame, metres)
  --radius F     default release points lie F x the cell width from the cell centre (default 0.25); the width is measured
                 along the grid's own axes, so on a rotated grid as on an unrotated one
  --run LIBMF6   run the PRT simulation through the MODFLOW 6 library (no mf6 executable needed); otherwise run
                 mf6 in OUTPUT_FOLDER/prt yourself

Writes OUTPUT_FOLDER/prt/ (mfsim.nam, prt.* files); after a run, prt.trk.csv (PRT's track file) and endpoints.csv
(per particle: release point, end point, travel time [d], the reason the track ended).
"""
import os, sys, re, csv, shutil, ctypes, argparse
import numpy as np


def read_block(path, name):
    """lines of the first 'BEGIN name' block of a MODFLOW 6 input file (comments and blank lines removed)"""
    out, on = [], False
    for l in open(path):
        s = l.split('#')[0].strip()
        if not s:
            continue
        w = s.split()
        if w[0].upper() == 'BEGIN' and len(w) > 1 and w[1].upper() == name.upper():
            on = True; continue
        if on and w[0].upper() == 'END':
            break
        if on:
            out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('output'); ap.add_argument('--backward', action='store_true'); ap.add_argument('--points')
    ap.add_argument('--radius', type=float, default=0.25); ap.add_argument('--run')
    a = ap.parse_args()
    mf = os.path.join(a.output, 'mf6'); prt = os.path.join(a.output, 'prt')
    for f in ('gwf.nam', 'gwf.cbc', 'gwf.hds', 'gwf.porosity', 'sim.tdis'):
        if not os.path.exists(os.path.join(mf, f)):
            sys.exit('make_prt: %s not found: run Raven with :WriteGWBudgetFile (generated models)' % os.path.join(mf, f))
    pk = {l.split()[2].upper(): (l.split()[0].upper(), l.split()[1]) for l in read_block(os.path.join(mf, 'gwf.nam'), 'PACKAGES') if len(l.split()) >= 3}
    dis_type, dis_file = pk['DIS']
    if dis_type not in ('DIS6', 'DISV6'):
        sys.exit('make_prt: the model uses %s; MODFLOW 6 PRT tracks particles on DIS and DISV grids only (regular and quadtree grids)' % dis_type)
    import flopy
    os.makedirs(prt, exist_ok=True)
    grb = flopy.mf6.utils.MfGrdFile(os.path.join(mf, dis_file + '.grb'))
    mg = grb.modelgrid
    # release points
    pts = []
    if a.points:
        for r in csv.DictReader(open(a.points)):
            pts.append((r['name'], int(r['layer']), float(r['x']), float(r['y']), float(r['z'])))
    else:
        wel = os.path.join(mf, 'gwf.wel')
        if not os.path.exists(wel):
            sys.exit('make_prt: no :Wells in the run (mf6/gwf.wel); give the release points with --points')
        for i, l in enumerate(read_block(wel, 'PERIOD')):
            w = l.split()
            if dis_type == 'DIS6':
                lay, row, col = int(w[0]), int(w[1]), int(w[2]); node2 = (row - 1) * mg.ncol + (col - 1)
            else:
                lay, node2 = int(w[0]), int(w[1]) - 1
            xc, yc = np.ravel(mg.xcellcenters)[node2], np.ravel(mg.ycellcenters)[node2]
            xv, yv = np.array(mg.get_cell_vertices(node2 if dis_type == 'DISV6' else (row - 1, col - 1))).T
            xvl, yvl = mg.get_local_coords(xv, yv)   # (the cell's width along the grid's own axes: also on a rotated grid)
            width = min(np.ptp(xvl), np.ptp(yvl))
            top = mg.top.ravel()[node2] if lay == 1 else mg.botm.reshape(mg.nlay, -1)[lay - 2, node2]
            z = 0.5 * (top + mg.botm.reshape(mg.nlay, -1)[lay - 1, node2])
            for k in range(8):
                ang = 2 * np.pi * k / 8.0
                pts.append(('W%d_%d' % (i + 1, k + 1), lay, xc + a.radius * width * np.cos(ang), yc + a.radius * width * np.sin(ang), z))
    # cells of the release points: PRT needs the cell of every point
    rows = []
    for n, (name, lay, x, y, z) in enumerate(pts):
        c = mg.intersect(x, y)
        cid = (lay, c[0] + 1, c[1] + 1) if dis_type == 'DIS6' else (lay, c + 1)
        xl, yl = mg.get_local_coords(x, y)   # (PRT reads release points in the grid's own frame, before XORIGIN/YORIGIN/ANGROT)
        rows.append((n + 1,) + tuple(int(v) for v in cid) + (float(xl), float(yl), float(z), name))
    # time: the flow model's periods (reversed for backward tracking)
    per = [l.split() for l in read_block(os.path.join(mf, 'sim.tdis'), 'PERIODDATA')]
    if a.backward:
        per = per[::-1]
        flopy.utils.HeadFile(os.path.join(mf, 'gwf.hds')).reverse(filename=os.path.join(prt, 'gwf_rev.hds'))
        flopy.utils.CellBudgetFile(os.path.join(mf, 'gwf.cbc'), precision='double').reverse(filename=os.path.join(prt, 'gwf_rev.cbc'))
        hds, cbc = 'gwf_rev.hds', 'gwf_rev.cbc'
    else:
        hds, cbc = '../mf6/gwf.hds', '../mf6/gwf.cbc'
    W = lambda f, t: open(os.path.join(prt, f), 'w').write(t)
    W('mfsim.nam', 'BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN TIMING\n  TDIS6  prt.tdis\nEND TIMING\n\nBEGIN MODELS\n  PRT6  prt.nam  PRT\nEND MODELS\n\n'
                   'BEGIN EXCHANGES\nEND EXCHANGES\n\nBEGIN SOLUTIONGROUP 1\n  EMS6  prt.ems  PRT\nEND SOLUTIONGROUP\n')
    W('prt.tdis', 'BEGIN OPTIONS\n  TIME_UNITS DAYS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NPER %d\nEND DIMENSIONS\n\nBEGIN PERIODDATA\n%sEND PERIODDATA\n'
      % (len(per), ''.join('  %s\n' % ' '.join(p) for p in per)))
    W('prt.ems', 'BEGIN OPTIONS\nEND OPTIONS\n')
    W('prt.nam', 'BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN PACKAGES\n  %s  prt.%s  DIS\n  MIP6  prt.mip  MIP\n  PRP6  prt.prp  PRP\n  FMI6  prt.fmi  FMI\n  OC6  prt.oc  OC\nEND PACKAGES\n'
      % (dis_type, 'dis' if dis_type == 'DIS6' else 'disv'))
    shutil.copy(os.path.join(mf, dis_file), os.path.join(prt, 'prt.dis' if dis_type == 'DIS6' else 'prt.disv'))
    shutil.copy(os.path.join(mf, 'gwf.porosity'), os.path.join(prt, 'prt.mip'))
    W('prt.fmi', 'BEGIN PACKAGEDATA\n  GWFHEAD  FILEIN  %s\n  GWFBUDGET  FILEIN  %s\nEND PACKAGEDATA\n' % (hds, cbc))
    W('prt.prp', 'BEGIN OPTIONS\n  BOUNDNAMES\n  EXIT_SOLVE_TOLERANCE 1e-5\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NRELEASEPTS %d\nEND DIMENSIONS\n\n'
      'BEGIN PACKAGEDATA\n%sEND PACKAGEDATA\n\nBEGIN PERIOD 1\n  FIRST\nEND PERIOD\n'
      % (len(rows), ''.join('  ' + ' '.join(str(v) if not isinstance(v, float) else repr(v) for v in r) + '\n' for r in rows)))
    W('prt.oc', 'BEGIN OPTIONS\n  TRACK FILEOUT prt.trk\n  TRACKCSV FILEOUT prt.trk.csv\nEND OPTIONS\n')
    print('make_prt: PRT simulation with %d release points written to %s (%s tracking)' % (len(rows), prt, 'backward' if a.backward else 'forward'))
    if not a.run:
        return
    lib = ctypes.CDLL(os.path.abspath(a.run)); cwd = os.getcwd(); os.chdir(prt)
    try:
        if lib.initialize(b'mfsim.nam') != 0:
            sys.exit('make_prt: MODFLOW 6 did not initialise the PRT simulation (see %s/mfsim.lst)' % prt)
        t, te = ctypes.c_double(0.0), ctypes.c_double(0.0); lib.get_end_time(ctypes.byref(te))
        while True:
            lib.get_current_time(ctypes.byref(t))
            if t.value >= te.value - 1e-9:
                break
            if lib.update() != 0:
                sys.exit('make_prt: the PRT run failed (see %s/mfsim.lst)' % prt)
        lib.finalize()
    finally:
        os.chdir(cwd)
    trk = os.path.join(prt, 'prt.trk.csv')
    import pandas as pd
    T = pd.read_csv(trk)
    out = []
    for irpt, g in T.groupby('irpt'):
        g = g.sort_values('t'); s, e = g.iloc[0], g.iloc[-1]
        (x0, y0), (x1, y1) = mg.get_coords(s['x'], s['y']), mg.get_coords(e['x'], e['y'])   # (back to the coordinates of gwf.dis(v))
        out.append(dict(particle=int(irpt), name=rows[int(irpt) - 1][-1], x0=x0, y0=y0, z0=s['z'], x1=x1, y1=y1, z1=e['z'],
                        travel_time_d=e['t'] - s['t'], ended=int(e['istatus'])))
    pd.DataFrame(out).to_csv(os.path.join(prt, 'endpoints.csv'), index=False)
    print('make_prt: %d particles tracked; endpoints in %s' % (len(out), os.path.join(prt, 'endpoints.csv')))


if __name__ == '__main__':
    main()
