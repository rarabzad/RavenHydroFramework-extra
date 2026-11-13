# Audit A6, phase 17: manual, hand-over, commit messages and workshops

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Issues: MT6-1 to MT6-6, IB6-6, WS6-1 to WS6-14 (findings in `spec/audit_A6/F_MT.md`, `F_IB.md`, `F_WS.md`). Code
unchanged in this phase. Extra on top of `b181b24` (branch rb-p17-tests). The commit-message tool and the reviewed
proposals are outside the repositories: `tools/dev/neutral_messages.py` and `spec/neutral_messages_proposals.json` of the
coordinator's folder. Two steps wait for the phase-16 build: the workshops are regenerated with it, and `main.pdf` is
rebuilt after phase 16 is merged (see the end).

## MT6-1 (S2) the committed manual PDF is stale
New `tools/check_manual_pdf.py`: builds the manual from `docs/manual` in a scratch folder (`latexmk -pdf`, or pdflatex,
bibtex, pdflatex twice; SOURCE_DATE_EPOCH set) and compares the `pdftotext -layout` text (whitespace collapsed) and the
page count of `main.pdf` with the build. A build with LaTeX warnings, overfull boxes or undefined references fails on its
own. `--rev REV` checks a commit (git archive), `--write` replaces a stale PDF of the working tree. Text, not bytes, is
compared: a PDF holds font subsets and IDs that differ between otherwise equal builds.

`tools/package_sources.py` runs it on the extra revision it packages (`--no-manual-check` skips it) and, when the package
folder holds `Raven_MF6_Manual.pdf`, checks that it is that revision's `main.pdf` byte for byte. Its final line reads
"package check (manual PDF, README ... restore section)".

