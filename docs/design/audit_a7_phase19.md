# Audit A7, phase 19: manual, hand-over, commit messages, release recipe and workshops

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Issues: MT7-1 to MT7-4, MT7-6 (text), MT7-7, IB7-6 = WS7-3, WS7-1, WS7-2, WS7-4 (findings in `spec/audit_A7/F_MT.md`,
`F_IB.md`, `F_WS.md`). Code unchanged in this phase. Extra on top of `6faea98` (branch rb-p19-tests). The commit-message
tool and the reviewed proposals are outside the repositories: `tools/dev/neutral_messages.py` and
`spec/neutral_messages_proposals.json` of the coordinator's folder. Two steps wait for the phase-18 build: the workshops
are regenerated with it, and `main.pdf` is rebuilt after phase 18 is merged (see the end).

## MT7-1 (S3) commit messages: git's conflict lists, process wording, line-ending conversions
`neutral_messages.py`:
- **Pattern widened** (used by `propose`, `check` and the `apply` verification): git's `# Conflicts:` list and notes of
  how conflicts were resolved ("Conflicts ... resolved"); wording that something was regenerated, revised, reviewed,
  brought up to date, taken out, left to fill or is "to be filled"; "first release"; "merged build"; build reports such as
  "built (130 pages". A new check flags every line that begins with `#` (git drops such lines with `--cleanup=strip`; a
  message written with `commit-tree` keeps them), and the rule-based proposals drop them.
- **Line-ending conversions**: `line_endings(repo, commit)` lists the files whose share of CRLF lines crosses one half
  between a commit and its parent (files of at least 10 lines; merges are not checked). Such a commit shows in
  `git log --stat` as a whole-file rewrite, so its message must say so (`CRLF` or "line endings"). `propose` records the
  conversions in the entry (`line_endings`), `check` recomputes them from the repositories when they are given (else it
  uses the recorded ones), and `apply` checks the rewritten commits the same way.

Messages (`patches/mt7_1_reviewed_messages.py`, which writes the reviewed file from `propose --reviewed`): 26 entries set
by hand.
- Line endings: the tool finds four code commits, not two: 10305bb and 8827517 convert GroundwaterModel.cpp/.h (and
  8827517 also ParseGWFile.cpp and ParseInitialConditionFile.cpp) from CRLF to LF, 7c88363 and f45fc94 back to CRLF as
  in base Raven. Each message now has a "Line endings:" paragraph naming the files and the direction (7c88363's subject
  said "CRLF line endings kept", which did not describe a conversion).
- `# Conflicts:` lists removed from c35d3da and 6faea98.
- Process wording reworded to what the commit changes: b181b24, d6709d1, 02d7112, b4f2b7a, cabcc41, 8b0cb80, 4a8ad69,
  24cf588, 3b36a8d, 06df6a6, d5974b3, 5e68ebf, 6dd98ee, fdfc2d7, 2f0b372 (extra); 17afed3 ("Following review"), 7c3de8e
  (code).
- The four commits added since the reviewed file: d47888a and 5f28962 kept; b78a078 "Tests and documentation: ..." (its
  subject was d47888a's); 6faea98 "Merge the manual PDF check, developer chapter, workshop text and release recipe".

Numbers (log: `patches/mt7_1_check_before.log`, `patches/mt7_1_neutral_messages.log`):
- Before: the old tool's `check` of the phase-17 reviewed file finds no wording problem (only the 1 + 3 commits added
  since). The new tool flags 21 reviewed entries in it: 3 line-ending commits, 1 `# Conflicts:` list (c35d3da), 17 with
  process wording.
- After: `propose --reviewed` on the current tips (code d47888a, extra 6faea98): 82 + 125 commits, 23 to edit (the 21,
  6faea98 and the repeated subject of b78a078). With the hand-set messages, `check` against the repositories: PASS
  (0 flagged, every subject unique, the file lists exactly the commits of both branches); every entry is marked
  reviewed. `apply` into scratch clones of bare copies of the repositories (never on the repositories): PASS, 82 and
  125 commits rewritten, tip trees identical, 34 upstream commits unchanged; `^#` lines in the rewritten histories: 0
  and 0.
- The coordinator runs `propose --reviewed` again after the phase-18/19 merges; the new merge commits then need
  "Merge <topic>" messages without git's conflict list.

## MT7-2 (S3) HANDOVER 4-keep: the advice for a second run fails
4-keep leaves branch `release` checked out, so the printed `git -C RavenHydroFramework branch -D release` always failed
("cannot delete branch 'release' used by worktree"). The STOP text now says: end an unfinished cherry-pick with
`git -C RavenHydroFramework cherry-pick --abort`, then
`git -C RavenHydroFramework checkout -q --detach && git -C RavenHydroFramework branch -D release`, and run the block
again. `make_handover.py`'s self-check now runs 4-keep again after the conflicting pick was aborted: it must stop with
"branch release exists", the printed command line must delete the branch (run as printed, rc 0), and 4-keep must then
start again (here: the same conflict, aborted again before the 4-merge steps). Kit made from the repositories in a
scratch folder (`--no-public-check`): PASS, the new step "run again: stops; the printed commands delete release; then it
starts again" ok. The old advice, run in a clone with `release` checked out: rc 1 with that error; the new one: rc 0
(`patches/mt7_2_make_handover.log`).

