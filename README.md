# RavenHydroFramework-extra: groundwater for Raven with MODFLOW 6

RavenHydroFramework-extra adds groundwater to the [Raven hydrological modelling framework](https://raven.uwaterloo.ca) with
[MODFLOW 6](https://github.com/MODFLOW-ORG/modflow6). Raven either **builds a MODFLOW 6 model** from its HRUs
(`:GroundwaterModel MODFLOW6`) or **couples an existing one** (`:MF6Simulation`), and exchanges recharge, seepage,
river leakage, water-table ET, wells, boundaries and reservoir seepage with it every time step. Optionally
(`:SoilZone PHYSICAL`) the water table rises into Raven's soil layers, with the soil zone and MODFLOW iterated to
agreement within each step, for generated and existing models alike. On sloping and irregular land every cell samples
the DEM at many points, so the soil saturates first at the foot of slopes and in hollows. Below the soil, recharge can
cross an unsaturated zone (`:SoilZoneVadose RICHARDS`, `KINEMATIC` or `LAG`, with depth classes on hummocky ground);
dry soil draws water up from a shallow water table by capillary rise; the exchange is lagged into Raven's step to cut the
splitting error; Raven's processes can act on classes of an HRU's columns (`:SoilZoneClasses`); and soil over specified
heads exchanges with them exactly (manual chapter 5, "The soil zone and the water table"; reference table of the
`:SoilZone*` commands in chapter 7).

The coupling's source code is part of Raven itself (RavenHydroFramework). This repository holds everything around it:

| Folder | Contents |
|---|---|
| `docs/` | user guide (`Raven_MF6_Groundwater_UserGuide.md`), manual (`manual/`, LaTeX with `main.pdf`; verification in chapter 9) |
| `examples/` | the Liard River model with a groundwater model built by Raven, and coupled to an existing MODFLOW 6 model; step-by-step guide in `examples/README.md` |
| `tests/` | the verification suite; `python3 tests/run_all.py` runs everything and writes one report |
| `tools/get_mf6.py` | downloads the MODFLOW 6 library (6.8.1, the tested version) for your computer, for a Raven built without it |
| `tools/plot_soilzone.py` | plots the soil-zone exchange of a `:SoilZone PHYSICAL` run (`GWSoilExchange.csv`, `GWBudget.csv`), with specified heads too |
| `tools/package_sources.py` | writes the `source/` folder of a release package (source archives and the complete git history of both repositories as bundles on branch `soil-zone`; a shallow Raven clone is completed from the upstream Raven repository first; `COMMITS.txt`) and runs the clone commands of the package README's "Restore the git history" section as written, checking that each bundle clones with its whole history, branch, tip and commit count as the README states |
| `examples/Liard_groundwater/tools_audit.py` | checks every balance identity of a run, including the soil-zone identities (rejected recharge, applied exchange, shortfall, interface convergence) |

## Quick start

Put Raven and this repository side by side, build Raven (with MODFLOW 6), and run an example:

```
git clone -b mf6-coupling https://github.com/rarabzad/RavenHydroFramework.git
git clone https://github.com/rarabzad/RavenHydroFramework-extra.git

cd RavenHydroFramework
cmake -S . -B build                          # also gets MODFLOW 6.8.1 (see below)
cmake --build build --config Release         # Raven and libmf6 side by side in build/ (Windows: build\Release\)

cd ../RavenHydroFramework-extra/examples/Liard_existing_model
../../../RavenHydroFramework/build/Raven Liard -o output/            # Windows: ..\..\..\RavenHydroFramework\build\Release\Raven.exe
```

CMake gets the MODFLOW 6 library by itself (option `RAVEN_MF6`): with a Fortran compiler (gfortran or ifx),
meson >= 1.7, ninja and git (`pip install meson ninja`) it builds it from the MODFLOW 6.8.1 source; without them it
downloads the official release library (Linux x86_64, Windows x64, Apple Silicon Macs; checked against pinned SHA-256);
`-DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=/path/to/libmf6.so` uses one you have, `-DRAVEN_MF6_ZIP=mf6.8.1_linux.zip` a release
zip on disk, and `-DRAVEN_MF6=OFF` builds Raven alone. On Linux other than x86_64 (e.g. aarch64), Windows on ARM64 and
Intel Macs MODFLOW releases no library: there, install the source tools (`-DRAVEN_MF6=SOURCE`) or use `PATH`; without
either the configure warns and builds Raven alone. `cmake --install build` and `cpack` give one folder (package) with
Raven, the library and the Fortran runtime it needs (on Linux, a library built elsewhere is given the run path `$ORIGIN`
with `patchelf` when that is installed, so that it loads the runtime beside it); a build without the library installs
Raven alone. Details: manual, chapter 10, "Building".

For a Raven built without the library (GNU make, Visual Studio solution, `-DRAVEN_MF6=OFF`):
`python tools/get_mf6.py` puts MODFLOW 6.8.1 into `../RavenHydroFramework/lib/mf6`, where Raven finds it (Linux x86_64,
Windows x64, Apple Silicon Macs; Intel Macs only with `--version 6.6.3`).

Until the coupling is merged into the Raven repository (https://github.com/CSHS-CWRA/RavenHydroFramework), use the
`mf6-coupling` branch of https://github.com/rarabzad/RavenHydroFramework, which holds the coupling and its changes to Raven's own
files. Windows, Linux and macOS step by step: `examples/README.md`.

## Requirements

- A C++ compiler and CMake 3.20 or newer (or GNU make) to build Raven; for the MODFLOW 6 library built from source also
  a Fortran compiler, meson >= 1.7, ninja and git (optional: otherwise the release library is downloaded).
- Python 3 for `tools/get_mf6.py` (standard library only); the tests also need numpy, pandas, shapely, pyproj and flopy.
- MODFLOW 6.5 or newer as a shared library (tested with 6.8.1 and 6.6.3). It is loaded at run time; Raven builds and runs
  without it when groundwater is not used.

## Tests

```
cd tests
python3 run_all.py --nolib     # checks that need no MODFLOW library (a few minutes)
python3 run_all.py --quick     # everything in quick mode (about 35 minutes on two cores, up to an hour on a busy machine)
python3 run_all.py             # everything in full mode (about 1.5 hours, up to 2.5 hours on a busy machine)
```

`--quick` runs fewer randomized set-ups and sets `RAVEN_TEST_QUICK=1` for every script. The soil-zone scripts and
`behaviour_check`, `budget_file`, `combinations`, `crs_inputs`, `input_checks`, `mf6version_check`, `ext_exchanges`,
`ext_inputs` and `restart_ext` then run shorter cases; the other scripts (among them the long `edge`, `liard_grids` and
the existing-model guards) run their usual cases in both modes. `tests/README.md` lists them.

The tests find Raven in `../RavenHydroFramework`; otherwise set `RAVEN_SRC` (see `tests/README.md`). The C++ unit tests
compile Raven's sources from `RAVEN_SRC`, so it must point at the Raven source even when `RAVEN_EXE` names a built Raven.

From the release package (the two source archives unpacked side by side in one folder `<dir>`, which gives
`<dir>/raven-soil-zone` and `<dir>/raven-mf6-extra`; `<pkg>` the unpacked package):

```
cd <dir>/raven-mf6-extra/tests
RAVEN_SRC=<dir>/raven-soil-zone RAVEN_EXE=<pkg>/bin/Raven RAVEN_MF6_LIB=<pkg>/bin/libmf6.so python3 run_all.py --quick
```

## License

Code: Artistic License 2.0 (`LICENSE`), the license of Raven. Documentation: CC BY 4.0 (`docs/LICENSE-docs.md`).
Liard River model inputs: see `examples/Liard_groundwater/DATA_NOTICE.md`. Details in `NOTICE.md`.
