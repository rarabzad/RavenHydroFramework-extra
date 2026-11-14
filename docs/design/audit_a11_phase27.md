# Audit A11, Phase 27: documentation, workshops, commit messages and the history-cleaning tool

Issues: SV11-1, SV11-2 (documentation), MT11-1, MT11-2, MT11-4, MT11-5, WS11-1 to WS11-5 and MT11-3 (option (c), the
tool). The code side of SV11-2 (the KINEMATIC warning), MT11-6 (renaming the test A1) and the rest of A11 are Phase 26.

## SV11-1: the condition under which the release limit binds
- `exchanges.tex` and the user guide (section 4) now state the condition with both limits: the limit binds when a
  rising water table meets more water above equilibrium in the band it crosses than the smaller of Sy dh and the room
  the top cell has left. The list of causes is kept. Phase 26 changes the code comment in `GWVadoseModel.cpp`.

## SV11-2: the room limit under KINEMATIC
- `sz_vadose_kinematic.tex`: the release of a rising water table is never more than the integral of Sy over the rise,
  but in one step it is at most the room the top cell has left. A nearly full top cell can hold part of it back, and the
  column then releases it in the next steps, with a warning the first time in a run. The Sy dh limit never binds.
- `exchanges.tex`: the "(not with KINEMATIC ...)" exception is gone. With KINEMATIC only the room can hold the release
  back, and its warning names that room. This matches Phase 26's warning ("... than the room left in the top cell above
  the water table; the column releases at most that room per step ...").
- The user guide says the same.

## MT11-1 and MT11-2: the verification chapter
- The input-check list is "N1--N28, U0--U4, RN1--RN2, E1--E23, AM1". **AM1** is the new name of A1. Phase 26 must use
  the same name in `tests/input_checks.py` and `tests/README.md` (MT11-6).
- A new table, `tab:faultyext`, holds:
  - OPEN/CLOSE in the name files (E13-E15, E19-E21);
  - the balance-error warning (E16);
  - the `:OverlapWeights` limits (E17, E18, E22, E23);
  - the antimeridian model (AM1).

  It is a separate table because these rows made `tab:faultynum` too tall for a page.
- `tab:geom`: 16 conic cases, including longitudes written beyond ±180° and the apex of a southern cone.
- `tab:geojson`: the three new shapes without area (an outline on one line, a square traced out and back, a figure
  eight), and the reason text.
- The ensemble paragraph says that the channel storage (WatershedStorage.csv and `:ChannelStorage`) is compared, with
  difference 0. The rivulet storage and the total are not compared. `developers.tex`: the ModelInitialize.cpp row lists
  the channel storage.
- Phase 26 adds tests: OPEN/CLOSE in every MODFLOW text reader, the time-unit guard, CSUB, and the band units through
  aux.xml. Their verification rows are to be added when the two phases are merged (listed under "Open").

## MT11-5: message rows
- Appendix:
  - the "no polygon" row also covers a polygon without area ("fix its outline");
  - a new row "grid cell ... of ... has no area";
  - the out-of-range row is now its own row for the `ParseGWFile` message. It covers IDs and cell numbers of
    `:OverlapWeights`, `:Wells` and `:MonitoringWells`. Its wording follows Phase 26's form, "the <role> '...' is out of
    range";
  - the `:HRUGeometry` command row says that a feature without area is left out, and that this stops the run only for
    an HRU the model couples.
- The user guide (the command table and section 8) and `applying.tex` have the same rows.

## MT11-4: proposed commit messages
These are edited in `spec/neutral_messages_proposals.json` (outside the repositories):
- 1239d54: the subject no longer claims tests of the two-way package check. The body notes that no test input reaches
  that stop, and lists the user guide, verification and tests/README changes.
- 5c09535: adds the known-issue count (22 of the 65 subbasins) and the examples/README folder name.
- 981da06: names the ID range stop for `:Wells` and `:MonitoringWells`, and the comment in GWVadoseModel.cpp.

`neutral_messages.py check`: PASS (86 + 139 commits, 0 flagged, every subject unique).

## Workshops (sources; the outputs are regenerated with the Phase 26 build)
- **WS11-1:** `scripts/plot_gw.py` labels the column "recharge received by MODFLOW". The copy is in W1, W2, W4 and W5.
- **WS11-2:** the new macro `\msg` sets a message Raven prints in typewriter type. Its spaces stretch at most by half,
  so a justified line no longer spreads "Exiting Gracefully: Successful Simulation".
  - All 21 occurrences in the six workshops use it.
  - `\cmd` is unchanged: fixed spaces in every `\cmd`, tried first, gave badly underfull lines elsewhere.
  - A trial build of the six PDFs in a scratch copy, with the committed numbers, had no warnings and no overfull boxes.
    It had one underfull line, of badness 1122, in W3 Step 13. That line moves when the run times are regenerated.
- **WS11-3:** W5 Step 10: "hold no results: the CSV files have their header (GWHeads.csv also the initial heads at
  t = 0)".
- **WS11-4:** the W6 README asks for the OSTRICH export line of Step 2 in every new terminal. The folder map names
  work/ with best/, model/output/ and validation/.
- **WS11-5:** `plot_tracks.py` sets `sys.dont_write_bytecode` before it imports plot_gw. Checked: no `__pycache__` is
  left.

