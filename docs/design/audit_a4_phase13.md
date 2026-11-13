# Audit A4, phase 13: documentation, code comments, hand-over kit

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Phase 13 of the round-4 audit (issue list: `spec/audit_A4/AUDIT_A4_issues_and_phases.md`; brief:
`spec/phase13_brief.md`): MT4-4, MT4-5, SZ4-3, VZ4-5, MT4-8 = IB4-6 (code comments included), MT4-9, the user-guide gaps
(MT4-10, third point) and the restart wording, the repositories and clone instructions (MT4-6, the publication step),
the hand-over kit, and the review-brief references. Reference build: phase 12 (`wt/p12m_Raven.exe`, md5
`5c6eb7a272bc10ba0c390de7defa5717`); this build: `wt/p13/Raven_p13.exe` (md5 `7ddfcc28ee4c9b990b06f8b2de52f5f9`, built after the review fixes; see Review
responses for the build date it carries).
Worktrees `wt/p13/code` (branch rb-p13) and `wt/p13/extra` (rb-p13-tests); nothing is committed (patches in
`wt/p13/patches/`).

Behaviour changes: none, apart from two output headers (VZ4-5's summary line and SZ4-3's `gwf.swx` header comment).

## MT4-4: Raven's balance error after a hotstart with a spilling reservoir (known issue of Raven)

Added to the known issues of Raven itself in the manual (`developers.tex`, "Known issues in Raven itself") and the user
guide (section 9), with the restart wording of `accounting.tex` and the guide pointing to it. The text names the cause
(Raven's initial storage at a hotstart leaves out half the water that crossed the reservoir in the step before the
restart: half its outflow, and half of returned or unsupplied reservoir seepage flowing on into it), says that base
Raven does the same, that the restarted run's states, flows and stages are the continuous run's (exactly when coupled),
that only `MB Error` (and with it `tools_audit.py`'s "Raven MB error max") is offset, and gives numbers.

Numbers measured for this note (`patches/mt44_restart_offset.py`, log `patches/mt44_restart_offset.log`): the lake of
`combinations.py`'s `CONC_NONE_res_plain` (4 HRUs, 0.16 km2), started 0.2 m above its crest so that it spills on the
first two days, 15 days continuous against restarts from the `solution.rvc` of days 2, 4, 6 and 9:

| Build, model | Restart day 2 (lake spilling) | Restart days 4, 6, 9 (no outflow) | Largest store difference |
|---|---|---|---|
| base Raven 4.15, no groundwater | +7.3872 mm = 1,182.0 m3 = half of 2,364.0 m3 | 0 | 1e-3 mm (5-decimal states) |
| this build, no groundwater | +7.3875 mm (the same) | 0 | 0 |
| this build, coupled | +14.9244 mm = 2,387.9 m3 = half of 4,775.8 m3 | 0 | 0 |

The offset is constant over the restarted run (first and last day equal to 1e-3 mm). The audit's own numbers (50.3 mm
for a lake spilling 16,100 m3/d), the phase 12 review's F6 (0.1 to 0.6 mm when returned or unsupplied seepage is in
transit) and the phase 11 note (0.1 mm, returned seepage) are quoted as "about 50 mm" and "0.1 to 0.6 mm".

Not done: starting the Raven balance of `tools_audit.py` / `sz_check` at the restart's first step (the audit's second
suggestion): the identity would then hide the offset rather than explain it, and base Raven's output is left as it is.

## MT4-5: the FAQ on rivers and the existing-model river loss

- `applying.tex` FAQ: "Hardly from a river Raven builds" (the supply limit at the start of the step; review F5), and an existing model's stream package keeps its
  own conductance, has no supply limit, and carries what the channel cannot supply (Section `sec:extlimits`); Example B
  does this for months, up to about 1e8 m3, repaid by the end.
- "normally zero" qualified in `accounting.tex` (with the pointer to the limits), `appendix.tex` and `inputs_outputs.tex`
  (shortened there so that the `GWBudget.csv` table still fits its page).
- `examples/README.md` Step B5 states `max outer iterations` 245 and the carried river loss (about 1.06e8 m3, 288 of 731
  days, 0 at the end). Checked with this build: Example B, 2 years, 4 min 38 s, Successful; `tools_audit.py`: recharge
  0, residual -1.94e-11, worst step 4.03e-8 %, 0 unconverged, max outer iterations 245, river -5.28e-12, carried at end 0,
  carried max 1.06e+08 (1986-04-18), non-zero on 288 of 731 days (first 1985-10-02, last 1987-03-30), Raven MB error max
  0.515 mm, 0 ERROR lines.
