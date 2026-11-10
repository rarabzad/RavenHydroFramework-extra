"""Projected input files (:InputCRS): the Liard example with every geometry and raster input in UTM zone 10 against the
same example in longitude/latitude.

    python3 crs_inputs.py            # all checks (needs the MODFLOW 6 library)
    python3 crs_inputs.py --nolib    # only the input checks that stop Raven before MODFLOW is loaded

The UTM copy (EPSG:32610, the coordinates converted with PROJ through pyproj):
  - HRU polygons, river lines, GHB line and CHD polygon as GeoJSON in UTM, each with a "crs" member naming EPSG:32610;
    the GHB head (1310 m) lies above the top layer's bottom (1300 m) under the line, and the CHD lake has HEAD 0 with a
    :BoundaryHead series of 1312 m, which places its cells;
  - DEM and bedrock as ESRI ASCII grids in UTM (cell size 300 m), resampled from the lon/lat grids by the same bilinear
    sampling Raven uses, so both runs see nearly the same land surface;
  - a monitoring well given by X and Y in the UTM copy and by LATITUDE and LONGITUDE in the lon/lat copy;
  - :InputCRS EPSG:32610 in the .rvg file.
Checks:
  - the same grid: active columns, active cells, river cells, GHB/CHD cells and the monitoring well's cell are identical,
    and both runs have GHB and CHD cells (not zero); HRU polygon and linked areas agree within 1e-6 (relative) and every
    HRU has the same number of cells;
  - the runs agree: Hydrographs.csv and the GWBudget.csv flows within the tolerance of the resampled DEM (reported);
  - input checks: a UTM GeoJSON without :InputCRS, a UTM raster without :InputCRS, UTM boundary polygons without a "crs"
    member, files in EPSG:32610 with :InputCRS EPSG:32609, and a well given by X and Y without :InputCRS stop Raven with a
    message naming the file or :InputCRS; with :InputCRS, a DEM raster, an HRU file and a boundary file left in
    longitude/latitude stop with "looks like longitude/latitude";
  - with RAVEN_EXE_REF: the lon/lat run is byte-identical to the reference build (solution.rvc the same state,
    testconfig.rvc_same; otherwise SKIP).
Quick mode (RAVEN_TEST_QUICK=1): 10 days; full mode: 120 days.
"""
import os, sys, re, json, shutil, subprocess, filecmp
import numpy as np
import pyproj

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import testconfig as tc   # noqa: E402

NOLIB = '--nolib' in sys.argv
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
DAYS = 10 if QUICK else 120
EPSG = 'EPSG:32610'
UCS = 300.0                                     # cell size of the UTM rasters [m]
W = os.path.join(tc.WORK, 'crs_inputs')
OW = (59.27310, -124.73060)                     # monitoring well (lat, lon)
fwd = pyproj.Transformer.from_crs('EPSG:4326', EPSG, always_xy=True)
inv = pyproj.Transformer.from_crs(EPSG, 'EPSG:4326', always_xy=True)
fails = 0


