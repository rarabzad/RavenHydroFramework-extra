# MODFLOW 6 build integration (rebuild, final form incl. audit rounds 8-10)

Code: RavenHydroFramework `CMakeLists.txt`, `cmake/RavenMF6.cmake`, `RavenMF6Verify.cmake` (git clone + pinned-commit check,
build time), `RavenMF6Copy.cmake` (library + `libmf6_version.txt` next to Raven, build time), `RavenMF6Bundle.cmake`
(Fortran runtime at install time), `src/MF6Engine.cpp/.h` (version guard), `.github/workflows/raven-mf6.yml`,
`testing.yml` (`-DRAVEN_MF6=OFF`). Extra: manual ch9 file (chapter "Developer guide": sections Building, Getting MODFLOW 6),
ch7 step 0, README.md, examples/README.md, tools/get_mf6.py, tests/cmake_checks.py, tests/mf6version_check.py
(+ mf6version_stub.c), tests/mf6lib_check.py part 0, run_all steps `mf6lib_unit`, `mf6version`, `cmake`.

## Decisions

1. Run-time loading of a bundled libmf6 (dlopen/LoadLibrary), not static linking (user approved item 1, 27 Oct).
2. `RAVEN_MF6` cache entry keeps only a value the user gives; empty = default, re-chosen at every configure (R8 h5.2).
   No internal flag needed. Old build folders whose first version cached the default read it as explicit (documented).
3. A plain `-DRAVEN_MF6=OFF` returns from RavenMF6.cmake before creating any cache entry, target, RPATH or install
   rule, and CMakeLists adds install/CPack only for the other modes. Verified: link.txt, flags.make, build.make, Makefile,
   cmake_install.cmake, CMakeCache.txt (paths normalised) identical to the base f12baab; the only generated difference
   is `CMakeFiles/Makefile.cmake` listing RavenMF6.cmake as a CMake input (re-run dependency, no compile/link effect).
4. Default order: offline option names its mode (PATH > ZIP > SOURCE_DIR/URL; others reported ignored) -> SOURCE
   (Fortran + meson >= 1.7 + ninja + git; git only when no SOURCE_DIR/URL) -> PREBUILT (platform has a release zip)
   -> OFF with warning naming `-DRAVEN_MF6=OFF`, SOURCE and PATH. A failed default download -> OFF with warning. Explicit
   or inferred modes stop (FATAL) with alternatives. A checksum mismatch always stops (also in the default).
5. Fortran compiler for meson: RAVEN_MF6_FORTRAN, then **$ENV{FC}**, then check_language(Fortran), then gfortran/ifx/ifort
   on PATH. FC is read before CMake's check (the spec lists the check first): with Makefile/Ninja generators CMake's
   check returns FC anyway, with Visual Studio it ignores FC (R8 h5.7), and meson itself uses FC; reading FC first makes
   the choice the same everywhere and makes cmake_checks check 7 meaningful (CMake's check is given another compiler;
   removing the FC lines fails it). A NOTFOUND result of check_language is re-checked at every configure.
6. SOURCE: ExternalProject `mf6_source` (so `mf6_source-cfgcmd.txt` records the meson command with FC). Download step
   = RavenMF6Verify.cmake: `git clone --depth 1 --branch <tag>`, HEAD compared with the pinned commit
   5b2ebd1a95720d5c3732dc482e05fbf559e6ef41 for 6.8.1 (verified with `git ls-remote` on 28 Oct); `--no-single-branch`
   not used (a tag clone needs no other refs). `meson setup --reconfigure ... --buildtype=release --wrap-mode=nodownload
   -Ddebug=false`, `meson compile mf6:shared_library`. On Linux/macOS the library gets run path `$ORIGIN`/`@loader_path`
   (`-Dfortran_link_args`), so the libgfortran installed beside it is used by the dynamic loader (Raven's own RUNPATH
   does not apply to the dependencies of a dlopened library). Verified: `readelf -d` RUNPATH [$ORIGIN]; in the moved
   install `ldd libmf6.so` resolves libgfortran.so.5 to the bin folder.
