# Audit A1, phase 2: tests, build system, input messages, age-tracer hotstart (agent p2)

Issue list: spec/audit_final/AUDIT_A1_issues_and_phases.md; findings F_MT, F_IB, F_VZ. Built on phase 1 (rb-p1,
docs/design/audit_a1_phase1.md). Builds compared: Raven_p1.exe (phase 1) and Raven_p2.exe (this phase), both
`make -O2` from src (tools/build_raven.sh), MODFLOW 6.8.1.

## A. Tests

### MT1 test_hillslope T3: a test-expectation error, not a model defect
- Evidence (closed 20 m aquifer, rain 10 mm/d for 150 d then none): the MODFLOW-only reference (soil as a MODFLOW layer,
  a drain at the land surface) still discharges 173.6 m3/d on day 300 (6,146 m3 over the last 30 days); the coupled run
  gives 173.5 m3/d. The water table at the toe (HRU 10) stays above its land (95.34 m against 95.25 m), so the water
  draining from upslope seeps out there in a recession (814 m3/d on day 161 to 174 on day 300). "Overflow stops after
  rain" is false for this model and for the reference alike; the model is right.
- What does stop: the overflow of the upslope HRUs (3-7) on day 150, with the rain; HRUs 2-7, which connected during the
  rain, end with F = 0; HRUs 8-10 (reference head above their soil-zone base) stay saturated.
- New T3 checks (t3_checks): HRUs that connected and whose reference head ends below their base end with F < 1e-6 (at
  least five: HRUs 2-7); HRUs whose reference head ends above it with F > 0.999; on day 300 no overflow where the water
  table is below the land and overflow where it is above; the upslope overflow stops by day 151; the outflow does not
  rise after day 160; saturated HRUs fall from >= 8 (9) to <= 4 (3). The old check (F[-1,0], HRU 1, which never
  connects) is gone; tconn < 10^6 is required for every HRU checked.
- `--selftest` (run_all passes it): an upslope HRU left saturated, upslope overflow on day 300, a rising recession and
  no connected HRU each make the checks fail. Docstring and ch4_exchanges (hillslope paragraph) corrected.

### MT2 C9
- C9 now runs `test_rough_terrain.py --case rough_cases/band_e43.json:LAG --vzclasses 3` (R20, preceded by its NONE run)
  and requires the R20 line PASS, F_err <= 0.004 (gets 0.0001), 0 failed runs and `:SoilZoneVadoseClasses 3` in the
  run's .rvg. run_all runs it in soilzone_vz_classes, and the full mode also runs the whole rough-terrain suite with
  three classes (soilzone_rough_terrain_k3, R20 included). ch4_vz_classes and ch8_rough_terrain corrected.

