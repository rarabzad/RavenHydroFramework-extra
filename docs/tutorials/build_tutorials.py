#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Builds the Raven-MODFLOW 6 tutorials: runs every step of every tutorial with the given Raven (and Ostrich), writes the
tutorial files (start and finished state of each tutorial), captures the numbers and output excerpts quoted in the text
into generated LaTeX includes, makes the figures, compiles the PDFs and zips the tutorial files.

    python3 build_tutorials.py [--raven EXE] [--mf6lib LIB] [--package DIR] [--ostrich EXE] [--work DIR]
                               [--only t1,t2,...] [--quick] [--check] [--no-pdf | --pdf-only]

  --raven EXE     Raven with the MODFLOW 6 coupling (default: $RAVEN_EXE, else bin/Raven of --package)
  --mf6lib LIB    the MODFLOW 6 library (default: $RAVEN_MF6_LIB, else bin/libmf6.so of --package)
  --tools DIR     the tools folder of RavenHydroFramework-extra used in the steps (make_prt.py, plot_soilzone.py;
                  default: the tools/ of this repository)
  --package DIR   the unpacked release package (Raven_MF6_linux: README.md, bin/, examples/, source/); used for the
                  installation check and the Liard example. Without it, the examples of this repository and Raven's
                  cmake/RavenMF6InstallCheck.py ($RAVEN_SRC) are used, with Raven and the library copied into one folder
  --ostrich EXE   an OSTRICH executable for the calibration (tutorial 6). Without it (or with --quick) the calibration is
                  not rerun: its record (files/t6_calibration/finished/OstOutput0.txt) is read as committed and only the
                  validation of the best parameter set is rerun. An executable whose ELF interpreter is missing (as the
                  Linux build of the Raven-Ostrich tutorial files) is started through the system loader
  --work DIR      scratch folder for the runs (default: _work beside this script; deleted runs can be rebuilt)
  --only LIST     build only these tutorials (t1..t6); the PDFs are compiled only for a full build
  --quick         skip the long steps: the 20-year Liard run (tutorial 1) and the DDS calibration (tutorial 6)
  --check         rerun the steps and compare every generated number, output excerpt and diff (tex/generated/) and every
                  tutorial file (files/) with the committed ones; nothing is written outside --work. Exit code 1 on any
                  difference. With --quick, the values of the skipped steps are taken from the committed files
  --no-pdf        do not compile the PDFs and do not write the zip
  --pdf-only      only compile the PDFs and write the zip, from the committed includes and figures

Needs Python 3 with numpy, pandas, matplotlib and pyproj; pdflatex for the PDFs; FloPy for the particle tracking of
tutorial 5 (tools/make_prt.py). Run times quoted in the text are measured on the build machine and are not compared by
--check.
"""
import argparse, datetime, difflib, filecmp, glob, io, json, math, os, re, shutil, struct, subprocess, sys, time, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))           # RavenHydroFramework-extra
FILES = os.path.join(HERE, 'files')                     # the tutorial files (zip root: Raven_MF6_Tutorials/)
TEX = os.path.join(HERE, 'tex')
GEN = os.path.join(TEX, 'generated')
FIG = os.path.join(TEX, 'figures')
PDF = os.path.join(HERE, 'pdf')
ZIPFILE = os.path.join(HERE, 'Raven_MF6_Tutorial_Files.zip')
SCRIPTS = os.path.join(FILES, 'scripts')
TUTS = ['t1', 't2', 't3', 't4', 't5', 't6']
TDIR = {'t1': 't1_getting_started', 't2': 't2_own_model', 't3': 't3_soil_zone', 't4': 't4_existing_model',
        't5': 't5_restarts_ensembles_particles', 't6': 't6_calibration'}
TITLES = {'t1': 'Getting started', 't2': 'Your own groundwater model', 't3': 'The soil-zone coupling',
          't4': 'Coupling an existing MODFLOW 6 model', 't5': 'Restarts, ensembles and particle tracking',
          't6': 'Calibration with Ostrich (DDS)'}

# what the user sees: the package and the tutorial files unpacked in the home folder of a user "user"
U_HOME = '/home/user'
U_PKG = U_HOME + '/Raven_MF6_linux'
U_TUT = U_HOME + '/Raven_MF6_Tutorials'
U_WORK = U_HOME + '/work'


# ======================================================================================================================
# configuration and helpers
# ======================================================================================================================
class Cfg:
    pass


C = Cfg()


def log(msg):
    print('[%s] %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


class Gen:
    """generated values (LaTeX macros) and texts (output excerpts, diffs) of all tutorials"""

    def __init__(self):
        self.values, self.volatile, self.texts = {}, set(), {}

    def val(self, key, latex, volatile=False):
        self.values[key] = str(latex)
        if volatile:
            self.volatile.add(key)

    def text(self, name, s):
        s = s.rstrip('\n') + '\n'
        self.texts[name] = s

    def write(self, d):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'values.tex'), 'w') as f:
            f.write('% generated by build_tutorials.py: every number quoted in the tutorials\n')
            for k in sorted(self.values):
                f.write('\\defval{%s}{%s}%s\n' % (k, self.values[k], '  % measured on the build machine' if k in self.volatile else ''))
        for n, s in self.texts.items():
            with open(os.path.join(d, n), 'w') as f:
                f.write(s)


G = Gen()


def fmt(x, nd=0, sign=False):
    """number for LaTeX: thin space as thousands separator, nd decimals"""
    s = ('{:+,.%df}' if sign else '{:,.%df}') % nd
    s = s.format(x)
    if s in ('-0', '+0', '-0.0', '+0.0', '-0.00', '+0.00', '-0.000', '+0.000', '-0.0000', '+0.0000'):
        s = s.replace('-', '').replace('+', '')
    return s.replace(',', '\\,').replace('-', '$-$')


def sci(x, nd=1):
    """1.2e-07 -> 1.2\\times10^{-7} (math mode)"""
    if x == 0:
        return '0'
    m, e = ('%.*e' % (nd, x)).split('e')
    return '$%s\\times10^{%d}$' % (m.replace('-', '-'), int(e))


def sig(x, n=3):
    """n significant digits, as a plain number (LaTeX)"""
    if x == 0:
        return '0'
    d = max(0, n - 1 - int(math.floor(math.log10(abs(x)))))
    return fmt(x, d)


def sanitize(s, cwd=None, ucwd=None):
    """build paths -> the paths a user of the tutorial sees"""
    rep = []
    if cwd and ucwd:
        rep.append((os.path.abspath(cwd), ucwd))
    rep += [(C.work, U_WORK), (C.pkgdir or '\0', U_PKG), (os.path.dirname(C.mf6lib), U_PKG + '/bin'),
            (os.path.dirname(C.raven), U_PKG + '/bin'), (C.tools, U_PKG + '/raven-mf6-extra/tools'), (FILES, U_TUT)]
    for a, b in rep:
        if a and a != '\0':
            s = s.replace(a, b)
    s = s.replace(os.path.basename(C.raven), 'Raven') if os.path.basename(C.raven) != 'Raven' else s
    return s


def run(argv, cwd, display=None, name=None, keep=None, ucwd=None, timeout=7200, check=True, env=None):
    """runs a command as a tutorial step; name: write '$ display' and the (abridged, sanitized) output to generated/name"""
    t0 = time.time()
    r = subprocess.run(argv, cwd=cwd, env=env or C.env, capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    out = r.stdout + r.stderr
    if check and r.returncode != 0:
        sys.stderr.write(out[-4000:])
        raise RuntimeError('step failed (%d): %s in %s' % (r.returncode, ' '.join(argv), cwd))
    if name:
        o = keep(out) if keep else out
        G.text(name, '$ ' + display + '\n' + sanitize(o, cwd, ucwd).rstrip('\n'))
    return out, dt


def sh(cmd, cwd, name, ucwd=None, keep=None):
    """runs a shell command exactly as the tutorial shows it (bash, with $RAVEN, $TUT, $PKG, $TOOLS set)"""
    return run(['bash', '-c', cmd], cwd, cmd, name, keep, ucwd)


def raven(cwd, outdir='out', name=None, ucwd=None, keep=None, model='Creek', check=True):
    """runs Raven as the user does ($RAVEN model -o out/); returns (exit line, seconds, stdout)"""
    out, dt = run([C.raven, model, '-o', outdir + '/'], cwd, '$RAVEN %s -o %s/' % (model, outdir), name,
                  keep or keep_raven, ucwd, check=check)
    ex = (re.findall(r'Exiting Gracefully: (.*)', out) or ['(no exit line)'])[-1].strip()
    if check and 'Successful' not in ex:
        raise RuntimeError('Raven run in %s: %s\n%s' % (cwd, ex, open(os.path.join(cwd, outdir, 'Raven_errors.txt')).read()[-3000:]))
    return ex, dt, out


def keep_raven(out):
    """Raven's console output, abridged: the model summary's first lines, groundwater lines and the end"""
    L = out.rstrip('\n').split('\n')
    head = [l for l in L[:60] if l.startswith(('  Initializing groundwater', '  Groundwater', 'Initializing Model'))]
    i = next((k for k, l in enumerate(L) if l.startswith('==MODEL SUMMARY')), None)
    summ = L[i + 1:i + 4] if i is not None else []
    tail = [l for l in L if l.startswith('Exiting Gracefully')]
    return '\n'.join(['...'] + head + summ + ['...'] + tail[-1:])


def excerpt(text, patterns=None, first=None, last=None, drop=None):
    """lines of a text: those matching any regex of patterns (in order), or the first/last n lines; '...' marks gaps"""
    L = text.rstrip('\n').split('\n')
    if drop:
        L = [l for l in L if not re.search(drop, l)]
    if patterns:
        keep = [k for k, l in enumerate(L) if any(re.search(p, l) for p in patterns)]
    else:
        keep = list(range(len(L)))
        if first is not None or last is not None:
            keep = list(range(min(first or 0, len(L)))) + list(range(max(len(L) - (last or 0), first or 0), len(L)))
    out, prev = [], -1
    for k in keep:
        if prev >= 0 and k != prev + 1:
            out.append('...')
        out.append(L[k]); prev = k
    if keep and keep[-1] < len(L) - 1 and (patterns or first is not None) and not last:
        out.append('...')
    return '\n'.join(out)


def udiff(a_text, b_text, a_name, b_name, n=1):
    """exact unified diff (the tutorials show every edit this way)"""
    d = difflib.unified_diff(a_text.splitlines(True), b_text.splitlines(True), a_name, b_name, n=n)
    return ''.join(x if x.endswith('\n') else x + '\n' for x in d)


def diff_file(name, a_path, b_path, a_label, b_label, n=1):
    a = open(a_path).read() if a_path and os.path.exists(a_path) else ''
    b = open(b_path).read()
    G.text(name, udiff(a, b, a_label, b_label, n))


def edit(path, old, new, count=1):
    t = open(path).read()
    if t.count(old) < 1:
        raise RuntimeError('edit of %s: text not found: %r' % (path, old[:80]))
    open(path, 'w').write(t.replace(old, new, count))


def fresh(d):
    if os.path.exists(d):
        shutil.rmtree(d)
    os.makedirs(d)
    return d


def copytree(src, dst):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def wfile(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)


def csv(path):
    import pandas as pd
    return pd.read_csv(path)


# ======================================================================================================================
# Tutorial Creek: a small synthetic basin in UTM zone 11N (EPSG:32611)
# ======================================================================================================================
EPSG = 32611
X0, Y0, LX, LY = 500000.0, 5600000.0, 8000.0, 6000.0
YC = Y0 + LY / 2              # the creek runs west to east along y = YC
XS = X0 + LX / 2              # divide between subbasin 1 (UPPER, west) and 2 (LOWER, east)
XL0, XL1 = 503200.0, 504000.0     # lake (reservoir) at the outlet of subbasin 1
WET = (506000.0, 507200.0, YC - 700.0, YC - 250.0)   # wetland of subbasin 2
VW = 700.0                    # half width of the valley floor
RIDGE = YC + 2200.0           # bare-rock ridge of subbasin 1 (no aquifer)
LAKE_BED = 4.0                # the lake basin lies 4 m below the valley floor
START = datetime.date(2010, 1, 1)
NDAYS = (datetime.date(2015, 1, 1) - START).days      # forcing 2010-2014
DUR3 = (datetime.date(2013, 1, 1) - START).days       # the tutorials' runs: 2010-2012
_TR = None


def to_ll(x, y):
    global _TR
    if _TR is None:
        from pyproj import Transformer
        _TR = Transformer.from_crs(EPSG, 4326, always_xy=True)
    return _TR.transform(x, y)


def ground(x, y):
    """land surface [m]: a valley floor falling 40 m to the east, slopes rising to the north and south, hummocks"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = np.abs(y - YC)
    zr = 1000.0 - 0.005 * (x - X0)
    side = np.where(d < VW, 0.004 * d, 2.8 + 0.06 * (d - VW) + 4.0e-6 * (d - VW) ** 2)
    hum = np.where(d < VW + 300, 0.6 * np.sin(x / 90.0) * np.cos(y / 110.0), 0.0)
    lake = np.where((x > XL0) & (x < XL1) & (d < VW), -LAKE_BED, 0.0)
    return zr + side + hum + lake


def bedrock(x, y):
    """bedrock surface [m]: 40 m of valley fill, 35-40 m of till and weathered rock on the slopes"""
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = np.abs(y - YC)
    th = np.where(d < VW, 40.0, 40.0 - 5.0 * np.exp(-(d - VW) / 300.0))
    lake = np.where((x > XL0) & (x < XL1) & (d < VW), -LAKE_BED, 0.0)
    return ground(x, y) - lake - th


def write_geotiff(path, z, x_ul, y_ul, px, nodata=-9999.0):
    """single-band float32 GeoTIFF, one uncompressed strip, ModelPixelScale + ModelTiepoint, EPSG code, GDAL_NODATA"""
    nr, nc = z.shape
    data = z.astype('<f4').tobytes()
    gk = [1, 1, 0, 4, 1024, 0, 1, 1, 1025, 0, 1, 1, 3072, 0, 1, EPSG, 3076, 0, 1, 9001]
    nod = ('%g' % nodata).encode() + b'\0'
    tags = [(256, 4, 1, [nc]), (257, 4, 1, [nr]), (258, 3, 1, [32]), (259, 3, 1, [1]), (262, 3, 1, [1]),
            (273, 4, 1, None), (277, 3, 1, [1]), (278, 4, 1, [nr]), (279, 4, 1, [len(data)]), (284, 3, 1, [1]),
            (339, 3, 1, [3]), (33550, 12, 3, [px, px, 0.0]), (33922, 12, 6, [0.0, 0.0, 0.0, x_ul, y_ul, 0.0]),
            (34735, 3, len(gk), gk), (42113, 2, len(nod), nod)]
    fmtc, size = {3: 'H', 4: 'I', 12: 'd'}, {2: 1, 3: 2, 4: 4, 12: 8}
    n = len(tags)
    extra_off = 8 + 2 + 12 * n + 4
    extra, entries = b'', []
    for tag, typ, cnt, val in tags:
        if tag == 273:
            entries.append((tag, typ, cnt, None)); continue
        raw = val if typ == 2 else struct.pack('<' + fmtc[typ] * cnt, *val)
        if size[typ] * cnt <= 4:
            entries.append((tag, typ, cnt, raw.ljust(4, b'\0')))
        else:
            entries.append((tag, typ, cnt, struct.pack('<I', extra_off + len(extra))))
            extra += raw + (b'\0' if len(raw) % 2 else b'')
    data_off = extra_off + len(extra)
    out = b'II' + struct.pack('<HI', 42, 8) + struct.pack('<H', n)
    for tag, typ, cnt, raw in entries:
        out += struct.pack('<HHI', tag, typ, cnt) + (struct.pack('<I', data_off) if tag == 273 else raw)
    with open(path, 'wb') as f:
        f.write(out + struct.pack('<I', 0) + extra + data)


def write_rasters(d, ascii_too=False, px=50.0, margin=500.0):
    xa, ya = X0 - margin, Y0 - margin
    nc, nr = int((LX + 2 * margin) / px), int((LY + 2 * margin) / px)
    X, Y = np.meshgrid(xa + (np.arange(nc) + 0.5) * px, ya + (nr - np.arange(nr) - 0.5) * px)
    for name, f in (('dem', ground), ('bedrock', bedrock)):
        z = np.round(f(X, Y), 2)
        write_geotiff(os.path.join(d, name + '.tif'), z, xa, ya + nr * px, px)
        if ascii_too:
            with open(os.path.join(d, name + '.asc'), 'w') as fo:
                fo.write('ncols %d\nnrows %d\nxllcorner %.1f\nyllcorner %.1f\ncellsize %.1f\nNODATA_value -9999\n' % (nc, nr, xa, ya, px))
                for r in range(nr):
                    fo.write(' '.join('%.2f' % v for v in z[r]) + '\n')


def rect(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


HRUS = [  # id, subbasin, kind, polygon (UTM 11N)
    (1, 1, 'VALLEY', rect(X0, XL0, YC - VW, YC + VW)),
    (2, 1, 'SLOPE', rect(X0, XS, YC + VW, RIDGE)),
    (3, 1, 'SLOPE', rect(X0, XS, Y0, YC - VW)),
    (4, 1, 'RIDGE', rect(X0, XS, RIDGE, Y0 + LY)),
    (5, 1, 'LAKE', rect(XL0, XL1, YC - VW, YC + VW)),
    (6, 2, 'VALLEY', [[XS, YC - VW], [WET[0], YC - VW], [WET[0], WET[3]], [WET[1], WET[3]], [WET[1], YC - VW],
                      [X0 + LX, YC - VW], [X0 + LX, YC + VW], [XS, YC + VW], [XS, YC - VW]]),
    (7, 2, 'SLOPE', rect(XS, X0 + LX, YC + VW, Y0 + LY)),
    (8, 2, 'SLOPE', rect(XS, X0 + LX, Y0, YC - VW)),
    (9, 2, 'WETLAND', rect(WET[0], WET[1], WET[2], WET[3])),
]
AQ_OF = {1: 'VALLEY_FILL', 5: 'VALLEY_FILL', 6: 'VALLEY_FILL', 9: 'VALLEY_FILL',
         2: 'SLOPE_TILL', 3: 'SLOPE_TILL', 7: 'SLOPE_TILL', 8: 'SLOPE_TILL'}
WELL = (505500.0, 5603300.0)
OBSW = [(101, 'OW_NEAR', 505700.0, 5603300.0, 955.0), (102, 'OW_UPPER', 501500.0, 5602700.0, 985.0),
        (103, 'OW_SLOPE', 506500.0, 5604500.0, 995.0)]


def area(r):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r[:-1], r[1:]))) / 2


def centroid(r):
    p = np.array(r[:-1])
    return p[:, 0].mean(), p[:, 1].mean()


def hru_point(r):
    """a representative interior point of an HRU polygon (the L-shaped HRU 6: the middle of its northern half)"""
    x, y = centroid(r)
    return (x, YC + VW / 2) if len(r) > 6 else (x, y)


def gj(features, path):
    crs = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::%d" % EPSG}}
    with open(path, 'w') as f:
        json.dump({"type": "FeatureCollection", "crs": crs, "features": features}, f, indent=1)
        f.write('\n')