## MT7-3 (S3) "pull request" in the user guide and applying.tex
Both now use the wording of NOTICE.md and developers.tex: the coupling is offered to the Raven team for inclusion; until
it is part of Raven, use the `mf6-coupling` branch. No "pull request" is left outside docs/design (git grep).

## MT7-4 (S3) ensemble members and the rivulet storage
Checked with rel16 on WB12's models (`watershed_balance.py`, scratch work folder): of `WatershedStorage.csv` only
`Rivulet Storage [mm]` and `Total [mm]` differ between the single run and the members (0.410678 mm single, 2.05339 and
2.46407 mm for members 1 and 2, on every row, with and without groundwater and for all three routing methods); channel
storage and `MB Error` are equal. Base Raven gives the same values (below). The claim "member 1 equals the single run"
is narrowed in the user guide (section 7), accounting.tex (Ensembles) and the verification table to the hydrographs,
flows, groundwater books and Raven's balance error, and the rivulet storage is named as base Raven's (Raven adds it
again at every initialization). The known-issues item of developers.tex said "channel and rivulet storages"; it now
says rivulet storage (and the total) and that channel storage equals the single run's. The user guide's known issues
gain the same item.

## MT7-6 (S4) verification.tex, WB12 and WB13 (text; the test change is phase 18's)
- WB12: states the test's limits (no difference without groundwater, 1e-12 relative with it; observed 0), and that the
  byte identity of member 1 with base Raven's member 1 is a separate check, not WB12's. That check, repeated here with
  `audit/CB/Raven_base.exe` on the three no-groundwater ensembles of WB12: `Hydrographs.csv` and `WatershedStorage.csv`
  of member 1 identical for ROUTE_HYDROLOGIC, ROUTE_STORAGECOEFF and ROUTE_TVD (`patches/mt7_6_wb12_base_raven.log`).
- WB13: states the test's limit for the channel storage (1e-5 of the leakage, about 0.03 m3) beside the observed
  1e-11 m3.

## MT7-7 (S4) developers.tex: the EnKF change is in group (1)
The `EnKF.cpp/.h` row is marked (1): the change applies only to coupled runs.

