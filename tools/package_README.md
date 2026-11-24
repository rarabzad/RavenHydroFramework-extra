# Raven with MODFLOW 6 groundwater: Linux package

Raven, the semi-distributed hydrological modelling framework, with groundwater from MODFLOW 6. Raven either builds a
MODFLOW 6 model from its HRUs (`:GroundwaterModel MODFLOW6`) or couples an existing one (`:MF6Simulation`), and the two
exchange recharge, seepage, river leakage, water-table evapotranspiration, wells, boundaries and reservoir seepage every
time step. With `:SoilZone PHYSICAL` the water table rises into Raven's soil layers. The manual, in two volumes, describes
every option.

## Contents

| Path | Contents |
|---|---|
| `bin/Raven` | Raven 4.15 with the MODFLOW 6 coupling, for Linux x86_64 |
| `bin/libmf6.so` | the MODFLOW 6 library (6.8.1, the official release). Raven loads it from its own folder: keep the two files together |
| `bin/RavenMF6InstallCheck.py` | the install check (below) |
| `bin/VERSIONS.txt` | versions, source commit and SHA-256 sums of the two programs |
| `bin/LICENSE-Raven.txt`, `bin/NOTICE-MODFLOW6.txt` | the licences of the two programs |
| `Raven_MF6_User_Manual.pdf` | the manual, Volume 1 (User Manual): what the coupling does, a quick start with the examples, building and coupling models, the exchanges and the soil zone in plain terms, outputs and the water balance, restarts and calibration, troubleshooting, a command summary |
| `Raven_MF6_Reference.pdf` | the manual, Volume 2 (Reference and Verification): every rule and equation, the command, output and message tables, verification, the developer guide, limitations and known issues |
| `examples/` | two Liard River models: `Liard_groundwater` (Raven builds the MODFLOW 6 model) and `Liard_existing_model` (Raven couples an existing MODFLOW 6 model); `examples/README.md` walks through both |
| `workshops/` | six self-contained student workshops, one zip each (a PDF, the model files, scripts and the programs) |
| `source/` | the source code of both repositories as archives, and their complete git history as bundles |
| `SHA256SUMS.txt` | SHA-256 sums of every file of the package |

