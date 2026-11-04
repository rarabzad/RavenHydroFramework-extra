# Audit A2, phase 5: tests, build and inputs (agent p5)

Issue list: spec/audit_A2/AUDIT_A2_issues_and_phases.md; findings F_MT (MT-1, MT-3), F_CB (CB5, CB6), F_IB (IB2, IB3,
IB5, IB6). Code on rb-p5 (from 18c8bb6), tests and documents on rb-p5-tests (from 96a3756); changes left uncommitted,
diffs in wt/p5/patches/. Builds compared: Raven_p4.exe ("before", the phase-4 build) and Raven_p5.exe ("after"), both
`make -O2` (tools/build_raven.sh), MODFLOW 6.8.1; base Raven for byte identity: audit/CB/Raven_base.exe. CMake checks
"before" use the rb-p4 source (wt/p4/code, same commit as the rb-p5 base).

## MT-1 (S2) column identity of test_vz_lag.py and test_vz_kinematic.py
- Both scripts replaced sz_check's column identity with their own storage-scaled form that skipped step 1. Deleted
  (test_vz_lag `vz_identity` and its overwrite in `check`; test_vz_kinematic `vz_identity` and its overwrites in `run`
  and K6). Every run of both scripts now takes `sz_check.checks` as it is, and requires that the identity starts at
  step 1: a new item `vz_step1_missing` (limit 0) fails a run whose GWModelSummary.txt gives no start storage.
- `test_vz_kinematic.check(d, name, dt)` (factored out of `run`) is the one judgement of the script.
- New tests: `sz_check.leak_copy(d, dst, leak, smin=5000)` copies a run and writes a column leak into GWBudget.csv
  (leak m3 lost on every step whose storage exceeds smin, the storage of that and every later step lower by the leaks
  so far, 10 significant digits as Raven writes it). L7 (test_vz_lag: the L1 storm, LAG 2) and K9 (test_vz_kinematic:
  the V2a storm) pass on the run and must fail on the leaked copies (1e-5 and 1e-4 m3 per step).