def write_geometry(d):
    gj([{"type": "Feature", "properties": {"HRU_ID": i, "SUBBASIN": sb},
         "geometry": {"type": "Polygon", "coordinates": [[[round(x, 2), round(y, 2)] for x, y in r]]}} for i, sb, k, r in HRUS],
       os.path.join(d, 'hrus.geojson'))
    gj([{"type": "Feature", "properties": {"SUBBASIN": 1}, "geometry": {"type": "LineString", "coordinates": [[X0 + 100, YC], [XL0, YC]]}},
        {"type": "Feature", "properties": {"SUBBASIN": 2}, "geometry": {"type": "LineString", "coordinates": [[XS, YC], [X0 + LX, YC]]}}],
       os.path.join(d, 'rivers.geojson'))
    gj([{"type": "Feature", "properties": {"NAME": "OUTLET"},
         "geometry": {"type": "LineString", "coordinates": [[507900.0, YC - 900], [507900.0, YC + 900]]}}],
       os.path.join(d, 'outlet.geojson'))
    gj([{"type": "Feature", "properties": {"NAME": "POND"},
         "geometry": {"type": "Polygon", "coordinates": [rect(504500.0, 505000.0, YC + 250, YC + 600)]}}],
       os.path.join(d, 'pond.geojson'))


def season(ndays=NDAYS):
    t = np.arange(ndays)
    return np.cos(2 * math.pi * (t % 365.25 - 15) / 365.25)      # +1 mid January, -1 mid July


def write_forcing(path, seed=20101):
    rs = np.random.RandomState(seed)
    s = season()
    wet = rs.uniform(size=NDAYS) < 0.45 + 0.17 * s
    amt = rs.exponential(1.0, size=NDAYS) * (5.5 + 2.5 * s)
    p = np.where(wet, amt, 0.0)
    temp = np.maximum(10.0 - 8.0 * s + rs.normal(0, 2.0, NDAYS), 0.5)
    lon, lat = to_ll(X0 + LX / 2, YC)
    with open(path, 'w') as f:
        f.write('# CreekMet.rvt - daily weather at the Tutorial Creek station, 2010-2014 (synthetic)\n')
        f.write(':Gauge CreekMet\n  :Latitude %.6f\n  :Longitude %.6f\n  :Elevation 1000.0\n' % (lat, lon))
        f.write('  :MultiData\n    %s 00:00:00 1.0 %d\n    :Parameters, PRECIP, TEMP_DAILY_AVE\n    :Units, mm/d, C\n' % (START.isoformat(), NDAYS))
        for a, b in zip(p, temp):
            f.write('    %.1f, %.1f\n' % (a, b))
        f.write('  :EndMultiData\n:EndGauge\n')


def write_gw_series(path):
    s = season()
    q = -(900.0 - 500.0 * s)
    h = 976.5 + 0.4 * s
    with open(path, 'w') as f:
        f.write('# CreekGW.rvt - pumping of well PW_1 and level of the gravel-pit pond, 2010-2014\n')
        f.write(':WellFlowRate 1 m3/d\n  %s 00:00:00 1.0 %d\n' % (START.isoformat(), NDAYS) + ''.join('  %.1f\n' % v for v in q) + ':EndWellFlowRate\n')
        f.write(':BoundaryHead POND m\n  %s 00:00:00 1.0 %d\n' % (START.isoformat(), NDAYS) + ''.join('  %.3f\n' % v for v in h) + ':EndBoundaryHead\n')


# ---------------------------------------------------------------------------------------------------- Raven files
RVI = """# Creek.rvi - Tutorial Creek: model options and processes
:StartDate          2010-01-01 00:00:00
:Duration           %d
:TimeStep           1.0
:Method             ORDERED_SERIES
:SoilModel          SOIL_MULTILAYER 3
:Routing            ROUTE_DIFFUSIVE_WAVE
:CatchmentRoute     ROUTE_DUMP
:Evaporation        PET_OUDIN
:OW_Evaporation     PET_OUDIN
:RainSnowFraction   RAINSNOW_THRESHOLD
:OroTempCorrect     OROCORR_NONE
:OroPrecipCorrect   OROCORR_NONE

:Alias  TOPSOIL     SOIL[0]
:Alias  SUBSOIL     SOIL[1]
:Alias  DEEP_STORE  SOIL[2]

:HydrologicProcesses
  :Precipitation        PRECIP_RAVEN     ATMOS_PRECIP  MULTIPLE
  :LakeEvaporation      LAKE_EVAP_BASIC  SURFACE_WATER ATMOSPHERE
    :-->Conditional HRU_TYPE IS LAKE
  :Flush                RAVEN_DEFAULT    PONDED_WATER  DEPRESSION
    :-->Conditional HRU_TYPE IS WETLAND
  :DepressionOverflow   DFLOW_THRESHPOW  DEPRESSION    SURFACE_WATER
  :OpenWaterEvaporation OPEN_WATER_EVAP  DEPRESSION    ATMOSPHERE
  :Seepage              SEEP_LINEAR      DEPRESSION    SUBSOIL
  :Infiltration         INF_HBV          PONDED_WATER  MULTIPLE
  :SoilEvaporation      SOILEVAP_HBV     TOPSOIL       ATMOSPHERE
  :Percolation          PERC_GAWSER      TOPSOIL       SUBSOIL
  :Baseflow             BASE_LINEAR      SUBSOIL       SURFACE_WATER
  :Percolation          PERC_LINEAR      SUBSOIL       DEEP_STORE
  :Baseflow             BASE_LINEAR      DEEP_STORE    SURFACE_WATER
:EndHydrologicProcesses

:EvaluationMetrics NASH_SUTCLIFFE RMSE KLING_GUPTA
:WriteMassBalanceFile
"""

RVP = """# Creek.rvp - Tutorial Creek: parameters
:AvgAnnualRunoff 450.0
:GlobalParameter RAINSNOW_TEMP 0.0

:SoilClasses
  :Attributes
  :Units
  TOPSOIL
  SUBSOIL
  DEEP
:EndSoilClasses

:SoilProfiles
  # name,       #horizons, {class, thickness [m]} x #horizons
  LAKE,         0
  VALLEY_SOIL,  3, TOPSOIL, 0.3, SUBSOIL, 1.0, DEEP, 5.0
  SLOPE_SOIL,   3, TOPSOIL, 0.3, SUBSOIL, 0.7, DEEP, 5.0
  ROCK_SOIL,    3, TOPSOIL, 0.1, SUBSOIL, 0.2, DEEP, 5.0
  WETLAND_SOIL, 3, TOPSOIL, 0.3, SUBSOIL, 1.0, DEEP, 5.0
:EndSoilProfiles

:SoilParameterList
  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HBV_BETA, MAX_PERC_RATE, PERC_COEFF, BASEFLOW_COEFF
  :Units,      none,     none,           none,     none,     mm/d,          1/d,        1/d
  TOPSOIL,     0.45,     0.30,           0.10,     2.0,      20.0,          0.0,        0.0
  SUBSOIL,     0.40,     0.25,           0.10,     2.0,      0.0,           %s,       0.01
  DEEP,        0.30,     0.05,           0.0,      1.0,      0.0,           0.0,        0.005
:EndSoilParameterList

:VegetationClasses
  :Attributes, MAX_HT, MAX_LAI, MAX_LEAF_COND
  :Units,      m,      none,    mm_per_s
  GRASS,       0.5,    2.0,     5.0
  FOREST,      20.0,   5.0,     5.0
  BARE,        0.0,    0.0,     0.0
:EndVegetationClasses

:VegetationParameterList
  :Parameters, RAIN_ICEPT_PCT, SNOW_ICEPT_PCT
  :Units,      none,           none
  [DEFAULT],   0.0,            0.0
:EndVegetationParameterList

:LandUseClasses
  :Attributes, IMPERM, FOREST_COV
  :Units,      frac,   frac
  OPEN,        0.0,    0.0
  FOREST,      0.0,    1.0
  ROCK,        0.3,    0.0
  WATER,       0.0,    0.0
  WETLAND,     0.0,    0.0
:EndLandUseClasses

:LandUseParameterList
  :Parameters, DEP_THRESHOLD, DEP_N, DEP_MAX_FLOW, DEP_MAX, DEP_SEEP_K, OW_PET_CORR, LAKE_PET_CORR
  :Units,      mm,            none,  mm/d,         mm,      1/d,        none,        none
  [DEFAULT],   100.0,         1.0,   20.0,         300.0,   0.01,       1.0,         1.0
:EndLandUseParameterList

:ChannelProfile CREEK_CHANNEL
  :Bedslope 0.005
  :SurveyPoints
    0.0  4.0
    8.0  1.5
    10.0 0.0
    16.0 0.0
    18.0 1.5
    26.0 4.0
  :EndSurveyPoints
  :RoughnessZones
    0.0 0.04
  :EndRoughnessZones
:EndChannelProfile
"""

# the groundwater part of the .rvp (tutorial 2); the "true" parameters of the calibration (tutorial 6)
TRUE = {'K_GRAVEL': 40.0, 'K_TILL': 2.0, 'SY_GRAVEL': 0.20, 'PERC_SUBSOIL': 0.04, 'K_SAND': 8.0, 'SY_TILL': 0.08}
RVP_GW = """
# --- groundwater (Raven-MODFLOW 6) ---------------------------------------------
:AquiferClasses
  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY
  :Units,      m/d,     m/d,    1/m,          none,       none
  GRAVEL,      %s,    4.0,    1.0E-5,       %s,       0.30
  SAND,        %s,     0.8,    1.0E-5,       0.15,       0.32
  TILL,        %s,     0.2,    1.0E-4,       %s,       0.30
:EndAquiferClasses

:AquiferProfiles
  # name,      #layers, {class, thickness [m] or TO_BEDROCK, layer type} x #layers
  VALLEY_FILL, 2, GRAVEL, 12.0, AQUIFER, SAND, TO_BEDROCK, AQUIFER
  SLOPE_TILL,  2, TILL,   4.0,  AQUIFER, TILL, TO_BEDROCK, AQUIFER
:EndAquiferProfiles

:AquiferProfileParameters
  :Attributes, INITIAL_HEAD_DEPTH, SEEPAGE_LEAKANCE
  :Units,      m,                  1/d
  VALLEY_FILL, 2.0,                1.0
  SLOPE_TILL,  5.0,                1.0
:EndAquiferProfileParameters
"""


def rvp_text(gw=True, K_GRAVEL='40.0', SY_GRAVEL='0.20', K_TILL='2.0', PERC_SUBSOIL='0.04', K_SAND='8.0', SY_TILL='0.08'):
    t = RVP % PERC_SUBSOIL
    return t + (RVP_GW % (K_GRAVEL, SY_GRAVEL, K_SAND, K_TILL, SY_TILL) if gw else '')


RVC = """# Creek.rvc - initial conditions (soil water [mm]; the lake HRU 5 has no soil)
:HRUStateVariableTable
  :Attributes, SOIL[0], SOIL[1], SOIL[2]
  :Units,      mm,      mm,      mm
  1,           90.0,    250.0,   300.0
  2,           90.0,    175.0,   300.0
  3,           90.0,    175.0,   300.0
  4,           30.0,    50.0,    300.0
  6,           90.0,    250.0,   300.0
  7,           90.0,    175.0,   300.0
  8,           90.0,    175.0,   300.0
  9,           90.0,    250.0,   300.0
:EndHRUStateVariableTable
:InitialReservoirStage 1 982.0
"""


def rvh_text(aq=None, group=False, lake_seepage=False):
    aq = aq or {}
    L = ['# Creek.rvh - Tutorial Creek: two subbasins, nine HRUs, one reservoir',
         ':SubBasins',
         '  :Attributes, NAME,  DOWNSTREAM_ID, PROFILE,       REACH_LENGTH, GAUGED',
         '  :Units,      none,  none,          none,          km,           none',
         '  1,           UPPER, 2,             CREEK_CHANNEL, 3.2,          0',
         '  2,           LOWER, -1,            CREEK_CHANNEL, 4.0,          1',
         ':EndSubBasins', '',
         ':HRUs',
         '  :Attributes, AREA, ELEVATION, LATITUDE, LONGITUDE, BASIN_ID, LAND_USE_CLASS, VEG_CLASS, SOIL_PROFILE, AQUIFER_PROFILE, TERRAIN_CLASS, SLOPE, ASPECT',
         '  :Units,      km2,  m,         deg,      deg,       none,     none,           none,      none,         none,            none,          deg,   deg']
    kinds = {'VALLEY': ('OPEN', 'GRASS', 'VALLEY_SOIL', 1), 'SLOPE': ('FOREST', 'FOREST', 'SLOPE_SOIL', 6),
             'RIDGE': ('ROCK', 'BARE', 'ROCK_SOIL', 12), 'LAKE': ('WATER', 'BARE', 'LAKE', 0),
             'WETLAND': ('WETLAND', 'GRASS', 'WETLAND_SOIL', 0)}
    for i, sb, k, r in HRUS:
        x, y = hru_point(r)
        lon, lat = to_ll(x, y)
        lu, veg, soil, slope = kinds[k]
        L.append('  %d, %8.4f, %7.1f, %.6f, %.6f, %d, %-7s, %-6s, %-12s, %-11s, [NONE], %2d, 0' % (
            i, area(r) / 1e6, float(ground(x, y)) + (LAKE_BED if k == 'LAKE' else 0.0), lat, lon, sb, lu, veg, soil,
            aq.get(i, '[NONE]'), slope))
    L.append(':EndHRUs')
    if group:
        L += ['', ':HRUGroup AquiferHRUs', '  ' + ', '.join(str(i) for i in sorted(aq)), ':EndHRUGroup']
    L += ['', ':Reservoir CreekLake', '  :SubBasinID          1', '  :HRUID               5', '  :Type                RESROUTE_STANDARD',
          '  :WeirCoefficient     0.6', '  :CrestWidth          10.0', '  :MaxDepth            6.0', '  :LakeArea            1.12E6',
          '  :AbsoluteCrestHeight 982.0']
    if lake_seepage:
        L += ['  :SeepageParameters   0.05 978.0']
    L.append(':EndReservoir')
    return '\n'.join(L) + '\n'


RVT = """# Creek.rvt - forcing (and, later, groundwater series and observations)
:RedirectToFile CreekMet.rvt
"""

RVG = """# Creek.rvg - the groundwater model of Tutorial Creek (Raven builds it)

# --- input files and their projection ------------------------------------------
:InputCRS          EPSG:32611                      # every GeoJSON and raster below is in UTM zone 11N
:HRUGeometry       hrus.geojson    HRU_ID          # HRU polygons; HRU_ID matches the .rvh
:RiverGeometry     rivers.geojson  SUBBASIN        # creek lines, each with its Raven subbasin
:LandSurface       dem.tif                         # land surface (GeoTIFF; ESRI ASCII grids work too)
:BedrockSurface    bedrock.tif                     # base of the aquifer

# --- grid and start --------------------------------------------------------------
:GridCellSize      250.0                           # m
:GWInitialization  STEADY_STATE 1.2                # start from the steady state for 1.2 mm/d of recharge

# --- wells (rates in CreekGW.rvt) and observation wells (by X, Y with :InputCRS) ----
:Wells
  :Attributes, NAME, X, Y, SCREEN_TOP, SCREEN_BOT
  1, PW_1, 505500.0, 5603300.0, 958.0, 945.0
:EndWells
:ObservationWells
  :Attributes, NAME, X, Y, SCREEN_ELEV
  101, OW_NEAR,  505700.0, 5603300.0, 955.0
  102, OW_UPPER, 501500.0, 5602700.0, 985.0
  103, OW_SLOPE, 506500.0, 5604500.0, 995.0
:EndObservationWells

# --- head boundaries -------------------------------------------------------------
:GeneralHeadBoundary   OUTLET outlet.geojson HEAD 958.0 CONDUCTANCE 500.0 LAYERS ALL   # underflow leaving the valley
:SpecifiedHeadBoundary POND   pond.geojson   HEAD 976.5 LAYERS TOP                     # gravel-pit pond; level from CreekGW.rvt
"""


def rvi_coupled(duration=DUR3):
    t = RVI % duration
    t = t.replace(':Alias  TOPSOIL', ':GroundwaterModel  MODFLOW6\n:DefineHRUGroups   AquiferHRUs\n\n:Alias  TOPSOIL')
    t = t.replace('  :Percolation          PERC_LINEAR      SUBSOIL       DEEP_STORE\n',
                  '  :Percolation          PERC_LINEAR      SUBSOIL       DEEP_STORE\n    :-->Conditional HRU_GROUP IS_NOT AquiferHRUs\n'
                  '  :Percolation          PERC_LINEAR      SUBSOIL       GROUNDWATER\n    :-->Conditional HRU_GROUP IS AquiferHRUs\n')
    return t


def write_creek_start(d, ascii_too=False):
    """Tutorial Creek as a Raven model without groundwater, with the data a groundwater model needs"""
    os.makedirs(d, exist_ok=True)
    write_rasters(d, ascii_too)
    write_geometry(d)
    write_forcing(os.path.join(d, 'CreekMet.rvt'))
    write_gw_series(os.path.join(d, 'CreekGW.rvt'))
    wfile(os.path.join(d, 'Creek.rvi'), RVI % DUR3)
    wfile(os.path.join(d, 'Creek.rvp'), rvp_text(gw=False))
    wfile(os.path.join(d, 'Creek.rvh'), rvh_text())
    wfile(os.path.join(d, 'Creek.rvc'), RVC)
    wfile(os.path.join(d, 'Creek.rvt'), RVT)


def write_creek_coupled(d, ascii_too=False):
    """the finished model of tutorial 2"""
    write_creek_start(d, ascii_too)
    wfile(os.path.join(d, 'Creek.rvi'), rvi_coupled())
    wfile(os.path.join(d, 'Creek.rvp'), rvp_text())
    wfile(os.path.join(d, 'Creek.rvh'), rvh_text(AQ_OF, group=True))
    wfile(os.path.join(d, 'Creek.rvt'), RVT + ':RedirectToFile CreekGW.rvt\n')
    wfile(os.path.join(d, 'Creek.rvg'), RVG)


# ---------------------------------------------------------------------------------------------------- existing model
FT = 1.0 / 0.3048                 # feet per metre
EXT_DX = 1000.0                   # cell size [ft]
EXT_NCOL, EXT_NROW, EXT_NLAY = 28, 21, 2
EXT_XO, EXT_YO = X0 - 250.0, Y0 - 200.0       # lower-left corner of the grid [m]


def mf_array(name, a, fmt='%.2f', per=10):
    """a MODFLOW array, INTERNAL; every row of the grid starts on a new line (MODFLOW reads arrays row by row)"""
    a = np.asarray(a)
    L = ['  %s' % name, '    INTERNAL FACTOR 1.0']
    for row in a.reshape(-1, a.shape[-1]):
        for i in range(0, len(row), per):
            L.append('      ' + ' '.join(fmt % x for x in row[i:i + per]))
    return '\n'.join(L)


def ext_periods(start=START, end=datetime.date(2013, 1, 1)):
    """stress periods: one steady day, the rest of January, then calendar months"""
    per = [1]
    d = start + datetime.timedelta(days=1)
    while d < end:
        nm = min((d.replace(day=1) + datetime.timedelta(days=32)).replace(day=1), end)
        per.append((nm - d).days)
        d = nm
    return per


