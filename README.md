# RavenHydroFramework-extra: groundwater for Raven with MODFLOW 6

RavenHydroFramework-extra adds groundwater to the [Raven hydrological modelling framework](https://raven.uwaterloo.ca) with
[MODFLOW 6](https://github.com/MODFLOW-ORG/modflow6). Raven either **builds a MODFLOW 6 model** from its HRUs
(`:GroundwaterModel MODFLOW6`) or **couples an existing one** (`:MF6Simulation`), and exchanges recharge, seepage,
river leakage, water-table ET, wells, boundaries and reservoir seepage with it every time step.

The coupling's source code is part of Raven itself (RavenHydroFramework). This repository holds everything around it:

| Folder | Contents |
|---|---|
| `docs/` | user guide (`Raven_MF6_Groundwater_UserGuide.md`), manual (`manual/`, LaTeX with `main.pdf`), verification reports |
| `examples/` | the Liard River model with a groundwater model built by Raven, and coupled to an existing MODFLOW 6 model; step-by-step guide in `examples/README.md` |
| `tests/` | the verification suite; `python3 tests/run_all.py` runs everything and writes one report |
| `tools/get_mf6.py` | downloads the MODFLOW 6 library (6.8.1, the tested version) for your computer |

## Quick start

Put Raven and this repository side by side, build Raven, get MODFLOW 6, and run an example:

```
git clone -b mf6-coupling https://github.com/rarabzad/RavenHydroFramework.git
git clone https://github.com/rarabzad/RavenHydroFramework-extra.git

cd RavenHydroFramework
cmake -S . -B build
cmake --build build --config Release

cd ../RavenHydroFramework-extra
python tools/get_mf6.py                      # MODFLOW 6.8.1 into ../RavenHydroFramework/lib/mf6, where Raven finds it

cd examples/Liard_existing_model
../../../RavenHydroFramework/build/Raven Liard -o output/            # Windows: ..\..\..\RavenHydroFramework\build\Release\Raven.exe
```

Until the coupling is merged into the Raven repository (https://github.com/CSHS-CWRA/RavenHydroFramework), use the
`mf6-coupling` branch of https://github.com/rarabzad/RavenHydroFramework, which holds the coupling with the related Raven
fixes. Windows, Linux and macOS step by step: `examples/README.md`.

## Requirements

- A C++ compiler and CMake 3.20 or newer (or GNU make) to build Raven.
- Python 3 for `tools/get_mf6.py` (standard library only); the tests also need numpy, pandas, shapely, pyproj and flopy.
- MODFLOW 6.5 or newer as a shared library (tested with 6.8.1 and 6.6.3). It is loaded at run time; Raven builds and runs
  without it when groundwater is not used.

## Tests

```
cd tests
python3 run_all.py --nolib     # checks that need no MODFLOW library (a few minutes)
python3 run_all.py             # everything (about an hour)
```

The tests find Raven in `../RavenHydroFramework`; otherwise set `RAVEN_SRC` (see `tests/README.md`).

## License

Code: Artistic License 2.0 (`LICENSE`), the license of Raven. Documentation: CC BY 4.0 (`docs/LICENSE-docs.md`).
Liard River model inputs: see `examples/Liard_groundwater/DATA_NOTICE.md`. Details in `NOTICE.md`.