### MT3 run_all modes
- run_all sets RAVEN_TEST_QUICK=1 (quick) or 0 (full) in tc.ENV for every step; the rough-terrain step gets --quick only
  in quick mode. Full mode: rough terrain 400 seeds x 4 methods (+ regression cases, the manual's 1,620 runs) and the
  same with --vzclasses 3. Verified: `env -u RAVEN_TEST_QUICK run_all.py --quick --only soilzone_interface_stiff` now
  makes only s1_lagged_none / s1_lagged_richards (the full-mode folders before). ch8_verification corrected.

### MT4 SKIP lines
- Each step counts lines starting "SKIP "; status "PASS (k skipped)" / "FAIL (k skipped)", the report lists them, the
  console ends with the total. Verified on soilzone_confined_wet: "PASS (3 skipped)" (W4, W6, W11).

### MT5 package test command
- The package README is outside git; the corrected text is in README.md (Tests) and tests/README.md (Setting up):

      cd <dir>/raven-mf6-extra/tests
      RAVEN_SRC=<dir>/raven-soil-zone RAVEN_EXE=<pkg>/bin/Raven RAVEN_MF6_LIB=<pkg>/bin/libmf6.so python3 run_all.py --quick

  (<dir>: the folder where raven_code_src.tar.gz and raven_extra_docs_tests.tar.gz were unpacked.) Verified with the
  shipped tarballs and binary: gridtest, soilzone_unit, soilzone_column PASS (soilzone_unit failed without RAVEN_SRC).
  The package README's "SOURCE (default; ...)" should read "default: SOURCE when the source tools are found and the
  MODFLOW repository answers, else PREBUILT, else OFF" (Phase 3 rebuilds the package).

### MT10 test_v2 limits
- LIM = sz_check.ID_LIMITS (recharge 5e-9, soil zone and columns 1e-8, neg_unheld) + iface_not_conv 0 + mf6_not_conv 0
  for every V2 run. No case needed a looser limit: worst rch_identity 3.75e-10, vz_identity 4.0e-10, 0 unconverged steps.
- V2a against the manual's numbers: centroid 6.06 +- 0.5 d without the column, 15.62 +- 1 d with it, peak ratio
  0.45-0.65 (gets 0.55), column balance 1e-8 (was 1e-6; gets 7.8e-12).

### MT11 V2c
- `reformed` no longer ends in `or fell`: the column must hold water at the end or take inflow in the last 30 days
  (storage -46 m3 at the end: it re-forms).

### VZ4 sz_check.vz_identity: the code was wrong, the docstring right
- The scale added both storages in full (2e4 m3 on a 1e4 m3 store: 2e-4 m3 per step passed). The CSV rounding the
  comment wanted to allow is half a unit in the 10th significant digit of each value (5e-6 m3 for 12799.99999, 5e-7 for
  9776.xxx). Now: (|residual| - rounding of the five values) / max(1 m3, flows), as the docstring says (rounding stated).
- `python3 soilzone/sz_check.py` (run_all step soilzone_check_selftest): synthetic 9,776 m3 store, 220 m3/step, written
  with 10 digits: exact books 0; a 1e-4 m3/step leak 2.4e-7 (fails; the old form gave 5e-9 and passed).
- 105 existing runs re-checked (vz tests, test_v2): all <= 4e-10 except i4_up of test_vz_initial, whose start value is
  moved on purpose (9e-4, must fail). Quick tiers of test_vz_kinematic, _lag, _classes, _initial, test_v2,
  test_columns_mf6 pass.

## B. CMake (code repo cmake/, CMakeLists.txt, .github/workflows/raven-mf6.yml)

### IB1 offline default
- Default SOURCE now also needs the git repository to answer at configure time: `git ls-remote --exit-code <url>
  refs/tags/<version>` (GIT_TERMINAL_PROMPT=0, 60 s), skipped when an earlier configure's clone is already at the pinned
  commit. Otherwise a warning and the fallback PREBUILT (its download is at configure time, falling back to OFF when it
  fails) or OFF. Explicit SOURCE is unchanged (clones at build time, stops there). Header of RavenMF6.cmake and ch9 say so.
- Tested (cmake_checks 15): tools + unreachable repo + no release -> OFF with the warning, no library target; unreachable
  repo + reachable local release (file://, 6.7.0) -> PREBUILT, and `cmake --build --target raven_mf6_lib` succeeds with
  no network; reachable local stand-in repository -> SOURCE. Check 2 now gives a reachable stand-in repository (it
  expected SOURCE from an unreachable URL, i.e. the IB1 behaviour). Not tested: the timeout path (reasoned: TIMEOUT 60
  gives a non-numeric result, treated as unreachable).

### IB2 default build type
- CMakeLists.txt: if the generator is single-config and CMAKE_BUILD_TYPE is empty, cache Release. Tested (check 16):
  Unix Makefiles -> Release, flags.make has -O3 -DNDEBUG; -DCMAKE_BUILD_TYPE=Debug kept. (Raven has no assert() that
  NDEBUG would remove.) The makefile build (tools/build_raven.sh) is unaffected.

### IB7 runtime bundling and the install check
- macOS: recursive scan from libmf6 (otool -L of every copied library; its own install name skipped), libgcc_s added,
  @rpath resolved against the referencing binary's LC_RPATH entries and libmf6's, @loader_path against its folder; every
  reference in libmf6 and in the copied libraries rewritten to @loader_path/<name>, ids set, then `codesign -f -s -` on
  every edited file (warning without codesign). Linux: when more than one runtime library is copied, patchelf (if
  present) gives each RUNPATH $ORIGIN, else a warning. cmake_policy(VERSION 3.20) in the bundle file (cmake_install.cmake
  sets no policies; IN_LIST needs CMP0057).
- Tested on Linux by emulation (check 18): Mach-O stand-ins linked with ld64.lld (libmf6 -> @rpath/libgfortran.5 ->
  @rpath/libquadmath.0 and @rpath/libgcc_s.1.1, LC_RPATH to a "gcc" folder), llvm-otool / llvm-install-name-tool as the
  tools, a stand-in codesign: all three installed, every reference @loader_path, all four files signed. Not tested on a
  Mac: real otool output (same format as llvm-otool), codesign itself, dyld loading.
- Install check through Raven: cmake/RavenMF6InstallCheck.py <bin> [version] writes a one-HRU coupled model, runs the
  installed Raven with RAVEN_MF6_LIB unset and checks: Successful, two GWBudget steps, GWModelSummary names <bin>/libmf6.*
  and the version, and every Fortran runtime library loaded lies in <bin> (Linux: ldd of libmf6; macOS:
  DYLD_PRINT_LIBRARIES; Windows: PATH folders holding libgfortran-*.dll hidden). The CI step "Moved install runs" calls
  it instead of the ctypes snippet. Tested on Linux: source-built libmf6 (IB auditor's build) with libgfortran.so.5 beside
  it PASS; the same without the bundled copy FAIL ("libgfortran.so.5 => /lib/x86_64-linux-gnu/..."); official library
  PASS. macOS and Windows parts reasoned.

### IB8 Windows DLL search
- MF6Engine::Load: a path with a folder is made absolute (GetFullPathNameA) and loaded with LoadLibraryExA(...,
  LOAD_WITH_ALTERED_SEARCH_PATH), so the DLLs beside libmf6.dll are found first; a bare name keeps LoadLibraryA. The
  error names the Windows error code. Syntax-checked on Linux with -D_WIN32 and a stub windows.h (it caught a
  GetLastError clash with CMF6Engine::GetLastError: now ::GetLastError). Not run on Windows.
- Bundle: imports read recursively (libgfortran-5.dll's own imports), with `dumpbin /dependents` when there is no objdump;
  without either, the usual gfortran DLLs with a warning. Tested with stand-in objdump and dumpbin (check 18).

### IB9 version floor
- RAVEN_MF6_MIN_VERSION is read from MF6_MIN_VERSION in src/MF6Engine.h (one place). FATAL_ERROR for a known version
  below it: RAVEN_MF6_VERSION before any download or clone (SOURCE from git, PREBUILT download; also a non-numeric value),
  the zip's meson.build, a source folder's meson.build, a source archive's name; a warning for a version other than 6.8.1.
  PATH: run-time guard only. Tested (check 17): 6.4.0 stops in all five ways, 6.7.0 warns.

### IB10 messages
- _rmf6_giveup joins its pieces with string(APPEND) of ARGV0..3 (CONCAT ${ARGV} split at every ';'); a SHA256 must have
  64 hex digits. Tested (check 19). Parser: a short attribute-table row names ":Wells" (not ":EndWells"); a missing .rvg
  stops with "Cannot find or read .rvg file <name>" in Raven_errors.txt (test_inputs I13).
- cmake_checks: 15-19 fail on the phase-1 source (16 of 18 parts; the Windows dumpbin part could not run there) and pass
  here; --selftest shows each fails on its mutation.

## C. Input messages (code: GroundwaterModel.cpp/.h, ParseGWFile.cpp)
- IB4: ValidateInputs stops (BAD_DATA) for a :WellFlowRate ID that no well has and a :BoundaryHead name that no boundary
  has, listing the IDs / names there are (also for existing models, which have no Raven wells or boundaries).
- IB5: :MF6Model, :MF6StartDate, :KeepPackages, :SeepageToRaven on a model Raven builds stop ("apply only to an existing
  model", as :MF6CRS etc. already did); :SoilZoneVadoseClasses and :SoilZoneVadoseInitialFlux with :SoilZoneVadose NONE,
  and :SoilZoneAquiferClass on a generated model, give an "ignored" warning once after the .rvg is read; an unknown
  :AquiferProfileParameters attribute stops (as for :AquiferClasses); LAYERS other than ALL or TOP stops.
- Tests: test_inputs I11 (orphan series stop with the message; the right names run), I12, I13; all fail on phase 1.

## D. Age-tracer hotstart (Raven core; user-approved)
- As asked first: SetInitialTimeOffset is now called before UpdateInitialConditions. With that alone the shift reaches
  the HRU masses (mass = V x entry time, shifted by -V x offset) and the first reported ages are right, but the entry times
  before the new start are negative and so are the masses: CmvAdvection's emptying limit `|rate| > mass/dt` (written for
  mass >= 0) then empties the whole store each step, and CmvLatAdvection stops on a negative mass. Test model (2-layer
  soil, 20 d, restart after 10): after one step soil ages 1.0 d instead of 9.1, deep groundwater 1,014 d instead of 10.5;
  the channel and reservoir masses were not shifted at all.
- Implemented instead ("otherwise make the offset reach"): the masses keep the datum of the run that wrote the file; the
  offset shifts the age clock. CAgeTracer: UpdateInitialConditions no longer shifts masses; SetInitialTimeOffset sets
  _t_diff and moves _model_time by it; SetModelTime(t) = t + _t_diff; GetTimeOffset(). CmvAdvection: precipitation enters
  at tt.model_time + dt/2 + offset. StandardOutput: solution.rvc's :StartTime is the datum (run start - offset) when the
  model has an age tracer, so a chain of hotstarts keeps one datum (third run offset 14 d, not 7). Without an age tracer,
  or on a cold start (offset 0; x + 0.0 is exact), every value and file is unchanged.
- Test: test_inputs I14: 20 d continuous against 7 + 7 + 6 d chained: every store's age and the outflow age equal the
  continuous run's (largest 1e-4 d, the .rvc's 6 digits); each solution.rvc has :StartTime 2000-01-01. Phase 1: 12-14 d
  too young, :StartTime 2000-01-08 / 2000-01-15.
- Liard without groundwater, :Transport AGE, 1 + 1 years: the HRU stores' ages after the restart equal the continuous
  run's (phase 1: 365 d off, many negative); the outflow ages equal it except subbasin 52 (its reservoir: 29 days, 0.1 d at
  the start and days on which the continuous run reports 0, Raven's "no outflow mass" value), and columns whose stores
  base Raven's hotstart itself does not carry (cumulative losses, glacier ice reset to 0) or whose ages are undefined in
  both runs (deep groundwater, -2e6 d). These lie in base Raven's transport hotstart, not in the offset.
- Deliberate exception to byte-identity with base Raven / phase 1: age-tracer runs started from a hotstart file
  (Ages.csv, AGEPollutographs.csv, solution.rvc's masses and :StartTime). Everything else stays byte-identical (below).

## Byte-identity against phase 1 (bi/run_bi.py, MODFLOW 6.8.1)
- Liard without groundwater, 20 years: 9 files byte-identical. CONCEPTUAL (the example), 2 years: 32 files identical
  except the dates/timings of GWModelSummary.txt, mfsim.lst, mfsim.stdout. No-GW hotstart (1 + 1 years): identical.
  Age tracer cold start (2 years): identical. Age tracer hotstart: differs (the intended change).

## Full suite
- `run_all.py` full mode (RAVEN_TEST_QUICK=0 for every step), Raven_p2.exe, MODFLOW 6.8.1, RAVEN_EXE_REF = Raven_p1.exe
  (so the byte-identity checks K8, B, C1 ran: all byte-identical): 45 steps passed, 0 failed, 2 not run (usgs_sagehen,
  usgs_capture: the MODFLOW examples zip is not on this machine), 3 checks skipped (W4, W6, W11 of test_confined_wet,
  permanent skips), 2,938 s. Rough terrain 1,620 runs, 0 failed, and 1,620 with three classes, 0 failed; T7 Liard PASS;
  cmake checks 60 parts in 19 checks.
