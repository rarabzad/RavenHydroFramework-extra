"""Existing-model family of the rough-terrain suite (every fourth seed; rough_models.gen_spec(seed, 'ext')).

Raven couples a small MODFLOW 6 model written here (:MF6Simulation, cells placed by :MF6GridFile) instead of building
one. The model varies:
  grid      DIS (regular) or DISV (the same rows and columns with the inner vertices moved by up to 15 % of a cell:
            irregular quadrilaterals), cell size and HRU tiling as the generated family
  top       the cells' mean land (5 x 5 DEM samples) less the soil-zone thickness, moved up or down by up to the thickness
            (the soil-zone base of an existing model is its top: cell tops above and below the base the DEM gives, at
            different samples of the same cell)
  layers    1-3 layers whose thicknesses tilt across the model (sloping, pinching layers) with random noise; a layer
            below the first that thins below 0.5 m becomes a vertical pass-through cell (IDOMAIN -1); inactive columns
            (IDOMAIN 0) and columns whose first layer is inactive (the top active cell is in layer 2)
  material  the case's aquifer classes per layer (K11 = K_HORIZ, K33 = K_VERT, SY, SS); a confined bottom layer
            (ICELLTYPE 0, ICONVERT 0) in some models
  solver    NEWTON in most models (a few without it, to test the stop: :SoilZone PHYSICAL needs NEWTON), the IMS
            settings Raven writes for its own models
  heads     a specified head (the model's own CHD package) in the top cells along the low edge; starting heads at
            INITIAL_HEAD_DEPTH below the top
"""
import os, json, math
import numpy as np

def ext_spec(S, rng):
    """adds the existing model's description to spec S (drawn from the case's random stream)"""
    nl = int(rng.integers(1, 4))
    th = [float(round(rng.uniform(0.6, 6.0), 4))] + [float(round(rng.choice([rng.uniform(0.3, 1.0), rng.uniform(1.0, 8.0)]), 4)) for _ in range(nl - 1)]
    ncls = len(S['classes'])
    S['ext'] = dict(dis=str(rng.choice(['DIS', 'DISV'], p=[0.7, 0.3])), newton=bool(rng.random() < 0.94), nlay=nl, th=th,
                    tilt=[float(rng.uniform(-0.9, 0.9)) for _ in range(nl)], noise=float(rng.uniform(0.0, 0.3)),
                    top_off=float(rng.uniform(0.0, 1.0)), inactive=float(rng.choice([0.0, 0.0, rng.uniform(0.02, 0.12)])),
                    l1_off=float(rng.choice([0.0, 0.0, rng.uniform(0.02, 0.1)])), perturb=float(rng.uniform(0.0, 0.15)),
                    lcls=['AQ%d' % int(rng.integers(0, ncls)) for _ in range(nl)], confined=bool(nl > 1 and rng.random() < 0.2),
                    seed2=int(rng.integers(0, 2 ** 31 - 1)))

def _cells(S):
    """the model grid: origin, rows, columns and the cell outlines (projected metres, clockwise), rows from the north"""
    from rough_models import _hru_polys
    polys = _hru_polys(S); cs = S['cell']
    xa = min(p.bounds[0] for p in polys); ya = min(p.bounds[1] for p in polys)
    xb = max(p.bounds[2] for p in polys); yb = max(p.bounds[3] for p in polys)
    gx0, gy0 = math.floor(xa / cs) * cs, math.floor(ya / cs) * cs
    ncol, nrow = max(1, int(math.ceil((xb - gx0) / cs))), max(1, int(math.ceil((yb - gy0) / cs)))
    E = S['ext']; rng = np.random.default_rng(E['seed2'])
    V = np.zeros((nrow + 1, ncol + 1, 2))   # vertex (i from the north, j from the west)
    for i in range(nrow + 1):
        for j in range(ncol + 1):
            V[i, j] = (gx0 + j * cs, gy0 + (nrow - i) * cs)
            if E['dis'] == 'DISV' and 0 < i < nrow and 0 < j < ncol:
                V[i, j] += rng.uniform(-E['perturb'], E['perturb'], 2) * cs
    rings = []
    for r in range(nrow):
        for c in range(ncol):
            rings.append([tuple(V[r, c]), tuple(V[r, c + 1]), tuple(V[r + 1, c + 1]), tuple(V[r + 1, c])])   # clockwise
    return gx0, gy0, nrow, ncol, V, rings, rng