def write_existing_model(d):
    """a MODFLOW 6 model of Tutorial Creek as another modeller might have built it: feet and days, 1000-ft cells,
    two layers, a steady first day and monthly periods, its own recharge (RCH_MODEL) and ET (EVT_MODEL), river cells
    with their Raven subbasin (RIV_CREEK, auxiliary SUBBASIN), a pumping well and a head boundary at the outlet"""
    os.makedirs(d, exist_ok=True)
    m2f = FT
    xc = EXT_XO + (np.arange(EXT_NCOL) + 0.5) * EXT_DX / m2f
    yc = EXT_YO + (EXT_NROW - np.arange(EXT_NROW) - 0.5) * EXT_DX / m2f
    X, Y = np.meshgrid(xc, yc)
    s = (np.arange(5) + 0.5) / 5 - 0.5
    top = np.mean([ground(X + a * EXT_DX / m2f, Y + b * EXT_DX / m2f) for a in s for b in s], axis=0)
    bed = np.mean([bedrock(X + a * EXT_DX / m2f, Y + b * EXT_DX / m2f) for a in s for b in s], axis=0)
    valley = np.abs(Y - YC) < VW + 100
    bot1 = np.where(valley, top - 12.0, top - 4.0)
    inside = (X > X0) & (X < X0 + LX) & (Y > Y0) & (Y < Y0 + LY) & ~((X < XS) & (Y > RIDGE))
    idom = inside.astype(int)
    kh = np.array([np.where(valley, 40.0, 2.0), np.where(valley, 8.0, 2.0)])
    sy = np.array([np.where(valley, 0.20, 0.08), np.where(valley, 0.15, 0.08)])
    ss = np.array([np.where(valley, 1e-5, 1e-4)] * 2)
    per = ext_periods()

    def w(f, t):
        wfile(os.path.join(d, f), t.strip('\n') + '\n')
    w('mfsim.nam', 'BEGIN OPTIONS\nEND OPTIONS\nBEGIN TIMING\n  TDIS6  creek.tdis\nEND TIMING\nBEGIN MODELS\n  GWF6  creek.nam  CREEK\n'
      'END MODELS\nBEGIN EXCHANGES\nEND EXCHANGES\nBEGIN SOLUTIONGROUP 1\n  IMS6  creek.ims  CREEK\nEND SOLUTIONGROUP\n')
    w('creek.tdis', '# Tutorial Creek groundwater model: a steady first day, then monthly stress periods, 2010-2012\n'
      'BEGIN OPTIONS\n  TIME_UNITS DAYS\n  START_DATE_TIME %s\nEND OPTIONS\nBEGIN DIMENSIONS\n  NPER %d\nEND DIMENSIONS\nBEGIN PERIODDATA\n' % (START.isoformat(), len(per))
      + ''.join('  %.1f 1 1.0\n' % p for p in per) + 'END PERIODDATA\n')
    w('creek.ims', 'BEGIN OPTIONS\n  PRINT_OPTION SUMMARY\n  COMPLEXITY MODERATE\nEND OPTIONS\nBEGIN NONLINEAR\n  OUTER_DVCLOSE 1.0E-4\n'
      '  OUTER_MAXIMUM 500\nEND NONLINEAR\nBEGIN LINEAR\n  INNER_MAXIMUM 200\n  INNER_DVCLOSE 1.0E-5\n  INNER_RCLOSE 1.0E-1\n'
      '  LINEAR_ACCELERATION BICGSTAB\nEND LINEAR\n')
    w('creek.nam', 'BEGIN OPTIONS\n  NEWTON\nEND OPTIONS\nBEGIN PACKAGES\n  DIS6   creek.dis   DIS\n  IC6    creek.ic    IC\n'
      '  NPF6   creek.npf   NPF\n  STO6   creek.sto   STO\n  RCH6   creek.rcha  RCH_MODEL\n  EVT6   creek.evta  EVT_MODEL\n'
      '  RIV6   creek.riv   RIV_CREEK\n  WEL6   creek.wel   WEL_PUMP\n  GHB6   creek.ghb   GHB_OUTLET\n  OC6    creek.oc    OC\nEND PACKAGES\n')
    w('creek.dis', '# lengths in feet; the grid lies in UTM zone 11N (EPSG:32611), origin given in feet\n'
      'BEGIN OPTIONS\n  LENGTH_UNITS FEET\n  XORIGIN %.2f\n  YORIGIN %.2f\n  ANGROT 0.0\nEND OPTIONS\n' % (EXT_XO * m2f, EXT_YO * m2f)
      + 'BEGIN DIMENSIONS\n  NLAY %d\n  NROW %d\n  NCOL %d\nEND DIMENSIONS\nBEGIN GRIDDATA\n  DELR\n    CONSTANT %.1f\n  DELC\n    CONSTANT %.1f\n'
      % (EXT_NLAY, EXT_NROW, EXT_NCOL, EXT_DX, EXT_DX)
      + mf_array('TOP', top * m2f) + '\n' + mf_array('BOTM', np.array([bot1, bed]) * m2f) + '\n'
      + mf_array('IDOMAIN', np.array([idom, idom]), '%d', 28) + '\nEND GRIDDATA\n')
    h0 = top - np.where(valley, 1.0, 10.0)
    w('creek.ic', 'BEGIN GRIDDATA\n' + mf_array('STRT', np.array([h0, h0]) * m2f) + '\nEND GRIDDATA\n')
    w('creek.npf', 'BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN GRIDDATA\n  ICELLTYPE\n    CONSTANT 1\n'
      + mf_array('K', kh * m2f, '%.4g') + '\n' + mf_array('K33', kh / 10.0 * m2f, '%.4g') + '\nEND GRIDDATA\n')
    w('creek.sto', 'BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN GRIDDATA\n  ICONVERT\n    CONSTANT 1\n'
      + mf_array('SS', ss / m2f, '%.4g') + '\n' + mf_array('SY', sy, '%.3f') + '\nEND GRIDDATA\n'
      'BEGIN PERIOD 1\n  STEADY-STATE\nEND PERIOD\nBEGIN PERIOD 2\n  TRANSIENT\nEND PERIOD\n')
    w('creek.rcha', 'BEGIN OPTIONS\n  READASARRAYS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN PERIOD 1\n  RECHARGE\n    CONSTANT %.5f\nEND PERIOD\n' % (0.0008 * m2f))
    w('creek.evta', 'BEGIN OPTIONS\n  READASARRAYS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN PERIOD 1\n' + mf_array('SURFACE', top * m2f)
      + '\n  RATE\n    CONSTANT %.5f\n  DEPTH\n    CONSTANT %.2f\nEND PERIOD\n' % (0.002 * m2f, 1.5 * m2f))
    riv = []
    for c in range(EXT_NCOL):
        for r in range(EXT_NROW):
            if not (yc[r] - 0.5 * EXT_DX / m2f <= YC < yc[r] + 0.5 * EXT_DX / m2f) or not idom[r, c]:
                continue
            xa, xb = xc[c] - 0.5 * EXT_DX / m2f, xc[c] + 0.5 * EXT_DX / m2f
            for s0, s1, sb in ((X0 + 100, XL0, 1), (XS, X0 + LX, 2)):
                L = max(0.0, min(xb, s1) - max(xa, s0))
                if L > 50:
                    zb = 1000.0 - 0.005 * (xc[c] - X0)
                    riv.append((r + 1, c + 1, (zb - 0.5) * m2f, 50.0 * L * m2f * m2f, (zb - 1.5) * m2f, sb))
    w('creek.riv', '# stage, conductance [ft2/d], bottom; SUBBASIN: the Raven subbasin of the reach\n'
      'BEGIN OPTIONS\n  AUXILIARY SUBBASIN\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN DIMENSIONS\n  MAXBOUND %d\nEND DIMENSIONS\nBEGIN PERIOD 1\n' % len(riv)
      + ''.join('  1 %d %d %.2f %.1f %.2f %d\n' % x for x in riv) + 'END PERIOD\n')
    cw, rw = int((WELL[0] - EXT_XO) * m2f / EXT_DX), int((EXT_YO + EXT_NROW * EXT_DX / m2f - WELL[1]) * m2f / EXT_DX)
    L = ['# well PW_1 in layer 2: monthly pumping [ft3/d]\nBEGIN OPTIONS\n  SAVE_FLOWS\n  AUTO_FLOW_REDUCE 0.1\nEND OPTIONS\n'
         'BEGIN DIMENSIONS\n  MAXBOUND 1\nEND DIMENSIONS']
    t = 0
    for k, p in enumerate(per):
        mid = START + datetime.timedelta(days=t + p / 2.0)
        sn = math.cos(2 * math.pi * (mid.timetuple().tm_yday - 15) / 365.25)
        L.append('BEGIN PERIOD %d\n  2 %d %d %.1f\nEND PERIOD' % (k + 1, rw + 1, cw + 1, -(900.0 - 500.0 * sn) * m2f ** 3))
        t += p
    w('creek.wel', '\n'.join(L))
    ce = max(c for c in range(EXT_NCOL) if idom[EXT_NROW // 2, c])
    ghb = [(k + 1, r + 1, ce + 1) for k in range(2) for r in range(EXT_NROW) if idom[r, ce] and abs(yc[r] - YC) < 900]
    w('creek.ghb', 'BEGIN OPTIONS\n  SAVE_FLOWS\nEND OPTIONS\nBEGIN DIMENSIONS\n  MAXBOUND %d\nEND DIMENSIONS\nBEGIN PERIOD 1\n' % len(ghb)
      + ''.join('  %d %d %d %.2f %.1f\n' % (k, r, c, 958.0 * m2f, 500.0 * m2f * m2f) for k, r, c in ghb) + 'END PERIOD\n')
    w('creek.oc', 'BEGIN OPTIONS\n  HEAD FILEOUT creek.hds\nEND OPTIONS\nBEGIN PERIOD 1\n  SAVE HEAD LAST\nEND PERIOD\n')
    return {'periods': len(per), 'riv': len(riv), 'ghb': len(ghb), 'active': int(idom.sum())}


# ======================================================================================================================
# shared steps
# ======================================================================================================================
def tutfiles(t, *p):
    """path in the tutorial files (in --check mode a copy in the work folder, compared at the end)"""
    return os.path.join(C.files, TDIR[t], *p)


def figpath(name):
    os.makedirs(C.fig, exist_ok=True)
    return os.path.join(C.fig, name)


def plt_():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 9, 'axes.titlesize': 9.5, 'legend.fontsize': 8, 'figure.dpi': 100})
    return plt


def budget(out):
    import pandas as pd
    b = pd.read_csv(os.path.join(out, 'GWBudget.csv'))
    b['date'] = pd.to_datetime(b['date'])
    return b


def summary_text(out):
    return open(os.path.join(out, 'GWModelSummary.txt')).read()


def summary_excerpt(out, patterns, ucwd):
    s = summary_text(out)
    return sanitize(excerpt(s, patterns, drop=r'computed in'), ucwd=ucwd)


def plot_gw(t, out, ucwd, name, title, figs=('gw_budget', 'gw_watertable', 'gw_map', 'gw_obswells'), hrus=None, rel='out'):
    disp = 'python3 $TUT/scripts/plot_gw.py %s' % rel + (' --hrus ' + ' '.join(map(str, hrus)) if hrus else '') + \
           (' --title "%s"' % title if title else '')
    argv = [sys.executable, os.path.join(SCRIPTS, 'plot_gw.py'), out] + (['--hrus'] + [str(h) for h in hrus] if hrus else []) + \
           (['--title', title] if title else [])
    o, _ = run(argv, os.path.dirname(out), disp, name, ucwd=ucwd)
    for f in figs:
        p = os.path.join(out, f + '.png')
        if os.path.exists(p):
            shutil.copy(p, figpath('%s_%s.png' % (t, f)))
    return o


def audit(t, out, name, ucwd, rel='out'):
    tool = os.path.join(C.examples, 'Liard_groundwater', 'tools_audit.py')
    o, _ = run([sys.executable, tool, out], os.path.dirname(out), 'python3 $PKG/examples/Liard_groundwater/tools_audit.py %s' % rel,
               name, ucwd=ucwd)
    return o


def audit_values(t, o):
    """numbers of tools_audit.py's report"""
    def num(p):
        m = re.search(p, o)
        return float(m.group(1)) if m else float('nan')
    G.val(t + ':auditUnconv', '%d' % num(r'unconverged steps\s*[:=]?\s*([-0-9.eE+]+)'))
    G.val(t + ':auditRes', sci(num(r'MF6 cumulative residual / gross flow\s*[:=]?\s*([-0-9.eE+]+)')))


def hrustate(out):
    import pandas as pd
    return pd.read_csv(os.path.join(out, 'GWHRUState.csv'))


def gwheads(out):
    import pandas as pd
    return pd.read_csv(os.path.join(out, 'GWHeads.csv'))


def hydro(out, col='LOWER [m3/s]'):
    import pandas as pd
    h = pd.read_csv(os.path.join(out, 'Hydrographs.csv'))
    h['date'] = pd.to_datetime(h['date'])
    return h[['date', col]].rename(columns={col: 'q'})


def basin_map(path, out=None, title='Tutorial Creek', show_grid=True, extra=None):
    """map of Tutorial Creek: HRUs, creek, lake, wetland, wells, boundaries and (from a run) the active grid cells"""
    plt = plt_()
    from matplotlib.patches import Polygon as MPoly
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    col = {'VALLEY': '#e8f1d8', 'SLOPE': '#cfe3c1', 'RIDGE': '#d9d4cc', 'LAKE': '#9cc7ef', 'WETLAND': '#b7dbd3'}
    for i, sb, k, r in HRUS:
        p = np.array(r) / 1000.0
        ax.add_patch(MPoly(p, closed=True, fc=col[k], ec='#555555', lw=0.8))
        x, y = hru_point(r)
        ax.text(x / 1000.0, y / 1000.0, '%d' % i, ha='center', va='center', fontsize=9, fontweight='bold', color='#333333')
    if out and show_grid:
        from pyproj import Transformer
        tr = Transformer.from_crs(4326, EPSG, always_xy=True)
        cells = json.load(open(os.path.join(out, 'mf6', 'grid_cells.geojson')))['features']
        for c in cells:
            if c['properties'].get('active', 1):
                ring = np.array(c['geometry']['coordinates'][0])
                xs, ys = tr.transform(ring[:, 0], ring[:, 1])
                ax.plot(np.array(xs) / 1000.0, np.array(ys) / 1000.0, color='#7a7a7a', lw=0.25)
    ax.plot([(X0 + 100) / 1000, XL0 / 1000], [YC / 1000] * 2, color='#1f5fbf', lw=2.2, label='creek (rivers.geojson)')
    ax.plot([XS / 1000, (X0 + LX) / 1000], [YC / 1000] * 2, color='#1f5fbf', lw=2.2)
    ax.plot([507.9, 507.9], [(YC - 900) / 1000, (YC + 900) / 1000], color='#b03030', lw=2.0, label='GHB OUTLET (outlet.geojson)')
    ax.add_patch(MPoly(np.array(rect(504500.0, 505000.0, YC + 250, YC + 600)) / 1000.0, closed=True, fc='#4a90d9', ec='#b03030', lw=1.5,
                       label='CHD POND (pond.geojson)'))
    ax.plot(WELL[0] / 1000, WELL[1] / 1000, 'v', color='#b03030', ms=8, label='pumping well PW_1')
    for i, n, x, y, z in OBSW:
        ax.plot(x / 1000, y / 1000, 'o', mfc='white', mec='k', ms=6)
        ax.text(x / 1000 + 0.12, y / 1000 + 0.12, n, fontsize=7)
    ax.plot([], [], 'o', mfc='white', mec='k', ms=6, label='observation wells')
    if extra:
        extra(ax)
    ax.set_xlim(499.6, 508.4); ax.set_ylim(5599.6, 5606.4); ax.set_aspect(1.0)
    ax.set_xlabel('easting [km], UTM zone 11N'); ax.set_ylabel('northing [km]')
    ax.ticklabel_format(useOffset=False, style='plain')
    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1.0), fontsize=7.5, frameon=False)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ======================================================================================================================
# tutorial 6: calibration with Ostrich (DDS), a synthetic-truth experiment
# ======================================================================================================================
# the first attempt (tutorial 6, section "A first attempt"): four parameters, the gravel's among them; its record is
# committed in files/t6_calibration/finished/first_attempt/ (made with this set-up and FA_MAXITER runs)
FA_INIT = {'K_GRAVEL': 10.0, 'SY_GRAVEL': 0.10, 'K_TILL': 0.5, 'PERC_SUBSOIL': 0.02}
FA_PARS = [  # Ostrich name, key, initial, low, high, transformation
    ('par_K_gravel', 'K_GRAVEL', 10.0, 1.0, 200.0, 'log10'),
    ('par_Sy_gravel', 'SY_GRAVEL', 0.10, 0.05, 0.35, 'none'),
    ('par_K_till', 'K_TILL', 0.5, 0.05, 10.0, 'log10'),
    ('par_perc', 'PERC_SUBSOIL', 0.02, 0.005, 0.10, 'none')]
FA_MAXITER = 1000
# the calibration of the tutorial: the two conductivities the heads see, each in its own way (the sensitivity table); the
# other parameters keep the values of tutorial 2
INIT = {'K_SAND': 2.0, 'K_TILL': 0.5}
PARS = [
    ('par_K_sand', 'K_SAND', 2.0, 0.5, 50.0, 'log10'),
    ('par_K_till', 'K_TILL', 0.5, 0.05, 10.0, 'log10')]
SENS = ['K_GRAVEL', 'SY_GRAVEL', 'K_SAND', 'K_TILL', 'PERC_SUBSOIL']
MAXITER = 300
DDS_R = 0.20
FA_DDS_R = 0.20
HEAD_W = 5.0
NOISE_Q, NOISE_H = 0.05, 0.03
DUR5 = NDAYS

OSTIN_T = """# ostIn.txt - Ostrich setup: calibrate the Tutorial Creek groundwater model with DDS
ProgramType         DDS
ObjectiveFunction   GCOP
ModelExecutable     ./Ost-RAVEN.sh
PreserveBestModel   ./save_best.sh

BeginFilePairs
  Creek.rvp.tpl ; Creek.rvp
EndFilePairs

# parameters (hydraulic conductivity is searched in log10 space)
BeginParams
  #name          init    low     high    tx_in  tx_ost  tx_out
%s
EndParams

# responses: rows of Raven's Diagnostics.csv (line 0 is the header line; columns count from 1)
BeginResponseVars
  #name     filename                           keyword   line  col  token
  KGE_Q     ./model/output/Diagnostics.csv ;  OST_NULL  1     5    ','
  RMSE_101  ./model/output/Diagnostics.csv ;  OST_NULL  2     4    ','
  RMSE_102  ./model/output/Diagnostics.csv ;  OST_NULL  3     4    ','
  RMSE_103  ./model/output/Diagnostics.csv ;  OST_NULL  4     4    ','
EndResponseVars

# objective to minimise: -KGE of the streamflow + %s
BeginTiedRespVars
  COST 4 KGE_Q RMSE_101 RMSE_102 RMSE_103 wsum -1.0 %g %g %g
EndTiedRespVars

BeginGCOP
  CostFunction COST
  PenaltyFunction APM
EndGCOP

BeginConstraints
  # none; the PenaltyFunction line above is still required
EndConstraints

RandomSeed 20101

BeginDDSAlg
  PerturbationValue %.2f
  MaxIterations     %d
  UseInitialParamValues
EndDDSAlg
"""


