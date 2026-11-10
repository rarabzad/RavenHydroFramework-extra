# Copyright (c) 2026 Rezgar Arabzadeh -- Raven-MODFLOW 6 groundwater coupling
# SPDX-License-Identifier: Artistic-2.0
"""Offline particle tracking (MODFLOW 6 PRT) on the flows of a coupled Raven run.

The run must use :WriteGWBudgetFile (Raven then writes mf6/gwf.cbc with every package's flows, the specific discharge
and the saturation, and mf6/gwf.porosity with the porosity of every cell) and a regular or quadtree grid (PRT needs DIS
or DISV; HRU meshes, imported grids and :LayerConnection ELEVATION use DISU). For tracking through time, save the flows
every step (:HeadSaveFrequency 1, which tracking needs): the script checks that mf6/gwf.cbc and mf6/gwf.hds hold every
time step of the flow model and stops with a message before writing the PRT files when they do not (a coarser
:HeadSaveFrequency saves only some steps, and PRT can follow the flows only through saved steps).

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

Every point is released once: forward, at the start of Raven's run; backward, at its end. With :GWInitialization
STEADY_STATE the flow model's first stress period is the steady state solved before Raven's first step: forward tracking
releases after it (at the start of the second period), and backward tracking ends where Raven's run starts (the
tracking window is Raven's run; the steady-state period stays in the PRT time discretization, after the window, only
because PRT reads the flow files period by period).

Writes OUTPUT_FOLDER/prt/ (mfsim.nam, prt.* files); after a run, prt.trk.csv (PRT's track file) and endpoints.csv
(per particle: release point and time, the end point within the tracking window, travel time [d] = end - release, PRT's
status code of the track at that point, and why the endpoint was taken there: 'terminated' (PRT ended the track, e.g.
at a well, a boundary or in a weak sink) or 'end of the tracking window').
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
    # time: the flow model's periods (reversed for backward tracking). A first steady-state period followed by others is
    # the steady-state initialization before Raven's run: not part of the tracking window
    per = [l.split() for l in read_block(os.path.join(mf, 'sim.tdis'), 'PERIODDATA')]
    sto = open(os.path.join(mf, 'gwf.sto')).read().upper() if os.path.exists(os.path.join(mf, 'gwf.sto')) else ''
    m = re.search(r'BEGIN\s+PERIOD\s+1\s+(STEADY-STATE|TRANSIENT)', sto)
    steady0 = (len(per) > 1) and (m is not None) and (m.group(1) == 'STEADY-STATE')
    plen = [float(p[0]) for p in per]
    # PRT reads the flows of every time step: the head and budget files must hold each of them (:HeadSaveFrequency 1)
    want = [(k, j) for j, p in enumerate(per) for k in range(int(p[1]))]   # (time step, period), from 0 as FloPy counts
    have_c = set(tuple(int(v) for v in x) for x in flopy.utils.CellBudgetFile(os.path.join(mf, 'gwf.cbc'), precision='double').get_kstpkper())
    have_h = set(tuple(int(v) for v in x) for x in flopy.utils.HeadFile(os.path.join(mf, 'gwf.hds')).get_kstpkper())
    miss_c, miss_h = [w for w in want if w not in have_c], [w for w in want if w not in have_h]
    if miss_c or miss_h:
        sys.exit('make_prt: the flow model has %d time steps, but mf6/gwf.cbc holds flows for %d of them and mf6/gwf.hds heads for '
                 '%d (first missing: time step %d of period %d). PRT needs the flows and heads of every step: run Raven again with '
                 ':HeadSaveFrequency 1 (and :WriteGWBudgetFile) in the .rvg'
                 % (len(want), len(want) - len(miss_c), len(want) - len(miss_h), (miss_c or miss_h)[0][0] + 1, (miss_c or miss_h)[0][1] + 1))
    if a.backward:
        release_per, t0 = 1, 0.0                                       # (reversed: period 1 is the last period of the run)
        t1 = sum(plen) - (plen[0] if steady0 else 0.0)                 # Raven's start, in reversed time
    else:
        release_per = 2 if steady0 else 1
        t0 = plen[0] if steady0 else 0.0; t1 = sum(plen)
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
      'BEGIN PACKAGEDATA\n%sEND PACKAGEDATA\n\n%s'
      % (len(rows), ''.join('  ' + ' '.join(str(v) if not isinstance(v, float) else repr(v) for v in r) + '\n' for r in rows),
         # one release, in release_per; a PERIOD block's setting carries over to later periods, so the next period has an
         # empty block (no release)
         ''.join('BEGIN PERIOD %d\n%sEND PERIOD\n\n' % (p, '  FIRST\n' if p == release_per else '')
                 for p in range(1, len(per) + 1) if p in (release_per, release_per + 1))))
    W('prt.oc', 'BEGIN OPTIONS\n  TRACK FILEOUT prt.trk\n  TRACKCSV FILEOUT prt.trk.csv\nEND OPTIONS\n')
    print('make_prt: PRT simulation with %d release points written to %s (%s tracking, released at PRT time %g d, tracking window %g to %g d)'
          % (len(rows), prt, 'backward' if a.backward else 'forward', t0, t0, t1))
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
    for (irpt, trel), g in T.groupby(['irpt', 'trelease']):
        g = g[g['t'] <= t1 + 1e-9].sort_values('t'); s, e = g.iloc[0], g.iloc[-1]
        # (PRT's status 1: still active, 10: stopped at the end of the simulation; any other: the track ended there)
        last = (len(T[(T['irpt'] == irpt) & (T['trelease'] == trel)]) == len(g)) and (int(e['istatus']) not in (1, 10))
        (x0, y0), (x1, y1) = mg.get_coords(s['x'], s['y']), mg.get_coords(e['x'], e['y'])   # (back to the coordinates of gwf.dis(v))
        out.append(dict(particle=int(irpt), name=rows[int(irpt) - 1][-1], release_time_d=float(trel), x0=x0, y0=y0, z0=s['z'],
                        x1=x1, y1=y1, z1=e['z'], travel_time_d=e['t'] - trel, ended=int(e['istatus']),
                        end='terminated' if last else 'end of the tracking window'))
    if len(out) != len(rows) or any(abs(r['release_time_d'] - t0) > 1e-9 for r in out):
        sys.exit('make_prt: %d tracks for %d release points, released at %s d (expected one release each at %g d)'
                 % (len(out), len(rows), sorted({r['release_time_d'] for r in out}), t0))
    pd.DataFrame(out).to_csv(os.path.join(prt, 'endpoints.csv'), index=False)
    print('make_prt: %d particles tracked; endpoints in %s' % (len(out), os.path.join(prt, 'endpoints.csv')))


if __name__ == '__main__':
    main()
