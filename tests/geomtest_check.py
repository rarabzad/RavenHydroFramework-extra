"""Checks the geometry library (GWGeometry) against independent implementations.

Build and run from this folder:
    g++ -std=c++11 -O2 -I.. geomtest.cpp ../GWGeometry.cpp ../GWGeoTIFF.cpp -o geomtest
    python3 geomtest_check.py            (needs numpy, shapely, pyproj)

geomtest writes clipping areas, projected points and raster samples; this script writes the test raster first,
runs geomtest, then compares:
  - clipping: area of 400 random (often concave) polygons inside random squares, against shapely;
  - projection: Lambert azimuthal equal-area (sphere R=6371007.181 m) against PROJ, and the inverse round trip;
  - raster: bilinear sampling of an ESRI ASCII grid holding a plane, which bilinear sampling must reproduce exactly; a
    point 0.4 cell beyond the grid's edge has a value and one 0.6 cell beyond has none (the margin is half a cell);
  - :InputCRS: a raster in UTM zone 10 (EPSG:32610) holding a plane in metres, sampled at lon/lat points, against the
    plane at the PROJ position; GeoJSON polygons and lines in UTM read back in lon/lat against the originals (outer
    rings counterclockwise); the file's "crs" member: a projected file without :InputCRS, a different projection, a
    lon/lat file with :InputCRS, projected coordinates without any "crs" member and a projected raster without
    :InputCRS are refused; "crs" members naming geographic codes (EPSG:4326, 4269, 4617, 6318, 4979, 4267, a
    versioned URN urn:ogc:def:crs:EPSG:6.6:4326, an http://www.opengis.net/def/crs/EPSG/0/4269 URL, OGC CRS83) are read
    as longitude/latitude (and refused with :InputCRS), a versioned URN of a projection is read by its code, and
    projections that are not built in (EPSG:3157, and EPSG:4647, a projected code among the geographic ones of the
    4000s) ask for their parameters (not for :InputCRS), which are then accepted; geographic codes that are not degrees
    from Greenwich (EPSG:4801 Bern, 4035 in degrees-minutes-seconds) are refused, and so is a projection in US survey
    feet (EPSG:2227); a file that starts with a UTF-8 byte-order mark is read;
  - :InputCRS parameters are read strictly: a letter in a number (TMERC lon0 -ll7, k0 O.9996), a unit (FE 500km), a
    surplus value (TMERC ... WGS84 junk, EPSG:32610 junk), too few values and a code with letters (EPSG:32610x) are
    refused, each naming the parameter or the value; conic parameters that define no cone (ALBERS and LCC with standard
    parallels symmetric about the equator, 30 -30 or 0 0, and LCC with a parallel at a pole) are refused, naming the
    standard parallels;
  - GeoJSON coordinates: a coordinate that is a string, null, true or a number too large for a double is refused,
    naming the file, the feature (with its ID), the ring and the vertex, and so is a NaN or Infinity coordinate (not a
    finite number); hexadecimal (0x10) and a leading zero (-0122.9) are not JSON numbers (invalid JSON, naming the line
    and column of the token, and why); -1.229E2 is read; a feature without "properties" is refused when an ID field is
    needed and read when none is (polygons and lines);
  - GeoJSON IDs and nesting: an ID that is null, true, "7abc", 2.6, "7.5" or "" is refused (polygons and lines), naming
    the file, the feature and the value; "7", 7.0, " 7 " and "7.0" are read; a feature of another geometry type is skipped
    before its ID is read (a Point with a null ID in a polygon file; the null ID of its line stops the line reader); a Polygon nested one level too shallow, a vertex [1] (polygon
    and line) and a LineString whose coordinates are a number are refused, naming the vertex or member; attributes NaN,
    Infinity and -Infinity (as geopandas and Python's json write them) are read; a field name written with JSON's
    backslash-u escapes (Hoehe_ID with the o-umlaut escaped, a surrogate pair) matches the UTF-8 name; text after the root object is refused; a truncated file
    is refused without the hint about NaN and hexadecimal numbers;
  - conic projections against PROJ (forward within 1 mm, inverse round trip within 1e-9 degrees, modulo 360 degrees in
    longitude): LCC and ALBERS with their origin at either pole, also at the pole opposite the cone (LCC 50 60 -90,
    LCC -50 -60 90: PROJ takes the pole as the cone's apex), ordinary origins, points more than 180 degrees from the
    central meridian (Alaska Albers, EPSG:3338, at Attu, lon 172.9; an LCC centred on -96 at lon 151.2), which PROJ
    takes within +-180 degrees of it, and a point exactly 180 degrees from it (lon 26 with lon0 -154: the side PROJ keeps),
    also written beyond +-180 degrees (lon -334; lon -540 with lon0 0), and the apex of a southern cone (LCC with
    parallels -30 and -10 at lat -90);
  - GeoJSON IDs beyond 9e15 written as numbers are refused, with the advice to write them as strings for a whole number
    written in digits (the int64 9007199254740993) and to write them as strings of at most 18 digits otherwise (1e+16);
    a missing ID field whose feature has an "id" member names GDAL's ID_FIELD option; an ID none of whose polygons has an
    area (an outline of fewer than 3 distinct vertices, alone or with a hole; an outline of 3 vertices on one line; a
    square traced out and back; a figure eight of equal lobes; an empty Polygon) is left out and reported with the feature and why ("has no area",
    "has no polygon"), the other IDs are read; a MultiPolygon with such a part (fewer than 3 distinct vertices, or on
    one line) beside a proper one is read.
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
# "crs" members: geographic codes (the EPSG registry's geographic 2D and 3D codes: 4326, 4269, 4617, NAD83(2011) 6318, ...),
# versioned URNs and URLs, OGC CRS84/CRS83; projections that are not built in (EPSG:3157, NAD83(CSRS) / UTM zone 10N, and
# EPSG:4647, ETRS89 / UTM zone 32N (zE-N), a projected code between geographic ones): the message asks for the projection's
# parameters, and they work
pl = [[[list(p) for p in r + [r[0]]]] for r in polys_ll]
CRS_FILES = {'ll_6318': (pl, 'urn:ogc:def:crs:EPSG::6318'), 'll_4979': (pl, 'urn:ogc:def:crs:EPSG::4979'), 'll_4267': (pl, 'EPSG:4267'),
             'll_ver': (pl, 'urn:ogc:def:crs:EPSG:6.6:4326'), 'll_url': (pl, 'http://www.opengis.net/def/crs/EPSG/0/4269'),
             'll_crs83': (pl, 'urn:ogc:def:crs:OGC:1.3:CRS83'), 'utm_ver': (pu, 'urn:ogc:def:crs:EPSG:9.8.15:32610'),
             'utm_3157': (pu, 'urn:ogc:def:crs:EPSG::3157'), 'll_4326': (pl, 'EPSG:4326'), 'll_4269': (pl, 'urn:ogc:def:crs:EPSG::4269'),
             'll_4617': (pl, 'urn:ogc:def:crs:EPSG::4617'), 'xy_4647': (pu, 'urn:ogc:def:crs:EPSG::4647'),
             'll_4801': (pl, 'urn:ogc:def:crs:EPSG::4801'), 'll_4035': (pl, 'EPSG:4035'), 'xy_2227': (pu, 'urn:ogc:def:crs:EPSG::2227'),
             'll_bom': (pl, 'EPSG:4326')}
for k, (g, c) in CRS_FILES.items():
    json.dump(fc(g, c), open('test_crs_%s.geojson' % k, 'w'))
b = open('test_crs_ll_bom.geojson', 'rb').read(); open('test_crs_ll_bom.geojson', 'wb').write(b'\xef\xbb\xbf' + b)   # (a UTF-8 byte-order mark)
TM10 = 'TMERC 0 -123 0.9996 500000 0 GRS80'
CRS_CASES = [  # (name, file, :InputCRS or NONE, accepted, part of the message, text the message must not hold)
    ('crs_6318', 'll_6318', 'NONE', 1, '', ''), ('crs_4979', 'll_4979', 'NONE', 1, '', ''), ('crs_4267', 'll_4267', 'NONE', 1, '', ''),
    ('crs_ver4326', 'll_ver', 'NONE', 1, '', ''), ('crs_url4269', 'll_url', 'NONE', 1, '', ''), ('crs_crs83', 'll_crs83', 'NONE', 1, '', ''),
    ('crs_6318_inputcrs', 'll_6318', 'EPSG:32610', 0, 'is in longitude/latitude', ':InputCRS EPSG:6318'),
    ('crs_ver4326_inputcrs', 'll_ver', 'EPSG:32610', 0, 'is in longitude/latitude', 'EPSG:6 '),
    ('crs_utm_ver', 'utm_ver', 'EPSG:32610', 1, '', ''), ('crs_utm_ver_none', 'utm_ver', 'NONE', 0, ':InputCRS EPSG:32610', ''),
    ('crs_3157_none', 'utm_3157', 'NONE', 0, 'TMERC, ALBERS or LCC', ':InputCRS EPSG:3157'),
    ('crs_3157_tmerc', 'utm_3157', TM10, 1, '', ''),
    ('crs_4326', 'll_4326', 'NONE', 1, '', ''), ('crs_4269', 'll_4269', 'NONE', 1, '', ''), ('crs_4617', 'll_4617', 'NONE', 1, '', ''),
    ('crs_4617_inputcrs', 'll_4617', 'EPSG:32610', 0, 'is in longitude/latitude', ''),
    ('crs_4979_inputcrs', 'll_4979', TM10, 0, 'is in longitude/latitude', ''),
    ('crs_4647_none', 'xy_4647', 'NONE', 0, 'TMERC, ALBERS or LCC', 'is in longitude/latitude'),
    ('crs_4647_tmerc', 'xy_4647', TM10, 1, '', ''),
    ('crs_4801_bern', 'll_4801', 'NONE', 0, 'prime meridian of Bern', ''), ('crs_4035_dms', 'll_4035', 'NONE', 0, 'angles are in degree minute second', ''),
    ('crs_2227_feet', 'xy_2227', TM10, 0, 'whose coordinates are in US survey foot', ''), ('crs_bom', 'll_bom', 'NONE', 1, '', ''),
    ('spec_lon_letters', 'utm_ver', 'TMERC 0 -ll7 0.9996 500000 0', 0, "TMERC parameter lon0: '-ll7' is not a number", ''),
    ('spec_k0_letter', 'utm_ver', 'TMERC 0 -123 O.9996 500000 0', 0, "parameter k0: 'O.9996' is not a number", ''),
    ('spec_fe_unit', 'utm_ver', 'TMERC 0 -123 0.9996 500km 0', 0, "parameter FE: '500km' is not a number", ''),
    ('spec_surplus', 'utm_ver', 'TMERC 0 -123 0.9996 500000 0 WGS84 junk', 0, 'TMERC takes lat0 lon0 k0 FE FN and an optional ellipsoid', ''),
    ('spec_too_few', 'utm_ver', 'LCC 49 77 49 -95 0', 0, 'LCC takes lat1 lat2 lat0 lon0 FE FN', ''),
    ('spec_ellipsoid', 'utm_ver', 'TMERC 0 -123 0.9996 500000 0 NAD27', 0, "ellipsoid must be WGS84 or GRS80, not 'NAD27'", ''),
    ('spec_epsg_letters', 'utm_ver', 'EPSG:32610x', 0, "'EPSG:32610x' is not EPSG: followed by a whole-number code", ''),
    ('spec_epsg_surplus', 'utm_ver', 'EPSG:32610 junk', 0, "surplus value 'junk' after EPSG:32610", ''),
    ('spec_albers_symmetric', 'utm_ver', 'ALBERS 30 -30 0 -96 0 0', 0, 'ALBERS (standard parallels lat1 30, lat2 -30): the standard parallels lie symmetric about the equator', ''),
    ('spec_albers_equator', 'utm_ver', 'ALBERS 0 0 0 -96 0 0', 0, 'lie symmetric about the equator', ''),
    ('spec_lcc_symmetric', 'utm_ver', 'LCC 30 -30 0 -96 0 0', 0, 'LCC (standard parallels lat1 30, lat2 -30): the standard parallels lie symmetric about the equator', ''),
    ('spec_lcc_equator', 'utm_ver', 'LCC 0 0 0 -96 0 0', 0, 'lie symmetric about the equator', ''),
    ('spec_lcc_pole', 'utm_ver', 'LCC 90 90 49 -95 0 0', 0, 'a standard parallel at a pole defines no Lambert conformal cone', '')]
with open('crs_cases.txt', 'w') as f:
    for n, k, spec, _, _, _ in CRS_CASES:
        f.write('%s test_crs_%s.geojson %s\n' % (n, k, spec))
# GeoJSON coordinates that are not JSON numbers, and features without "properties"
def gj(name, coords, props=True, kind='Polygon'):
    """a one-feature file whose coordinates are written as given (raw JSON text)"""
    f = '{"type": "Feature", %s"geometry": {"type": "%s", "coordinates": %s}}' % ('"properties": {"ID": 7}, ' if props else '', kind, coords)
    open('test_json_%s.geojson' % name, 'w').write('{"type": "FeatureCollection", "features": [%s]}' % f)
SQ = '[[[-123.0, 49.0], [%s, 49.0], [-122.9, 49.1], [-123.0, 49.1], [-123.0, 49.0]]]'
for n, v in (('str', '"-122.9"'), ('null', 'null'), ('bool', 'true'), ('nan', 'NaN'), ('inf', 'Infinity'), ('hex', '0x10'), ('big', '1e999'),
             ('lead0', '-0122.9'), ('ok', '-1.229E2')):
    gj(n, SQ % v)
gj('noprops', SQ % '-122.9', props=False)
def gjp(name, props, coords=SQ % '-122.9', kind='Polygon', tail=''):
    """a one-feature file with the properties given as raw JSON text"""
    open('test_json_%s.geojson' % name, 'w').write('{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": %s, '
                                                   '"geometry": {"type": "%s", "coordinates": %s}}]}%s' % (props, kind, coords, tail))
for n, v in (('id_null', 'null'), ('id_true', 'true'), ('id_7abc', '"7abc"'), ('id_frac', '2.6'), ('id_empty', '""'), ('id_str7', '"7"'), ('id_7p0', '7.0'),
             ('id_sp7', '" 7 "'), ('id_s7p0', '"7.0"'), ('id_s7p5', '"7.5"')):
    gjp(n, '{"ID": %s}' % v)
open('test_json_mixed.geojson', 'w').write('{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 7}, "geometry": {"type": "Polygon", '
                                           '"coordinates": %s}}, {"type": "Feature", "properties": {"ID": null}, "geometry": {"type": "Point", "coordinates": [-123.0, 49.0]}}, '
                                           '{"type": "Feature", "properties": {"ID": null}, "geometry": {"type": "LineString", "coordinates": [[-123.0, 49.0], [-122.9, 49.1]]}}]}' % (SQ % '-122.9'))
gjp('lid_null', '{"ID": null}', '[[-123.0, 49.0], [-122.9, 49.1]]', 'LineString')
gjp('shallow', '{"ID": 7}', '[[-123.0, 49.0], [-122.9, 49.0], [-122.9, 49.1], [-123.0, 49.0]]')
gjp('shortv', '{"ID": 7}', '[[[-123.0, 49.0], [1], [-122.9, 49.1], [-123.0, 49.1], [-123.0, 49.0]]]')
gjp('lshortv', '{"ID": 7}', '[[-123.0, 49.0], [1], [-122.9, 49.1]]', 'LineString')
gjp('lnum', '{"ID": 7}', '5', 'LineString')
gjp('attr_nan', '{"ID": 7, "elev": NaN, "q": Infinity, "r": -Infinity}')
gjp('uname', '{"H\\u00f6he_ID": 7, "x\\ud83d\\ude00": 1}')
gjp('tail', '{"ID": 7}', tail=' garbage {"x": 1}')
open('test_json_trunc.geojson', 'w').write(open('test_json_id_str7.geojson').read()[:-30])
gjp('id_big', '{"ID": 9007199254740993}')
open('test_json_gdalid.geojson', 'w').write('{"type": "FeatureCollection", "features": [{"type": "Feature", "id": 7, "properties": {"name": "a"}, '
                                            '"geometry": {"type": "Polygon", "coordinates": %s}}]}' % (SQ % '-122.9'))
HOLE = '[[-122.98, 49.02], [-122.92, 49.02], [-122.92, 49.08], [-122.98, 49.08], [-122.98, 49.02]]'
gjp('degen', '{"ID": 7}', '[[[-123.0, 49.0], [-123.0, 49.0]], %s]' % HOLE)
gjp('degen3', '{"ID": 7}', '[[[-123.0, 49.0], [-122.9, 49.0], [-123.0, 49.0], [-122.9, 49.0]]]')
gjp('degen_part', '{"ID": 7}', '[[[[-123.0, 49.0], [-123.0, 49.0]], %s], %s]' % (HOLE, SQ % '-122.9'), 'MultiPolygon')
gjp('col', '{"ID": 7}', '[[[-80.0, 45.0], [-79.99, 45.0], [-79.98, 45.0], [-80.0, 45.0]]]')
gjp('retrace', '{"ID": 7}', '[[[-80.0, 45.0], [-79.99, 45.0], [-79.99, 45.01], [-80.0, 45.01], [-79.99, 45.01], [-79.99, 45.0], [-80.0, 45.0]]]')
gjp('eight', '{"ID": 7}', '[[[-80.0, 45.0], [-79.99, 45.01], [-79.99, 45.0], [-80.0, 45.01], [-80.0, 45.0]]]')
gjp('col_part', '{"ID": 7}', '[[[[-80.0, 45.0], [-79.99, 45.0], [-79.98, 45.0], [-80.0, 45.0]]], %s]' % (SQ % '-122.9'), 'MultiPolygon')
gjp('id_bigexp', '{"ID": 1e+16}')
open('test_json_empty.geojson', 'w').write('{"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"ID": 1}, "geometry": {"type": "Polygon", '
                                           '"coordinates": %s}}, {"type": "Feature", "properties": {"ID": 2}, "geometry": {"type": "Polygon", "coordinates": []}}]}' % (SQ % '-122.9'))
gj('line_null', '[[-123.0, 49.0], [-122.9, null], [-122.8, 49.2]]', kind='LineString')
gj('line_noprops', '[[-123.0, 49.0], [-122.9, 49.1]]', props=False, kind='LineString')
JSON_CASES = [  # (name, file, reader, ID field, accepted, part of the message)
    ('json_str', 'str', 'poly', 'ID', 0, 'feature 1 (ID 7), ring 1 (outline), vertex 2: its x (longitude) is the string "-122.9", not a number'),
    ('json_null', 'null', 'poly', 'ID', 0, 'vertex 2: its x (longitude) is null, not a number'),
    ('json_bool', 'bool', 'poly', 'ID', 0, 'vertex 2: its x (longitude) is true, not a number'),
    ('json_nan', 'nan', 'poly', 'ID', 0, 'vertex 2: its x (longitude) is NaN, not a finite number'), ('json_inf', 'inf', 'poly', 'ID', 0, 'vertex 2: its x (longitude) is Infinity, not a finite number'),
    ('json_hex', 'hex', 'poly', 'ID', 0, "invalid JSON in test_json_hex.geojson at line 1, column "), ('json_lead0', 'lead0', 'poly', 'ID', 0, "invalid JSON in test_json_lead0.geojson at line 1, column "),
    ('json_hex_hint', 'hex', 'poly', 'ID', 0, "(hexadecimal numbers and numbers with leading zeros are not JSON)"),
    ('json_big', 'big', 'poly', 'ID', 0, 'vertex 2: its x (longitude) is a number too large'),
    ('json_ok', 'ok', 'poly', 'ID', 1, ''),
    ('json_noprops_id', 'noprops', 'poly', 'ID', 0, 'feature 1 in test_json_noprops.geojson has no "properties" member, so no ID field \'ID\''),
    ('json_noprops', 'noprops', 'poly', '-', 1, ''),
    ('json_line_null', 'line_null', 'line', '-', 0, 'feature 1, vertex 2: its y (latitude) is null, not a number'),
    ('json_line_noprops_id', 'line_noprops', 'line', 'ID', 0, 'has no "properties" member'),
    ('json_line_noprops', 'line_noprops', 'line', '-', 1, ''),
    ('json_id_null', 'id_null', 'poly', 'ID', 0, "test_json_id_null.geojson, feature 1: its ID field 'ID' is null, not a whole number"),
    ('json_id_true', 'id_true', 'poly', 'ID', 0, "its ID field 'ID' is true, not a whole number"),
    ('json_id_7abc', 'id_7abc', 'poly', 'ID', 0, "its ID field 'ID' is the string \"7abc\", not a whole number"),
    ('json_id_frac', 'id_frac', 'poly', 'ID', 0, "its ID field 'ID' is the number 2.6, not a whole number"),
    ('json_id_empty', 'id_empty', 'poly', 'ID', 0, "its ID field 'ID' is the string \"\", not a whole number"),
    ('json_id_str7', 'id_str7', 'poly', 'ID', 1, ''), ('json_id_7p0', 'id_7p0', 'poly', 'ID', 1, ''),
    ('json_id_sp7', 'id_sp7', 'poly', 'ID', 1, ''), ('json_id_s7p0', 'id_s7p0', 'poly', 'ID', 1, ''),
    ('json_id_s7p5', 'id_s7p5', 'poly', 'ID', 0, "its ID field 'ID' is the string \"7.5\", not a whole number"),
    ('json_mixed_poly', 'mixed', 'poly', 'ID', 1, ''), ('json_mixed_line', 'mixed', 'line', 'ID', 0, "its ID field 'ID' is null"),
    ('json_lid_null', 'lid_null', 'line', 'ID', 0, "its ID field 'ID' is null, not a whole number"),
    ('json_shallow', 'shallow', 'poly', 'ID', 0, 'feature 1 (ID 7), ring 1 (outline), vertex 1: it is the number -123.0, not a position [x, y]'),
    ('json_shortv', 'shortv', 'poly', 'ID', 0, 'ring 1 (outline), vertex 2: it is an array of 1 value, not a position [x, y]'),
    ('json_lshortv', 'lshortv', 'line', 'ID', 0, 'feature 1 (ID 7), vertex 2: it is an array of 1 value, not a position [x, y]'),
    ('json_lnum', 'lnum', 'line', 'ID', 0, 'feature 1 (ID 7), its coordinates: it is the number 5, not an array'),
    ('json_attr_nan', 'attr_nan', 'poly', 'ID', 1, ''),
    ('json_uname', 'uname', 'poly', 'H\u00f6he_ID', 1, ''),
    ('json_tail', 'tail', 'poly', 'ID', 0, 'text after the end of the GeoJSON object at line 1, column'),
    ('json_trunc', 'trunc', 'poly', 'ID', 0, 'invalid JSON in test_json_trunc.geojson', 'not JSON'),
    ('json_id_big', 'id_big', 'poly', 'ID', 0, "its ID field 'ID' is the number 9007199254740993, larger than 9e15, the largest ID Raven reads as a number (write it as a string"),
    ('json_gdalid', 'gdalid', 'poly', 'ID', 0, "missing ID field 'ID' in test_json_gdalid.geojson (the feature has an \"id\" member, where GDAL's ID_FIELD option puts the field"),
    ('json_id_bigexp', 'id_bigexp', 'poly', 'ID', 0, "is the number 1e+16, larger than 9e15, the largest ID Raven reads as a number (write the ID as a string of at most 18 digits)"),
    ('json_degen', 'degen', 'poly', 'ID', 1, 'ids= noarea=7: GeoJSON file test_json_degen.geojson, feature 1 (ID 7): its polygon has no area (its outline has fewer than 3 distinct vertices, lies on one line or encloses no net area);'),
    ('json_degen3', 'degen3', 'poly', 'ID', 1, 'ids= noarea=7: GeoJSON file test_json_degen3.geojson, feature 1 (ID 7): its polygon has no area'),
    ('json_col', 'col', 'poly', 'ID', 1, 'ids= noarea=7: GeoJSON file test_json_col.geojson, feature 1 (ID 7): its polygon has no area (its outline has fewer than 3 distinct vertices, lies on one line or encloses no net area);'),
    ('json_retrace', 'retrace', 'poly', 'ID', 1, 'ids= noarea=7: GeoJSON file test_json_retrace.geojson, feature 1 (ID 7): its polygon has no area'),
    ('json_eight', 'eight', 'poly', 'ID', 1, 'ids= noarea=7: GeoJSON file test_json_eight.geojson, feature 1 (ID 7): its polygon has no area'),
    ('json_col_part', 'col_part', 'poly', 'ID', 1, 'ids=7(1) noarea='),
    ('json_degen_part', 'degen_part', 'poly', 'ID', 1, 'ids=7(1) noarea='),
    ('json_empty', 'empty', 'poly', 'ID', 1, 'ids=1(1) noarea=2: GeoJSON file test_json_empty.geojson, feature 2 (ID 2): it has no polygon (its coordinates are empty);')]
with open('json_cases.txt', 'w', encoding='utf-8') as f:
    for n, k, kind, idf, *_ in JSON_CASES:
        f.write('%s test_json_%s.geojson %s %s\n' % (n, k, kind, idf))
# conic projections against PROJ, including an origin at the pole opposite the cone (PROJ takes either pole as the apex)
CONIC_CASES = [('LCC 50 60 -90 -96 0 0', -96.0, 55.0), ('LCC 50 60 -90 -96 0 0', -90.0, 49.0), ('LCC -50 -60 90 -96 0 0', -96.0, -55.0),
               ('LCC -50 -60 90 -96 0 0', -100.0, -61.0), ('LCC 50 60 90 -96 0 0', -96.0, 55.0), ('LCC -50 -60 -90 -96 0 0', -96.0, -55.0),
               ('LCC 49 77 49 -95 0 0', -110.0, 60.0), ('ALBERS 50 60 -90 -96 0 0', -96.0, 55.0), ('ALBERS -50 -60 90 -96 0 0', -96.0, -55.0),
               ('ALBERS 50 70 40 -96 1000 2000', -120.0, 61.0),
               ('ALBERS 55 65 50 -154 0 0', 172.9, 52.9), ('LCC 33 45 23 -96 0 0', 151.2, 40.0),   # (more than 180 degrees from lon0)
               ('ALBERS 55 65 50 -154 0 0', 26.0, 60.0),   # (exactly 180 degrees from lon0: PROJ keeps the side, |l| < pi + 1e-12)
               ('ALBERS 55 65 50 -154 0 0', -334.0, 60.0), ('ALBERS 60 90 90 0 0 0', -540.0, 70.0),   # (the same, written beyond +-180)
               ('LCC -30 -10 -20 -170 500000 0', -170.0, -90.0)]   # (the apex of a southern cone)
with open('conic_cases.txt', 'w') as f:
    for spec, lon, lat in CONIC_CASES:
        f.write('%s|%r %r\n' % (spec, lon, lat))

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

# the no-data margin: a point 0.4 cell beyond the raster's edge has a value (the outermost cells' values), 0.6 cell beyond none
r = np.loadtxt('raster_margin.txt')
report('raster: half a cell beyond the edge has a value, more has none', r[0, 2] == 1 and r[1, 2] == 0, r[0, 3])

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
js = {l.split()[0]: (int(l.split()[1]), ' '.join(l.split()[2:])) for l in open('json_status.txt')}
for n, k, kind, idf, ok, msg, *nomsg in JSON_CASES:
    got = js.get(n, (-1, 'missing'))
    good = got[0] == ok and msg in got[1] and not (nomsg and nomsg[0] in got[1])
    report('GeoJSON %-22s %s' % (n[5:], 'accepted' if ok else 'refused (%s)' % msg[-46:]), good, got[0])
    if not good:
        print('      message: %s' % got[1][:300])
cn = np.atleast_2d(np.loadtxt('conic.txt'))
for (spec, lon, lat), r in zip(CONIC_CASES, cn):
    w = spec.split(); p = dict(zip(('lat_1', 'lat_2', 'lat_0', 'lon_0', 'x_0', 'y_0'), map(float, w[1:7])))
    x, y = pyproj.Proj(proj={'LCC': 'lcc', 'ALBERS': 'aea'}[w[0]], ellps='WGS84', **p)(lon, lat)
    e = float(np.hypot(r[1] - x, r[2] - y)) if r[0] == 1 else 1e9; rt = max(abs((r[3] - lon + 180.0) % 360.0 - 180.0) if abs(lat) < 90 else 0.0, abs(r[4] - lat))   # (the inverse's longitude may differ by 360 degrees; none at a pole)
    report('projection: %-26s at %g, %g against PROJ (m)' % (spec, lon, lat), r[0] == 1 and e < 1e-3 and rt < 1e-9, e)
for n, k, spec, ok, msg, nomsg in CRS_CASES:
    got = st.get(n, (-1, 'missing'))
    good = got[0] == ok and msg in got[1] and not (nomsg and nomsg in got[1])
    report('%s %-22s %-11s %s' % ('spec' if n.startswith('spec') else '"crs"', (spec if n.startswith('spec') else CRS_FILES[k][1])[-22:], '' if n.startswith('spec') else spec[:11],
                                  'accepted' if ok else 'refused (%s)' % msg[:40]), good, got[0])
    if not good:
        print('      message: %s' % got[1][:300])

for f in ('clip.txt', 'proj.txt', 'raster.txt', 'raster_margin.txt', 'test.asc', 'test_utm.asc', 'raster_utm.txt', 'crs_status.txt', 'poly_utm.txt', 'line_utm.txt',
          'test_utm_poly.geojson', 'test_utm_bare.geojson', 'test_ll_crs84.geojson', 'test_utm_line.geojson', 'crs_cases.txt', 'conic_cases.txt', 'conic.txt', 'json_cases.txt', 'json_status.txt') + tuple(
          'test_crs_%s.geojson' % k for k in CRS_FILES) + tuple('test_json_%s.geojson' % k for k in sorted(set(c[1] for c in JSON_CASES))):
    if os.path.exists(f):   # another run in the same checkout may have removed it already
        os.remove(f)
print('ALL PASSED' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