def report(name, ok, detail=''):
    global fails
    print('%-72s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def copy_liard(dest, days):
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(tc.LIARD, dest, ignore=shutil.ignore_patterns('out', '__pycache__', '*.gwcache'))
    p = os.path.join(dest, 'Liard.rvi'); t = open(p).read()
    t = re.sub(r':Duration[ \t]+\S+([ \t]+\S+)?', ':Duration %d' % days, t, count=1)
    open(p, 'w').write(t)
    return dest


def run(d, exe=None, env=None):
    out = os.path.join(d, 'out'); os.makedirs(out, exist_ok=True)
    r = subprocess.run([exe or tc.RAVEN, 'Liard', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=env or tc.ENV)
    err = open(os.path.join(out, 'Raven_errors.txt'), errors='replace').read() if os.path.exists(os.path.join(out, 'Raven_errors.txt')) else ''
    return ('Successful' in r.stdout + r.stderr), r.stdout + r.stderr + err


def edit_rvg(d, repl, add=''):
    p = os.path.join(d, 'Liard.rvg'); t = open(p).read()
    for a, b in repl:
        assert a in t, a
        t = t.replace(a, b)
    open(p, 'w').write(t + add)


# ---- conversion of the inputs to UTM ----
def geojson_utm(src, dst, crs_member=True):
    d = json.load(open(src))
    def conv(c):
        if isinstance(c[0], (int, float)):
            x, y = fwd.transform(c[0], c[1]); return [x, y]
        return [conv(e) for e in c]
    for f in d['features']:
        f['geometry']['coordinates'] = conv(f['geometry']['coordinates'])
    if crs_member:
        d['crs'] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32610"}}
    json.dump(d, open(dst, 'w'))


def read_asc(fn):
    h = {}
    with open(fn) as f:
        for _ in range(6):
            k, v = f.readline().split(); h[k.lower()] = float(v)
        a = np.loadtxt(f)
    return h, a


def sample_ll(h, a, lon, lat):
    """Raven's bilinear sampling of a lon/lat raster (CGWRaster::Sample), vectorised; NaN outside"""
    nc, nr, cs, x0, y0 = int(h['ncols']), int(h['nrows']), h['cellsize'], h['xllcorner'], h['yllcorner']
    nod = h.get('nodata_value', -9999.0)
    fc = (lon - x0) / cs - 0.5; fr = (y0 + nr * cs - lat) / cs - 0.5
    out = (fc < -1) | (fr < -1) | (fc > nc) | (fr > nr)
    fc = np.clip(fc, 0, nc - 1); fr = np.clip(fr, 0, nr - 1)
    c0 = np.floor(fc).astype(int); r0 = np.floor(fr).astype(int)
    c1 = np.minimum(c0 + 1, nc - 1); r1 = np.minimum(r0 + 1, nr - 1)
    wc = fc - c0; wr = fr - r0
    s = np.zeros_like(lon); ws = np.zeros_like(lon)
    for rr, cc, ww in ((r0, c0, (1 - wr) * (1 - wc)), (r0, c1, (1 - wr) * wc), (r1, c0, wr * (1 - wc)), (r1, c1, wr * wc)):
        v = a[rr, cc]; ok = np.abs(v - nod) > 1e-6
        s += np.where(ok, ww * v, 0.0); ws += np.where(ok, ww, 0.0)
    val = np.where(ws > 1e-9, s / np.maximum(ws, 1e-300), np.nan)
    return np.where(out, np.nan, val)


def raster_utm(src, dst):
    h, a = read_asc(src)
    nc, nr, cs, x0, y0 = int(h['ncols']), int(h['nrows']), h['cellsize'], h['xllcorner'], h['yllcorner']
    lon = np.r_[np.linspace(x0, x0 + nc * cs, 50), np.full(50, x0 + nc * cs), np.linspace(x0, x0 + nc * cs, 50), np.full(50, x0)]
    lat = np.r_[np.full(50, y0), np.linspace(y0, y0 + nr * cs, 50), np.full(50, y0 + nr * cs), np.linspace(y0, y0 + nr * cs, 50)]
    X, Y = fwd.transform(lon, lat)
    ux0, uy0 = np.floor(X.min() / UCS) * UCS, np.floor(Y.min() / UCS) * UCS
    unc, unr = int(np.ceil((X.max() - ux0) / UCS)), int(np.ceil((Y.max() - uy0) / UCS))
    xc = ux0 + (np.arange(unc) + 0.5) * UCS; yc = uy0 + (unr - 1 - np.arange(unr) + 0.5) * UCS
    XX, YY = np.meshgrid(xc, yc)
    LO, LA = inv.transform(XX, YY)
    V = sample_ll(h, a, LO, LA)
    V = np.where(np.isnan(V), -9999.0, V)
    with open(dst, 'w') as f:
        f.write('ncols %d\nnrows %d\nxllcorner %.3f\nyllcorner %.3f\ncellsize %.3f\nNODATA_value -9999\n' % (unc, unr, ux0, uy0, UCS))
        np.savetxt(f, V, fmt='%.4f')


GEO = [('Liard_HRUs_standin.geojson', 'utm_hrus.geojson'), ('Liard_rivers.geojson', 'utm_rivers.geojson'),
       ('boundary_line.geojson', 'utm_boundary_line.geojson'), ('lake.geojson', 'utm_lake.geojson')]
RAS = [('Liard_dem_standin.asc', 'utm_dem.asc'), ('Liard_bedrock_standin.asc', 'utm_bedrock.asc')]
BOUNDS = ('# :GeneralHeadBoundary   GHB1 boundary_line.geojson HEAD 1310.0 CONDUCTANCE 5000.0 LAYERS TOP\n'
          '# :SpecifiedHeadBoundary LAKE1 lake.geojson HEAD 1312.0 LAYERS TOP\n')
# heads above the cells under the boundaries (top layer: bottom 1300 m, top 1315 m there): GHB1 by the example's HEAD,
# LAKE1 by a :BoundaryHead series (HEAD 0 alone would leave it without cells)
HEADS = [('HEAD 1312.0', 'HEAD 0.0')]


def add_lake_series(d, days):
    open(os.path.join(d, 'Liard.rvt'), 'a').write('\n:BoundaryHead LAKE1 m\n  1985-10-01 00:00:00 1.0 %d\n' % (days + 2) + '  1312.0\n' * (days + 2) + ':EndBoundaryHead\n')


def ow_block(xy):
    if xy:
        x, y = fwd.transform(OW[1], OW[0])
        return ':ObservationWells\n  :Attributes, NAME, X, Y, SCREEN_ELEV\n  101, OW_NEAR, %.4f, %.4f, 1192.7\n:EndObservationWells\n' % (x, y)
    return ':ObservationWells\n  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_ELEV\n  101, OW_NEAR, %.5f, %.5f, 1192.7\n:EndObservationWells\n' % OW


def make_lonlat(d, days):
    copy_liard(d, days)
    edit_rvg(d, [(BOUNDS, BOUNDS.replace('# :', ':'))] + HEADS, ow_block(False)); add_lake_series(d, days)


def make_utm(d, days, crs_line=':InputCRS EPSG:32610\n', well_xy=True):
    copy_liard(d, days)
    for s, t in GEO:
        geojson_utm(os.path.join(d, s), os.path.join(d, t))
    for s, t in RAS:
        raster_utm(os.path.join(d, s), os.path.join(d, t))
    edit_rvg(d, [(BOUNDS, BOUNDS.replace('# :', ':'))] + HEADS + GEO + RAS, crs_line + ow_block(well_xy)); add_lake_series(d, days)


# ---- comparisons ----
def summary(d):
    t = open(os.path.join(d, 'out', 'GWModelSummary.txt')).read()
    keys = {}
    for k in ('active columns', 'active cells', 'river cells', 'GHB cells / CHD cells', 'grid  '):
        m = re.search(r'^\s*' + re.escape(k.strip()) + r'\s*:\s*(.*)$', t, re.M)
        keys[k.strip()] = m.group(1).strip() if m else None
    m = re.search(r'^\s*OW_NEAR: (.*)$', t, re.M); keys['OW_NEAR'] = m.group(1) if m else None
    hru = {}
    sec = t[t.index('HRU_ID,profile'):].strip().split('\n')[1:]
    for l in sec:
        v = l.split(',')
        if len(v) < 7:
            break
        hru[v[0]] = (float(v[3]), float(v[4]), int(v[6]))
    return keys, hru


def linkage(d, ids):
    """overlap areas per (HRU, cell) from the linkage cache (full precision), and the polygon areas"""
    L = open(os.path.join(d, 'out', 'mf6', 'linkage.cache')).read().split('\n')
    i = next(k for k in range(len(L) - 1) if L[k].strip() == str(len(ids)) and L[k + 1].split()[:1] == [ids[0]] and len(L[k + 1].split()) == 3)
    i += 1; ov, pa = {}, {}
    while i < len(L) and len(L[i].split()) == 3:
        h, a, n = L[i].split(); pa[h] = float(a)
        for j in range(int(n)):
            c, v = L[i + 1 + j].split(); ov[(h, int(c))] = float(v)
        i += 1 + int(n)
    return pa, ov


def csv_rel(a, b, skip=('date', 'time', 'hour')):
    import pandas as pd
    A = pd.read_csv(a); B = pd.read_csv(b)
    worst, where = 0.0, ''
    cols = [c for c in A.columns if not any(s in c.lower() for s in skip) and c in B.columns]
    big = max([np.nanmax(np.abs(pd.to_numeric(A[c], errors='coerce').values.astype(float)), initial=0.0) for c in cols] + [0.0])
    for c in A.columns:
        if any(s in c.lower() for s in skip) or c not in B.columns:
            continue
        x, y = pd.to_numeric(A[c], errors='coerce').values.astype(float), pd.to_numeric(B[c], errors='coerce').values.astype(float)
        if np.all(np.isnan(x)):
            continue
        scale = max(np.nanmax(np.abs(x)), 1e-6 * big, 1e-9)   # (a column of round-off is judged against the file's largest flow)
        e = np.nanmax(np.abs(x - y)) / scale if len(x) else 0.0
        if e > worst:
            worst, where = e, c
    return worst, where


def stops(d, want, label):
    ok, out = run(d, env=ENV_RUN)
    hit = want in out
    report(label, (not ok) and hit, ('stopped: ' + (re.findall(r'.*' + re.escape(want) + r'.*', out) or [''])[0].strip()[:150]) if hit else 'did not stop with "%s"' % want)


ENV_RUN = dict(tc.ENV)
if NOLIB:
    ENV_RUN.pop('RAVEN_MF6_LIB', None)
else:
    tc.need_mf6()
os.makedirs(W, exist_ok=True)

# ---- input checks (Raven stops while reading the geometry, before MODFLOW is loaded) ----
d = os.path.join(W, 'no_inputcrs'); make_utm(d, 2, crs_line='', well_xy=False)
stops(d, ':InputCRS EPSG:32610', 'UTM GeoJSON ("crs" EPSG:32610) without :InputCRS stops')
d = os.path.join(W, 'raster_only'); make_lonlat(d, 2)
raster_utm(os.path.join(d, 'Liard_dem_standin.asc'), os.path.join(d, 'utm_dem.asc'))
edit_rvg(d, [('Liard_dem_standin.asc', 'utm_dem.asc')])
stops(d, 'needs :InputCRS', 'UTM raster without :InputCRS stops')
d = os.path.join(W, 'bare_boundary'); make_lonlat(d, 2)     # a boundary polygon file in UTM without a "crs" member
geojson_utm(os.path.join(d, 'lake.geojson'), os.path.join(d, 'utm_lake_bare.geojson'), crs_member=False)
edit_rvg(d, [(':SpecifiedHeadBoundary LAKE1 lake.geojson', ':SpecifiedHeadBoundary LAKE1 utm_lake_bare.geojson')])
stops(d, 'utm_lake_bare.geojson has coordinates outside the longitude/latitude range', 'UTM boundary polygons without a "crs" member or :InputCRS stop')
d = os.path.join(W, 'mismatch'); make_utm(d, 2, crs_line=':InputCRS EPSG:32609\n')
stops(d, 'must use the projection of :InputCRS', 'files in EPSG:32610 with :InputCRS EPSG:32609 stop')
d = os.path.join(W, 'well_xy'); make_lonlat(d, 2)
edit_rvg(d, [(ow_block(False), ow_block(True))])
stops(d, 'is given by X and Y', 'monitoring well given by X and Y without :InputCRS stops')
# with :InputCRS, inputs left in longitude/latitude (no "crs" member) are recognised against the HRUs' place
d = os.path.join(W, 'lonlat_dem'); make_utm(d, 2)
edit_rvg(d, [('utm_dem.asc', 'Liard_dem_standin.asc')])
stops(d, 'raster Liard_dem_standin.asc looks like longitude/latitude', 'lon/lat DEM raster with :InputCRS stops')
d = os.path.join(W, 'lonlat_bedrock'); make_utm(d, 2)
edit_rvg(d, [('utm_bedrock.asc', 'Liard_bedrock_standin.asc')])
stops(d, 'Liard_bedrock_standin.asc looks like longitude/latitude', 'lon/lat bedrock raster with :InputCRS stops')
d = os.path.join(W, 'lonlat_hrus'); make_utm(d, 2)
edit_rvg(d, [('utm_hrus.geojson', 'Liard_HRUs_standin.geojson')])
stops(d, 'Liard_HRUs_standin.geojson looks like longitude/latitude', 'lon/lat HRU polygons with :InputCRS stop (not "no overlap")')
d = os.path.join(W, 'lonlat_boundary'); make_utm(d, 2)
edit_rvg(d, [('utm_boundary_line.geojson', 'boundary_line.geojson')])
stops(d, 'boundary_line.geojson looks like longitude/latitude', 'lon/lat boundary line with :InputCRS stops')

def dis_arrays(d):
    """TOP and BOTM of the generated DIS file"""
    t = open(os.path.join(d, 'out', 'mf6', 'gwf.dis')).read(); R = {}
    for name in ('TOP', 'BOTM'):
        i = re.search(r'^\s*' + name + r'\b.*$', t, re.M).end(); v = []
        for l in t[i:].split('\n'):
            if re.match(r'\s*(INTERNAL|LAYERED)', l):
                continue
            if re.match(r'\s*[A-Z]', l):
                break
            v += [float(x) for x in l.split()]
        R[name] = np.array(v)
    return R


NORASTER = [(':LandSurface        Liard_dem_standin.asc', '# (no DEM)'), (':BedrockSurface     Liard_bedrock_standin.asc', '# (no bedrock)')]
if not NOLIB:
    for case in ('geometry', 'rasters'):
        dl = os.path.join(W, case + '_lonlat'); make_lonlat(dl, DAYS)
        du = os.path.join(W, case + '_utm'); make_utm(du, DAYS)
        if case == 'geometry':     # HRU polygons, rivers, boundaries and the well only: land surface from HRU elevations
            edit_rvg(dl, NORASTER); edit_rvg(du, [(a.replace('Liard_dem_standin', 'utm_dem').replace('Liard_bedrock_standin', 'utm_bedrock'), b) for a, b in NORASTER])
        okl, outl = run(dl); oku, outu = run(du)
        what = 'without rasters' if case == 'geometry' else 'with DEM and bedrock rasters'
        report('%s: lon/lat run (%d days)' % (what, DAYS), okl, '' if okl else outl[-300:])
        report('%s: UTM run, :InputCRS EPSG:32610 (%d days)' % (what, DAYS), oku, '' if oku else outu[-300:])
        if not (okl and oku):
            continue
        kl, hl = summary(dl); ku, hu = summary(du)
        same = {k: (kl[k], ku[k]) for k in kl if kl[k] != ku[k]}
        report('%s: same grid (active columns and cells, river/GHB/CHD cells, monitoring well)' % what, not same and kl['OW_NEAR'] is not None,
               '; '.join('%s: %s / %s' % (k, a, b) for k, (a, b) in same.items()) or '%s; OW_NEAR %s' % (kl['active columns'], kl['OW_NEAR']))
        nb = [int(x) for x in re.findall(r'\d+', ku['GHB cells / CHD cells'] or '')]
        report('%s: the boundaries have cells (GHB by its HEAD, CHD placed by its :BoundaryHead series)' % what, len(nb) == 2 and min(nb) > 0,
               'GHB / CHD cells: %s (lon/lat run: %s)' % (ku['GHB cells / CHD cells'], kl['GHB cells / CHD cells']))
        if case == 'geometry':
            ids = list(hl.keys()); pl, ol = linkage(dl, ids); pu, ou = linkage(du, ids)
            ea = max(abs(pl[k] - pu[k]) / pl[k] for k in pl)
            cell = max(max(ol.values()), 1.0)       # (overlaps relative to a full cell's area)
            eo = max(abs(ol[k] - ou.get(k, 0.0)) for k in set(ol) | set(ou)) / cell
            nc = sum(1 for k in hl if hl[k][2] != hu[k][2])
            report('HRU polygon areas and HRU-cell overlaps within 1e-6, same cell counts', ea < 1e-6 and eo < 1e-6 and nc == 0 and set(ol) == set(ou),
                   'polygons %.2e, overlaps %.2e (of a cell), %d HRUs with other cell counts' % (ea, eo, nc))
            u = open(os.path.join(du, 'out', 'GWModelSummary.txt')).read()
            report('summary names the input coordinate system', 'input coordinates     : Transverse Mercator' in u)
            eh, ch = csv_rel(os.path.join(dl, 'out', 'Hydrographs.csv'), os.path.join(du, 'out', 'Hydrographs.csv'))
            report('Hydrographs.csv agree within 1e-6 (relative to the column maximum, at least 1e-6 of the largest)', eh < 1e-6, '%.2e (%s)' % (eh, ch))
            eb, cb = csv_rel(os.path.join(dl, 'out', 'GWBudget.csv'), os.path.join(du, 'out', 'GWBudget.csv'), skip=('date', 'time', 'iterations', 'converged', '%', 'balance error'))
            report('GWBudget.csv flows agree within 1e-5 (relative to the column maximum, at least 1e-6 of the largest)', eb < 1e-5, '%.2e (%s)' % (eb, cb))
            eg, cg = csv_rel(os.path.join(dl, 'out', 'GWHRUState.csv'), os.path.join(du, 'out', 'GWHRUState.csv'))
            report('GWHRUState.csv agrees within 1e-6 (relative to the column maximum, at least 1e-6 of the largest)', eg < 1e-6, '%.2e (%s)' % (eg, cg))
        else:                      # the UTM rasters are resampled from the lon/lat ones (300 m cells): close, not equal
            al, au = dis_arrays(dl), dis_arrays(du)
            dt, db = np.abs(al['TOP'] - au['TOP']), np.abs(al['BOTM'] - au['BOTM'])
            report('model top and layer bottoms from the UTM rasters: mean difference below 0.05 m', len(dt) == len(au['TOP']) and dt.mean() < 0.05 and db.mean() < 0.05,
                   'top: mean %.3f m, 99%% %.3f m, max %.2f m; bottoms: mean %.3f m' % (dt.mean(), np.percentile(dt, 99), dt.max(), db.mean()))
            eh, ch = csv_rel(os.path.join(dl, 'out', 'Hydrographs.csv'), os.path.join(du, 'out', 'Hydrographs.csv'))
            report('Hydrographs.csv agree within 1e-2 (resampled rasters)', eh < 1e-2, '%.2e (%s)' % (eh, ch))
            if tc.REF:
                dr = os.path.join(W, 'rasters_lonlat_ref'); make_lonlat(dr, DAYS); run(dr, exe=tc.REF)
                diffs = []
                for f in sorted(os.listdir(os.path.join(dl, 'out'))):
                    pa, pb = os.path.join(dl, 'out', f), os.path.join(dr, 'out', f)
                    if os.path.isdir(pa) or f in ('GWModelSummary.txt', 'Raven_errors.txt'):
                        continue
                    if not tc.same_output(pa, pb):
                        diffs.append(f)
                report('lon/lat run byte-identical to RAVEN_EXE_REF (outputs except the two text logs)', not diffs, ', '.join(diffs))
            else:
                tc.skip('lon/lat run against the reference build')
print('crs inputs: ALL PASSED' if fails == 0 else 'crs inputs: %d FAILED' % fails)
sys.exit(1 if fails else 0)