Numbers: `check_manual_pdf.py --rev HEAD` (b181b24): main.pdf 174 pages, the build of the chapters 179, 1,774 text lines
differ: FAIL (19 s). On a copy of this branch's `docs/manual` after `--write`: 179 pages, PASS. `package_sources.py` on
the real repositories (scratch package, local upstream stand-in) prints that FAIL and fails the package; the copy
`Raven_MF6_Manual.pdf` (= HEAD's main.pdf) is recognised. Test: `tools_check.py` TC8 on a two-chapter stand-in manual:
a PDF built from its chapters passes, a changed chapter fails with the changed line shown, `--write` replaces the PDF and
it passes again (needs pdflatex and pdftotext, else SKIP; 3 checks, ok). The reference tree has no such check.

`main.pdf` itself is not rebuilt here: the phase-16 merge changes chapters too. After that merge:
`python3 tools/check_manual_pdf.py --write`, then `python3 tools/check_manual_pdf.py` must PASS.

## MT6-2 (S3), MT6-3 (S4) the commit-message tool
`neutral_messages.py` (coordinator's `tools/dev/`):
- **Pattern widened**, so `propose`, the new `check` and the `apply` verification all use it: process wording (`WIP`,
  coordinator, usage-limit, work in progress, draft, pending, placeholder), branch names `rb-*`, `phase A`/`phase B`,
  `Integ`, `Merge3`, `_v2`/`v3build` and `v3h`, `MT-4`, finding prefixes WS and SV, and wording about earlier states
  (`rebuilt`, `recovered`, `reconstructed`, `history`, first full version, final form, final audited, honest, no longer,
  previously, not rebuilt). Word boundaries keep `PREBUILT`, `tools_audit`, routing `histories` and "root finding" out.
- **Form checks** (`problems()`): empty brackets `()` / `(, )`, a subject that begins with a bracket or a preposition
  ("In the manual ..."), ends in a dangling word ("docs for", "timing after") or says nothing ("Soil zone: fixes").
- **Repeated subjects**: `duplicates()`; `apply` fails when two commits would carry one subject (unless
  `--allow-flagged`).
- **MT6-3**: a message with no wording and a good form is proposed exactly as it is; rule proposals strip only spaces,
  `;` and `,` (a leading `:` of a command stays) and upper-case only a plain word (`sz_check:`, `test_vz_classes.py`,
  `tests/cmake_checks.py:` keep their case). In `apply` a kept message keeps its bytes and its encoding line.
- **`propose --reviewed FILE`** keeps the reviewed message of every commit the file lists and proposes only for commits
  added since: the way to extend the reviewed file to the release revision (the merges of phases 16 and 17 and anything
  after). **`check --proposal FILE [repos]`** reports what is left to edit, and with the repositories whether the file
  lists exactly their commits.

Reviewed proposals: `spec/neutral_messages_proposals.json`, 203 entries (code 81, extra 122, tips 3cd5346 and b181b24),
each marked `reviewed`. 48 messages are kept byte for byte; 155 are rewritten by hand, each from `git show --stat` (and,
for the soil-zone commits whose old message named only an audit round, from the comments their diff adds). Merges read
"Merge <topic>". Pairs of code and extra commits that carried one subject now differ ("Tests and documentation: ...");
the twelve "Soil zone: fixes" and seven "Soil-zone fixes" now name their changes; the first commit's body names the
RavenHydroFramework-extra repository instead of an unrelated URL and no longer cites the old Raven revision label.
The generator of the file (`patches/mt6_2_reviewed_messages.py`, `mt6_2_build_proposals.py`) is kept with the patches.

Numbers (old tool -> new): `propose` on the real repositories: wording found in 44 + 58 messages -> 59 + 88 (with form
problems); of the auditor's 61 unflagged proposals 49 are now flagged and the other 12 are bodies with "now", the false
`PREBUILT` hit, or repeated subjects (caught by `duplicates()`: 14 repeated subjects in the old proposals). Reviewed file:
`check` PASS (0 flagged, 0 repeated subjects, the file lists exactly the commits of both branches). `apply` into scratch
bare clones of the real repositories (never on the repositories): PASS, 81 and 122 commits rewritten, tip trees identical,
34 upstream commits unchanged; 48 kept messages identical in bytes, 155 rewritten as proposed. With a commit "Merge
rb-p16" added to the scratch clone, `check` reports the commit missing (FAIL) and `propose --reviewed` keeps all 203
reviewed messages and flags only the new one. Log: `patches/mt6_2_neutral_messages_test.log`.

## MT6-4 (S3) developer chapter: pull-request branches
`developers.tex` § "Changes to existing Raven files": the five groups are described by what they change, all held by the
branch `mf6-coupling`; the four groups other than the coupling are said to change Raven also in runs without
groundwater. The branch names, "offered as a pull request" and "merge cleanly in any order" are gone; the table caption
says "group in brackets". § "Where things live": "The branch `mf6-coupling` ... holds them all". The repository's
`NOTICE.md` (and the workshop's notice) name the branch instead of "pull requests".

## MT6-5 (S4) small mismatches
- `developers.tex`, `ParseInitialConditionFile.cpp` row: `:GWStartHeads` and `:GWRiverTake` added (the code reads both).
- `verification.tex` WB10: "the test allows 10^-5 of the loss taken, 0.065 m³ for Muskingum; the run ends 0.007 m³
  apart" instead of "within 0.01 m³" (the limit is the test's; tightening it was not chosen, as the other routing methods'
  end values were not all measured).
- `watershed_balance.py` docstring: WB9 before WB10 and WB11 ("the same reach" now follows WB8).

## MT6-6 (S4) hand-over text and cited commit IDs
- `make_handover.py` docstring: the sentence that rewriting history would give commits that do not match is replaced by:
  give the repositories exactly as they are to be published; when their commit messages are edited before publishing,
  edit them in new clones (trees, authors and dates kept) and give those; the IDs that docs/design cites are those of
  the development repositories, as each record says.
- The twelve records in `docs/design` that cite commit IDs (`audit_a1_phase3`, `audit_a2_phase4`, `audit_a2_phase5`,
  `audit_a3_phase10`, `audit_a4_phase13`, `audit_a5_phase15`, `defects_d1_d3`, `doc_phase6`, `mf6_build`,
  `rebuild_core_v1`, `rebuild_v2`, `rebuild_v3h`) and this one start with a note that the IDs are those of the development
  repositories and that base Raven's IDs (e7e2868 and ancestors) and public commits keep theirs. The IDs themselves are
  left as they are (rewriting them in the tree was the alternative; it changes the trees and was not chosen).

## IB6-6 (S4) release recipe: zig pin and flags
`build_release_raven.sh`: `ZIG_VERSION=0.17.1` (the version the zips were built with, found in the build folder's
`ziglang-0.17.1.dist-info`; the auditor reproduced the shipped binary with it). A zig of that version on the PATH is
used, otherwise `pip install ziglang==0.17.1` into BUILD_DIR; another version stops the script. The header describes the
flags as the script's own and says that the repository's builds differ (CMake Release -O3 -DNDEBUG; the Makefile sets
no optimisation). `bin/README.txt` of the zips names zig 0.17.1 (read from the script by `build_tutorials.py`) and says
that the script with it gives the executable again from the listed commit. The tutorials README names the script.
`bash -n` passes; the recipe was not rerun (it would rebuild the release binary).

## Workshops (WS6-1 to WS6-14)
| Issue | Change |
|---|---|
| WS6-1 | W2 Step 7 box: the AQUIFER_PROFILE case moved out of "Raven stops when"; Raven warns, the water leaves the model; the message's real start quoted; `grep WARNING out/Raven_errors.txt` |
| WS6-2 | W4 Step 7 box: the four messages quoted as Raven prints them (fragments checked against `GWExternal.cpp` lines 174, 283, 290, 1074) |
| WS6-3 | W2 Step 16: "two places" (GHB and well; DEEP_STORE); storage release described as a source that makes up part of what they take. The build now stops if GHB + well + DEEP_STORE no longer exceed the drop or the release is not positive |
| WS6-4 | `t1_ls_ws.txt` lists `bin/` from `BIN_FILES`, the same tuple `--package` writes (`LICENSE-Raven.txt NOTICE-MODFLOW6.txt README.txt Raven libmf6.so`); W1 Step 1 names the licences and the README |
| WS6-5 | `preamble.tex`: the terminal style breaks lines only at spaces (`breakatwhitespace=true`), so `--year 2011` and `--hrus 7 6` move whole to the next line |
| WS6-6 | the FloPy snippet, the GLIBC message (six workshops) and the pandas message use `\textquotesingle`: they copy as `'` |
| WS6-7 | W3: "lies on average 4.5 m deeper" (the value is the mean) |
| WS6-8 | `preamble.tex`: a section heading needs 16 lines below it, a step heading 10 |
| WS6-9 | W6 README: 25 minutes, as the PDF; the build compares the README's run times of W1 and W6 with the generated values (30 %, at least 5 minutes) |
| WS6-10 | W1 `model/start/NOTICE.md` is written for the zip (`WS1_NOTICE`: bin/Raven, bin/libmf6.so, scripts, texts, Liard inputs, with paths of the workshop folder); the copied Liard README says `out/mf6/` (the build stops if `output/` remains) |
| WS6-11 | tutorials README: "Each workshop is its own PDF and its own zip; there is no combined PDF or zip." |
| WS6-12 | `--check --no-pdf` ends "the texts were not compiled (--no-pdf)" |
| WS6-13 | W5 Step 10: the groundwater files and `mf6/` directly in `out_ens` come from the set-up and hold no results; use `ens_N` |
| WS6-14 | W5 Figure caption: each particle moves 51 to 68 m from its release point |

Checks with the current sources (scratch copies, new `preamble.tex`; `patches/ws_compile_check.py`): all six `tex/`
compile with no LaTeX warnings or overfull boxes (W1 10, W2 18, W3 12, W4 13, W5 9, W6 14 pages; before 10, 17, 11,
13, 9, 13); headings at the bottom of a page: none (before: W1 p. 9, W4 p. 11, W6 p. 2, found by the same script); `$`
lines broken inside a word when copied (`pdftotext -raw`): 0 (before 2); the FloPy snippet copies as
`HeadFile('out/mf6/gwf.hds')`. `build_tutorials.py --check --quick` with rel14 (393 s): all 375 values and 103 of
104 excerpts match; the only differences are the generated files this phase changes on purpose (`t1_ls_ws.txt` with the
two licence files, W1 `model/start/NOTICE.md` and `README.md` with `out/mf6/`, the six `tex/preamble.tex` copies and
`bin/README.txt` with zig 0.17.1). They are written when the workshops are regenerated with the phase-16 build.

## Waiting for the phase-16 build
1. Workshops: `python3 build_tutorials.py --raven <phase-16 Raven> --mf6 libmf6.so --raven-src <code> --quick` (or the
   full build), then `--check --quick` PASS, then the zips with the release binary built by `build_release_raven.sh`.
2. Manual: after the phase-16 merge, `tools/check_manual_pdf.py --write` and a PASS run; the package's
   `Raven_MF6_Manual.pdf` copied from the new `main.pdf`.
3. Commit messages, at release: `neutral_messages.py propose <code> <extra> --reviewed spec/neutral_messages_proposals.json
   --out release.json`, review the new entries (merges "Merge <topic>"), `check --proposal release.json <code> <extra>`,
   then `apply` into a new folder and `make_handover.py` on the rewritten clones.