def ostin(pars, maxiter, r, weights):
    if len(set(weights)) == 1:
        what = '%g x (head RMSE [m]) at each observation well' % weights[0]
    else:
        what = 'weight x (head RMSE [m]) at each observation well,\n# with weight = 1 / (2 x standard deviation of the well\'s observed heads)'
    return OSTIN_T % ('\n'.join('  %-14s %-7g %-7g %-7g none   %-6s  none' % (p[0], p[2], p[3], p[4], p[5]) for p in pars),
                      what, weights[0], weights[1], weights[2], r, maxiter)


def head_weights(obs_path):
    """1 / (2 x standard deviation of the observed heads of each well over the calibration years 2011-2012), 2 digits"""
    t = open(obs_path).read()
    w = []
    for wid, *_ in OBSW:
        blk = t.split(':ObservationData GW_HEAD %d m' % wid)[1].split(':End')[0].strip().split('\n')[1:]
        x = np.array([float(s) for s in blk])[365:365 + 731]
        x = x[x != -1.2345]
        w.append(float('%.2g' % (0.5 / x.std())))
    return tuple(w)


HEAD_WEIGHTS = None                     # set by tut6 from the observations (head_weights)
FA_WEIGHTS = (HEAD_W, HEAD_W, HEAD_W)   # the first attempt weighted every well alike

OST_RAVEN = """#!/bin/bash
# Ost-RAVEN.sh - runs the model once for Ostrich, which has just written Creek.rvp from Creek.rvp.tpl
set -e
cp ./Creek.rvp model/Creek.rvp
cd model
rm -f output/Diagnostics.csv          # a run that fails then stops Ostrich instead of reusing old results
"$RAVEN" Creek -o output/ > /dev/null
cd ..
exit 0
"""

SAVE_BEST = """#!/bin/bash
# save_best.sh - Ostrich runs this after every run that is the best so far
set -e
mkdir -p best
cp model/Creek.rvp               best/Creek.rvp
cp model/output/Diagnostics.csv  best/Diagnostics.csv
cp model/output/Hydrographs.csv  best/Hydrographs.csv
cp model/output/GWHeads.csv      best/GWHeads.csv
exit 0
"""

EVAL = """:EvaluationPeriod CALIBRATION 2011-01-01 2012-12-31
:EvaluationPeriod VALIDATION  2013-01-01 2014-12-31
"""


def write_observations(truth_out, path):
    """synthetic observations from the 'true' run: daily streamflow at the outlet (5% noise), weekly heads at the three
    observation wells (3 cm noise); weights 0 in the warm-up year 2010 and 1 afterwards"""
    import pandas as pd
    rs = np.random.RandomState(606)
    h = pd.read_csv(os.path.join(truth_out, 'Hydrographs.csv'))
    g = pd.read_csv(os.path.join(truth_out, 'GWHeads.csv'))
    q = h['LOWER [m3/s]'].values[1:DUR5 + 1]
    qo = q * np.exp(rs.normal(0.0, NOISE_Q, len(q)))
    w = ['%.1f' % (0.0 if i < 365 else 1.0) for i in range(DUR5)]
    L = ['# CreekObs.rvt - observed streamflow at the outlet and heads at the observation wells, 2010-2014',
         '# (synthetic: made with the true parameters of Tutorial Creek, with noise added)',
         ':ObservationData HYDROGRAPH 2 m3/s', '  %s 00:00:00 1.0 %d' % (START.isoformat(), DUR5)] + \
        ['  %.4f' % v for v in qo] + [':EndObservationData',
                                      ':ObservationWeights HYDROGRAPH 2', '  %s 00:00:00 1.0 %d' % (START.isoformat(), DUR5)] + \
        ['  ' + x for x in w] + [':EndObservationWeights']
    for wid, name, x, y, z in OBSW:
        col = [c for c in g.columns if '(%d)' % wid in c][0]
        v = g[col].values[:DUR5]
        noise = rs.normal(0.0, NOISE_H, len(v))
        L += [':ObservationData GW_HEAD %d m' % wid, '  %s 00:00:00 1.0 %d' % (START.isoformat(), DUR5)]
        L += [('  %.3f' % (v[i] + noise[i]) if i % 7 == 3 else '  -1.2345') for i in range(DUR5)]
        L += [':EndObservationData', ':ObservationWeights GW_HEAD %d' % wid, '  %s 00:00:00 1.0 %d' % (START.isoformat(), DUR5)]
        L += ['  ' + x for x in w] + [':EndObservationWeights']
    wfile(path, '\n'.join(L) + '\n')


def t6_model_files(d, pars):
    write_creek_coupled(d)
    for f in ('dem.asc', 'bedrock.asc'):
        if os.path.exists(os.path.join(d, f)):
            os.remove(os.path.join(d, f))
    wfile(os.path.join(d, 'Creek.rvp'), rvp_text(**{k: str(v) for k, v in pars.items()}))
    wfile(os.path.join(d, 'Creek.rvt'), RVT + ':RedirectToFile CreekGW.rvt\n:RedirectToFile CreekObs.rvt\n')


def diag(out):
    """Diagnostics.csv as {(series, metric): value}"""
    import pandas as pd
    t = pd.read_csv(os.path.join(out, 'Diagnostics.csv'))
    t = t.loc[:, [c for c in t.columns if not c.startswith('Unnamed')]]
    R = {}
    for _, r in t.iterrows():
        for c in t.columns[2:]:
            R[(r['observed_data_series'], c.replace('DIAG_', ''))] = float(r[c])
    return R


def cost_of(dg, period='ALL', weights=None):
    k = ('HYDROGRAPH_%s[2]' % period, 'KLING_GUPTA')
    weights = weights or HEAD_WEIGHTS
    return -dg[k] + sum(wt * dg[('GW_HEAD_%s[%d]' % (period, w[0]), 'RMSE')] for wt, w in zip(weights, OBSW))


def read_ostrich(d):
    """the run record of OstModel0.txt and the optimum of OstOutput0.txt"""
    rows = [l.split() for l in open(os.path.join(d, 'OstModel0.txt')) if l.strip()]
    hdr, data = rows[0], np.array([[float(x) for x in r] for r in rows[1:]])
    out = open(os.path.join(d, 'OstOutput0.txt')).read()
    best = {}
    blk = out.split('Optimal Parameter Set')[1].split('Summary of Constraints')[0]
    for l in blk.split('\n'):
        if ':' in l:
            k, v = [x.strip() for x in l.split(':', 1)]
            best[k] = float(v)
    return hdr, data, best, out


def ostrich_argv():
    """the Ostrich executable; one whose ELF interpreter does not exist (the Raven-Ostrich tutorial build) via ld.so"""
    exe = os.path.abspath(C.ostrich)
    try:
        r = subprocess.run(['readelf', '-l', exe], capture_output=True, text=True).stdout
        m = re.search(r'interpreter: (\S+?)\]', r)
        if m and not os.path.exists(m.group(1)):
            for ld in ('/lib64/ld-linux-x86-64.so.2', '/lib/ld-linux-x86-64.so.2'):
                if os.path.exists(ld):
                    return [ld, exe]
    except OSError:
        pass
    return [exe]


def tut6():
    t = 't6'
    log('t6: files')
    start, fin = tutfiles(t, 'start'), tutfiles(t, 'finished')
    # the "truth": tutorial 2's model, run for 2010-2014
    truth = fresh(os.path.join(C.work, 't6_truth'))
    write_creek_coupled(truth)
    edit(os.path.join(truth, 'Creek.rvi'), ':Duration           %d' % DUR3, ':Duration           %d' % DUR5)
    raven(truth)
    # start state
    if os.path.exists(start):
        shutil.rmtree(start)
    t6_model_files(os.path.join(start, 'model'), INIT)
    write_observations(os.path.join(truth, 'out'), os.path.join(start, 'model', 'CreekObs.rvt'))
    tpl = rvp_text(K_SAND='par_K_sand', K_TILL='par_K_till')
    wfile(os.path.join(start, 'Creek.rvp.tpl'), tpl)
    global HEAD_WEIGHTS
    HEAD_WEIGHTS = head_weights(os.path.join(start, 'model', 'CreekObs.rvt'))
    wfile(os.path.join(start, 'ostIn.txt'), ostin(PARS, MAXITER, DDS_R, HEAD_WEIGHTS))
    wfile(os.path.join(start, 'Ost-RAVEN.sh'), OST_RAVEN)
    wfile(os.path.join(start, 'save_best.sh'), SAVE_BEST)
    for f in ('Ost-RAVEN.sh', 'save_best.sh'):
        os.chmod(os.path.join(start, f), 0o755)
    G.text('t6_obs_head.txt', '$ head -n 7 model/CreekObs.rvt\n' + ''.join(open(os.path.join(start, 'model', 'CreekObs.rvt')).readlines()[:7]))
    G.text('t6_rvt.diff', udiff(RVT + ':RedirectToFile CreekGW.rvt\n', open(os.path.join(start, 'model', 'Creek.rvt')).read(), 'Creek.rvt (tutorial 2)', 'model/Creek.rvt', 1))
    G.text('t6_tpl.diff', udiff(open(os.path.join(start, 'model', 'Creek.rvp')).read(), tpl, 'model/Creek.rvp', 'Creek.rvp.tpl', 0))
    G.val('t6:maxiter', '%d' % MAXITER)
    G.val('t6:headw', '%g' % HEAD_W)
    for wt, (wid, *_) in zip(HEAD_WEIGHTS, OBSW):
        G.val('t6:w%d' % wid, '%g' % wt)
    G.val('t6:noiseq', '%d' % round(100 * NOISE_Q))
    G.val('t6:noiseh', '%d' % round(100 * NOISE_H))

    # step 1: the initial parameter set, run by hand
    w = copytree(start, os.path.join(C.work, 't6'))
    uw = U_WORK + '/t6'
    ex, dt, _ = raven(os.path.join(w, 'model'), 'output', 't6_run_init.txt', ucwd=uw + '/model')
    G.val('t6:runsec', '%d' % max(1, round(dt)), volatile=True)
    G.text('t6_diag_init.txt', '$ cat output/Diagnostics.csv\n' + open(os.path.join(w, 'model', 'output', 'Diagnostics.csv')).read())
    d0 = diag(os.path.join(w, 'model', 'output'))
    G.val('t6:kgeInit', fmt(d0[('HYDROGRAPH_ALL[2]', 'KLING_GUPTA')], 3))
    for wid, n, *_ in OBSW:
        G.val('t6:rmseInit%d' % wid, fmt(d0[('GW_HEAD_ALL[%d]' % wid, 'RMSE')], 2))
    G.val('t6:costInit', fmt(cost_of(d0), 3))

    # which parameters do the observations see? the objective at the true parameters, each changed by -10% and +10%
    log('t6: sensitivity')
    s = os.path.join(C.work, 't6_sensitivity')
    base = None
    sens_rows = {}
    for key in [None] + SENS:
        for f in ((1.0,) if key is None else (0.9, 1.1)):
            d = copytree(os.path.join(start, 'model'), s)
            pr = {k: str(v) for k, v in TRUE.items()}
            if key:
                pr[key] = '%.6g' % (TRUE[key] * f)
            wfile(os.path.join(d, 'Creek.rvp'), rvp_text(**pr))
            raven(d, 'output')
            dg_ = diag(os.path.join(d, 'output'))
            c = cost_of(dg_)
            sens_rows[(key, f)] = (dg_[('HYDROGRAPH_ALL[2]', 'KLING_GUPTA')],
                                   [dg_[('GW_HEAD_ALL[%d]' % ow[0], 'RMSE')] for ow in OBSW], c)
            if key is None:
                base = c
                G.val('t6:sens:base', fmt(c, 3))
                G.val('t6:fa:costtrue', fmt(cost_of(dg_, weights=FA_WEIGHTS), 3))
            else:
                G.val('t6:sens:%s:%s' % (key, 'lo' if f < 1 else 'hi'), fmt(c - base, 3, sign=True))
    shutil.rmtree(s)
    for key in SENS:
        G.val('t6:true' + key, sig(TRUE[key]))
    # the same, per series: the change of the KGE, of each well's head RMSE [mm] and of the objective
    lab = {'K_GRAVEL': '$K_h$ GRAVEL', 'SY_GRAVEL': '$S_y$ GRAVEL', 'K_SAND': '$K_h$ SAND', 'K_TILL': '$K_h$ TILL',
           'PERC_SUBSOIL': '\\cmd{PERC\\_COEFF}'}
    k0, r0, c0 = sens_rows[(None, 1.0)]
    G.val('t6:sens:kge', fmt(k0, 3))
    for ow, r in zip(OBSW, r0):
        G.val('t6:sens:rmse%d' % ow[0], fmt(r * 1000.0, 0))
    rows = []
    for key in SENS:
        for f in (0.9, 1.1):
            kg, rr, c = sens_rows[(key, f)]
            rows.append(' & '.join([lab[key], '$-$10\\%' if f < 1 else '+10\\%', fmt(kg - k0, 3, sign=True)] +
                                   [fmt((x - y) * 1000.0, 0, sign=True) for x, y in zip(rr, r0)] + [fmt(c - c0, 3, sign=True)]) + '\\\\')
            G.val('t6:sens:%s:%s:slope' % (key, 'lo' if f < 1 else 'hi'), fmt(rr[2], 2))
        if key != SENS[-1]:
            rows[-1] += '[2pt]'
    G.text('t6_sens_table.tex', '\n'.join(
        ['\\begin{tabular}{llrrrrr}\\toprule',
         ' & & & \\multicolumn{3}{c}{change of the head RMSE [mm]} & \\\\\\cmidrule(lr){4-6}',
         'Parameter & change & KGE & OW\\_NEAR & OW\\_UPPER & OW\\_SLOPE & objective\\\\\\midrule'] + rows +
        ['\\bottomrule', '\\end{tabular}']))
    d_sand = [(sens_rows[('K_SAND', f)][1][2] - r0[2]) * 100.0 for f in (0.9, 1.1)]
    G.val('t6:sens:sandslopemin', fmt(min(d_sand), 1)); G.val('t6:sens:sandslopemax', fmt(max(d_sand), 1))
    # the spread of the observed heads of each well over the calibration years (max - min) [cm]
    ot = open(os.path.join(start, 'model', 'CreekObs.rvt')).read()
    for ow in OBSW:
        blk = ot.split(':ObservationData GW_HEAD %d m' % ow[0])[1].split(':End')[0].strip().split('\n')[1:]
        x = np.array([float(v) for v in blk])[365:365 + 731]
        x = x[x != -1.2345]
        G.val('t6:swing%d' % ow[0], fmt((x.max() - x.min()) * 100.0, 0))
        G.val('t6:swingm%d' % ow[0], fmt(x.max() - x.min(), 1))

    # step 2: DDS (or, without Ostrich or with --quick, the committed record of the last DDS run). The record of the first
    # attempt (four parameters, FA_MAXITER runs; section "A first attempt") is always the committed one.
    RECORD = ('OstOutput0.txt', 'OstModel0.txt', 'best/Creek.rvp', 'best/Diagnostics.csv')
    FA_RECORD = ('first_attempt/OstOutput0.txt', 'first_attempt/OstModel0.txt')
    committed = os.path.join(FILES, TDIR[t], 'finished')
    saved = {}
    for f in FA_RECORD:
        pth = os.path.join(committed, f)
        if not os.path.exists(pth):
            raise RuntimeError('t6: no committed record of the first attempt (%s)' % pth)
        saved[f] = open(pth).read()
    if C.ostrich and not C.quick:
        log('t6: Ostrich DDS, %d runs (about %d minutes)' % (MAXITER, MAXITER * dt / 60 + 1))
        shutil.rmtree(os.path.join(w, 'model', 'output'))
        out, dts = run(ostrich_argv(), w, '$OSTRICH', None, timeout=4 * 3600)
        G.val('t6:ddsmin', '%d' % round(dts / 60.0), volatile=True)
        for f in RECORD:
            saved[f] = open(os.path.join(w, f)).read()
    else:
        for f in RECORD:
            pth = os.path.join(committed, f)
            if not os.path.exists(pth):
                raise RuntimeError('t6: no committed record of the calibration (%s): run with --ostrich, without --quick' % pth)
            saved[f] = open(pth).read()
        m = re.search(r'\\defval\{t6:ddsmin\}\{(\d+)\}', open(os.path.join(GEN, 'values.tex')).read()) \
            if os.path.exists(os.path.join(GEN, 'values.tex')) else None
        G.val('t6:ddsmin', m.group(1) if m else '?', volatile=True)
    if os.path.exists(fin):
        shutil.rmtree(fin)
    copytree(start, fin)
    for f, s_ in saved.items():
        wfile(os.path.join(fin, f), s_)
    wfile(os.path.join(fin, 'first_attempt', 'ostIn.txt'), ostin(FA_PARS, FA_MAXITER, FA_DDS_R, FA_WEIGHTS))
    wfile(os.path.join(fin, 'first_attempt', 'Creek.rvp.tpl'),
          rvp_text(K_GRAVEL='par_K_gravel', SY_GRAVEL='par_Sy_gravel', K_TILL='par_K_till', PERC_SUBSOIL='par_perc'))
    # the first attempt
    fh, fdata, fbest, fout = read_ostrich(os.path.join(fin, 'first_attempt'))
    fobj = fdata[:, 1]
    G.val('t6:fa:nevals', '%d' % len(fobj)); G.val('t6:fa:maxiter', '%d' % FA_MAXITER)
    G.val('t6:fa:cost', fmt(fbest['Objective Function'], 3))
    G.val('t6:fa:itBest', '%d' % (int(np.argmin(fobj)) + 1))
    kt = fdata[:, fh.index('par_K_till')]
    bkt = [kt[int(np.argmin(fobj[:i + 1]))] for i in range(len(fobj))]
    G.val('t6:fa:ktfrom', '%d' % (next(i for i in range(len(bkt)) if all(abs(x - bkt[-1]) < 1e-12 for x in bkt[i:])) + 1))
    for p in FA_PARS:
        G.val('t6:fa:init' + p[1], sig(p[2]))
        G.val('t6:fa:best' + p[1], sig(fbest[p[0]]))
        G.val('t6:fa:err' + p[1], fmt(100.0 * (fbest[p[0]] / TRUE[p[1]] - 1.0), 0, sign=True))
    fo = ostin(FA_PARS, FA_MAXITER, FA_DDS_R, FA_WEIGHTS)
    G.text('t6_fa_params.txt', '$ grep -A%d BeginParams first_attempt/ostIn.txt\n' % (len(FA_PARS) + 2) +
           fo[fo.index('BeginParams'):fo.index('EndParams') + len('EndParams')])
    hdr, data, best, ostout = read_ostrich(fin)
    G.val('t6:ostver', re.search(r'OSTRICH version ([0-9.]+)', ostout).group(1))
    G.text('t6_ostout.txt', excerpt(ostout, [r'OSTRICH version', r'^Model\s+:', r'^Algorithm\s+:', r'^Number of Parameters',
                                              r'^Seed', r'^Optimal Parameter Set', r'^Objective Function :', r'^par_',
                                              r'^Actual Generations', r'^Total Evals']))
    rr = ostout.split('Ostrich Run Record')[1].split('Optimal Parameter Set')[0].strip().split('\n')
    G.text('t6_runrecord.txt', '\n'.join(rr[:6] + ['...'] + rr[-4:]))
    obj = data[:, 1]
    bestsofar = np.minimum.accumulate(obj)
    G.val('t6:nevals', '%d' % len(obj))
    G.val('t6:costBest', fmt(best['Objective Function'], 3))
    ibest = int(np.argmin(obj)) + 1
    G.val('t6:itBest', '%d' % ibest)
    for frac, key in ((0.95, 'ninetyfive'),):
        tgt = obj[0] - frac * (obj[0] - bestsofar[-1])
        G.val('t6:it' + key, '%d' % (int(np.argmax(bestsofar <= tgt)) + 1))
    for p in PARS:
        G.val('t6:init' + p[1], sig(p[2]))
        G.val('t6:true' + p[1], sig(TRUE[p[1]]))
        G.val('t6:best' + p[1], sig(best[p[0]]))
        G.val('t6:err' + p[1], fmt(100.0 * (best[p[0]] / TRUE[p[1]] - 1.0), 0, sign=True))
        G.val('t6:low' + p[1], sig(p[3])); G.val('t6:high' + p[1], sig(p[4]))
    # the best .rvp must be the template with the optimum
    bestrvp = open(os.path.join(fin, 'best', 'Creek.rvp')).read()
    # convergence figure
    plt = plt_()
    fig, ax = plt.subplots(1, 2, figsize=(9.2, 3.4))
    ax[0].plot(np.arange(1, len(obj) + 1), obj, '.', ms=3, color='#9db8d9', label='each run')
    ax[0].plot(np.arange(1, len(obj) + 1), bestsofar, '-', color='#1f4e79', lw=1.6, label='best so far')
    ax[0].plot(np.arange(1, len(fobj) + 1), np.minimum.accumulate(fobj), '-', color='0.6', lw=1.2, label='best so far, first attempt')
    ax[0].set_ylim(min(obj) - 0.1, min(max(obj), obj[0] + 1.0) + 0.2)
    ax[0].set_xlabel('model run'); ax[0].set_ylabel('objective COST'); ax[0].legend(); ax[0].set_title('DDS convergence')
    for k, p in enumerate(PARS):
        v = data[:, hdr.index(p[0])]
        bi = np.minimum.accumulate(obj)
        bv = [v[int(np.argmin(obj[:i + 1]))] for i in range(len(obj))]
        rel = np.array(bv) / TRUE[p[1]]
        ax[1].plot(np.arange(1, len(obj) + 1), rel, lw=1.4, label=p[0])
    ax[1].axhline(1.0, color='k', lw=0.6, ls='--')
    ax[1].set_yscale('log'); ax[1].set_xlabel('model run'); ax[1].set_ylabel('best parameter / true value')
    ax[1].set_title('parameters of the best run so far'); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(figpath('t6_convergence.png'), dpi=150); plt.close(fig)

    # step 3: validation of the best parameter set on 2013-2014
    log('t6: validation')
    vfin = os.path.join(fin, 'validation')
    copytree(os.path.join(fin, 'model'), vfin)
    shutil.copy(os.path.join(fin, 'best', 'Creek.rvp'), os.path.join(vfin, 'Creek.rvp'))
    rvi = open(os.path.join(vfin, 'Creek.rvi')).read()
    rvi2 = rvi.replace(':Duration           %d' % DUR3, ':Duration           %d' % DUR5).replace(':EvaluationMetrics', EVAL + ':EvaluationMetrics')
    wfile(os.path.join(vfin, 'Creek.rvi'), rvi2)
    G.text('t6_valid_rvi.diff', udiff(rvi, rvi2, 'model/Creek.rvi', 'validation/Creek.rvi', 1))
    v = copytree(vfin, os.path.join(C.work, 't6_validation'))
    raven(v, 'output', 't6_run_valid.txt', ucwd=uw + '/validation')
    G.text('t6_diag_valid.txt', '$ cat output/Diagnostics.csv\n' + open(os.path.join(v, 'output', 'Diagnostics.csv')).read())
    dv = diag(os.path.join(v, 'output'))
    for per in ('CALIBRATION', 'VALIDATION'):
        P = per[:5].lower()
        G.val('t6:kge' + P, fmt(dv[('HYDROGRAPH_%s[2]' % per, 'KLING_GUPTA')], 3))
        G.val('t6:nse' + P, fmt(dv[('HYDROGRAPH_%s[2]' % per, 'NASH_SUTCLIFFE')], 3))
        for wid, n, *_ in OBSW:
            G.val('t6:rmse%s%d' % (P, wid), fmt(dv[('GW_HEAD_%s[%d]' % (per, wid), 'RMSE')], 3))
        G.val('t6:cost' + P, fmt(cost_of(dv, per), 3))
    # the same with the true and the initial parameters (for the figure and the comparison)
    for lab, pars in (('true', TRUE), ('init', INIT)):
        d = copytree(vfin, os.path.join(C.work, 't6_validation_' + lab))
        wfile(os.path.join(d, 'Creek.rvp'), rvp_text(**{k: str(x) for k, x in pars.items()}))
        raven(d, 'output')
        dd = diag(os.path.join(d, 'output'))
        for per in ('CALIBRATION', 'VALIDATION'):
            P = per[:5].lower()
            G.val('t6:kge%s%s' % (P, lab), fmt(dd[('HYDROGRAPH_%s[2]' % per, 'KLING_GUPTA')], 3))
            G.val('t6:cost%s%s' % (P, lab), fmt(cost_of(dd, per), 3))
            for wid, n, *_ in OBSW:
                G.val('t6:rmse%s%d%s' % (P, wid, lab), fmt(dd[('GW_HEAD_%s[%d]' % (per, wid), 'RMSE')], 3))
    # figure: observed and simulated streamflow and heads, validation years
    import pandas as pd
    obs = open(os.path.join(vfin, 'CreekObs.rvt')).read()

    def series(tag):
        blk = obs.split(tag)[1].split(':End')[0].strip().split('\n')[1:]
        x = np.array([float(s) for s in blk])
        return np.where(x == -1.2345, np.nan, x)
    dates = pd.date_range(START.isoformat(), periods=DUR5, freq='D')
    fig, ax = plt.subplots(4, 1, figsize=(9.2, 8.4), sharex=True)
    qo = series(':ObservationData HYDROGRAPH 2 m3/s')
    ax[0].plot(dates, qo, color='0.55', lw=0.8, label='observed')
    for lab, d, c in (('initial', 't6_validation_init', '#d08a2b'), ('calibrated', 't6_validation', '#1f4e79')):
        h = hydro(os.path.join(C.work, d, 'output'))
        ax[0].plot(h['date'] - pd.Timedelta(days=1), h['q'], color=c, lw=0.9, label=lab)
    ax[0].set_ylabel('m$^3$/s'); ax[0].set_title('streamflow at the outlet (subbasin 2)'); ax[0].legend(ncol=3)
    for k, (wid, n, *_) in enumerate(OBSW):
        ho = series(':ObservationData GW_HEAD %d m' % wid)
        a = ax[k + 1]
        a.plot(dates, ho, 'o', ms=2.2, color='0.45', label='observed')
        for lab, d, c in (('initial', 't6_validation_init', '#d08a2b'), ('calibrated', 't6_validation', '#1f4e79')):
            g = gwheads(os.path.join(C.work, d, 'output'))
            col = [c2 for c2 in g.columns if '(%d)' % wid in c2][0]
            a.plot(pd.to_datetime(g['date']), g[col], color=c, lw=0.9, label=lab)
        a.set_ylabel('head [m]'); a.set_title('%s (%d)' % (n, wid))
    for a in ax:
        a.axvspan(pd.Timestamp('2010-01-01'), pd.Timestamp('2011-01-01'), color='0.93', lw=0)
        a.axvline(pd.Timestamp('2013-01-01'), color='k', lw=0.6, ls='--')
    ax[0].text(pd.Timestamp('2010-02-01'), np.nanmax(qo) * 0.92, 'warm-up', fontsize=8)
    ax[0].text(pd.Timestamp('2011-02-01'), np.nanmax(qo) * 0.92, 'calibration', fontsize=8)
    ax[0].text(pd.Timestamp('2013-02-01'), np.nanmax(qo) * 0.92, 'validation', fontsize=8)
    fig.tight_layout(); fig.savefig(figpath('t6_validation.png'), dpi=150); plt.close(fig)




