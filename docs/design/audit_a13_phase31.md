# Audit A13, Phase 31: Workshop 3 text, history tool, hand-over note, figure scripts, message rows

Issues: SV13-1 (= WS13-1, the Workshop 3 text), MT13-1, MT13-2, MT13-3, MT13-4. Base: code soil-zone 56e385b (unchanged
here), extra soil-zone d2eb5f3. Outside the repositories: /home/claude/rebuild/tools/dev/neutral_trees.py. Still to do after
Phase 30 is merged: message rows for Phase 30's new stops, main.pdf, and the workshops regenerated with the Phase 30 build.

## SV13-1: Workshop 3, Step 13 (depth classes)

The classes run's third warning is the room form ("than the room left in the top cell above the water table ..."), not
the Sy dh form of the LAG run. 07_vadose.tex now quotes it as a generated excerpt, `t3_warn_classes.txt` (`grep "more water
above equilibrium" out_classes/Raven_errors.txt`, written by build_tutorials.py next to `t3_warn_lag.txt`), and says that
it names the other limit: the room left in the top cell is less than Sy dh, the column releases at most that room per
step and the rest in the next steps, no water is lost. Step 12 got the label `st:lag`.
- The excerpt in the tree was made by running `model/finished` with rel28 (50 s, 3 warnings); `--check` and the
  regeneration with the Phase 30 build rewrite it.
- The generator guard on which limit each warning names (LAG: "than MODFLOW stores for the rise"; classes: "than the room
  left") is Phase 30's (the new `G.text` line sits one line below it, so the two hunks merge).
- W3 tex compiled in a scratch copy: 13 pages, no warning, no overfull or underfull box.

## MT13-1: change-history wording in older commits

neutral_trees.py:
- HIST_RULES (applied before TEXT_RULES, on the notes' own wording): each change note of the older extra and code commits
  is taken out whole, or its sentence is said without it, for example:
  - "Before audit A1 the columns started ... a start-up pulse." and "(Before audit A1 the discharge ... B8.)": dropped;
  - "(an uncaught exception before audit A1)", "(... created before audit round 8)", "(round-off decided whether classes
    applied before audit round 2)", "(before audit round N: ...)": dropped;
  - "overflowed the integer before v3 audit round 1)" -> "would overflow an integer)";
  - "the build before the classes / before LAG" -> "a build without the classes / without LAG";
  - "byte for byte with the previous version." -> "with a build without your change (RAVEN_EXE_REF)." (the tip's words);
  - the MODFLOW 6.6.3 paragraph ("first failed ... Raven now writes NEWTON alone ... identical byte for byte") -> the
    tip's paragraph;
  - "the ages now continue" -> "the ages continue"; "(checked again after audit A1 on" -> "(checked on";
  - test_interface_stiff.py: the sentences on the commits that brought the report line ("came with bbab5ef ... before and
    after the round-3 fix", "came with the fix (bbab5ef) ... builds before bbab5ef ... with the fix's cap line reverted"),
    "on bbab5ef", "0 with 105c54b", "(the earlier code: 38 to 219)", "before audit round 10 the residual stayed ...",
    "(builds before audit round 10 ...)", "The warning used to give ...";
  - test_robustness "(late updates used to leave ...)", test_rough_terrain "(the columns used to inject ...)" and "(g350_LAG
    removed: fixed, regression R19)", sz_check "or an older build", test_mf6_budget "before audit A1 \"...\"", R15b "117.47
    before the fix".
- The tool's own substitution "before audit A1" -> "before the change" is gone: such a clause is now taken out whole (the
  known ones have HIST_RULES of their own). The self-test checks every replacement string of every rule against the final
  check, so no rule writes change or process wording.
- Commit IDs: a text of an older commit that cites a rewritten commit gets the commit's final ID (IdMap: original ID ->
  ID after apply, from id_map.tsv -> final ID, filled as the commits are rewritten; e.g. the tutorials' REQUIRES and
  README "5f042ff"/"c1c5839" -> the final IDs). An ID that names no commit of the published history stays flagged.
