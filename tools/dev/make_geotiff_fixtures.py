#!/usr/bin/env python3
"""Writes the GeoTIFF test fixtures of tests/geotiff/fixtures (GeoTIFF files, their ESRI ASCII twins and manifest.json).

    python3 make_geotiff_fixtures.py [<extra repository>/tests/geotiff/fixtures]

Development tool only: the files are written once by two independent TIFF writers, GDAL (through rasterio) and tifffile
(with imagecodecs), and committed; the tests read them with nothing but Raven and the test harness.
    pip install rasterio tifffile imagecodecs pyproj
Every file is read back with tifffile and compared with the values written before it is kept.

Fixtures (37 x 29 pixels of 1/1024 degree around the synthetic test models of tests/soilzone/sz_models.py, 55 N 120 W):
  matrix_*   every supported compression (none, LZW, DEFLATE 8, DEFLATE 32946, PackBits) x predictor (1; 2 and 3 with
             LZW and DEFLATE, 3 for floats only) x sample type (8 to 64 bit unsigned and signed integers, 32 and 64 bit
             floats) x byte order; strips (8 rows, a shorter last strip) or tiles (16 x 16, partial edge tiles) and classic
             TIFF or BigTIFF in turn, so that each layout appears with every compression, predictor and byte order; written
             by GDAL and tifffile in turn (DEFLATE 32946 by tifffile, which GDAL does not write)
  range_*    integer extremes (minimum, maximum, -1, 0, random values over the type's range) for the decoders' carries
  nodata_*   GDAL_NODATA: a 16-bit value, the float32 lowest value, NaN
  point_*    PixelIsPoint (tie point at the centre of the upper-left pixel), by GDAL and by tifffile (ModelTransformation)
  mask_*     a GDAL internal mask (1 bit) and a tifffile 8-bit mask page; the twin has NODATA at the masked pixels
  bigtile_*  tiles of 2048 x 2048 pixels on the small raster
  chain_*    a damaged pointer to the next image directory after a good raster (read without its mask, with a warning)
  vert_*     a user-defined vertical coordinate system (read as metres, with a warning)
  fill_*     no GDAL_NODATA but -9999 and float32-lowest pixels (read as values, with a warning)
  nonsquare_* rectangular pixels (twice as wide, twice as high), with the values of twin_float64.asc
  crs_*      EPSG:4326 and 4269 (geographic), 32611 (UTM 11N, built into Raven), 2955 (NAD83(CSRS) / UTM 11N, not built in),
             a user-defined projection (32767) and no GeoKeys at all; utm11 rasters are on a 64 m grid
  cover_*    a raster 1 degree east of the model (covers no model cell)
  stop_*     files Raven must refuse with a message: JPEG, ZSTD, three bands (RGB), two bands, palette, 1-bit, 12-bit,
             16-bit float, complex, rotated (ModelTransformation), south-up, control points, no georeferencing, geocentric,
             FillOrder 2, units other than metres or degrees (projection in feet, elevations in US feet, geographic
             linear units in feet, angles in grads), a vertical system in US survey feet (EPSG:4269+6360), prime
             meridians other than Greenwich (EPSG:4801, the prime-meridian key), a code in degrees-minutes-seconds,
             blocks covering more than 200 million pixels,
             truncated and corrupt files, a raster above the pixel limit
Each fixture that Raven reads has an ESRI ASCII twin holding the same values (written as the shortest decimal that reads
back as the same double), so the twin must give identical cell elevations and byte-identical outputs.
hru_utm11.geojson: the HRUs of the test model (make_case(nhru=2, hru_w=400, width=400, cell=100)) in EPSG:32611.
"""
import os, sys, json, math, shutil, tempfile, struct
import numpy as np
import rasterio
from rasterio.transform import from_origin, Affine
from rasterio.crs import CRS
import tifffile
import pyproj

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'tests', 'geotiff', 'fixtures')
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tests', 'soilzone'))
import sz_models   # noqa: E402

NC, NR = 37, 29
CS = 1.0 / 1024.0
XLL = sz_models.LON0 - 18 * CS
YTOP = sz_models.LAT0 + 15 * CS
YLL = YTOP - NR * CS
UCS = 64.0                       # UTM grid
UNC, UNR = 40, 30

os.makedirs(OUT, exist_ok=True)
for f in os.listdir(OUT):
    if f.endswith(('.tif', '.asc', '.json', '.geojson', '.tiff', '.TIF')):
        os.remove(os.path.join(OUT, f))
manifest = []

