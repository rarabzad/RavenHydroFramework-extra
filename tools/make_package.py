#!/usr/bin/env python3
# SPDX-License-Identifier: Artistic-2.0
"""Makes the Linux release package of Raven with MODFLOW 6 from the two repositories, and checks it.

    python3 make_package.py <package folder> --code <code repo> --code-rev <rev> --raven <Raven> --mf6 <libmf6.so>
                            [--extra <extra checkout>] [--extra-rev HEAD] [--code-branch mf6-coupling]
                            [--extra-branch main] [--no-manual-check]
    python3 make_package.py --self-test

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
  Raven_MF6_User_Manual.pdf docs/manual/Raven_MF6_User_Manual.pdf of the extra revision (Volume 1 of the manual)
  Raven_MF6_Reference.pdf   docs/manual/Raven_MF6_Reference.pdf of the extra revision (Volume 2)
  examples/                 examples/ of the extra revision
  workshops/                the six workshop zips (docs/tutorials/build_tutorials.py --package), whose bin/README.txt
                            names the code revision as the source commit of Raven
  source/                   tools/package_sources.py: source archives, history bundles, RESTORE_HISTORY.md, COMMITS.txt
  SHA256SUMS.txt            the SHA-256 sum of every other file

Checks (exit code 0 only when all pass):
  - package_sources.py: the README's clone commands give both histories complete, as stated; the two manual PDFs are
    the build of the manual's sources (unless --no-manual-check) and the package's copies are those PDFs;
  - the install check (bin/RavenMF6InstallCheck.py bin 6.8.1) passes;
  - Raven's banner date is the committer date (UTC) of the code revision, as build_release_raven.sh makes it;
  - bin/Raven is a release build, as build_release_raven.sh makes it and the README's requirements assume: read from its
    ELF dynamic section, the highest GLIBC_ symbol version it needs is at most 2.28 and it does not load libstdc++ or
    libgcc_s (it contains its C++ runtime); a normal build of the same commit (glibc of the build machine, the system's
    libstdc++) fails this check; bin/libmf6.so needs at most GLIBC_2.34, the floor the README names;
  - every workshop zip holds the package's bin/Raven and bin/libmf6.so, byte for byte, and names the code revision;
  - the README names only files the package holds, and has no wording about the making of the package: none of the
    words of PROCESS below, which is the commit-message wording rule of tools/process_wording.py (audit, phase, round,
    draft, WIP, review, revision, rebuilt, regenerated, recovered, reconstructed, previously, no longer, pending,
    placeholder, merged build, brought up to, a version or finding ID, and the like) and a few more for a README (TODO,
    FIXME, not yet, final, status at, by your order, corrected, fixed in, earlier version, ...); "git history" and
    "Raven history" are allowed;
  - the extra checkout is clean and at the extra revision (tools/, docs/tutorials/).

--self-test checks the two checks above that need no package: each process phrase injected into the README template
is found, and the template with the restore section package_sources.py writes passes; synthetic ELF files with GLIBC_2.38, with libstdc++ or libgcc_s NEEDED, or
with no dynamic section fail, one with GLIBC_2.16 and libc only passes. It prints 'make_package self-test: ALL PASSED'.
"""
import os, sys, re, io, shutil, subprocess, tempfile, tarfile, zipfile, hashlib, argparse, datetime, calendar

HERE = os.path.dirname(os.path.abspath(__file__))
MF6_VERSION = '6.8.1'
RAVEN_GLIBC, MF6_GLIBC = (2, 28), (2, 34)   # the highest GLIBC_ versions bin/Raven and bin/libmf6.so may need
sys.path.insert(0, HERE)
from process_wording import RULE_SOURCE   # the commit-message wording rule: the one list of process words
# wording about the making of the package: the commit-message rule's words, and more for a README; "git history" and
# "Raven history" are allowed (the README's restore section and package_sources.py's text)
README_EXTRA = (
    r'\bphases?\b|\brounds?\b|\bfindings?\b|\bTODO\b|\bFIXME\b|\bnot yet\b|\bfinal\b|\bstatus at\b|\bby your order\b|'
    r'\bas you (?:asked|ordered|requested)\b|\bcorrect(?:ed|ions?)\b|\bfixed in\b|'
    r'\bearlier (?:version|package|release|build)s?\b|\bnew in this (?:version|package|release)\b')
