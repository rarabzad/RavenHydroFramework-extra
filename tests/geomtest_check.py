"""Checks the geometry library (GWGeometry) against independent implementations.

Build and run from this folder:
    g++ -std=c++11 -O2 -I.. geomtest.cpp ../GWGeometry.cpp -o geomtest
    python3 geomtest_check.py            (needs numpy, shapely, pyproj)

geomtest writes clipping areas, projected points and raster samples; this script writes the test raster first,
runs geomtest, then compares:
  - clipping: area of 400 random (often concave) polygons inside random squares, against shapely;
  - projection: Lambert azimuthal equal-area (sphere R=6371007.181 m) against PROJ, and the inverse round trip;
  - raster: bilinear sampling of an ESRI ASCII grid holding a plane, which bilinear sampling must reproduce exactly;
  - :InputCRS: a raster in UTM zone 10 (EPSG:32610) holding a plane in metres, sampled at lon/lat points, against the
    plane at the PROJ position; GeoJSON polygons and lines in UTM read back in lon/lat against the originals (outer
    rings counterclockwise); the file's "crs" member: a projected file without :InputCRS, a different projection, a
    lon/lat file with :InputCRS, projected coordinates without any "crs" member and a projected raster without
    :InputCRS are refused.
"""
import os, subprocess, sys, json
import numpy as np
from shapely.geometry import Polygon, box
import pyproj

here = os.path.dirname(os.path.abspath(__file__))
os.chdir(here)

# test raster: a plane v = 3*lon + 2*lat + 1 on a 0.5-degree grid (lon -3..3, lat 9..14); cell centres are sampled
ncols, nrows, x0, y0, cs = 12, 10, -3.0, 9.0, 0.5
with open('test.asc', 'w') as f:
    f.write(f'ncols {ncols}\nnrows {nrows}\nxllcorner {x0}\nyllcorner {y0}\ncellsize {cs}\nNODATA_value -9999\n')
    for r in range(nrows):
        lat = y0 + (nrows - 1 - r + 0.5) * cs
        f.write(' '.join('%.6f' % (3 * (x0 + (c + 0.5) * cs) + 2 * lat + 1) for c in range(ncols)) + '\n')

# :InputCRS inputs: UTM zone 10 raster holding the plane v = 0.001 x + 0.002 y - 10000 (x, y in m)
utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32610', always_xy=True)
UX0, UY0, UCS, UN = 450000.0, 5440000.0, 1000.0, 100
def plane(x, y):
    return 0.001 * x + 0.002 * y - 10000.0
with open('test_utm.asc', 'w') as f:
    f.write(f'ncols {UN}\nnrows {UN}\nxllcorner {UX0}\nyllcorner {UY0}\ncellsize {UCS}\nNODATA_value -9999\n')
    for r in range(UN):
        yc = UY0 + (UN - 1 - r + 0.5) * UCS
        f.write(' '.join('%.6f' % plane(UX0 + (c + 0.5) * UCS, yc) for c in range(UN)) + '\n')
rng = np.random.default_rng(7)
polys_ll = []
for i in range(20):    # quadrilaterals, clockwise in the file (the reader orients outer rings counterclockwise)
    cx, cy = -123.4 + 0.8 * rng.random(), 49.25 + 0.5 * rng.random()
    ring = [(cx - 0.02, cy - 0.01), (cx - 0.015, cy + 0.012), (cx + 0.02, cy + 0.01), (cx + 0.018, cy - 0.011)]
    polys_ll.append(ring)
def fc(geoms, crs=None, kind='Polygon'):
    d = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": i + 1}, "geometry": {"type": kind, "coordinates": g}} for i, g in enumerate(geoms)]}
    if crs: d["crs"] = {"type": "name", "properties": {"name": crs}}
    return d
def to_utm(ring):
    return [list(utm.transform(x, y)) for x, y in ring]
pu = [[to_utm(r + [r[0]])] for r in polys_ll]
json.dump(fc(pu, 'urn:ogc:def:crs:EPSG::32610'), open('test_utm_poly.geojson', 'w'))
json.dump(fc(pu), open('test_utm_bare.geojson', 'w'))
json.dump(fc([[[list(p) for p in r + [r[0]]]] for r in polys_ll], 'urn:ogc:def:crs:OGC:1.3:CRS84'), open('test_ll_crs84.geojson', 'w'))
lines_ll = [[(-123.3, 49.3), (-123.1, 49.35), (-122.8, 49.6)], [(-122.9, 49.7), (-122.7, 49.75)]]
json.dump(fc([to_utm(l) for l in lines_ll], 'EPSG:32610', 'LineString'), open('test_utm_line.geojson', 'w'))

exe = os.path.join(here, 'geomtest')
if not os.path.exists(exe):
    sys.exit('build geomtest first (see the docstring)')
out = subprocess.run([exe], capture_output=True, text=True)
if 'done' not in out.stdout:
    sys.exit('geomtest failed: ' + out.stdout + out.stderr)

fails = 0
def report(name, ok, value):
    global fails
    print('%-60s %s  (%.3g)' % (name, 'ok' if ok else 'FAIL', value))
    fails += 0 if ok else 1

