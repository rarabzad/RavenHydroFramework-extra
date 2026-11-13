# Raven-MODFLOW 6 workshops

Six self-contained student workshops for the groundwater coupling of Raven, one folder each in `workshops/`, and one zip
each for the students:

| Folder | Workshop |
|---|---|
| `Workshop_1_Getting_Started` | installation check, the Liard River example, the groundwater outputs |
| `Workshop_2_Own_Groundwater_Model` | a groundwater model that Raven builds for Tutorial Creek |
| `Workshop_3_Soil_Zone_Coupling` | `:SoilZone PHYSICAL`, unsaturated columns, depth classes |
| `Workshop_4_Existing_MODFLOW_Model` | coupling an existing MODFLOW 6 model (in feet); ET, wetland, reservoir |
| `Workshop_5_Restarts_Ensembles_Particles` | hotstarts, a Monte Carlo ensemble, particle tracking |
| `Workshop_6_Calibration_With_Ostrich` | DDS calibration with OSTRICH, validation |

Each folder holds `README.txt`, the PDF, `tex/` (`main.tex`, `preamble.tex`, `sections/` with one file per section,
`generated/`, `figures/`), `model/` (start, finished and some intermediate states), `scripts/` (only the helpers that
workshop uses) and `bin/`. A student needs only the workshop's zip and a Linux shell (on Windows: WSL). The texts tell
Windows users to use WSL; the programs in `bin/` are Linux (x86_64) builds.

Each workshop is its own PDF and its own zip; there is no combined PDF or zip.

## What is committed and what is generated

- Hand-written: `workshops/*/README.txt`, `workshops/*/tex/main.tex`, `workshops/*/tex/sections/*.tex`,
  `preamble.tex` (the source of every `tex/preamble.tex`), `scripts/` (the source of `plot_gw.py`, `compare_runs.py`,
  `plot_tracks.py`) and `build_tutorials.py`.
- Written by `build_tutorials.py` (committed, do not edit by hand): each workshop's `tex/generated/` (every number,
  output excerpt and file change quoted in the text), `tex/figures/`, `model/`, `scripts/` (copies: `plot_soilzone.py`
  and `make_prt.py` from `tools/`, `tools_audit.py` from `examples/Liard_groundwater/`, `RavenMF6InstallCheck.py` from
  the Raven source's `cmake/`), `tex/preamble.tex`, `bin/README.txt` and the PDF.
- Not committed: the programs in `bin/` (Raven and `libmf6.so`). `bin/` holds only `README.txt` in git; the programs are
  added to the zips by `--package`.

## Build

```
python3 build_tutorials.py --raven RAVEN_EXE --mf6 libmf6.so --raven-src RAVEN_CHECKOUT [--ostrich OSTRICH_EXE]
```

runs every step of every workshop, writes the generated parts and compiles each workshop's PDF from a copy of its folder
(`pdflatex main.tex`, twice). The build fails on any LaTeX warning, overfull box or undefined reference. The PDFs carry a
fixed date (`SOURCE_DATE_EPOCH`). Without `--ostrich` (or with `--quick`), the committed DDS record of workshop 6 is kept
and only its validation is rerun; `--quick` also keeps the committed 20-year Liard values of workshop 1.

## Check

```
python3 build_tutorials.py --check --quick --raven RAVEN_EXE --mf6 libmf6.so --raven-src RAVEN_CHECKOUT
```

reruns the steps in `--work` and compares every number, excerpt, diff, model file, script copy, preamble copy and
`bin/README.txt` with the committed ones, and compiles each committed `tex/` standalone. `tests/tutorials_check.py`
runs it in the test suite.

## Release: the six zips

```
python3 build_tutorials.py --package OUT_DIR --raven RAVEN_EXE --mf6 libmf6.so --raven-src RAVEN_CHECKOUT
```

writes `OUT_DIR/Workshop_N_<Name>.zip`, each holding its folder with `bin/Raven`, `bin/libmf6.so` and a `bin/README.txt`
that lists their versions and SHA-256 sums and the licences (Raven: Artistic License 2.0; MODFLOW 6: U.S. Geological
Survey, public domain). The zips have fixed timestamps. Run `--check` with the same Raven first: the numbers in the texts
belong to that build. The Raven of the zips is built with `build_release_raven.sh RAVEN_CHECKOUT BUILD_DIR RAVEN_EXE
[COMMIT]` (a Linux executable for glibc 2.28 or newer, with zig 0.17.1, pinned in the script). The script takes the
build date in Raven's banner from the commit, so the same commit gives the same executable, byte for byte, on any day.
