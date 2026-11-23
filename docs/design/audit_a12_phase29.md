# Audit A12, Phase 29: documents, history tool, hand-over, commit messages, workshops

Issues: MT12-2/CB12-5, SV12-1 to SV12-3 (documents), IB12-4 (documents), MT12-1, MT12-3, MT12-4, WS12-1 to WS12-3.
Base: code soil-zone f8c3d0f (unchanged here), extra soil-zone bb37878. Outside the repositories:
/home/claude/rebuild/tools/dev/neutral_trees.py and /home/claude/rebuild/spec/neutral_messages_proposals.json.

## MT12-2 / CB12-5: TS6 rows read through OPEN/CLOSE

Since f8c3d0f a later start reads the TIMESERIES rows of a TS6 file through BlockLines, shifts them and writes them
inline (test E27). The stale statements are gone:
- existing_model.tex (limits list): the clause "and TS6 files whose TIMESERIES rows come from another file";
- appendix.tex: the message row "the time-series file ... reads its rows from another file" (no source file prints it);
- developers.tex (limits): the same clause; it now says the TS6 series are shifted, also rows read through OPEN/CLOSE;
- user guide: the later-start bullet, the message row, and the limits list ("TS6 series are shifted, also rows read
  through OPEN/CLOSE").
Phase 28 edits the line before the limits clause of existing_model.tex (several models); the two hunks touch adjacent
lines and merge by hand.

## SV12-1 to SV12-3: release limits (documents)

Written against Phase 28's warnings (GWVadoseModel.cpp in wt/p28): the release warning names the limit that bound (Sy dh
or the room left in the top cell); rule (ii) writes its own warning once a run.
- exchanges.tex: the warning "names the limit that bound"; KINEMATIC: with one material only the room can bind, across
  aquifer classes Sy dh can bind too. Rule (ii): at most the smaller of Sy dh and the room (at most Sy Lmin, none once
  the head has reached the base or the cell top), so usually nearly all of the column's water goes back to the soil
  zone; a warning the first time.
- sz_vadose_kinematic.tex: the release is at most the integral of Sy over the rise with one material; a node straddling a
  class boundary is counted with the material at its centre, so Sy dh can bind there; the warning names the limit.
  "The limit Sy dh never binds" is gone.
- user guide (section 4, columns): the same three points.
- verification_soilzone.tex R21 and the R21 docstring of tests/soilzone/test_robustness.py: "beyond the smaller of
  Sy dh and the room left in the top cell".
The message rows of the two warnings are Phase 28's (appendix, user guide).

## IB12-4: side files (documents)

building.tex's side-file sentence and the appendix/user-guide rows are rewritten by Phase 28 together with the
canonical-form rule (the BOM message is gone there). Here: verification.tex's side-file row now lists the files in
GDAL's form and the other forms of geotiff_check.py, and states the rule: GDAL's form read as GDAL reads it; other forms
stop ("rewrite it with GDAL") when they name a band or a band value; a file naming none is ignored, as GDAL takes no band
value from it. ("Not a PAM dataset" is no longer listed among the refused files.)

## MT12-1: neutral_trees.py

New rules (applied to every file outside docs/design of every rewritten commit; the tip's lines outside docs/design are
protected, so the tip trees stay identical):
- MORE_RULES: references to files_spec, decisions(.md), FINDINGS_R*, "R1 item 4" (parenthetical, prefix, suffix and
  bracketed forms); finding IDs after a row label ("(IB1)"); the Issue column of the regression-test table (cells, header
  and column widths); change notes ("(117.47 before)", "(120.0 against 100.8 before)", "(before the change: ...)", "the
  old scale gave ..."); the water-table tests V2a-V2j as P1-P10 (the tip's names); "# v2:", "# ---- v3:", "v2
  existing-model tests" (the tip's "soil-zone existing-model tests"), tc.work('soilzone', 'v2') (the tip's
  'water_table'), "(1: the HRU mean, v1)", "the v3 hooks build", "(case v6)"; the KW/LAG stub's "PLACEHOLDER (to be
  implemented)"; COORDINATOR lines, the "PARTIAL reconstruction" line, "Raven previously started it ...", "The suite was
  rebuilt after the loss ...", "rebuild, ... Raven_integ", "no longer fires it", "on the rebuilt code", "not rebuilt"
  (the tip's "not implemented"), "of the rebuilt generator", and the sentences of the old verification chapter that cite
  the dropped sections.
- BLOCK_RULES (applied to the whole file before the protection): the "History" paragraph of the rough-terrain chapter,
  the "Release check" (release audit) and "Findings and corrections" sections of the old verification chapter, the
  table row naming the release check, the regression-test section's audit paragraph (replaced by a neutral one), and
  two multi-line sentences.
- PATH_RULES: spike_xmi.py's V1-V3 as Q1-Q3 (the tip's names, also in tests/README.md); input_checks.py's A1 as AM1
  (also in tests/README.md); vadose_ref.py's "(V2)" and "V2 drainage".
