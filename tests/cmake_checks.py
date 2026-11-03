"""Configure checks of Raven's MODFLOW 6 build integration (CMakeLists.txt, cmake/RavenMF6*.cmake of RavenHydroFramework).

    python3 cmake_checks.py [--src DIR] [--only 1,4,...] [--selftest] [--keep]

Offline and fast (Linux; about a minute): every check configures Raven's CMake project into its own folder under
<scratch>/cmake_checks with small stand-in libraries and zips, and never compiles Raven. Downloads point at a missing
local folder (RAVEN_MF6_RELEASE_URL, RAVEN_MF6_GIT_URL), so nothing leaves the computer. Needs cmake >= 3.20, a C
compiler (cc), and for checks 2, 7 and 9 gfortran, meson >= 1.7, ninja and git (otherwise those parts are skipped).

 1 Linux aarch64 (emulated: CMAKE_SYSTEM_NAME=Linux, CMAKE_SYSTEM_PROCESSOR=aarch64), no meson: the default falls back to
   OFF with a warning naming -DRAVEN_MF6=OFF, configure succeeds
 2 that default fallback survives a reconfigure (still the default, RAVEN_MF6 empty in the cache) and becomes SOURCE
   once the tools are there (h5.2)
 3 RPATH (raven_mf6_rpath() on a small project): a private shared library outside the system folders is found from
   the build tree and from a moved install, and a library beside the executable from a moved install (h5.3)
 4 PATH mode: a symlink to libmf6_663.so, and libmf6.so.6.8.1, are copied next to Raven and installed as libmf6.so (h5.4)
 5 libmf6_version.txt and the package name: "unknown (given library)" and no MODFLOW version for PATH; the version in
   meson.build for a renamed zip and a source folder (h5.5)
 6 offline options name the mode (RAVEN_MF6_ZIP -> PREBUILT even with source tools, RAVEN_MF6_PATH -> PATH,
   RAVEN_MF6_SOURCE_DIR -> SOURCE), an option of another mode is reported as ignored, an unpinned zip is used with a
   warning (h5.6)
 7 meson gets the Fortran compiler of FC: FC = a renamed link W/fc/myfc while CMake's own check names another compiler;
   that path is in mf6_source-cfgcmd.txt (h5.7.4: fails when the FC lines are removed)
 8 a meson whose --version is not readable is named as such (default and explicit SOURCE) (h5.8)
 9 a staged install (DESTDIR, absolute and relative) of a gfortran-built library gets libgfortran.so.5 (h5.8)
10 no git (CMAKE_DISABLE_FIND_PACKAGE_Git, GIT_EXECUTABLE NOTFOUND): the default falls back naming git (10a), explicit
   SOURCE stops naming git (10b), SOURCE with RAVEN_MF6_SOURCE_URL needs no git (10c)
11 an unpinned RAVEN_MF6_ZIP replaced by another (same name) is unpacked again; a third configure does not unpack
   (a sentinel file put into mf6/prebuilt survives) (i5.2)
12 Windows target (emulated: CMAKE_SYSTEM_NAME=Windows, CMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY): AMD64 takes
   mf6.8.1_win64.zip, ARM64 with PREBUILT stops ("no library for Windows ARM64"), ARM64 by default falls back to OFF (i5.3)
13 package version 6.7.2 from RAVEN_MF6_SOURCE_URL .../v6.7.2.tar.gz, and the info line of an unpinned zip
   my_mf6_download.zip says "not checked", not "official release" (i5.5, i5.6)
14 a wrong RAVEN_MF6_ZIP_SHA256 given after an unpinned zip was unpacked stops the configure; the right one passes and
   is named as the user's checksum; a downloaded unpinned zip (local file:// release folder): wrong SHA256 stops, right
   one passes, not called official
15 offline default: with the source tools but an unreachable git repository the default does not pick
   SOURCE (whose clone would fail at build time): it falls back at configure time to PREBUILT (a local file:// release
   folder: configures with the library target) or, with no release reachable either, to OFF with a warning; a reachable
   repository (a local git repository with the release tag) gives SOURCE (needs gfortran, meson, ninja, git)
16 default build type: Unix Makefiles without CMAKE_BUILD_TYPE configure Release (cache and -O3 in Raven's
   flags.make); a given -DCMAKE_BUILD_TYPE=Debug is kept
17 version floor: RAVEN_MF6_VERSION=6.4.0 (SOURCE and PREBUILT), a zip and a source folder whose meson.build says
   6.4.0 stop the configure naming 6.5.0 (MF6_MIN_VERSION of src/MF6Engine.h); 6.7.0 configures with a warning naming
   the tested 6.8.1
18 runtime bundling: macOS emulated (Mach-O dylibs linked with ld64.lld, llvm-otool and llvm-install-name-tool
   as otool and install_name_tool, a stand-in codesign): libmf6 -> @rpath/libgfortran.5.dylib -> @rpath/libquadmath and
   @rpath/libgcc_s, resolved through LC_RPATH, all three installed, every reference rewritten to @loader_path and every
   edited file signed; Windows emulated (stand-in objdump, then dumpbin only): libgfortran-5.dll and the DLLs it imports
   in turn are installed (needs clang and the LLVM 18 tools for the macOS part)
19 messages: RAVEN_MF6_PATH given a folder keeps the ';' of "is a folder; give the library file itself"; a
   6-digit RAVEN_MF6_ZIP_SHA256 is named as not a SHA256 (not "a damaged or different file")

Prints one line per part and "cmake checks: ALL PASSED (N parts)" at the end; exit code = number of failed parts.
"""
import os, sys, re, shutil, subprocess, zipfile, hashlib, tarfile, io, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)


def default_src():
    env = os.environ.get('RAVEN_SRC', '')
    if env:
        env = os.path.abspath(env)
        return os.path.dirname(env) if os.path.basename(env) == 'src' else env
    return os.path.join(os.path.dirname(REPO), 'RavenHydroFramework')


ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
ap.add_argument('--src', default=default_src(), help='Raven checkout (default: RAVEN_SRC or ../RavenHydroFramework)')
ap.add_argument('--only', default='', help='comma-separated check numbers')
ap.add_argument('--selftest', action='store_true', help='show that each check fails on its mutation')
ap.add_argument('--keep', action='store_true', help='keep the work folder')
ap.add_argument('--work', default='', help='work folder (default: RAVEN_TEST_WORK/cmake_checks)')
A = ap.parse_args()
SRC = os.path.abspath(A.src)
WORK = os.path.abspath(A.work or os.path.join(os.environ.get('RAVEN_TEST_WORK', os.path.join(HERE, '_work')), 'cmake_checks'))
CMAKE = shutil.which('cmake') or 'cmake'
GFORTRAN = shutil.which('gfortran')
MESON = shutil.which('meson')
NINJA = shutil.which('ninja')
GIT = shutil.which('git')
CC = shutil.which('cc') or shutil.which('gcc')
RAVEN_VER = (re.findall(r'__RAVEN_VERSION__\s*=\s*"([^"]+)"', open(os.path.join(SRC, 'src', 'RavenInclude.h')).read())
             or ['?'])[0] if os.path.exists(os.path.join(SRC, 'src', 'RavenInclude.h')) else '?'