# ======================================================================================================================
# tutorial 3: the soil-zone coupling
# ======================================================================================================================
SOIL_OLD = """  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HBV_BETA, MAX_PERC_RATE, PERC_COEFF, BASEFLOW_COEFF
  :Units,      none,     none,           none,     none,     mm/d,          1/d,        1/d
  TOPSOIL,     0.45,     0.30,           0.10,     2.0,      20.0,          0.0,        0.0
  SUBSOIL,     0.40,     0.25,           0.10,     2.0,      0.0,           0.04,       0.01
  DEEP,        0.30,     0.05,           0.0,      1.0,      0.0,           0.0,        0.005
"""
SOIL_NEW = """  :Parameters, POROSITY, FIELD_CAPACITY, SAT_WILT, HBV_BETA, MAX_PERC_RATE, PERC_COEFF, BASEFLOW_COEFF, HYDRAUL_COND, CLAPP_B, AIR_ENTRY_PRESSURE
  :Units,      none,     none,           none,     none,     mm/d,          1/d,        1/d,            mm/d,         none,    mm
  TOPSOIL,     0.45,     0.30,           0.10,     2.0,      20.0,          0.0,        0.0,            500.0,        5.0,     100.0
  SUBSOIL,     0.40,     0.25,           0.10,     2.0,      0.0,           0.04,       0.01,           200.0,        6.0,     200.0
  DEEP,        0.30,     0.05,           0.0,      1.0,      0.0,           0.0,        0.005,          50.0,         4.0,     300.0
"""
AQ_OLD = """  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY
  :Units,      m/d,     m/d,    1/m,          none,       none
  GRAVEL,      40.0,    4.0,    1.0E-5,       0.20,       0.30
  SAND,        8.0,     0.8,    1.0E-5,       0.15,       0.32
  TILL,        2.0,     0.2,    1.0E-4,       0.08,       0.30
"""
AQ_NEW = """  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY, CLAPP_B, AIR_ENTRY_PRESSURE
  :Units,      m/d,     m/d,    1/m,          none,       none,     none,    m
  GRAVEL,      40.0,    4.0,    1.0E-5,       0.20,       0.30,     3.0,     0.15
  SAND,        8.0,     0.8,    1.0E-5,       0.15,       0.32,     4.0,     0.25
  TILL,        2.0,     0.2,    1.0E-4,       0.08,       0.30,     5.0,     0.30
"""
T3_RUNS = [('out_conceptual', 'CONCEPTUAL'), ('out_physical', 'PHYSICAL'), ('out_richards', 'RICHARDS'),
           ('out_kinematic', 'KINEMATIC'), ('out_lag', 'LAG'), ('out_classes', 'RICHARDS, 3 depth classes')]


def t3_metrics(out):
    sys.path.insert(0, SCRIPTS)
    import compare_runs
    return compare_runs.metrics(out, [6, 7])


def lag_days(b):
    """the lag [d] at which the recharge leaving the unsaturated columns correlates best with what enters them"""
    if 'unsaturated zone inflow [m3]' not in b:
        return None
    x = b['unsaturated zone inflow [m3]'].values; y = b['unsaturated zone to aquifer [m3]'].values
    x, y = x - x.mean(), y - y.mean()
    cc = [np.corrcoef(x[:len(x) - k], y[k:])[0, 1] for k in range(0, 250)]
    return int(np.argmax(cc))


def tut3():
    t = 't3'
    start, fin = tutfiles(t, 'start'), tutfiles(t, 'finished')
    for d in (start, fin):
        if os.path.exists(d):
            shutil.rmtree(d)
    write_creek_coupled(start)
    write_creek_coupled(fin)
    rvp0 = open(os.path.join(start, 'Creek.rvp')).read()
    rvp1 = rvp0.replace(SOIL_OLD, SOIL_NEW)
    rvp2 = rvp1.replace(AQ_OLD, AQ_NEW)
    assert rvp1 != rvp0 and rvp2 != rvp1
    rvg0 = open(os.path.join(start, 'Creek.rvg')).read()
    SZ = ('\n# --- the soil zone and the water table ---------------------------------------------\n'
          ':SoilZone          PHYSICAL SOIL[0] SOIL[1]        # Raven owns TOPSOIL and SUBSOIL; MODFLOW starts below them\n')
    rvg1 = rvg0 + SZ
    VZ = ':SoilZoneVadose    RICHARDS                        # unsaturated columns between the soil zone and a deeper water table\n'
    rvg2 = rvg1 + VZ
    CL = ':SoilZoneVadoseClasses 3                           # one column per depth class of the DEM points in a cell\n'
    rvg_k = rvg2.replace('RICHARDS                        #', 'KINEMATIC                       #')
    rvg_l = rvg2.replace('RICHARDS                        #', 'LAG                             #')
    rvg3 = rvg2 + CL
    wfile(os.path.join(fin, 'Creek.rvp'), rvp2)
    wfile(os.path.join(fin, 'Creek.rvg'), rvg3)
    G.text('t3_soil.diff', udiff(rvp0, rvp1, 'Creek.rvp', 'Creek.rvp', 0))
    G.text('t3_physical.diff', udiff(rvg0, rvg1, 'Creek.rvg', 'Creek.rvg', 0))
    G.text('t3_aquifer.diff', udiff(rvp1, rvp2, 'Creek.rvp', 'Creek.rvp', 0))
    G.text('t3_richards.diff', udiff(rvg1, rvg2, 'Creek.rvg', 'Creek.rvg', 0))
    G.text('t3_kinematic.diff', udiff(rvg2, rvg_k, 'Creek.rvg', 'Creek.rvg', 0))
    G.text('t3_lag.diff', udiff(rvg_k, rvg_l, 'Creek.rvg', 'Creek.rvg', 0))
    G.text('t3_classes.diff', udiff(rvg_l, rvg3, 'Creek.rvg', 'Creek.rvg', 0))
    w = copytree(start, os.path.join(C.work, 't3'))
    uw = U_WORK + '/t3'
    secs = {}
    # the runs, in the order of the tutorial
    for out, rvp, rvg, name in (('out_conceptual', rvp0, rvg0, 't3_run_conceptual.txt'), ('out_physical', rvp1, rvg1, 't3_run_physical.txt'),
                                ('out_richards', rvp2, rvg2, 't3_run_richards.txt'), ('out_kinematic', rvp2, rvg_k, None),
                                ('out_lag', rvp2, rvg_l, None), ('out_classes', rvp2, rvg3, None)):
        wfile(os.path.join(w, 'Creek.rvp'), rvp)
        wfile(os.path.join(w, 'Creek.rvg'), rvg)
        log('t3: ' + out)
        ex, dt, so = raven(w, out, name, ucwd=uw)
        secs[out] = dt
        G.val('t3:sec' + out.split('_')[1], '%d' % max(1, round(dt)), volatile=True)
    # warnings of the soil-zone run
    errs = open(os.path.join(w, 'out_physical', 'Raven_errors.txt')).read()
    G.text('t3_warnings.txt', '$ grep WARNING out_physical/Raven_errors.txt\n' + sanitize(''.join(l for l in errs.splitlines(True) if l.startswith('WARNING')), w, uw))
    errs2 = open(os.path.join(w, 'out_richards', 'Raven_errors.txt')).read()
    G.val('t3:nwarnRich', '%d' % sum(1 for l in errs2.splitlines() if l.startswith('WARNING')))
    G.val('t3:nwarn', '%d' % sum(1 for l in errs.splitlines() if l.startswith('WARNING')))
    m = re.search(r'soil zone\s*:\s*PHYSICAL, SOIL\[0\.\.1\]; (\d+) HRUs with a soil zone, (\d+) without', summary_text(os.path.join(w, 'out_physical')))
    G.val('t3:nszhru', m.group(1)); G.val('t3:nnosz', m.group(2))
    m = re.search(r'on (\d+) links the soil-zone base of the HRU lies up to ([0-9.]+) m', errs)
    G.val('t3:offlinks', m.group(1) if m else '?'); G.val('t3:offmax', fmt(float(m.group(2)), 2) if m else '?')
    m = re.search(r'on (\d+) links the specific yield .* \(ratio ([0-9.]+) to ([0-9.]+)\)', errs)
    G.val('t3:sylinks', m.group(1) if m else '?')
    G.val('t3:syratio', fmt(float(m.group(2)), 2) if m else '?')
    s = summary_text(os.path.join(w, 'out_physical'))
    G.text('t3_summary.txt', '$ grep -A6 "soil zone  " out_physical/GWModelSummary.txt\n' +
           excerpt(s, [r'^\s+soil zone\s+:', r'^\s+soil-zone thickness', r'^\s+soil-zone links', r'^\s+interface iteration', r'^\s+soil-zone columns']))
    s2 = summary_text(os.path.join(w, 'out_richards'))
    G.text('t3_summary_rich.txt', '$ grep -i "unsaturated" out_richards/GWModelSummary.txt\n' +
           excerpt(s2, [r'(?i)unsaturated'], drop=r'computed in'))
    G.text('t3_soilex_head.txt', '$ head -n 3 out_physical/GWSoilExchange.csv | cut -d, -f1-9\n' +
           '\n'.join(','.join(l.rstrip('\n').split(',')[:9]) for l in open(os.path.join(w, 'out_physical', 'GWSoilExchange.csv')).readlines()[:3]))
    # the comparison, with the tutorial's script
    disp = 'python3 $TUT/scripts/compare_runs.py ' + ' '.join(o for o, _ in T3_RUNS) + ' --hrus 7 6'
    run([sys.executable, os.path.join(SCRIPTS, 'compare_runs.py')] + [o for o, _ in T3_RUNS] + ['--hrus', '7', '6',
        '--png', 'compare_runs.png'], w, disp, 't3_compare.txt', ucwd=uw)
    shutil.copy(os.path.join(w, 'compare_runs.png'), figpath('t3_compare.png'))
    M = {o: t3_metrics(os.path.join(w, o)) for o, _ in T3_RUNS}
    for o, lab in T3_RUNS:
        k = o.split('_')[1]
        mm = M[o]
        G.val('t3:%s:leaves' % k, fmt(mm['leaves soil'], 0)); G.val('t3:%s:reaches' % k, fmt(mm['reaches WT'], 0))
        G.val('t3:%s:rejected' % k, fmt(mm['rejected'], 0)); G.val('t3:%s:aqsoil' % k, fmt(mm['aq->soil'], 0))
        G.val('t3:%s:seep' % k, fmt(mm['seepage'], 0)); G.val('t3:%s:toriv' % k, fmt(mm['to rivers'], 0))
        G.val('t3:%s:uz' % k, fmt(mm['UZ storage end'] / 1e6, 1)); G.val('t3:%s:wt7' % k, fmt(mm['WT depth 7'], 1))
        G.val('t3:%s:wt6' % k, fmt(mm['WT depth 6'], 2)); G.val('t3:%s:q' % k, fmt(mm['Q outlet'], 3))
        b = budget(os.path.join(w, o))
        lg = lag_days(b)
        if lg is not None:
            G.val('t3:%s:lag' % k, '%d' % lg)
    A = sum(area(r) for i, sb, kk, r in HRUS if AQ_OF.get(i) == 'SLOPE_TILL')
    G.val('t3:uzmm', fmt(M['out_richards']['UZ storage end'] / A * 1000.0, 0))
    G.val('t3:slopearea', fmt(A / 1e6, 1))
    br = budget(os.path.join(w, 'out_richards'))
    uin, uout = br['unsaturated zone inflow [m3]'].sum(), br['unsaturated zone to aquifer [m3]'].sum()
    G.val('t3:withheld', fmt(100.0 * (uin - uout) / uin, 0))
    G.val('t3:wtdrop', fmt(M['out_richards']['WT depth 7'] - M['out_physical']['WT depth 7'], 1))
    # GWSoilExchange of the valley HRU 6
    import pandas as pd
    se = pd.read_csv(os.path.join(w, 'out_physical', 'GWSoilExchange.csv'))
    s6 = se[se['HRU_ID'] == 6]
    G.val('t3:F6mean', fmt(s6['saturated fraction [-]'].mean(), 2)); G.val('t3:F6max', fmt(s6['saturated fraction [-]'].max(), 2))
    G.val('t3:F6min', fmt(s6['saturated fraction [-]'].min(), 2))
    # the package's plotting tool
    tool = os.path.join(C.tools, 'plot_soilzone.py')
    run([sys.executable, tool, 'out_physical', '6', '1', '--png', 'soilzone.png'], w,
        'python3 $TOOLS/plot_soilzone.py out_physical 6 1 --png soilzone.png', 't3_plot_soilzone.txt', ucwd=uw)
    shutil.copy(os.path.join(w, 'soilzone.png'), figpath('t3_soilzone.png'))
    # the unsaturated columns: what goes in and what reaches the water table
    plt = plt_()
    fig, ax = plt.subplots(2, 1, figsize=(8.6, 5.4), sharex=True)
    for o, lab, c in (('out_richards', 'RICHARDS', '#1f4e79'), ('out_kinematic', 'KINEMATIC', '#2e8b57'), ('out_lag', 'LAG', '#d08a2b')):
        b = budget(os.path.join(w, o))
        if o == 'out_richards':
            ax[0].plot(b['date'], b['unsaturated zone inflow [m3]'].rolling(30, min_periods=1).mean() / 1000.0, color='0.5', lw=1.0, label='into the columns')
        ax[0].plot(b['date'], b['unsaturated zone to aquifer [m3]'].rolling(30, min_periods=1).mean() / 1000.0, color=c, lw=1.0, label='to the water table, ' + lab)
        ax[1].plot(b['date'], b['unsaturated zone storage [m3]'] / 1e6, color=c, lw=1.2, label=lab)
    ax[0].set_ylabel('1000 m$^3$/d'); ax[0].set_title('unsaturated columns: inflow and outflow to the aquifer, 30-day means'); ax[0].legend(fontsize=7)
    ax[1].set_ylabel('million m$^3$'); ax[1].set_title('water stored in the unsaturated columns'); ax[1].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(figpath('t3_vadose.png'), dpi=150); plt.close(fig)
    for o, _ in T3_RUNS:
        if o != 'out_physical':
            shutil.rmtree(os.path.join(w, o, 'mf6'), ignore_errors=True)



