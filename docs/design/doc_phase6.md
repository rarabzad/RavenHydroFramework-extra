# Audit A2, phase 6: documentation as a first release, MT-4..MT-8, package (agent p6)

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Items: DOC1 (the user's request), MT-4, MT-5, MT-6, MT-7, MT-8 (spec/audit_A2/AUDIT_A2_issues_and_phases.md, F_MT.md).
Code unchanged (rb-p6 = cf3e946, the merged soil-zone code). Changes in extra (rb-p6-tests), left uncommitted as asked
(renames staged with git mv; this note added with git add -N).

## DOC1: history removed, manual reorganised
Removed from the manual, user guide, README and tests/README: audit rounds and phases, "v1/v2/v3", the findings and
corrections table (change log), "before audit ...", "fixed", "previously", "now", "(audit ...)" notes, the port from
Raven 4.1.1 (sec:port), "Release audit" as a section, "Audit A1: regression tests" as a section, the rough-terrain
"History" paragraph, run-number and build names (Raven_v3build, v3m11, bbab5ef). Kept as behaviour: where a model without
groundwater differs from Raven 4.15 (new Table 9.2, tab:ravendiff, built from the old findings rows "Raven itself" and the
age-tracer and reservoir rows); design reasons stated in the present tense (XT3D off by default, NEWTON without
UNDER_RELAXATION, head tolerance).

Chapter files (all renamed to topic names; numbers in names no longer match chapter numbers anyway):

| Before | After | Notes |
|---|---|---|
| ch1_intro | intro | |
| ch2_concepts | concepts | |
| ch3_building | building | |
| ch4_existing | existing_model | "Current limits" -> "Limits" |
| ch4_exchanges (+ ch4_vz_kinematic, ch4_vz_lag, ch4_vz_classes, ch4_sz_interface) | exchanges (+ sz_vadose_kinematic, sz_vadose_lag, sz_vadose_classes, sz_interface) | |
| ch5_accounting + ch5_sz_v3 | accounting | the v3 books merged into "The whole system" (sec:accsz, replaces sec:accsz2/sec:szbooks3); one definition of the gross flow in "MODFLOW's balance" |
| ch6_reference | inputs_outputs | MT-6 |
| ch7_applying | applying | MT-5 |
| ch8_verification + ch8_sz_v1 + ch8_sz_v3 + ch8_rough_terrain | verification + verification_soilzone + verification_rough | regrouped by topic, see below |
| ch9_developers | developers | known issues (MT-4); 22 cmake checks; no pull-request history |
| appendix + appendix_sz_v3 | appendix | "Which columns are written" and "Run totals" after the GWBudget table; new A.13 "Warnings and stops during a run" (app:warnings) |

Verification chapter (9) now: 9.1 Models without groundwater (Table 9.2 differences from Raven 4.15), 9.2 Automatic checks
of every run, 9.3 Behaviour tests (incl. reservoirs that run dry), 9.4 Independent checks, 9.5 Model files and faulty input
(mf6files_check, edge.py, faulty-input table), 9.6 Randomized testing, 9.7 Grid types, 9.8 Coupling an existing model
(USGS models, MODFLOW versions = sec:mf6versions), 9.9 The soil zone (test models and checks; column/hillslope/Liard;
unsaturated column and rise; the water table in every position; the interface and MODFLOW's side incl. B8; methods, depth
classes and steady starts incl. I5, I6, C9, C10; input handling; robustness), 9.10 Rough terrain, 9.11 Build checks (all 22
cmake checks in one table), 9.12 Code checks, 9.13 Running the tests. Rows that described "before -> after" were reduced to
the current result; rows that could not be traced to a current test script (the old "Audit round 4" row, the "X3 round trip
after round 4" row, "Suite with LAGGED") were dropped.

Test IDs: V2a..V2j -> P1..P10 (test_v2.py -> test_water_table.py, run_all step soilzone_v2 -> soilzone_water_table);
test_v2_ext.py -> test_sz_existing.py (step soilzone_v2_ext -> soilzone_existing); final lines "water-table tests: ...",
"soil-zone existing-model tests: ..."; work folders soilzone/water_table, soilzone/sz_existing. All references in tests,
manual, README updated; design notes keep the old names (developer records). Figures fig_v2_* -> fig_sz_*,
make_v2_*.py -> make_sz_*.py, tikz_v2_regimes -> tikz_sz_regimes, tables/audit_table -> tables/run_checks
(make_tables.py writes there, no absolute path).

Test scripts: docstrings and comments scrubbed of "(audit round N, x.y)", "audit A1 XX", "v3 audit", FINDINGS/decisions/
files_spec references (files not in the repository), build hashes; technical content kept. "not rebuilt" skips (W6, W11)
now read "not implemented". py_compile clean.

docs/AUDIT_REPORT.md and docs/VERIFICATION_REPORT_MF6.*.md (audit history and run logs of earlier builds) moved to
docs/design/release_audit_report.md and docs/design/logs/verification_report_mf6.*.md.

## MT items
- MT-4: ch10 "Limitations and known issues" gets "Known issues in Raven itself": valgrind uninitialised reads in
  RVPParameterWarning (ParseClassPropertiesFile, 3 contexts) and CVegetationClass::RecalculateRootParams (2 contexts), with
  the channel-storage and dry-reservoir items; also in the user guide (section 9) and the package README; 9.12 refers there.
- MT-5: ch8 "400 randomly drawn rough-terrain cases (1,620 runs with the four unsaturated-zone methods and the regression
  cases)" (test_rough_terrain.py: 400 default seeds).
- MT-6: ch7 output table: the row "GWBudget.csv, last column" removed; "other model packages" is now a row of the
  GWBudget table (existing models, positive into the aquifer); appendix A.10 notes which columns are written and in what
  order (checked against GroundwaterModel.cpp OpenOutputs).
- MT-7: Figure 5.5 (figures/tikz_sz_regimes.tex): "rise from the column" now right-aligned left of its arrow (arrow from
  the water table); panel labels 23 mm wide inside the 26 mm panels; panel (c) label moved below its arrow. Rendered and
  checked at 200 dpi.
- MT-8: test_inputs.py I14/I15: limit 2e-4 d plus 1e-5 of the age (Ages.csv writes 6 significant digits) instead of
  1e-3 d; docstring and manual Table 9.15 agree. Run with Raven_m7.exe: quick and full mode ALL PASSED; largest difference
  1e-4 d (I14, I15 year-end chain), 0 (full 400 + 380 day chain).

## Manual build
latexmk: 0 errors, 0 overfull boxes, no undefined references or citations, no float-specifier warnings; TOC section
numbers widened (10.11, A.15). Pages rendered and inspected: TOC, Figure 5.5, 9.1-9.2, Table 9.13, A.12-A.13, 10.11.

## Package (wt/p6/pkg/Raven_MF6_linux, zip wt/p6/Raven_MF6_package.zip)
- bin: cmake -S wt/p6/code -B wt/p6/bld_pkg -DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=code/lib/mf6/libmf6.so (official 6.8.1
  release library), Release by default (configure: "CMAKE_BUILD_TYPE not given: Release"), cmake --install into the
  package. RavenMF6InstallCheck.py: PASS.
- source/: tools/package_sources.py. The extra changes are uncommitted, so the extra archive and bundle come from a scratch
  clone (scratchpad/snap_extra) in which the working tree was staged and recorded with git write-tree / commit-tree on top
  of rb-p6-tests (a0322f7; the worktree and its branch are untouched). Code from rb-p6 (cf3e946; shallow, completed from
  upstream). Restore check PASS: 851 and 103 commits, not shallow, fsck clean. When the coordinator commits these changes,
  the commit hash will differ from a0322f7 (same tree, apart from this note's package section).
- Manual = docs/manual/main.pdf; examples from git archive of the snapshot (no __pycache__, no outputs); README from the
  phase-3 model without history wording, restore section from source/RESTORE_HISTORY.md, known issues incl. MT-4; no
  VERIFICATION_REPORT logs.
- From the zip (wt/p6/fromzip): install check PASS; Liard_groundwater 20 years: Successful, 16.6 min, recharge identity 0,
  MF6 residual -1.04e-10, 0 unconverged, Raven MB 0.516 mm; Liard_existing_model 2 years: Successful, 6.9 min, recharge 0,
  residual -1.94e-11, 0 unconverged. README quick command (RAVEN_SRC/RAVEN_EXE/RAVEN_MF6_LIB as written): 51 steps passed,
  0 failed, 2 not run (USGS examples absent), 15 checks skipped (W4, W6, W11; cmake 20 without patchelf; 11 byte-identity
  checks without RAVEN_EXE_REF); rough terrain 180 + 180 runs, 0 failed; 58 min on 2 shared cores.
  Log: wt/p6/fromzip/src/quick.log.
