"""GeoTIFF rasters for :LandSurface and :BedrockSurface, the EPSG longitude/latitude rule, and rasters that cover no cell.

    python3 geotiff_check.py            # all checks (Raven runs need the MODFLOW 6 library)
    python3 geotiff_check.py --nolib    # only the reader checks (no Raven runs)

The fixtures in fixtures/ were written once by GDAL and tifffile (tools/dev/make_geotiff_fixtures.py, which lists them);
each GeoTIFF that Raven reads has an ESRI ASCII twin with the same values. This script needs only Raven, its source (the
reader is compiled into a small unit driver, geotiff_unit.cpp) and the test harness (testconfig.py and its modules).

Reader checks (unit driver):
  - every fixture against its twin: the same corner, cell size and every value bit for bit (NODATA where the twin has
    it), and the encoding read as written (compression, predictor, byte order, strips or tiles, classic or BigTIFF);
    PixelIsPoint files give the same corner as PixelIsArea ones; internal masks (GDAL 1 bit, tifffile 1 bit in tiles and
    8 bit) give no data at the masked pixels; tiles of 2048 x 2048 on a small raster; the EPSG code and its kind as written;
  - GDAL's band scale and offset (GDAL_METADATA) are applied (16-bit decimetres against a twin of the scaled values,
    NODATA pixels no data); items named SCALE, OFFSET and UNITTYPE without GDAL's role are ordinary metadata (values as
    stored); a band unit in feet stops, an unknown band unit gives a warning; the unit's words are matched whole: "m
    (Admiralty datum)", "metres above Hydrographic Datum", "elevation in metres", "in metres", "in m" and "in meters above
    sea level" are metres, "hydraulic head" is an unknown unit (a warning), "feet above sea level", "US survey foot",
    "kilometres" and "in" (inches) stop; so do the US-foot spellings of GDAL and PROJ, also fused ("ftUS", "usft",
    "us-ft", "USfeet", "foot_us", "Foot_US", "foot_survey_us", "NAVD88 ftUS", "sft", "ind-ft") and "fathom"; a unit
    without letters ("'", "?") and "\u00b5m" (micrometres: m glued to a non-ASCII letter) give the unknown-unit warning;
    "metre" and "m above NAVD88" are metres; PROJ's short ids (ch, mi, fath, link, in, also after us/ind: "us-in",
    "us-ch") stop only as the first word and without a metre word, so "Elevation in m (CH1903+)", "elevation [m] CH",
    "H\u00f6he in m \u00fc. M. (CH)", "Elevation (m) see link" and "height in metres, mi" are metres and "hauteur \u00e0
    mi-mar\u00e9e" an unknown unit; a number before the metre word ("0.1 m") gives the unknown-unit warning, a word
    that ends in a digit does not ("CH1903 m", "CH1903 metres", "NAVD88 m", "EGM96 m" are metres); feet written in
    camel case or as one word ("SurveyFeet", "InternationalFeet", "USSurveyFoot", "esriSRUnit_SurveyFoot",
    "decimalfeet", "fasl") stop, as do "fmsl", the EPSG feet codes (EPSG:9002, EPSG:9003; EPSG:9001 is metres) and
    "pies", "pieds", "Fu\u00df", "voet", "Fuss", "FUSS", "piedi", "p\u00e9s", "P\u00c9S", "fot", "Fod"; "mASL" is metres
    and "Micrometer" another unit; a number with punctuation or a factor sign before the metre word ("[0.1 m]", "(0.1 m)",
    "1,5 m", "1/1000 m", "x0.1 m", "1:1000 m") gives the unknown-unit warning, and so does a number after it that is a
    scale: after a factor sign or word, or a fraction ("m*0.1", "metres x 0.1", "m (scaled by 0.1)", "m \u00d70.1",
    "m / 10"), while datum years, versions and other whole numbers after it are not ("m NAVD 88", "m (NAVD 1988)",
    "m CGVD 2013", "m (RH 2000)", "metres NN 2016", "m \u00fc. NHN 2016", "m, EGM 2008", "height m 2020", "m above datum
    1", "Elevation, m, version 2", "m (2 m grid)", "m, 1 m resolution": metres); the EPSG codes of other lengths
    (EPSG:9036 km, 1033 cm, 1025 mm, 9030 nautical mile, 9093 mile, 9301 British chain), a prefix written as a word and
    attached to the metre word ("kiloMeters", "Kilo Meter") and "tenths of metres" stop, a prefix word elsewhere does not
    ("nano DEM m", "m kilo": metres); "pesos" (no unit word) gives the unknown-unit warning;
  - no GDAL_NODATA tag: -9999 and float32-lowest pixels stay values, with a warning naming their counts; a user-defined
    vertical system is read as metres with a warning (EPSG:4326+5773, in metres, without one); a damaged pointer to the
    next image directory after a good raster gives a warning and the raster without its mask; a mask after 100 pages
    is found;
  - rectangular pixels (twice as wide, twice as high): corner, pixel size and values as written, and 3,000 samples
    against a bilinear sampler written here from the manual's description (within 1e-9);
  - the same rasters through CGWRaster (Raven's sampling): 4,000 points inside, on the edges and outside give the same
    values and the same misses for the GeoTIFF and its twin;
  - every file Raven must refuse is refused with a message naming the file and the reason (also FillOrder 2 and units
    other than metres and degrees, vertical systems in feet, prime meridians other than Greenwich, also when given only
    by their longitude (GDAL's user-defined systems) or by the datum, a projected code in feet without its units key, a
    decoding area above the bound), also a file over the size limit (a sparse file made here and removed);
  - ESRI ASCII grids: GDAL's dx and dy header (rectangular pixels) gives the GeoTIFF's samples, NODATA_value nan the
    -9999 twin's, and so do a Ctrl-Z after the values, a UTF-8 byte-order mark and xllcenter with yllcorner; more values than ncols*nrows, an unknown header key, a value that is not a number, a key given
    twice (cellsize 1, then cellsize 2) and both xllcenter and xllcorner are refused, naming the problem;
  - CRS rules: a geographic code is refused with :InputCRS, a projected one without it; another built-in projection
    than :InputCRS is refused, the same one given by its parameters accepted; a code that is not built in is accepted
    under :InputCRS given by parameters (with a note) and refused under another EPSG code; a user-defined CRS and none at
    all are read as an ESRI ASCII grid is; :InputCRS ESRI:102001 counts as a code; the advice for a projected code
    without :InputCRS names EPSG:n only when it is built in;
  - EPSG codes: 4647 (ETRS89 / UTM 32N, zE-N) is not longitude/latitude; 4326, 4269, 4617, 6318, 4979 are;
  - fuzzing: damaged copies of every fixture (bytes changed, cut, inserted, random) and random decoder input are read
    without a crash (each refused with a message or read).
Raven runs (a 2-HRU CONCEPTUAL model, 32 active columns, 2 days):
  - every fixture as :LandSurface (several also as :BedrockSurface) against its ESRI ASCII twin: byte-identical outputs
    (mf6/gwf.dis holds the sampled cell elevations), timing lines and MODFLOW listing files excepted;
  - projected rasters under :InputCRS (EPSG:32611 and the same projection by its parameters, a user-defined CRS, a
    code that is not built in) against the twin, and the CRS stops through Raven;
  - a raster that covers no active column (1 degree east, GeoTIFF and ESRI ASCII, DEM and bedrock, and a raster with
    only NODATA over the model) stops with the raster's and the model's extents; one that covers part of the columns
    gives a warning with the count; an unsupported file stops the run with the reader's message.
Quick mode (RAVEN_TEST_QUICK=1): fuzzing with 100 damaged copies per file instead of 1,000; the Raven runs are the same.
"""
import os, sys, re, json, math, shutil, subprocess, filecmp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'soilzone'))
import testconfig as tc   # noqa: E402

