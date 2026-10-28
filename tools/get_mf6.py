#!/usr/bin/env python3
"""Download the MODFLOW 6 shared library (libmf6) that Raven's groundwater coupling loads at run time.

    python tools/get_mf6.py                  # the tested version (6.8.1) for this computer (see "Where it goes")
    python tools/get_mf6.py --latest         # the newest MODFLOW 6 release instead
    python tools/get_mf6.py --version 6.7.0  # a given release
    python tools/get_mf6.py --zip mf6.8.1_win64.zip   # use a release zip downloaded by hand (no internet needed)
    python tools/get_mf6.py --raven PATH     # PATH: your RavenHydroFramework checkout, or the folder holding Raven.exe
    python tools/get_mf6.py --dest DIR       # put the library exactly in DIR
    python tools/get_mf6.py --force          # replace a library that is already there

Where it goes: with --raven PATH, into PATH/lib/mf6 when PATH is a Raven checkout (it has src/RavenMain.cpp), otherwise
next to the Raven executable in PATH. Without --raven or --dest: into lib/mf6 of the Raven checkout named by the
environment variable RAVEN_SRC, or of a RavenHydroFramework folder beside this repository; failing both, into lib/mf6 of
this repository. Raven finds the library next to its executable or in lib/mf6 of its checkout without any setting.

The release zips come from https://github.com/MODFLOW-ORG/modflow6/releases (for 6.8.1: mf6.8.1_linux.zip, mf6.8.1_win64.zip,
mf6.8.1_macarm.zip; mf6.X.Y_mac.zip for Intel Macs up to MODFLOW 6.7, e.g. --version 6.6.3). MODFLOW releases no library
for Linux other than x86_64 (e.g. aarch64), Windows on ARM, or Intel Macs from 6.8 on: there, build it with Raven
(cmake -DRAVEN_MF6=SOURCE) or give one you have (cmake -DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=...). Only the library is kept (libmf6.so, libmf6.dll or libmf6.dylib), with a
small text file naming its version and source (see the manual, "Getting MODFLOW 6").

Standard Python 3 only; no other packages. MODFLOW 6 is public-domain software of the U.S. Geological Survey.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile

TESTED = '6.8.1'    # the version the coupling was verified with (docs/VERIFICATION_REPORT_MF6.8.1.md)
REPO = 'MODFLOW-ORG/modflow6'
HERE = os.path.dirname(os.path.abspath(__file__))
ADDON = os.path.dirname(HERE)                         # the RavenHydroFramework-extra repository
DEST = os.path.join(ADDON, 'lib', 'mf6')              # last resort


def raven_dest(path):
    """lib/mf6 of a Raven checkout, or the folder of a Raven executable"""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        sys.exit('%s does not exist: give your RavenHydroFramework checkout or the folder of the Raven executable' % path)
    if os.path.isfile(path):
        return os.path.dirname(path)
    for root in (path, os.path.dirname(path)):        # the checkout, or its src/ folder
        if os.path.exists(os.path.join(root, 'src', 'RavenMain.cpp')):
            return os.path.join(root, 'lib', 'mf6')
    return path


def default_dest():
    env = os.environ.get('RAVEN_SRC', '')
    if env and os.path.exists(env):
        return raven_dest(env)
    beside = os.path.join(os.path.dirname(ADDON), 'RavenHydroFramework')
    if os.path.exists(os.path.join(beside, 'src', 'RavenMain.cpp')):
        return os.path.join(beside, 'lib', 'mf6')
    return DEST


def vtuple(v):
    return tuple(int(x) for x in re.findall(r'[0-9]+', v or '')[:3]) or (0,)


BUILD_HINT = ('build the library from source when building Raven (cmake -DRAVEN_MF6=SOURCE: needs a Fortran compiler, '
              'meson >= 1.7, ninja and git), or give one you have (cmake -DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=/path/to/%s); '
              'see the manual, "Building" and "Getting MODFLOW 6"')


def platform_info(version=TESTED, zip_given=False):
    """(release zip suffixes to try, library file name) for this computer; stops with advice where MODFLOW releases no
    library (Linux other than x86_64, Windows on ARM, Intel Macs from MODFLOW 6.8 on)"""
    s, m = platform.system(), platform.machine().lower()
    if s == 'Windows':
        if m in ('arm64', 'aarch64') or m.startswith('arm'):
            if zip_given:   # a win64 zip given by hand: an x64 Raven runs under emulation on Windows on ARM
                print('note: MODFLOW 6 releases no Windows ARM64 library; the library of this zip (x64) works only with an '
                      'x64 build of Raven (x64 emulation)')
                return ['win64'], 'libmf6.dll'
            sys.exit('MODFLOW 6 releases no library for Windows ARM64 (this computer): ' + BUILD_HINT % 'libmf6.dll')
        if not (sys.maxsize > 2 ** 32 or m.endswith('64')):
            sys.exit('MODFLOW 6 is released for 64-bit Windows only')
        return ['win64'], 'libmf6.dll'
    if s == 'Darwin':
        if m in ('arm64', 'aarch64'):
            return ['macarm'], 'libmf6.dylib'
        if not zip_given and vtuple(version) >= (6, 8):
            sys.exit('MODFLOW %s releases no library for Intel Macs (x86_64; from MODFLOW 6.8 on): use an earlier '
                     'release (--version 6.6.3), or %s' % (version, BUILD_HINT % 'libmf6.dylib'))
        return ['mac'], 'libmf6.dylib'   # Intel Macs: release zips up to MODFLOW 6.7
    if s == 'Linux':
        if m not in ('x86_64', 'amd64'):
            sys.exit('MODFLOW 6 releases a Linux library for x86_64 only (this is %s): %s' % (m, BUILD_HINT % 'libmf6.so'))
        return ['linux'], 'libmf6.so'
    sys.exit('unsupported system %s: download libmf6 from https://github.com/%s/releases' % (s, REPO))


def request(url):
    return urllib.request.Request(url, headers={'User-Agent': 'Raven-get_mf6', 'Accept': 'application/octet-stream'})


def latest_version():
    """tag of the newest release: the GitHub API, else the redirect of /releases/latest"""
    try:
        with urllib.request.urlopen(request('https://api.github.com/repos/%s/releases/latest' % REPO), timeout=30) as r:
            return json.load(r)['tag_name'].lstrip('v')
    except Exception:
        pass
    try:
        with urllib.request.urlopen(request('https://github.com/%s/releases/latest' % REPO), timeout=30) as r:
            m = re.search(r'/releases/tag/v?([0-9][^/?#]*)', r.geturl())
    except Exception as e:
        sys.exit('could not reach GitHub to find the latest MODFLOW 6 release (%s); give --version' % e)
    if not m:
        sys.exit('could not find the latest MODFLOW 6 release; give --version')
    return m.group(1)


def download(url, path):
    """download url to path with a progress line; False if the file does not exist (404)"""
    try:
        with urllib.request.urlopen(request(url), timeout=60) as r, open(path, 'wb') as f:
            total = int(r.headers.get('Content-Length') or 0); got = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b); got += len(b)
                if total:
                    sys.stdout.write('\r  %s: %.0f of %.0f MB' % (os.path.basename(path), got / 1e6, total / 1e6)); sys.stdout.flush()
        if total:
            print()
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def extract_library(zpath, libname):
    """(member name, bytes) of the library in a release zip"""
    with zipfile.ZipFile(zpath) as z:
        names = [n for n in z.namelist() if n.replace('\\', '/').split('/')[-1] == libname]
        if not names:
            sys.exit('%s holds no %s: is it a MODFLOW 6 release zip for this system?' % (zpath, libname))
        names.sort(key=lambda n: ('/bin/' not in n.replace('\\', '/'), len(n)))
        return names[0], z.read(names[0])


def main():
    ap = argparse.ArgumentParser(description='Download the MODFLOW 6 library for Raven (default: version %s).' % TESTED)
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--version', help='MODFLOW 6 release, e.g. 6.8.1 (default: %s, the tested version)' % TESTED)
    g.add_argument('--latest', action='store_true', help='the newest MODFLOW 6 release')
    g.add_argument('--zip', help='a MODFLOW 6 release zip already downloaded (works offline)')
    ap.add_argument('--raven', help='your RavenHydroFramework checkout, or the folder holding the Raven executable')
    ap.add_argument('--dest', help='put the library exactly in this folder')
    ap.add_argument('--force', action='store_true', help='replace a library that is already there')
    a = ap.parse_args()

    if a.zip:
        version = (re.search(r'mf([0-9]+\.[0-9]+\.[0-9]+)', os.path.basename(a.zip)) or [None, 'unknown'])[1]
    else:
        version = latest_version() if a.latest else (a.version or TESTED)
    suffixes, libname = platform_info(version, bool(a.zip))
    a.dest = a.dest or (raven_dest(a.raven) if a.raven else default_dest())
    os.makedirs(a.dest, exist_ok=True)
    target = os.path.join(a.dest, libname)
    info = os.path.join(a.dest, 'libmf6_version.txt')

    if os.path.exists(target) and not a.force:
        have = open(info).read().split('\n')[0].strip() if os.path.exists(info) else 'unknown version'
        if a.zip or version in have:
            print('%s is already there (%s); nothing to do (use --force to replace it)' % (target, have))
            return 0
        print('%s is already there (%s); use --force to replace it with MODFLOW %s' % (target, have, version))
        return 0

    tmp = tempfile.mkdtemp(prefix='get_mf6_')
    try:
        if a.zip:
            zpath, url = os.path.abspath(a.zip), a.zip
        else:
            zpath = None
            for suf in suffixes:
                url = 'https://github.com/%s/releases/download/%s/mf%s_%s.zip' % (REPO, version, version, suf)   # e.g. mf6.8.1_linux.zip
                p = os.path.join(tmp, os.path.basename(url))
                print('downloading %s' % url)
                if download(url, p):
                    zpath = p; break
            if zpath is None:
                extra = (' Intel Macs: use an earlier release (--version 6.6.3), or ' + BUILD_HINT % libname + '.'
                         if suffixes == ['mac'] else '')
                sys.exit('MODFLOW %s has no release zip for this system (%s).%s See https://github.com/%s/releases'
                         % (version, ', '.join(suffixes), extra, REPO))
        member, data = extract_library(zpath, libname)
        part = target + '.part'
        with open(part, 'wb') as f:
            f.write(data)
        os.replace(part, target)                       # never leave a half-written library behind
        if platform.system() != 'Windows':
            os.chmod(target, 0o755)
        sha = hashlib.sha256(data).hexdigest()
        with open(info, 'w') as f:
            f.write('MODFLOW %s\nsource: %s (%s)\nsha256: %s\n' % (version, url, member, sha))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('MODFLOW %s library: %s (%.1f MB)' % (version, target, len(data) / 1e6))
    if os.path.abspath(a.dest) == os.path.abspath(DEST):
        print('Raven does not look here by itself: copy %s next to the Raven executable, put it in lib/mf6 of your '
              'Raven checkout (or rerun with --raven PATH), or set RAVEN_MF6_LIB=%s' % (libname, target))
    return 0


if __name__ == '__main__':
    sys.exit(main())