- The user guide's section 9 bullet on existing models names the carry too.

## SZ4-3: wording and output of the soil-zone interface

- **`gwf.swx` header (output, generated models with `:SurfaceWaterExchange`).** The header comment states the bed datum
  `SWXDatum` uses: with `:SoilZone PHYSICAL` "the ground above the soil zone (soil-zone base + thickness; the model top
  under HRUs without a soil zone, area-weighted)"; without it, when a store's profile gives `SOIL_ZONE_DEPTH`, "the model
  top (the land surface less the profile's SOIL_ZONE_DEPTH)"; otherwise the line is unchanged ("land surface", which is
  then the model top). Only the comment lines change; the entries are the same. The existing-model `raven.swx` already
  distinguished the cases.
- `tools/plot_soilzone.py` docstring: the levels are drawn against the soil-zone base (dashed); the land surface is not
  mentioned.
- `inputs_outputs.tex` (Table of outputs), `appendix.tex` and the user guide (two places): `interface updates` and
  `interface change [m]` of `GWSoilExchange.csv` are listed apart, as model-wide values of the step repeated on every row.
- `exchanges.tex` (wetlands and lakes): groundwater under an empty store returns through the seepage drain, and under
  `:SoilZone PHYSICAL` the soil-zone HRUs, which have no seepage drain, take it into the soil zone, from which it
  overflows. The code comment in `GroundwaterModel.cpp` at the supply limit says the same.

## VZ4-5: the summary header of the unsaturated columns

`GWModelSummary.txt`'s header line for `RICHARDS` and `KINEMATIC` columns read "...; 0 substeps and 0 Newton iterations
in all" (the summary is written before the first step). It now ends "accuracy 0.02 (the substeps and Newton iterations
of the run are in the run totals)", as the `LAG` line points to the run totals; the run totals at the end are unchanged
("38 substeps and 150 Newton iterations in all" in byte-identity case `t1_phys`). Dropping the counts was chosen over
rewriting the header at the end: the header is written once, before the run, like the rest of the summary's header.

## MT4-8 = IB4-6: audit references and history wording

**Code (worktree `code`, every file the coupling added or changed against Raven 4.15, `git diff e7e2868`).** 91 audit
references removed from comments ("audit round N, xN.N", "audit A1 IB7", "v3 audit R1 item N", "round 9 i5.3",
"decisions.md C.n", "Phase 2/3", "soil zone v2/v3", "(v1)", "plan §"), in `cmake/RavenMF6.cmake`,
`cmake/RavenMF6Bundle.cmake`, `.github/workflows/raven-mf6.yml`, `src/GWSoilZoneModel.cpp`, `GroundwaterModel.cpp/.h`,
`GWExternal.cpp`, `GWVadose*.cpp`, `GWSoilZone.cpp`, `MF6Engine.h`, `AgeTracers.cpp`, `ParseInitialConditionFile.cpp`,
`ParseGWFile.cpp`, `ParseInput.cpp`, `GWGrid.cpp/.h`. Past-tense accounts of failures ("MODFLOW took 8453 m3/d from a
column...", "the previous per-link test stalled the Liard run", "is gone", "Fill ignored it", "the original arithmetic",
"(obsolete MODFLOW-USG recharge classes removed)", "preserved ... in legacy/mfusg/") are rewritten as what the code does
and what would happen otherwise. Domain wording that only looks like history was kept: simulation states ("the
seepage was computed", "a column that was a specified head in the last step"), the user-facing message about the
MODFLOW-USG commands of Raven 4.15 and earlier, and the output text "(was period N)" in a renumbered working copy.

**Proof that the comment edits change nothing.** The build of the code worktree with every comment edit and without the
two output changes is byte-identical to the reference executable (`cmp`, md5 `5c6eb7a...` for both; built twice: after
the first set of edits, `wt/p13/Raven_p13_comments.exe`, and with all edits and the two output changes reversed in a
scratch copy). `patches/code_comments_only.diff` is the first set; `patches/comments_only_binary.md5` the checksums.

**Tests, examples, manual, guide, READMEs (worktree `extra`).** "IB10" (`test_inputs.py`), "(they were dropped
silently ...)", "(they were written at the start, always 0)", "(a line there was 30-50 % off)", "(it was 17 times)", "(it
was 39 m3/d ...)", "583 m3 were lost", "(before: ...)", "(It was dropped silently ...)", "(the name ... once used)",
"case v6"/`s5_v6`, the cmake_checks IDs h5.2-h5.8 and i5.3-i5.6, the unit tests' "[R1 item N]", "bit for bit as before",
"plan §9.2"/"plan §7" are recast as present-tense statements of what each check guards against ("a clip would lose 583
m3", "without them ... would be"). The I21 row of the manual's input table now gives the results only (the GHB drains,
the water table is not held at a cell bottom, the restart has the same 4 CHD cells). `docs/design/` keeps its records.