results = []        # (check, label, ok)


def report(check, label, ok, detail=''):
    results.append((check, label, ok))
    print('%-3s %-78s %s %s' % (check, label, 'ok' if ok else ('SKIP' if ok is None else 'FAIL'), detail), flush=True)


def flat(s):
    """configure output with CMake's line wrapping removed"""
    return re.sub(r'\s+', ' ', s)


def env_base(**kw):
    e = {k: v for k, v in os.environ.items() if k not in ('FC', 'DESTDIR', 'CMAKE_GENERATOR')}
    e.update(kw)
    return e


def cfg(bdir, *args, env=None, src=None, release=None):
    """configure Raven into bdir; returns (rc, flattened output)"""
    cmd = [CMAKE, '-S', src or SRC, '-B', bdir,
           '-DRAVEN_MF6_RELEASE_URL=' + (release or 'file://%s/no_release' % WORK),
           '-DRAVEN_MF6_GIT_URL=file://%s/no_git' % WORK] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, env=env or env_base())
    return r.returncode, flat(r.stdout + r.stderr)


def run(cmd, cwd=None, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env or env_base())
    return r.returncode, r.stdout + r.stderr


def cache(bdir, name):
    p = os.path.join(bdir, 'CMakeCache.txt')
    if not os.path.exists(p):
        return None
    m = re.search(r'^%s:[A-Z]+=(.*)$' % re.escape(name), open(p).read(), re.M)
    return m.group(1) if m else None


def package(bdir):
    p = os.path.join(bdir, 'CPackConfig.cmake')
    m = re.search(r'set\(CPACK_PACKAGE_FILE_NAME "([^"]*)"\)', open(p).read()) if os.path.exists(p) else None
    return m.group(1) if m else ''


def has_lib_target(bdir):
    p = os.path.join(bdir, 'Makefile')
    return os.path.exists(p) and 'raven_mf6_lib' in open(p).read()


def first_line(p):
    return open(p).read().split('\n')[0] if os.path.exists(p) else '(missing %s)' % os.path.basename(p)


def fresh(name):
    d = os.path.join(WORK, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d


def stub_lib(path, tag='stub'):
    """a small shared library standing in for libmf6 (its content differs with tag)"""
    c = path + '.c'
    open(c, 'w').write('const char *raven_stub_tag(void){return "%s";}\n' % tag)
    rc, out = run([CC, '-shared', '-fPIC', '-o', path, c])
    os.remove(c)
    if rc != 0:
        raise RuntimeError('cc failed: ' + out)
    return path


def release_zip(path, version, lib, top=None, plat='linux'):
    """a zip laid out like a MODFLOW release: <top>/bin/libmf6.so, <top>/meson.build (version), <top>/src/meson.build"""
    top = top or 'mf%s_%s' % (version, plat)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(lib, top + '/bin/libmf6.so')
        z.writestr(top + '/meson.build', "project(\n  'MODFLOW 6',\n  'fortran',\n  version: '%s',\n)\n" % version)
        z.writestr(top + '/src/meson.build', "# not the top-level file\nproject('x', version: '0.0.1')\n")
        z.writestr(top + '/doc/readme.txt', 'not the library')
    return path


def sha256(p):
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


def source_folder(d, version):
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'meson.build'), 'w').write("project('MODFLOW 6', 'fortran', version: '%s')\n" % version)
    return d