cc, rr = np.meshgrid(np.arange(NC), np.arange(NR))
Z = 120.0 + 0.6 * cc - 0.4 * rr + 3.0 * np.sin(cc / 3.0) * np.cos(rr / 4.0)    # smooth land, about 100-150 m
DATA = {
    'uint8': np.round(Z).astype('uint8'),
    'int8': (np.round(Z) - 60).astype('int8'),
    'uint16': (np.round(Z) + 1000).astype('uint16'),
    'int16': (np.round(Z) - 300).astype('int16'),
    'uint32': (np.round(Z) + 2000).astype('uint32'),
    'int32': (np.round(Z) - 500).astype('int32'),
    'uint64': (np.round(Z) + 3000).astype('uint64'),
    'int64': (np.round(Z) - 1000).astype('int64'),
    'float32': (Z + 0.25 * np.sin(cc * rr / 7.0)).astype('float32'),
    'float64': (Z + 1e-3 * np.cos(cc * 1.7 + rr * 0.3) + math.pi * 1e-7),
}


def num(v):
    """the shortest decimal that reads back as the same double"""
    v = float(v)
    return repr(v) if v != int(v) or abs(v) >= 1e15 else str(int(v))


def write_asc(name, a, xll=XLL, yll=YLL, cs=CS, nodata=-9999.0):
    with open(os.path.join(OUT, name), 'w') as f:
        f.write('ncols %d\nnrows %d\nxllcorner %s\nyllcorner %s\ncellsize %s\nNODATA_value %s\n' % (a.shape[1], a.shape[0], repr(float(xll)), repr(float(yll)), repr(float(cs)), num(nodata)))
        for r in range(a.shape[0]):
            f.write(' '.join(num(v) for v in a[r]) + '\n')
    return name


def check(path, a, comp=None, pred=None, be=None, big=None, tiled=None):
    """reads a written file back with tifffile: values and layout as intended"""
    t = tifffile.TiffFile(path); p = t.pages[0]
    b = p.asarray()
    same = np.array_equal(b, a, equal_nan=True) if b.dtype.kind == 'f' else np.array_equal(b, a)
    assert same and b.dtype == a.dtype, (path, b.dtype, a.dtype)
    if comp is not None: assert int(p.compression) == comp, (path, int(p.compression), comp)
    if pred is not None: assert int(p.predictor) == pred, (path, int(p.predictor), pred)
    if be is not None: assert (t.byteorder == '>') == be, (path, t.byteorder)
    if big is not None: assert t.is_bigtiff == big, (path, t.is_bigtiff)
    if tiled is not None: assert p.is_tiled == tiled, (path, p.is_tiled)
    t.close()


GDAL_COMP = {1: 'none', 5: 'lzw', 8: 'deflate', 32773: 'packbits'}
TF_COMP = {1: None, 5: 'lzw', 8: 'zlib', 32946: 'deflate', 32773: 'packbits'}
TF_PRED = {1: None, 2: 'horizontal', 3: 'floatingpoint'}


def gdal_write(name, a, comp=1, pred=1, be=False, big=False, tiled=False, crs=4326, transform=None, nodata=None, point=False, **extra):
    opts = dict(driver='GTiff', width=a.shape[1], height=a.shape[0], count=1 if a.ndim == 2 else a.shape[0], dtype=a.dtype,
                transform=transform or from_origin(XLL, YTOP, CS, CS), compress=GDAL_COMP.get(comp, comp),
                bigtiff='yes' if big else 'no', endianness='big' if be else 'little')
    if crs is not None:
        opts['crs'] = CRS.from_epsg(crs) if isinstance(crs, int) else CRS.from_string(crs)
    if pred != 1: opts['predictor'] = pred
    if tiled: opts.update(tiled=True, blockxsize=16, blockysize=16)
    else: opts['blockysize'] = 8
    if nodata is not None: opts['nodata'] = nodata
    opts.update(extra)
    p = os.path.join(OUT, name)
    with rasterio.open(p, 'w', **opts) as d:
        if point: d.update_tags(AREA_OR_POINT='Point')
        d.write(a if a.ndim == 3 else a, None if a.ndim == 3 else 1)
    return name


def geokeys(model=2, code=4326, raster=1, extra=()):
    keys = [(1024, 0, 1, model), (1025, 0, 1, raster)]
    if code is not None:
        keys.append((2048 if model == 2 else 3072, 0, 1, code))
    keys += [(k, 0, 1, v) for k, v in extra]
    keys.sort()
    v = [1, 1, 0, len(keys)]
    for k in keys: v += list(k)
    return v