Kept on purpose: the tool name `tools_audit.py` and "the audit tool" / "audited" for it (a water-balance check of a
run, named so in the manual, the README and every test that imports it; renaming the shipped tool would break users'
scripts for no gain); "reference build" for `RAVEN_EXE_REF` (the byte-identity setting of the tests); "regression cases"
of the rough-terrain suite (stored hard cases).

## MT4-9: unique test IDs

Every ID prefix now belongs to one script, and no ID is used twice (scripts, `tests/README.md`, manual tables):

| Script | Before | After |
|---|---|---|
| `soilzone/test_vz_initial.py` | I1-I8 (against `test_inputs.py` I1-I22) | VI1-VI8 |
| `soilzone/test_plot_tool.py` | P1-P3 (against `test_water_table.py` P1-P11) | PT1-PT3 |
| `budget_file.py` | B1-B6 (against `test_mf6_budget.py` B1-B9) | BF1-BF6 |
| `reservoir_checks.py` | R1-R4, R1b, R1c (against `test_robustness.py` R1-R22) | RV1-RV4, RV1b, RV1c |
| `input_checks.py` | R1-R2 (the same) | RN1-RN2 (N1-N16, U0-U4 kept) |
| `tools_check.py` | T1-T5 (against the soil-zone T1-T7) | TC1-TC5 |
| `soilzone/test_column.py`, `test_hillslope.py`, `test_dynamics.py`, `test_liard_physical.py` | T1/T1b, T2/T3, T4/T5, T7 (one prefix, four scripts) | CT1/CT1b, HS1/HS2, DY1/DY2 (SG kept), LP1 |
| `soilzone/test_robustness.py` | R14-R22 also called N1-N9 (against `input_checks.py` N1-N16) | R14-R22 only |
| `soilzone/test_vz_lag.py` | U, L1-L7, S, B (U against `input_checks.py` U0-U4, B against B1-B9) | LU, L1-L7, LS, LB |

`tests/README.md` gives each script's IDs, and `test_inputs.py`'s row says I1-I22 (it said I1-I19). `run_all.py` reads
two of the renamed lines (`HS1/HS2 hillslope: PASS`, `LP1 Liard physical: PASS`): changed with them. The code comment
naming the tests run with MODFLOW 6.5.0 (`MF6Engine.h`) says HS1/HS2. The workflow and judges otherwise read no ID.

## User-guide gaps and the restart wording

- Section 4.3b gains "Reservoir seepage": the share F of the lake's linked area over cells that can take seepage (not the
  model's specified heads of the step, not inactive cells without NEWTON), the seepage computed with k F, delivery the
  next step to the cells that can take it then (each at most at its earlier rate), the return of a loss MODFLOW does not
  take to the reservoir's subbasin (`reservoir seepage not delivered by MODFLOW [m3]`, warning, run total), the gain
  MODFLOW does not supply taken back (`reservoir gain not supplied by MODFLOW [m3]`), and `:GWReservoirSeepage`.
- Section 9's "work as with a generated model" now says that these exchanges move no water on the model's specified-head
  (and, without NEWTON, inactive) cells and that undelivered seepage returns to the subbasin.
- Restart wording: in a coupled run "a run continued from `solution.rvc` carries on exactly"; a run without groundwater
  is base Raven's hotstart and continues from 5-decimal states; Raven's `MB Error` offset of MT4-4 is named, in the guide
  (4.5) and the manual (`accounting.tex`, now labelled `sec:hotstart`, and the FAQ "How do I restart a long run?").
- `sz_vadose_kinematic.tex` said the column contents are written with 15 significant digits; they are written with 17
  (phase 12); test K5 now gives a restart deviation of 0 (60 + 60 days against 120), as this phase's quick run shows.

## Repositories and clone instructions (MT4-6)