- Binary files are dropped when either the old wording check or the final check finds wording in their text.
- Protection now uses only the tip's lines outside docs/design (a docs/design line no longer protects an older line).

The final check (final_scan, part of `run`): process_wording.RULE (finding IDs and generation names included) plus
FINDINGS, files_spec, decisions(.md), "R1 item", "fixed in", rel builds, "N before)" notes, the finding-ID families as
words, "the old scale/code", "now reports"; applied after masking the product words listed in ALLOW (the water-balance
audit tool, its module, outputs and identities; product test, step and case names RS1-RS6, BR1-BR3, AM1, D1-D3, Steps
A1-A6, grep's -A6; other software's versions; git and English words in their product meaning, each as a phrase; the
design notes by their file names, which the code tip cites) and, in code files, short identifiers in the code part of a
line (d1, a2, v5). A phrase that a line break splits is masked across the break (the line is checked with its
neighbours). Every line it still finds is printed; there must be none. The tip's own lines that it finds (code: only lines
that are not base Raven's) are printed as "tip (kept as it is)" and never changed.

Self-test: 52 text cases, 21 final-check cases (forms it must find, product words it must leave), the repository case.

Rehearsal on fresh clones (wt/p29/hist, deleted afterwards): see patches/rehearsal_*.log. Result: final check 0 lines,
0 names, 0 binary files in both repositories; tip trees identical (code 54694c3, extra 64d08b8); the old wording checks
0; the tip lines it reports: the 18 stored rough-terrain cases' "how" field ("of the rebuilt generator"), extra only. A second
run changes nothing (0 new trees in both repositories); every rule was checked to be idempotent on every blob of the
range. Times: apply 19 s; run 2 min 49 s (code 36 s, extra 132 s, most of it the final check).

## MT12-3: e03243d and a route without a backup branch

make_handover.py: KNOWN_PUBLIC holds e03243d and what it contains (docs/AUDIT_REPORT.md, comments naming the stages of the
work in src/GroundwaterModel.h, a README line pointing to the report). When the public branch holds commits the kit does
not, HANDOVER.md says that they are already public, names e03243d's content, says which routes keep them on GitHub (the
backup branch of 1A-replace, 1B, step 4), and offers block 1A-replace-local: it saves GitHub's branch into
RavenHydroFramework_<branch>-before-release.bundle in the working folder (verified with git bundle verify), then
replaces the branch with --force-with-lease, so no GitHub branch holds the old commits (GitHub may still serve a commit by
its full ID until it removes unreferenced commits). The user decides when publishing. run_blocks now runs
1A-replace-local (published, no backup branch, the bundle holds the old commit; run again: nothing to replace; an
existing bundle without the branch: stops, nothing pushed) and 1A-replace (backup branch at the old commit). Nothing is
pushed to GitHub; the public branch is only read.

## MT12-4

spec/neutral_messages_proposals.json: f8c3d0f gains "ParseGWFile messages name the HRU ID or cell number; :LandSurface
and :BedrockSurface take the file name and METRES only"; 1ecc1ef gains "make_handover.py: the tip keeps its tree when
older commits' files are edited". neutral_messages check: PASS.

## WS12-1 to WS12-3

- W1 and W5 README folder maps name work_full/ (optional full run) and work_part2/.
- W3 08_compare: the conceptual run's recharge reaches the aquifer: \V{t3:conceptual:reaches} m3/d the water table, the
  rest the pond's specified-head cells (W2 Step 13). values.tex holds 54 881 until the regeneration writes it.
- W4 Steps 4 and 5: "Or copy" lines from model/step_07 (Creek.rvh, Creek.rvi; Creek.rvp).
The workshops are regenerated with the Phase 28 build.

## Follow-up: tip lines the wide check flagged