def git_repo(d, tag):
    """a local git repository with one commit tagged `tag` (file:// URL), standing in for MODFLOW's"""
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'meson.build'), 'w').write("project('MODFLOW 6', 'fortran', version: '%s')\n" % tag)
    e = env_base(GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')
    for c in (['init', '-q'], ['add', 'meson.build'], ['commit', '-q', '-m', 'stand-in'], ['tag', tag]):
        rc, out = run([GIT, '-C', d] + c, env=e)
        if rc != 0:
            raise RuntimeError('git %s: %s' % (c, out))
    return 'file://' + d


TOOLS = bool(GFORTRAN and MESON and NINJA and GIT)
LLVM = '/usr/lib/llvm-18/bin'


# ------------------------------------------------------------------------------------------------------------------
def check1():
    b = os.path.join(fresh('c1'), 'b')
    rc, out = cfg(b, '-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64', '-DRAVEN_MESON=/nonexistent/meson')
    report(1, 'aarch64, no meson, default: configure succeeds', rc == 0, '' if rc == 0 else out[-300:])
    report(1, '  warning: no release library for Linux aarch64, names -DRAVEN_MF6=OFF',
           'CMake Warning' in out and 'releases no library for Linux aarch64' in out and '-DRAVEN_MF6=OFF' in out)
    report(1, '  no library target (OFF)', rc == 0 and not has_lib_target(b))


def check2():
    d = fresh('c2')
    b = os.path.join(d, 'b')
    emu = ['-DCMAKE_SYSTEM_NAME=Linux', '-DCMAKE_SYSTEM_PROCESSOR=aarch64']
    cfg(b, *emu, '-DRAVEN_MESON=/nonexistent/meson')
    rc, out = cfg(b)                                         # reconfigure, nothing given
    report(2, 'reconfigure keeps the default: still the OFF fallback with its warning',
           rc == 0 and 'releases no library for Linux aarch64' in out and '-DRAVEN_MF6=OFF' in out and not has_lib_target(b))
    report(2, '  RAVEN_MF6 stays empty in the cache', cache(b, 'RAVEN_MF6') == '', repr(cache(b, 'RAVEN_MF6')))
    if not TOOLS:
        report(2, '  becomes SOURCE when the tools appear', None, 'needs gfortran, meson, ninja, git')
        return
    rc, out = cfg(b, '-DRAVEN_MESON=' + MESON, '-DRAVEN_MF6_GIT_URL=' + git_repo(os.path.join(d, 'git'), '6.8.1'))   # meson appears
    report(2, '  becomes SOURCE when the tools appear', rc == 0 and 'RAVEN_MF6: SOURCE (default' in out and has_lib_target(b),
           '' if rc == 0 else out[-300:])


def check3():
    d = fresh('c3')
    if not CC:
        report(3, 'RPATH', None, 'no C compiler')
        return
    for name in ('priv', 'next'):                            # two libraries, each in its own folder outside the system dirs
        os.makedirs(os.path.join(d, name))
        open(os.path.join(d, name, name + '.c'), 'w').write('int %s_value(void){return 7;}\n' % name)
        rc, out = run([CC, '-shared', '-fPIC', '-o', os.path.join(d, name, 'lib%s.so' % name), os.path.join(d, name, name + '.c')])
    mini = os.path.join(d, 'mini')
    os.makedirs(mini)
    open(os.path.join(mini, 'main.c'), 'w').write(
        '#include <stdio.h>\nint priv_value(void);int next_value(void);\n'
        'int main(void){printf("mini %d\\n",priv_value()+next_value());return 0;}\n')
    open(os.path.join(mini, 'CMakeLists.txt'), 'w').write('''cmake_minimum_required(VERSION 3.20)
project(mini C)
set(RAVEN_MF6_FUNCTIONS_ONLY ON)
include("%s/cmake/RavenMF6.cmake")
add_executable(mini main.c)
target_link_libraries(mini "%s/priv/libpriv.so" "%s/next/libnext.so")
raven_mf6_rpath(mini)
add_custom_command(TARGET mini POST_BUILD COMMAND ${CMAKE_COMMAND} -E copy "%s/next/libnext.so" $<TARGET_FILE_DIR:mini>)
install(TARGETS mini RUNTIME DESTINATION bin)
install(FILES "%s/next/libnext.so" DESTINATION bin)
''' % (SRC, d, d, d, d))
    b = os.path.join(d, 'b')
    rc, out = run([CMAKE, '-S', mini, '-B', b, '-DCMAKE_INSTALL_PREFIX=' + os.path.join(d, 'inst')])
    rc2, out2 = run([CMAKE, '--build', b])
    rc3, out3 = run([os.path.join(b, 'mini')])
    report(3, 'build tree: the executable starts (private library found)', rc3 == 0 and 'mini 14' in out3, (out + out2 + out3)[-200:] if rc3 else '')
    run([CMAKE, '--install', b])
    moved = os.path.join(d, 'moved')
    shutil.move(os.path.join(d, 'inst'), moved)
    shutil.rmtree(os.path.join(d, 'next'))                 # libnext only beside the moved executable now
    shutil.rmtree(b)
    rc4, out4 = run([os.path.join(moved, 'bin', 'mini')])
    report(3, '  moved install: starts (library beside it via $ORIGIN, private one via link path)',
           rc4 == 0 and 'mini 14' in out4, out4[-200:] if rc4 else '')


def check4():
    d = fresh('c4')
    real = stub_lib(os.path.join(d, 'libmf6_663.so'), 'six-six-three')
    os.makedirs(os.path.join(d, 'link'))
    os.symlink(real, os.path.join(d, 'link', 'libmf6.so'))
    dotted = stub_lib(os.path.join(d, 'libmf6.so.6.8.1'), 'dotted')
    for tag, given, want in (('symlink to libmf6_663.so', os.path.join(d, 'link', 'libmf6.so'), real),
                             ('libmf6.so.6.8.1', dotted, dotted)):
        b = os.path.join(d, 'b_' + os.path.basename(want))
        inst = os.path.join(d, 'inst_' + os.path.basename(want))
        rc, out = cfg(b, '-DRAVEN_MF6=PATH', '-DRAVEN_MF6_PATH=' + given, '-DCMAKE_INSTALL_PREFIX=' + inst)
        rc2, out2 = run([CMAKE, '--build', b, '--target', 'raven_mf6_lib'])
        lib = os.path.join(b, 'libmf6.so')
        report(4, 'PATH, %s: copied next to Raven as libmf6.so' % tag,
               rc == 0 and rc2 == 0 and os.path.isfile(lib) and not os.path.islink(lib) and sha256(lib) == sha256(want),
               '' if rc == 0 else out[-300:])
        rc3, out3 = run([CMAKE, '--install', b, '--component', 'mf6'])
        ilib = os.path.join(inst, 'bin', 'libmf6.so')
        others = [f for f in os.listdir(os.path.join(inst, 'bin'))] if os.path.isdir(os.path.join(inst, 'bin')) else []
        report(4, '  installed as bin/libmf6.so (nothing under another name)',
               rc3 == 0 and os.path.isfile(ilib) and sha256(ilib) == sha256(want)
               and not [f for f in others if f.startswith('libmf6') and f not in ('libmf6.so', 'libmf6_version.txt')],
               ' '.join(others))


def check5():
    d = fresh('c5')
    lib = stub_lib(os.path.join(d, 'libmf6_given.so'))
    b = os.path.join(d, 'b_path')
    rc, out = cfg(b, '-DRAVEN_MF6_PATH=' + lib)
    run([CMAKE, '--build', b, '--target', 'raven_mf6_lib'])
    v = first_line(os.path.join(b, 'libmf6_version.txt'))
    report(5, 'PATH: libmf6_version.txt says "MODFLOW unknown (given library)"', v == 'MODFLOW unknown (given library)', v)
    p = package(b)
    report(5, '  package name without a MODFLOW version', p == 'Raven-%s-linux-x86_64' % RAVEN_VER, p)
    z = release_zip(os.path.join(d, 'renamed.zip'), '6.7.0', stub_lib(os.path.join(d, 'z.so'), 'zip670'))
    b = os.path.join(d, 'b_zip')
    rc, out = cfg(b, '-DRAVEN_MF6_ZIP=' + z)
    run([CMAKE, '--build', b, '--target', 'raven_mf6_lib'])
    v = first_line(os.path.join(b, 'libmf6_version.txt'))
    p = package(b)
    report(5, '  renamed zip: version file and package from its meson.build (6.7.0)',
           v == 'MODFLOW 6.7.0' and p == 'Raven-%s-mf6-6.7.0-linux-x86_64' % RAVEN_VER, '%s; %s' % (v, p))
    b = os.path.join(d, 'b_srcdir')
    rc, out = cfg(b, '-DRAVEN_MF6_SOURCE_DIR=' + source_folder(os.path.join(d, 'mf6src'), '6.7.1'))
    p = package(b)
    report(5, '  source folder: package from its meson.build (6.7.1)', rc == 0 and p == 'Raven-%s-mf6-6.7.1-linux-x86_64' % RAVEN_VER,
           p if rc == 0 else out[-300:])


def check6():
    d = fresh('c6')
    lib = stub_lib(os.path.join(d, 'libmf6.so'))
    z = release_zip(os.path.join(d, 'custom_build.zip'), '6.8.1', lib)
    rc, out = cfg(os.path.join(d, 'b_zip'), '-DRAVEN_MF6_ZIP=' + z)
    report(6, 'RAVEN_MF6_ZIP alone -> PREBUILT (also with source tools)', rc == 0 and 'RAVEN_MF6: PREBUILT (from RAVEN_MF6_ZIP)' in out,
           '' if rc == 0 else out[-300:])
    report(6, '  unpinned zip used with a warning ("used unchecked")', 'CMake Warning' in out and 'it is used unchecked' in out)
    rc, out = cfg(os.path.join(d, 'b_path'), '-DRAVEN_MF6_PATH=' + lib)
    report(6, '  RAVEN_MF6_PATH alone -> PATH', rc == 0 and 'RAVEN_MF6: PATH (from RAVEN_MF6_PATH)' in out)
    rc, out = cfg(os.path.join(d, 'b_src'), '-DRAVEN_MF6_SOURCE_DIR=' + source_folder(os.path.join(d, 'src'), '6.8.1'))
    report(6, '  RAVEN_MF6_SOURCE_DIR alone -> SOURCE', rc == 0 and 'RAVEN_MF6: SOURCE (from RAVEN_MF6_SOURCE_DIR' in out,
           '' if rc == 0 else out[-300:])
    rc, out = cfg(os.path.join(d, 'b_both'), '-DRAVEN_MF6=PATH', '-DRAVEN_MF6_PATH=' + lib, '-DRAVEN_MF6_ZIP=' + z)
    report(6, '  RAVEN_MF6=PATH with RAVEN_MF6_ZIP: the zip is reported as ignored',
           rc == 0 and 'RAVEN_MF6_ZIP is ignored with RAVEN_MF6=PATH' in out)


def check7():
    d = fresh('c7')
    if not TOOLS:
        report(7, 'FC passed to meson', None, 'needs gfortran, meson, ninja, git')
        return
    os.makedirs(os.path.join(d, 'fc'))
    myfc = os.path.join(d, 'fc', 'myfc')
    os.symlink(GFORTRAN, myfc)
    b = os.path.join(d, 'b')
    rc, out = cfg(b, '-DRAVEN_MF6_SOURCE_DIR=' + source_folder(os.path.join(d, 'src'), '6.8.1'),
                  '-DCMAKE_Fortran_COMPILER=' + GFORTRAN, env=env_base(FC=myfc))
    txt = ''
    for root, dirs, files in os.walk(os.path.join(b, 'mf6', 'source')):   # ExternalProject's record of the configure command
        if 'mf6_source-cfgcmd.txt' in files:
            txt = open(os.path.join(root, 'mf6_source-cfgcmd.txt')).read()
    report(7, 'FC=W/fc/myfc (CMake\'s check: gfortran): meson setup runs with FC=.../fc/myfc',
           rc == 0 and ('FC=' + myfc) in txt, txt[:200] if rc == 0 else out[-300:])


def check8():
    d = fresh('c8')
    fake = os.path.join(d, 'meson')
    open(fake, 'w').write('#!/bin/sh\necho "this is not a version"\n')
    os.chmod(fake, 0o755)
    rc, out = cfg(os.path.join(d, 'b_def'), '-DRAVEN_MESON=' + fake)
    report(8, 'meson without a readable version: the default names it', rc == 0 and
           ("gives no readable version ('this is not a version')" in out), '' if rc == 0 else out[-300:])
    rc, out = cfg(os.path.join(d, 'b_src'), '-DRAVEN_MF6=SOURCE', '-DRAVEN_MESON=' + fake)
    report(8, '  explicit SOURCE stops and names it', rc != 0 and "gives no readable version ('this is not a version')" in out)


def check9():
    d = fresh('c9')
    if not GFORTRAN:
        report(9, 'DESTDIR bundling', None, 'needs gfortran')
        return
    f = os.path.join(d, 'f.f90')
    open(f, 'w').write('subroutine hello() bind(c)\n  write(*,*) "hello from a Fortran library"\nend subroutine\n')
    lib = os.path.join(d, 'libmf6.so')
    rc, out = run([GFORTRAN, '-shared', '-fPIC', '-o', lib, f])
    ld = run(['ldd', lib])[1]
    if 'libgfortran.so.5' not in ld:
        report(9, 'DESTDIR bundling', None, 'the test library does not link libgfortran.so.5')
        return
    b = os.path.join(d, 'b')
    prefix = '/opt/raven_cmake_check_%d' % os.getpid()      # never created: DESTDIR stages it
    rc, out = cfg(b, '-DRAVEN_MF6_PATH=' + lib, '-DCMAKE_INSTALL_PREFIX=' + prefix)
    run([CMAKE, '--build', b, '--target', 'raven_mf6_lib'])
    stage = os.path.join(d, 'stage')
    rc, out = run([CMAKE, '--install', b, '--component', 'mf6'], env=env_base(DESTDIR=stage))
    got = os.path.join(stage + prefix, 'bin')
    report(9, 'DESTDIR=<absolute>: staged bin has libmf6.so and libgfortran.so.5',
           rc == 0 and os.path.isfile(os.path.join(got, 'libmf6.so')) and os.path.isfile(os.path.join(got, 'libgfortran.so.5')),
           ' '.join(os.listdir(got)) if os.path.isdir(got) else out[-300:])
    rc, out = run([CMAKE, '--install', b, '--component', 'mf6'], cwd=d, env=env_base(DESTDIR='relstage'))
    got = os.path.join(d, 'relstage' + prefix, 'bin')
    report(9, '  DESTDIR=<relative>: the same', rc == 0 and os.path.isfile(os.path.join(got, 'libgfortran.so.5')),
           ' '.join(os.listdir(got)) if os.path.isdir(got) else out[-300:])
    report(9, '  nothing installed outside DESTDIR', not os.path.exists(prefix))


def check10():
    d = fresh('c10')
    if not (GFORTRAN and MESON and NINJA):
        report(10, 'no git', None, 'needs gfortran, meson, ninja')
        return
    nogit = ['-DCMAKE_DISABLE_FIND_PACKAGE_Git=ON', '-DGIT_EXECUTABLE=GIT_EXECUTABLE-NOTFOUND']
    rc, out = cfg(os.path.join(d, 'b_def'), *nogit)
    report('10a', 'no git, default: falls back (not SOURCE), naming git', rc == 0 and 'git not found' in out
           and 'RAVEN_MF6: SOURCE' not in out, '' if rc == 0 else out[-300:])
    rc, out = cfg(os.path.join(d, 'b_src'), '-DRAVEN_MF6=SOURCE', *nogit)
    report('10b', 'no git, RAVEN_MF6=SOURCE: stops, naming git', rc != 0 and 'git not found' in out)
    rc, out = cfg(os.path.join(d, 'b_url'), '-DRAVEN_MF6=SOURCE', '-DRAVEN_MF6_SOURCE_URL=file://%s/v6.8.1.tar.gz' % d, *nogit)
    report('10c', 'no git, SOURCE from RAVEN_MF6_SOURCE_URL: configures', rc == 0 and 'git not found' not in out,
           '' if rc == 0 else out[-300:])


def check11():
    d = fresh('c11')
    os.makedirs(os.path.join(d, 'z'))
    z = os.path.join(d, 'z', 'mymf6.zip')
    la = stub_lib(os.path.join(d, 'a.so'), 'first zip')
    lb = stub_lib(os.path.join(d, 'b.so'), 'second zip, same name')
    b = os.path.join(d, 'b')
    unpacked = os.path.join(b, 'mf6', 'prebuilt', 'mf6.7.0_linux', 'bin', 'libmf6.so')
    release_zip(z, '6.7.0', la)
    rc, out = cfg(b, '-DRAVEN_MF6_ZIP=' + z)
    report(11, 'unpinned zip unpacked', rc == 0 and os.path.exists(unpacked) and sha256(unpacked) == sha256(la),
           '' if rc == 0 else out[-300:])
    release_zip(z, '6.7.0', lb)                              # replaced by another zip of the same name
    rc, out = cfg(b)
    report(11, '  replaced (same name): unpacked again', rc == 0 and os.path.exists(unpacked) and sha256(unpacked) == sha256(lb))
    sentinel = os.path.join(b, 'mf6', 'prebuilt', 'SENTINEL')
    open(sentinel, 'w').write('unpacking empties this folder\n')
    rc, out = cfg(b)
    report(11, '  unchanged: not unpacked again (sentinel in mf6/prebuilt survives)', rc == 0 and os.path.exists(sentinel))


def check12():
    d = fresh('c12')
    win = ['-DCMAKE_SYSTEM_NAME=Windows', '-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY', '-DRAVEN_MESON=/nonexistent/meson']
    rc, out = cfg(os.path.join(d, 'b_x64'), *win, '-DCMAKE_SYSTEM_PROCESSOR=AMD64', '-DRAVEN_MF6=PREBUILT')
    report(12, 'Windows AMD64, PREBUILT: takes mf6.8.1_win64.zip', 'mf6.8.1_win64.zip' in out, out[-200:] if 'win64' not in out else '')
    rc, out = cfg(os.path.join(d, 'b_arm'), *win, '-DCMAKE_SYSTEM_PROCESSOR=ARM64', '-DRAVEN_MF6=PREBUILT')
    report(12, '  Windows ARM64, PREBUILT: stops, no library for Windows ARM64',
           rc != 0 and 'releases no library for Windows ARM64' in out and 'win64.zip' not in out)
    rc, out = cfg(os.path.join(d, 'b_armdef'), *win, '-DCMAKE_SYSTEM_PROCESSOR=ARM64')
    report(12, '  Windows ARM64, default: OFF with a warning', rc == 0 and 'releases no library for Windows ARM64' in out
           and '-DRAVEN_MF6=OFF' in out and not has_lib_target(os.path.join(d, 'b_armdef')))


def check13():
    d = fresh('c13')
    b = os.path.join(d, 'b_url')
    rc, out = cfg(b, '-DRAVEN_MF6=SOURCE', '-DRAVEN_MF6_SOURCE_URL=file://%s/v6.7.2.tar.gz' % d)
    p = package(b)
    report(13, 'SOURCE_URL .../v6.7.2.tar.gz: package version 6.7.2', rc == 0 and p == 'Raven-%s-mf6-6.7.2-linux-x86_64' % RAVEN_VER,
           p if rc == 0 else out[-300:])
    z = release_zip(os.path.join(d, 'my_mf6_download.zip'), '6.8.1', stub_lib(os.path.join(d, 'l.so')), top='mf6.8.1_linux')
    rc, out = cfg(os.path.join(d, 'b_zip'), '-DRAVEN_MF6_ZIP=' + z)
    report(13, '  unpinned my_mf6_download.zip: info line "not checked", not "official release"',
           rc == 0 and 'my_mf6_download.zip given by RAVEN_MF6_ZIP (bin/libmf6.so; not checked)' in out
           and 'official release' not in out)


def check14():
    d = fresh('c14')
    lib = stub_lib(os.path.join(d, 'l.so'), 'fourteen')
    z = release_zip(os.path.join(d, 'myzip.zip'), '6.8.1', lib)
    right = sha256(z)
    wrong = hashlib.sha256(b'not the zip').hexdigest()
    b = os.path.join(d, 'b')
    rc0, out = cfg(b, '-DRAVEN_MF6_ZIP=' + z)
    rc, out = cfg(b, '-DRAVEN_MF6_ZIP_SHA256=' + wrong)
    report(14, 'unpacked unpinned zip, then a wrong RAVEN_MF6_ZIP_SHA256: configure stops',
           rc0 == 0 and rc != 0 and right in out and wrong in out)
    rc, out = cfg(b, '-DRAVEN_MF6_ZIP_SHA256=' + right)
    report(14, '  the right SHA256: passes, named as RAVEN_MF6_ZIP_SHA256, not official',
           rc == 0 and 'SHA256 of RAVEN_MF6_ZIP_SHA256' in out and 'official' not in out, '' if rc == 0 else out[-300:])
    rel = os.path.join(d, 'rel', '6.7.0')
    os.makedirs(rel)
    dz = release_zip(os.path.join(rel, 'mf6.7.0_linux.zip'), '6.7.0', lib)
    dl = ['-DRAVEN_MF6=PREBUILT', '-DRAVEN_MF6_VERSION=6.7.0']
    b = os.path.join(d, 'b_dl')
    rc, out = cfg(b, *dl, '-DRAVEN_MF6_ZIP_SHA256=' + wrong, release='file://' + os.path.join(d, 'rel'))
    report(14, '  downloaded unpinned zip, wrong SHA256: stops', rc != 0 and wrong in out and sha256(dz) in out)
    rc, out = cfg(b, *dl, '-DRAVEN_MF6_ZIP_SHA256=' + sha256(dz), release='file://' + os.path.join(d, 'rel'))
    report(14, '  downloaded unpinned zip, right SHA256: passes, not official',
           rc == 0 and 'downloaded, SHA256 of RAVEN_MF6_ZIP_SHA256' in out and 'official' not in out
           and os.path.exists(os.path.join(b, 'mf6', 'prebuilt', 'mf6.7.0_linux', 'bin', 'libmf6.so')),
           '' if rc == 0 else out[-300:])


def check15():
    d = fresh('c15')
    if not TOOLS:
        report(15, 'offline default', None, 'needs gfortran, meson, ninja, git')
        return
    b = os.path.join(d, 'b_off')
    rc, out = cfg(b)                                          # tools found; git and release URLs point at missing folders
    report(15, 'tools, repository unreachable, no release: OFF with a warning at configure time',
           rc == 0 and 'cannot be reached for tag 6.8.1' in out and 'RAVEN_MF6: SOURCE' not in out and '-DRAVEN_MF6=OFF' in out
           and not has_lib_target(b), '' if rc == 0 else out[-300:])
    rel = os.path.join(d, 'rel', '6.7.0')
    os.makedirs(rel)
    release_zip(os.path.join(rel, 'mf6.7.0_linux.zip'), '6.7.0', stub_lib(os.path.join(d, 'l.so'), 'fifteen'))
    b = os.path.join(d, 'b_pre')
    rc, out = cfg(b, '-DRAVEN_MF6_VERSION=6.7.0', release='file://' + os.path.join(d, 'rel'))
    report(15, '  repository unreachable, release reachable: PREBUILT with the library target',
           rc == 0 and 'cannot be reached for tag 6.7.0' in out and 'RAVEN_MF6: PREBUILT (default' in out and has_lib_target(b),
           '' if rc == 0 else out[-300:])
    rc2, out2 = run([CMAKE, '--build', b, '--target', 'raven_mf6_lib'])
    report(15, '  ... and the build needs no network', rc2 == 0 and os.path.isfile(os.path.join(b, 'libmf6.so')), out2[-300:] if rc2 else '')
    b = os.path.join(d, 'b_src')
    rc, out = cfg(b, '-DRAVEN_MF6_GIT_URL=' + git_repo(os.path.join(d, 'git'), '6.8.1'))
    report(15, '  repository reachable: SOURCE', rc == 0 and 'RAVEN_MF6: SOURCE (default' in out and 'reachable' in out
           and has_lib_target(b), '' if rc == 0 else out[-300:])


def check16():
    d = fresh('c16')
    b = os.path.join(d, 'b')
    rc, out = cfg(b, '-G', 'Unix Makefiles', '-DRAVEN_MF6=OFF')
    fl = os.path.join(b, 'CMakeFiles', 'Raven.dir', 'flags.make')
    flags = open(fl).read() if os.path.exists(fl) else ''
    report(16, 'Unix Makefiles, no CMAKE_BUILD_TYPE: Release (cache, -O3 in flags.make)',
           rc == 0 and cache(b, 'CMAKE_BUILD_TYPE') == 'Release' and '-O3' in flags,
           '%r %s' % (cache(b, 'CMAKE_BUILD_TYPE'), re.findall(r'CXX_FLAGS = .*', flags)))
    b = os.path.join(d, 'b_dbg')
    rc, out = cfg(b, '-G', 'Unix Makefiles', '-DRAVEN_MF6=OFF', '-DCMAKE_BUILD_TYPE=Debug')
    report(16, '  -DCMAKE_BUILD_TYPE=Debug is kept', rc == 0 and cache(b, 'CMAKE_BUILD_TYPE') == 'Debug', repr(cache(b, 'CMAKE_BUILD_TYPE')))


def check17():
    d = fresh('c17')
    rc, out = cfg(os.path.join(d, 'b_v'), '-DRAVEN_MF6=PREBUILT', '-DRAVEN_MF6_VERSION=6.4.0')
    report(17, 'PREBUILT, RAVEN_MF6_VERSION=6.4.0: stops naming 6.5.0', rc != 0 and 'MODFLOW 6.4.0, older than 6.5.0' in out
           and 'downloading' not in out, out[-200:] if rc == 0 else '')
    if TOOLS:
        rc, out = cfg(os.path.join(d, 'b_s'), '-DRAVEN_MF6=SOURCE', '-DRAVEN_MF6_VERSION=6.4.0')
        report(17, '  SOURCE, RAVEN_MF6_VERSION=6.4.0: stops', rc != 0 and 'MODFLOW 6.4.0, older than 6.5.0' in out)
    z = release_zip(os.path.join(d, 'old.zip'), '6.4.0', stub_lib(os.path.join(d, 'o.so'), 'old'))
    rc, out = cfg(os.path.join(d, 'b_z'), '-DRAVEN_MF6_ZIP=' + z)
    report(17, '  a zip whose meson.build says 6.4.0: stops', rc != 0 and 'MODFLOW 6.4.0, older than 6.5.0' in out, out[-200:] if rc == 0 else '')
    rc, out = cfg(os.path.join(d, 'b_d'), '-DRAVEN_MF6_SOURCE_DIR=' + source_folder(os.path.join(d, 'src640'), '6.4.0'))
    report(17, '  a source folder of 6.4.0: stops', rc != 0 and 'MODFLOW 6.4.0, older than 6.5.0' in out, out[-200:] if rc == 0 else '')
    z = release_zip(os.path.join(d, 'new.zip'), '6.7.0', stub_lib(os.path.join(d, 'n.so'), 'new'))
    rc, out = cfg(os.path.join(d, 'b_ok'), '-DRAVEN_MF6_ZIP=' + z)
    report(17, '  6.7.0: configures, warning names the tested 6.8.1', rc == 0 and 'is MODFLOW 6.7.0; Raven\'s coupling was tested with 6.8.1' in out,
           '' if rc == 0 else out[-300:])


def _bundle(lib, system, name, prefix, env=None, extra=()):
    return run([CMAKE, '-DRAVEN_MF6_BUNDLE_LIB=' + lib, '-DRAVEN_MF6_BUNDLE_SYSTEM=' + system, '-DRAVEN_MF6_BUNDLE_NAME=' + name,
                '-DCMAKE_INSTALL_PREFIX=' + prefix] + list(extra) + ['-P', os.path.join(SRC, 'cmake', 'RavenMF6Bundle.cmake')], env=env)


def check18():
    d = fresh('c18')
    clang = shutil.which('clang')
    tools = [os.path.join(LLVM, x) for x in ('ld64.lld', 'llvm-otool', 'llvm-install-name-tool')]
    if not clang or not all(os.path.exists(x) for x in tools):
        report(18, 'macOS bundling (emulated)', None, 'needs clang and %s/{ld64.lld,llvm-otool,llvm-install-name-tool}' % LLVM)
    else:
        lld, otool, intool = tools
        tc_ = os.path.join(d, 'gcc', 'lib'); os.makedirs(tc_); bdir = os.path.join(d, 'b'); os.makedirs(bdir)
        src = {'q': 'int qm(void){return 1;}', 'g': 'int gs(void){return 2;}',
               'f': 'int qm(void);int gs(void);int gf(void){return qm()+gs();}', 'm': 'int gf(void);int get_version(char*b){return gf();}'}
        for k, s in src.items():
            open(os.path.join(d, k + '.c'), 'w').write(s + '\n')
            run([clang, '--target=arm64-apple-macos11', '-c', os.path.join(d, k + '.c'), '-o', os.path.join(d, k + '.o')])
        LD = [lld, '-arch', 'arm64', '-platform_version', 'macos', '11.0', '11.0', '-dylib', '-undefined', 'dynamic_lookup']
        q, g, f = (os.path.join(tc_, n) for n in ('libquadmath.0.dylib', 'libgcc_s.1.1.dylib', 'libgfortran.5.dylib'))
        lib = os.path.join(bdir, 'libmf6.dylib')
        r = [run(LD + ['-install_name', '@rpath/libquadmath.0.dylib', '-o', q, os.path.join(d, 'q.o')]),
             run(LD + ['-install_name', '@rpath/libgcc_s.1.1.dylib', '-o', g, os.path.join(d, 'g.o')]),
             run(LD + ['-install_name', '@rpath/libgfortran.5.dylib', '-rpath', '@loader_path', '-o', f, os.path.join(d, 'f.o'), q, g]),
             run(LD + ['-install_name', '@rpath/libmf6.dylib', '-rpath', tc_, '-rpath', '@loader_path', '-o', lib, os.path.join(d, 'm.o'), f, g])]
        if any(rc for rc, _ in r):
            report(18, 'macOS bundling (emulated)', None, 'could not link the Mach-O stand-ins: ' + ' '.join(o for _, o in r)[-200:])
        else:
            inst = os.path.join(d, 'inst'); os.makedirs(os.path.join(inst, 'bin'))
            shutil.copy2(lib, os.path.join(inst, 'bin'))                 # (install(PROGRAMS) puts libmf6 there first)
            cs = os.path.join(d, 'codesign'); log = os.path.join(d, 'signed.txt')
            open(cs, 'w').write('#!/bin/sh\necho "$4" >> %s\n' % log); os.chmod(cs, 0o755)
            rc, out = _bundle(lib, 'Darwin', 'libmf6.dylib', inst, extra=['-DRAVEN_MF6_OTOOL=' + otool, '-DRAVEN_MF6_INSTALL_NAME_TOOL=' + intool,
                                                                          '-DRAVEN_MF6_CODESIGN=' + cs])
            got = sorted(os.listdir(os.path.join(inst, 'bin')))
            report(18, 'macOS: libgfortran, and libquadmath and libgcc_s through it, installed',
                   rc == 0 and got == ['libgcc_s.1.1.dylib', 'libgfortran.5.dylib', 'libmf6.dylib', 'libquadmath.0.dylib'], ' '.join(got) if rc == 0 else out[-300:])
            refs = ''.join(run([otool, '-L', os.path.join(inst, 'bin', n)])[1] for n in got)
            report(18, '  every runtime reference is @loader_path/ (none left @rpath/ or absolute)',
                   '@loader_path/libgfortran.5.dylib' in refs and '@loader_path/libquadmath.0.dylib' in refs
                   and not re.search(r'(@rpath/|%s/)lib(gfortran|quadmath|gcc_s)' % re.escape(tc_), refs),
                   '' if '@loader_path/libquadmath' in refs else refs[-300:])
            signed = sorted(os.path.basename(x) for x in open(log).read().split()) if os.path.exists(log) else []
            report(18, '  every edited file signed again (codesign -f -s -)', signed == got, ' '.join(signed))
    # Windows (emulated): stand-in import listers; libgfortran-5.dll imports libquadmath-0.dll and libgcc_s_seh-1.dll
    tl = os.path.join(d, 'wtools'); fc = os.path.join(d, 'wfc'); os.makedirs(tl); os.makedirs(fc)
    for n in ('gfortran.exe', 'libgfortran-5.dll', 'libquadmath-0.dll', 'libgcc_s_seh-1.dll'):
        open(os.path.join(fc, n), 'w').write('stand-in\n')
    wlib = os.path.join(d, 'libmf6.dll'); open(wlib, 'w').write('stand-in\n')
    deps = 'case "$f" in libmf6.dll) d="KERNEL32.dll libgfortran-5.dll";; libgfortran-5.dll) d="KERNEL32.dll libquadmath-0.dll libgcc_s_seh-1.dll";; *) d="KERNEL32.dll";; esac\n'
    open(os.path.join(tl, 'objdump'), 'w').write('#!/bin/sh\nf=${2##*/}\n' + deps + 'for x in $d; do printf "\\tDLL Name: %s\\n" $x; done\n')
    open(os.path.join(tl, 'dumpbin'), 'w').write('#!/bin/sh\nf=${3##*/}\n' + deps +
        'printf "Dump of file %s\\r\\n\\r\\n  Image has the following dependencies:\\r\\n\\r\\n" "$3"; for x in $d; do printf "    %s\\r\\n" $x; done; printf "\\r\\n  Summary\\r\\n"\n')
    for x in ('objdump', 'dumpbin'): os.chmod(os.path.join(tl, x), 0o755)
    for tool in ('objdump', 'dumpbin'):
        if tool == 'dumpbin': os.rename(os.path.join(tl, 'objdump'), os.path.join(tl, 'objdump.off'))
        inst = os.path.join(d, 'winst_' + tool)
        rc, out = _bundle(wlib, 'Windows', 'libmf6.dll', inst, env=env_base(PATH=tl), extra=['-DRAVEN_MF6_BUNDLE_FC=' + os.path.join(fc, 'gfortran.exe')])
        got = sorted(os.listdir(os.path.join(inst, 'bin'))) if os.path.isdir(os.path.join(inst, 'bin')) else []
        report(18, '  Windows (%s): libgfortran-5.dll and the DLLs it imports installed' % tool,
               rc == 0 and got == ['libgcc_s_seh-1.dll', 'libgfortran-5.dll', 'libquadmath-0.dll'], ' '.join(got) if rc == 0 else out[-300:])


def check19():
    d = fresh('c19')
    rc, out = cfg(os.path.join(d, 'b_dir'), '-DRAVEN_MF6=PATH', '-DRAVEN_MF6_PATH=' + d)
    report(19, 'RAVEN_MF6_PATH a folder: "is a folder; give the library file itself"', rc != 0 and 'is a folder; give the library file itself' in out,
           re.findall(r'is a folder.{0,40}', out))
    z = release_zip(os.path.join(d, 'z.zip'), '6.8.1', stub_lib(os.path.join(d, 'l.so')))
    rc, out = cfg(os.path.join(d, 'b_sha'), '-DRAVEN_MF6_ZIP=' + z, '-DRAVEN_MF6_ZIP_SHA256=abc123')
    report(19, '  6-digit RAVEN_MF6_ZIP_SHA256: "is not a SHA256 (64 hexadecimal digits"', rc != 0 and 'is not a SHA256 (64 hexadecimal digits' in out
           and 'damaged or different file' not in out)


CHECKS = {1: check1, 2: check2, 3: check3, 4: check4, 5: check5, 6: check6, 7: check7, 8: check8, 9: check9,
          10: check10, 11: check11, 12: check12, 13: check13, 14: check14, 15: check15, 16: check16, 17: check17,
          18: check18, 19: check19}

# one mutation per check: (file, text in it, replacement) = the bug the check was written for
MUTATIONS = {
    1: ('cmake/RavenMF6.cmake', 'macro(_rmf6_giveup)\n', 'macro(_rmf6_giveup)\n  set(_rmf6_explicit TRUE)\n'),
    2: ('cmake/RavenMF6.cmake', '  set(RAVEN_MF6_MODE OFF)\n  return()\nendmacro()',
        '  set(RAVEN_MF6_MODE OFF)\n  set(RAVEN_MF6 OFF CACHE STRING "" FORCE)\n  return()\nendmacro()'),
    3: ('cmake/RavenMF6.cmake', '\n                        INSTALL_RPATH_USE_LINK_PATH TRUE)', ')'),
    4: ('CMakeLists.txt', 'DESTINATION bin RENAME "${RAVEN_MF6_LIBNAME}" COMPONENT mf6', 'DESTINATION bin COMPONENT mf6'),
    5: ('cmake/RavenMF6.cmake', '  set(_vtext "unknown (given library)")', '  set(_vtext "${RAVEN_MF6_VERSION}")'),
    6: ('cmake/RavenMF6.cmake', 'elseif(NOT "${RAVEN_MF6_ZIP}" STREQUAL "")\n  set(_rmf6_explicit TRUE)',
        'elseif(FALSE)\n  set(_rmf6_explicit TRUE)'),
    7: ('cmake/RavenMF6.cmake', '  elseif(NOT "$ENV{FC}" STREQUAL "")', '  elseif(FALSE)'),
    8: ('cmake/RavenMF6.cmake', '      list(APPEND _miss "meson ${_meson} gives no readable version (\'${_mshow}\')")',
        '      list(APPEND _miss "meson ${_meson}: version too old")'),
    9: ('cmake/RavenMF6Bundle.cmake', 'set(_dest "${CMAKE_INSTALL_PREFIX}/bin")',
        'set(_dest "${CMAKE_INSTALL_PREFIX}/bin")\nif(DEFINED ENV{DESTDIR})\n  return()\nendif()'),
    10: ('cmake/RavenMF6.cmake', '    find_package(Git QUIET)                        # the source is cloned\n'
         '    if(GIT_FOUND AND GIT_EXECUTABLE)', '    if(TRUE)'),
    11: ('cmake/RavenMF6.cmake', 'if(_old_key STREQUAL _key AND EXISTS', 'if(FALSE AND EXISTS'),
    12: ('cmake/RavenMF6.cmake', 'if(_la MATCHES "^(x64|amd64|x86_64|em64t)$")', 'if(_la MATCHES "64")'),
    13: ('cmake/RavenMF6.cmake', '      elseif(_uname MATCHES "^(modflow6-)?v?', '      elseif(FALSE AND _uname MATCHES "^(modflow6-)?v?'),
    14: ('cmake/RavenMF6.cmake', '    if(_expected AND NOT _actual STREQUAL _expected)\n      message(FATAL_ERROR "RAVEN_MF6_ZIP:',
         '    if(NOT EXISTS "${_stamp}" AND _expected AND NOT _actual STREQUAL _expected)\n      message(FATAL_ERROR "RAVEN_MF6_ZIP:'),
    15: ('cmake/RavenMF6.cmake', '    if(NOT _rmf6_git_ok)                           # offline', '    if(FALSE)'),
    16: ('CMakeLists.txt', 'if(NOT _raven_multi_config AND NOT CMAKE_BUILD_TYPE)', 'if(FALSE)'),
    17: ('cmake/RavenMF6.cmake', '  if(NOT "${v}" STREQUAL "" AND "${v}" VERSION_LESS RAVEN_MF6_MIN_VERSION)', '  if(FALSE)'),
    18: ('cmake/RavenMF6Bundle.cmake', '        list(APPEND _queue "${_real}|${_n}")', '        # (dependencies of dependencies not followed)'),
    19: ('cmake/RavenMF6.cmake', '  set(_rmf6_msg "${ARGV0}")\n', '  string(CONCAT _rmf6_msg ${ARGV})\n'),
}


def selftest(only):
    """applies each check's mutation to a copy of the source (cmake/, CMakeLists.txt, src/RavenInclude.h and the source
    file list are all a configure needs) and runs that check against it; each must fail"""
    global SRC, results
    good = SRC
    nfail = 0
    for n in only:
        f, old, new = MUTATIONS[n]
        mut = fresh('selftest_src_%d' % n)
        shutil.copytree(os.path.join(good, 'cmake'), os.path.join(mut, 'cmake'))
        shutil.copy2(os.path.join(good, 'CMakeLists.txt'), mut)
        os.makedirs(os.path.join(mut, 'src'))
        for s in os.listdir(os.path.join(good, 'src')):
            if s.endswith(('.cpp', '.h')):
                shutil.copy2(os.path.join(good, 'src', s), os.path.join(mut, 'src', s))
        p = os.path.join(mut, f)
        t = open(p).read()
        if t.count(old) != 1:
            print('%-3s mutation text not found once in %s: cannot show this check failing' % (n, f))
            nfail += 1
            continue
        open(p, 'w').write(t.replace(old, new))
        SRC = mut
        results = []
        print('--- check %d on a source with its bug put back (%s)' % (n, f))
        try:
            CHECKS[n]()
        except Exception as e:
            report(n, 'exception: %s' % e, False)
        failed = [r for r in results if r[2] is False]
        skipped = all(r[2] is None for r in results)
        print('%-3s %s' % (n, 'fails on its mutation: ok' if failed else ('SKIPPED' if skipped else 'DOES NOT FAIL on its mutation')))
        nfail += 0 if (failed or skipped) else 1
    SRC = good
    print('cmake checks self-test: %s' % ('ALL CHECKS CAN FAIL' if nfail == 0 else '%d checks do not fail on their mutation' % nfail))
    return nfail


def main():
    if not os.path.exists(os.path.join(SRC, 'cmake', 'RavenMF6.cmake')):
        print('cmake checks: %s has no cmake/RavenMF6.cmake (not a Raven checkout with the MODFLOW 6 build); give --src' % SRC)
        return 1
    os.makedirs(WORK, exist_ok=True)
    only = [int(x) for x in A.only.split(',') if x.strip()] or sorted(CHECKS)
    print('Raven source %s; work %s; cmake %s' % (SRC, WORK, run([CMAKE, '--version'])[1].split('\n')[0]))
    if A.selftest:
        n = selftest(only)
    else:
        for c in only:
            try:
                CHECKS[c]()
            except Exception as e:
                report(c, 'exception: %s' % e, False)
        bad = [r for r in results if r[2] is False]
        skip = [r for r in results if r[2] is None]
        n = len(bad)
        print('cmake checks: %s (%d parts in %d checks%s)' % ('ALL PASSED' if not bad else '%d FAILED' % len(bad),
              len(results), len(only), ', %d skipped' % len(skip) if skip else ''))
    if not A.keep:
        shutil.rmtree(WORK, ignore_errors=True)
    return n


if __name__ == '__main__':
    sys.exit(main())