# ======================================================================================================================
# tutorial 4: coupling an existing MODFLOW 6 model
# ======================================================================================================================
RVG_EXT = """# Creek.rvg - Raven coupled to an existing MODFLOW 6 model of Tutorial Creek
:InputCRS          EPSG:32611                  # hrus.geojson is in UTM zone 11N
:HRUGeometry       hrus.geojson  HRU_ID        # HRU polygons; HRU_ID matches the .rvh
:MF6Simulation     model/mfsim.nam             # the existing simulation (Raven runs a copy in out/mf6/)
:MF6CRS            EPSG:32611                  # projection of the model's coordinates (here in feet)
:MF6StartDate      2010-01-01                  # calendar date of the model's time zero
:RavenTakesOver    RCH_MODEL EVT_MODEL         # Raven supplies the recharge; the model's own ET is removed
:StreamPackage     RIV_CREEK AUX SUBBASIN      # river cells: their flows go to the Raven subbasin in SUBBASIN
:SeepageToRaven    ON                          # groundwater seeping out at the top returns to Raven
"""
RVP_EXT = """
# --- groundwater: the layers and properties come from the MODFLOW 6 model --------
:AquiferProfiles
  VALLEY_FILL, 0
  SLOPE_TILL,  0
:EndAquiferProfiles

:AquiferProfileParameters
  :Attributes, SEEPAGE_LEAKANCE
  :Units,      1/d
  VALLEY_FILL, 1.0
  SLOPE_TILL,  1.0
:EndAquiferProfileParameters
"""
RVP_EXT_ET = """
# --- groundwater: the layers and properties come from the MODFLOW 6 model --------
:AquiferProfiles
  VALLEY_FILL, 0
  SLOPE_TILL,  0
:EndAquiferProfiles

:AquiferProfileParameters
  :Attributes, SEEPAGE_LEAKANCE, EXTINCTION_DEPTH
  :Units,      1/d,              m
  VALLEY_FILL, 1.0,              1.5
  SLOPE_TILL,  1.0,              1.5
:EndAquiferProfileParameters
"""


def tut4():
    t = 't4'
    start, fin = tutfiles(t, 'start'), tutfiles(t, 'finished')
    for d in (start, fin):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(start)
    write_geometry(start)
    for f in ('rivers.geojson', 'outlet.geojson', 'pond.geojson'):
        os.remove(os.path.join(start, f))
    write_forcing(os.path.join(start, 'CreekMet.rvt'))
    wfile(os.path.join(start, 'Creek.rvi'), RVI % DUR3)
    wfile(os.path.join(start, 'Creek.rvp'), rvp_text(gw=False))
    wfile(os.path.join(start, 'Creek.rvh'), rvh_text())
    wfile(os.path.join(start, 'Creek.rvc'), RVC)
    wfile(os.path.join(start, 'Creek.rvt'), RVT)
    info = write_existing_model(os.path.join(start, 'model'))
    G.val('t4:nper', '%d' % info['periods']); G.val('t4:nriv', '%d' % info['riv']); G.val('t4:nghb', '%d' % info['ghb'])
    G.val('t4:cellft', fmt(EXT_DX, 0)); G.val('t4:cellm', fmt(EXT_DX * 0.3048, 1))
    G.val('t4:nrow', '%d' % EXT_NROW); G.val('t4:ncol', '%d' % EXT_NCOL)
    G.text('t4_ls_model.txt', '$ ls model\n' + '  '.join(sorted(os.listdir(os.path.join(start, 'model')))))
    G.text('t4_nam.txt', '$ cat model/creek.nam\n' + open(os.path.join(start, 'model', 'creek.nam')).read())
    G.text('t4_dis_head.txt', '$ head -n 6 model/creek.dis\n' + ''.join(open(os.path.join(start, 'model', 'creek.dis')).readlines()[:6]))
    G.text('t4_riv_head.txt', '$ head -n 12 model/creek.riv\n' + ''.join(open(os.path.join(start, 'model', 'creek.riv')).readlines()[:12]))
    G.text('t4_tdis_head.txt', '$ head -n 12 model/creek.tdis\n' + ''.join(open(os.path.join(start, 'model', 'creek.tdis')).readlines()[:12]))
    # stage A: couple
    A = {'Creek.rvh': rvh_text(AQ_OF, group=True), 'Creek.rvi': rvi_coupled(), 'Creek.rvp': rvp_text(gw=False) + RVP_EXT,
         'Creek.rvg': RVG_EXT}
    w = copytree(start, os.path.join(C.work, 't4'))
    uw = U_WORK + '/t4'
    for f, txt in A.items():
        if f != 'Creek.rvg':
            G.text('t4_a_%s.diff' % f.split('.')[1], udiff(open(os.path.join(start, f)).read(), txt, f + ' (start)', f, 1))
        wfile(os.path.join(w, f), txt)
    wfile(os.path.join(C.work, 't4_rvg_a.txt'), RVG_EXT)
    G.text('t4_rvg_a.txt', RVG_EXT)
    ex, dt, so = raven(w, 'out_coupled', 't4_run_a.txt', ucwd=uw)
    G.val('t4:runsec', '%d' % max(1, round(dt)), volatile=True)
    out = os.path.join(w, 'out_coupled')
    s = summary_text(out)
    G.text('t4_summary.txt', '$ grep -v "computed in" out_coupled/GWModelSummary.txt | head -n 19\n' + sanitize(excerpt(s, first=19, drop=r'computed in'), ucwd=uw))
    lf = {int(m.group(1)): 100 * float(m.group(2)) for m in re.finditer(r'^(\d+),[^,]*,[^,]*,[^,]*,[^,]*,([0-9.]+),', s, re.M)}
    for h in (3, 7, 8):
        G.val('t4:link%d' % h, fmt(lf[h], 1))
    G.val('t4:linkothers', fmt(min(v for h, v in lf.items() if h not in (3, 7, 8)), 0))
    G.val('t4:coverage', re.search(r'HRU coverage\s*:\s*([0-9.]+)%', s).group(1))
    G.val('t4:activecols', re.search(r'active columns\s*:\s*(\d+)', s).group(1))
    G.text('t4_mf6nam.txt', '$ cat out_coupled/mf6/creek.nam\n' + open(os.path.join(out, 'mf6', 'creek.nam')).read())
    b = budget(out)
    G.val('t4:a:rech', fmt(b['MF6 recharge [m3/d]'].mean(), 0)); G.val('t4:a:seep', fmt(b['seepage to Raven [m3/d]'].mean(), 0))
    G.val('t4:a:toriv', fmt(b['aquifer discharge to rivers [m3/d]'].mean(), 0)); G.val('t4:a:fromriv', fmt(b['river leakage to aquifer [m3/d]'].mean(), 0))
    G.val('t4:a:other', fmt(b['other model packages [m3/d]'].mean(), 0)); G.val('t4:a:stor', fmt(b['storage release [m3/d]'].mean(), 0))
    G.val('t4:a:q', fmt(hydro(out)['q'].iloc[1:].mean(), 2))
    G.val('t4:a:unconv', '%d' % (b['converged'] == 0).sum())
    G.val('t4:a:rechday1', fmt(b['MF6 recharge [m3/d]'].iloc[0], 0))
    G.val('t4:a:rechday1mm', fmt(b['MF6 recharge [m3/d]'].iloc[0] / sum(area(r) for i, sb, k, r in HRUS if i in AQ_OF) * 1000, 1))
    G.val('t4:a:stor1', fmt(b['storage release [m3/d]'].iloc[:365].mean(), 0)); G.val('t4:a:stor3', fmt(b['storage release [m3/d]'].iloc[-365:].mean(), 0))
    o = audit(t, out, 't4_audit_a.txt', uw, rel='out_coupled')
    audit_values('t4:a', o)
    # stage B: water-table ET from Raven (EVT_RAVEN)
    rvpB = rvp_text(gw=False) + RVP_EXT_ET
    G.text('t4_b_rvp.diff', udiff(A['Creek.rvp'], rvpB, 'Creek.rvp', 'Creek.rvp', 1))
    wfile(os.path.join(w, 'Creek.rvp'), rvpB)
    raven(w, 'out_et', 't4_run_b.txt', ucwd=uw)
    out = os.path.join(w, 'out_et')
    s = summary_text(out)
    G.text('t4_summary_b.txt', '$ grep -E "taken over|water-table ET" out_et/GWModelSummary.txt\n' + excerpt(s, [r'packages taken over', r'water-table ET']))
    b = budget(out)
    G.val('t4:b:et', fmt(b['water-table ET [m3/d]'].mean(), 0)); G.val('t4:b:seep', fmt(b['seepage to Raven [m3/d]'].mean(), 0))
    G.val('t4:b:etmax', fmt(b['water-table ET [m3/d]'].max(), 0))
    G.val('t4:b:q', fmt(hydro(out)['q'].iloc[1:].mean(), 2))
    # stage C: the wetland and the reservoir exchange with the aquifer
    rvhC = rvh_text(AQ_OF, group=True, lake_seepage=True).replace(':EndHRUGroup\n', ':EndHRUGroup\n:HRUGroup WetlandHRUs\n  9\n:EndHRUGroup\n')
    rviC = rvi_coupled().replace(':DefineHRUGroups   AquiferHRUs', ':DefineHRUGroups   AquiferHRUs, WetlandHRUs')
    rvgC = RVG_EXT + (':SurfaceWaterExchange DEPRESSION WetlandHRUs LEAKANCE 0.01   # the wetland\'s DEPRESSION store <-> aquifer\n'
                      ':ReservoirExchange                                         # CreekLake (lake HRU 5) <-> aquifer\n')
    for f, a_, b_ in (('Creek.rvh', A['Creek.rvh'], rvhC), ('Creek.rvi', A['Creek.rvi'], rviC), ('Creek.rvg', RVG_EXT, rvgC)):
        G.text('t4_c_%s.diff' % f.split('.')[1], udiff(a_, b_, f, f, 1))
        wfile(os.path.join(w, f), b_)
    raven(w, 'out', 't4_run_c.txt', ucwd=uw)
    out = os.path.join(w, 'out')
    s = summary_text(out)
    G.text('t4_summary_c.txt', '$ grep -E "surface-water|reservoirs" out/GWModelSummary.txt\n' + excerpt(s, [r'surface-water exchange', r'coupled reservoirs']))
    G.text('t4_mf6nam_c.txt', '$ grep RAVEN out/mf6/creek.nam\n' + ''.join(l for l in open(os.path.join(out, 'mf6', 'creek.nam')) if 'RAVEN' in l))
    G.val('t4:nraven', '%d' % sum(1 for l in open(os.path.join(out, 'mf6', 'creek.nam')) if 'RAVEN' in l))
    b = budget(out)
    for k, c in (('swin', 'surface-store leakage to aquifer [m3/d]'), ('swout', 'aquifer discharge to surface stores [m3/d]'),
                 ('ressent', 'reservoir seepage sent [m3/d]'), ('resdel', 'reservoir seepage delivered [m3/d]'), ('et', 'water-table ET [m3/d]'),
                 ('seep', 'seepage to Raven [m3/d]'), ('other', 'other model packages [m3/d]')):
        G.val('t4:c:' + k, fmt(b[c].mean(), 0))
    G.val('t4:c:resnet', fmt(b['reservoir seepage sent [m3/d]'].mean(), 0, sign=True))
    rs = csv(os.path.join(out, 'ReservoirStages.csv'))
    o = audit(t, out, 't4_audit_c.txt', uw)
    audit_values('t4:c', o)
    copytree(start, fin)
    for f, txt in (('Creek.rvh', rvhC), ('Creek.rvi', rviC), ('Creek.rvp', rvpB), ('Creek.rvg', rvgC)):
        wfile(os.path.join(fin, f), txt)
    plot_gw(t, out, uw, 't4_plot.txt', 'existing model')
    for d in ('out_coupled', 'out_et'):
        shutil.rmtree(os.path.join(w, d, 'mf6'), ignore_errors=True)



# ======================================================================================================================
# tutorial 5: restarts, ensembles and particle tracking
# ======================================================================================================================
RVE = """# Creek.rve - a Monte Carlo ensemble: PERC_COEFF of SUBSOIL (how fast the subsoil feeds the aquifer) drawn per member
:OutputDirectoryFormat ./out_ens/ens_*/
:ParameterDistributions
  #  parameter  class type  class    default  distribution  low   high
  PERC_COEFF    SOIL        SUBSOIL  0.04     DIST_UNIFORM  0.02  0.06
:EndParameterDistributions
"""
NENS = 5