NOLIB = '--nolib' in sys.argv
QUICK = os.environ.get('RAVEN_TEST_QUICK', '') == '1'
FIX = os.path.join(HERE, 'fixtures')
W = os.path.join(tc.WORK, 'geotiff')
M = json.load(open(os.path.join(FIX, 'manifest.json')))
fails = 0


def report(name, ok, detail=''):
    global fails
    print('%-86s %s  %s' % (name, 'ok' if ok else 'FAIL', detail), flush=True)
    fails += 0 if ok else 1


def fx(f):
    return os.path.join(FIX, f)


# ---- the unit driver
os.makedirs(W, exist_ok=True)
UNIT = os.path.join(W, 'geotiff_unit')
r = subprocess.run('g++ -std=c++11 -O2 -I%s %s %s/GWGeoTIFF.cpp %s/GWGeometry.cpp -o %s' % (tc.SRC, os.path.join(HERE, 'geotiff_unit.cpp'), tc.SRC, tc.SRC, UNIT),
                   shell=True, capture_output=True, text=True)
if r.returncode != 0:
    sys.exit('geotiff_unit does not compile:\n' + r.stdout + r.stderr)


def unit(*args):
    r = subprocess.run([UNIT] + list(args), capture_output=True, text=True)
    if r.returncode != 0:
        return 'CRASH (exit code %d) %s' % (r.returncode, (r.stdout + r.stderr)[-300:])
    return r.stdout


def twin(f):
    L = open(fx(f)).read().split('\n'); h = {}
    for l in L[:6]:
        k, v = l.split(); h[k.lower()] = float(v)
    return h, [[float(x) for x in l.split()] for l in L[6:] if l.strip()]


CNAME = {1: 'uncompressed', 5: 'LZW', 8: 'DEFLATE', 32946: 'DEFLATE', 32773: 'PackBits'}
NBITS = {'uint8': '8-bit unsigned', 'int8': '8-bit signed', 'uint16': '16-bit unsigned', 'int16': '16-bit signed', 'uint32': '32-bit unsigned',
         'int32': '32-bit signed', 'uint64': '64-bit unsigned', 'int64': '64-bit signed', 'float32': '32-bit float', 'float64': '64-bit float'}

# ---- reader: every fixture against its twin
n_ok, bad = 0, []
for m in M:
    if not m['twin']:
        continue
    out = unit('dump', fx(m['file'])).split('\n')
    if not out[0].startswith('OK '):
        bad.append('%s: %s' % (m['file'], out[0][:200])); continue
    f = out[0].split(); fmt = out[1][len('FORMAT '):]
    h, v = twin(m['twin'])
    geo = (float(f[3]), float(f[4]), float(f[5]), float(f[6])) == (h['xllcorner'], h['yllcorner'], h['cellsize'], h['cellsize'])
    vals = [[float(x) for x in l.split()] for l in out[2:] if l.strip()]
    nd = h['nodata_value']; hasnd, tnd = f[7] == '1', float(f[8])

    def same(a, b):
        if b == nd:      # NODATA in the twin: NODATA (or NaN) in the GeoTIFF
            return a != a or (hasnd and a == tnd)
        return a == b and not (hasnd and a == tnd)
    eq = len(vals) == len(v) and all(len(ra) == len(rb) and all(same(a, b) for a, b in zip(ra, rb)) for ra, rb in zip(vals, v))
    enc = True
    if 'compression' in m:
        enc = (CNAME[m['compression']] in fmt and ('predictor %d' % (m['predictor'] if m['compression'] in (5, 8, 32946) else 1)) in fmt
               and NBITS[m['dtype']] in fmt and ('big-endian' if m.get('byteorder') == 'big' else 'little-endian') in fmt) if m['kind'] in ('matrix', 'range') and 'byteorder' in m else True
        if m['kind'] == 'matrix' and 'layout' in m:
            enc = enc and (('tiled 16x16' if m['layout'] == 'tiles' else 'strips of 8 rows') in fmt) and fmt.startswith('BigTIFF' if m['container'] == 'BigTIFF' else 'TIFF,')
    if m['kind'] == 'point':
        enc = enc and 'PixelIsPoint' in fmt and f[11] == '2'
    if m['kind'] == 'mask':
        nmask = sum(1 for r in v for b in r if b == nd)
        enc = enc and ('internal mask (%d pixels no data)' % nmask) in fmt
    if m['kind'] == 'bigtile':
        enc = enc and 'tiled 2048x2048' in fmt
    if m['kind'] == 'crs':
        enc = enc and int(f[9]) == (m['epsg'] if m['epsg'] != 32767 else 0) and f[10] == ('1' if m['epsg'] in (4269, 4326) else '0')
    if geo and eq and enc:
        n_ok += 1
    else:
        bad.append('%s: corner/cell size %s, values %s, encoding %s (%s)' % (m['file'], geo, eq, enc, fmt))
nt = sum(1 for m in M if m['twin'])
report('reader: %d GeoTIFF fixtures against their ESRI ASCII twins (corner, cell size, every value, encoding)' % nt, n_ok == nt, '%d of %d' % (n_ok, nt))
for b in bad[:10]:
    print('      ' + b)
cnt = {}
for m in M:
    if m['kind'] == 'matrix' and 'layout' in m:
        for k in ('compression', 'predictor', 'dtype', 'byteorder', 'layout', 'container', 'writer'):
            cnt.setdefault(k, set()).add(str(m[k]))
