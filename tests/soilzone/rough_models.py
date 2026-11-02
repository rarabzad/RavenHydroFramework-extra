"""Generator of the rough-terrain stress cases (test_rough_terrain.py; manual, "Verification on rough terrain").

gen_spec(seed, family) draws a case from its seed: a JSON-serialisable dict (the "spec") that describes everything the
model needs; build(d, S, method, vz_classes, extra_rvg, days) writes the Raven model of spec S into folder d (for the
existing-model family also the MODFLOW 6 model, rough_ext.py) and returns the meta dict the checks use (HRU polygons in
projected metres, soil-zone thickness of each HRU, ...); it also writes d/case.json = {spec, meta}, which
test_rough_terrain.py --case accepts.

What a generated case ('gen') varies:
  ground    a plane sloping 0-30 % in any direction plus roughness: spectral noise, bumps, pits, closed depressions,
            cliffs (steps a few metres wide or sharper than the DEM), ridges; the relief inside a cell from much smaller to
            much larger than the soil-zone thickness D
  DEM       resolution 0.08-1.6 cells (finer and coarser than the grid), edges inside the grid (dem_cut), NODATA holes
  HRUs      a tiling of the domain cut at random positions (edges on and off cell edges, HRUs inside one cell), domain
            edges on cell edges or inside cells, :MinCellCoverage 0.1-0.5
  soil      two soil profiles by position (west/east), 2 layers, D 0.3-3 m, Campbell retention for the capillary rise
  aquifer   two aquifer profiles by position (south/north), 1-3 layers of 2-3 contrasting aquifer classes (Kh, Kv down to
            mm/d, Sy 0.02-0.3, retention of the columns), thin layers, layers that slope and pinch out on a sloping
            bedrock raster (or DEFAULT_BEDROCK_DEPTH), layers clipped at bedrock and pass-through cells; the bedrock
            capped at max D + 1.0123 m below the land (no column without an aquifer) unless the case is an outcrop case
            (bedrock above the soil-zone base under a whole HRU: a justified stop)
  water     :SoilZoneSubgrid 1/3/5/9, SEEPAGE_SMOOTHING_DEPTH 0.02-0.5 m, mean rain 8-45 mm/d on 10-40 wet days (daily
            2.4-77 mm/d) between dry spells, soil evaporation, start deep (3-15 m), shallow or at the land, a specified
            head along the low edge, :SoilZoneCapillaryRise ON/OFF/default, :SoilZoneExchangeTiming LAGGED/AFTER
The existing-model family ('ext', every fourth seed) is described in rough_ext.py.
"""
import os, json, math
import numpy as np
from sz_models import ll, xy, LAT0, LON0, R_EARTH

METHODS = ('NONE', 'RICHARDS', 'KINEMATIC', 'LAG')

def family_of(seed):
    """the family of a seed in the suite: every fourth seed an existing model"""
    return 'ext' if seed % 4 == 0 else 'gen'

# ---------------------------------------------------------------------------------------------------- fields
def field(F, X, Y):
    """elevation [m] of field spec F at projected X, Y (arrays): a plane plus terms"""
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    ca, sa = math.cos(F['aspect']), math.sin(F['aspect'])
    z = F['z0'] - F['slope'] * (X * ca + Y * sa)
    for t in F['terms']:
        k = t[0]
        if k == 'wave':                  # spectral noise component: amp, kx, ky, phase
            _, a, kx, ky, ph = t; z = z + a * np.cos(kx * X + ky * Y + ph)
        elif k == 'bump':                # gaussian bump (h > 0) or pit (h < 0): x, y, r, h
            _, x0, y0, r, h = t; z = z + h * np.exp(-((X - x0) ** 2 + (Y - y0) ** 2) / (r * r))
        elif k == 'bowl':                # closed depression with a sharp rim: x, y, r, depth
            _, x0, y0, r, h = t; q = ((X - x0) ** 2 + (Y - y0) ** 2) / (r * r); z = z - h * np.clip(1.0 - q, 0.0, None)
        elif k == 'cliff':               # step of height h across a line (normal angle th, offset c) over width w
            _, th, c, h, w = t; s = (X * math.cos(th) + Y * math.sin(th) - c) / max(w, 1e-6)
            s = np.clip(s + 0.5, 0.0, 1.0); z = z + h * s * s * (3.0 - 2.0 * s)
        elif k == 'ridge':               # ridge (h > 0) or trench (h < 0) along a line: th, c, h, w
            _, th, c, h, w = t; s = (X * math.cos(th) + Y * math.sin(th) - c) / w; z = z + h * np.exp(-s * s)
    return z

# ---------------------------------------------------------------------------------------------------- rasters
def raster_over(path, F, x0, x1, y0, y1, res, holes=(), keep=None, cap=None):
    """writes field F as an ESRI ASCII raster (lon/lat) covering the projected box [x0,x1]x[y0,y1], about res metres per
    raster cell along x; holes: [(x, y, r)] NODATA discs; keep(X, Y) False: NODATA (a DEM that ends inside the grid);
    cap = (Fland, depth): values at most Fland - depth at every raster point"""
    lons, lats = [], []
    for (a, b) in ((x0, y0), (x1, y0), (x0, y1), (x1, y1), (0.5 * (x0 + x1), y0), (0.5 * (x0 + x1), y1)):
        lo, la = ll(a, b); lons.append(lo); lats.append(la)
    csd = math.degrees(res / (R_EARTH * math.cos(math.radians(LAT0))))
    lonA, latA = min(lons) - csd, min(lats) - csd
    ncol = int(math.ceil((max(lons) + csd - lonA) / csd)); nrow = int(math.ceil((max(lats) + csd - latA) / csd))
    csd_s = '%.12f' % csd; csd = float(csd_s)
    LON = lonA + (np.arange(ncol) + 0.5) * csd
    LAT = latA + (nrow - np.arange(nrow) - 0.5) * csd
    LO, LA = np.meshgrid(LON, LAT)
    X, Y = xy_np(LO, LA)
    Z = field(F, X, Y)
    if cap is not None:
        Z = np.minimum(Z, field(cap[0], X, Y) - cap[1])
    bad = np.zeros(Z.shape, bool)
    for (hx, hy, hr) in holes:
        bad |= (X - hx) ** 2 + (Y - hy) ** 2 < hr * hr
    if keep is not None:
        bad |= ~keep(X, Y)
    with open(path, 'w') as f:
        f.write('ncols %d\nnrows %d\nxllcorner %.10f\nyllcorner %.10f\ncellsize %s\nNODATA_value -9999\n' % (ncol, nrow, lonA, latA, csd_s))
        for r in range(nrow):
            f.write(' '.join('-9999' if bad[r, c] else '%.4f' % Z[r, c] for c in range(ncol)) + '\n')