7. PREBUILT: pins (SHA256 of the zips downloaded 28 Oct 2026; libmf6.so inside the linux zip = 09fb8cf6..., the library
   shipped in lib/mf6):
   mf6.8.1_linux.zip 439a29f3e60f8e88b0ac083db10c92e3474b203d18ca6583863d8464b811ba90,
   mf6.8.1_macarm.zip 2167d553d8f0c57c6c356156cb158b14e60684199785a82031b5c6cccf0b1e4c,
   mf6.8.1_win64.zip de54d0d78f2c3e5aa2104ec688c458e85ac4cbc770feff24015df4ba7d027837; mf6.8.1_mac.zip is 404.
   Unpack only `*libmf6.<ext>` and `*meson.build` into an emptied `mf6/prebuilt`; version from the shortest-path
   meson.build, else from the name `mfX.Y.Z_`. Stamp `mf6/prebuilt.stamp` (key, lib, version): key = the local zip's own
   SHA256 (R9 i5.2), or the expected SHA256 of a download (new expected SHA -> new download). Expected SHA (user or pin)
   compared with the local zip at every configure (R10 j5.1). "official release" only with the pinned checksum.
8. Target arch for release zips: Windows: CMAKE_GENERATOR_PLATFORM, else CMAKE_CXX_COMPILER_ARCHITECTURE_ID, else
   CMAKE_SYSTEM_PROCESSOR (R9 i5.3, R10 j5.3); macOS: a single CMAKE_OSX_ARCHITECTURES, else processor; Intel Mac zip
   only for versions < 6.8.
9. Library copied by a custom target `raven_mf6_lib` (ALL) to `$<TARGET_FILE_DIR:Raven>` (= MF6_DEST) under
   RAVEN_MF6_LIBNAME, plus `libmf6_version.txt` (also staged in `mf6/` for install). Install: components `Raven` and
   `mf6` (lets cmake_checks install the library without compiling Raven); `install(PROGRAMS ... RENAME)`.
10. Bundling reads the dependencies from the build-tree library (ldd / otool / objdump) and installs them with
    `file(INSTALL DESTINATION ${CMAKE_INSTALL_PREFIX}/bin)`, which applies DESTDIR exactly as for Raven's own files
    (absolute and relative DESTDIR both checked); unresolvable dependencies are warned about. macOS and Windows branches
    are written but unverified (no runners here).
11. Version guard inside CMF6Engine::Load (CheckVersion), so no change to GroundwaterModel.cpp/GWExternal.cpp callers:
    strtol-based parse (accepts leading blanks/sign; "-1.0" refused, "abc"/"v6.8.1" unreadable -> warning quoting it),
    numeric per-part compare with missing parts 0; older than 6.5.0 -> ExitGracefully(BAD_DATA) with remedy; other
    versions / no version -> one WriteWarning (static once-per-process flag). Raven_errors.txt unchanged for 6.8.1.
12. Package name `Raven-<RavenInclude.h version>-mf6-<ver>-<linux|macos|windows>-<arch>`; no `-mf6-` part when unknown
    (PATH; SOURCE_URL whose name gives no version until built).

## Evidence (28 Oct 2026, this machine, 2 cores)
- tests/cmake_checks.py: 42 parts in 14 checks ALL PASSED in ~14 s; `--selftest`: each of the 14 checks fails on its
  mutation (the bug of R8 h5.1-h5.8, R9 i5.1-i5.5, R10 j5.1-j5.3 put back).
- OFF identity: scratch script offcmp.sh (base f12baab vs worktree, -DRAVEN_MF6=OFF), see decision 3.
- Full SOURCE build (default mode, git clone of tag 6.8.1 from GitHub, gfortran 13.3, meson 1.12.1): libmf6 ~70 s,
  Raven ~70 s (-j2); install: Raven, libmf6.so, libmf6_version.txt, libgfortran.so.5; cpack
  Raven-4.15-mf6-6.8.1-linux-x86_64.tar.gz 5.0 MB; extracted elsewhere it ran the Liard example (365 d) with no setting
  (GWModelSummary names the bin folder's library, version 6.8.1). Same Raven with the official library: heads in
  solution.rvc differ by <= 8.9e-11 m; Hydrographs.csv, WatershedStorage.csv, GWHRUState.csv identical.
- SOURCE from RAVEN_MF6_SOURCE_URL=file://.../mf6.8.1_linux.zip (pinned, offline): builds in 60 s.
- mf6version_check.py: 20/20 on the new build; 15 FAIL on the base build (no guard).
- mf6lib_check.py --unit: 8/8; the Windows ARM64 parts fail with the ARM branch removed from get_mf6.py.
- actionlint: raven-mf6.yml clean (testing.yml has one pre-existing finding, `matrix.conda`). Workflow never run.