print('      matrix covers: ' + '; '.join('%s %s' % (k, ', '.join(sorted(v))) for k, v in cnt.items()))

# ---- reader: rectangular pixels, against the values and corner written and an independent bilinear sampler
def bilinear(V, xll, yll, dx, dy, nd, x, y):
    """Raven's sampling (manual, Raster maps): bilinear between pixel centres, no-data pixels left out, points more than one
    pixel off the raster have no value"""
    nr, nc = len(V), len(V[0])
    fc, fr = (x - xll) / dx - 0.5, (yll + nr * dy - y) / dy - 0.5
    if fc < -1 or fr < -1 or fc > nc or fr > nr:
        return None
    fc, fr = max(0.0, min(nc - 1.0, fc)), max(0.0, min(nr - 1.0, fr))
    c0, r0 = int(math.floor(fc)), int(math.floor(fr)); c1, r1 = min(c0 + 1, nc - 1), min(r0 + 1, nr - 1)
    wc, wr = fc - c0, fr - r0
    s = w = 0.0
    for r, c, k in ((r0, c0, (1 - wr) * (1 - wc)), (r0, c1, (1 - wr) * wc), (r1, c0, wr * (1 - wc)), (r1, c1, wr * wc)):
        if V[r][c] != nd:
            s += k * V[r][c]; w += k
    return s / w if w >= 1e-9 else None
for m in M:
    if m['kind'] != 'nonsquare':
        continue
    out = unit('dump', fx(m['file'])).split('\n')
    h, v = twin(m['values'])
    ok, geo, vals, miss, worst, nfound = out[0].startswith('OK '), False, False, 0, 0.0, 0
    if ok:
        f = out[0].split()
        geo = [float(x) for x in f[3:7]] == [m['xll'], m['yll'], m['dx'], m['dy']]
        vals = [[float(x) for x in l.split()] for l in out[2:] if l.strip()] == v
        worst, miss, nfound = 0.0, 0, 0
        for l in unit('sample', fx(m['file']), '3000').split('\n'):
            if not l.strip():
                continue
            x, y, found, val = l.split(); x, y, val = float(x), float(y), float(val)
            ref = bilinear(v, m['xll'], m['yll'], m['dx'], m['dy'], h['nodata_value'], x, y)
            if (ref is None) != (found == '0'):
                miss += 1
            elif ref is not None:
                worst = max(worst, abs(val - ref)); nfound += 1
        ok = geo and vals and miss == 0 and worst < 1e-9 and nfound > 1000
    report('rectangular pixels: %-26s (%g/1024 x %g/1024 degree): corner, values, 3000 samples' % (m['file'], m['dx'] * 1024, m['dy'] * 1024),
           ok, ('%d samples with values, worst difference %.1e' % (nfound, worst)) if ok else out[0][:150] + (' geo %s values %s misses %d worst %.2e' % (geo, vals, miss, worst) if out[0].startswith('OK') else ''))

# ---- reader: CGWRaster sampling of each fixture and its twin
n_ok, bad = 0, []
for m in M:
    if not m['twin'] or m['kind'] == 'range':
        continue
    crs = 'EPSG:32611' if 'utm11' in m['twin'] else 'NONE'
    if m['file'] == 'crs_2955_f32.tif':
        crs = 'TMERC 0 -117 0.9996 500000 0 GRS80'
    o = unit('samplecmp', fx(m['file']), fx(m['twin']), crs)
    g = re.search(r'SAMPLES (\d+) points, (\d+) with values, (\d+) differ', o)
    if g and int(g.group(3)) == 0 and int(g.group(2)) > 1000:
        n_ok += 1
    else:
        bad.append('%s: %s' % (m['file'], o.strip()[:200]))
nt = sum(1 for m in M if m['twin'] and m['kind'] != 'range')
report('sampling: CGWRaster samples of %d GeoTIFFs and their twins at 4000 points each, bit for bit' % nt, n_ok == nt, '%d of %d' % (n_ok, nt))
for b in bad[:10]:
    print('      ' + b)

# ---- reader: refused files
n_ok, bad = 0, []
for m in M:
    if m['kind'] != 'stop':
        continue
    o = unit('dump', fx(m['file'])).split('\n')[0]
    if o.startswith('ERROR') and m['expect'] in o and m['file'] in o:
        n_ok += 1
    else:
        bad.append('%s: expected "%s", got: %s' % (m['file'], m['expect'], o[:240]))
nt = sum(1 for m in M if m['kind'] == 'stop')
report('refused: %d unsupported, corrupt or truncated files, each with its reason' % nt, n_ok == nt, '%d of %d' % (n_ok, nt))
for b in bad:
    print('      ' + b)
big = os.path.join(W, 'oversize.tif')
with open(big, 'wb') as f:
    f.write(open(fx('matrix_uint8_c1_p1_le_strip_classic.tif'), 'rb').read()); f.truncate(1100 * 1024 * 1024)   # (sparse: no disk space used)
o = unit('dump', big).split('\n')[0]
os.remove(big)
report('refused: a file over the size limit (1100 MB, sparse) stops before it is read', o.startswith('ERROR') and 'MB, more than the 1024 MB' in o, o[:120])

# ---- reader: CRS rules (CGWRaster with :InputCRS)
TM_WGS, TM_GRS = 'TMERC 0 -117 0.9996 500000 0 WGS84', 'TMERC 0 -117 0.9996 500000 0 GRS80'
CRS_CASES = [('crs_4269_f32.tif', 'NONE', 'OK', ''), ('matrix_float32_c5_p3_le_strip_classic.tif', 'NONE', 'OK', ''),
             ('crs_4269_f32.tif', 'EPSG:32611', 'ERROR', 'is in longitude/latitude (EPSG:4269'),
             ('matrix_float32_c5_p3_le_strip_classic.tif', 'EPSG:32611', 'ERROR', 'is in longitude/latitude (EPSG:4326'),
             ('crs_32611_f32.tif', 'NONE', 'ERROR', 'give :InputCRS EPSG:32611 in the .rvg file'), ('crs_32611_f32.tif', 'EPSG:32611', 'OK', ''),
             ('crs_32611_f32.tif', TM_WGS, 'OK', ''), ('crs_32611_f32.tif', 'EPSG:32610', 'ERROR', 'but :InputCRS is EPSG:32610'),
             ('crs_32611_f32.tif', TM_GRS, 'ERROR', 'all input files must use the projection of :InputCRS'),
             ('crs_2955_f32.tif', TM_GRS, 'OK', 'a projection that is not built in'),
             ('crs_2955_f32.tif', 'NONE', 'ERROR', "give :InputCRS with the projection's parameters (TMERC, ALBERS or LCC; EPSG:2955 is not built in)"),
             ('crs_2955_f32.tif', 'ESRI:102001', 'ERROR', 'is in EPSG:2955 (in its GeoTIFF keys), but :InputCRS is ESRI:102001'),
             ('crs_2955_f32.tif', 'EPSG:32611', 'ERROR', 'is in EPSG:2955 (in its GeoTIFF keys), but :InputCRS is EPSG:32611'),
             ('crs_userdef_f32.tif', 'EPSG:32611', 'OK', ''), ('crs_userdef_f32.tif', 'NONE', 'ERROR', 'outside the longitude/latitude range'),
             ('crs_none_f32.tif', 'NONE', 'OK', '')]
