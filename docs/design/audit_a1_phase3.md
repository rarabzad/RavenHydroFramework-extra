# Audit A1, phase 3: documentation and package (agent p3)

Issue list: spec/audit_final/AUDIT_A1_issues_and_phases.md; findings F_CB, F_IB, F_MT. Built on phases 1-2 (rb-p2,
audit_a1_phase1.md, audit_a1_phase2.md). Code unchanged in this phase (rb-p3 = a2133bf, the phase-2 code). Build used
for the measurements: Raven_p2.exe (make -O2) and, for the package, a CMake Release build of the same commit.

## Manual (docs/manual, rebuilt with latexmk: 0 errors, no undefined references or citations, one 1.2 pt overfull box)
- CB2: ch1 (design goal and "What changes for an existing Raven model"), appendix options table, ch8 approaches table and
  Section 9.1: models without groundwater are identical to Raven 4.15 except models with reservoirs (crest start, drying,
  12-digit .rvc), ensembles and age-tracer hotstarts (phase 2); the age-tracer change described in 9.1 and ch9 (a fifth
  core change, files AgeTracers, Advection, StandardOutput, ParseInitialConditionFile).
- IB6 / MT7: capillary-rise default "ON with an unsaturated column (RICHARDS, KINEMATIC or LAG), OFF with NONE" in
  ch4_exchanges (text and reference card), appendix, ch6 and the user guide; KINEMATIC/LAG get their rise from the water
  table. Appendix row of :SoilZoneVadose with KINEMATIC {eps} {N} and LAG {t_m} {N}. ch6 (Inputs and outputs) has a new
  subsection "Soil-zone commands" (Table 7.5): every :SoilZone* command with syntax, default, range and meaning, plus the
  soil-class requirements; :GWVadoseClassColumns in the solution.rvc row; aquifer attributes CLAPP_B and
  AIR_ENTRY_PRESSURE; POROSITY = theta_s of the columns (was "reserved for transport", also in the appendix parameter
  index, which now lists the soil-zone commands and soil-class parameters).
- MT8: reference card: the rejecting fraction is recomputed on every interface update from MODFLOW's head; only the share
  an unsaturated column carries uses F_0, handed back as F rises. The old "3.3 m above the base for one day" sentence is gone.
- MT12, re-measured with Raven_p2.exe (test_v2.py, log logs/test_v2.log outside git): V2b evaporation 180 / 114 / 50 mm
  (was 117, 51); V2c falls 1.11 m below the base (was 0.62); V2f 10 classes = 10 HRUs to 6.5e-7 m (ch4 had 8e-6, ch8
  7e-7); V2i 1,765 / 1,732 / 1,732 m3 (was 1,733), 111 outer iterations (112); V2d restart 6e-15 (3e-9); V2e restart
  7e-9 m; V2h 5e-8 (3e-8). Appendix: :GWHeads 12 digits, 17 with :SoilZone PHYSICAL; :GWVadoseColumns for every method;
  GWBudget table complete (negative recharge not held, unsaturated zone x4, capillary rise from the water table, lagged
  debt/repayment, specified heads x2, recharge not applied); notation N for every method; depth classes are now a
  subsection (5.3.12), not a subsubsection of LAG.
- MT9: new ch8_sz_v1.tex: Section 9.8 "Soil zone v1" (unit, spike, T1, T1b, T2, T3, T4, T5, SG, restart incl. R2, T6
  "planned, not implemented" with what covers it, T7), input table I1-I14, robustness table R1-R13 + R15b; Section 9.9
  "Audit A1: regression tests" (B8, R15b, I5, I6, C10, I9-I14, T3, C9, run_all, test_v2, sz_check, cmake 15-19) and the
  cmake 15-19 table. Numbers from the phase-2 full-suite logs (Raven_p2.exe, full mode; wt/p2/work_full/run_all_logs).
  ch4 cross-references to T1 and T2/T3 point there; ch9 says 19 cmake checks.
- Found while reading (manual vs code, not an audit item): ch4 sec:szexisting said an existing model without NEWTON gets a
  warning; the code stops at start-up (GWExternal.cpp:490, test X6). Text corrected.
