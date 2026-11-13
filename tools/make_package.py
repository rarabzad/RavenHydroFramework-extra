#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Makes the Linux release package of Raven with MODFLOW 6 from the two repositories, and checks it.

    python3 make_package.py <package folder> --code <code repo> --code-rev <rev> --raven <Raven> --mf6 <libmf6.so>
                            [--extra <extra checkout>] [--extra-rev HEAD] [--code-branch mf6-coupling]
                            [--extra-branch main] [--no-manual-check]

<package folder> must be new or empty. --code is the RavenHydroFramework repository and --code-rev its revision (the
tip of mf6-coupling that is published); --raven is the Raven executable built from that revision with
docs/tutorials/build_release_raven.sh, and --mf6 the MODFLOW 6 library (6.8.1). --extra is the checkout of
RavenHydroFramework-extra that holds this script (default: the one this script is in) and --extra-rev its revision
(default HEAD); the workshop zips and the README template are taken from the checkout, which must be clean and at that
revision for the package to pass.

The package:
  README.md                 tools/package_README.md, its section "Restore the git history" written by package_sources.py
  bin/                      Raven, libmf6.so, RavenMF6InstallCheck.py (cmake/ of the code revision), LICENSE-Raven.txt
                            (the code revision's LICENSE), NOTICE-MODFLOW6.txt, VERSIONS.txt
  Raven_MF6_Manual.pdf      docs/manual/main.pdf of the extra revision
  examples/                 examples/ of the extra revision
  workshops/                the six workshop zips (docs/tutorials/build_tutorials.py --package), whose bin/README.txt
                            names the code revision as the source commit of Raven
  source/                   tools/package_sources.py: source archives, history bundles, RESTORE_HISTORY.md, COMMITS.txt
  SHA256SUMS.txt            the SHA-256 sum of every other file

Checks (exit code 0 only when all pass):
  - package_sources.py: the README's clone commands give both histories complete, as stated; the manual PDF is the
    build of the manual's chapters (unless --no-manual-check) and the package's copy is that PDF;
  - the install check (bin/RavenMF6InstallCheck.py bin 6.8.1) passes;
  - Raven's banner date is the committer date (UTC) of the code revision, as build_release_raven.sh makes it;
  - every workshop zip holds the package's bin/Raven and bin/libmf6.so, byte for byte, and names the code revision;
  - the README names only files the package holds, and has no wording about the making of the package;
  - the extra checkout is clean and at the extra revision (tools/, docs/tutorials/).
"""
import os, sys, re, io, shutil, subprocess, tempfile, tarfile, zipfile, hashlib, argparse, datetime, calendar

HERE = os.path.dirname(os.path.abspath(__file__))
MF6_VERSION = '6.8.1'
PROCESS = re.compile(r'(?<!tools_)audit|\bphase\b|\bround\b|\bnot yet\b|\bdraft\b|\bWIP\b|\bTODO\b|\bpreviously\b|\bno longer\b', re.I)


def git(args, cwd, binary=False):
    r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=not binary)
    if r.returncode != 0:
        sys.exit('git %s (in %s) failed:\n%s' % (' '.join(args), cwd, r.stderr if not binary else r.stderr.decode(errors='replace')))
    return r.stdout if binary else r.stdout.strip()


def unpack(repo, rev, paths, dest):
    """the files of paths at rev of repo, unpacked into dest"""
    data = git(['archive', '--format=tar', rev, '--'] + paths, repo, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        t.extractall(dest, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pkg')
    ap.add_argument('--code', required=True); ap.add_argument('--code-rev', required=True)
    ap.add_argument('--extra', default=os.path.dirname(HERE)); ap.add_argument('--extra-rev', default='HEAD')
    ap.add_argument('--raven', required=True); ap.add_argument('--mf6', required=True)
    ap.add_argument('--code-branch', default='mf6-coupling'); ap.add_argument('--extra-branch', default='main')
    ap.add_argument('--no-manual-check', action='store_true')
    a = ap.parse_args()
    pkg, extra = os.path.abspath(a.pkg), os.path.abspath(a.extra)
    if os.path.exists(pkg) and os.listdir(pkg):
        sys.exit('%s is not empty: give a new or empty folder' % pkg)
    for p, what in ((a.raven, '--raven'), (a.mf6, '--mf6')):
        if not os.path.isfile(p):
            sys.exit('%s: %s not found' % (what, p))
    ctip = git(['rev-parse', '--verify', a.code_rev + '^{commit}'], a.code)
    cshort = git(['rev-parse', '--short', ctip], a.code)
    xtip = git(['rev-parse', '--verify', a.extra_rev + '^{commit}'], extra)
    print('code  %s (%s), extra %s' % (ctip[:12], a.code_rev, xtip[:12]))
    fails = []
    tmp = tempfile.mkdtemp(prefix='mkpkg_')
    try:
        src = os.path.join(tmp, 'code'); os.makedirs(src)
        unpack(a.code, ctip, ['LICENSE', 'cmake/RavenMF6InstallCheck.py'], src)
        # bin/
        b = os.path.join(pkg, 'bin'); os.makedirs(b)
        for s, d, mode in ((a.raven, 'Raven', 0o755), (a.mf6, 'libmf6.so', 0o755),
                           (os.path.join(src, 'cmake', 'RavenMF6InstallCheck.py'), 'RavenMF6InstallCheck.py', 0o755),
                           (os.path.join(src, 'LICENSE'), 'LICENSE-Raven.txt', 0o644),
                           (os.path.join(extra, 'docs', 'tutorials', 'NOTICE-MODFLOW6.txt'), 'NOTICE-MODFLOW6.txt', 0o644)):
            shutil.copyfile(s, os.path.join(b, d)); os.chmod(os.path.join(b, d), mode)
        probe = os.path.join(tmp, 'probe'); os.makedirs(probe)
        ban = subprocess.run([os.path.join(b, 'Raven')], cwd=probe, capture_output=True, text=True).stdout
        ver = re.search(r'Version:\s*(\S+)', ban); bd = re.search(r'BuildDate:\s*(.+)', ban)
        ver, bd = (ver.group(1) if ver else '?'), (' '.join(bd.group(1).split()) if bd else '?')
        t = datetime.datetime.fromtimestamp(int(git(["log", "-1", "--format=%ct", ctip], a.code)), datetime.timezone.utc)
        cdate = '%s %d %d' % (calendar.month_abbr[t.month], t.day, t.year)
        if bd != cdate:
            fails.append('bin/Raven was built on %s, not with the date of the code revision (%s): build it with '
                         'docs/tutorials/build_release_raven.sh from %s' % (bd, cdate, cshort))
        with open(os.path.join(b, 'VERSIONS.txt'), 'w') as f:
            f.write('Raven       %s, build date %s, source commit %s of RavenHydroFramework (branch %s)\n'
                    '            sha256 %s\n'
                    'libmf6.so   MODFLOW 6 %s (the official release)\n'
                    '            sha256 %s\n' % (ver, bd, cshort, a.code_branch, sha256(a.raven), MF6_VERSION, sha256(a.mf6)))
        # the manual and the examples of the extra revision
        with open(os.path.join(pkg, 'Raven_MF6_Manual.pdf'), 'wb') as f:
            f.write(git(['show', '%s:docs/manual/main.pdf' % xtip], extra, binary=True))
        unpack(extra, xtip, ['examples'], pkg)
        # the README template
        shutil.copyfile(os.path.join(HERE, 'package_README.md'), os.path.join(pkg, 'README.md'))
        # the workshop zips
        r = subprocess.run([sys.executable, os.path.join(extra, 'docs', 'tutorials', 'build_tutorials.py'), '--package',
                            os.path.join(pkg, 'workshops'), '--raven', os.path.join(b, 'Raven'), '--mf6', os.path.join(b, 'libmf6.so'),
                            '--raven-src', src, '--source-commit', cshort], capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            fails.append('build_tutorials.py --package failed')
        # source/ and the README's restore section
        cmd = [sys.executable, os.path.join(HERE, 'package_sources.py'), pkg, a.code, ctip, extra, xtip,
               '--code-branch', a.code_branch, '--extra-branch', a.extra_branch, '--update-readme']
        r = subprocess.run(cmd + (['--no-manual-check'] if a.no_manual_check else []), capture_output=True, text=True)
        print((r.stdout + r.stderr).strip())
        if r.returncode != 0:
            fails.append('package_sources.py: FAIL (above)')
        # the install check
        r = subprocess.run([sys.executable, os.path.join(b, 'RavenMF6InstallCheck.py'), b, MF6_VERSION], cwd=tmp,
                           capture_output=True, text=True)
        print((r.stdout + r.stderr).strip().split('\n')[-1])
        if r.returncode != 0:
            fails.append('install check: ' + (r.stdout + r.stderr).strip()[-300:])
        # the workshop zips hold the package's programs and name the code revision
        zips = sorted(f for f in os.listdir(os.path.join(pkg, 'workshops')) if f.endswith('.zip')) \
            if os.path.isdir(os.path.join(pkg, 'workshops')) else []
        if len(zips) != 6:
            fails.append('%d workshop zips, not 6' % len(zips))
        want = {'Raven': open(a.raven, 'rb').read(), 'libmf6.so': open(a.mf6, 'rb').read()}
        for zn in zips:
            with zipfile.ZipFile(os.path.join(pkg, 'workshops', zn)) as z:
                top = zn[:-4]
                for f, data in want.items():
                    if z.read(top + '/bin/' + f) != data:
                        fails.append('%s: bin/%s is not the package\'s' % (zn, f))
                if ('source commit %s' % cshort) not in z.read(top + '/bin/README.txt').decode():
                    fails.append('%s: bin/README.txt does not name the source commit %s' % (zn, cshort))
        print('workshop zips: %d, each with the package\'s programs and source commit %s' % (len(zips), cshort))
        # the README: the files it names exist; no wording about the making of the package
        text = open(os.path.join(pkg, 'README.md')).read()
        for p in sorted(set(re.findall(r'`((?:bin|source|examples|workshops)/[^`<>* ]*|Raven_MF6_Manual\.pdf|SHA256SUMS\.txt)`', text))):
            if p != 'SHA256SUMS.txt' and not os.path.exists(os.path.join(pkg, p.split(' ')[0])):
                fails.append('README.md names %s, which the package does not hold' % p)
        for m in PROCESS.finditer(text):
            fails.append('README.md: wording "%s"' % m.group(0))
        # the checkout the zips and the README template come from is the extra revision
        if git(['rev-parse', 'HEAD'], extra) != xtip:
            fails.append('the extra checkout is not at %s: the workshops and README come from the checkout' % xtip[:12])
        dirty = git(['status', '--porcelain', '--', 'tools', 'docs/tutorials'], extra)
        if dirty:
            fails.append('the extra checkout has changes in tools/ or docs/tutorials/ (git status):\n  ' + dirty.replace('\n', '\n  '))
        # SHA256SUMS.txt
        files = sorted(os.path.relpath(os.path.join(r_, f), pkg) for r_, _, fs in os.walk(pkg) for f in fs)
        with open(os.path.join(pkg, 'SHA256SUMS.txt'), 'w') as f:
            for p in files:
                f.write('%s  %s\n' % (sha256(os.path.join(pkg, p)), p))
        print('SHA256SUMS.txt: %d files' % len(files))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for f in fails:
        print('FAIL: ' + f)
    print('package %s: %s' % (pkg, 'PASS' if not fails else 'FAIL'))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