for f, crs, want, part in CRS_CASES:
    o = unit('raster', fx(f), crs).strip()
    ok = o.startswith(want) and part in o and (want == 'ERROR' or part != '' or o == 'OK') and not (f == 'crs_2955_f32.tif' and ':InputCRS EPSG:2955' in o)
    report('CRS: %-26s :InputCRS %-34s %s' % (f, crs, 'accepted' if want == 'OK' else 'refused'), ok, o[:150] if not ok else '')

# ---- no GDAL_NODATA: values that usually mark missing data are reported, and read as values
for m in M:
    if m['kind'] in ('fill', 'vertnote', 'chain', 'unitnote'):
        o = unit('raster', fx(m['file']), 'NONE').strip()
        report('warning: %s "%s"' % (m['file'], m['expect'][:60]), o.startswith('OK') and m['expect'] in o, o[:200])
o = unit('raster', fx('matrix_int16_c8_p2_le_strip_classic.tif') if os.path.exists(fx('matrix_int16_c8_p2_le_strip_classic.tif')) else fx('twin_int16.asc'), 'NONE').strip()
report('no NODATA tag and no such values: no warning', o == 'OK', o[:120])

# ---- band units (UNITTYPE): matched as whole words
def with_unit(text, name):
    """unit_height_meta.tif with another UNITTYPE text (the GDAL_METADATA string rewritten at the end of the file)"""
    import struct
    b = bytearray(open(fx('unit_height_meta.tif'), 'rb').read()); off = struct.unpack('<I', b[4:8])[0]; n = struct.unpack('<H', b[off:off + 2])[0]
    for i in range(n):
        e = off + 2 + 12 * i; t, ty, c, v = struct.unpack('<HHII', b[e:e + 12])
        if t == 42112:
            meta = (bytes(b[v:v + c]).rstrip(b'\0').decode().replace('>height<', '>%s<' % text)).encode() + b'\0'
            b[e:e + 12] = struct.pack('<HHII', t, ty, len(meta), len(b)); b += meta
    p = os.path.join(W, name); open(p, 'wb').write(bytes(b)); return p
for text, want, part in (('m (Admiralty datum)', 'OK', ''), ('metres above Hydrographic Datum', 'OK', ''), ('elevation in metres', 'OK', ''),
                         ('in metres', 'OK', ''), ('in m', 'OK', ''), ('in meters above sea level', 'OK', ''),
                         ('hydraulic head', 'OK', "has the band unit 'hydraulic head'"), ('feet above sea level', 'ERROR', 'elevations are in feet above sea level'),
                         ('US survey foot', 'ERROR', 'elevations are in US survey foot'), ('kilometres', 'ERROR', 'elevations are in kilometres'), ('in', 'ERROR', 'elevations are in in'),
                         ('ftUS', 'ERROR', 'elevations are in ftUS'), ('usft', 'ERROR', 'elevations are in usft'), ('us-ft', 'ERROR', 'elevations are in us-ft'),
                         ('USfeet', 'ERROR', 'elevations are in USfeet'), ('foot_us', 'ERROR', 'elevations are in foot_us'), ('Foot_US', 'ERROR', 'elevations are in Foot_US'),
                         ('foot_survey_us', 'ERROR', 'elevations are in foot_survey_us'), ('NAVD88 ftUS', 'ERROR', 'elevations are in NAVD88 ftUS'),
                         ('sft', 'ERROR', 'elevations are in sft'), ('ind-ft', 'ERROR', 'elevations are in ind-ft'), ('fathom', 'ERROR', 'elevations are in fathom'),
                         ("'", 'OK', "has the band unit '''"), ('?', 'OK', "has the band unit '?'"), ('\u00b5m', 'OK', "has the band unit '\u00b5m'"),
                         ('metre', 'OK', ''), ('m above NAVD88', 'OK', ''),
                         ('Elevation in m (CH1903+)', 'OK', ''), ('elevation [m] CH', 'OK', ''), ('H\u00f6he in m \u00fc. M. (CH)', 'OK', ''),
                         ('Elevation (m) see link', 'OK', ''), ('height in metres, mi', 'OK', ''),
                         ('hauteur \u00e0 mi-mar\u00e9e', 'OK', "has the band unit 'hauteur"), ('0.1 m', 'OK', "has the band unit '0.1 m'"),
                         ('us-in', 'ERROR', 'elevations are in us-in'), ('us-ch', 'ERROR', 'elevations are in us-ch'), ('mi', 'ERROR', 'elevations are in mi'),
                         ('link', 'ERROR', 'elevations are in link'),
                         ('CH1903 m', 'OK', ''), ('CH1903 metres', 'OK', ''), ('in CH1903 m', 'OK', ''), ('NAVD88 m', 'OK', ''), ('EGM96 m', 'OK', ''),
                         ('SurveyFeet', 'ERROR', 'elevations are in SurveyFeet'), ('InternationalFeet', 'ERROR', 'elevations are in InternationalFeet'),
                         ('USSurveyFoot', 'ERROR', 'elevations are in USSurveyFoot'), ('esriSRUnit_SurveyFoot', 'ERROR', 'elevations are in esriSRUnit_SurveyFoot'),
                         ('decimalfeet', 'ERROR', 'elevations are in decimalfeet'), ('fasl', 'ERROR', 'elevations are in fasl'),
                         ('mASL', 'OK', ''), ('Micrometer', 'ERROR', 'elevations are in Micrometer'),
                         ('[0.1 m]', 'OK', "has the band unit '[0.1 m]'"), ('(0.1 m)', 'OK', "has the band unit '(0.1 m)'"), ('1,5 m', 'OK', "has the band unit '1,5 m'"),
                         ('1/1000 m', 'OK', "has the band unit '1/1000 m'"), ('x0.1 m', 'OK', "has the band unit 'x0.1 m'"), ('1:1000 m', 'OK', "has the band unit '1:1000 m'"),
                         ('EPSG:9002', 'ERROR', 'elevations are in EPSG:9002'), ('EPSG:9003', 'ERROR', 'elevations are in EPSG:9003'), ('EPSG:9001', 'OK', ''),
                         ('fmsl', 'ERROR', 'elevations are in fmsl'), ('pies', 'ERROR', 'elevations are in pies'), ('pieds', 'ERROR', 'elevations are in pieds'),
                         ('Fu\u00df', 'ERROR', 'elevations are in Fu\u00df'), ('voet', 'ERROR', 'elevations are in voet'),
                         ('Fuss', 'ERROR', 'elevations are in Fuss'), ('FUSS', 'ERROR', 'elevations are in FUSS'), ('piedi', 'ERROR', 'elevations are in piedi'),
                         ('p\u00e9s', 'ERROR', 'elevations are in p\u00e9s'), ('P\u00c9S', 'ERROR', 'elevations are in P\u00c9S'), ('fot', 'ERROR', 'elevations are in fot'),
                         ('Fod', 'ERROR', 'elevations are in Fod'), ('EPSG:9036', 'ERROR', 'elevations are in EPSG:9036'), ('EPSG:1033', 'ERROR', 'elevations are in EPSG:1033'),
                         ('EPSG:1025', 'ERROR', 'elevations are in EPSG:1025'), ('EPSG:9030', 'ERROR', 'elevations are in EPSG:9030'), ('EPSG:9093', 'ERROR', 'elevations are in EPSG:9093'),
                         ('kiloMeters', 'ERROR', 'elevations are in kiloMeters'), ('Kilo Meter', 'ERROR', 'elevations are in Kilo Meter'),
                         ('tenths of metres', 'ERROR', 'elevations are in tenths of metres'), ('m*0.1', 'OK', "has the band unit 'm*0.1'"),
                         ('metres x 0.1', 'OK', "has the band unit 'metres x 0.1'"), ('m (scaled by 0.1)', 'OK', "has the band unit 'm (scaled by 0.1)'"),
                         ('pesos', 'OK', "has the band unit 'pesos'"), ('EPSG:9301', 'ERROR', 'elevations are in EPSG:9301'),
                         ('m NAVD 88', 'OK', ''), ('m (NAVD 1988)', 'OK', ''), ('m CGVD 2013', 'OK', ''), ('m (RH 2000)', 'OK', ''), ('metres NN 2016', 'OK', ''),
                         ('m \u00fc. NHN 2016', 'OK', ''), ('m, EGM 2008', 'OK', ''), ('height m 2020', 'OK', ''), ('m above datum 1', 'OK', ''),
                         ('Elevation, m, version 2', 'OK', ''), ('m (2 m grid)', 'OK', ''), ('m, 1 m resolution', 'OK', ''), ('nano DEM m', 'OK', ''),
                         ('m kilo', 'OK', ''), ('m \u00d70.1', 'OK', "has the band unit 'm \u00d70.1'"), ('m / 10', 'OK', "has the band unit 'm / 10'")):
    o = unit('raster', with_unit(text, 'unit_%s.tif' % re.sub(r'\W', '_', text)), 'NONE').strip()
    good = o.startswith(want) and part in o and (part != '' or o == 'OK')
    report('band unit "%s": %s' % (text, {'OK': 'read as metres' if not part else 'read as metres, with a note', 'ERROR': 'stops'}[want]), good, o[:160])