# clipping against shapely
worst = 0.0
for line in open('clip.txt'):
    v = line.split(); n = int(v[0]); xa, ya, xb, yb, A = map(float, v[1:6])
    pts = np.array(v[6:6 + 2 * n], float).reshape(-1, 2)
    P = Polygon(pts)
    if not P.is_valid:
        P = P.buffer(0)
    ref = P.intersection(box(xa, ya, xb, yb)).area
    worst = max(worst, abs(A - ref) / max(ref, 1e-9) if ref > 1e-9 else abs(A))
report('clipping: 400 polygons against shapely (worst relative error)', worst < 1e-9, worst)

# projection against PROJ
d = np.loadtxt('proj.txt')
laea = pyproj.Proj(proj='laea', lat_0=59.0, lon_0=-125.3, R=6371007.181)
x, y = laea(d[:, 0], d[:, 1])
e = np.max(np.hypot(x - d[:, 2], y - d[:, 3]))
report('projection: forward against PROJ (worst position error, m)', e < 1e-3, e)
rt = np.max(np.abs(np.r_[d[:, 4] - d[:, 0], d[:, 5] - d[:, 1]]))
report('projection: inverse round trip (worst error, degrees)', rt < 1e-9, rt)

# raster: a plane is reproduced exactly by bilinear sampling (points inside the outer cell centres)
r = np.loadtxt('raster.txt')
inside = (r[:, 0] >= x0 + cs / 2) & (r[:, 0] <= x0 + (ncols - 0.5) * cs) & (r[:, 1] >= y0 + cs / 2) & (r[:, 1] <= y0 + (nrows - 0.5) * cs)
ok = r[:, 2] == 1
e = np.max(np.abs(r[inside & ok, 3] - (3 * r[inside & ok, 0] + 2 * r[inside & ok, 1] + 1))) if np.any(inside & ok) else 1e9
report('raster: bilinear sampling of a plane (worst error)', e < 1e-6 and np.all(ok[inside]), e)

# :InputCRS: projected raster against the plane at PROJ's position
r = np.loadtxt('raster_utm.txt')
x, y = utm.transform(r[:, 0], r[:, 1])
e = np.max(np.abs(r[:, 3] - plane(x, y)))
report(':InputCRS raster: bilinear sampling of a UTM plane at lon/lat points (worst error)', e < 1e-5 and np.all(r[:, 2] == 1), e)
# GeoJSON in UTM read back in lon/lat
e, ccw = 0.0, True
for line in open('poly_utm.txt'):
    v = line.split(); fid, A = int(v[0]), float(v[2]); pts = np.array(v[3:], float).reshape(-1, 2)
    ref = np.array(polys_ll[fid - 1])[::-1]       # (reversed to counterclockwise by the reader)
    k = int(np.argmin(np.hypot(ref[:, 0] - pts[0, 0], ref[:, 1] - pts[0, 1]))); ref = np.roll(ref, -k, axis=0)
    e = max(e, np.max(np.abs(pts - ref))) if len(pts) == len(ref) else 1e9
    ccw = ccw and A > 0
report(':InputCRS GeoJSON polygons: UTM -> lon/lat against the originals (worst, degrees)', e < 1e-9 and ccw, e)
d = np.loadtxt('line_utm.txt'); ref = np.array([p for l in lines_ll for p in l])
e = np.max(np.abs(d[:, 1:] - ref)) if len(d) == len(ref) else 1e9
report(':InputCRS GeoJSON lines: UTM -> lon/lat against the originals (worst, degrees)', e < 1e-9, e)
st = {l.split()[0]: (int(l.split()[1]), ' '.join(l.split()[2:])) for l in open('crs_status.txt')}
expect = {'raster_nocrs': (0, ':InputCRS'), 'poly_crs': (1, ''), 'line_crs': (1, ''), 'poly_nocrs': (0, ':InputCRS EPSG:32610'),
          'line_nocrs': (0, ':InputCRS EPSG:32610'), 'poly_mismatch': (0, 'must use the projection'), 'bare_nocrs': (0, 'outside the longitude/latitude'),
          'bare_crs': (1, ''), 'll_nocrs': (1, ''), 'll_crs': (0, 'longitude/latitude'), 'same_tmerc': (1, ''), 'same_other': (0, '')}
for k, (ok, msg) in expect.items():
    got = st.get(k, (-1, 'missing'))
    report(':InputCRS file check %-14s %s' % (k, 'accepted' if ok else 'refused (%s)' % msg), got[0] == ok and msg in got[1], got[0])

for f in ('clip.txt', 'proj.txt', 'raster.txt', 'test.asc', 'test_utm.asc', 'raster_utm.txt', 'crs_status.txt', 'poly_utm.txt', 'line_utm.txt',
          'test_utm_poly.geojson', 'test_utm_bare.geojson', 'test_ll_crs84.geojson', 'test_utm_line.geojson'):
    if os.path.exists(f):   # another run in the same checkout may have removed it already
        os.remove(f)
print('ALL PASSED' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