## MT11-3, option (c): the history-cleaning tool
`/home/claude/rebuild/tools/dev/neutral_trees.py` sits beside `neutral_messages.py` (outside the repositories). The
release command sequence becomes:

    python3 neutral_messages.py apply <code> <extra> --proposal neutral_messages_proposals.json --dest <dest>
    python3 neutral_trees.py run <dest>/code <dest>/extra
    python3 <dest>/extra/tools/make_handover.py <dest>/code <dest>/extra --code-rev soil-zone --extra-rev soil-zone ...
    python3 <dest>/extra/tools/make_package.py <package> --code <dest>/code --code-rev soil-zone ...

Neither make_handover.py nor package_sources.py needs a new step. They take the clones as given. The one sentence of
make_handover.py's docstring that said every commit keeps its tree now says that the tip keeps its tree.

### What the tool does
- **Which commits:** the same as neutral_messages.py. In the code repository, the commits not reachable from base
  Raven (e7e2868), whose upstream commits keep their IDs. In the extra repository, every commit.
- **What changes:** each commit object is the old one with a new tree and mapped parents. Author, committer, dates,
  encoding and message keep their exact bytes.
- **Files outside docs/design:**
  - report files are dropped: `docs/AUDIT_REPORT.md` and `docs/VERIFICATION_REPORT_MF6.{6.3,8.1}.md`;
  - versioned or audit-named files are renamed, the same way in every commit, and so are their mentions in text:
    - `ch8_sz_v1` → `ch8_sz_columns`, `ch8_sz_v3` → `ch8_sz_interface`, `ch5_sz_v3` → `ch5_sz_books`;
    - `appendix_sz_v3` → `appendix_sz`, `tikz_v2_regimes` → `tikz_sz_regimes`;
    - `fig_v2_*` → `fig_sz_*`, `make_v2_figures` → `make_sz_figures`,
      `make_v2_subgrid_figures` → `make_sz_subgrid_figures`;
    - `test_v2(_ext)` → `test_sz_models(_ext)`, `audit_table` → `run_checks`.

    No target ever coexists with its source in one commit; the tool checks this.
  - in text files, these are taken out or replaced, together with their punctuation:
    - references to audit rounds and IDs ("audit round 8, h2.3", "v3 audit rounds 6-8", "audit A1 VZ4",
      "[v3 audit R1 item 4]");
    - "phase N" and "round N";
    - "Release audit" and "code audit";
    - the soil zone's generation names v1, v2 and v3 (in prose files only; in code, v1 is a variable).

    "before audit A1" becomes "before the change". The 32 text cases of the self-test are real lines of the history.
  - a PDF or zip whose text still holds such wording is dropped from that commit. These were the main.pdf of 102 of
    the 139 extra commits; the PDF is a build of the chapters in the same commit. `--binaries keep` keeps them instead.
- **The tip:** a blob of the tip tree and a line of a tip text file are never changed, and no tip path is dropped or
  renamed. So the tip tree is the same object, and the release binary, package and zips do not change. "Audit" in the
  sense of the water-balance audit tool is product wording and stays.
- **Safety:** the tool refuses a repository with a remote or with any ref besides the branch. This means it runs only
  on the clones that `apply` leaves. Running it a second time changes nothing.

### Rehearsal (throwaway clones under wt/p27/hist, deleted afterwards)
The steps were: clone the two repositories, apply the messages (PASS), then run neutral_trees.py (PASS). Results:

| | code | extra |
|---|---|---|
| commits | 86 rewritten (83 with a new ID), 34 upstream unchanged | 139 |
| tip tree | b574e44, identical | 3205129, identical |
| auditor's `git log -G` outside docs/design, rewritten range | 0 (was 21) | 0 (was 42) |
| the wider pattern | 0 lines | 0 lines |
| run time | 12 s | 37 s |

- **Other checks:**
  - the md5 of `log --format='%ct %at %an %ae %cn %ce'` equals the development repositories';
  - git fsck is clean;
  - a second run gives the same commits;
  - neutral_trees.py `--self-test`: ALL PASSED.
- **On the whole branch:** `git log -G` lists one commit, upstream 713abd9 (lp_solve's "primal phase 1"). That commit is
  base Raven's, so it is not rewritten.
- **Hand-over kit:** `make_handover.py --no-public-check` from the rewritten clones: PASS (60 s, every block). The
  bundles have 867 and 139 commits, `git log -G` lists no rewritten commit, and none of the old IDs is present.
- **What remains of the wider process-wording rule:** 23 distinct lines in code and 319 in extra. They are
  "history", "rebuilt", "findings", test IDs such as V2a, names of design notes (`soil_zone_v2_plan.md`, a real
  docs/design path) and the audit tool. These are outside the scope of option (c) and are listed in
  `patches/neutral_trees_rule_residual.txt`.

## Tests
- The manual builds cleanly in a scratch copy (`tools/check_manual_pdf.py`: no LaTeX warning, no overfull box, no
  undefined reference). main.pdf is to be rebuilt once Phase 26's chapters are merged.
- No new process wording in the added lines.

## Open
- **Workshops:** regenerate them with the Phase 26 build (`build_tutorials.py`, then `--check`). This gives:
  - the plot excerpts t1/t2/t4_plot.txt and the gw_budget figures with the new label;
  - the PDFs with `\msg`;
  - the zips.
- **Verification chapter:** add rows for Phase 26's new tests, and use the final name of the antimeridian test (AM1
  here).
- **Manual:** rebuild main.pdf after the merge (`check_manual_pdf.py --write`).
- **Release:** neutral_messages_proposals.json needs entries for the commits of Phases 26 and 27 when they are made.
  Run neutral_trees.py after `apply` in the release sequence. If those commits add new versioned names, its RENAME list
  needs them; the tool stops on any audit- or version-named file it does not handle.