- Before/after on the same leaked outputs (auditor's mutation):

  | leak per step | LAG 2 (10 leaking steps): old form / now | KINEMATIC (88 steps): old form / now |
  |---|---|---|
  | 1e-5 m3 | 8.6e-10 passes / 3.7e-7 fails | 1.5e-9 passes / 9.0e-6 fails |
  | 5e-5 m3 | 4.2e-9 passes / 2.1e-6 fails | 6.3e-9 passes / 4.9e-5 fails |
  | 1e-4 m3 | 8.5e-9 passes / 4.2e-6 fails | 1.25e-8 fails / 9.9e-5 fails |

  The unaltered runs give 0 with sz_check's form (no limit loosened).

## MT-3 (S3) quick mode in every soil-zone script
Each script now reads RAVEN_TEST_QUICK and documents its quick mode in its header; full mode is unchanged.
| script | quick mode | quick run time |
|---|---|---|
| test_liard_physical.py (T7) | 30 days (October 1985) unless days are given; run_all passes 365 only in full mode | 13 s (365 d: ~60 s) |
| test_dynamics.py | T4 with 1 d and 6 h only (error shrinks 1 d -> 6 h, outflow within 1e-3); hourly limits in full mode | 28 s |
| test_restart.py | hillslope 120 d against 60 + 60 (R2-R4 unchanged) | 5 s |
| test_v2.py | V2d 30 + 30 against 60 | 33 s (machine shared) |
| test_v2_ext.py | round trips X1-X4 (and X5-X7 using them) over the first 120 days of the rain | 6 s |
| test_column.py | T1/T1b 45 days instead of 70 (full on day 41) | 1 s |
| test_columns_mf6.py | M2 75 days instead of 120 (same last-30-day check) | 1 s |
| spike_xmi.py | the same single-step 3 x 3 case (already the smallest); prints the mode | 2 s |
| test_hillslope.py | the same 300-day case (the drying checks need the whole wet and dry season; ~10 s); prints the mode | 9 s |
All quick variants were run and pass. tests/README.md, run_all.py's header and the manual (ch8 "Repeating the coupled
tests") describe the quick mode as shorter cases, with examples, and name the two scripts that run the same case.

## CB5 (S3) Raven :Transport in coupled runs: stop
- Choice: stop. F_CB shows no legitimate use: the coupling exchanges no constituent mass, so the mass of the water sent
  to MODFLOW stays in GROUNDWATER and keeps growing, and seepage/discharge return water without mass (age = time since
  the datum). The age-tracer hotstart work (I14-I16) is Raven-core behaviour in runs without groundwater; no test,
  example or document uses :Transport with :GroundwaterModel MODFLOW6.
- ParseInput.cpp, after ParseGWFile (coupled runs only): any constituent -> ExitGracefully BAD_DATA ":Transport <name>
  cannot be used with :GroundwaterModel MODFLOW6: the coupling exchanges water only, no constituent mass (...). Remove
  the :Transport commands from the .rvi file, or run the model without :GroundwaterModel MODFLOW6." Runs without
  groundwater take exactly the old path.
- Test: test_inputs.py I19 (Nitrate CONCEPTUAL and PHYSICAL, AGE CONCEPTUAL: stop with the message; Nitrate without
  groundwater: runs). Before: all four run -> FAIL. After: three stop with the message, the fourth runs -> ok.
- Documents: ch6_reference .rvi table (`:Transport` row), ch1 scope list, ch5 (the age-tracer restart paragraph moved
  out of the coupled-restart list: it concerns runs without groundwater), user guide section 9, ch8 table (I19),
  tests/README.

## CB6 (S4) stale comment
The ParseInitialConditionFile.cpp comment went with phase 4's rewrite (checked: no "shifts the entry times" left). The
CMakeLists.txt comment on the default (IB6, first point) now names the repository condition and the download.

## IB2 (S3) Linux PATH mode: $ORIGIN for the installed libmf6
- RavenMF6Bundle.cmake: when any runtime library is copied (Linux/FreeBSD), the installed libmf6's run path is read
  (patchelf --print-rpath, else readelf -d). With $ORIGIN: a status line. Without, and patchelf found: `patchelf
  --set-rpath '$ORIGIN[:old]'` and a status line. Without patchelf: a warning that the library loads the system's
  runtime (named) instead of the copies beside it, how to fix it (install patchelf and install again, or link libmf6
  with -Wl,-rpath,'$ORIGIN'). patchelf is RAVEN_MF6_PATCHELF (found on the PATH when not given; the tests pass
  NOTFOUND to emulate its absence). The existing patchelf step for the copied runtime libraries uses the same variable.
- Test: cmake_checks.py check 20 (gfortran-built libmf6 with no run path; the bundle run with `cmake -P` as at install):
  with patchelf the installed copy has $ORIGIN and ldd resolves libgfortran.so.5 to the install folder; without patchelf
  the warning; a libmf6 built with $ORIGIN: status line, no warning. Before: all three FAIL (runpath '', libgfortran
  from /lib/x86_64-linux-gnu). After: ok. Self-test mutation 20 fails the check.
- patchelf is not installed on this machine; the tests used patchelf 0.19.3 from PyPI (`pip install --target
  wt/p5/pyloc patchelf`, on the PATH for the runs). Without it check 20's first part is a SKIP.

## IB3 (S3) package code history bundle
- Cause: /home/claude/rebuild/code (and every worktree) is a shallow clone (graft at 5db5cba v577b); a bundle made from
  it cannot be cloned. Verified before: `git bundle create` from wt/p5/code, then the README command `git clone
  source/raven_code_history.bundle raven-code -b rb-p5` -> "fatal: Failed to traverse parents of commit 5db5cba".
- No packaging script existed in the repositories (the packages were assembled by hand). New: extra
  tools/package_sources.py `<package> <code repo> <code branch> <extra repo> <extra branch>`: writes the source archives
  and both history bundles into <package>/source; a shallow repository is first completed in a temporary bare
  repository from the upstream Raven history (RAVEN_UPSTREAM, default https://github.com/rchlumsk/RavenHydroFramework
  main, which holds 5db5cba and its whole history), stopping if the upstream does not reach the shallow boundary; then
  it writes source/RESTORE_HISTORY.md (the package README's "Restore the git history" section, branch names filled in)
  and runs those commands as written in an empty folder holding only a copy of source/: each clone must be complete
  (not shallow), at the branch tip, with the full commit count, and `git fsck --full` clean.
- After (rb-p5 / rb-p5-tests): code bundle 20 MB, clone 846 commits back to a00017d "Creating standard CHyMS repository
  layout", not shallow, fsck clean; extra 97 commits; restore check PASS (19 s). Also followed by hand in the package
  folder: the README command clones 846 commits.
- The package README (built in phase 6) takes its restore section from source/RESTORE_HISTORY.md.

## IB5 (S3) cmake --install with RAVEN_MF6 OFF
- CMakeLists.txt: `install(TARGETS Raven ...)` is outside the MODFLOW block, so every mode installs bin/Raven; with OFF
  (explicit, or a default that falls back) the configure says "cmake --install installs Raven alone (bin/Raven, no
  MODFLOW 6 library)" and the install prints "RAVEN_MF6 was OFF: Raven installed without the MODFLOW 6 library (a
  coupled model needs one at run time ...)". OFF's compile and link commands are unchanged (flags.make and link.txt of
  an OFF configure identical to rb-p4's). RAVEN_MF6.cmake's header comment no longer claims "no install rules".
- Docs and examples are not part of the CMake install in any mode (they live in the extra repository and the package):
  nothing to add there.
- Test: cmake_checks.py check 21 (explicit OFF; default fallback on emulated aarch64 without meson; a stand-in ELF at
  the build tree's Raven path, as the checks never compile Raven): the configure message, and `cmake --install --prefix`
  gives exactly bin/Raven with the install message. Before: no message, nothing installed -> FAIL. After: ok.

## IB6 (S4) offline fallback warning
- `_rmf6_giveup` (the OFF fallback warning) asked to install a Fortran compiler, meson, ninja and git even when the
  default had found them and only the network failed. `_rmf6_tools_found` records the tool check before the git probe;
  with the tools found the warning says "The source tools (Fortran compiler, meson, ninja, git) are installed: with
  network access, configure again; offline, give a MODFLOW 6 source folder (-DRAVEN_MF6_SOURCE_DIR=...) or release zip
  (-DRAVEN_MF6_ZIP=...)"; without them, the request to install them as before.
- Test: cmake_checks.py check 22 (tools present, repository and release unreachable: no "install a Fortran compiler",
  the network text; aarch64 without meson: the install request). Before: the first part FAIL. After: ok.
- Whole cmake_checks: 69 parts in 22 checks, all pass; --selftest 20-22: each fails on its mutation.

## Results
- Full suite (`run_all.py`, full mode, RAVEN_TEST_QUICK=0, Raven_p5.exe, RAVEN_EXE_REF = Raven_p4.exe, the MODFLOW 6
  examples zip for the USGS steps, patchelf on the PATH): 47 steps, 47 passed, 0 failed, 0 not run; 3 checks skipped
  (the permanent W4, W6, W11 of soilzone_confined_wet). The run hit the 2-hour limit of the background job during
  soilzone_rough_terrain_k3 after 44 passing steps; the three remaining steps (rough_terrain_k3, v2_ext, liard) were run
  again with `--only` and pass. Highlights: cmake 69 parts in 22 checks; usgs_sagehen and usgs_capture pass (1013 s, 12 s);
  rough terrain 1620 runs, 0 failed, and 1620 with three classes, 0 failed; T7 365 days PASS; soilzone_inputs incl. I19,
  vz_lag incl. L7, vz_kinematic incl. K9 and K8 (byte identity against the phase-4 build) pass. Logs:
  wt/p5/logs/full_suite.log, full_suite_rest.log.
- Byte identity (wt/p5/scratch/byteid.py, the phase-4 script with its text filter extended to the build date and the
  linkage timing line): without groundwater, Raven_p5 against base Raven: small model cold start + two chained hotstarts
  without tracer and with Nitrate, age-tracer cold start, Liard without :GroundwaterModel 5 years and a 1-year hotstart:
  all identical. Coupled, against the phase-4 build: Liard CONCEPTUAL 180 d, Liard existing model 31 d, PHYSICAL +
  RICHARDS 4 HRUs, CONCEPTUAL with 10 unconverged steps: all identical. 0 of 13 comparisons differ.
- The only change of behaviour in Raven itself: a coupled run with :Transport stops (CB5).
