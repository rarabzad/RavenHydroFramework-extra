# Audit A3, phase 10: documentation and package

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Phase 10 of the round-3 audit (issue list: `spec/audit_A3/AUDIT_A3_issues_and_phases.md`) covers VZ3-3, CB3-3, MT3-4 to
MT3-8, IB3-1, IB3-8, the remaining history wording, Phase 9's hand-over (the example's commented boundary heads), the
manual PDF and the Linux package. Code unchanged (rb-p10 = d986fb0, the Phase 9 code). Changes in extra (rb-p10-tests),
left uncommitted as asked; this note added with `git add -N`.

## VZ3-3: the hand-back rules
`exchanges.tex`, Section "The unsaturated column" (sec:szvadose): a new paragraph "Water handed back to the soil zone"
defines
- rule (i) (`VZBackRate`): where MODFLOW's head rises during a step onto ground unsaturated at its start (F0 -> F(h)),
  the columns' outputs on that ground go back to the soil zone, R_q min(max(F(h) - F0, 0), 1 - F0), R_q = outputs /
  (1 - F0); F0 = 1 hands back everything; it follows the head of each interface iteration, in explicit coupling only the
  F0 = 1 case; class by class with depth classes;
- rule (ii) (`VZStep`): a vanishing column releases at most S_y dh to the aquifer, the rest to the soil zone;
- the booking: both in *rejected recharge*; subtracted from *unsaturated zone inflow* (both) and from *unsaturated zone
  to aquifer* (rule (i)) (GroundwaterModel.cpp, GWBudget writer), so the column identity holds; the water entered the
  columns in earlier steps, so on a step with little new inflow and a rising water table the inflow column can be
  negative.
Also: the GWBudget row of the appendix (inflow "less the water they hand back ... negative on steps where ..."), the
reference in `sz_interface.tex` to the new definition, and a sentence in the user guide (soil zone outputs).

## CB3-3: changes to existing Raven files (developer guide)
Checked against `git diff e7e2868 (v593) d986fb0 -- src CMakeLists.txt README.md .gitignore .github`:
- item 5 (age-tracer hotstart) rewritten: `:StartTime` stays the start of the run (as Raven 4.15), `:AgeTracerDatum`
  carries the datum when it is earlier; reading: `:AgeTracerDatum`, else `:StartTime` when the file holds age-tracer
  masses, else 0;
- table rows: StandardOutput.cpp (`:AgeTracerDatum`, outputs closed), AgeTracers (`SetDatum`/`GetDatum`/`GetTimeOffset`),
  ParseInitialConditionFile.cpp (all hotstart blocks, `GWHotValue` checks, blocks ignored without groundwater, capacity
  check skipped for the seepage target, `:AgeTracerDatum` and age-mass detection), ParseInput.cpp (`:Transport` stop,
  `:Drain`/`:Recharge` stops), Solvers.cpp and Model.cpp (column classes), ParseTimeSeriesFile.cpp (units), new rows
  ProcessGroup.h/SoilWaterMovers.h (accessors) and README.md/.gitignore/workflows; the CMake row names the `RAVEN_MF6`
  option. The table is a longtable now (it no longer fits a page as a float).
- NOTICE.md: the list of coupling source files gains `GWSoilZone*`, `GWVadose*` and `cmake/RavenMF6*`.

## MT3-4: quick mode and run times
Which scripts have a quick mode (grep of `RAVEN_TEST_QUICK`): every soil-zone script (spike_xmi, test_hillslope,
test_surface_stores and test_plot_tool run the same case in both modes), behaviour_check, budget_file, combinations,
crs_inputs, input_checks, mf6version_check, existing/ext_exchanges, ext_inputs, restart_ext (its sub-daily case). The
others run their usual cases: edge, liard_grids, mf6files_check, mf6lib_check, restart_test, lake_test, dry_start, thiem,
existing/guards, roundtrip, the USGS examples, the C++ unit tests, cmake_checks, budget_xcheck. run_all itself runs
fewer randomized set-ups in quick mode (fuzz_grids 8/72, fuzz_lakes 4/24, ext_fuzz 6/20, rough terrain 40/400 seeds,
T7 30/365 days). No quick mode was added (the long ones, edge, liard_grids and the guards, would need new expected
values). Stated in run_all.py's header, README.md, tests/README.md and the manual (Running the tests).

