# Audit A9, phase 23: manual, user guide, release recipe, package checks, commit message and workshops

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees and committer dates,
under new IDs.*

Issues: SV9-1 (manual and user guide), IB9-4, MT9-1, MT9-2, MT9-3, MT9-4, MT9-6 and WS9-2 (findings in
`spec/audit_A9/F_SV.md`, `F_IB.md`, `F_MT.md`, `F_WS.md`). Code unchanged in this phase (the SV9-1 code comment is
phase 22's). Extra on top of `8dda640` (branch rb-p23-tests). The commit-message tool and the reviewed proposals are
outside the repositories: `tools/dev/neutral_messages.py` and `spec/neutral_messages_proposals.json` of the
coordinator's folder. One step waits for the phase-22 build: the workshops are regenerated with it (see the end).
Logs and diffs: `wt/p23/patches/`.

## SV9-1 (S3) when the release cap binds
exchanges.tex said the S_y Δh limit binds in two cases, "at every rise" with S_y well below the drainable porosity.
SV's runs (S_y 0.02-0.03 against a drainable porosity of 0.078) show rises of 3 to 4 m, with the start-up S_y warning,
in which the cap never bound: a column at rest, under a small steady flux, or raised by a specified head. It now states
one condition: the limit binds when a rising water table meets more water above equilibrium than S_y Δh in the band it
crosses (water in transit: the LAG store, a wetting front, a recharge pulse; or a nearly full top cell); without it the
release would grow from step to step (gain (θ−θ_eq)/S_y > 1); the smaller S_y against the drainable porosity, the more
readily (with S_y well below it, every recharge pulse that reaches the water table); a column at rest or under a small
steady flux, and a water table raised from below or from the side, hold no such excess and do not bind it, whatever
S_y. The user guide's column paragraph (§4) says the same. The code comment at `GWVadoseModel.cpp:440-444` is aligned
in phase 22.

## IB9-4 (S3) link order of the release build
`build_release_raven.sh` passes the source files to make sorted by name (`srcfiles="$(LC_ALL=C ls -- *.cpp)"`, a
command-line variable, which overrides the Makefile's `$(wildcard *.cpp)`), so the order of the objects on the link line
no longer depends on whether make sorts its wildcard (3.81 and 4.3+ do, 3.82-4.2.1 do not). The header says so;
docs/tutorials/README.md adds "and with any version of GNU make".
Check (`patches/ib9_4_release_build.log`): the script on 93e5166 in a new build folder (zig 0.17.1, make 4.3,
`TZ=Pacific/Kiritimati`): sha256 `cdb126348a44...`, identical to `wt/rel20_release_glibc.exe` and the zips' Raven;
GLIBC 2.16 at most; the link line in make.log lists the 130 objects in C-locale name order. `make -n` with `srcfiles`
given in reverse order links in that order, so the order is the script's, not make's (IB's reverse-order link gave
`88747d73...`). make 4.2.1 is not on this machine.

## MT9-1 (S3) the package README's wording check
`make_package.py`'s `PROCESS` held nine words. It now holds the commit-message rule's words (audit, phase, round,
replay, findings, version and finding IDs, WIP, draft, pending, placeholder, rebuilt, recovered, reconstructed, history,
no longer, previously, regenerated, revised, review, up to date, taken out, ...) plus TODO, FIXME, not yet, final,
status at, by your order, as you asked, corrected, fixed in, earlier version/package/release/build and new in this
release. "git history" and "Raven history" are allowed (the README's restore section and package_sources.py's text).
`neutral_messages.py` notes beside its PATTERN that the two lists change together.
`make_package.py --self-test` injects 25 phrases (MT's eight among them) into the README template and checks each is
found; the template with the restore section `package_sources.restore_text` writes passes; "fixed heads" and
"tools_audit.py" pass. Before → after on MT's probe (`patches/mt9_1_process_before_after.log`): 2 of 8 flagged → 8 of 8.

## MT9-2 (S3) the package accepts a Raven that is not the release build
`make_package.py` reads bin/Raven's dynamic section (program headers, DT_NEEDED and DT_VERNEED, a small ELF64 reader;
no binutils needed) and fails when it needs a GLIBC_ version above 2.28 (or a non-numbered one such as GLIBC_PRIVATE)
or loads libstdc++ or libgcc_s; bin/libmf6.so must need at most GLIBC_2.34, the floor the README names. The docstring
states the checks; the extra README's tool table names them.
- The reader agrees with `objdump -p`/`objdump -T` on rel20_Raven.exe (NEEDED libstdc++, libm, libgcc_s, libc; GLIBC_2.38),
  rel20_release_glibc.exe (libm, libc, ld-linux, libpthread, libdl; 2.16), libmf6.so (libc, ld-linux; 2.34) and base
  Raven (`patches/mt9_2_elf_real_binaries.log`).
- `--self-test` writes synthetic ELF files: GLIBC_2.38, GLIBC_2.29 in libm, GLIBC_PRIVATE, libstdc++ and libgcc_s
  NEEDED, and a shell script fail; GLIBC_2.16 with libc and libdl, and exactly 2.28, pass; a libmf6 with 2.34 passes.
- Before → after: MT's `make_package.py ... --raven wt/rel20_Raven.exe` gave PASS; now (`patches/mt9_2_make_package_rel20_Raven.log`,
  code worktree HEAD, `--no-manual-check`) three FAIL lines (GLIBC_2.38, libstdc++, libgcc_s), each naming
  build_release_raven.sh. With the release build of this phase (`relb/Raven_rel.exe`, = rel20_release_glibc.exe):
  "release builds", and the only FAIL is the expected one, this worktree's uncommitted changes in tools/ and
  docs/tutorials/. README wording: no FAIL in either package (restore section included). Both trial packages deleted.
- tests/tools_check.py TC10 runs `make_package.py --self-test`; tests/README.md lists it (TC1-TC10).

## MT9-3 (S3) user guide §9
Two items of developers.tex were missing from §9 "Known issues in Raven itself": the reservoir stage iteration that
stops at a 0.1 mm change (up to the lake area times 0.1 mm near the weir crest, 3 to 7 m3 on a 0.04 km2 lake in base
Raven, with `:ReservoirExchange` where the aquifer holds a lake near its crest), and `CSubBasin::SetQlatHist`'s read
past the end of the `.rvc` lateral-inflow history, which coupled runs do not guard. Both added in the manual's terms;
§9 now has every item of the manual's list, as the package README says.

## MT9-4 (S4) the verification chapter's input checks
- `tab:readers`: the GeoJSON numbers row loses "(14 files)"; a new row "GeoJSON IDs and structure" lists the cases
  `geomtest_check.py` adds (IDs `null`, `true`, `"7abc"`, 2.6, `"7.5"`, `""` refused; `"7"`, `" 7 "`, `"7.0"`, 7.0
  read; other geometry types skipped before their ID; too shallow nesting, a vertex `[1]`, a LineString whose
  coordinates are a number refused; NaN/Infinity attributes and `\u` names read; trailing text and a truncated file
  refused). No case count, as phase 22 (IB9-6) may add cases.
- `tab:faulty`: two rows, N25-N26 (river lines of an unknown subbasin: left out with a warning; the only line: stop) and
  E1-E6 (an existing model's TDIS and package text in the forms MODFLOW 6 reads: read as MODFLOW reads them; `1.0x` and
  an NPER mismatch stop). The period-number forms are given as "such as 2.0 and 3/", so the row holds when phase 22
  (MT9-5) adds `0.2D1` to E5.
- Both tables then exceeded a page ("Float too large" by 125 and 101 pt): split as phase 21 split `tab:geom`, into
  `tab:readers` (GeoJSON and CRS) and `tab:rasters` (GeoTIFF and ESRI ASCII), and `tab:faulty` (setup errors) and
  `tab:faultynum` (malformed numbers, grid-size limits and other unusual input). The text refers to both of each pair.

## MT9-6 (S4) the merge's message
`spec/neutral_messages_proposals.json`, extra 8dda640: a body, written from the merge's diff against both parents (25
files differ from both): both sides joined in accounting.tex (the river loss a hotstarted run starts with, beside the
averaging caveat), developers.tex and tests/README.md; developers.tex and the user guide add the SetQinHist write past
its array and the coupled guard (WB15); verification.tex the river identities of WB13-WB15; build_release_raven.sh
compiles every object, as the Makefile does not track headers; the workshops' values, excerpts, tools_audit.py copies
and PDFs, Workshop 1's run time, and main.pdf built from the joined sources. `neutral_messages.py check` without and
with the repositories: PASS (84 + 131, all reviewed, subjects unique; `patches/mt9_6_check.log`). Not applied anywhere.