def build_model(d, S, polys, Dk, method, meta):
    """writes the MODFLOW 6 model into d/model and the grid file d/cells.geojson; returns the model part of the .rvg"""
    from rough_models import Raster, sample_points, ll_np
    from sz_models import ll
    from shapely.geometry import Polygon
    E = S['ext']; cs = S['cell']
    gx0, gy0, nrow, ncol, V, rings, rng = _cells(S)
    ncpl = nrow * ncol; nl = E['nlay']
    dem = Raster(os.path.join(d, 'dem.asc'))
    cellP = [Polygon(r) for r in rings]
    land = np.zeros(ncpl); Dc = np.zeros(ncpl); cover = np.zeros(ncpl)
    for ic in range(ncpl):
        b = cellP[ic].bounds
        pts = sample_points(b[0], b[2], b[1], b[3], 5, None if E['dis'] == 'DIS' else rings[ic])
        lo, la = ll_np([p[0] for p in pts], [p[1] for p in pts]); v = dem.sample(lo, la); v = v[np.isfinite(v)]
        land[ic] = float(np.mean(v)) if len(v) else np.nan
        a = 0.0
        for k, p in enumerate(polys):
            A = p.intersection(cellP[ic]).area; a += A; Dc[ic] += A * Dk[k]
        cover[ic] = a; Dc[ic] = Dc[ic] / a if a > 0 else max(Dk)
    ok = np.isfinite(land)
    land[~ok] = np.nanmean(land) if ok.any() else S['land']['z0']
    # columns: inactive (IDOMAIN 0) where not covered, a few at random; every HRU keeps an active column
    idom = np.ones((nl, ncpl), int)
    act = cover > 1e-6
    for ic in range(ncpl):
        if rng.random() < E['inactive']: act[ic] = False
    for k, p in enumerate(polys):
        if not any(act[ic] and p.intersection(cellP[ic]).area > 1e-6 for ic in range(ncpl)):
            best = max(range(ncpl), key=lambda ic: p.intersection(cellP[ic]).area); act[best] = True
    top = land - Dc + E['top_off'] * Dc * rng.uniform(-1.0, 1.0, ncpl)
    xs = np.array([cellP[ic].centroid.x for ic in range(ncpl)]); ys = np.array([cellP[ic].centroid.y for ic in range(ncpl)])
    u = (xs - xs.mean()) / max(np.ptp(xs), cs) * 2.0 + (ys - ys.mean()) / max(np.ptp(ys), cs)
    botm = np.zeros((nl, ncpl)); prev = top.copy()
    for l in range(nl):
        t = E['th'][l] * (1.0 + E['tilt'][l] * u) * (1.0 + E['noise'] * rng.uniform(-1, 1, ncpl))
        if l == 0:
            t = np.maximum(t, 0.5)
        else:
            t = np.maximum(t, 0.05)
            idom[l, t < 0.5] = -1      # pinched out: vertical pass-through
        botm[l] = prev - t; prev = botm[l]
    for ic in range(ncpl):
        if not act[ic]: idom[:, ic] = 0
        elif nl > 1 and idom[1, ic] == 1 and rng.random() < E['l1_off']: idom[0, ic] = 0
    # a column needs an active cell: one whose cells below the first are all pass-through keeps its first layer
    for ic in range(ncpl):
        if act[ic] and not (idom[:, ic] > 0).any(): idom[0, ic] = 1
    md = os.path.join(d, 'model'); os.makedirs(md, exist_ok=True)
    def arr(a, fmt):
        a = np.asarray(a).reshape(-1, ncol if E['dis'] == 'DIS' else ncpl)
        return ''.join('      ' + ' '.join(fmt % v for v in row) + '\n' for row in a)
    with open(os.path.join(md, 'mfsim.nam'), 'w') as f:
        f.write('BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN TIMING\n  TDIS6 sim.tdis\nEND TIMING\n\nBEGIN MODELS\n  GWF6 gwf.nam gwf\nEND MODELS\n\n'
                'BEGIN EXCHANGES\nEND EXCHANGES\n\nBEGIN SOLUTIONGROUP 1\n  IMS6 sim.ims gwf\nEND SOLUTIONGROUP\n')
    days = meta['days']
    with open(os.path.join(md, 'sim.tdis'), 'w') as f:
        f.write('BEGIN OPTIONS\n  TIME_UNITS DAYS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NPER 1\nEND DIMENSIONS\n\nBEGIN PERIODDATA\n  %d.0 %d 1.0\nEND PERIODDATA\n' % (days, days))
    with open(os.path.join(md, 'sim.ims'), 'w') as f:
        f.write('BEGIN OPTIONS\n  PRINT_OPTION SUMMARY\n  COMPLEXITY COMPLEX\nEND OPTIONS\n\nBEGIN NONLINEAR\n  OUTER_DVCLOSE 1e-05\n  OUTER_MAXIMUM 500\n'
                '  UNDER_RELAXATION DBD\n  UNDER_RELAXATION_THETA 0.7\n  UNDER_RELAXATION_KAPPA 0.07\n  UNDER_RELAXATION_GAMMA 0.1\n  UNDER_RELAXATION_MOMENTUM 0.0\n'
                '  BACKTRACKING_NUMBER 20\n  BACKTRACKING_TOLERANCE 1.05\n  BACKTRACKING_REDUCTION_FACTOR 0.1\n  BACKTRACKING_RESIDUAL_LIMIT 0.002\nEND NONLINEAR\n\n'
                'BEGIN LINEAR\n  INNER_MAXIMUM 500\n  INNER_DVCLOSE 1e-06\n  INNER_RCLOSE 1.0\n  LINEAR_ACCELERATION BICGSTAB\n  PRECONDITIONER_LEVELS 5\n'
                '  PRECONDITIONER_DROP_TOLERANCE 0.0001\n  NUMBER_ORTHOGONALIZATIONS 2\nEND LINEAR\n')
    chd = []
    if S.get('chd') is not None:   # the model's own specified heads: the top active cells along the low edge
        a = S['land']['aspect']; ca, sa = math.cos(a), math.sin(a)
        side = ('E' if ca > 0 else 'W') if abs(ca) >= abs(sa) else ('N' if sa > 0 else 'S')
        x0, x1, y0, y1 = S['domain']
        sel = [ic for ic in range(ncpl) if act[ic] and ((side == 'E' and xs[ic] > x1 - cs) or (side == 'W' and xs[ic] < x0 + cs) or
                                                        (side == 'N' and ys[ic] > y1 - cs) or (side == 'S' and ys[ic] < y0 + cs))]
        if sel:
            tn = {ic: int(np.argmax(idom[:, ic] > 0)) for ic in sel}
            h = min(land[ic] for ic in sel) - S['chd']
            h = max(h, max(botm[tn[ic], ic] for ic in sel) + 0.2)
            chd = [(tn[ic], ic, h) for ic in sel]
            meta['chd_head'] = float(h)
    with open(os.path.join(md, 'gwf.nam'), 'w') as f:
        f.write('BEGIN OPTIONS\n%sEND OPTIONS\n\nBEGIN PACKAGES\n  %s6  gwf.dis  DIS\n  NPF6  gwf.npf  NPF\n  STO6  gwf.sto  STO\n  IC6   gwf.ic   IC\n%s  OC6   gwf.oc   OC\nEND PACKAGES\n'
                % ('  NEWTON\n' if E['newton'] else '', E['dis'], '  CHD6  gwf.chd  CHD\n' if chd else ''))
    with open(os.path.join(md, 'gwf.dis'), 'w') as f:
        if E['dis'] == 'DIS':
            f.write('BEGIN OPTIONS\n  LENGTH_UNITS METERS\n  XORIGIN %.10g\n  YORIGIN %.10g\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NLAY %d\n  NROW %d\n  NCOL %d\nEND DIMENSIONS\n\n'
                    'BEGIN GRIDDATA\n  DELR\n    CONSTANT %g\n  DELC\n    CONSTANT %g\n' % (gx0, gy0, nl, nrow, ncol, cs, cs))
        else:
            f.write('BEGIN OPTIONS\n  LENGTH_UNITS METERS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  NLAY %d\n  NCPL %d\n  NVERT %d\nEND DIMENSIONS\n\nBEGIN GRIDDATA\n' % (nl, ncpl, (nrow + 1) * (ncol + 1)))
        f.write('  TOP\n    INTERNAL FACTOR 1.0\n' + arr(top, '%.10f') + '  BOTM LAYERED\n')
        for l in range(nl): f.write('    INTERNAL FACTOR 1.0\n' + arr(botm[l], '%.10f'))
        f.write('  IDOMAIN LAYERED\n')
        for l in range(nl): f.write('    INTERNAL FACTOR 1\n' + arr(idom[l], '%d'))
        f.write('END GRIDDATA\n')
        if E['dis'] == 'DISV':
            f.write('\nBEGIN VERTICES\n')
            for i in range(nrow + 1):
                for j in range(ncol + 1): f.write('  %d %.10f %.10f\n' % (i * (ncol + 1) + j + 1, V[i, j, 0], V[i, j, 1]))
            f.write('END VERTICES\n\nBEGIN CELL2D\n')
            for r in range(nrow):
                for c in range(ncol):
                    ic = r * ncol + c; P = cellP[ic].centroid
                    vs = [r * (ncol + 1) + c + 1, r * (ncol + 1) + c + 2, (r + 1) * (ncol + 1) + c + 2, (r + 1) * (ncol + 1) + c + 1]
                    f.write('  %d %.10f %.10f 4 %s\n' % (ic + 1, P.x, P.y, ' '.join(str(v) for v in vs)))
            f.write('END CELL2D\n')
    cls = {c['name']: c for c in S['classes']}
    lc = [cls[n] for n in E['lcls']]
    conf = [E['confined'] and l == nl - 1 for l in range(nl)]
    with open(os.path.join(md, 'gwf.npf'), 'w') as f:
        f.write('BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\n\nBEGIN GRIDDATA\n  ICELLTYPE LAYERED\n')
        for l in range(nl): f.write('    CONSTANT %d\n' % (0 if conf[l] else 1))
        f.write('  K LAYERED\n'); [f.write('    CONSTANT %.8g\n' % lc[l]['Kh']) for l in range(nl)]
        f.write('  K33 LAYERED\n'); [f.write('    CONSTANT %.8g\n' % lc[l]['Kv']) for l in range(nl)]
        f.write('END GRIDDATA\n')
    with open(os.path.join(md, 'gwf.sto'), 'w') as f:
        f.write('BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\n\nBEGIN GRIDDATA\n  ICONVERT LAYERED\n')
        for l in range(nl): f.write('    CONSTANT %d\n' % (0 if conf[l] else 1))
        f.write('  SS LAYERED\n'); [f.write('    CONSTANT %.6g\n' % lc[l]['Ss']) for l in range(nl)]
        f.write('  SY LAYERED\n'); [f.write('    CONSTANT %.6g\n' % lc[l]['Sy']) for l in range(nl)]
        f.write('END GRIDDATA\n\nBEGIN PERIOD 1\n  TRANSIENT\nEND PERIOD\n')
    low = np.array([botm[np.where(idom[:, ic] > 0)[0][-1], ic] if (idom[:, ic] > 0).any() else botm[-1, ic] for ic in range(ncpl)])
    h0 = np.maximum(top - S['init_depth'], low + 0.1)
    with open(os.path.join(md, 'gwf.ic'), 'w') as f:
        f.write('BEGIN GRIDDATA\n  STRT LAYERED\n')
        for l in range(nl): f.write('    INTERNAL FACTOR 1.0\n' + arr(h0, '%.10f'))
        f.write('END GRIDDATA\n')
    if chd:
        with open(os.path.join(md, 'gwf.chd'), 'w') as f:
            f.write('BEGIN OPTIONS\nEND OPTIONS\n\nBEGIN DIMENSIONS\n  MAXBOUND %d\nEND DIMENSIONS\n\nBEGIN PERIOD 1\n' % len(chd))
            for (l, ic, h) in chd:
                f.write('  %d %s %.10f\n' % (l + 1, ('%d %d' % (ic // ncol + 1, ic % ncol + 1)) if E['dis'] == 'DIS' else str(ic + 1), h))
            f.write('END PERIOD\n')
    with open(os.path.join(md, 'gwf.oc'), 'w') as f:
        f.write('BEGIN OPTIONS\n  HEAD FILEOUT gwf.hds\nEND OPTIONS\n\nBEGIN PERIOD 1\n  SAVE HEAD ALL\nEND PERIOD\n')
    feats = [{"type": "Feature", "properties": {"cell": ic + 1}, "geometry": {"type": "Polygon", "coordinates": [[list(ll(x, y)) for (x, y) in list(rings[ic])[::-1] + [rings[ic][-1]]]]}}
             for ic in range(ncpl)]
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(d, 'cells.geojson'), 'w'))
    meta['ext'] = dict(x0=gx0, y0=gy0, nrow=nrow, ncol=ncol, rings=[[list(p) for p in r] for r in rings], top=top.tolist(), botm=botm.tolist(),
                       idomain=idom.tolist(), chd_cells=[[l, ic] for (l, ic, h) in chd])
    body = ':MF6Simulation model/mfsim.nam\n:MF6GridFile cells.geojson cell\n:MF6StartDate 2000-01-01\n:MinCellCoverage %g\n' % S['min_cover']
    if method != 'NONE':
        body += ':SoilZoneAquiferClass %s\n' % E['lcls'][0]
    return body