- tests/soilzone/rough_cases/*.json (18 files): the "how" field reads "... of the generator ..." (as
  test_rough_terrain.py --make-cases already writes it). Only "spec" of these files is read (test_rough_terrain.py:397,
  610); nothing compares or checksums "how".
- The design notes whose names held a version are renamed: soil_zone_v2_plan.md -> soil_zone_columns_plan.md,
  soil_zone_v3_cls -> soil_zone_depth_classes, _f2 -> soil_zone_stiff_interface, _f3 -> soil_zone_existing_outputs,
  _integ -> soil_zone_interface_iteration, _kw -> soil_zone_kinematic, _lag -> soil_zone_lag, _q1 ->
  soil_zone_restart_sy, _rough -> soil_zone_rough_terrain, rebuild_core_v1 -> rebuild_core, rebuild_v2 ->
  rebuild_columns, rebuild_v3h -> rebuild_hooks. References: three design records here, and 12 comment lines of the
  code (GWSoilZoneStep.cpp, GWVadose.cpp/.h, GWVadoseKW.cpp, GWVadoseLag.cpp, GWVadoseModel.cpp, GroundwaterModel.h,
  comments only). The extra tip held no other reference outside docs/design.
- neutral_trees.py: the design-note names are no longer in ALLOW (the final check flags them); DESIGN_RENAME renames
  the files in docs/design of every older commit (text kept, apart from the names) and every mention of an old name,
  in docs/design too, LaTeX form and the "soil_zone_v3_*.md" glob included.
- make_handover.py's note on e03243d describes the report without its file name.
- "Review:" in verification.tex stays (a product use, in ALLOW).
Rehearsal with the Phase 29 changes committed on top of the rewritten clones (a stand-in tip): final check 0 lines in
both repositories, tip trees identical, the tip lines the final check finds: code 0, extra 0.

## After the merge (code 56e385b, extra 0f02576)

- Rule (ii) writes no warning (Phase 28 removed it: it fired in ordinary runs). exchanges.tex and the user guide say so;
  sz_vadose_kinematic.tex describes K11 and K12 (K12: no release warning); R21 (manual, test docstring) matches the code.
- Merge resolution checked in appendix.tex, existing_model.tex and the user guide. Also corrected: existing_model.tex's
  later-start paragraph (a simulation of several models stops at any start, not only a later one; "time series in a
  simulation holding more than one model" removed); developers.tex's limits list (one GWF model with no exchanges; a
  restart refuses kept packages with a state of their own); the user guide's limits list (the same restart rule).
- verification.tex: Table tab:faultyext2 (E31-E37 with E31b, E32a-E32e, E32c2, E34b, E34c, E35b, E35c); the band-unit row
  (553 texts: 146 metre forms, 3 none, 185 other lengths, 73 scaled, 146 other texts; the METRES warning); a table of its
  own for the side file (tab:sidefiles: CRLF line ends, a value starting with a line end, georeferencing, ESRI ASCII side
  files); the ESRI ASCII row (no NODATA_value line; no GDAL_NODATA tag). verification_soilzone.tex: K1-K12, L1-L8;
  sz_vadose_lag.tex: L8. tests/README.md: E31-E37, K11, K12, the band-unit count and the side-file rule, to match.
- W4: the copy commands end in a tied dot (no dot alone on a line).
- Workshops regenerated with rel28 (only W3's LAG warning excerpt changed; run times kept as committed, the build ran
  beside two compiles); --check on all six; release binary built twice from 56e385b (TZ UTC/LANG C and
  TZ Asia/Kathmandu/LANG C.UTF-8): identical. (The zips were not made in that pass; see below.)

## Final pass (after the session loss)

- Checked the earlier pass's edits against the code at 56e385b: rule (ii) has no WriteWarning (GWVadoseModel.cpp, the
  vanishing-column branch); the release warning names the limit that bound (room or Sy dh) as exchanges.tex, appendix.tex
  and the user guide say; the one-model refusal (GWExternal.cpp: several models or any EXCHANGES row, at any start) and
  the restart refusal (ExtRestartState: LAK, MAW, UZF, CSUB, SFR with STORAGE) as appendix.tex, existing_model.tex,
  developers.tex and the user guide say. tab:faultyext2 against input_checks.py E31-E37; K11, K12, L8 against the test
  docstrings; band_units.tsv: 553 rows, M 146, N 3, F 185, X 73, S 146. No text edits were needed.
- Workshops: the earlier pass's regeneration with rel28 and its --check on all six (patches/ws_build.log, ws_check.log)
  stand; nothing in the workshop folders changed since.
- Release binary: wt/p29/Raven_release.exe (56e385b), sha256 0af36ce4...44c5. Rebuilt in a fresh folder: identical, first
  with zig's shared cache, then with an empty cache of its own (ZIG_GLOBAL_CACHE_DIR in the fresh folder, TZ
  America/Los_Angeles): see patches/rel_check.log and rel_cold.log. The fresh folders are deleted.
- Zips: --package --source-commit 56e385b with the release binary into wt/ws/zips_final (the old zips replaced;
  patches/zips_old_sha256.txt, zips_new_sha256.txt); bin/Raven in each is the release binary.
- Manual: check_manual_pdf.py --write and then the check: PASS (195 pages). tools_check.py: ALL PASSED; make_package.py
  --self-test: ALL PASSED.
- Rehearsal on fresh clones (wt/p29/hist/r6, deleted): neutral_messages apply PASS (code 90, extra 146 rewritten, trees
  identical); the extra changes of this worktree committed on top as a stand-in tip (code has none); neutral_trees run:
  final check 0 lines (names 0, binary files 0) in both, tip trees identical (code ab87522, extra 51f5b35), tip lines
  the final check finds: 0 and 0. PASS. (The stand-in held this note without this section; docs/design is outside the
  check.)