## WS9-2 (S4) finished-state comparisons
A typed `Creek.rvg` (W2 Step 8) or `Creek.rve` (W5 Step 9) differs from the shipped one in spacing and, copied from
the PDF, in empty lines. `diff -w` alone still reports the empty lines of WS's W2 file, so the commands use `-wB`:
W2 Step 20 `diff -rqwB`, W2's trouble box `diff -wB`, W5 "The finished state" `diff -rqwB` (both folders), and W3
Step 6's trouble box `diff -wB` (the student edits `Creek.rvg` there too). Each text says that `-wB` leaves spacing and
empty lines aside, and how to see the lines of a file named as different. Before → after on WS's folders
(`patches/ws9_2_diff_before_after.log`): W2 "Files ... Creek.rvg ... differ" → only `Only in ... hydrograph.png`; the
trouble-box diff 46 lines → 0; W5 "Files ... Creek.rve ... differ" → only `Only in ... ensemble.png`.

## Checks in this phase
- Manual, in a scratch copy (`check_manual_pdf.py`): builds with no LaTeX warnings, overfull boxes or undefined
  references after the table split; against the committed main.pdf 184 → 185 pages, 545 text lines differ (this
  phase's text: FAIL, as expected; `patches/manual_check_scratch.log`). main.pdf is rebuilt after the merge.
- Workshops 2, 3 and 5: `tex/` compiled in a scratch copy (pdflatex twice): 18, 12 and 10 pages as shipped, no LaTeX
  warnings or overfull boxes (`patches/workshop_tex_scratch.log`).
- tools_check.py: ALL PASSED (TC3-TC5, TC7, TC9, TC10; the run cases TC1, TC2, TC6, TC8 skipped without this phase's
  build; their tools are unchanged). `make_package.py --self-test`: ALL PASSED.
- Added lines outside docs/design: no history or audit wording (grep).

## After the merge with phase 22 (code 5b49d0a, extra 65c1858)
- verification.tex: the conic row (13 cases, also more than 180 degrees and exactly 180 degrees from the central
  meridian; worst 4.75e-7 m from geomtest_check.py on 5b49d0a); the GeoJSON rows (IDs beyond 9e15, GDAL's ID_FIELD
  case, polygons without area) in a table of their own (`tab:geojson`, the readers table was 104 pt over a page); a
  band-unit row in `tab:rasters`; E1-E6 with `0.2D1`; rows for E7-E12 and N27-N28 (N27-N28 in `tab:faulty`, as
  `tab:faultynum` was 17 pt over). tests/README.md: input_checks N1-N28, E1-E12 (E5 `0.2D1`), the geomtest and band-unit
  cases.
- Workshops regenerated with wt/rel22_Raven.exe (`--raven-src` the code repository, without OSTRICH, 819 s): only
  measured run times change (`t1:fullmin` 10 -> 8, also in README.txt and model/start/README.md; t2, t3, t5, t6 seconds)
  and the PDFs; no Workshop 6 value changed, so the DDS was not rerun. No `fort.*` file in any run folder.
- Release executable from 5b49d0a with the recipe (sorted link): `wt/rel22_release_glibc.exe`, sha256 938a6301...,
  GLIBC 2.16 at most, banner date Nov 14 2026. `build_tutorials.py --check` with it: PASS (377 values, 105 excerpts);
  its 253 CSV, .rvc, .hds, .cbc and .nc outputs of the workshop runs equal rel22's byte for byte (the other files differ
  in build date, folder paths and timings only). Zips: `wt/ws/zips_final/` with `--source-commit 5b49d0a`.
- Manual: `check_manual_pdf.py --write` (184 -> 186 pages), then PASS.
- Commit messages: reviewed entries for code 5b49d0a, extra f4eee97 (its subject repeated 5b49d0a's), 503c4d6 and
  65c1858; `check` PASS with the repositories (85 + 134).