def tut5():
    t = 't5'
    start, fin = tutfiles(t, 'start'), tutfiles(t, 'finished')
    for d in (start, fin):
        if os.path.exists(d):
            shutil.rmtree(d)
    write_creek_coupled(start)
    w = copytree(start, os.path.join(C.work, 't5'))
    p2 = os.path.join(C.work, 't5_part2')
    if os.path.exists(p2):
        shutil.rmtree(p2)
    uw, up2 = U_WORK + '/t5', U_WORK + '/t5_part2'
    # A. a continuous run, and the same run in two parts
    raven(w, 'out', 't5_run_full.txt', ucwd=uw)
    rvi0 = open(os.path.join(w, 'Creek.rvi')).read()
    d1 = (datetime.date(2012, 1, 1) - START).days
    rvi1 = rvi0.replace(':Duration           %d' % DUR3, ':Duration           %d' % d1)
    G.text('t5_part1.diff', udiff(rvi0, rvi1, 'Creek.rvi', 'Creek.rvi', 0))
    G.val('t5:d1', '%d' % d1)
    wfile(os.path.join(w, 'Creek.rvi'), rvi1)
    raven(w, 'out_part1', 't5_run_part1.txt', ucwd=uw)
    rvc = open(os.path.join(w, 'out_part1', 'solution.rvc')).read()
    G.text('t5_rvc_blocks.txt', '$ grep -n "^:" out_part1/solution.rvc\n' +
           '\n'.join('%d:%s' % (i + 1, l) for i, l in enumerate(rvc.split('\n')) if l.startswith(':')))
    G.text('t5_rvc_head.txt', '$ head -n 6 out_part1/solution.rvc | cut -c1-110\n' + '\n'.join(l[:110] for l in rvc.split('\n')[:6]))
    m = re.search(r':GWHeads (\d+) (\d+) (\d+)', rvc)
    G.val('t5:gwheads', '%s %s %s' % m.groups())
    os.makedirs(p2)
    for f in sorted(os.listdir(w)):
        if f.startswith('Creek.') or f in ('CreekMet.rvt', 'CreekGW.rvt') or f.endswith(('.geojson', '.tif')):
            shutil.copy(os.path.join(w, f), os.path.join(p2, f))
    shutil.copy(os.path.join(w, 'out_part1', 'solution.rvc'), os.path.join(p2, 'Creek.rvc'))
    rvi2 = rvi1.replace(':StartDate          2010-01-01 00:00:00', ':StartDate          2012-01-01 00:00:00').replace(
        ':Duration           %d' % d1, ':Duration           %d' % (DUR3 - d1))
    G.text('t5_part2.diff', udiff(rvi1, rvi2, 'Creek.rvi', 'Creek.rvi', 0))
    wfile(os.path.join(p2, 'Creek.rvi'), rvi2)
    ex, dt, so = raven(p2, 'out', 't5_run_part2.txt', ucwd=up2,
                       keep=lambda o: keep_raven(o).replace('...\n', '...\n' + '\n'.join(l for l in o.split('\n') if 'hotstart' in l.lower()) + '\n', 1))
    err = open(os.path.join(p2, 'out', 'Raven_errors.txt')).read()
    G.text('t5_part2_advisory.txt', '$ grep hotstart out/Raven_errors.txt\n' + ''.join(l for l in err.splitlines(True) if 'hotstart' in l))
    run([sys.executable, os.path.join(SCRIPTS, 'compare_runs.py'), '--diff', os.path.join(w, 'out'), os.path.join(p2, 'out')], p2,
        'python3 $TUT/scripts/compare_runs.py --diff ../t5/out out', 't5_diff.txt', ucwd=up2)
    o = G.texts['t5_diff.txt']
    G.val('t5:maxdiff', re.search(r'largest difference of all: (\S+)', o).group(1))
    wfile(os.path.join(w, 'Creek.rvi'), rvi0)
    # B. an ensemble
    rviE = rvi0.replace(':EvaluationMetrics', ':EnsembleMode       ENSEMBLE_MONTECARLO %d\n:RandomSeed         7\n\n:EvaluationMetrics' % NENS)
    G.text('t5_ens.diff', udiff(rvi0, rviE, 'Creek.rvi', 'Creek.rvi', 0))
    wfile(os.path.join(w, 'Creek.rvi'), rviE)
    wfile(os.path.join(w, 'Creek.rve'), RVE)
    ex, dt, so = raven(w, 'out_ens', 't5_run_ens.txt', ucwd=uw)
    G.val('t5:enssec', '%d' % max(1, round(dt)), volatile=True)
    G.val('t5:nens', '%d' % NENS)
    G.text('t5_ls_ens.txt', '$ ls out_ens\n' + '  '.join(sorted(os.listdir(os.path.join(w, 'out_ens')))) +
           '\n$ ls out_ens/ens_1\n' + '  '.join(sorted(os.listdir(os.path.join(w, 'out_ens', 'ens_1')))))
    plt = plt_()
    fig, ax = plt.subplots(2, 1, figsize=(8.6, 5.0), sharex=True)
    import pandas as pd
    ens = []
    for k in range(1, NENS + 1):
        e = os.path.join(w, 'out_ens', 'ens_%d' % k)
        g = gwheads(e); b = budget(e)
        ax[0].plot(pd.to_datetime(g['date']), g['OW_SLOPE (103) [m]'], lw=1.0, label='member %d' % k)
        ax[1].plot(b['date'], b['MF6 recharge [m3/d]'].rolling(30, min_periods=1).mean() / 1000.0, lw=1.0)
        ens.append((g['OW_SLOPE (103) [m]'].iloc[-1], b['MF6 recharge [m3/d]'].mean()))
    gref = gwheads(os.path.join(w, 'out'))
    ax[0].plot(pd.to_datetime(gref['date']), gref['OW_SLOPE (103) [m]'], 'k--', lw=1.0, label='single run (0.04)')
    ax[0].set_ylabel('head [m]'); ax[0].set_title('OW_SLOPE (103): head in each member'); ax[0].legend(fontsize=7, ncol=3)
    ax[1].set_ylabel('1000 m$^3$/d'); ax[1].set_title('recharge reaching MODFLOW, 30-day means')
    fig.tight_layout(); fig.savefig(figpath('t5_ensemble.png'), dpi=150); plt.close(fig)
    hs = [e[0] for e in ens]; rs = [e[1] for e in ens]
    G.val('t5:enshmin', fmt(min(hs), 2)); G.val('t5:enshmax', fmt(max(hs), 2))
    G.val('t5:ensrmin', fmt(min(rs), 0)); G.val('t5:ensrmax', fmt(max(rs), 0))
    shutil.rmtree(os.path.join(w, 'out_ens'))
    wfile(os.path.join(w, 'Creek.rvi'), rvi0)
    # C. MODFLOW's budget file and particle tracking: one year from the start, flows saved every day
    rviP = rvi0.replace(':Duration           %d' % DUR3, ':Duration           365')
    G.text('t5_prt_rvi.diff', udiff(rvi0, rviP, 'Creek.rvi', 'Creek.rvi', 0))
    wfile(os.path.join(w, 'Creek.rvi'), rviP)
    rvg0 = open(os.path.join(w, 'Creek.rvg')).read()
    rvgP = rvg0.replace(':GWInitialization  STEADY_STATE 1.2                # start from the steady state for 1.2 mm/d of recharge\n',
                        ':GWInitialization  STEADY_STATE 1.2                # start from the steady state for 1.2 mm/d of recharge\n'
                        ':WriteGWBudgetFile                                 # MODFLOW budget file mf6/gwf.cbc, for particle tracking\n'
                        ':HeadSaveFrequency 1                               # heads and flows saved every day\n')
    G.text('t5_prt.diff', udiff(rvg0, rvgP, 'Creek.rvg', 'Creek.rvg', 0))
    wfile(os.path.join(w, 'Creek.rvg'), rvgP)
    raven(w, 'out_prt', 't5_run_prt.txt', ucwd=uw)
    mf = os.path.join(w, 'out_prt', 'mf6')
    G.val('t5:cbcmb', fmt(os.path.getsize(os.path.join(mf, 'gwf.cbc')) / 1e6, 0))
    o, dt = run([sys.executable, os.path.join(C.tools, 'make_prt.py'), 'out_prt', '--backward', '--run', C.mf6lib], w,
                'python3 $TOOLS/make_prt.py out_prt --backward --run $PKG/bin/libmf6.so', 't5_make_prt.txt', ucwd=uw)
    epf = os.path.join(w, 'out_prt', 'prt', 'endpoints.csv')
    ep = csv(epf)
    G.text('t5_endpoints.txt', '$ head -n 4 out_prt/prt/endpoints.csv\n' + ''.join(open(epf).readlines()[:4]))
    G.val('t5:npart', '%d' % len(ep))
    dist = np.hypot(ep['x1'] - ep['x0'], ep['y1'] - ep['y0'])
    G.val('t5:distmin', fmt(dist.min(), 0)); G.val('t5:distmax', fmt(dist.max(), 0))
    G.val('t5:ttime', fmt(ep['travel_time_d'].max(), 0))
    run([sys.executable, os.path.join(SCRIPTS, 'plot_tracks.py'), 'out_prt'], w,
        'python3 $TUT/scripts/plot_tracks.py out_prt', 't5_plot_tracks.txt', ucwd=uw)
    shutil.copy(os.path.join(w, 'out_prt', 'prt', 'tracks.png'), figpath('t5_tracks.png'))
    # the finished state: both folders as the tutorial leaves them
    copytree(w, os.path.join(fin, 't5'))
    copytree(p2, os.path.join(fin, 't5_part2'))
    for d in (os.path.join(fin, 't5'), os.path.join(fin, 't5_part2')):
        for x in os.listdir(d):
            if x.startswith('out') and os.path.isdir(os.path.join(d, x)):
                shutil.rmtree(os.path.join(d, x))
    shutil.rmtree(os.path.join(w, 'out_prt'))


# ======================================================================================================================
# committed values (for steps skipped with --quick)
# ======================================================================================================================
def committed_values(prefix):
    p = os.path.join(GEN, 'values.tex')
    rx = re.compile(r'\\defval\{([^}]*)\}\{(.*)\}(  % measured on the build machine)?$')
    out = {}
    if os.path.exists(p):
        for l in open(p):
            m = rx.match(l.rstrip('\n'))
            if m and m.group(1).startswith(prefix):
                out[m.group(1)] = (m.group(2), bool(m.group(3)))
    return out


def keep_committed(prefix, texts=()):
    for k, (v, vol) in committed_values(prefix).items():
        G.val(k, v, volatile=vol)
    for n in texts:
        p = os.path.join(GEN, n)
        if os.path.exists(p):
            G.text(n, open(p).read())


def summary_value(s, label):
    m = re.search(r'^\s*' + re.escape(label) + r'\s*:\s*(.*)$', s, re.M)
    return m.group(1).strip() if m else ''


# ======================================================================================================================
# tutorial 1: getting started (the package and the Liard example)
# ======================================================================================================================
def tut1():
    t = 't1'
    # the release package the tutorials need: built from these commits (or later) of the Raven code and of
    # RavenHydroFramework-extra; files/README.txt names them too
    G.val('t1:reqcode', REQUIRES['code']); G.val('t1:reqextra', REQUIRES['extra'])
    rd = open(os.path.join(FILES, 'README.txt')).read()
    if REQUIRES['code'] not in rd or REQUIRES['extra'] not in rd:
        raise RuntimeError('files/README.txt does not name the required commits %s' % REQUIRES)
    r = subprocess.run(['git', '-C', C.tools, 'merge-base', '--is-ancestor', REQUIRES['extra'], 'HEAD'], capture_output=True)
    if r.returncode == 1:
        log('WARNING: the tools folder %s is older than commit %s' % (C.tools, REQUIRES['extra']))
    if not C.pkgdir:
        raise RuntimeError('tutorial 1 needs the unpacked release package: give --package')
    w = fresh(os.path.join(C.work, 't1'))
    # the package
    G.text('t1_ls_pkg.txt', '$ ls $PKG\n' + '  '.join(sorted(f for f in os.listdir(C.pkgdir) if f not in ('raven-soil-zone', 'raven-mf6-extra'))) + '\n$ ls $PKG/bin\n' + '  '.join(sorted(os.listdir(os.path.join(C.pkgdir, 'bin')))))
    # installation check, as the package README says
    x = os.path.join(w, 'pkgsrc')
    os.makedirs(x)
    subprocess.run(['tar', 'xzf', os.path.join(C.pkgdir, 'source', 'raven_code_src.tar.gz'), 'raven-soil-zone/cmake/RavenMF6InstallCheck.py'], cwd=x, check=True)
    run([sys.executable, os.path.join(x, 'raven-soil-zone', 'cmake', 'RavenMF6InstallCheck.py'), os.path.join(C.pkgdir, 'bin')], C.pkgdir,
        'python3 raven-soil-zone/cmake/RavenMF6InstallCheck.py bin', 't1_installcheck.txt', ucwd=U_PKG,
        env=dict(C.env, RAVEN_MF6_LIB=''))
    tools = sorted(f for f in os.listdir(C.tools) if not f.startswith('.') and f != '__pycache__')
    G.text('t1_ls_tools.txt', '$ ls $TOOLS\n' + '  '.join(tools))
    # the Liard example, one year
    ex = copytree(C.examples, os.path.join(w, 'examples'))
    lg = os.path.join(ex, 'Liard_groundwater')
    uw = U_WORK + '/examples/Liard_groundwater'
    rvi = open(os.path.join(lg, 'Liard.rvi')).read()
    nd = int(re.search(r'^:Duration\s+(\d+)', rvi, re.M).group(1))
    G.val('t1:fullDays', '%d' % nd); G.val('t1:fullYears', '%d' % round(nd / 365.25))
    edit(os.path.join(lg, 'Liard.rvi'), ':Duration           7305 00:00:00', ':Duration           365 00:00:00')
    G.text('t1_duration.txt', '$ grep :Duration Liard.rvi\n' + [l for l in open(os.path.join(lg, 'Liard.rvi')) if l.startswith(':Duration')][0])
    ex1, dt, _ = raven(lg, 'out', 't1_run.txt', ucwd=uw, model='Liard')
    G.val('t1:runsec', '%d' % max(1, round(dt)), volatile=True)
    out = os.path.join(lg, 'out')
    G.text('t1_ls_out.txt', '$ ls out\n' + '  '.join(sorted(os.listdir(out))) + '\n$ ls out/mf6\n' + '  '.join(sorted(os.listdir(os.path.join(out, 'mf6')))))
    s = summary_text(out)
    G.text('t1_summary.txt', '$ grep -v "computed in" out/GWModelSummary.txt | head -n 17\n' + sanitize(excerpt(s, first=17, drop=r'computed in'), lg, uw))
    G.val('t1:mf6ver', re.search(r'MODFLOW 6 library\s*:.*\(version ([0-9.]+)\)', s).group(1))
    m = re.search(r'regular, (\d+) layers x (\d+) rows x (\d+) cols, cell size (\d+) m', s)
    G.val('t1:nlay', m.group(1)); G.val('t1:nrow', m.group(2)); G.val('t1:ncol', m.group(3)); G.val('t1:cell', fmt(float(m.group(4))))
    G.val('t1:activecols', fmt(float(re.search(r'active columns\s*:\s*(\d+)', s).group(1))))
    G.val('t1:rivcells', re.search(r'river cells\s*:\s*(\d+)', s).group(1))
    G.val('t1:nhru', re.search(r'coupled HRUs\s*:\s*(\d+)', s).group(1))
    G.text('t1_budget_head.txt', '$ head -n 3 out/GWBudget.csv | cut -d, -f1-7\n' +
           '\n'.join(','.join(l.rstrip('\n').split(',')[:7]) for l in open(os.path.join(out, 'GWBudget.csv')).readlines()[:3]))
    b = budget(out)
    G.val('t1:ncolsBudget', '%d' % len(b.columns))
    G.val('t1:rech', fmt(b['MF6 recharge [m3/d]'].mean() / 1e6, 2))
    G.val('t1:seep', fmt(b['seepage to Raven [m3/d]'].mean() / 1e6, 2))
    G.val('t1:toriv', fmt(b['aquifer discharge to rivers [m3/d]'].mean() / 1e6, 2))
    G.val('t1:fromriv', fmt(b['river leakage to aquifer [m3/d]'].mean() / 1e6, 2))
    G.val('t1:stor', fmt(b['storage release [m3/d]'].mean() / 1e6, 2))
    G.val('t1:balerr', sci(b['MF6 balance error [%]'].abs().max(), 1))
    G.val('t1:maxouter', '%d' % b['outer iterations'].max())
    h = hrustate(out)
    dm = h.filter(like='wtdepth_').mean()
    G.val('t1:wtmin', fmt(dm.min(), 1)); G.val('t1:wtmax', fmt(dm.max(), 1))
    G.text('t1_hrustate_head.txt', '$ head -n 3 out/GWHRUState.csv | cut -d, -f1-5\n' +
           '\n'.join(','.join(l.rstrip('\n').split(',')[:5]) for l in open(os.path.join(out, 'GWHRUState.csv')).readlines()[:3]))
    o = audit(t, out, 't1_audit.txt', uw)
    audit_values(t, o)
    mb = re.search(r'Raven MB error max \[mm\]\s+([-0-9.eE+]+)', o)
    G.val('t1:auditMB', mb.group(1) if mb else '?')
    plot_gw(t, out, uw, 't1_plot.txt', 'Liard', figs=('gw_budget', 'gw_watertable', 'gw_map'))
    G.text('t1_restore.txt', '$ sed -i \'s/^:Duration           365 /:Duration           7305 /\' Liard.rvi\n$ grep :Duration Liard.rvi\n'
           + [l for l in rvi.split('\n') if l.startswith(':Duration')][0])
    # the full 20-year run (skipped with --quick)
    if C.quick:
        keep_committed('t1:full', ('t1_audit_full.txt',))
        return
    wfile(os.path.join(lg, 'Liard.rvi'), rvi)
    shutil.rmtree(out)
    log('t1: the 20-year Liard run')
    ex2, dt2, _ = raven(lg, 'out', None, ucwd=uw, model='Liard')
    G.val('t1:fullmin', '%d' % max(1, round(dt2 / 60.0)), volatile=True)
    o2 = audit(t, out, 't1_audit_full.txt', uw)
    G.val('t1:fullUnconv', '%d' % float(re.search(r'unconverged steps\s+([-0-9.eE+]+)', o2).group(1)))
    G.val('t1:fullRes', sci(float(re.search(r'MF6 cumulative residual / gross flow\s+([-0-9.eE+]+)', o2).group(1))))
    import pandas as pd
    dg = pd.read_csv(os.path.join(out, 'Diagnostics.csv'))
    for gname in ('10BE004', '10BE005', '10BE010'):
        r = dg[dg['filename'].str.contains(gname) & dg['observed_data_series'].str.startswith('HYDROGRAPH')]
        G.val('t1:fullNSE' + gname, fmt(float(r['DIAG_NASH_SUTCLIFFE'].iloc[0]), 3) if len(r) else '?')
    shutil.rmtree(os.path.join(out, 'mf6'))