# ---- ESRI ASCII grids (CGWRaster): GDAL's rectangular-pixel header, NaN NODATA, and malformed grids
def asc_write(name, header, rows):
    p = os.path.join(W, name)
    with open(p, 'w') as f:
        f.write(''.join('%s %s\n' % kv for kv in header) + ''.join(' '.join(r) + '\n' for r in rows))
    return p
for m in M:
    if m['kind'] != 'nonsquare':
        continue
    L = open(fx(m['values'])).read().split('\n'); rows = [l.split() for l in L[6:] if l.strip()]
    hd = [('ncols', len(rows[0])), ('nrows', len(rows)), ('xllcorner', repr(m['xll'])), ('yllcorner', repr(m['yll'])), ('dx', repr(m['dx'])), ('dy', repr(m['dy'])),
          ('NODATA_value', -9999)]
    a = asc_write('dxdy.asc', hd, rows)
    o = unit('samplecmp', fx(m['file']), a, 'NONE')
    g = re.search(r'SAMPLES (\d+) points, (\d+) with values, (\d+) differ', o)
    report('ESRI ASCII: dx %g/1024, dy %g/1024 header (GDAL) samples as %s' % (m['dx'] * 1024, m['dy'] * 1024, m['file']), bool(g) and g.group(3) == '0' and int(g.group(2)) > 1000, o.strip()[:150])
    xc = [('xllcenter', repr(m['xll'] + 0.5 * m['dx'])), ('yllcenter', repr(m['yll'] + 0.5 * m['dy']))]
    a = asc_write('dxdy_center.asc', hd[:2] + xc + hd[4:], rows)
    o = unit('samplecmp', fx(m['file']), a, 'NONE'); g = re.search(r'(\d+) differ', o)
    report('ESRI ASCII: dx, dy with xllcenter, yllcenter (half a pixel each way)', bool(g) and g.group(1) == '0', o.strip()[:150])
    break