def tf_write(name, a, comp=1, pred=1, be=False, big=False, tiled=False, keys='ll', nodata=None, scale=None, tie=None, mt=None, extra=()):
    tags = list(extra)
    if mt is not None:
        tags.append((34264, 'd', 16, tuple(mt), True))
    else:
        if scale is not False:
            tags.append((33550, 'd', 3, tuple(scale or (CS, CS, 0.0)), True))
        tags.append((33922, 'd', len(tie) if tie else 6, tuple(tie or (0.0, 0.0, 0.0, XLL, YTOP, 0.0)), True))
    if keys == 'll': keys = geokeys()
    if keys is not None: tags.append((34735, 'H', len(keys), tuple(keys), True))
    if nodata is not None: tags.append((42113, 's', 0, nodata, True))
    kw = dict(byteorder='>' if be else '<', bigtiff=big, photometric='minisblack', extratags=tags, metadata=None)
    if TF_COMP[comp]: kw['compression'] = TF_COMP[comp]
    if TF_PRED[pred]: kw['predictor'] = TF_PRED[pred]
    if tiled: kw['tile'] = (16, 16)
    else: kw['rowsperstrip'] = 8
    tifffile.imwrite(os.path.join(OUT, name), a, **kw)
    return name


def set_compression(name, comp):
    p = os.path.join(OUT, name); t = tifffile.TiffFile(p); tg = t.pages[0].tags[259]; o = tg.valueoffset; bo = t.byteorder; t.close()
    b = bytearray(open(p, 'rb').read()); b[o:o + 2] = struct.pack(bo + 'H', comp); open(p, 'wb').write(b)


def add(name, kind, twin=None, expect='ok', **info):
    e = dict(file=name, kind=kind, twin=twin, expect=expect); e.update(info); manifest.append(e)


# ---- twins of the matrix data
TWIN = {dt: write_asc('twin_%s.asc' % dt, a) for dt, a in DATA.items()}