The source archives: `raven_code_src.tar.gz` is RavenHydroFramework (Raven with the coupling, branch `mf6-coupling` of
https://github.com/rarabzad/RavenHydroFramework) and unpacks as `raven-soil-zone/`; `raven_extra_docs_tests.tar.gz` is
RavenHydroFramework-extra (the user guide, the manual sources, examples, tests and tools,
https://github.com/rarabzad/RavenHydroFramework-extra) and unpacks as `raven-mf6-extra/`. `source/COMMITS.txt` names
the commit of each.

## Requirements

- Linux on x86_64 with glibc 2.34 or newer (set by `libmf6.so`): for example Ubuntu 22.04, Debian 12, RHEL or Rocky 9,
  Fedora 35 or newer, and Ubuntu in the Windows Subsystem for Linux. Raven itself contains its C++ runtime.
- Python 3 for the install check, and Python 3 with pandas for `tools_audit.py`, the examples' balance checks.

## Install check

From the package folder:

    python3 bin/RavenMF6InstallCheck.py bin 6.8.1

It runs Raven on a tiny coupled model with the library beside it and ends with `install check: PASS`. If Raven does not
start: `chmod +x bin/Raven`; a message naming `GLIBC_2.34` means the Linux is older than the library needs.

## Quick start

    export RAVEN=$PWD/bin/Raven
    cd examples/Liard_groundwater
    $RAVEN Liard -o output/                # 20 years, daily; about 10 minutes on one core
    python3 tools_audit.py output          # water-balance and consistency checks

The groundwater results are `output/GWBudget.csv`, `GWHRUState.csv`, `GWConnectivity.csv` and `GWModelSummary.txt`,
and the MODFLOW 6 model Raven built is in `output/mf6/`. The second example runs the same way from
`examples/Liard_existing_model` (2 years, about 5 minutes). `examples/README.md` explains each step and the results to
expect; its "Part 1" (building Raven) is not needed with this package.

## Workshops

Unzip a workshop and open its PDF; each zip holds everything the workshop needs, including its own copy of the programs:

1. Getting started: the install check and the Liard example
2. Your own groundwater model
3. Soil-zone coupling
4. An existing MODFLOW model
5. Restarts, ensembles and particle tracking
6. Calibration with OSTRICH (OSTRICH is not included; the workshop names where to get it)

## Build from source

    tar xzf source/raven_code_src.tar.gz
    cd raven-soil-zone
    cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j

The build also provides the MODFLOW 6 library, chosen with `-DRAVEN_MF6=`: `SOURCE` (builds the pinned MODFLOW 6.8.1;
needs a Fortran compiler, meson, ninja and git), `PREBUILT` (the official release, checked by its SHA-256), `PATH`
(`-DRAVEN_MF6_PATH=/path/libmf6.so`) or `OFF` (Raven without the library). Without the option, `SOURCE` is taken when
its tools and the network are there, otherwise `PREBUILT`. The minimum MODFLOW 6 version is 6.5.0; 6.8.1 is the tested version. The manual's
Volume 2, chapter "Developer guide and limitations", section "Building", has the details, also for Windows and macOS.

## Tests

Unpack both source archives in one folder `<dir>`, then:

    cd <dir>/raven-mf6-extra/tests
    pip install numpy pandas shapely pyproj flopy
    RAVEN_SRC=<dir>/raven-soil-zone RAVEN_EXE=<pkg>/bin/Raven RAVEN_MF6_LIB=<pkg>/bin/libmf6.so python3 run_all.py --quick

`<pkg>` is this package's folder. `--quick` takes about 50 minutes on two cores; without it the full suite takes about
2.5 hours. `tests/README.md` lists every test.

## Restore the git history
From the package folder (offline; the same checkouts as cloning https://github.com/rarabzad/RavenHydroFramework, branch mf6-coupling, and https://github.com/rarabzad/RavenHydroFramework-extra, branch main):

    git clone source/raven_code_history.bundle RavenHydroFramework -b mf6-coupling
    git clone source/raven_extra_history.bundle RavenHydroFramework-extra -b main

## Known issues

The manual lists the limitations of the coupling and the known issues of Raven itself (Volume 2, chapter "Developer guide
and limitations", section "Limitations and known issues"); the user guide (`docs/Raven_MF6_Groundwater_UserGuide.md` in
`raven_extra_docs_tests.tar.gz`) has the same list in its section 9.

## Licences

| Part | Copyright | Licence |
|---|---|---|
| Raven with the coupling (`bin/Raven`, `source/raven_code_src.tar.gz`) | the Raven Development Team; the coupling and the changes to Raven by Rezgar Arabzadeh | Artistic License 2.0 (`bin/LICENSE-Raven.txt`) |
| MODFLOW 6 library (`bin/libmf6.so`, unchanged) | U.S. Geological Survey | public domain; licence and disclaimer in `bin/NOTICE-MODFLOW6.txt` |
| Tests, tools and scripts | Rezgar Arabzadeh | Artistic License 2.0 |
| Manual, user guide and workshop texts | Rezgar Arabzadeh | Creative Commons Attribution 4.0 International |
| Liard River model inputs (`examples/Liard_groundwater/`) | their original authors | not relicensed; see `examples/Liard_groundwater/DATA_NOTICE.md` |
| Synthetic MODFLOW 6 model (`examples/Liard_existing_model/model/`) | Rezgar Arabzadeh | Artistic License 2.0 |

`NOTICE.md` in `raven_extra_docs_tests.tar.gz` gives the details. As the Artistic License 2.0 asks for modified
versions, the differences of `bin/Raven` from Raven 4.15 (v593) are documented file by file in the manual (Volume 2,
chapter "Developer guide and limitations", "Changes to existing Raven files") and in full in the branch `mf6-coupling` of
RavenHydroFramework. The modifications are offered to the Raven Development Team for inclusion in Raven under the
Artistic License 2.0. Raven and MODFLOW are the names of their projects; they are used here to describe compatibility
only.