tw = [m['twin'] for m in M if m['twin'] and m['kind'] == 'nodata' and '-9999' in open(fx(m['twin'])).read().split('\n', 6)[6]][0]
L = open(fx(tw)).read().split('\n'); hd = [tuple(l.split()) for l in L[:6]]; rows = [l.split() for l in L[6:] if l.strip()]
a = asc_write('nan.asc', [kv if kv[0].lower() != 'nodata_value' else ('NODATA_value', 'nan') for kv in hd], [['nan' if v == '-9999' else v for v in r] for r in rows])
o = unit('samplecmp', a, fx(tw), 'NONE'); g = re.search(r'(\d+) with values, (\d+) differ', o)
report('ESRI ASCII: NODATA_value nan (NaN pixels) samples as the -9999 twin %s' % tw, bool(g) and g.group(2) == '0' and int(g.group(1)) > 1000, o.strip()[:150])
BAD_ASC = [('surplus.asc', hd, rows + [rows[0][:1]], 'has more values than ncols*nrows'),
           ('wrap.asc', [('ncols', int(hd[0][1]) - 1)] + hd[1:], rows, 'has more values than ncols*nrows'),
           ('fewer.asc', hd, rows[:-1], 'fewer than ncols*nrows'),
           ('badkey.asc', [('cellsizee', hd[4][1]) if kv[0].lower() == 'cellsize' else kv for kv in hd], rows, "unknown header key 'cellsizee'"),
           ('badval.asc', hd, [rows[0][:2] + ['1O'] + rows[0][3:]] + rows[1:], "the value '1O' (row 1, column 3) is not a number"),
           ('badhead.asc', [('xllcorner', '-12O.5') if kv[0].lower() == 'xllcorner' else kv for kv in hd], rows, "header key xllcorner ('-12O.5') is not a number"),
           ('onlydx.asc', [('dx', hd[4][1]) if kv[0].lower() == 'cellsize' else kv for kv in hd], rows, 'needs a positive cellsize, or positive dx and dy'),
           ('dupcs.asc', hd[:5] + [('cellsize', repr(2 * float(hd[4][1])))] + hd[5:], rows, 'the header gives the key cellsize twice'),
           ('both.asc', hd[:2] + [('xllcenter', repr(float(hd[2][1]) + 0.5 * float(hd[4][1]))), hd[2]] + hd[3:], rows,   # (hd: ncols, nrows, xllcorner, ...)
            'the header gives xllcorner and xllcenter (a corner and a centre of the same axis)')]
# a DOS end-of-file mark (Ctrl-Z) after the values, a UTF-8 byte-order mark, and a centre on one axis and a corner on the
# other: read, and sampled as the twin
x0 = float([kv for kv in hd if kv[0].lower() == 'xllcorner'][0][1]); cs0 = float([kv for kv in hd if kv[0].lower() == 'cellsize'][0][1])
OK_ASC = [('ctrlz.asc', hd, rows, lambda b: b + b'\x1a'), ('bom.asc', hd, rows, lambda b: b'\xef\xbb\xbf' + b),
          ('mixed.asc', [('xllcenter', repr(x0 + 0.5 * cs0)) if kv[0].lower() == 'xllcorner' else kv for kv in hd], rows, lambda b: b)]
for name, h, r, f in OK_ASC:
    a = asc_write(name, h, r); b = open(a, 'rb').read(); open(a, 'wb').write(f(b))
    o = unit('samplecmp', a, fx(tw), 'NONE'); g = re.search(r'(\d+) with values, (\d+) differ', o)
    report('ESRI ASCII read: %-14s (%s) samples as the twin' % (name, {'ctrlz.asc': 'Ctrl-Z at the end', 'bom.asc': 'UTF-8 byte-order mark',
           'mixed.asc': 'xllcenter with yllcorner'}[name]), bool(g) and g.group(2) == '0' and int(g.group(1)) > 1000, o.strip()[:150])
for name, h, r, want in BAD_ASC:
    o = unit('raster', asc_write(name, h, r), 'NONE').strip()
    report('ESRI ASCII refused: %-14s "%s"' % (name, want[:52]), o.startswith('ERROR') and want in o and name in o, o[:160])
for f in ('dxdy.asc', 'dxdy_center.asc', 'nan.asc') + tuple(b[0] for b in BAD_ASC) + tuple(b[0] for b in OK_ASC):
    if os.path.exists(os.path.join(W, f)):
        os.remove(os.path.join(W, f))

# ---- EPSG longitude/latitude rule
o = unit('epsg', '4647', '4326', '4269', '4617', '6318', '4979', '4978', '32610', '4839', '4087')
want = {'4647': 'not-geographic', '4326': 'geographic', '4269': 'geographic', '4617': 'geographic', '6318': 'geographic', '4979': 'geographic',
        '4978': 'not-geographic', '32610': 'not-geographic', '4839': 'not-geographic', '4087': 'not-geographic'}
got = dict(re.findall(r'EPSG (\d+) (\S+)', o))
report('EPSG: 4647, 4839, 4087 (projected), 4978 (geocentric), 32610 not lon/lat; 4326, 4269, 4617, 6318, 4979 lon/lat', got == want,
       '' if got == want else str(got))

# ---- fuzzing
NF = 100 if QUICK else 1000
o = unit('fuzz', '20261109', str(NF), *[fx(m['file']) for m in M if m['file'].endswith('.tif')])
report('fuzz: %d damaged copies of each fixture and 3000 random decoder inputs, no crash' % NF, o.startswith('FUZZ') and 'no crash' in o, o.strip()[:160])

# ---- Raven runs
if NOLIB:
    print('(--nolib: no Raven runs)')
elif not (tc.MF6LIB and os.path.exists(tc.MF6LIB)):
    tc.skip('Raven runs with GeoTIFF rasters', 'RAVEN_MF6_LIB not set')