# ---- matrix: compression x predictor x sample type x byte order; layout and container in turn; writer in turn
i = 0
for comp in (1, 5, 8, 32946, 32773):
    for be in (False, True):
        for pred in ((1, 2, 3) if comp in (5, 8, 32946) else (1,)):
            for dt, a in DATA.items():
                if pred == 3 and a.dtype.kind != 'f':
                    continue
                tiled, big = (i % 4) in (1, 3), (i % 4) in (2, 3)
                writer = 'tifffile' if (comp == 32946 or (i // 4) % 2 == 1) else 'gdal'
                if pred == 2 and a.dtype.kind == 'f':
                    writer = 'gdal'            # (tifffile does not write the horizontal predictor for floats)
                name = 'matrix_%s_c%d_p%d_%s_%s_%s.tif' % (dt, comp, pred, 'be' if be else 'le', 'tile' if tiled else 'strip', 'big' if big else 'classic')
                if writer == 'gdal' and comp == 32946:     # GDAL writes DEFLATE as 8: the same zlib data, the tag set to 32946
                    gdal_write(name, a, 8, pred, be, big, tiled); set_compression(name, 32946); writer = 'gdal (tag 259 set to 32946)'
                elif writer == 'gdal':
                    gdal_write(name, a, comp, pred, be, big, tiled)
                else:
                    tf_write(name, a, comp, pred, be, big, tiled)
                check(os.path.join(OUT, name), a, comp, pred if comp in (5, 8, 32946) else None, be, big, tiled)
                add(name, 'matrix', TWIN[dt], dtype=dt, compression=comp, predictor=pred, byteorder='big' if be else 'little',
                    layout='tiles' if tiled else 'strips', container='BigTIFF' if big else 'classic', writer=writer)
                i += 1

# ---- integer extremes (unit tests only: not elevations)
rng = np.random.default_rng(11)
for k, dt in enumerate(('uint8', 'int8', 'uint16', 'int16', 'uint32', 'int32', 'uint64', 'int64')):
    info = np.iinfo(dt)
    a = rng.integers(info.min, info.max, size=(NR, NC), dtype=dt, endpoint=True)
    a.flat[:6] = np.array([info.min, info.max, 0, 1 if info.min == 0 else -1, info.max - 1, info.min + 1], dtype=dt)
    tw = write_asc('twin_range_%s.asc' % dt, a)
    for comp, pred, be, tiled, big, wr in ((5, 2, True, True, True, 'gdal'), (8, 2, False, False, False, 'tifffile'), (32946, 2, True, False, True, 'tifffile'), (1, 1, True, True, False, 'gdal')):
        name = 'range_%s_c%d_p%d_%s_%s_%s.tif' % (dt, comp, pred, 'be' if be else 'le', 'tile' if tiled else 'strip', 'big' if big else 'classic')
        (gdal_write if wr == 'gdal' else tf_write)(name, a, comp, pred, be, big, tiled)
        check(os.path.join(OUT, name), a, comp, None, be, big, tiled)
        add(name, 'range', tw, dtype=dt, compression=comp, predictor=pred, writer=wr)

# ---- NODATA
a = DATA['int16'].copy(); a[12:16, 16:20] = -32768; a[0, :] = -32768
add(gdal_write('nodata_int16_lzw.tif', a, 5, 2, nodata=-32768), 'nodata', write_asc('twin_nodata_int16.asc', a, nodata=-32768), nodata='-32768')
f = DATA['float32'].copy(); lo = float(np.finfo('float32').min); f[13:15, 15:21] = lo; f[5, 5] = lo
add(gdal_write('nodata_f32_lowest_deflate.tif', f, 8, 3, nodata=lo), 'nodata', write_asc('twin_nodata_f32_lowest.asc', f, nodata=lo), nodata='float32 lowest')
g = DATA['float32'].copy(); g[13:15, 15:21] = np.nan; g[20, 30] = np.nan
add(tf_write('nodata_f32_nan_be_tile.tif', g, 5, 3, True, True, True, nodata='nan'), 'nodata',
    write_asc('twin_nodata_f32_nan.asc', np.where(np.isnan(g), -9999.0, g.astype('float64'))), nodata='nan')
h = DATA['float64'].copy(); h[14, 18] = np.nan     # NaN without a NODATA tag: never valid
add(tf_write('nodata_f64_nan_untagged.tif', h, 8, 3), 'nodata', write_asc('twin_nodata_f64_untagged.asc', np.where(np.isnan(h), -9999.0, h)), nodata='none (NaN pixel)')

# ---- PixelIsPoint (the same corner as the PixelIsArea files)
add(gdal_write('point_f32_gdal.tif', DATA['float32'], 5, 3, point=True), 'point', TWIN['float32'], writer='gdal')
mt = [CS, 0, 0, XLL + 0.5 * CS, 0, -CS, 0, YTOP - 0.5 * CS, 0, 0, 0, 0, 0, 0, 0, 1]
add(tf_write('point_i16_mt_tifffile.tif', DATA['int16'], 8, 2, True, False, True, keys=geokeys(raster=2), mt=mt), 'point', TWIN['int16'], writer='tifffile')
add(tf_write('area_u16_mt_tifffile.tif', DATA['uint16'], 32773, 1, False, True, False, mt=[CS, 0, 0, XLL, 0, -CS, 0, YTOP, 0, 0, 0, 0, 0, 0, 0, 1]), 'matrix', TWIN['uint16'], writer='tifffile')

# ---- rectangular pixels (the values of twin_float64.asc on pixels twice as wide, or twice as high)
add(gdal_write('nonsquare_f64_wide.tif', DATA['float64'], 8, 3, transform=from_origin(XLL, YTOP, 2 * CS, CS)), 'nonsquare', None,
    values='twin_float64.asc', xll=XLL, yll=YTOP - NR * CS, dx=2 * CS, dy=CS, writer='gdal')
add(tf_write('nonsquare_f64_tall_mt.tif', DATA['float64'], 5, 3, True, True, True, mt=[CS, 0, 0, XLL, 0, -2 * CS, 0, YTOP, 0, 0, 0, 0, 0, 0, 0, 1]), 'nonsquare', None,
    values='twin_float64.asc', xll=XLL, yll=YTOP - NR * 2 * CS, dx=CS, dy=2 * CS, writer='tifffile')

# ---- a GDAL internal mask (1 bit, NewSubfileType 4) and a tifffile 8-bit mask page: masked pixels hold 0 and are no data
MASK = np.ones((NR, NC), bool); MASK[12:16, 15:21] = False; MASK[0, :] = False; MASK[20:23, 2:5] = False
mv = np.where(MASK, DATA['float32'], 0).astype('float32')
mtw = write_asc('twin_mask_f32.asc', np.where(MASK, mv.astype('float64'), -9999.0))
with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
    p = gdal_write('mask_f32_gdal.tif', mv, 5, 3)
    with rasterio.open(os.path.join(OUT, p), 'r+') as ds:
        ds.write_mask(np.where(MASK, 255, 0).astype('uint8'))
tt = tifffile.TiffFile(os.path.join(OUT, p)); assert len(tt.pages) == 2 and tt.pages[1].subfiletype == 4 and tt.pages[1].bitspersample == 1; tt.close()
add(p, 'mask', mtw, writer='gdal', mask='1 bit')
GEO = [(33550, 'd', 3, (CS, CS, 0.0), True), (33922, 'd', 6, (0.0, 0.0, 0.0, XLL, YTOP, 0.0), True), (34735, 'H', len(geokeys()), tuple(geokeys()), True)]
p = os.path.join(OUT, 'mask_f32_1bit_tiled_tifffile.tif')         # tifffile: a bilevel mask page in 16 x 16 tiles, PackBits
with tifffile.TiffWriter(p, byteorder='>', bigtiff=True) as tw:
    tw.write(mv, photometric='minisblack', compression='zlib', predictor='floatingpoint', tile=(16, 16), metadata=None, extratags=GEO)
    tw.write(MASK, photometric='mask', subfiletype=4, compression='packbits', tile=(16, 16), metadata=None)
tt = tifffile.TiffFile(p); assert tt.pages[1].subfiletype == 4 and tt.pages[1].bitspersample == 1 and tt.pages[1].is_tiled; tt.close()
add('mask_f32_1bit_tiled_tifffile.tif', 'mask', mtw, writer='tifffile', mask='1 bit, tiles')
p = os.path.join(OUT, 'mask_f32_8bit_tifffile.tif')               # an 8-bit mask page (0/255), LZW with predictor 2
with tifffile.TiffWriter(p, byteorder='<', bigtiff=False) as tw:
    tw.write(mv, photometric='minisblack', compression='zlib', rowsperstrip=8, metadata=None, extratags=GEO)
    tw.write(np.where(MASK, 255, 0).astype('uint8'), photometric='minisblack', compression='lzw', predictor='horizontal', rowsperstrip=8, metadata=None,
             extratags=[(254, 'I', 1, 4, True)])
tt = tifffile.TiffFile(p); assert tt.pages[1].tags[254].value == 4 and tt.pages[1].bitspersample == 8; tt.close()
add('mask_f32_8bit_tifffile.tif', 'mask', mtw, writer='tifffile', mask='8 bit')

# a mask after 100 reduced-resolution pages (tifffile); a damaged pointer to the next directory after a good raster (the
# raster is read without its mask, with a warning: the twin holds the stored values, 0 at the masked pixels)
p = os.path.join(OUT, 'mask_f32_after_100_pages.tif')
with tifffile.TiffWriter(p) as tw:
    tw.write(mv, photometric='minisblack', compression='zlib', rowsperstrip=8, metadata=None, extratags=GEO)
    for k in range(100):
        tw.write(np.zeros((2, 2), 'float32'), photometric='minisblack', subfiletype=1, metadata=None)
    tw.write(MASK, photometric='mask', subfiletype=4, compression='packbits', rowsperstrip=8, metadata=None)
tt = tifffile.TiffFile(p); assert len(tt.pages) == 102 and tt.pages[101].subfiletype == 4; tt.close()
add('mask_f32_after_100_pages.tif', 'mask', mtw, writer='tifffile', mask='1 bit, after 100 pages')
b = bytearray(open(os.path.join(OUT, 'mask_f32_gdal.tif'), 'rb').read())
o = struct.unpack('<I', b[4:8])[0]; ne = struct.unpack('<H', b[o:o + 2])[0]; b[o + 2 + 12 * ne:o + 6 + 12 * ne] = struct.pack('<I', len(b) + 1000)
open(os.path.join(OUT, 'chain_damaged_f32.tif'), 'wb').write(b)
add('chain_damaged_f32.tif', 'chain', write_asc('twin_mask_values_f32.asc', mv.astype('float64'), nodata=-12345.0), expect='chain of image directories is damaged after the raster')

# ---- tiles of 2048 x 2048 on the 37 x 29 raster
add(gdal_write('bigtile_int16_deflate.tif', DATA['int16'], 8, 2, blockxsize=2048, blockysize=2048, tiled=True), 'bigtile', TWIN['int16'], writer='gdal')
tt = tifffile.TiffFile(os.path.join(OUT, 'bigtile_int16_deflate.tif')); assert tt.pages[0].tilewidth == 2048; tt.close()

# ---- no GDAL_NODATA, but values that usually mark no data (corner pixels away from the test model): a warning
fz = DATA['float32'].copy(); fz[0:2, 0:3] = -9999.0; fz[28, 36] = np.finfo('float32').min
add(gdal_write('fill_f32_nonodata.tif', fz, 5, 3), 'fill', write_asc('twin_fill_f32.asc', fz.astype('float64'), nodata=-12345.0), expect='6 pixels of -9999, 1 pixel of -3.40282346639e+38')

# ---- CRS
add(gdal_write('crs_4326_egm96_f32.tif', DATA['float32'], 5, 3, crs='EPSG:4326+5773'), 'crs', TWIN['float32'], epsg=4326)
add(tf_write('vert_userdef_f32.tif', DATA['float32'], 8, 3, keys=geokeys(extra=[(4096, 32767)])), 'vertnote', TWIN['float32'],
    expect='has a vertical coordinate system (user-defined) whose unit Raven does not know; its elevations are read as metres')
add(gdal_write('crs_4269_f32.tif', DATA['float32'], 5, 3, crs=4269), 'crs', TWIN['float32'], epsg=4269)
add(tf_write('crs_none_f32.tif', DATA['float32'], 8, 3, keys=None), 'crs', TWIN['float32'], epsg=0)
utm = pyproj.Transformer.from_crs('EPSG:4326', 'EPSG:32611', always_xy=True)
x0, y0 = utm.transform(sz_models.LON0, sz_models.LAT0)
UXLL, UYTOP = math.floor(x0 / UCS) * UCS - 20 * UCS, math.floor(y0 / UCS) * UCS + 15 * UCS
uc, ur = np.meshgrid(np.arange(UNC), np.arange(UNR))
U = (200.0 + 0.4 * uc - 0.3 * ur + 2.0 * np.sin(uc / 4.0)).astype('float32')
utw = write_asc('twin_utm11_f32.asc', U, UXLL, UYTOP - UNR * UCS, UCS)
ut = from_origin(UXLL, UYTOP, UCS, UCS)
add(gdal_write('crs_32611_f32.tif', U, 8, 3, crs=32611, transform=ut), 'crs', utw, epsg=32611)
add(gdal_write('crs_2955_f32.tif', U, 5, 2, crs=2955, transform=ut), 'crs', utw, epsg=2955)
add(gdal_write('crs_userdef_f32.tif', U, 5, 1, crs='+proj=tmerc +lat_0=0 +lon_0=-119.5 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m', transform=ut), 'crs', utw, epsg=32767)
d = tempfile.mkdtemp()
sz_models.make_case(d, nhru=2, hru_w=400.0, width=400.0, cell=100.0, physical=False, days=2)
g = json.load(open(os.path.join(d, 'hru.geojson')))
for ft in g['features']:
    ft['geometry']['coordinates'] = [[list(utm.transform(*p)) for p in r] for r in ft['geometry']['coordinates']]
g['crs'] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::32611"}}
json.dump(g, open(os.path.join(OUT, 'hru_utm11.geojson'), 'w'))
shutil.rmtree(d)

# ---- a raster 1 degree east of the model
add(gdal_write('cover_east_f32.tif', DATA['float32'], 5, 3, transform=from_origin(XLL + 1.0, YTOP, CS, CS)), 'cover', None)

# ---- files Raven must refuse
def stop(name, expect, **info):
    add(name, 'stop', None, expect, **info)
u8 = DATA['uint8']
stop(gdal_write('stop_jpeg.tif', u8, 'jpeg'), 'compression JPEG (7) is not supported')
stop(gdal_write('stop_zstd.tif', DATA['float32'], 'zstd'), 'compression ZSTD (50000) is not supported')
stop(gdal_write('stop_rgb.tif', np.stack([u8, u8, u8]), 5, photometric='RGB'), '3 samples (bands) per pixel')
stop(gdal_write('stop_2band.tif', np.stack([DATA['int16'], DATA['int16']]), 8), '2 samples (bands) per pixel')
p = gdal_write('stop_palette.tif', u8, 5, photometric='palette')
with rasterio.open(os.path.join(OUT, p), 'r+') as ds:
    ds.write_colormap(1, {k: (k, 255 - k, 0, 255) for k in range(256)})
assert int(tifffile.TiffFile(os.path.join(OUT, p)).pages[0].photometric) == 3
stop(p, 'palette colour')
stop(gdal_write('stop_1bit.tif', (u8 > 120).astype('uint8'), 1, nbits=1), 'samples of 1 bits')
stop(gdal_write('stop_12bit.tif', DATA['uint16'], 5, nbits=12), 'samples of 12 bits')
stop(tf_write('stop_float16.tif', DATA['float32'].astype('float16'), 8), 'samples of 16 bits, floating-point')
stop(gdal_write('stop_complex.tif', DATA['float32'].astype('complex64'), 1), 'complex floating-point')
stop(gdal_write('stop_rotated.tif', DATA['float32'], 5, transform=Affine(CS * 0.98, CS * 0.2, XLL, CS * 0.2, -CS * 0.98, YTOP)), 'rotates or shears')
stop(tf_write('stop_southup.tif', DATA['float32'], 5, mt=[CS, 0, 0, XLL, 0, CS, 0, YLL, 0, 0, 0, 0, 0, 0, 0, 1]), 'not north-up')
stop(tf_write('stop_gcps.tif', DATA['float32'], 1, tie=(0, 0, 0, XLL, YTOP, 0, NC, NR, 0, XLL + NC * CS, YLL, 0), scale=False), 'control points')
stop(tifffile.imwrite(os.path.join(OUT, 'stop_nogeo.tif'), DATA['float32'], photometric='minisblack', metadata=None) or 'stop_nogeo.tif', 'no georeferencing')
stop(tf_write('stop_geocentric.tif', DATA['float32'], 1, keys=geokeys(model=3, code=None)), 'geocentric')
stop(tf_write('stop_units_foot.tif', U, 5, keys=geokeys(model=1, code=32767, extra=[(3076, 9002)]), scale=(UCS, UCS, 0.0), tie=(0, 0, 0, UXLL, UYTOP, 0)), 'linear units of its projection (ProjLinearUnitsGeoKey) are foot')
stop(tf_write('stop_vunits_usft.tif', DATA['float32'], 8, keys=geokeys(extra=[(4099, 9003)])), 'elevations are in US survey foot')
stop(tf_write('stop_geoglin_foot.tif', DATA['float32'], 8, keys=geokeys(extra=[(2052, 9002)])), 'GeogLinearUnitsGeoKey) are foot')
stop(tf_write('stop_angular_grad.tif', DATA['float32'], 8, keys=geokeys(code=32767, extra=[(2054, 9105)])), 'angular units (GeogAngularUnitsGeoKey) are grad')
def raw_fillorder2(name, a):
    """a classic little-endian float32 TIFF in one uncompressed strip with FillOrder 2 (the bits of every byte reversed, as
    libtiff reads them back); tifffile does not write tag 266, so the file is put together here"""
    data = bytes(int('{:08b}'.format(x)[::-1], 2) for x in a.astype('<f4').tobytes())
    h, w = a.shape; keys = geokeys()
    tags = [(256, 3, [w]), (257, 3, [h]), (258, 3, [32]), (259, 3, [1]), (262, 3, [1]), (266, 3, [2]), (273, 4, [0]), (277, 3, [1]),
            (278, 3, [h]), (279, 4, [len(data)]), (339, 3, [3]), (33550, 12, [CS, CS, 0.0]), (33922, 12, [0.0, 0.0, 0.0, XLL, YTOP, 0.0]), (34735, 3, keys)]
    fmt = {3: 'H', 4: 'I', 12: 'd'}; size = {3: 2, 4: 4, 12: 8}
    ifd = 8; extra = ifd + 2 + 12 * len(tags) + 4; blobs = b''; ents = []
    for tag, typ, vals in tags:
        raw = struct.pack('<%d%s' % (len(vals), fmt[typ]), *vals)
        ents.append([tag, typ, len(vals), raw, None])
    for e in ents:
        if len(e[3]) > 4:
            e[4] = extra + len(blobs); blobs += e[3] + (b'\0' if len(e[3]) % 2 else b'')
    dataoff = extra + len(blobs)
    out = b'II*\0' + struct.pack('<I', ifd) + struct.pack('<H', len(ents))
    for tag, typ, n, raw, off in ents:
        if tag == 273: raw = struct.pack('<I', dataoff)
        out += struct.pack('<HHI', tag, typ, n) + (struct.pack('<I', off) if off is not None else raw.ljust(4, b'\0'))
    out += struct.pack('<I', 0) + blobs + data
    open(os.path.join(OUT, name), 'wb').write(out)
    b = tifffile.TiffFile(os.path.join(OUT, name)).pages[0]
    assert int(b.tags[266].value) == 2 and b.shape == a.shape
    return name
stop(raw_fillorder2('stop_fillorder2.tif', DATA['float32']), 'FillOrder 2')
stop(gdal_write('stop_navd88ft.tif', DATA['float32'], 5, 3, crs='EPSG:4269+6360'), 'elevations are in US survey foot (vertical coordinate system EPSG:6360)')
stop(gdal_write('stop_bern_pm.tif', DATA['float32'], 5, 3, crs=4801), 'prime meridian of Bern')
stop(tf_write('stop_paris_pm_key.tif', DATA['float32'], 8, keys=geokeys(code=32767, extra=[(2051, 8903)])), 'GeogPrimeMeridianGeoKey 8903')
stop(tf_write('stop_dms_4035.tif', DATA['float32'], 8, keys=geokeys(code=4035)), 'angles are in degree minute second hemisphere')
# a decoding area above the bound: 5 tiles of 7056 x 7056 on a 35280 x 1 raster (the size tags of a small tiled file changed)
src = [m['file'] for m in manifest if m['kind'] == 'matrix' and m.get('layout') == 'tiles' and m.get('container') == 'classic' and m.get('byteorder') == 'little'][0]
b = bytearray(open(os.path.join(OUT, src), 'rb').read()); t2 = tifffile.TiffFile(os.path.join(OUT, src)); pg = t2.pages[0]
for tag, val in ((256, 35280), (257, 1), (322, 7056), (323, 7056)):
    tg = pg.tags[tag]; b[tg.valueoffset:tg.valueoffset + (2 if tg.dtype == 3 else 4)] = struct.pack('<H' if tg.dtype == 3 else '<I', val)
t2.close()
open(os.path.join(OUT, 'stop_block_area.tif'), 'wb').write(b); stop('stop_block_area.tif', 'cover more than 200 million pixels')
# truncated and corrupt copies of matrix files
def raw(name): return open(os.path.join(OUT, name), 'rb').read()
cands = [m['file'] for m in manifest if m['kind'] == 'matrix' and m.get('compression') == 8 and m.get('container') == 'classic']
b = bytearray(raw(cands[0]))
open(os.path.join(OUT, 'stop_truncated_header.tif'), 'wb').write(b[:6]); stop('stop_truncated_header.tif', 'too short for a TIFF header')
t = tifffile.TiffFile(os.path.join(OUT, cands[0])); pg = t.pages[0]
offs, cnts = (pg.dataoffsets, pg.databytecounts); t.close()
end = max(o + c for o, c in zip(offs, cnts)); last = int(np.argmax([o + c for o, c in zip(offs, cnts)]))
open(os.path.join(OUT, 'stop_truncated_data.tif'), 'wb').write(b[:end - 3]); stop('stop_truncated_data.tif', 'lie outside the file (truncated or corrupt file)')
c = bytearray(b); o = offs[1]
for k in range(6, min(40, cnts[1] - 4)): c[o + k] ^= 0x5A
open(os.path.join(OUT, 'stop_corrupt_deflate.tif'), 'wb').write(c); stop('stop_corrupt_deflate.tif', 'decompression error')
lz = [m['file'] for m in manifest if m['kind'] == 'matrix' and m.get('compression') == 5 and m.get('container') == 'classic' and m.get('layout') == 'strips']
b = bytearray(raw(lz[0])); t = tifffile.TiffFile(os.path.join(OUT, lz[0])); pg = t.pages[0]; o, n = pg.dataoffsets[0], pg.databytecounts[0]; t.close()
b[o + n // 2:o + n] = bytes([0xFF]) * (n - n // 2)
open(os.path.join(OUT, 'stop_corrupt_lzw.tif'), 'wb').write(b); stop('stop_corrupt_lzw.tif', 'decompression error')
# a raster of 100000 x 100000 pixels (the width and height tags of a small file changed)
small = tf_write('stop_huge.tif', DATA['uint8'], 1, keys='ll')
b = bytearray(raw(small)); t = tifffile.TiffFile(os.path.join(OUT, small)); pg = t.pages[0]
for tag in (256, 257):
    tg = pg.tags[tag]
    fmt = '<I' if tg.dtype == 4 else '<H'
    if tg.dtype == 3: b[tg.valueoffset:tg.valueoffset + 2] = struct.pack('<H', 50000 if tag == 256 else 60000)
    else: b[tg.valueoffset:tg.valueoffset + 4] = struct.pack('<I', 100000)
t.close()
open(os.path.join(OUT, small), 'wb').write(b); stop(small, 'pixels, more than the 50 million')

json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'), indent=0)
tot = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
big = max((os.path.getsize(os.path.join(OUT, f)), f) for f in os.listdir(OUT) if f.endswith('.tif'))
print('%d fixtures (%d matrix), %d files, %.0f KB in all, largest %s %.1f KB' % (len(manifest), sum(1 for m in manifest if m['kind'] == 'matrix'),
      len(os.listdir(OUT)), tot / 1024, big[1], big[0] / 1024))
