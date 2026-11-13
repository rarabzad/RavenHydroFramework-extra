# Audit A8, phase 21: manual, user guide, hand-over, commit messages, workshops and the release package

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees and committer dates,
under new IDs.*

Issues: CB8-2, SV8-1 (manual), MT8-1 to MT8-6, WS8-2 to WS8-4, IB8-7, and the README of the release package (findings
in `spec/audit_A8/F_CB.md`, `F_SV.md`, `F_MT.md`, `F_WS.md`, `F_IB.md`). Code unchanged in this phase. Extra on top of
`ea39c0a` (branch rb-p21-tests). The commit-message tool and the reviewed proposals are outside the repositories:
`tools/dev/neutral_messages.py` and `spec/neutral_messages_proposals.json` of the coordinator's folder. One step waits
for the phase-20 build: the workshops are regenerated with it (see the end).

## CB8-2 (S3) restart with a longer step after the inflows varied
Raven's `SetQinHist` averages a reach's inflow history to the new step, while the reach upstream books its first
outflow from its last stored outflow; the first step's balance error changes by ½·Δt·(Q̄ − Q_last) per reach whose
inflow varied, also without groundwater (−1.42 mm in CB's base-Raven case). In a coupled run takes on an upstream reach
make its outflow vary the same way (0.0711 mm, 0.5 → 1 d; 0.0092 mm, 0.25 → 1 d); the take itself is restored exactly.
- developers.tex, "Known issues in Raven itself": a new item with the mechanism and the numbers above; the
  `SetQinHist` item (partial rescale, read past the end) kept.
- accounting.tex (river takes): the `:GWRiverInflowTakes` paragraph now says the take is restored exactly, and that
  Raven's averaging of a downstream reach's inflow against the upstream reach's last outflow still changes Raven's
  balance error by its own amount (a known issue of Raven).
- user guide §4 (`:GWRiverInflowTakes`): the same narrowing, pointing to §9; §9 gains the item (below, MT8-1).
- verification.tex WB14: the test's reach is fed by a steady inflow; with takes upstream, Raven's averaging adds its
  own error (pointer to the known issues).
Not changed: `_sbInHist` is not extended to the downstream reach (CB's advice: it would compensate a base-Raven error
for one cause of unsteadiness only).

## SV8-1 (S3) the release cap of a rising water table (manual; the warning is phase 20's)
exchanges.tex said the S_y Δh limit "never binds" with S_y consistent with the retention curve. It now says when it
binds: at every rise with S_y well below the drainable porosity (the start-up warning), and with a consistent S_y
where the column carries water in transit above equilibrium (the LAG store, a RICHARDS wetting front) or the top cell
is nearly full; the column keeps the water for the next steps, no water is lost, Raven warns the first time in a run
(not with KINEMATIC). The user guide's column paragraph (§4.3) gains the same two sentences.
Workshop 3 Step 12: the explanation says the specific yields are not the cause and that the LAG store holds water in
transit. `build_tutorials.py` finds the release-cap warning by "more water above equilibrium" (in the old and in
phase 20's new wording) instead of "releases at most Sy dh per step" (only in the old); the excerpt's `grep` uses the
same text. The excerpt itself (`t3_warn_lag.txt`) changes when the workshops are regenerated with phase 20's build.

## MT8-1 (S3) the user guide's known issues
§9 "Known issues in Raven itself" now lists the restart with another `:TimeStep`: `SetQinHist`'s rescale over the
lateral-history length and its read past the end of the history (up to 2.2 mm in WB14's runs without the river), and
CB8-2's averaging mismatch. The restart paragraph of §4 points to it (with the `:GWRiverInflowTakes` text).
If phase 20 confirms with ASan that `SetQinHist` also *writes* past `_aQinHist`, the developers.tex item and this one
must say so (phase 20's finding; not changed here).

## MT8-2 (S4) the geometry table
- Values now the test's own (geomtest_check.py is deterministic): clipping 4.6e-12 (relative; was 1.3e-10),
  equal-area projection 6.7e-7 m (was 5e-7, which the test exceeds).
- The raster row describes the plane test (exact reproduction, 3.6e-15) and the no-data margin (a value 0.4 cell
  beyond the edge, none 0.6 beyond), not a no-data cell against independent code.
- New rows: the ten Albers and LCC cases against PROJ (worst 4.7e-7 m, also with the origin at either pole and false
  eastings); the 14 GeoJSON number files (invalid ones refused naming feature/ring/vertex or line/column; a feature
  without `"properties"` refused only where an ID is read).
- The gridtest paragraph names the grid-size stop check (cell size, refinement, HRU-mesh seeds, imported grid,
  existing model).
- The table had then grown 143 pt beyond a page ("Float too large"): it is split in two, `tab:geom` (geometry
  functions) and `tab:readers` (readers of the spatial inputs: GeoJSON, `"crs"` members, GeoTIFF, ESRI ASCII).
Values from MT's run `audit8/MT/geom_head.log` (HEAD, twice identical).

## MT8-3 (S4) three commit messages
`spec/neutral_messages_proposals.json`:
- code 3b9c778: "... pass-through steps for KINEMATIC and LAG" (the commit adds GWVadoseKW.cpp and GWVadoseLag.cpp with
  pass-through steps).
- extra 572a589: "test_restart.py (T2/T3, R2); cases X1-X7 of the extended column tests" (it changes test_restart.py
  and test_v2_ext.py).
- extra 48ee5c2: "Rough-terrain suite: test_rough_terrain.py on generated and existing-model cases", body
  "rough_models.py records the specified-head cells of each case." The auditor's proposal named rough_ext.py, which this
  commit does not change (d7b23f9 adds it; its message says so); the commit adds test_rough_terrain.py and one line of
  rough_models.py.
`tools/dev/neutral_messages.py`: PATTERN also flags `still to come` and `completed` (the docstring lists them). Scan of
all 211 messages for other progress words (still, yet, later, remaining, finished, done, TODO, stub, for now, now): only
change descriptions ("now books", "now stops"), which are neutral.
Before → after (`patches/mt8_3_*.log`): old tool on the old file: PASS; new tool on the old file: FAIL, the three
entries flagged; new tool on the new file: `check` PASS (83 + 128, all reviewed, subjects unique). `apply` into
scratch clones of bare copies (never on the repositories): PASS, 83 and 128 commits rewritten, tip trees identical,
34 upstream commits unchanged; no "still to come" or "completed" in the rewritten histories. The rewritten code tip
(1dbac97 in that rehearsal) keeps the committer time of 78d6c0b (1794575143).

## MT8-4 (S4) test_vz_initial.py
The VI1 skip branch for "not available in this build" (text no source writes any more) and its docstring sentence are
removed, with the `tc.skip` fallback only it used. The docstring now says what makes VI1 fail when the steady start is
missing (start storage 0, step-1 outflow below the inflow): the existing checks already require both.

## MT8-5 (S4) HANDOVER: branches
The sentence now reads: on GitHub nothing deletes a branch, and nothing changes a branch other than `mf6-coupling` of
RavenHydroFramework (and `mf6-coupling-before-release`, created only where it does not exist) and `main` of the new
-extra; step 4 creates the local branches `release` and `release-merge`, and the advice for running 4-keep again
deletes the local `release`. 4-keep now stops first when a 4-merge is unfinished (MERGE_HEAD), as 4-merge does for an
unfinished cherry-pick, instead of git's index error. The self-check runs 4-keep inside the unfinished 4-merge of its
rehearsal: "STOP: a merge (block 4-merge) is not finished", nothing pushed. Kit from the repositories in a scratch
folder (`--no-public-check`): PASS, 19 block runs (`patches/mt8_5_make_handover.log`).

## MT8-6 (S4) tests/README WB12
"every member equals the single run" → "every member's hydrographs, GWBudget.csv and Demands.csv equal the single
run's (Raven adds the rivulet storage again in each member, so WatershedStorage.csv differs there and in its total)".

## WS8-2 (S4) Workshop 1 budget columns
"... reservoirs and the soil zone have columns of their own. They are zero" → "... surface stores and reservoirs have
columns of their own. They are zero in this example. With the soil-zone coupling (Workshop 3), more columns follow."

## WS8-3 (S4) Workshop 1 model/start/README.md run time
`LIARD_README_HEAD` gives the time as `@FULLMIN@`; `liard_for_workshop` writes the committed `t1:fullmin` into it, and
after the 20-year run of a build `liard_readme_minutes` writes the measured value (as `readme_minutes` does for
README.txt). `--check` compares model/start with the committed files, so README.md must give the committed value.
The committed README.md now says 11 (= `t1:fullmin`, README.txt and the PDF).

## WS8-4 (S4) Workshop 5: the ensemble lines
Step 11's diff of `Creek.rvi` now starts from the ensemble's file (`udiff(rviE, rviP)`): it removes `:EnsembleMode` and
`:RandomSeed` and sets `:Duration` 365 (printed diff, two hunks; `patch -p0` applies it to the Step 9 state and gives
`model/finished/work/Creek.rvi`). The `\why` after Figure 1 no longer asks for a removal by hand ("The next step removes
the two lines ... again"); Step 11's text says the ensemble lines go. `tools/make_prt.py` (and the workshop's copy)
stops on an ensemble run's output folder (MonteCarloOutput.csv) with "... holds an ensemble run ...: remove
:EnsembleMode from the .rvi and run Raven again" instead of the step-count message; the trouble box names it. Test BF9
(budget_file.py): make_prt.py on a folder with MonteCarloOutput.csv and a real run's mf6/ must stop naming the ensemble
and `:EnsembleMode`, without a traceback or PRT files. The old make_prt.py gives "gwf.nam not found" on an empty mf6/
and, on a real ensemble's header-only mf6/, WS's step-count message (`patches/bf9_make_prt_old_new.log`).

## IB8-7 (S3) the commit the zips name
`build_tutorials.py --package` takes `--source-commit ID`, the commit bin/README.txt names; without it, the HEAD of
`--raven-src` (as before; a checkout is recognised only when `--raven-src` is its top level, not a folder inside another
repository). A given ID that the `--raven-src` checkout holds must have its HEAD's tree, else it stops. The release uses
`tools/make_package.py` (below), which passes the tip of the code it packages: after `neutral_messages.py apply`, the
rewritten commit, which keeps the tree and the committer date, so `build_release_raven.sh` gives the same Raven from it
(option 1A). Checked: `--package` with `--raven-src` = the rewritten code clone and `--source-commit 1dbac97`: the six
bin/README.txt name 1dbac97; `--source-commit d47888a` with the development checkout at 78d6c0b stops ("its tree
differs"). BIN_README_T's claim (the named commit gives the executable again, byte for byte) holds for 1A; the
release does 1A.

## The release package
- `tools/package_README.md`: the package README (contents, requirements, install check, quick start, workshops, build
  from source, tests, the restore section that `package_sources.py --update-readme` writes, known-issues pointer,
  licences), no process or history wording.
- `tools/make_package.py <pkg> --code <repo> --code-rev <rev> --raven <release Raven> --mf6 <libmf6.so>`: one command
  that assembles bin/ (Raven, libmf6.so, RavenMF6InstallCheck.py and LICENSE of the code revision, NOTICE-MODFLOW6.txt,
  VERSIONS.txt), the manual of the extra revision, its examples/, the six workshop zips (`build_tutorials.py --package
  --source-commit <code tip>`), source/ (`package_sources.py --update-readme`) and SHA256SUMS.txt, and checks it:
  package_sources (restore clones and manual), the install check, Raven's banner date against the code revision's
  committer date (the release recipe's date), the zips' programs and source commit, the README's file names and wording,
  and that the extra checkout is clean at the revision.
- Trial (`patches/package_make_rewritten_code.log`): with the rewritten code clone of the MT8-3 rehearsal (tip
  1dbac97), wt/rel18_release_glibc.exe and libmf6 6.8.1, 65 s, 227 MB: package_sources PASS (864 + 128 commits),
  install check PASS, banner date = commit date, six zips naming 1dbac97, 223 files summed. The only FAIL is the
  expected one: this worktree has uncommitted changes in tools/ and docs/tutorials/. The trial package was deleted.
- extra README's tool table and `neutral_messages.py`'s docstring name `make_package.py`.

## Checks in this phase
- Manual, in a scratch copy: the chapters build with no LaTeX warnings, overfull boxes or undefined references (after
  the table split); against the committed main.pdf 182 → 183 pages, 611 text lines differ (this phase's text: FAIL, as
  expected); after `--write` in the copy: PASS (`patches/manual_check_scratch.log`). main.pdf is rebuilt after the
  phase-20/21 merge.
- Workshops 1, 3 and 5: `tex/` compiled standalone in a scratch copy (pdflatex twice): 10, 12 and 10 pages (5 was 9),
  no LaTeX warnings or overfull boxes.
- `make_handover.py` self-check: PASS. `neutral_messages.py`: above. budget_file.py with rel18: below.
- Added lines outside docs/design: no history or audit wording (grep).

## With the phase-20 build (to do)
- Regenerate the workshops with the phase-20 build (`build_tutorials.py`, `--raven-src` the code worktree): expected
  changes `t3_warnings.txt` (WS8-1's ratio range), `t3_warn_lag.txt` (SV8-1's wording) and the regex for
  `t3:sylinks`/`t3:syratio` if the factor-2 warning's wording changes; run times; Workshop 5's PDF (new pagination).
  Then `--check --quick` with it, and the zips with `--source-commit`.
- If phase 20 changes the known-issue facts (`SetQinHist` write), update developers.tex and user guide §9.
- `check_manual_pdf.py --write` after the merge.
- `propose --reviewed` after the merges (the new merge commits need neutral messages).