else:
    import sz_models
    SKIP_FILES = ('mfsim.lst', 'gwf.lst', 'mfsim.stdout', 'linkage.cache')
    TIMING = re.compile(r'BuildDate|Build date|HRU/grid linkage|Simulation time|time|elapsed|seconds|MODFLOW 6 files|library|Raven.*Version', re.I)

    def model(name, dem='dem.asc', bed=None, rasters=(), inputcrs=None, hru=None, z0=100.0):
        d = os.path.join(W, name)
        if os.path.exists(d):
            shutil.rmtree(d)
        sz_models.make_case(d, nhru=2, hru_w=400.0, width=400.0, cell=100.0, physical=False, days=2, z0=z0)
        for f in rasters:
            shutil.copy(fx(f), os.path.join(d, os.path.basename(f)))
        if hru:   # (its "crs" member names EPSG:32611: dropped under another :InputCRS, so that the raster is what is checked)
            g = json.load(open(fx(hru)))
            if inputcrs != 'EPSG:32611':
                g.pop('crs', None)
            json.dump(g, open(os.path.join(d, 'hru.geojson'), 'w'))
        p = os.path.join(d, 'm.rvg'); t = open(p).read()
        t = t.replace(':LandSurface dem.asc\n', (':LandSurface %s\n' % dem) if dem else '')
        if bed:
            t += ':BedrockSurface %s\n' % bed
        if inputcrs:
            t = ':InputCRS %s\n' % inputcrs + t
        open(p, 'w').write(t)
        os.makedirs(os.path.join(d, 'out'), exist_ok=True)
        r = subprocess.run([tc.RAVEN, 'm', '-o', 'out/'], cwd=d, capture_output=True, text=True, env=tc.ENV, timeout=600)
        e = os.path.join(d, 'out', 'Raven_errors.txt')
        err = open(e, errors='replace').read() if os.path.exists(e) else ''
        return d, 'Successful Simulation' in r.stdout + r.stderr, err

    def outputs_differ(a, b, skip=(), names=()):
        """output files of runs a and b that differ (timing lines and MODFLOW listings excepted; in the .txt files the raster
        file names `names` of the two runs are replaced by one placeholder)"""
        def lines(p):
            L = []
            for l in open(p, errors='replace'):
                if TIMING.search(l):
                    continue
                for n in names:
                    l = l.replace(n, '<raster>')
                L.append(l)
            return L
        diffs = []
        for sub in ('out', os.path.join('out', 'mf6')):
            A, B = os.path.join(a, sub), os.path.join(b, sub)
            for f in sorted(set(os.listdir(A)) | set(os.listdir(B))):
                pa, pb = os.path.join(A, f), os.path.join(B, f)
                if os.path.isdir(pa) or f in SKIP_FILES or f in skip:
                    continue
                if not (os.path.exists(pa) and os.path.exists(pb)):
                    diffs.append(f + ' (missing)'); continue
                if f.endswith('.txt'):
                    if lines(pa) != lines(pb):
                        diffs.append(f)
                elif not filecmp.cmp(pa, pb, shallow=False):
                    diffs.append(f)
        return diffs

    twins = {}

    def twin_run(tw, role='dem', z0=100.0, **kw):
        key = (tw, role, z0, tuple(sorted(kw.items())))
        if key not in twins:
            name = 'twin_%d' % len(twins)
            if role == 'dem':
                twins[key] = model(name, dem=tw, rasters=[tw], z0=z0, **kw)
            else:
                twins[key] = model(name, dem=None, bed=tw, rasters=[tw], z0=z0, **kw)
        return twins[key]

    def compare(label, f, tw, role='dem', z0=100.0, skip=(), want_warn=None, **kw):
        dt, okt, et = twin_run(tw, role, z0, **kw)
        name = 'run_' + re.sub(r'\W', '_', label)
        if role == 'dem':
            d, ok, e = model(name, dem=os.path.basename(f), rasters=[f], z0=z0, **kw)
        else:
            d, ok, e = model(name, dem=None, bed=os.path.basename(f), rasters=[f], z0=z0, **kw)
        diffs = outputs_differ(d, dt, skip, (os.path.basename(f), os.path.basename(tw))) if ok and okt else ['run failed: ' + (re.findall(r'ERROR[^\n]*', e + et) or ['?'])[0][:200]]
        warn_ok = want_warn is None or want_warn in e
        return ok and okt and not diffs and warn_ok, diffs, d

    # every fixture with a twin as the DEM
    n_ok, bad, nrun = 0, [], 0
    for m in M:
        if m['kind'] not in ('matrix', 'nodata', 'point', 'mask', 'bigtile', 'scaled') or not m['twin']:
            continue
        ok, diffs, d = compare(m['file'], m['file'], m['twin'])
        nrun += 1
        if ok:
            n_ok += 1; shutil.rmtree(d)
        else:
            bad.append('%s: %s' % (m['file'], ', '.join(diffs)[:200]))
    report('Raven: %d GeoTIFFs as :LandSurface (all encodings, NODATA, masks, PixelIsPoint, large tiles, scale and offset) = twins' % nrun, n_ok == nrun, '%d of %d byte-identical' % (n_ok, nrun))
    for b in bad[:10]:
        print('      ' + b)
    # as the bedrock (the land from the HRU ELEVATION above the rasters' values)
    n_ok, bad, nrun = 0, [], 0
    for m in M:
        if m['kind'] != 'matrix' or not m['twin'] or m.get('container') != 'BigTIFF' or m.get('layout') != 'tiles':
            continue
        h, v = twin(m['twin']); z0 = math.ceil(max(max(r) for r in v)) + 30.0
        ok, diffs, d = compare('bed_' + m['file'], m['file'], m['twin'], role='bed', z0=z0)
        nrun += 1
        if ok:
            n_ok += 1; shutil.rmtree(d)
        else:
            bad.append('%s: %s' % (m['file'], ', '.join(diffs)[:200]))
    report('Raven: %d GeoTIFFs (tiled BigTIFF) as :BedrockSurface = twins' % nrun, n_ok == nrun and nrun >= 10, '%d of %d byte-identical' % (n_ok, nrun))
    for b in bad[:10]:
        print('      ' + b)
    # rectangular pixels: the run succeeds and every active column gets the DEM's value
    for m in M:
        if m['kind'] == 'nonsquare':
            d, ok, e = model('nonsquare_' + m['file'][:-4], dem=m['file'], rasters=[m['file']])
            top = open(os.path.join(d, 'out', 'mf6', 'gwf.dis')).read() if ok else ''
            good = ok and 'gives no value' not in e and 'TOP' in top
            report('Raven: %s (rectangular pixels) as :LandSurface' % m['file'], good, '' if good else (re.findall(r'ERROR[^\n]*', e) or ['?'])[0][:200])
            if good:
                shutil.rmtree(d)
    # file name extensions .TIFF and .GTiff (any case)
    for ext in ('DEM_INT16.TIFF', 'dem_int16.GTiff'):
        shutil.copy(fx([m['file'] for m in M if m.get('dtype') == 'int16' and m['kind'] == 'matrix'][0]), os.path.join(W, ext))
        ok, diffs, d = compare('ext_' + ext, os.path.join(W, ext), 'twin_int16.asc')
        report('Raven: the extension %s is read as GeoTIFF' % ext.split('.')[1], ok, ', '.join(diffs))
        os.remove(os.path.join(W, ext))
        if ok:
            shutil.rmtree(d)
    # no NODATA tag, -9999 and float32-lowest pixels (away from the model): the same run as the twin, with a warning
    for m in M:
        if m['kind'] in ('fill', 'vertnote', 'chain', 'unitnote'):
            ok, diffs, d = compare(m['kind'], m['file'], m['twin'], skip=('Raven_errors.txt',), want_warn=m['expect'])
            report('Raven: %s = twin, and warns' % m['file'], ok, ', '.join(diffs))
            if ok:
                shutil.rmtree(d)
    # projected rasters (:InputCRS), the HRUs in the same projection
    U = dict(hru='hru_utm11.geojson')
    for label, f, crs, warn in (('EPSG:32611', 'crs_32611_f32.tif', 'EPSG:32611', None), ('TMERC (32611 by its parameters)', 'crs_32611_f32.tif', TM_WGS, None),
                                ('user-defined CRS', 'crs_userdef_f32.tif', 'EPSG:32611', None), ('EPSG:2955 (not built in), TMERC GRS80', 'crs_2955_f32.tif', TM_GRS, 'a projection that is not built in')):
        ok, diffs, d = compare('utm_' + label, f, 'twin_utm11_f32.asc', inputcrs=crs, skip=('Raven_errors.txt',) if warn else (), **U)
        if warn:
            e = open(os.path.join(d, 'out', 'Raven_errors.txt')).read()
            ok = ok and warn in e and f in e
        report('Raven: %s with :InputCRS %s = twin' % (f, label), ok, ', '.join(diffs))
        if ok:
            shutil.rmtree(d)
    a, oka, _ = model('crs_epsg', dem='crs_32611_f32.tif', rasters=['crs_32611_f32.tif'], inputcrs='EPSG:32611', **U)
    b, okb, _ = model('crs_tmerc', dem='crs_32611_f32.tif', rasters=['crs_32611_f32.tif'], inputcrs=TM_WGS, **U)
    diffs = outputs_differ(a, b) if oka and okb else ['run failed']
    report('Raven: :InputCRS EPSG:32611 and the same projection by its parameters give identical runs', not diffs, ', '.join(diffs))
    shutil.rmtree(a); shutil.rmtree(b)
    for label, f, crs, hru, part in (('projected raster, no :InputCRS', 'crs_32611_f32.tif', None, None, 'is in EPSG:32611 (a projection'),
                                     ('lon/lat raster (EPSG:4269) with :InputCRS', 'crs_4269_f32.tif', 'EPSG:32611', 'hru_utm11.geojson', 'is in longitude/latitude (EPSG:4269'),
                                     ('EPSG:32611 raster with :InputCRS EPSG:32610', 'crs_32611_f32.tif', 'EPSG:32610', 'hru_utm11.geojson', 'but :InputCRS is EPSG:32610'),
                                     ('EPSG:2955 raster with :InputCRS EPSG:32611', 'crs_2955_f32.tif', 'EPSG:32611', 'hru_utm11.geojson', 'is in EPSG:2955'),
                                     ('raster without GeoKeys in lon/lat with :InputCRS', 'crs_none_f32.tif', 'EPSG:32611', 'hru_utm11.geojson', 'looks like longitude/latitude'),
                                     ('JPEG-compressed raster', 'stop_jpeg.tif', None, None, 'compression JPEG (7) is not supported'),
                                     ('truncated raster', 'stop_truncated_data.tif', None, None, 'truncated or corrupt file'),
                                     ('three-band raster', 'stop_rgb.tif', None, None, '3 samples (bands) per pixel'),
                                     ('rotated raster', 'stop_rotated.tif', None, None, 'rotates or shears'),
                                     ('FillOrder 2', 'stop_fillorder2.tif', None, None, 'FillOrder 2'),
                                     ('elevations in US survey feet', 'stop_vunits_usft.tif', None, None, 'elevations are in US survey foot'),
                                     ('NAVD88 heights in US survey feet (EPSG:4269+6360)', 'stop_navd88ft.tif', None, None, 'vertical coordinate system EPSG:6360'),
                                     ('Bern prime meridian (EPSG:4801)', 'stop_bern_pm.tif', None, None, 'prime meridian of Bern')):
        d, ok, e = model('stop_' + re.sub(r'\W', '_', label), dem=f, rasters=[f], inputcrs=crs, hru=hru)
        good = (not ok) and part in e and f in e
        report('Raven stops: %s' % label, good, '' if good else (re.findall(r'ERROR[^\n]*', e) or ['no error'])[0][:200])
        if good:
            shutil.rmtree(d)

    # rasters that cover no active column, or part of them
    def shifted(name, src, dx=0.0, cut_cols=None, all_nodata=False):
        L = open(fx(src)).read().split('\n'); out = []
        for i, l in enumerate(L):
            if l.lower().startswith('xllcorner') and dx:
                l = 'xllcorner %r' % (float(l.split()[1]) + dx)
            if l.lower().startswith('ncols') and cut_cols:
                l = 'ncols %d' % cut_cols
            if i >= 6 and l.strip() and cut_cols:
                l = ' '.join(l.split()[:cut_cols])
            if i >= 6 and l.strip() and all_nodata:
                l = ' '.join('-9999' for _ in l.split())
            out.append(l)
        p = os.path.join(W, name); open(p, 'w').write('\n'.join(out)); return p
    cases = [('GeoTIFF DEM 1 degree east', dict(dem='cover_east_f32.tif', rasters=['cover_east_f32.tif']), ':LandSurface raster cover_east_f32.tif gives no value for any of the 32 active columns'),
             ('ESRI ASCII DEM 1 degree east', dict(dem='dem_east.asc', rasters=[shifted('dem_east.asc', 'twin_float32.asc', 1.0)]), ':LandSurface raster dem_east.asc gives no value for any of the 32'),
             ('ESRI ASCII bedrock 1 degree east', dict(bed='bed_east.asc', rasters=[shifted('bed_east.asc', 'twin_float32.asc', 1.0)], z0=200.0), ':BedrockSurface raster bed_east.asc gives no value for any of the 32'),
             ('ESRI ASCII DEM with only NODATA', dict(dem='dem_nodata.asc', rasters=[shifted('dem_nodata.asc', 'twin_float32.asc', all_nodata=True)]), 'gives no value for any of the 32')]
    for label, kw, part in cases:
        d, ok, e = model('cover_' + re.sub(r'\W', '_', label), **kw)
        good = (not ok) and part in e and 'the raster covers x' in e and "the model's active columns lie at x" in e
        report('Raven stops: %s (raster and model extents in the message)' % label, good, '' if good else (re.findall(r'ERROR[^\n]*', e) or ['no error'])[0][:240])
        if good:
            shutil.rmtree(d)
    for f in ('dem_east.asc', 'bed_east.asc', 'dem_nodata.asc'):
        os.remove(os.path.join(W, f))
    p = shifted('dem_west.asc', 'twin_float32.asc', cut_cols=18)
    d, ok, e = model('cover_part', dem='dem_west.asc', rasters=[p])
    m_ = re.search(r':LandSurface raster dem_west.asc gives no value for (\d+) of the 32 active columns', e)
    report('Raven warns: a DEM covering the western half of the model (count of the columns without a value)', ok and m_ is not None and 0 < int(m_.group(1)) < 32,
           m_.group(0) if m_ else 'no warning')
    os.remove(p)
    if ok:
        shutil.rmtree(d)
    for key, (d, ok, e) in twins.items():
        if os.path.exists(d):
            shutil.rmtree(d)

print('geotiff checks: ALL PASSED' if fails == 0 else 'geotiff checks: %d FAILED' % fails)
sys.exit(1 if fails else 0)