Target: code = branch `mf6-coupling` of https://github.com/rarabzad/RavenHydroFramework (our `soil-zone` of `code`),
extra = https://github.com/rarabzad/RavenHydroFramework-extra, default branch `main` (our `soil-zone` of `extra`).
- README (Quick start comment "default branch main", the paragraph on the branches with the offline bundles),
  `examples/README.md` Step 2, the user guide (section 2: both clone commands, the offline bundles), the manual
  (`applying.tex` Step 0: both repositories; `developers.tex` "Where things live": branch `main`, the two clone commands,
  the offline bundles, `make_handover.py`), `tests/README.md` (the clone commands in the layout), the code repository's
  README (a pointer to the -extra repository). The examples' Liard README already named `mf6-coupling`.
- `tools/package_sources.py`: the bundles carry the branches of the public repositories (`--code-branch`, default
  `mf6-coupling`; `--extra-branch`, default `main`; the single `--branch soil-zone` is replaced), and the README restore
  section clones them as `RavenHydroFramework` and `RavenHydroFramework-extra`, "the same checkouts as cloning" the public
  repositories. The statement check matches a folder name only as a whole word (one name is a prefix of the other).
  Tested on a scratch package (`handover_test/pkg`): PASS (857 commits to 3155d20 on mf6-coupling, 111 to f8f074e on
  main, both not shallow and fsck clean); with the README's count edited to 856: FAIL naming the statement
  (`patches/package_sources_test.log`). The source archives keep their folder names (`raven-soil-zone/`,
  `raven-mf6-extra/`), which `tests/README.md` and the README use.
- The package README itself is written at release (not in these repositories): its "Restore the git history" section is
  rewritten by `package_sources.py --update-readme`; its known-issue list should take the MT4-4 text (left open below).

**Finding.** The public `mf6-coupling` is at `e03243d` ("Raven-MODFLOW 6 groundwater coupling", 2026-09-30, one commit on
`e7e2868`), which is **not** an ancestor of `soil-zone` (whose history starts the coupling with `0cdb83c` and three
sibling commits on `e7e2868`). The audit's report (MT4-6) called it an ancestor. Publishing the history therefore needs a
forced push (with lease, after a copy of the old branch), not a fast-forward; `make_handover.py` reads this at kit time
and `HANDOVER.md` gives both cases.

## Hand-over kit: `tools/make_handover.py`

`python3 tools/make_handover.py <code repo> <extra repo> [--code-rev soil-zone] [--extra-rev soil-zone] [--out handover]`
writes:
- `RavenHydroFramework_mf6-coupling.bundle`: the complete history of code `soil-zone` as branch `mf6-coupling` (a
  shallow repository is completed from the upstream Raven history, `package_sources.publish_repo`);
- `RavenHydroFramework-extra_main.bundle`: extra `soil-zone` as `main`, with its whole history;
- `RavenHydroFramework_mf6-coupling.tar.gz`, `RavenHydroFramework-extra_main.tar.gz`: `git archive` of each tip;
- `HANDOVER.md`, made of self-contained command blocks (each tagged `# [name] run in: the working folder`, run in a
  `( set -eu ... )` subshell from the folder holding `handover/`; see Review responses, F2): 0-checksums; 1A-check,
  1A-push (fast-forward), 1A-replace (a copy as `mf6-coupling-before-release` only when missing, then
  `--force-with-lease` on the value just read); 1B-bundle and 1B-archive (one new commit, pushed only when its tree is the
  kit's); 2-extra and 2-extra-files; 3-verify (clone back, IDs, counts, fsck: `verify: PASS`) and 3-build (CMake build in
  `check/RavenHydroFramework/build`, install, `RavenMF6InstallCheck.py`, `run_all.py --nolib`); 4-show, 4-keep,
  4-keep-push, 4-merge for commits GitHub holds and the kit does not; 5 afterwards;
- `KIT.txt` (commit, tree, date, subject, count of each, the public state read at kit time), `SHA256SUMS.txt`.