- Sloping terrain and the water table in the soil (user request): ch5 already shows them with Figures 5.3 (one cell with
  irregular land, four states), 5.4 (hillslope run), 5.5 (every position of the water table), the depth-class figure and
  the rough-terrain section 9.12. Added: ch1 overview paragraph, and Section 8.5 "A water table in the soil, on sloping and
  irregular land" (setup steps, what is resolved within and between cells, which figure shows what, how it was verified).
- MT14: main.pdf rebuilt and committed (also the duplicate "page.i" destination fixed: title page numbered Alph).
- Visual check: pages 43 (Figure 5.3), 82 (Table 7.5), 94 (Section 8.5), 113 (Table 9.13), 143 (Table A.6) rendered
  with pdftoppm and inspected; overfull boxes of the new tables fixed by column widths.

## User guide (docs/Raven_MF6_Groundwater_UserGuide.md, MT6)
Section 4.3c rewritten from the manual: PHYSICAL with existing models (NEWTON required), LAGGED default (AFTER = v1),
warning below 0.1 m, every :SoilZone* command in a table, sloping land, the per-update rejection, unsaturated columns,
outputs. Also: CMake defaults (offline fallback, Release, version floor), aquifer attributes, hotstart blocks, outputs,
troubleshooting (MODFLOW's own errors, unconverged steps withholding only the negative residual, orphan series, options
for existing models only, NEWTON, ignored options).

## Tests and design notes (MT13)
- Docstrings: test_interface_stiff (PARTIAL header removed: the file is complete), test_vz_initial I1 (KINEMATIC/LAG
  implemented; what is and is not enforced), test_confined_wet W4 (permanent skip; the suite runs in run_all), test_mf6_budget
  B3 (checked in test_confined_wet), test_inputs I2 (count 0) and I5 (only the warning is checked). No test logic changed.
- docs/design/soil_zone_v3_f2.md, _f3.md, _q1.md written from the code, manual, tests and the spec (marked as
  reconstructions; section numbers match the references in the tests).
- tests/README.md: soil-zone section (every script and run_all step), cmake checks 15-19, check 2 text, the soil-zone tests
  do not start from the Liard examples.

## README files
- extra README.md: KINEMATIC/LAG, depth classes, sloping land; chapter numbers (Building is chapter 10).
- Package README (from pkg/Raven_MF6_linux/README.md): test command with RAVEN_SRC (phase 2), status from the phase-2 full
  suite and this package's quick run, build defaults corrected, known issues updated (the "empty .rvt crashes" claim
  dropped: not reproducible; :StartTime fixed in phase 1), platforms tested (Linux) vs reasoned (macOS, Windows).

## Package (wt/p3/pkg/Raven_MF6_linux, zip wt/p3/Raven_MF6_package_phase3.zip)
- cmake -S code -B bld_pkg -DRAVEN_MF6_PATH=/home/claude/rebuild/code/lib/mf6/libmf6.so -DCMAKE_INSTALL_PREFIX=...;
  cmake --build; cmake --install (Release by default). Manual, examples (no __pycache__), source archives (git archive of
  rb-p3 / rb-p3-docs with prefixes raven-soil-zone/, raven-mf6-extra/) and bundles.
- cmake/RavenMF6InstallCheck.py on the installed bin: PASS (library beside Raven used, version 6.8.1).
- Smoke: Liard_groundwater 30 days and Liard_existing_model 31 days, RAVEN_MF6_LIB unset: Successful; tools_audit recharge
  identity 0, residual 1.0e-11 / -2.3e-11, 0 unconverged; existing model DIS 4 x 11466, RCH_MODEL EVT_MODEL taken over,
  coverage 99.74 %.
- The package's own test command (README, quick mode, unpacked archives): see "Quick run" below.

## Quick run
The README command, run on the unpacked package archives (RAVEN_SRC=<dir>/raven-soil-zone, RAVEN_EXE and RAVEN_MF6_LIB
of the package, extra at b4f2b7a, which differs from the final commit only by this note): 45 steps passed, 0 failed, 2 not run (usgs_sagehen, usgs_capture: no MODFLOW examples on the machine), 10 checks skipped (W4, W6, W11 permanent; 7 byte-identity checks without RAVEN_EXE_REF: M3, K8, B, C1 x4), about 29 minutes on 2 cores; rough terrain 180 + 180 runs, 0 failed; T7 PASS. Log: wt/p3/pkgtest/quick.log.