Run times quoted: quick about an hour (Phase 6 from the zip: 58 min; this phase from the zip: see below), full about two
hours on two cores (step times: Phase 9 1.35 h without the USGS steps; Phase 5 2.25 h with them, Sagehen 17 min).

## MT3-5: history wording
- Figure 9.6 legend "AFTER (v1), largest" -> "AFTER, largest" (`make_sz_figures.py`; the figure regenerated from a fresh
  `test_water_table.py` run with the current build, same curves; the legend moved to the upper right, off the curves).
- `exchanges.tex`: "(Using raw heads here was an error ...)" -> "(Raw heads are not used here because ...)".
- `make_tables.py`: caption = the committed table's ("Automatic checks of the behaviour-test runs"); imports the shipped
  `tools_audit.py` instead of a path of the original machine; `make_figures.py`: "(Phase 3 runs R1, R2)" removed.
- Tests: sz_check (Audit A1 VZ4 note, self-test print "the old storage-scaled form"), test_hillslope (Audit A1 MT1),
  test_mf6_budget (two "earlier" notes, now conditional), test_interface_stiff (S1 "before", "now", S3/S5/S6/S7 past
  defects, "the earlier code", the build hash 105c54b), test_robustness ("used to"), test_rough_terrain ("used to inject",
  "v2c", "repros"), cmake_checks (IB2/IB7-IB10 ids, "failed on the commit before its fix", "bug put back"), test_inputs
  (IB5), mf6files_check (OLD_RAVEN_EXE / "old build" -> OTHER_RAVEN_EXE / "other build"), spike_xmi (V1-V3 -> Q1-Q3),
  vadose_ref ("(V2)"); design-note references (`docs/design/...`) removed from test_vz_lag, test_interface_stiff,
  test_sz_existing (X5-X7), sz_models, test_vz_kinematic, test_vz_classes, spike_xmi and run_all.
- `tools_audit.py`: "#soil zone v2" comments.
- Manual: "rounds" of randomized set-ups -> "batches"; "now" in applying.tex (3), "used to" in building/applying.
- User guide and README: no pointer to `docs/design/`; `tools/package_sources.py` leaves `docs/design` out of the
  extra source archive (it stays in the repository and therefore in the history bundle).
Final grep: see "Checks".

## MT3-6: example numbers and run times
Measured with the current build (d986fb0), one run beside another single-core job on the two cores:
| | wt/p9/Raven_p9.exe | package build, from the zip |
|---|---|---|
| Example A, 20 years | 523 s, recharge 0, residual -1.04e-10, worst step 3.6e-6 %, 0 unconverged, Raven 0.516 mm | 480 s, the same figures |
| Example A, `:Duration` 365 | | 15 s, recharge 0, residual -1.47e-11, 0 unconverged |
| Example B, 2 years | 253 s, recharge 0, residual -1.94e-11, worst 4.0e-8 %, 0 unconverged, river -5.28e-12, Raven 0.515 mm | 233 s, the same figures |
Quoted everywhere as "about 10 minutes" (A) and "about 5 minutes" (B) (examples/README.md table, both example READMEs,
`applying.tex`, `intro.tex`, `existing_model.tex`, the package README); the Liard README's results now say residual about
-1e-10 and worst day 4e-6 % (NSE 0.850 / 0.821 / 0.634 unchanged, checked). `building.tex`'s tolerance paragraph says
"a run about twice as long" instead of "15 instead of 8 minutes". The shortening instruction (examples/README Step A3 and
the package README) names the line as it is in `Liard.rvi` (`:Duration           7305 00:00:00`): followed literally
from the zip, the earlier wording (`:Duration 7305`) matched no line.