Checks: `git bundle verify`, each bundle holds only its branch, a clone of each is on that branch, at the recorded
commit and tree, not shallow, with the recorded count, `git fsck --full` clean; each archive unpacks into one folder
named as the repository; every block of HANDOVER.md passes `bash -n`, and the blocks are run as written, each in a new
bash, against local stand-ins for the GitHub repositories (`url.insteadOf`): 0-checksums, 2-extra, 1B-bundle and
1B-archive (published tree = the kit's), 1A-check and 1A-push, 4-show, 3-verify, 2-extra-files; the public branch is
read with `ls-remote` and fetched to test ancestry (never pushed; `GIT_TERMINAL_PROMPT=0`). The output folder must be
new or empty.

**Release policy for docs/design: kept in the -extra repository.** The brief left the choice open. `package_sources.py`
already states the policy: the developer records stay in the repository and its history and are left out of the
package's source archive. Publishing the history means publishing every earlier commit, all of which hold
`docs/design`; leaving it out of the tip would not take it out of the public repository, and taking it out of the
history would rewrite every commit, so the published commits would no longer be those of `soil-zone` (no check by
commit ID, bundles of the package and the kit disagreeing). The code's comments also refer to the design notes
(notation, `GWSoilZone.h`).

**Test run** (`wt/p13/handover_test/handover`, from `/home/claude/rebuild/code` and `/home/claude/rebuild/extra`, branch
`soil-zone`; log `patches/make_handover_test.log`): 24 s, PASS. Code: commit 3155d20, tree 0891fdaf, 857 commits, bundle
20.5 MB, archive 33.9 MB; extra: commit f8f074e, tree 69d385e0, 111 commits, bundle 17.4 MB, archive 10.7 MB. Public
state: `mf6-coupling` at e03243d, not an ancestor (1 commit not in the bundle); the -extra repository not readable
anonymously. Refused: a second run into the same (non-empty) folder. The real kit is made at release time from the
committed branches.

## Review-brief references

None found outside `docs/design/` in either worktree (grep for "brief", "reviewer", "review" in documentation, tests,
tools and the coupling's code; `verification.tex`'s "Review: line-by-line reading" describes the method).

## Results

- **Builds.** Before the review: `wt/p13/Raven_p13.exe` md5 `8c0201869cea8a4cb9df4f28ab88a5e3`; with the two output edits
  reversed the sources built the reference executable byte for byte (`patches/comments_only_binary.md5`). After the
  review fixes (comments only): see Review responses.
- **Byte-identity** (`patches/byteid.py`, the phase 12 script with this build, the p12m reference and three new cases;
  log `patches/byteid.log`): 0 comparisons with differences. Without groundwater against base Raven: the small model
  (none, Nitrate, AGE; three chained parts) identical; Liard 5 years and its 1-year hotstart identical; the reservoir
  model identical to the reference build and different from base Raven only in WatershedStorage.csv, solution.rvc,
  ReservoirMassBalance.csv and ReservoirStages.csv (the reservoir corrections). Coupled against the reference build:
  Liard CONCEPTUAL 180 d, the existing model 31 d (outputs and mf6 folders), the CONCEPTUAL case with 10 unconverged
  steps: identical, `solution.rvc` included; PHYSICAL + RICHARDS and the new PHYSICAL + KINEMATIC case: identical but
  for the one `GWModelSummary.txt` header line of the columns (checked to be exactly the counts replaced by the pointer);
  the three new surface-store cases (PHYSICAL; CONCEPTUAL; CONCEPTUAL with SOIL_ZONE_DEPTH 0.5): every output and
  every mf6 file identical, `gwf.swx` identical in its entries, its header naming the ground above the soil zone, the
  land surface (byte-identical file), and the land surface less SOIL_ZONE_DEPTH.
- **`run_all.py --quick`** (`RAVEN_EXE_REF` = p12m; `patches/run_all_quick.log`, `run_all_report.md`, step logs in
  `patches/run_all_logs/`): 60 passed, 0 failed, 2 not run (the USGS examples: no mf6examples.zip), 3 checks skipped
  inside passing steps (W4, W6, W11, as before); 50 min 34 s. The reference-build comparisons ran and passed (C1, K8, LB,
  BF4, M3, X8, D3, the `crs_inputs` lon/lat run, the `ext_exchanges` plain run); combinations 311 runs, 0 failed, 0
  known; the renamed IDs print as renamed and `run_all.py`'s judges match them (`HS1/HS2 hillslope: PASS`, `LP1
  Liard physical: PASS`); K5's restart deviation 0.
- **Manual** (scratch copy, `latexmk -pdf`; `patches/manual_build.log`): 173 pages, 0 LaTeX or package warnings, 0
  overfull boxes, 0 undefined references or citations. `main.pdf` is not rebuilt in the worktree.
- **Example B** with this build (`patches/exampleB_audit.log`): as in the MT4-5 section.
- **Kit and package tools:** `make_handover.py` PASS; `package_sources.py` PASS and its negative check FAIL as it should
  (sections above).

## Files

Code worktree: `.github/workflows/raven-mf6.yml`, `CMakeLists.txt` (review), `README.md`, `cmake/RavenMF6.cmake`, `cmake/RavenMF6Bundle.cmake`,
`src/AgeTracers.cpp`, `src/GWExternal.cpp`, `src/GWGrid.cpp`, `src/GWGrid.h`, `src/GWSoilZone.cpp`,
`src/GWSoilZoneModel.cpp`, `src/GWSoilZoneStep.cpp` (review), `src/GWVadose.cpp`, `src/GWVadoseKW.cpp`, `src/GWVadoseLag.cpp`, `src/GWVadoseModel.cpp`,
`src/GroundwaterModel.cpp` (comments; VZ4-5 header line; SZ4-3 `gwf.swx` header), `src/GroundwaterModel.h`,
`src/MF6Engine.h`, `src/ParseGWFile.cpp`, `src/ParseInitialConditionFile.cpp`, `src/ParseInput.cpp`.

Extra worktree: `README.md`; `docs/Raven_MF6_Groundwater_UserGuide.md`; manual chapters `accounting.tex`, `appendix.tex`,
`applying.tex`, `building.tex` (review), `developers.tex`, `exchanges.tex`, `inputs_outputs.tex`, `sz_vadose_kinematic.tex`, `sz_vadose_lag.tex`,
`verification.tex`, `verification_soilzone.tex`; `examples/README.md`; `tests/README.md`, `tests/budget_file.py`,
`cmake_checks.py`, `edge.py` (review), `input_checks.py`, `reservoir_checks.py`, `run_all.py`, `testconfig.py`, `tools_check.py`,
`tests/soilzone/` `sz_check.py`, `sz_reference.py`, `test_column.py`, `test_confined_wet.py`, `test_dynamics.py`,
`test_hillslope.py`, `test_inputs.py`, `test_interface_stiff.py`, `test_liard_physical.py`, `test_mf6_budget.py`,
`test_plot_tool.py`, `test_restart.py`, `test_robustness.py`, `test_surface_stores.py`, `test_sz_existing.py`,
`test_vz_initial.py`, `test_vz_lag.py`, `test_water_table.py`, `soilzone_unit.cpp` (review), `vadose_kw_unit.cpp`,
`vadose_lag_unit.cpp`;
`tools/package_sources.py`, `tools/plot_soilzone.py`, `tools/make_handover.py` (new); this note (new).
`main.pdf` is not rebuilt in the worktree (compiled in a scratch copy only).

## Left open

- The release package's README (outside the repositories): take the MT4-4 known-issue text, and rewrite its restore
  section with `package_sources.py --update-readme` (it then names `mf6-coupling` and `main`).
- `developers.tex` names the five pull-request groups by branch names (`mf6-groundwater`, `fix-ensemble-reset`, ...)
  that exist neither in the repositories nor on GitHub; they are the planned pull-request names (the groups are the four
  commits on `e7e2868` at the start of the history and the age-tracer change). Left as written.
- Publishing (MT4-6) remains the user's step: `make_handover.py` at release, then `HANDOVER.md`.

## Independent review

The review (`wt/p13/review/REVIEW.md`, logs in `wt/p13/review/logs/`) found one S1 (conditional), one S2, three S3 and
five S4 items, and confirmed the rest (no behaviour change, byte-identity, the MT4-4 and Example B numbers, the
reservoir-seepage and restart texts, the test IDs apart from F8, the clone instructions, the kit's verified paths, the
non-ancestor public branch).

## Review responses

**F2 (S1): HANDOVER.md step 4 could delete the backup branch in a new shell.** `$OLD`, set only by a block of 1A, was
empty in a new shell, and `git push origin $OLD:refs/heads/mf6-coupling-before-release` became a delete. HANDOVER.md is
now made of self-contained blocks: each is tagged `# [name] run in: the working folder (the one that holds handover/)`,
runs in a `( set -eu ... )` subshell (it stops at the first failing command, an unset variable is an error, and the
shell is left in the working folder), clones or reuses `RavenHydroFramework/` itself, and works out every value again
from GitHub (`git fetch --prune origin`): the branch's current commit `CUR` for the lease, and the commits to keep `OLD`
(from `mf6-coupling-before-release` when it exists, else from `mf6-coupling`). Every expansion is quoted; no block pushes
an empty or computed-empty ref (set -u, `rev-parse -q --verify` guards). The backup is pushed only when it is missing,
and a block stops when an existing backup does not hold GitHub's branch; no block deletes anything. The stray `cd` is
gone (blocks start in the working folder and `cd` inside their subshell). Step 4 is split into 4-show, 4-keep (cherry-pick
onto a local `release`, refusing an existing one), 4-keep-push (plain push when GitHub's branch is in `release`, else
backup-if-missing and lease) and 4-merge (no force: the merge holds GitHub's branch). Folder and shell-state dependence
of every block was checked by running each block in a new bash (below).

**F1 (S2): 1B from the archive published a tree without `src/Makefile`.** Both archive paths (1B-archive and
2-extra-files) use `git add -A -f`, and every block that builds a commit from files (1B-bundle, 1B-archive,
2-extra-files) pushes only after a scripted check that the commit's tree is the kit's (`test "$TREE" = <tree> || {
echo "STOP: ... nothing pushed"; exit 1; }`). `make_handover.py` no longer checks the archives its own way: it extracts
the blocks from the HANDOVER.md it has just written (`blocks()`) and runs them as written (`run_blocks()`), each in a
new bash with git's `url.insteadOf` mapping the GitHub addresses to local bare stand-ins (code: an ancestor of the
kit's tip with another tree, `main` beside it; -extra: empty), and checks the result of each: 0-checksums, 2-extra
(-extra `main` = the kit's commit), 1B-bundle and 1B-archive (published tree = the kit's; the stand-in reset after
each), 1A-check and 1A-push (fast-forward to the kit's commit), 4-show, 3-verify (`verify: PASS`), 2-extra-files on an
empty stand-in (the kit's tree). Every block also has to pass `bash -n`.

**F3 (S3): step 3's tests did not find the Raven it built.** Block 3-build builds in `check/RavenHydroFramework/build`,
where `testconfig.py` looks (`build/Raven`, or `build/Release/Raven.exe` on Windows), installs from there and runs the
install check and `run_all.py --nolib`. The simulation checks that `testconfig.RAVEN` in `check/` points there.

**F4 (S3): GWExternal.cpp SY comment.** Now: SY is kept as given also where it is 0 (as ICONVERT 0 cells often hold it)
and floored at 0.01 where Raven uses it, because a 0 cannot be told from an intended small value and MODFLOW stores only
S_s b in a confined cell, which a small S_y matches better than an assumed 0.2.

**F5 (S3): "0 for rivers Raven builds".** Now "normally 0" in `appendix.tex` and `inputs_outputs.tex`. `accounting.tex`
says when it is not: the loss is supply-limited by the channel's outflow at the start of the step, so a receding river
whose routed water falls short of that, or a reservoir gain MODFLOW does not supply (taken from the reach), leaves a
carry, taken the next step; the existing-model sentence stays. The contradictory "is zero ...; when not" is gone. The
FAQ says "Hardly from a river Raven builds" and names the receding-river rest.

**F6 (S4): leftovers.** `ParseGWFile.cpp` "as in v1" -> "AFTER: the whole exchange follows the processes";
`MF6Engine.h` V2a -> P1 (`test_water_table.py`, the storm test V2a became); `soilzone_unit.cpp` "plan §9.1 G1-G7" ->
"G1-G7"; `building.tex` "cut into cells as before" -> how the default grid cuts lines (pieces of at most a twentieth of
the cell size, each to the cell holding its middle, `GroundwaterModel.cpp`); `GWVadoseModel.cpp` "rejected as before"
-> "as on a link without columns". A further grep of every added code line against e7e2868 and of the extra tree
outside docs/design and docs/tutorials (`as in v[0-9]`, `\bv[0-9]\b`, `§`, `as before`, `V[0-9][a-j]`, `plan`,
`test_v2`, `earlier round/phase/build/code/version`, `before the change/fix`, `(case v`) found and fixed four more:
`CMakeLists.txt` "choose with --config as before" -> "take the configuration from --config"; `GWSoilZoneModel.cpp` "the
checks of the plan (section 3)" -> "the checks of the soil-zone set-up"; `GWSoilZoneStep.cpp` "booked as before
(MODFLOW's flow)" -> "booked as MODFLOW's flow"; `applying.tex` (twice) "run exactly as before" -> "as they do without
groundwater"; `exchanges.tex` "see the HRU as before" -> "see one soil store per HRU, as without the soil zone";
`test_inputs.py` "holds the column as before" -> "holds the column". The remaining hits are domain words (version pins
such as `@v1`, `v6.8.1`, "plan-view", loop variables `v0`/`v5`, the `('plan', ...)` case name of C1, a design-note file
name in a code comment).

**F7 (S4): `plot_soilzone.py` docstring.** Per HRU: the levels against the soil-zone base, and the exchange with the
connected fraction; model-wide from GWBudget.csv: the exchange, rejected recharge and overflow, the interface updates and
the last interface change (unconverged steps marked).

**F8 (S4): `edge.py` case prefixes.** E.., N.., P.. -> EE.. (existing-model example), EN.. (faulty set-ups), EP.. (valid
ones), 55 names; the docstring says so. `run_all.py` counts "k of n cases pass" only.

**F9 (S4).** tests/README "X1-X8" -> "X1-X9". User guide 4.5: a run without groundwater writes its HRU and channel
states with 5 decimals and reservoir stages and flows with 12 digits. Checksums: block 0-checksums runs in `handover/`
with `sha256sum -c`, or `shasum -a 256 -c` where there is no `sha256sum` (macOS).

**F10 (S4): byteid.py.** The .txt filter drops only lines that differ between two runs of one build: build date,
"HRU/grid linkage : computed in", "MODFLOW 6 files :" and "MODFLOW 6 library :" (the run's own paths), simulation and
elapsed times. "time steps ... unconverged" and Raven's time-series warnings are compared now.

**Results after the fixes.**
- **Binary.** The code changes are comments only (`GWExternal.cpp`, `ParseGWFile.cpp`, `MF6Engine.h`,
  `GWVadoseModel.cpp`, `GWSoilZoneModel.cpp`, `GWSoilZoneStep.cpp`; and `CMakeLists.txt`). The rebuild recompiled
  `RavenMain.cpp`, which holds `__DATE__`, so the new `Raven_p13.exe` (md5 `7ddfcc28ee4c9b990b06f8b2de52f5f9`) carries
  "Nov 10 2026" and another GNU build-id. `patches/bincmp.py` compares two executables with the build-id note removed
  and the date string masked (`patches/binary_review.log`): the new build = the tested pre-review build; the sources with
  the two output edits reversed = p12m; the new build != p12m (the two output edits).
- **Byte-identity** (`patches/byteid.py` with the narrower filter, `patches/byteid.log`): 0 comparisons with
  differences, the same notes as before (the summary header line in the RICHARDS and KINEMATIC cases; the three
  `gwf.swx` headers).
- **Kit** (`make_handover.py` into a fresh `wt/p13/handover_test/handover`, `patches/make_handover_test.log`): PASS, every
  block run as written ok; the public `mf6-coupling` read as e03243d, not an ancestor.
- **Simulation of HANDOVER.md** (`patches/sim_handover.py`, `patches/sim_handover.log`): every block run as written in a
  new bash, against local bare stand-ins (the real e03243d and e7e2868 fetched from GitHub): 40 checks, PASS. State A
  (the reported public state): 1A-check lists e03243d; 1A-push refused, nothing changed; 4-keep-push without `release`
  stops; 1A-replace makes the backup and replaces the branch; again: backup kept; 4-show in a new shell finds the commit
  on the backup; 4-keep (the squashed upload conflicts) stops with nothing pushed and the backup intact; 2-extra;
  3-verify PASS (1A) and refuses an existing `check/`; `testconfig.RAVEN` in `check/` is
  `check/RavenHydroFramework/build/Raven`; every branch kept. A2: a push between the block's read and its force push:
  refused ("stale info"), the other push kept. C: 1B-bundle and 1B-archive on the reported state: tree = kit, parent =
  e03243d, no force; refused when their folder exists; 2-extra-files; 3-verify PASS (1B). D: the archive block as it was
  before (without `-f`): the tree check stops it, nothing pushed. B: fast-forward. G: a fork commit of its own: 4-show,
  4-keep, 4-keep refusing an existing `release`, 4-keep-push (backup = the fork commit, lease), 3-verify FAIL before step
  2 (empty -extra) and PASS (step 4) after; the same after 1A-replace (4-keep-push a fast-forward, backup untouched). H:
  4-merge before and after 1A-replace (no force, the merge holds both).
- **run_all.py --quick --only** run_all_selftest, edge_nolib, edge, soilzone_inputs, soilzone_unit, soilzone_plot_tool:
  6 passed (`patches/run_all_review_steps.log`, step logs in `patches/run_all_review_logs/`); edge prints the EN/EE/EP
  names, 53 of 53.
- **Manual** (scratch copy): 173 pages, 0 warnings, 0 overfull boxes, 0 undefined references
  (`patches/manual_build.log`).

Not run here, as in the review: 3-build (CMake downloads MODFLOW 6) and a Windows or macOS run of the blocks.