# ======================================================================================================================
# tutorial 2: your own groundwater model (Tutorial Creek)
# ======================================================================================================================
def tut2():
    t = 't2'
    start, fin = tutfiles(t, 'start'), tutfiles(t, 'finished')
    for d in (start, fin):
        if os.path.exists(d):
            shutil.rmtree(d)
    write_creek_start(start, ascii_too=True)
    write_creek_coupled(fin, ascii_too=True)
    w = copytree(start, os.path.join(C.work, 't2'))
    uw = U_WORK + '/t2'
    G.text('t2_ls_start.txt', '$ ls\n' + '  '.join(sorted(os.listdir(w))))
    # step 0: the model without groundwater
    raven(w, 'out_nogw', 't2_run_nogw.txt', ucwd=uw)
    q0 = hydro(os.path.join(w, 'out_nogw'))
    G.val('t2:qmeanNoGW', fmt(q0['q'].iloc[1:].mean(), 2))
    # the edits, as exact diffs
    for f, n in (('Creek.rvh', 't2_rvh.diff'), ('Creek.rvp', 't2_rvp.diff'), ('Creek.rvi', 't2_rvi.diff'), ('Creek.rvt', 't2_rvt.diff')):
        diff_file(n, os.path.join(start, f), os.path.join(fin, f), f + ' (start)', f + ' (finished)', 1)
        shutil.copy(os.path.join(fin, f), os.path.join(w, f))
    shutil.copy(os.path.join(fin, 'Creek.rvg'), os.path.join(w, 'Creek.rvg'))
    G.val('t2:pondmin', fmt(976.5 - 0.4, 1)); G.val('t2:pondmax', fmt(976.5 + 0.4, 1))
    G.text('t2_gwrvt_head.txt', '$ head -n 6 CreekGW.rvt\n' + ''.join(open(os.path.join(w, 'CreekGW.rvt')).readlines()[:6]))
    G.val('t2:nhru', '%d' % len(HRUS))
    G.val('t2:ncoupled', '%d' % len(AQ_OF))
    for i, sb, k, r in HRUS:
        G.val('t2:area%d' % i, fmt(area(r) / 1e6, 2))
    G.val('t2:areaTotal', fmt(sum(area(r) for *_, r in HRUS) / 1e6, 1))
    # step: run the coupled model
    ex, dt, so = raven(w, 'out', 't2_run.txt', ucwd=uw)
    G.val('t2:runsec', '%d' % max(1, round(dt)), volatile=True)
    out = os.path.join(w, 'out')
    s = summary_text(out)
    G.text('t2_summary.txt', '$ grep -v "computed in" out/GWModelSummary.txt | head -n 40\n' + sanitize(excerpt(s, first=40, drop=r'computed in'), ucwd=uw))
    m = re.search(r'regular, (\d+) layers x (\d+) rows x (\d+) cols, cell size (\d+) m', s)
    G.val('t2:nlay', m.group(1)); G.val('t2:nrow', m.group(2)); G.val('t2:ncol', m.group(3))
    G.val('t2:ncells', fmt(int(m.group(2)) * int(m.group(3))))
    G.val('t2:activecols', re.search(r'active columns\s*:\s*(\d+)', s).group(1))
    G.val('t2:inactivecols', re.search(r'active columns\s*:\s*\d+ \(inactive (\d+)\)', s).group(1))
    G.val('t2:rivcells', re.search(r'river cells\s*:\s*(\d+)', s).group(1))
    gc = re.search(r'GHB cells / CHD cells\s*:\s*(\d+) / (\d+)', s)
    G.val('t2:ghbcells', gc.group(1)); G.val('t2:chdcells', gc.group(2))
    G.val('t2:fidelity', re.search(r'HRU fidelity of cells\s*:\s*([0-9.]+)%', s).group(1))
    for wid, n, *_ in OBSW:
        mm = re.search(r'%s: layer (\d+), MODFLOW cell \((\d+ \d+ \d+)\)' % n, s)
        G.val('t2:owlay%d' % wid, mm.group(1))
    ss = re.search(r'Groundwater steady-state initialization converged in (\d+) outer iterations', so)
    G.val('t2:ssiter', ss.group(1) if ss else '?')
    b = budget(out)
    A = sum(area(r) for i, sb, k, r in HRUS if i in AQ_OF)
    for key, col, sg in (('rech', 'MF6 recharge [m3/d]', 1), ('seep', 'seepage to Raven [m3/d]', 1), ('toriv', 'aquifer discharge to rivers [m3/d]', 1),
                         ('fromriv', 'river leakage to aquifer [m3/d]', 1), ('stor', 'storage release [m3/d]', 1), ('ghb', 'GHB [m3/d]', -1),
                         ('chd', 'CHD [m3/d]', -1), ('wel', 'wells actual [m3/d]', -1)):
        G.val('t2:' + key, fmt(sg * b[col].mean(), 0))
    G.val('t2:rechmm', fmt(b['MF6 recharge [m3/d]'].mean() / A * 1000 * 365.25, 0))
    G.val('t2:seeppct', fmt(100 * b['seepage to Raven [m3/d]'].mean() / b['MF6 recharge [m3/d]'].mean(), 0))
    G.val('t2:balerr', sci(b['MF6 balance error [%]'].abs().max(), 1))
    G.val('t2:maxouter', '%d' % b['outer iterations'].max())
    G.val('t2:unconv', '%d' % (b['converged'] == 0).sum())
    G.val('t2:wellmin', fmt(-b['wells specified [m3/d]'].max(), 0)); G.val('t2:wellmax', fmt(-b['wells specified [m3/d]'].min(), 0))
    h = hrustate(out)
    for i in AQ_OF:
        G.val('t2:wt%d' % i, fmt(h['wtdepth_%d [m]' % i].mean(), 1))
    g = gwheads(out)
    for wid, n, *_ in OBSW:
        col = [c for c in g.columns if '(%d)' % wid in c][0]
        G.val('t2:owmin%d' % wid, fmt(g[col].min(), 2)); G.val('t2:owmax%d' % wid, fmt(g[col].max(), 2))
    G.text('t2_budget_head.txt', '$ head -n 3 out/GWBudget.csv | cut -d, -f1-9\n' +
           '\n'.join(','.join(l.rstrip('\n').split(',')[:9]) for l in open(os.path.join(out, 'GWBudget.csv')).readlines()[:3]))
    G.text('t2_heads_head.txt', '$ head -n 4 out/GWHeads.csv\n' + ''.join(open(os.path.join(out, 'GWHeads.csv')).readlines()[:4]))
    o = audit(t, out, 't2_audit.txt', uw)
    audit_values(t, o)
    mb = re.search(r'Raven MB error max \[mm\]\s+([-0-9.eE+]+)', o)
    G.val('t2:auditMB', mb.group(1) if mb else '?')
    plot_gw(t, out, uw, 't2_plot.txt', 'Tutorial Creek')
    basin_map(figpath('t2_basin.png'), None, 'Tutorial Creek: HRUs and groundwater features', show_grid=False)
    basin_map(figpath('t2_grid.png'), out, 'Tutorial Creek: the active cells of the grid Raven built')
    # hydrograph with and without groundwater
    q1 = hydro(out)
    G.val('t2:qmean', fmt(q1['q'].iloc[1:].mean(), 2))
    G.val('t2:qdrop', fmt(round((q0['q'].iloc[1:].mean() - q1['q'].iloc[1:].mean()) * 86400.0, -2)))
    dd = {}
    for o in ('out_nogw', 'out'):
        import pandas as pd
        ws = pd.read_csv(os.path.join(w, o, 'WatershedStorage.csv'))
        c = [c for c in ws.columns if 'Soil Water[2]' in c][0]
        dd[o] = float(ws[c].iloc[-1] - ws[c].iloc[0])
    G.val('t2:deepgw', fmt(dd['out'], 0, sign=True)); G.val('t2:deepnogw', fmt(dd['out_nogw'], 0, sign=True))
    ndays = len(q1) - 1
    G.val('t2:deeprate', fmt(round((dd['out'] - dd['out_nogw']) / 1000.0 * sum(area(r) for *_, r in HRUS) / ndays, -2)))
    plt = plt_()
    fig, ax = plt.subplots(figsize=(8.6, 3.0))
    sel = (q1['date'] >= '2011-01-01') & (q1['date'] < '2012-01-01')
    ax.plot(q0['date'][sel], q0['q'][sel], color='#d08a2b', lw=0.9, label='Raven alone (step 1)')
    ax.plot(q1['date'][sel], q1['q'][sel], color='#1f4e79', lw=0.9, label='Raven + MODFLOW 6')
    ax.set_ylabel('m$^3$/s'); ax.set_title('streamflow at the outlet of subbasin 2 (LOWER), 2011'); ax.legend()
    fig.tight_layout(); fig.savefig(figpath('t2_hydrograph.png'), dpi=150); plt.close(fig)
    # variant 1: the ESRI ASCII grids instead of the GeoTIFF files
    rvg = open(os.path.join(w, 'Creek.rvg')).read()
    rvg_a = rvg.replace('dem.tif    ', 'dem.asc    ').replace('bedrock.tif ', 'bedrock.asc ')
    G.text('t2_ascii.diff', udiff(rvg, rvg_a, 'Creek.rvg', 'Creek.rvg', 0))
    wfile(os.path.join(w, 'Creek.rvg'), rvg_a)
    raven(w, 'out_ascii')
    ha = hrustate(os.path.join(w, 'out_ascii'))
    hc = [c for c in h.columns if c.startswith('head_')]
    G.val('t2:asciidiff', sci(float(np.abs(ha[hc].values - h[hc].values).max()), 0) if np.abs(ha[hc].values - h[hc].values).max() > 0 else '0')
    # variant 2: :InputCRS forgotten
    rvg_n = rvg.replace(':InputCRS          EPSG:32611', '# :InputCRS        EPSG:32611')
    G.text('t2_nocrs.diff', udiff(rvg, rvg_n, 'Creek.rvg', 'Creek.rvg', 0))
    wfile(os.path.join(w, 'Creek.rvg'), rvg_n)
    ex, dt, so = raven(w, 'out_nocrs', None, check=False)
    err = [l for l in open(os.path.join(w, 'out_nocrs', 'Raven_errors.txt')) if l.startswith('ERROR')]
    G.text('t2_nocrs_err.txt', '$ $RAVEN Creek -o out_nocrs/\n...\nExiting Gracefully: ' + sanitize(ex, w, uw) + '\n$ grep ERROR out_nocrs/Raven_errors.txt\n' + sanitize(''.join(err[:2]), w, uw))
    # variant 3: finer cells along the creek
    rvg_r = rvg.replace(':GridCellSize      250.0                           # m\n',
                        ':GridCellSize      250.0                           # m\n:GridRefinement    RIVERS 125.0                    # 125 m cells along the creek\n')
    G.text('t2_refine.diff', udiff(rvg, rvg_r, 'Creek.rvg', 'Creek.rvg', 0))
    wfile(os.path.join(w, 'Creek.rvg'), rvg_r)
    ex, dtr, so = raven(w, 'out_refined')
    sr = summary_text(os.path.join(w, 'out_refined'))
    G.text('t2_refine_summary.txt', '$ grep -E "grid|active|river cells" out_refined/GWModelSummary.txt\n' +
           excerpt(sr, [r'^\s+grid\s+:', r'^\s+active columns', r'^\s+active cells', r'^\s+river cells']))
    m = re.search(r'(\d+) layers x (\d+) rows x (\d+) cols', sr)
    G.val('t2:refnrow', m.group(2)); G.val('t2:refncol', m.group(3))
    G.val('t2:refactive', re.search(r'active columns\s*:\s*(\d+)', sr).group(1))
    G.val('t2:refriv', re.search(r'river cells\s*:\s*(\d+)', sr).group(1))
    G.val('t2:refsec', '%d' % max(1, round(dtr)), volatile=True)
    br = budget(os.path.join(w, 'out_refined'))
    G.val('t2:reftoriv', fmt(br['aquifer discharge to rivers [m3/d]'].mean(), 0))
    G.val('t2:refseep', fmt(br['seepage to Raven [m3/d]'].mean(), 0))
    hr = hrustate(os.path.join(w, 'out_refined'))
    G.val('t2:refwt6', fmt(hr['wtdepth_6 [m]'].mean(), 1))
    wfile(os.path.join(w, 'Creek.rvg'), rvg)
    for d in ('out_ascii', 'out_nocrs', 'out_refined'):
        shutil.rmtree(os.path.join(w, d), ignore_errors=True)



REQUIRES = {'code': 'f8ee662', 'extra': '7be65a6'}   # the commits of the release package the tutorials were made with


# ======================================================================================================================
# PDFs and the zip of the tutorial files
# ======================================================================================================================
DOCS = [('t1', 'Tutorial1_Getting_started'), ('t2', 'Tutorial2_Own_groundwater_model'), ('t3', 'Tutorial3_Soil_zone'),
        ('t4', 'Tutorial4_Existing_MODFLOW_model'), ('t5', 'Tutorial5_Restarts_ensembles_particles'),
        ('t6', 'Tutorial6_Calibration_Ostrich')]
COMBINED = 'Raven_MF6_Tutorials'


def pdflatex(name, texsrc):
    """compiles tex/<name>.tex (written from texsrc) in a scratch folder; returns the page count"""
    b = fresh(os.path.join(C.work, 'latex', name))
    wfile(os.path.join(TEX, name + '.tex'), texsrc)
    for _ in range(2):
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', '-output-directory', b, name + '.tex'],
                           cwd=TEX, capture_output=True, text=True)
        if r.returncode != 0:
            sys.stderr.write(r.stdout[-3000:])
            raise RuntimeError('pdflatex failed on %s' % name)
    log_ = open(os.path.join(b, name + '.log'), errors='ignore').read()
    bad = re.findall(r'(LaTeX Warning: (?:Reference|Citation).*undefined.*)', log_)
    if bad:
        raise RuntimeError('%s: %s' % (name, bad[0]))
    os.makedirs(PDF, exist_ok=True)
    shutil.copy(os.path.join(b, name + '.pdf'), os.path.join(PDF, name + '.pdf'))
    return int(re.search(r'Output written on .*?\((\d+)\s+pages?', log_, re.S).group(1))


def build_pdfs():
    pages = {}
    for t, name in DOCS:
        src = ('\\documentclass[11pt,a4paper]{article}\n\\input{preamble}\n\\hypersetup{pdftitle={Raven-MODFLOW 6 tutorial %s: %s}}\n'
               '\\begin{document}\n\\input{%s_body}\n\\end{document}\n' % (t[1], TITLES[t], t))
        pages[name] = pdflatex(name, src)
        log('%s.pdf: %d pages' % (name, pages[name]))
    src = ('\\documentclass[11pt,a4paper,oneside]{report}\n\\input{preamble}\n\\hypersetup{pdftitle={Raven-MODFLOW 6 tutorials}}\n'
           '\\begin{document}\n\\input{cover}\n' + ''.join('\\input{%s_body}\n' % t for t, _ in DOCS) + '\\end{document}\n')
    pages[COMBINED] = pdflatex(COMBINED, src)
    log('%s.pdf: %d pages' % (COMBINED, pages[COMBINED]))
    wfile(os.path.join(PDF, 'pages.txt'), ''.join('%s.pdf %d\n' % (k, v) for k, v in pages.items()))
    return pages


def build_zip():
    """Raven_MF6_Tutorial_Files.zip: the tutorial files and the PDFs, as the folder Raven_MF6_Tutorials/ (fixed dates, so
    that a rebuild with unchanged files gives the same zip)"""
    if os.path.exists(ZIPFILE):
        os.remove(ZIPFILE)
    with zipfile.ZipFile(ZIPFILE, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        items = []
        for r, ds, fs in os.walk(FILES):
            ds.sort()
            for f in sorted(fs):
                if f.endswith('.pyc') or '__pycache__' in r:
                    continue
                items.append((os.path.join(r, f), os.path.join('Raven_MF6_Tutorials', os.path.relpath(os.path.join(r, f), FILES))))
        for f in sorted(os.listdir(PDF)):
            if f.endswith('.pdf'):
                items.append((os.path.join(PDF, f), os.path.join('Raven_MF6_Tutorials', 'pdf', f)))
        for src, arc in items:
            zi = zipfile.ZipInfo(arc, date_time=(2026, 11, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            ex = src.endswith(('.sh', '.py'))
            zi.external_attr = ((0o755 if ex else 0o644) | 0o100000) << 16
            z.writestr(zi, open(src, 'rb').read())
    log('%s: %.1f MB' % (os.path.basename(ZIPFILE), os.path.getsize(ZIPFILE) / 1e6))


# ======================================================================================================================
# main
# ======================================================================================================================
RUNNERS = {}


def setup(a):
    C.quick, C.check = a.quick, a.check
    C.work = os.path.abspath(a.work)
    os.makedirs(C.work, exist_ok=True)
    C.pkgdir = os.path.abspath(a.package) if a.package else None
    C.raven = os.path.abspath(a.raven or os.environ.get('RAVEN_EXE') or (C.pkgdir and os.path.join(C.pkgdir, 'bin', 'Raven')) or '')
    C.mf6lib = os.path.abspath(a.mf6lib or os.environ.get('RAVEN_MF6_LIB') or (C.pkgdir and os.path.join(C.pkgdir, 'bin', 'libmf6.so')) or '')
    if not os.path.exists(C.raven):
        sys.exit('Raven not found: give --raven or --package, or set RAVEN_EXE')
    if not os.path.exists(C.mf6lib):
        sys.exit('MODFLOW 6 library not found: give --mf6lib or --package, or set RAVEN_MF6_LIB')
    C.examples = os.path.join(C.pkgdir, 'examples') if C.pkgdir else os.path.join(REPO, 'examples')
    C.tools = os.path.abspath(a.tools) if a.tools else os.path.join(REPO, 'tools')
    C.ostrich = a.ostrich
    C.files = os.path.join(C.work, 'check', 'files') if C.check else FILES
    C.gen = os.path.join(C.work, 'check', 'generated') if C.check else GEN
    C.fig = os.path.join(C.work, 'check', 'figures') if C.check else FIG
    if C.check:
        for d in (C.files, C.gen, C.fig):
            fresh(d)
        if os.path.exists(SCRIPTS):
            shutil.copytree(SCRIPTS, os.path.join(C.files, 'scripts'))
    C.env = dict(os.environ)
    C.env['RAVEN'] = C.raven
    C.env['RAVEN_MF6_LIB'] = C.mf6lib
    C.env['TUT'] = C.files
    C.env['PKG'] = C.pkgdir or ''
    C.env['TOOLS'] = C.tools
    C.env['MPLBACKEND'] = 'Agg'


def compare_trees(a, b, what):
    """files of tree a (generated now) against tree b (committed): list of differences"""
    bad = []
    fa = {os.path.relpath(os.path.join(r, f), a) for r, _, fs in os.walk(a) for f in fs}
    fb = {os.path.relpath(os.path.join(r, f), b) for r, _, fs in os.walk(b) for f in fs} if os.path.exists(b) else set()
    for f in sorted(fa | fb):
        if f not in fb:
            bad.append('%s: %s is new (not committed)' % (what, f))
        elif f not in fa:
            bad.append('%s: %s was not generated' % (what, f))
        elif not filecmp.cmp(os.path.join(a, f), os.path.join(b, f), shallow=False):
            bad.append('%s: %s differs' % (what, f))
    return bad


def check_values(gen_now, gen_committed, volatile):
    bad = []
    rx = re.compile(r'\\defval\{([^}]*)\}\{(.*)\}')

    def vals(p):
        return dict(rx.match(l).groups() for l in open(p) if rx.match(l)) if os.path.exists(p) else {}
    a, b = vals(os.path.join(gen_now, 'values.tex')), vals(os.path.join(gen_committed, 'values.tex'))
    p = os.path.join(gen_committed, 'values.tex')
    volatile = set(volatile) | ({rx.match(l).group(1) for l in open(p) if rx.match(l) and 'measured on the build machine' in l}
                                if os.path.exists(p) else set())
    for k in sorted(set(a) | set(b)):
        if k in volatile:
            continue
        if k not in b:
            bad.append('value %s is new: %s' % (k, a[k]))
        elif k not in a:
            bad.append('value %s was not generated' % k)
        elif a[k] != b[k]:
            bad.append('value %s: now %s, committed %s' % (k, a[k], b[k]))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--raven'); ap.add_argument('--mf6lib'); ap.add_argument('--package'); ap.add_argument('--ostrich')
    ap.add_argument('--tools', help='the tools folder of RavenHydroFramework-extra (make_prt.py, plot_soilzone.py); default: ../../tools')
    ap.add_argument('--work', default=os.path.join(HERE, '_work'))
    ap.add_argument('--only', default=','.join(TUTS))
    ap.add_argument('--quick', action='store_true'); ap.add_argument('--check', action='store_true')
    ap.add_argument('--no-pdf', action='store_true')
    ap.add_argument('--pdf-only', action='store_true', help='only compile the PDFs and write the zip (from the committed includes)')
    a = ap.parse_args()
    setup(a)
    only = [x.strip() for x in a.only.split(',') if x.strip()]
    if a.pdf_only:
        build_pdfs(); build_zip(); return
    t0 = time.time()
    if not C.check and os.path.exists(GEN):
        # keep the committed values of tutorials not implemented now
        rx = re.compile(r'\\defval\{([^}]*)\}\{(.*)\}(  % measured on the build machine)?$')
        for l in open(os.path.join(GEN, 'values.tex')) if os.path.exists(os.path.join(GEN, 'values.tex')) else []:
            m = rx.match(l.rstrip('\n'))
            if m and m.group(1).split(':')[0] not in only:
                G.val(m.group(1), m.group(2), volatile=bool(m.group(3)))
    times = {}
    for t in TUTS:
        if t in only:
            t1 = time.time()
            RUNNERS[t]()
            times[t] = time.time() - t1
            log('%s done in %.0f s' % (t, times[t]))
    if C.check:
        G.write(C.gen)
        bad = check_values(C.gen, GEN, G.volatile)
        for n in sorted(G.texts):
            p = os.path.join(GEN, n)
            if not os.path.exists(p):
                bad.append('excerpt %s is new' % n)
            elif open(p).read() != G.texts[n]:
                diff = udiff(open(p).read(), G.texts[n], 'committed/' + n, 'now/' + n, 0)
                bad.append('excerpt %s differs:\n%s' % (n, diff[:1500]))
        for t in only:
            bad += compare_trees(os.path.join(C.files, TDIR[t]), os.path.join(FILES, TDIR[t]), 'tutorial files')
        print('\n'.join(bad) if bad else 'check: every number, excerpt, diff and tutorial file matches')
        print('check: %d values, %d excerpts, %s; %.0f s' % (len(G.values), len(G.texts), ', '.join(only), time.time() - t0))
        sys.exit(1 if bad else 0)
    for t in TUTS:
        if t in times:
            G.val(t + ':buildmin', '%d' % max(1, round(times[t] / 60.0)), volatile=True)
    G.write(GEN)
    if set(only) == set(TUTS):
        for f in os.listdir(GEN):                 # excerpts of steps that no longer exist
            if f != 'values.tex' and f not in G.texts:
                os.remove(os.path.join(GEN, f))
    if not a.no_pdf and set(only) == set(TUTS):
        build_pdfs()
        build_zip()
    log('done in %.0f s' % (time.time() - t0))


RUNNERS.update({'t1': tut1, 't2': tut2, 't3': tut3, 't4': tut4, 't5': tut5, 't6': tut6})

if __name__ == '__main__':
    main()