## MT3-7: unique test IDs
- test_restart.py: the hillslope restart is RS1, the other cases R2-R4 -> RS2-RS4 (prints, last line, `--rs3rs4`);
  run_all self-test, tests/README, verification_soilzone (Restart row), sz_vadose_kinematic (RS4).
- Rough-terrain regression cases R1-R20 -> RT1-RT20 (test_rough_terrain REG names and docstrings, work folders
  `case_RT20_...`, test_vz_classes C9 which parses that name, test_interface_stiff, test_confined_wet, verification_rough
  incl. Table "Problems the suite found", sz_vadose_classes, sz_vadose_lag, verification_soilzone, tests/README).
- R1-R22 remain the robustness cases (test_robustness; N1-N9 = R14-R22).

## MT3-8: TS6 rows from another file
`GWExternal.cpp` `ExtShiftTimeSeries` stops a later start when a kept package's TS6 file reads its TIMESERIES rows with
OPEN/CLOSE or INTERNAL. Added to existing_model.tex (Starting later; Safeguards list; Limits), the developer guide's
limits, the appendix error table (message and remedy) and the user guide (later starts, limits, troubleshooting row).
Checked by hand on the synthetic existing model of `ext_inputs.py` (wells driven by a TS6 file whose TIMESERIES block is
`OPEN/CLOSE wel_rows.txt`): a start at the model's time zero runs (Successful); a start 10 days later stops with "the
time-series file .../wel.ts reads its rows from another file; list them in the file itself", as the manual quotes. (No
test script added: Phase 10 changes no code.)

## IB3-1 and the package script
`tools/package_sources.py` rewritten:
- revisions may be commits (a snapshot of uncommitted work); both bundles hold one branch, `--branch` (default
  `soil-zone`), whatever the local branch is called; the extra archive leaves out `docs/design`;
- writes `RESTORE_HISTORY.md` and `COMMITS.txt` from what it recorded (commit, branch, count);
- checks the package README: its "Restore the git history" section must exist; its `git clone` commands are run as
  written in an empty folder next to a copy of `source/`; together they must clone both bundles, each on branch
  `soil-zone`, at the recorded tip with the full commit count, not shallow, fsck clean; the "n commits ... to <tip>"
  statements must match; `--update-readme` writes the section first.

## IB3-8
- Version guard: the package README and the user guide say that a `PATH` library's version is checked when Raven loads
  it (an older one stops the run), the configure check applies where the version is known.
- `tools/make_prt.py --radius`: the cell width is measured along the grid's own axes (`get_local_coords` of the cell's
  vertices). Rotated Liard (`:GridRotation 30`, 2 km cells, a well): release points at 0.250 of the width from the
  centre (500 m), all inside the cell; before, 683 m (0.34). Unrotated grids are unchanged.
- examples/README.md: a paragraph for the release package (Raven in `bin/`, the manual `Raven_MF6_Manual.pdf`, the
  repository files in `source/raven_extra_docs_tests.tar.gz`); the closing "More:" line names both locations.

## Phase 9 hand-over: the example's boundary heads
`examples/Liard_groundwater/Liard.rvg`: the commented GHB1/LAKE1 lines had heads 1146.85 / 1226.5 m, below the top
layer there (1300 to 1315 m), so uncommenting them gave boundaries without cells. Now HEAD 1310.0 / 1312.0 with a comment
(heads must lie above the cells' bottoms; 3 GHB and 9 CHD cells). Checked: Liard 3 days with both uncommented: GHB / CHD
cells 3 / 9, Successful, recharge identity 0, residual -2.3e-11. Followed in applying.tex (the listing),
inputs_outputs.tex and exchanges.tex (examples), tests/crs_inputs.py (BOUNDS text; LAKE1 still placed by its series) and
mf6files_check.py (its boundary case uncomments the lines: now with cells). Both pass (crs_inputs quick: 3 / 9 cells in
both runs; mf6files 16 cases, 127 checks, 0 failed).

## Checks
- Targeted runs of the changed scripts with the Phase 9 build (quick mode): crs_inputs (GHB / CHD 3 / 9 cells, ALL
  PASSED), mf6files_check (16 cases, 127 checks, 0 failed), sz_check self-test, test_restart (RS1-RS4 PASS),
  test_hillslope --selftest, test_mf6_budget, test_interface_stiff, test_robustness, test_vz_classes (C9 RT20 ok), run_all
  --selftest: all pass. Every Python file compiles.
- History wording, user-facing files (everything tracked or new outside `docs/design/`): no hit for audit rounds, phases,
  finding ids, v1/v2/v3, "previously", "used to", "formerly", "before the fix", "was an error", "now", "earlier
  check/code/build", "the old". The remaining "audit" words name the audit tool (`tools_audit.py`, "audit tool", "audit
  identities"), "round" is round-off / round trip / round(), "earlier" is time ("earlier entries", "an earlier run",
  "an earlier iterate", "an earlier release" of MODFLOW), "fixed" is fixed head / fixed rates; "no longer" occurs twice
  in its plain sense (a removed package, substeps no longer than a time).