## IB7-6 = WS7-3 (S3) the release executable is reproducible on any day
`build_release_raven.sh` sets `SOURCE_DATE_EPOCH` to the commit's committer time (`git log -1 --format=%ct COMMIT`),
which clang uses for `__DATE__`, and compiles RavenMain.o again. A second cause found here: zig keeps compiled objects
in its cache without regard to `SOURCE_DATE_EPOCH`, so a RavenMain object compiled with another date is taken from the
cache. The script therefore also passes the date as a macro, `-DRAVEN_SOURCE_DATE_EPOCH=...` (unused by Raven; it puts
the date into zig's cache key). The script header, `docs/tutorials/README.md` and the zips' `bin/README.txt`
(`BIN_README_T` and the six committed copies) say that the same commit gives the same executable, byte for byte, on any
day, the banner's date being the commit's.

Numbers (d47888a, zig 0.17.1; `patches/ib7_6_release_rebuild.log`; a build on another day simulated with
`SOURCE_DATE_EPOCH` = 20 Nov 2026 in the environment, which clang takes as the build time):
- old recipe, cold zig cache: sha256 011d4730..., 2 bytes differ from the shipped executable (the date);
- new recipe, the cache now holding that 20-Nov object: sha256 6884aaa2..., identical to the shipped executable
  (`wt/rel16_release_glibc.exe`, the zips' value), banner date Nov 13 2026 = the commit's date (13 Nov 2026 07:51 UTC);
- the old recipe with a warm cache gave 6884aaa2 too, which is how the cache hides the date: a test of this needs a
  cache that holds an object compiled with another date.

## WS7-1 (S3) Workshop 3: the third warning of the LAG and depth-class runs
- Step 9 now says what its values avoid: the warning at the start of the run that the specific yield and the drainable
  porosity differ (labelled `st:aquifer`).
- Step 12 (LAG) gives the number of warnings and shows the extra one (`t3_warn_lag.txt`, `grep "releases at most" out_lag/Raven_errors.txt`) and
  explains it: a rising water table met more water above equilibrium than MODFLOW stores for the rise (at most
  Sy dh, and no more than the room left in the top cell); the column keeps the rest and releases it in the next steps,
  no water is lost, once per run, and KINEMATIC does not write it. Step 13 says the depth-class run holds the same
  warnings with RICHARDS.
- `build_tutorials.py` counts the warnings of `out_richards`, `out_kinematic`, `out_lag` and `out_classes` and the
  release-cap warnings among them, writes `t3:nwarnLag` and `t3:nwarnClasses`, and stops with "make them agree" unless
  RICHARDS and KINEMATIC have the PHYSICAL run's warnings, and LAG and the depth classes one more, the release cap,
  naming LAG and RICHARDS.

## WS7-2 (S4) Workshop 6: one calibration time
`readme_minutes()` no longer accepts a difference: a build writes the generated value (the number the PDF prints) into
the hand-written README.txt, and `--check` requires README.txt's number to equal the committed value exactly. The
README now says 28 minutes, as the PDF (`t6:ddsmin`); Workshop 1's README and `t1:fullmin` both say 10.

## WS7-4 (S4) `diff -rq` in Workshops 2 and 5
The expected output names the pictures the plotting scripts wrote into `work/`: `hydrograph.png` (Workshop 2, Step 20)
and `ensemble.png` (Workshop 5, "The finished state").

## Checks in this phase
- Workshop 3 built with rel16 in a scratch copy of this branch (`build_tutorials.py --only t3`, 3 min): the new count
  passes (warnings: PHYSICAL 2, RICHARDS 2, KINEMATIC 2, LAG 3, depth classes 3; the release cap once each in LAG and
  the depth classes, naming LAG and RICHARDS); `t3:nwarnLag` = `t3:nwarnClasses` = 3; `t3_warn_lag.txt` holds the
  warning line. The first wording of Step 12 gave an overfull box (4.8 pt); reworded, the PDF compiles clean (12
  pages). Log: `patches/ws7_1_w3_build_rel16.log`. The scratch copy was deleted; nothing generated is committed.
- Manual, in a scratch copy of this branch: `check_manual_pdf.py` builds the chapters with no LaTeX warnings, overfull
  boxes or undefined references; against the committed main.pdf 180 = 180 pages and 117 text lines differ (this
  phase's text: FAIL, as expected); after `--write` in the copy: PASS (`patches/manual_check_scratch.log`).
- `make_handover.py` self-check (kit from the repositories, scratch): PASS. `neutral_messages.py`: above.
- Added lines outside docs/design: no history or audit wording (grep).

## With the phase-18 build (merge of rb-p19-tests on 94450cc; code 78d6c0b, wt/rel18_Raven.exe)
- verification.tex WB14: the five chains of phase 18's final test (with the one-step middle parts 0.1, 0.2, 1 d and 1,
  0.2, 1 d), the comparison with the same runs without the river (the test allows 1e-6 mm; observed up to 5.7e-14 mm;
  Raven's own error in the runs without the river up to 2.2 mm), the leakage limit (0.5 m3 plus 1e-5 of the leakage) and
  the restart from a file of RAVEN_EXE_REF (0.01742 mm in both). watershed_balance with rel18 and RAVEN_EXE_REF = rel16:
  14 of 14.
- Workshops regenerated with rel18 (`--raven-src` the code repository; full build without OSTRICH, 18 min): only run
  times changed (`t1:fullmin` 10 -> 11, written into Workshop 1's README.txt by `readme_minutes`, and seven other
  measured times); no workshop 6 number changed, so the DDS was not rerun. New: `t3:nwarnLag` = `t3:nwarnClasses` = 3,
  `t3_warn_lag.txt`.
- Release executable from 78d6c0b with the recipe of this phase: `wt/rel18_release_glibc.exe`, sha256 c7105495...,
  glibc 2.16 at most, banner date Nov 13 2026 (the commit's). Its outputs equal rel18's: `watershed_balance.py` run with
  each, 791 CSV and .rvc files under out*/ identical byte for byte; `tutorials_check.py` (quick) with it: PASS, 377
  values, 105 excerpts, the six texts compile (385 s).
- Zips: `build_tutorials.py --package wt/ws/zips_final` with that executable (the six zips replaced).
- Manual: `check_manual_pdf.py --write` (180 -> 182 pages), then PASS.
- Commit messages: `propose --reviewed` on code 78d6c0b and extra 94450cc: 83 + 126 commits, one repeated subject
  (78d6c0b and 94450cc); 94450cc becomes "Tests and documentation: ...", 58954ca (this phase, on a branch until the merge
  is committed) gets "Hand-over step 4 rerun advice; ..." (its subject named the commit-message checks, which live
  outside the repository, and "recovery"). The merge's message must avoid "revisions" and "recovery" (both flagged).
- Tests with rel18: tools_check ALL PASSED, watershed_balance 14 of 14, geotiff_check ALL PASSED, geomtest_check ALL
  PASSED (built from the code repository's sources in a scratch folder), tutorials_check PASS.