def xy_np(lon, lat):
    """forward LAEA (sz_models.xy) on arrays"""
    p, l = np.radians(lat), np.radians(lon) - math.radians(LON0)
    p0 = math.radians(LAT0)
    k = np.sqrt(2.0 / (1.0 + math.sin(p0) * np.sin(p) + math.cos(p0) * np.cos(p) * np.cos(l)))
    return R_EARTH * k * np.cos(p) * np.sin(l), R_EARTH * k * (math.cos(p0) * np.sin(p) - math.sin(p0) * np.cos(p) * np.cos(l))

def ll_np(x, y):
    """inverse LAEA (sz_models.ll) on arrays"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    p0, l0 = math.radians(LAT0), math.radians(LON0)
    rho = np.hypot(x, y); rho_s = np.where(rho < 1e-9, 1.0, rho)
    c = 2.0 * np.arcsin(np.minimum(1.0, rho_s / (2.0 * R_EARTH)))
    lat = np.arcsin(np.cos(c) * math.sin(p0) + y * np.sin(c) * math.cos(p0) / rho_s)
    lon = l0 + np.arctan2(x * np.sin(c), rho_s * math.cos(p0) * np.cos(c) - y * math.sin(p0) * np.sin(c))
    lat = np.where(rho < 1e-9, p0, lat); lon = np.where(rho < 1e-9, l0, lon)
    return np.degrees(lon), np.degrees(lat)

class Raster:
    """an ESRI ASCII raster read back from its file, sampled as Raven samples it (bilinear between raster-cell centres,
    no-data corners left out and the weights renormalised; points more than a raster cell outside: no data)"""
    def __init__(self, path):
        with open(path) as f:
            h = {}
            for _ in range(6):
                k, v = f.readline().split(); h[k.lower()] = v
            self.v = np.array(f.read().split(), float).reshape(int(h['nrows']), int(h['ncols']))
        self.nr, self.nc = self.v.shape
        self.xll, self.yll, self.cs = float(h['xllcorner']), float(h['yllcorner']), float(h['cellsize'])
        self.nodata = float(h.get('nodata_value', -9999))
        self.valid = np.abs(self.v - self.nodata) > 1e-6

    def sample(self, lon, lat):
        """values at lon, lat (arrays); NaN where Raven has no data"""
        lon = np.atleast_1d(np.asarray(lon, float)); lat = np.atleast_1d(np.asarray(lat, float))
        ytop = self.yll + self.nr * self.cs
        fc = (lon - self.xll) / self.cs - 0.5; fr = (ytop - lat) / self.cs - 0.5
        out = (fc < -1.0) | (fr < -1.0) | (fc > self.nc) | (fr > self.nr)
        fc = np.clip(fc, 0.0, self.nc - 1.0); fr = np.clip(fr, 0.0, self.nr - 1.0)
        c0 = np.floor(fc).astype(int); r0 = np.floor(fr).astype(int)
        c1 = np.minimum(c0 + 1, self.nc - 1); r1 = np.minimum(r0 + 1, self.nr - 1)
        wc, wr = fc - c0, fr - r0
        s = np.zeros(lon.shape); ws = np.zeros(lon.shape)
        for rr, cc, w in ((r0, c0, (1 - wr) * (1 - wc)), (r0, c1, (1 - wr) * wc), (r1, c0, wr * (1 - wc)), (r1, c1, wr * wc)):
            ok = self.valid[rr, cc]
            s += np.where(ok, w * self.v[rr, cc], 0.0); ws += np.where(ok, w, 0.0)
        val = np.where(ws < 1e-9, np.nan, s / np.where(ws < 1e-9, 1.0, ws))
        return np.where(out, np.nan, val)

# ---------------------------------------------------------------------------------------------------- spec
def _logu(rng, a, b):
    return float(math.exp(rng.uniform(math.log(a), math.log(b))))

def _terms(rng, L, W, relief, x0, y0, n_extra=None):
    """roughness terms whose amplitudes scale with relief [m] over a domain of L x W m starting at x0, y0"""
    T = []
    nw = int(rng.integers(0, 7))
    for _ in range(nw):                                   # spectral noise: wavelength 0.3 cell .. domain, amplitude ~ wavelength^0.8
        lam = _logu(rng, 0.04 * max(L, W), 1.2 * max(L, W)); th = rng.uniform(0, 2 * math.pi)
        k = 2 * math.pi / lam
        T.append(['wave', float(relief * 0.5 * (lam / max(L, W)) ** 0.8 * rng.uniform(0.3, 1.0)), float(k * math.cos(th)), float(k * math.sin(th)), float(rng.uniform(0, 2 * math.pi))])
    for _ in range(int(rng.integers(0, 4))):              # bumps and pits
        T.append(['bump', float(x0 + rng.uniform(0, L)), float(y0 + rng.uniform(0, W)), float(_logu(rng, 0.03 * L, 0.4 * L)),
                  float(relief * rng.uniform(0.3, 1.5) * (1 if rng.random() < 0.5 else -1))])
    for _ in range(int(rng.integers(0, 3))):              # closed depressions
        T.append(['bowl', float(x0 + rng.uniform(0, L)), float(y0 + rng.uniform(0, W)), float(_logu(rng, 0.05 * L, 0.35 * L)), float(relief * rng.uniform(0.3, 1.2))])
    if rng.random() < 0.3:                                # cliff (step), sometimes sharper than the DEM
        th = rng.uniform(0, 2 * math.pi); cx, cy = x0 + rng.uniform(0.2, 0.8) * L, y0 + rng.uniform(0.2, 0.8) * W
        T.append(['cliff', float(th), float(cx * math.cos(th) + cy * math.sin(th)), float(relief * rng.uniform(0.5, 3.0) * (1 if rng.random() < 0.5 else -1)), float(_logu(rng, 0.2, 0.15 * L))])
    if rng.random() < 0.3:                                # ridge or trench
        th = rng.uniform(0, 2 * math.pi); cx, cy = x0 + rng.uniform(0.2, 0.8) * L, y0 + rng.uniform(0.2, 0.8) * W
        T.append(['ridge', float(th), float(cx * math.cos(th) + cy * math.sin(th)), float(relief * rng.uniform(0.5, 2.0) * (1 if rng.random() < 0.6 else -1)), float(_logu(rng, 0.02 * L, 0.2 * L))])
    return T

def _cuts(rng, a, b, n, cs, ngrid):
    """n-1 cut positions in (a, b): some on cell edges, some anywhere"""
    out = []
    for _ in range(n - 1):
        if rng.random() < 0.35:
            out.append(float(round(rng.uniform(a, b) / cs) * cs))
        else:
            out.append(float(rng.uniform(a, b)))
    out = sorted(set(min(max(c, a + 0.05 * cs), b - 0.05 * cs) for c in out))
    return [a] + out + [b]

def gen_spec(seed, family=None):
    """the case of a seed (family 'gen' or 'ext'; default family_of(seed))"""
    family = family or family_of(seed)
    rng = np.random.default_rng([seed, 1 if family == 'ext' else 0, 20261028])
    S = dict(seed=int(seed), family=family)
    cs = float(rng.choice([25.0, 40.0, 50.0, 75.0, 100.0, 150.0]))
    nx, ny = int(rng.integers(4, 10)), int(rng.integers(3, 7))
    S['cell'] = cs
    # domain: edges on cell edges (1 mm inside) or inside cells
    if rng.random() < 0.5:
        x0 = -math.floor(nx / 2) * cs + 1e-3; y0 = -math.floor(ny / 2) * cs + 1e-3; L, W = nx * cs - 2e-3, ny * cs - 2e-3
    else:
        x0 = -math.floor(nx / 2) * cs + rng.uniform(0.15, 0.85) * cs; y0 = -math.floor(ny / 2) * cs + rng.uniform(0.15, 0.85) * cs
        L, W = (nx - rng.uniform(0.2, 1.0)) * cs, (ny - rng.uniform(0.2, 1.0)) * cs
    S['domain'] = [float(x0), float(x0 + L), float(y0), float(y0 + W)]
    # soils (two profiles by position: west / east) and their soil class
    nsoil = 1 if rng.random() < 0.4 else 2
    S['soils'] = [[round(float(rng.uniform(0.15, 1.0)), 4), round(float(rng.uniform(0.15, 2.0)), 4)] for _ in range(nsoil)]   # (rounded as written)
    S['soil'] = dict(n=float(rng.uniform(0.3, 0.5)), sfc=float(rng.uniform(0.25, 0.6)), ksat=_logu(rng, 20, 500), perc=_logu(rng, 5, 60),
                     perc_type=str(rng.choice(['PERC_CONSTANT', 'PERC_GAWSER_CONSTRAIN'])), b=float(rng.uniform(3, 8)), psia=float(rng.uniform(50, 400)))
    D = max(sum(s) for s in S['soils'])
    # ground
    slope = float(rng.choice([0.0, _logu(rng, 0.002, 0.05), _logu(rng, 0.05, 0.30)], p=[0.1, 0.45, 0.45]))
    relief = float(D * _logu(rng, 0.05, 6.0))             # roughness amplitude: much smaller to much larger than D
    S['slope'] = slope; S['relief'] = relief
    S['land'] = dict(z0=float(rng.uniform(200, 400)), slope=slope, aspect=float(rng.uniform(0, 2 * math.pi)), terms=_terms(rng, L, W, relief, x0, y0))
    S['dem_res'] = float(cs * _logu(rng, 0.08, 1.6))
    nh = int(rng.choice([0, 0, 1, 2, 3]))
    S['holes'] = [[float(x0 + rng.uniform(0, L)), float(y0 + rng.uniform(0, W)), float(cs * rng.uniform(0.1, 0.35))] for _ in range(nh)]   # (smaller than a cell: no cell loses all its land samples)
    S['dem_cut'] = float(rng.uniform(0.6, 0.97)) if rng.random() < 0.12 else None
    # HRUs: a tiling cut at random positions; sometimes a small HRU inside one cell
    ncx = int(rng.integers(1, 4)); xs = _cuts(rng, x0, x0 + L, ncx, cs, nx)
    S['hru_x'] = xs; S['hru_y'] = [_cuts(rng, y0, y0 + W, int(rng.integers(1, 4)), cs, ny) for _ in range(len(xs) - 1)]
    S['hru_small'] = None
    if rng.random() < 0.3:   # a one-cell HRU: a rectangle inside a cell (one wholly inside the domain), cut out of the HRU it lies in
        i0, i1 = math.ceil(x0 / cs), math.floor((x0 + L) / cs) - 1; j0, j1 = math.ceil(y0 / cs), math.floor((y0 + W) / cs) - 1
        cx, cy = int(rng.integers(i0, i1 + 1)) * cs, int(rng.integers(j0, j1 + 1)) * cs
        a, b = rng.uniform(0.05, 0.35), rng.uniform(0.65, 0.95)
        S['hru_small'] = [float(cx + a * cs), float(cx + b * cs), float(cy + a * cs), float(cy + b * cs)]
    S['min_cover'] = float(rng.choice([0.1, 0.25, 0.25, 0.5]))
    if not _covered(S):     # every HRU over at least one active column (else Raven stops: not a case the suite means to draw)
        S['min_cover'] = 0.1
        if not _covered(S): S['hru_small'] = None
        while not _covered(S):   # (slivers along the domain edge over thinly covered columns: drop cuts until every HRU is linked)
            yy = [i for i, c in enumerate(S['hru_y']) if len(c) > 2]
            if yy: S['hru_y'][yy[-1]] = [S['hru_y'][yy[-1]][0]] + S['hru_y'][yy[-1]][2:]
            elif len(S['hru_x']) > 2: S['hru_x'] = [S['hru_x'][0]] + S['hru_x'][2:]; S['hru_y'] = S['hru_y'][1:]
            else: break
    # aquifer classes and profiles (two by position: south / north)
    ncls = int(rng.integers(2, 4)); S['classes'] = []
    for i in range(ncls):
        Kh = _logu(rng, 0.05, 30.0); Sy = float(rng.uniform(0.02, 0.3))
        S['classes'].append(dict(name='AQ%d' % i, Kh=Kh, Kv=float(Kh * 10 ** rng.uniform(-2.5, 0.0)), Sy=Sy, Ss=1e-5,
                                 por=float(max(Sy + 0.05, rng.uniform(0.25, 0.45))), b=float(rng.uniform(2, 8)), psia=float(rng.uniform(0.1, 1.0))))
    S['profiles'] = []
    for p in range(1 if rng.random() < 0.4 else 2):
        nl = int(rng.integers(1, 4)); lay = []
        for l in range(nl):
            cls = 'AQ%d' % int(rng.integers(0, ncls))
            if l == nl - 1 and rng.random() < 0.6:
                th = 'TO_BEDROCK'
            elif l == 0:
                th = round(float(rng.uniform(0.6, 6.0)), 4)
            else:
                th = round(float(rng.choice([rng.uniform(0.2, 0.8), rng.uniform(0.8, 6.0)])), 4)
            typ = 'AQUIFER' if l == 0 else str(rng.choice(['AQUIFER', 'AQUITARD', 'CONFINED_AQUIFER'], p=[0.6, 0.2, 0.2]))
            lay.append([cls, th, typ])
        S['profiles'].append(lay)
    thick = max(sum(l[1] if l[1] != 'TO_BEDROCK' else 4.0 for l in P) for P in S['profiles'])
    S['use_bedrock'] = bool(rng.random() < 0.8)
    S['default_bedrock'] = round(float(D + rng.uniform(2.0, 15.0)), 4)
    sb = float(max(0.0, slope + rng.uniform(-0.15, 0.15)))
    S['bedrock'] = dict(z0=float(S['land']['z0'] - D - rng.uniform(1.2, 1.2 * thick + 3.0)), slope=sb, aspect=float(S['land']['aspect'] + rng.uniform(-1.0, 1.0)),
                        terms=_terms(rng, L, W, float(rng.uniform(0.2, 3.0)), x0, y0)[:4])
    S['outcrop'] = bool(S['use_bedrock'] and rng.random() < 0.03)
    # water
    S['subgrid'] = int(rng.choice([1, 3, 5, 9], p=[0.15, 0.25, 0.35, 0.25]))
    S['ds'] = _logu(rng, 0.02, 0.5)
    days = int(rng.integers(40, 91)); S['days'] = days
    d0, nw = int(rng.integers(0, 11)), int(rng.integers(10, 41)); m = float(rng.uniform(8, 45))
    rain = [0.0] * days
    for i in range(d0, min(days, d0 + nw)):
        rain[i] = float(round(min(77.0, max(2.4, m * rng.lognormal(0.0, 0.6))), 2))
    S['rain'] = rain; S['pet'] = float(rng.choice([0.0, rng.uniform(0.5, 4.0)]))
    S['init_depth'] = float(rng.choice([rng.uniform(3.0, 15.0), rng.uniform(0.2, 2.0), 0.0], p=[0.5, 0.4, 0.1]))
    S['chd'] = float(rng.uniform(-0.5, 2.0)) if rng.random() < 0.3 else None      # depth of the specified head below the low edge's land
    S['caprise'] = str(rng.choice(['default', 'ON', 'OFF']))
    S['timing'] = str(rng.choice(['default', 'LAGGED', 'AFTER'], p=[0.4, 0.3, 0.3]))
    if family == 'ext':
        import rough_ext
        rough_ext.ext_spec(S, rng)
    return S

# ---------------------------------------------------------------------------------------------------- geometry
def _covered(S):
    """True when every HRU overlaps a column that the HRUs cover by at least :MinCellCoverage"""
    from shapely.geometry import box
    polys = _hru_polys(S); cs = S['cell']
    xa = min(p.bounds[0] for p in polys); ya = min(p.bounds[1] for p in polys); xb = max(p.bounds[2] for p in polys); yb = max(p.bounds[3] for p in polys)
    gx0, gy0 = math.floor(xa / cs) * cs, math.floor(ya / cs) * cs
    cells = [box(gx0 + i * cs, gy0 + j * cs, gx0 + (i + 1) * cs, gy0 + (j + 1) * cs) for i in range(int(math.ceil((xb - gx0) / cs))) for j in range(int(math.ceil((yb - gy0) / cs)))]
    cov = [sum(p.intersection(c).area for p in polys) for c in cells]
    return all(any(cov[i] >= S['min_cover'] * cs * cs and p.intersection(c).area > 1e-6 for i, c in enumerate(cells)) for p in polys)

def _hru_polys(S):
    """HRU polygons [(x0,x1,y0,y1) rectangles in projected metres] of the tiling, minus the small HRU (which is added
    last, its host split around it)"""
    from shapely.geometry import box
    polys = []
    xs = S['hru_x']
    for i in range(len(xs) - 1):
        ys = S['hru_y'][i]
        for j in range(len(ys) - 1):
            polys.append(box(xs[i], ys[j], xs[i + 1], ys[j + 1]))
    if S.get('hru_small'):
        a = S['hru_small']; sm = box(a[0], a[2], a[1], a[3])
        out = []
        for p in polys:
            if p.intersects(sm) and p.intersection(sm).area > 1e-6:
                q = p.difference(sm)
                if q.geom_type == 'Polygon':
                    out.append(q)
                else:   # split by the hole: cut the host into its pieces left / right of the small HRU
                    xm = 0.5 * (a[0] + a[1]); minx, miny, maxx, maxy = p.bounds
                    for half in (box(minx, miny, xm, maxy), box(xm, miny, maxx, maxy)):
                        h = q.intersection(half)
                        if h.area > 1e-6: out.append(h)
            else:
                out.append(p)
        polys = [p for p in out if p.area > 1e-6] + [sm.intersection(box(S['domain'][0], S['domain'][2], S['domain'][1], S['domain'][3]))]
    from shapely.geometry.polygon import orient
    return [orient(p, 1.0) for p in polys]

def _ring_ll(p):
    return [list(ll(x, y)) for (x, y) in p.exterior.coords]

def _domain(S):
    return S['domain']

def raven_files(d, S, polys, soilof, aqof, Dk, method, vz_classes, extra_rvg, days, rvg_body):
    """the Raven files (.rvi, .rvh, .rvp, .rvt, .rvc, .rvg) of a case; rvg_body: the grid/model part of the .rvg"""
    sp = S['soil']; nsoil = len(S['soils'])
    with open(os.path.join(d, 'm.rvh'), 'w') as f:
        f.write(':SubBasins\n  :Attributes, NAME, DOWNSTREAM_ID, PROFILE, REACH_LENGTH, GAUGED\n  :Units, none, none, none, km, none\n  1, box, -1, NONE, ZERO-, 1\n:EndSubBasins\n')
        f.write(':HRUs\n  :Attributes, AREA, ELEVATION, LATITUDE, LONGITUDE, BASIN_ID, LAND_USE_CLASS, VEG_CLASS, SOIL_PROFILE, AQUIFER_PROFILE, TERRAIN_CLASS, SLOPE, ASPECT\n')
        f.write('  :Units, km2, m, deg, deg, none, none, none, none, none, none, deg, deg\n')
        Fl = S['land']; elevs = []
        for k, p in enumerate(polys):
            c = p.representative_point()
            elevs.append(round(float(field(Fl, c.x, c.y)), 4))
            # (every HRU carries the projection origin as its centroid: Raven's projection origin is their mean, so the
            # projected coordinates of the files are exactly those of the spec)
            f.write('  %d, %.10f, %.4f, %.6f, %.6f, 1, OPEN, GRASS, SOILP%d, AQP%d, [NONE], 0, 0\n' % (k + 1, p.area / 1e6, elevs[-1], LAT0, LON0, soilof[k], aqof[k]))
        f.write(':EndHRUs\n')
    with open(os.path.join(d, 'm.rvi'), 'w') as f:
        f.write(':StartDate 2000-01-01 00:00:00\n:Duration %d\n:TimeStep 1.0\n:Method ORDERED_SERIES\n' % days)
        f.write(':SoilModel SOIL_MULTILAYER 2\n:Routing ROUTE_NONE\n:CatchmentRoute ROUTE_DUMP\n:Evaporation PET_CONSTANT\n')
        f.write(':RainSnowFraction RAINSNOW_DATA\n:OroTempCorrect OROCORR_NONE\n:OroPrecipCorrect OROCORR_NONE\n')
        f.write(':HydrologicProcesses\n  :Precipitation PRECIP_RAVEN ATMOS_PRECIP MULTIPLE\n  :Infiltration INF_RATIONAL PONDED_WATER MULTIPLE\n')
        if S['pet'] > 0:
            f.write('  :SoilEvaporation SOILEVAP_ALL SOIL[0] ATMOSPHERE\n')
        f.write('  :Percolation   %s SOIL[0] SOIL[1]\n  :Percolation   %s SOIL[1] GROUNDWATER\n:EndHydrologicProcesses\n' % (sp['perc_type'], sp['perc_type']))
        f.write(':CustomOutput DAILY AVERAGE Between:SOIL[1].And.GROUNDWATER BY_HRU\n')
        f.write(':GroundwaterModel MODFLOW6\n:WriteMassBalanceFile\n:SilentMode\n')
    with open(os.path.join(d, 'm.rvp'), 'w') as f:
        f.write(':SoilClasses\n  :Attributes\n  :Units\n  SOIL\n:EndSoilClasses\n:SoilProfiles\n')
        for i, s in enumerate(S['soils']):
            f.write('  SOILP%d, 2, SOIL, %.6g, SOIL, %.6g\n' % (i, s[0], s[1]))
        f.write(':EndSoilProfiles\n')
        f.write(':VegetationClasses\n  :Attributes, MAX_HT, MAX_LAI, MAX_LEAF_COND\n  :Units, m, none, mm_per_s\n  GRASS, 1, 1, 5\n:EndVegetationClasses\n')
        f.write(':LandUseClasses\n  :Attributes, IMPERM, FOREST_COV\n  :Units, frac, frac\n  OPEN, 0, 0\n:EndLandUseClasses\n')
        f.write(':SoilParameterList\n  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HYDRAUL_COND, MAX_PERC_RATE, CLAPP_B, AIR_ENTRY_PRESSURE\n'
                '  :Units, none, none, none, mm_per_d, mm_per_d, none, mm\n')
        f.write('  [DEFAULT], %.6g, %.6g, 0.0, %.6g, %.6g, %.6g, %.6g\n:EndSoilParameterList\n' % (sp['n'], sp['sfc'], sp['ksat'], sp['perc'], sp['b'], sp['psia']))
        f.write(':LandUseParameterList\n  :Parameters, PARTITION_COEFF\n  :Units, none\n  [DEFAULT], 0.0\n:EndLandUseParameterList\n')
        f.write(':AquiferClasses\n  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY, CLAPP_B, AIR_ENTRY_PRESSURE\n  :Units, m/d, m/d, 1/m, none, none, none, m\n')
        for c in S['classes']:
            f.write('  %s, %.8g, %.8g, %.6g, %.6g, %.6g, %.6g, %.6g\n' % (c['name'], c['Kh'], c['Kv'], c['Ss'], c['Sy'], c['por'], c['b'], c['psia']))
        f.write(':EndAquiferClasses\n:AquiferProfiles\n')
        for i, P in enumerate(S['profiles']):
            if S['family'] == 'ext':
                f.write('  AQP%d, 0\n' % i)
            else:
                f.write('  AQP%d, %d, %s\n' % (i, len(P), ', '.join('%s, %s, %s' % (l[0], l[1] if l[1] == 'TO_BEDROCK' else '%.6g' % l[1], l[2]) for l in P)))
        f.write(':EndAquiferProfiles\n')
        f.write(':AquiferProfileParameters\n  :Attributes, INITIAL_HEAD_DEPTH, DEFAULT_BEDROCK_DEPTH, SEEPAGE_LEAKANCE, SEEPAGE_SMOOTHING_DEPTH\n  :Units, m, m, 1/d, m\n')
        for i in range(len(S['profiles'])):
            f.write('  AQP%d, %.6g, %.6g, 1.0, %.6g\n' % (i, S['init_depth'], S['default_bedrock'], S['ds']))
        f.write(':EndAquiferProfileParameters\n')
    rains = list(S['rain'][:days]) + [0.0] * max(0, days - len(S['rain']))
    with open(os.path.join(d, 'm.rvt'), 'w') as f:
        f.write(':Gauge G\n  :Latitude %.6f\n  :Longitude %.6f\n  :Elevation %g\n' % (LAT0, LON0, S['land']['z0']))
        f.write('  :Data RAINFALL mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + ''.join('    %g\n' % r for r in rains) + '  :EndData\n')
        f.write('  :Data SNOWFALL mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + '    0\n' * days + '  :EndData\n')
        f.write('  :Data TEMP_AVE C\n    2000-01-01 00:00:00 1.0 %d\n' % days + '    10\n' * days + '  :EndData\n')
        if S['pet'] > 0:
            f.write('  :Data PET mm/d\n    2000-01-01 00:00:00 1.0 %d\n' % days + ('    %g\n' % S['pet']) * days + '  :EndData\n')
        f.write(':EndGauge\n')
    with open(os.path.join(d, 'm.rvc'), 'w') as f:   # soil at field capacity
        f.write(''.join(':UniformInitialConditions SOIL[%d] %g\n' % (j, 1000.0 * min(s[j] for s in S['soils']) * sp['n'] * sp['sfc']) for j in range(2)))
    with open(os.path.join(d, 'm.rvg'), 'w') as f:
        f.write(':HRUGeometry hru.geojson HRU_ID\n:LandSurface dem.asc\n:HeadSaveFrequency 1\n' + rvg_body)
        f.write(':SoilZone PHYSICAL SOIL[0] SOIL[1]\n:SoilZoneSubgrid %d\n' % S['subgrid'])
        if method != 'NONE':
            f.write(':SoilZoneVadose %s\n' % method)
            if vz_classes > 1:
                f.write(':SoilZoneVadoseClasses %d\n' % vz_classes)
        if S['caprise'] != 'default':
            f.write(':SoilZoneCapillaryRise %s\n' % S['caprise'])
        if S['timing'] != 'default':
            f.write(':SoilZoneExchangeTiming %s\n' % S['timing'])
        f.write(extra_rvg)

def build(d, S, method='NONE', vz_classes=1, extra_rvg='', days=None):
    """writes case S into folder d; method = :SoilZoneVadose (NONE, RICHARDS, KINEMATIC, LAG); returns the meta dict
    (HRU polygons in projected metres, the soil-zone thickness of each HRU, ...) that the checks use"""
    os.makedirs(d, exist_ok=True)
    days = int(days or S['days'])
    polys = _hru_polys(S)
    x0, x1, y0, y1 = _domain(S); cs = S['cell']; L, W = x1 - x0, y1 - y0
    # soil profile of each HRU (two profiles: by position), aquifer profile of each HRU
    soilof = [0 if (len(S['soils']) == 1 or p.centroid.x < 0.5 * (x0 + x1)) else 1 for p in polys]
    aqof = [0 if (len(S['profiles']) == 1 or p.centroid.y < 0.5 * (y0 + y1)) else 1 for p in polys]
    Dk = [sum(S['soils'][s]) for s in soilof]
    feats = [{"type": "Feature", "properties": {"HRU_ID": k + 1}, "geometry": {"type": "Polygon", "coordinates": [_ring_ll(p)]}} for k, p in enumerate(polys)]
    json.dump({"type": "FeatureCollection", "features": feats}, open(os.path.join(d, 'hru.geojson'), 'w'))
    # DEM (margin of a cell around the domain; optionally cut inside the grid) and bedrock rasters
    keep = None
    if S.get('dem_cut'):
        xc = x0 + S['dem_cut'] * L
        keep = lambda X, Y: X < xc
    raster_over(os.path.join(d, 'dem.asc'), S['land'], x0 - cs, x1 + cs, y0 - cs, y1 + cs, S['dem_res'], S['holes'], keep)
    meta = dict(elev=[round(float(field(S['land'], p.representative_point().x, p.representative_point().y)), 4) for p in polys], polys=[[list(c) for c in p.exterior.coords] for p in polys], areas=[p.area for p in polys], Dk=Dk, soilof=soilof,
                aqof=aqof, method=method, vz_classes=vz_classes, days=days, family=S['family'])
    if S['family'] == 'ext':
        import rough_ext
        rvg_body = rough_ext.build_model(d, S, polys, Dk, method, meta)
    else:
        if S['use_bedrock']:
            # (at least a metre below the soil-zone base everywhere, unless the case allows outcrops: columns where bedrock
            # reaches the model top are inactive, which an HRU over no other cell cannot have)
            B = S['bedrock']
            if S.get('outcrop'):   # bedrock above the land around the smallest HRU: all its cells inactive
                k = int(np.argmin([p.area for p in polys])); bx0, by0, bx1, by1 = polys[k].bounds
                B = dict(B); B['terms'] = list(B['terms']) + [['bump', 0.5 * (bx0 + bx1), 0.5 * (by0 + by1), 1.2 * max(bx1 - bx0, by1 - by0) + 1.5 * cs, 400.0]]
            raster_over(os.path.join(d, 'bed.asc'), B, x0 - cs, x1 + cs, y0 - cs, y1 + cs, S['dem_res'],
                        cap=None if S.get('outcrop') else (S['land'], max(Dk) + 1.0123 + ((1.5 * S['slope'] * cs + 3.0 * S['relief'])
                                                                                         if (S.get('dem_cut') or S['holes']) else 0.0)))
            # (where the DEM ends inside a cell or has holes, the cell's land surface is the mean of its covered part only)
        rvg_body = ':GridCellSize %g\n:MinCellCoverage %g\n%s' % (cs, S['min_cover'], ':BedrockSurface bed.asc\n' if S['use_bedrock'] else '')
        if S.get('chd') is not None:
            # specified head over the cells of the lowest edge (polygon selects cells by their centres): head = the land at the
            # edge's lowest point less chd, but at least 0.2 m above every layer-1 bottom of those cells (MODFLOW refuses a
            # specified head below a cell bottom)
            G = geometry(d, S, meta, chd=False)
            a = S['land']['aspect']; ca, sa = math.cos(a), math.sin(a)
            # downslope direction (ca, sa): the edge of the domain furthest along it
            if abs(ca) >= abs(sa):
                side = 'E' if ca > 0 else 'W'
            else:
                side = 'N' if sa > 0 else 'S'
            sel = []
            for ic in G['active_cols']:
                cx, cy = G['cx'][ic], G['cy'][ic]
                if (side == 'E' and cx > x1 - cs) or (side == 'W' and cx < x0 + cs) or (side == 'N' and cy > y1 - cs) or (side == 'S' and cy < y0 + cs):
                    sel.append(ic)
            if sel:
                h = min(G['land'][ic] for ic in sel) - S['chd']
                h = max(h, max(G['botm'][0][ic] for ic in sel) + 0.2)
                ring = []
                pts = [(G['cx'][ic], G['cy'][ic]) for ic in sel]
                from shapely.geometry import MultiPoint
                hull = MultiPoint(pts).buffer(0.3 * cs, cap_style=3, join_style=2)
                if hull.geom_type != 'Polygon': hull = hull.convex_hull
                ring = [list(ll(x, y)) for (x, y) in hull.exterior.coords]
                json.dump({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "Polygon", "coordinates": [ring]}}]},
                          open(os.path.join(d, 'edge.geojson'), 'w'))
                rvg_body += ':SpecifiedHeadBoundary EDGE edge.geojson HEAD %.6f\n' % h
                meta['chd_head'] = h; meta['chd_side'] = side; meta['chd_cells'] = [int(i) for i in sel]
    raven_files(d, S, polys, soilof, aqof, Dk, method, vz_classes, extra_rvg, days, rvg_body)
    json.dump(dict(spec=S, meta=meta), open(os.path.join(d, 'case.json'), 'w'))
    return meta

# ---------------------------------------------------------------------------------------------------- independent construction
GW_MIN_LAYER_THICK, GW_PASS_THICK = 0.5, 0.01

def sample_points(x0c, x1c, y0c, y1c, n, ring=None):
    """Raven's n x n sample points of a cell's bounding box (inside its polygon ring, for non-rectangular cells)"""
    pts = [(x0c + (i + 0.5) / n * (x1c - x0c), y0c + (j + 0.5) / n * (y1c - y0c)) for i in range(n) for j in range(n)]
    if ring is not None:
        from shapely.geometry import Polygon, Point
        P = Polygon(ring); pts = [p for p in pts if P.covers(Point(p))] or [tuple(P.centroid.coords[0])]
    return pts

def geometry(d, S, meta, chd=True, grid=None):
    """an independent construction of what Raven builds for a generated case (manual, "Building the layers"): grid
    (regular, from the HRUs' extent), overlaps, active columns, land (5x5 DEM samples, Raven's bilinear rule), model top =
    land - overlap-weighted D, bedrock, layer bottoms clipped at bedrock with the 0.5 m minimum and pass-through cells,
    the DEM samples of every cell for the sub-grid closure; grid = (xorigin, yorigin, nrow, ncol) to use MODFLOW's"""
    from shapely.geometry import Polygon, box
    polys = [Polygon(p) for p in meta['polys']]
    cs = S['cell']
    xa = min(p.bounds[0] for p in polys); ya = min(p.bounds[1] for p in polys)
    xb = max(p.bounds[2] for p in polys); yb = max(p.bounds[3] for p in polys)
    if grid is None:
        gx0, gy0 = math.floor(xa / cs) * cs, math.floor(ya / cs) * cs
        ncol, nrow = max(1, int(math.ceil((xb - gx0) / cs))), max(1, int(math.ceil((yb - gy0) / cs)))
    else:
        gx0, gy0, nrow, ncol = grid
    ncpl = nrow * ncol
    cx = [gx0 + (ic % ncol + 0.5) * cs for ic in range(ncpl)]; cy = [gy0 + (nrow - 1 - ic // ncol + 0.5) * cs for ic in range(ncpl)]
    cells = [box(cx[ic] - 0.5 * cs, cy[ic] - 0.5 * cs, cx[ic] + 0.5 * cs, cy[ic] + 0.5 * cs) for ic in range(ncpl)]
    ov = [dict() for _ in polys]
    cover = np.zeros(ncpl); best = np.zeros(ncpl); prof = [-1] * ncpl; colA = np.zeros(ncpl); colD = np.zeros(ncpl)
    for k, p in enumerate(polys):
        for ic in range(ncpl):
            if not p.intersects(cells[ic]): continue
            A = p.intersection(cells[ic]).area
            if A > 1e-6:
                ov[k][ic] = A; cover[ic] += A; colA[ic] += A; colD[ic] += A * meta['Dk'][k]
                if A > best[ic]: best[ic] = A; prof[ic] = meta['aqof'][k]
    dem = Raster(os.path.join(d, 'dem.asc'))
    bed = Raster(os.path.join(d, 'bed.asc')) if (S['family'] == 'gen' and S['use_bedrock']) else None
    land = np.zeros(ncpl); top = np.zeros(ncpl); bedr = np.zeros(ncpl)
    nlay = max(len(P) for P in S['profiles']) if S['family'] == 'gen' else 1
    botm = np.zeros((nlay, ncpl)); idom = np.zeros((nlay, ncpl), int)
    samples, high = {}, {}
    active = []
    for ic in range(ncpl):
        if cover[ic] < S['min_cover'] * cs * cs: prof[ic] = -1
        if prof[ic] < 0:
            top[ic] = 0.0
            for l in range(nlay): botm[l, ic] = -(l + 1.0)
            continue
        pts = sample_points(cx[ic] - 0.5 * cs, cx[ic] + 0.5 * cs, cy[ic] - 0.5 * cs, cy[ic] + 0.5 * cs, 5)
        lo, la = ll_np([p[0] for p in pts], [p[1] for p in pts])
        v = dem.sample(lo, la); v = v[np.isfinite(v)]
        if len(v): land[ic] = float(np.mean(v)); hi5 = float(v.max())
        else:
            ew = sum(ov[k].get(ic, 0.0) * meta['elev'][k] for k in range(len(polys)))
            land[ic] = ew / cover[ic]; hi5 = land[ic]   # (the HRUs' .rvh ELEVATION, as written)
        # sub-grid samples (as SZBuildEntries: DEM at the n x n points, else the cell's land)
        n = S['subgrid']
        if n > 1:
            pts = sample_points(cx[ic] - 0.5 * cs, cx[ic] + 0.5 * cs, cy[ic] - 0.5 * cs, cy[ic] + 0.5 * cs, n)
            lo, la = ll_np([p[0] for p in pts], [p[1] for p in pts]); s = dem.sample(lo, la); s = list(s[np.isfinite(s)])
        else:
            s = []
        samples[ic] = s if s else [land[ic]]
        high[ic] = max(hi5, max(samples[ic]))
        if S['family'] != 'gen':
            continue
        P = S['profiles'][prof[ic]]
        t = land[ic] - colD[ic] / colA[ic]
        b = land[ic] - S['default_bedrock']
        if bed is not None:
            pts = sample_points(cx[ic] - 0.5 * cs, cx[ic] + 0.5 * cs, cy[ic] - 0.5 * cs, cy[ic] + 0.5 * cs, 5)
            lo, la = ll_np([p[0] for p in pts], [p[1] for p in pts]); vb = bed.sample(lo, la); vb = vb[np.isfinite(vb)]
            if len(vb): b = float(np.mean(vb))
        if b > t - GW_MIN_LAYER_THICK:
            prof[ic] = -1; top[ic] = 0.0
            for l in range(nlay): botm[l, ic] = -(l + 1.0)
            continue
        top[ic] = t; bedr[ic] = b; prev = t
        for l in range(nlay):
            if l < len(P):
                th = P[l][1]
                bt = b if th == 'TO_BEDROCK' else prev - th
                bt = max(bt, b)
                if l == 0:
                    if prev - bt < GW_MIN_LAYER_THICK: bt = prev - GW_MIN_LAYER_THICK
                    idm = 1
                elif prev - bt < GW_MIN_LAYER_THICK:
                    bt = prev - GW_PASS_THICK; idm = -1
                else:
                    idm = 1
            else:
                bt = prev - GW_PASS_THICK; idm = -1
            botm[l, ic] = bt; idom[l, ic] = idm; prev = bt
        active.append(ic)
    return dict(ncol=ncol, nrow=nrow, ncpl=ncpl, x0=gx0, y0=gy0, cx=cx, cy=cy, ov=ov, land=land, top=top, botm=botm, idomain=idom,
                bedrock=bedr, prof=prof, active_cols=active, samples=samples, high=high, nlay=nlay)
