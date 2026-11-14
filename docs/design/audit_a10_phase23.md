# Audit A10, phase 25: manual, user guide, package wording check, commit message and workshops

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees and committer dates,
under new IDs.*

Issues: SV10-1 (manual and user guide), MT10-1 to MT10-6, WS10-1 and WS10-2 (findings in `spec/audit_A10/F_SV.md`,
`F_MT.md`, `F_WS.md`). Code unchanged in this phase (the SV10-1 code comment is phase 24's). Extra on top of `a6298a7`.
The commit-message tool and the reviewed proposals are outside the repositories: `tools/dev/neutral_messages.py` and
`spec/neutral_messages_proposals.json` of the coordinator's folder. One step waits for the phase-24 build: the
workshops are regenerated with it (see the end). Logs and diffs: `wt/p25/patches/`.

## SV10-1 (S3) when the release cap binds
exchanges.tex and user guide §4 kept the one condition (the limit binds when a rising water table meets more water above
equilibrium than S_y Δh in the band it crosses) but built two absolute claims on it: "with S_y well below the drainable
porosity every recharge pulse binds" and "a column under a small steady flux does not bind, whatever S_y". SV's runs
disprove both (pulses up to 40 mm with S_y 0.02 do not bind; steady 1-3 mm/d with S_y 0.01-0.03 binds at 2.8-4.4 m below
the top cell's top). Both texts now state the condition and what it depends on: the water above equilibrium in the band
the rise crosses (water in transit, more of it the larger the pulse; the excess of a column under a steady flux, which
grows with the height above the water table and is met when a small S_y makes the water table rise fast; a nearly full
top cell), binding the more readily the smaller S_y is against the drainable porosity. The one case SV confirmed stays:
a column at rest, raised from below or from the side, does not bind.

## MT10-1 (S3) verification.tex: "Thirty-nine faulty or unusual set-ups of the Liard model"
No test gives 39, and many cases are not on Liard. The paragraph now names the cases behind the two tables:
input_checks.py N1-N28, U0-U4, RN1-RN2 and E1-E12 (on the Liard model and smaller generated and existing models) and
test_inputs.py I22.

## MT10-2 (S3) user guide §9 and the existing-model limitation without NEWTON
§9's existing-model item now carries the manual's sentence (developers.tex, "Current limitations"): a dried top cell
of a model without NEWTON becomes inactive; recharge and ET move to the cell below, the seepage drain and a reservoir's
seepage stop on that column until it rewets; the water table below can rise above the ground. The package README's
"the same list" holds again.

## MT10-3 (S4) known issue: 22 subbasins
developers.tex: "17 subbasins" → "22 of the 65 subbasins" (MT's base-Raven run, 365 and 7305 days).

## MT10-4 (S4) one list of process words
`tools/process_wording.py` (new) holds the commit-message rule, `RULE_SOURCE` and `RULE`, identical to the
`PATTERN` of `neutral_messages.py` (checked: same pattern text and flags). `make_package.py` builds `PROCESS` from
`RULE_SOURCE` plus the README-only words (`README_EXTRA`: phases, rounds, finding, TODO, FIXME, not yet, final, status
at, by your order, as you asked, corrected, fixed in, earlier version, new in this release) and allows "git history"
and "Raven history" by a check of the words before the match, as before. The self-test adds MT's six phrases (merged
build, built (2026-..., brought ... up to, merge3, conflicts ... resolved, v3build), "the Raven history bundle" as
allowed, and a check that PROCESS starts with the rule's pattern. Probe (`patches/mt10_4_probe_before_after.log`): the
six phrases not found → found; the allowed ones still pass. For `neutral_messages.py` (coordinator's folder) the patch
`patches/mt10_4_neutral_messages_import.diff` replaces its PATTERN by `from process_wording import RULE as PATTERN`
(the extra checkout's tools/, beside tools/dev by default, or `RAVEN_EXTRA_TOOLS`); `check` with it: PASS.

## MT10-5 (S4) the message of a6298a7
In `spec/neutral_messages_proposals.json` only: the subject no longer names a release binary or "the current
sources"; the body lists the verification.tex rows, the tests/README.md row, the workshops' measured run times and
PDFs, main.pdf and the design note, as `git show --stat a6298a7` lists them. `neutral_messages.py check` with the
repositories: PASS (85 + 135, 0 flagged). Not applied to the repositories.

## MT10-6 (S4) examples/README.md
"(`Raven_MF6_linux`)" → "(the folder made by `tools/make_package.py`, with `bin/`, `examples/` and `README.md`)".

## WS10-1 (S3) README "How to start"
The six README.txt files gave Step 1's commands and then sent the student to Step 1, so unzip asked about every file and
`cp -r` made `work/start`. "How to start" now gives no commands: open the PDF and follow it from Step 1 (which unpacks
the zip and sets WS and RAVEN; a later step copies model/start to work); skip Step 1's unzip line when the zip is
already unpacked in the home folder; type the two export lines again in every new terminal.

## WS10-2 (S4) Workshop 1's warning count
build_tutorials.py counted lines beginning with WARNING (133) and the text called them the warnings; `grep -c WARNING`
gives 137, because Raven writes a repeated warning once and then `**[PREVIOUS WARNING REPEATED n TIMES]**`. The build
now counts as `grep -c WARNING` does (`t1:nwarn` 137) and counts the repeat lines (`t1:nwarnrep` 4); it stops when the
four kinds do not add up or when a repeat line follows anything but a missing-metric warning. The text says what is
counted: 137 lines, as `grep -c WARNING out/Raven_errors.txt` counts them; 85 polygon-area, 27 cross-section, 21 lines
naming a fit statistic that cannot be calculated without observations and 4 repeat lines. values.tex carries the
counts of the committed run until the regeneration. `build_tutorials.py --check --quick --only t1` with
wt/rel22_Raven.exe: PASS (36 values, 12 excerpts; tex compiles, 10 pages, no warnings or boxes;
`patches/ws10_2_t1_check_rel22.log`).

## Checks
- Manual built in a scratch copy (`check_manual_pdf.py`): builds without LaTeX warnings, overfull boxes or undefined
  references, 186 pages as the committed main.pdf; the text differs by this phase's changes (FAIL against main.pdf, as
  expected; `patches/manual_build_check.log`). main.pdf is rebuilt after the merge.
- tools_check.py with wt/rel22_Raven.exe: ALL PASSED (TC10: the self-test above). `make_package.py --self-test`: ALL
  PASSED (`patches/mt10_4_selftest.log`).
- Added lines outside docs/design: no history or audit wording (grep).

## After the merge with phase 24
To do: regenerate the workshops with the phase-24 build, rebuild main.pdf (`check_manual_pdf.py --write`), and add the
proposal entries for the merged commits.