- FINAL_RE also holds: before/after/since/until/with/of/by the change|fix (not "the change of|in"), "the fix", "fix's",
  "builds before/after", "earlier/older code|builds", "an older build", "used to leave|inject|give|..." (not after is,
  are, be, was, were or a colon), "now writes|reports|continues|...", "previous version|build|code", "removed: fixed",
  "was fixed in", and commit IDs (7 to 12 lower-case hex digits with a letter and a digit, not part of a number); an ID
  passes only when it is a commit of the published history (PUBLISHED, filled after each repository is rewritten).
  ALLOW: "rest of the change", "the build after it", "the problem and the fix", "the build before a change", "prompt now
  starts", e03243d (the public commit the kit names).
- Self-test: 64 text cases, 40 final-check cases, the repository case (with a cited commit ID mapped to its new ID): PASS.

Rehearsal on throwaway clones (wt/p31/hist: `git clone --no-local` of soil-zone, then apply, then run):
- neutral_messages apply: PASS (13 s; code 56e385b -> 7b15fbe, extra d2eb5f3 -> 7d4461e).
- neutral_trees run: PASS in 3 min 40 s. code 90 commits -> 8ab6cda, extra 147 commits -> b64679c. Tip trees identical
  (code ab87522, extra 794f59e). Query 0, wide 0, final check 0 lines, 0 names, 0 binaries, 0 tip lines.
- extra: 7 files dropped (4 before: the three reports and main.pdf), 30 renamed. The three new drops are binaries of older
  commits whose text cites commit 5f042ff, which the rewrite replaces: Raven_MF6_Tutorial_Files.zip,
  Raven_MF6_Tutorials.pdf, Tutorial1_Getting_started.pdf (the tip's files are kept as they are).
- `git log -S` over the rewritten extra branch, outside docs/design: no commit adds or removes "before the change",
  "after the fix", "used to leave", "now writes", "previous version" or "bbab5ef"; "build before" only in the tip's own
  "the build before a change".
- make_handover.py on the rehearsal clones (with the public check): PASS in 1 min 5 s.

## MT13-2: the open pull request #1

make_handover.py:
- KNOWN_PULLS and `pull_note()`: HANDOVER.md, under the state of the public repositories, has a paragraph "Pull request
  #1": open, from mf6-coupling into main, opened 2026-09-30 with e03243d; its public description tells how the coupling
  was developed and checked, names the Raven versions it was built on, and describes a layout the kit does not have;
  every route updates it; after publishing, edit its description or close it; its timeline keeps a link to e03243d, so
  GitHub keeps that commit even after 1A-replace-local, and removing it needs GitHub support.
- The 1A-replace paragraph says that an open pull request on the branch keeps referring to the replaced commit.
- The public check also lists `refs/pull/*/head` of the code repository (read only); a pull request KNOWN_PULLS does not
  describe is reported with "read it on GitHub before publishing".
- tools_check.py TC7: the paragraph is written for the code branch (with what to do and GitHub support) and not for
  another branch. tools_check: PASS.
- Checked read only: PR #1 is open, head e03243d, base main.

## MT13-3: figure scripts

make_figures.py (MODEL BASE PUMP DRY CALIB), make_tables.py (the nine run folders in the table's order) and
make_plain_figures.py (CELLS HRUS RVH) take their inputs as arguments, each documented in the script's docstring, which
they print when called without them. No development folder is left in the tip outside docs/design.

## MT13-4: message rows

appendix.tex (error messages) and the user guide's message table: the time-series file named by a path Raven cannot
rewrite (in an OPEN/CLOSE file of its OPTIONS); a package file in a folder of the simulation that holds Raven's output
folder (-o outside the simulation's folders); a BEGIN PERIOD number that is not a whole number of at least 1. The manual
builds in a scratch copy (check_manual_pdf: builds, 196 pages; main.pdf is not rebuilt here, since Phase 30 changes the
manual too).

## Tests

- neutral_trees --self-test: PASS. Rehearsal: PASS (above).
- neutral_messages check (source clones): PASS, 90 + 147 commits, 0 flagged.
- tools_check.py: PASS (TC7 with the new check).
- Manual: builds in a scratch copy. Workshop 3: compiles in a scratch copy.