PROCESS = re.compile(RULE_SOURCE + '|' + README_EXTRA, re.I)
ALLOWED = re.compile(r'(?:\bgit|\bRaven) $', re.I)   # before "history"


def readme_problems(text):
    # the wording of the README about the making of the package
    return ['README.md: wording "%s"' % m.group(0) for m in PROCESS.finditer(text)
            if not (m.group(0).lower() == 'history' and ALLOWED.search(text[max(0, m.start() - 6):m.start()]))]


def elf_needs(path):
    # (NEEDED libraries, {library: [versions]}) of an ELF64 little-endian file, read from its dynamic section as the
    # dynamic loader reads it (program headers, DT_NEEDED, DT_VERNEED); None when it is not such a file
    import struct
    with open(path, 'rb') as f:
        d = f.read()
    if d[:4] != b'\x7fELF' or d[4] != 2 or d[5] != 1:
        return None
    phoff, = struct.unpack_from('<Q', d, 0x20); phentsize, phnum = struct.unpack_from('<HH', d, 0x36)
    loads, dyn = [], None
    for i in range(phnum):
        ptype, _, off, vaddr, _, filesz, _, _ = struct.unpack_from('<IIQQQQQQ', d, phoff + i * phentsize)
        if ptype == 1:
            loads.append((vaddr, off, filesz))
        elif ptype == 2:
            dyn = (off, filesz)
    if dyn is None:
        return None

    def at(v):   # file offset of a virtual address
        for vaddr, off, filesz in loads:
            if vaddr <= v < vaddr + filesz:
                return v - vaddr + off
        raise ValueError('address %#x outside the loaded segments' % v)
    tags, needed = {}, []
    for i in range(dyn[1] // 16):
        tag, val = struct.unpack_from('<qQ', d, dyn[0] + 16 * i)
        if tag == 0:
            break
        if tag == 1:
            needed.append(val)
        else:
            tags[tag] = val
    if 5 not in tags:
        return None
    strtab = at(tags[5])

    def cstr(o):
        return d[strtab + o:d.index(b'\0', strtab + o)].decode()
    versions = {}
    if 0x6ffffffe in tags:   # DT_VERNEED, DT_VERNEEDNUM entries
        o = at(tags[0x6ffffffe])
        for _ in range(tags.get(0x6fffffff, 0)):
            _, cnt, vfile, aux, nxt = struct.unpack_from('<HHIII', d, o)
            a, names = o + aux, []
            for _ in range(cnt):
                _, _, _, vname, anext = struct.unpack_from('<IHHII', d, a)
                names.append(cstr(vname)); a += anext
            versions[cstr(vfile)] = names
            if not nxt:
                break
            o += nxt
    return [cstr(n) for n in needed], versions


def binary_problems(path, what, max_glibc, own_runtime):
    # why path is not a program as the release needs it: a GLIBC_ version above max_glibc, a dynamic C++ runtime
    try:
        r = elf_needs(path)
    except (OSError, ValueError, IndexError, UnicodeDecodeError) as e:
        return ['%s: not readable as an ELF file (%s)' % (what, e)]
    if r is None:
        return ['%s is not a dynamically linked x86_64 ELF file' % what]
    needed, versions = r
    out, top = [], None
    for v in (v for vs in versions.values() for v in vs if v.startswith('GLIBC_')):
        m = re.match(r'GLIBC_(\d+)\.(\d+)', v)
        if not m:
            out.append('%s needs %s' % (what, v)); continue
        t = (int(m.group(1)), int(m.group(2)))
        top = max(top, t) if top else t
    if top and top > max_glibc:
        out.append('%s needs GLIBC_%d.%d, more than %d.%d' % ((what,) + top + max_glibc))
    if own_runtime:
        for n in needed:
            if n.startswith(('libstdc++', 'libgcc_s')):
                out.append('%s loads %s: it is not the release build, which contains its C++ runtime' % (what, n))
    return out


def make_elf(path, needed, versions):
    # a minimal ELF64 file with a dynamic section (for the self-test): NEEDED libraries and {library: [versions]}
    import struct
    strs = b'\0'
    def add(t):
        nonlocal strs
        o = len(strs); strs += t.encode() + b'\0'; return o
    nd = [add(n) for n in needed]
    vn = b''
    libs = list(versions.items())
    for i, (lib, vs) in enumerate(libs):
        fo = add(lib)
        aux = b''.join(struct.pack('<IHHII', 0, 0, 2 + j, add(v), 16 if j < len(vs) - 1 else 0) for j, v in enumerate(vs))
        vn += struct.pack('<HHIII', 1, len(vs), fo, 16, 16 + len(aux) if i < len(libs) - 1 else 0) + aux
    hdr, ph = 64, 56 * 2
    o_str = hdr + ph; o_vn = o_str + len(strs); o_dyn = o_vn + len(vn)
    ent = [(1, n) for n in nd] + [(5, o_str), (10, len(strs))] + ([(0x6ffffffe, o_vn), (0x6fffffff, len(libs))] if libs else []) + [(0, 0)]
    dyn = b''.join(struct.pack('<qQ', t, v) for t, v in ent)
    size = o_dyn + len(dyn)
    eh = b'\x7fELF' + bytes([2, 1, 1]) + bytes(9) + struct.pack('<HHIQQQIHHHHHH', 3, 62, 1, 0, hdr, 0, 0, hdr, 56, 2, 64, 0, 0)
    ph1 = struct.pack('<IIQQQQQQ', 1, 4, 0, 0, 0, size, size, 0x1000)
    ph2 = struct.pack('<IIQQQQQQ', 2, 4, o_dyn, o_dyn, o_dyn, len(dyn), len(dyn), 8)
    with open(path, 'wb') as f:
        f.write(eh + ph1 + ph2 + strs + vn + dyn)


def self_test():
    fails = []
    def check(name, ok, detail=''):
        print('%-72s %s%s' % (name, 'ok' if ok else 'FAIL', ('  (' + detail + ')') if detail else ''))
        if not ok:
            fails.append(name)
    sys.path.insert(0, HERE)
    import package_sources as ps
    readme = open(os.path.join(HERE, 'package_README.md')).read()
    readme += '\n' + ps.restore_text({'code': 'mf6-coupling', 'extra': 'main'}, {'code': ('0' * 40, 865), 'extra': ('1' * 40, 131)})
    check('the README template and its restore section have no process wording', not readme_problems(readme), '; '.join(readme_problems(readme)))
    for ph in ('This is the final package.', 'Status at packaging: all tests pass', 'Not yet done (by your order)',
               'built from the round-10 code', 'rebuilt after the review', 'the corrected binary', 'fixed in this release',
               'the earlier version of the package', 'checked in the audit', 'made in phase 3', 'a draft of the manual',
               'as previously', 'no longer needed', 'regenerated with the new build', 'the revised text', 'WIP', 'TODO',
               'the history of the work', 'reviewed by the team', 'recovered files', 'pending a check',
               'new in this release', 'the v2 tools', 'see SZ-12', 'as you asked', 'the merged build',
               'Raven built (2026-11-13)', 'brought up to the current code', 'merge3 sources',
               'conflicts in x were resolved', 'the v3build binary'):
        check('the README with "%s" fails' % ph, bool(readme_problems(readme + '\n' + ph + '\n')))
    for ok_text in ('Restore the git history', 'their complete git history as bundles', 'the Raven history bundle',
                    'fixed heads', 'the tools_audit.py check'):
        check('"%s" is allowed' % ok_text, not readme_problems(ok_text))
    import process_wording
    check('PROCESS is built from the commit-message rule (process_wording.RULE_SOURCE)',
          PROCESS.pattern.startswith(process_wording.RULE.pattern + '|'))
    tmp = tempfile.mkdtemp(prefix='mkpkg_test_')
    try:
        cases = [('release build: libc GLIBC_2.16, libdl', ['libc.so.6', 'libdl.so.2'], {'libc.so.6': ['GLIBC_2.2.5', 'GLIBC_2.16'], 'libdl.so.2': ['GLIBC_2.2.5']}, 0),
                 ('GLIBC_2.28 exactly', ['libc.so.6'], {'libc.so.6': ['GLIBC_2.28', 'GLIBC_2.3']}, 0),
                 ('a normal build: GLIBC_2.38', ['libc.so.6'], {'libc.so.6': ['GLIBC_2.2.5', 'GLIBC_2.38']}, 1),
                 ('GLIBC_2.29 in libm', ['libm.so.6', 'libc.so.6'], {'libm.so.6': ['GLIBC_2.29'], 'libc.so.6': ['GLIBC_2.2.5']}, 1),
                 ('libstdc++ NEEDED', ['libstdc++.so.6', 'libc.so.6'], {'libc.so.6': ['GLIBC_2.2.5']}, 1),
                 ('libgcc_s NEEDED', ['libgcc_s.so.1', 'libc.so.6'], {'libc.so.6': ['GLIBC_2.2.5']}, 1),
                 ('GLIBC_PRIVATE', ['libc.so.6'], {'libc.so.6': ['GLIBC_PRIVATE']}, 1)]
        for name, needed, versions, bad in cases:
            p = os.path.join(tmp, 'elf'); make_elf(p, needed, versions)
            pr = binary_problems(p, 'bin/Raven', RAVEN_GLIBC, True)
            got = elf_needs(p)
            check('ELF %s: %s' % (name, 'fails' if bad else 'passes'), bool(pr) == bool(bad) and got == (needed, versions), '; '.join(pr))
        p = os.path.join(tmp, 'libmf6'); make_elf(p, ['libc.so.6'], {'libc.so.6': ['GLIBC_2.34']})
        check('ELF libmf6.so with GLIBC_2.34 passes', not binary_problems(p, 'bin/libmf6.so', MF6_GLIBC, False))
        p = os.path.join(tmp, 'text'); open(p, 'w').write('#!/bin/sh\n')
        check('a script instead of an ELF file fails', bool(binary_problems(p, 'bin/Raven', RAVEN_GLIBC, True)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('make_package self-test: %s' % ('ALL PASSED' if not fails else '%d FAILED' % len(fails)))
    return 1 if fails else 0


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
    if sys.argv[1:] == ['--self-test']:
        return self_test()
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
        rel = binary_problems(os.path.join(b, 'Raven'), 'bin/Raven', RAVEN_GLIBC, True)
        fails += [f + ' (build it with docs/tutorials/build_release_raven.sh)' for f in rel]
        fails += binary_problems(os.path.join(b, 'libmf6.so'), 'bin/libmf6.so', MF6_GLIBC, False)
        print('bin/Raven and bin/libmf6.so: %s' % ('release builds (GLIBC_%d.%d and %d.%d at most, no libstdc++ or libgcc_s)'
                                                  % (RAVEN_GLIBC + MF6_GLIBC) if not rel else 'FAIL (below)'))
        with open(os.path.join(b, 'VERSIONS.txt'), 'w') as f:
            f.write('Raven       %s, build date %s, source commit %s of RavenHydroFramework (branch %s)\n'
                    '            sha256 %s\n'
                    'libmf6.so   MODFLOW 6 %s (the official release)\n'
                    '            sha256 %s\n' % (ver, bd, cshort, a.code_branch, sha256(a.raven), MF6_VERSION, sha256(a.mf6)))
        # the manual (both volumes) and the examples of the extra revision
        import package_sources as ps
        for name in ps.MANUAL_COPIES:
            with open(os.path.join(pkg, name), 'wb') as f:
                f.write(git(['show', '%s:docs/manual/%s' % (xtip, name)], extra, binary=True))
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
        for p in sorted(set(re.findall(r'`((?:bin|source|examples|workshops)/[^`<>* ]*|Raven_MF6_(?:User_Manual|Reference)\.pdf|SHA256SUMS\.txt)`', text))):
            if p != 'SHA256SUMS.txt' and not os.path.exists(os.path.join(pkg, p.split(' ')[0])):
                fails.append('README.md names %s, which the package does not hold' % p)
        fails += readme_problems(text)
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