- Manual: `latexmk -pdf`: 164 pages, 0 errors, 0 overfull boxes, no undefined references or citations. Pages rendered
  and inspected: 5.3.9 (the hand-back paragraph), 4.6 (safeguards), Figure 9.6, Table 9.19 (RT cases), 9.14 (Running the
  tests), Table 10.3 (changes to Raven files, two pages), Table A.12 (the TS6 row).
- Package (`wt/p10/pkg/Raven_MF6_linux`, zip `wt/p10/Raven_MF6_package.zip`, 92 MB): bin from `cmake -S wt/p10/code -B
  wt/p10/bld_pkg -DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=code/lib/mf6/libmf6.so` (Release by default) and `cmake --install`;
  examples from `git archive` of a provisional snapshot of this worktree (a scratch bare clone in which the working tree
  is committed on top of e0301a5; the real worktree and branch are untouched); manual = `docs/manual/main.pdf`; source/
  by `tools/package_sources.py <pkg> wt/p10/code rb-p10 <snapshot> rb-p10-tests --update-readme`: restore check PASS
  (code 853 commits to d986fb0, extra 106 commits to the snapshot, both branch `soil-zone`, not shallow, fsck clean); the
  check fails, as it must, on a README with `-b rb-p6` and on one with a wrong commit count.
- From the zip (wt/p10/fromzip, then wt/p10/fromzip2 for the final zip), following the README as written: install check
  PASS; Example A 20 years 480 s (Successful; recharge 0, residual -1.04e-10, 0 unconverged, Raven 0.516 mm); one year
  with `:Duration` 365 15 s; Example B 233 s (recharge 0, residual -1.94e-11, river -5.28e-12, 0 unconverged); the
  README's quick test command: 56 steps passed, 0 failed, 2 not run (USGS examples absent), 15 checks skipped (W4, W6,
  W11; cmake 20 without patchelf; byte-identity checks without RAVEN_EXE_REF), rough terrain 180 + 180 runs, 0 failed,
  combinations 237 runs, 0 failed, 34 minutes (2034 s) on two cores; restore history: 853 and 106 commits, branch
  soil-zone, not shallow. The final zip differs from the tested one only in README and documentation text (run times,
  the `:Duration` instruction); its install check, restore, one-year example and run_all self-test pass, and its extra
  source archive equals this worktree apart from `docs/design`.

## Left open
- `docs/design/` is in the extra history bundle (the bundle is the repository's history); only the source archive
  leaves it out. Removing it from the bundle would need a rewritten history whose commits differ from the repository's.
- Comments in the code (`src/GW*.cpp`, `GroundwaterModel.*`) still name audit rounds and items (e.g. "v3 audit round 1
  items 9, 10, 12" in GWVadoseModel.cpp, "audit A1 IB3" in ParseInitialConditionFile.cpp); the code was not touched in
  this phase (code comments were not in the A3 list).
- The package sources must be regenerated after the coordinator's commit (the bundles and archive now hold a
  provisional snapshot commit): see the commands in the phase report.
