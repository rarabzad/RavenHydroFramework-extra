# The manual in two volumes

Decision of 23 Nov 2026: the one-volume manual (`docs/manual/main.tex`, 197 pages) is split into two volumes for
modellers new to the coupling (hydrologists who know Raven or MODFLOW, not both).

| Volume | Source | PDF (committed in `docs/manual/`, shipped in the package root) | Pages |
|---|---|---|---|
| 1, User Manual | `user_manual.tex` | `Raven_MF6_User_Manual.pdf` | 56 |
| 2, Reference and Verification | `reference.tex` | `Raven_MF6_Reference.pdf` | 178 |

`main.tex`, `main.pdf`, `chapters/intro.tex` and `chapters/applying.tex` are removed. Both volumes read the shared
preamble `preamble.tex` (the old preamble, with `xr-hyper`, a header naming the volume, and two new boxes,
`inpractice` "In practice" and `whattowrite` "What to write").

## Structure

Volume 1 (new files `chapters/u_*.tex`):

1. `u_intro` What the coupling does: the problem, the two ways, how to use the two volumes, what you do and what Raven
   does, what is new for a Raven user and for a MODFLOW user, the pieces, one day, features, design principles, scope,
   when to use it, what changes for an existing Raven model, files at a glance.
2. `u_quickstart` Quick start with example A: installation, the four files changed, run, results.
3. `u_build` Building a groundwater model: coupled HRUs, classes and profiles, how layers stack, maps (HRU polygons,
   rasters, units and `METRES`, `:InputCRS`, river lines), the grid (cell size, types, the Liard grid table), starting
   heads, wells and boundaries, a starter `.rvg`, checklist, typical values.
4. `u_existing` Coupling an existing model: the working copy, example B, linking, time, units, packages, a table of what
   is supported and refused, later starts and restarts, rivers (the carried river loss of example B), outputs.
5. `u_exchanges` The exchanges in plain terms: recharge, seepage, rivers and the river-loss take, water-table ET,
   wetlands and lakes, reservoirs, wells and boundaries, the soil zone (`CONCEPTUAL` against `PHYSICAL`, the old
   "water table in the soil" steps), the unsaturated zone (`NONE`, `RICHARDS`, `KINEMATIC`, `LAG`), common questions.
6. `u_outputs` Running, the output files, `GWModelSummary.txt`, `GWBudget.csv` (main columns, a Liard day, what a good
   run looks like), the audit tool `tools_audit.py`, heads and particle tracking.
7. `u_restarts` Spin-up, restarts, ensembles, calibration (synthetic test, the Ostrich file line by line).
8. `u_trouble` Troubleshooting: the old message table plus a few common stops, unconverged steps, FAQ.
9. `u_commands` Command summary: one table, each command with the section and page of Volume 2 that explains it and the
   page of its full entry in the Reference command table.
A. `u_glossary` the glossary (moved from the introduction).

Volume 2: `concepts`, `building`, `existing_model`, `exchanges` (with `sz_*`), `accounting`, `inputs_outputs`,
`verification` (with `verification_soilzone`, `verification_rough`), `developers`, appendix `appendix`. An "About this
volume" page with a table of where to find what. These files are unchanged except:
- each chapter (and the appendix) starts with an "About this chapter" paragraph pointing to the Volume 1 chapter on the
  same subject;
- `appendix.tex`: a label `cmd:<name>` on each row of the command table (for the page references of Volume 1);
- `exchanges.tex`: the diagram of all exchanges is moved to `figures/tikz_exchanges.tex`, which both volumes input;
- `developers.tex`: the paragraph on `check_manual_pdf.py` names the two volumes and PDFs.
`figures/tikz_two_ways.tex` (Volume 1 only) points to the Volume 1 chapters.

Where the old text went:

| Old | New |
|---|---|
| intro.tex | Volume 1, chapter 1 (glossary: appendix A); "How to read this manual" rewritten for the two volumes |
| applying.tex: tutorial | Volume 1, chapter 2 |
| applying.tex: preparing data, Liard grids, checklist, typical values, how much groundwater | Volume 1, chapter 3 |
| applying.tex: water table in the soil | Volume 1, section 5.8.1 |
| applying.tex: calibration, synthetic test, Ostrich file | Volume 1, chapter 7 |
| applying.tex: troubleshooting, FAQ | Volume 1, chapter 8 (FAQ items on rivers, frozen ground, partial coupling, two aquifers, other subbasins: section 5.9) |
| every other chapter | Volume 2, unchanged apart from the additions above |

Volume 1 states nothing that is not in the old manual: its plain-language text restates the old rules, and its
"What to write" boxes and examples use the old examples' numbers.

## Cross references

Volume 1 loads `\externaldocument[R-]{reference}[Raven_MF6_Reference.pdf]`, Volume 2
`\externaldocument[U-]{user_manual}[Raven_MF6_User_Manual.pdf]` (package `xr-hyper`). A reference into the other volume
is written `Reference, Section~\ref{R-...}` or `User Manual, Chapter~\ref{U-...}`; links open the other PDF, which sits
beside it in `docs/manual/` and in the package. Labels of Volume 1 that are new start with `uch:`, `sec:u`, `fig:u`,
`tab:u`; the old labels of intro.tex and applying.tex keep their names in Volume 1.

The volumes read each other's `.aux`, so they are built together: `tools/check_manual_pdf.py` runs pdflatex on each,
bibtex on each, then pdflatex on each again until no rerun is asked for and the `.aux` files stop changing (at most 8
rounds; 3 in practice). Both builds end without warnings, overfull boxes or undefined references.

## Coverage check

`docs/design/manual_two_volumes_coverage.py` compares the old manual (revision 132b551, `main.tex` with every input)
with the two volumes of the working tree:

```
labels: 196 of 196 of the old manual are defined in a volume (20 in Volume 1, 176 in Volume 2)
tables: 86 of 86 of the old manual are in a volume (69 by caption, 17 uncaptioned by their first row)
commands: 491 of 491 command names and keywords of the old manual appear in a volume (138 names with a colon)
numbers: 139 of 139 numbers of intro.tex and applying.tex appear in Volume 1
coverage: PASS
```

A negative test (one label renamed and one number changed in Volume 1) gives `FAIL (2 items missing)`.

## Claims left unchanged that look wrong (for the coordinator)

1. The same Liard day (15 June 1996, the 20-year run) has two sets of numbers: `accounting.tex` (worked example)
   gives seepage to Raven 19 087 047 m3/d and storage release -3 925 212 m3/d; `inputs_outputs.tex` (the sample row of
   `GWBudget.csv`) gives 19 087 056.98 and -3 925 200.44. Both cannot be one run's row. Volume 1 quotes the
   `accounting.tex` numbers. Both are kept.
2. Coupled area of example A: the tutorial says "about 13 800 km2" for the three subbasins, the cell-size paragraph of
   `building.tex` "the Liard example's 13 000 km2". 3 252 active 2 km columns cover about 13 000 km2, so the two may
   measure different things (subbasins against active cells), but neither says so.
3. Example A: "3 layers x 85 x 54 cells, 3 252 active columns" (tutorial) against 8 840 active cells for the default
   2 km grid in the Liard grid table; 3 x 3 252 = 9 756. Probably columns of the one-layer profile have inactive lower
   cells, but the text does not say so.
4. Synthetic calibration table: gravel S_y 0.239 against 0.25 is -4.4 %, the table says -4.5 % (perhaps rounded from an
   unrounded estimate).
5. `inputs_outputs.tex`, table of `.rvg` commands: `:LandSurface file [METRES]` but `:BedrockSurface file` without
   `[METRES]`, which the appendix and building chapter allow for both (an omission, not a wrong statement).

## Tools, tests and other files

- `tools/check_manual_pdf.py`: builds and checks both volumes (`--write` replaces either PDF); a missing PDF fails.
- `tools/package_sources.py`: `MANUAL_COPIES` (both PDF names); checks each package copy against
  `docs/manual/<name>` of the extra revision.
- `tools/make_package.py`: ships both PDFs; its README file check knows both names.
- `tools/package_README.md`: the contents table lists both volumes; the chapter references name Volume 2.
- `tests/tools_check.py` TC9: a two-volume stand-in with a reference across the volumes; a changed chapter fails; a
  missing PDF fails.
- `README.md`, `examples/README.md`, `examples/Liard_existing_model/README.md`, the user guide: the two volumes and their
  chapter numbers.
- Workshops 3 and 4: their closing paragraphs name the two volumes; their PDFs rebuilt (`build_tutorials.py
  --pdf-only --only t3,t4`, 13 pages each, as before).

Results: `check_manual_pdf.py` PASS (56 and 178 pages; 60 and 178 after the figures below were added); `tools_check.py` ALL PASSED (TC1, TC2, TC6 and TC8 run with the
test environment); `make_package.py --self-test` ALL PASSED.

## Open

- `docs/tutorials/build_tutorials.py` writes `model/start/NOTICE.md` of Workshop 1 with "the manual of the coupling
  (chapter "Developer guide and limitations", ...)". The chapter keeps that name in Volume 2, so the sentence stays true;
  naming the volume would need a full workshop rebuild with Raven, which this change does not do.
- The test scripts' docstrings cite the manual by section names ("manual, 'Restarts'" and the like). Those sections are in
  Volume 2 under the same names, except the tables "The Liard model on each grid" (`tests/liard_grids.py`) and the
  calibration, now in Volume 1.
- Volume 1 has 56 pages, below the 60 to 80 aimed at; it holds every user-facing statement of the old introduction and
  application chapters, the plain-language chapters, and eight figures shared with Volume 2.


## Later additions

- Twelve explanatory figures of Volume 2 were added to Volume 1 (shared figure files); Volume 1 now has 60 pages.
- The synthetic calibration caption was lengthened; the coverage script accepts a caption that begins with the old one.
  Coverage after these changes: PASS (196 labels, 86 tables, 491 commands, 139 numbers).
- Every Volume 1 figure is referred to in the text; the quick start says its .rvg listing shows the main commands.
