# Tests

The tests used for the verification in the manual (chapter "Verification"). They run from any checkout: every script
reads its settings from `testconfig.py`, which finds the repository from its own location.

## Setting up

The tests run Raven from a separate RavenHydroFramework checkout (with the MODFLOW 6 coupling). Put the two side by
side, build Raven, and get the MODFLOW 6 library:

    <folder>/RavenHydroFramework         cmake -S . -B build && cmake --build build   (or make in src/)
    <folder>/RavenHydroFramework-extra   this repository
    python3 tools/get_mf6.py          # MODFLOW 6 library into RavenHydroFramework/lib/mf6
    pip install numpy pandas shapely pyproj flopy

Optional settings (see `testconfig.py`): `RAVEN_SRC` (the Raven checkout, if not beside this one), `RAVEN_EXE`,
`RAVEN_MF6_LIB`, `RAVEN_TEST_WORK` (scratch folder; default `tests/_work`), `RAVEN_EXE_REF` (a reference build for the
byte-identity checks; without it they are reported as skipped). `RAVEN_SRC` is needed whenever Raven's source is not in
`../RavenHydroFramework`: the C++ unit tests (gridtest, geomtest, crs, soilzone_unit, the vadose units) and the CMake checks
compile or configure it, also when `RAVEN_EXE` names a built Raven. With the release package, whose source archives
unpack as `raven-soil-zone/` and `raven-mf6-extra/` in one folder `<dir>`:

    cd <dir>/raven-mf6-extra/tests
    RAVEN_SRC=<dir>/raven-soil-zone RAVEN_EXE=<pkg>/bin/Raven RAVEN_MF6_LIB=<pkg>/bin/libmf6.so python3 run_all.py --quick

## Everything at once

    python3 run_all.py            # every test below and one report, full mode (needs the MODFLOW 6 library; about an hour on one core)
    python3 run_all.py --quick    # quick mode: smaller randomized rounds, RAVEN_TEST_QUICK=1 for every script
    python3 run_all.py --nolib    # only the checks that need no MODFLOW library (a few minutes)
    python3 run_all.py --only thiem,liard_grids

The report goes to `<scratch>/run_all_report.md`, the full output of every step to `<scratch>/run_all_logs/`; the exit
code is the number of failed steps. A check a script could not make prints "SKIP <what>: <why>"; the step's result then
reads "PASS (k skipped)" (or FAIL) and the report lists those lines. The full mode runs the rough-terrain suite with 400
seeds and all four unsaturated-zone methods, and again with three depth classes (`soilzone_rough_terrain_k3`). With `--only`, the report keeps the earlier results of the other steps (each row shows
when it ran). The report lists which steps give the numbers quoted in the manual.

Every coupled test starts from the shipped Liard examples (`examples/Liard_groundwater`, `examples/Liard_existing_model`),
copies them into the scratch folder and edits the copies; the examples themselves are never changed. Each run is checked
with the audit tool shipped with the example (`examples/Liard_groundwater/tools_audit.py`).

## Unit tests (no MODFLOW needed)

| Test | What it checks | Run |
|---|---|---|
| `gridtest.cpp` | every grid generator: cells tile the domain, neighbours symmetric, Voronoi faces orthogonal, quadtree balanced, concave and cocircular clipping, cache round trip | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src gridtest.cpp $RAVEN_SRC/src/GWGrid.cpp $RAVEN_SRC/src/GWGeometry.cpp -o gridtest && ./gridtest` |
| `geomtest.cpp` + `geomtest_check.py` | polygon clipping against shapely, the equal-area projection against PROJ, bilinear raster sampling | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src geomtest.cpp $RAVEN_SRC/src/GWGeometry.cpp -o geomtest && python3 geomtest_check.py` |

## Checks without MODFLOW

Raven writes every MODFLOW input file (and `grid_cells.geojson`) before it loads the MODFLOW library, and in the
existing-model mode it copies and prepares the model first. With `RAVEN_MF6_LIB` pointing at a file that does not exist the
run stops, with a message, right after that, so these checks need only Raven, Python and FloPy:

| Script | What it checks |
|---|---|
| `cmake_checks.py [--src DIR] [--selftest]` | the MODFLOW 6 build integration of Raven's CMake (option `RAVEN_MF6`), offline, about a minute, no compiling of Raven: 1 Linux aarch64 default without tools falls back to OFF with a warning naming `-DRAVEN_MF6=OFF`; 2 that default survives a reconfigure and becomes SOURCE when the tools appear; 3 RPATH (private library from the build tree and a moved install, `$ORIGIN`); 4 PATH mode installs a symlinked or renamed library as `libmf6.so`; 5 `libmf6_version.txt` and package name (unknown for PATH, `meson.build` version for zips and sources); 6 offline options name the mode, other-mode options reported as ignored, unpinned zip warned; 7 meson gets `FC` (renamed link); 8 meson without a readable version named; 9 `DESTDIR` staged install gets `libgfortran.so.5`; 10 no git (default falls back, SOURCE stops, SOURCE_URL needs none); 11 replaced zip unpacked again, unchanged one not (sentinel); 12 Windows AMD64/ARM64 (emulated); 13 package version from a `v6.7.2.tar.gz` source URL, unpinned zip "not checked"; 14 a wrong `RAVEN_MF6_ZIP_SHA256` stops (local and downloaded zips). `--selftest` puts each check's bug back into a copy of the source and shows that the check then fails |
| `mf6version_check.py` | Raven's MODFLOW 6 version guard with a stand-in library (`mf6version_stub.c`, compiled by the script): older than 6.5.0 refused, other versions, no version and unreadable versions (quoted) one warning, 6.8.1 with suffixes silent; a real 2-day run when a library is configured |
| `mf6lib_check.py [--unit]` | part 0 (`--unit`, no library needed): `tools/get_mf6.py` platform choice with faked platforms (Windows ARM64 and Linux aarch64 stop and point to `-DRAVEN_MF6=SOURCE`/`PATH`, `--zip` accepts win64 on Windows ARM64 with a note, Intel Mac needs `--version 6.6.3`); then getting and finding the MODFLOW 6 library: `tools/get_mf6.py --zip` unpacks a release-style zip (with version file, idempotent); Raven with no setting finds the library in `lib/mf6` one folder up and next to its executable; with none, the message lists the places searched |
| `mf6files_check.py [OLD_RAVEN]` | 16 generated set-ups (every grid type, rotation, refinement, layers by elevation, aquicludes, boundaries, wells, lakes, imported cells): FloPy reads the model; cells valid and not overlapping; DIS origin and rotation, DISV/DISU vertices, DISU symmetry and face angles against the cell file; no vertical connection through an aquiclude; drains inside the top cell; boundary polygons select the right cells. With an older Raven as argument, also shows which input files changed |
| `edge.py --nolib` | the faulty and unusual set-ups of `edge.py` (below), judged by the message Raven stops with; valid existing-model preparations checked in detail (stress periods split at the start date, restart renumbering, original model untouched) |

## Generated models (Raven builds the groundwater model)

The smaller grid tests use subbasin 52 of the Liard example (`testconfig.sb52`); `testconfig.grid_base()` builds their base
case once (3 km cells, half-day steps, a pumping and a monitoring well).


| Script | What it checks |
|---|---|
| `thiem/run_thiem.py`, `thiem/fit_thiem.py` | a well pumping a confined aquifer against the exact Thiem solution, on every grid type and several cell sizes; `quad.py` checks symmetry, `ownsolve.py` solves a DISU model independently |
| `restart_test.py` | a 60-day run against 30 days restarted from `solution.rvc`, on every grid type |
| `lake_test.py` | `:GridRefinement LAKES` (and `POLYGONS`) around a reservoir on each refinable grid: cell sizes near the lake, water accounts, reservoir identity |
| `liard_grids.py [--table]` | the Liard example on every grid type for two years, and the manual's grid table (cells, run time, NSE, seepage, rivers) |
| `behaviour_check.py` | a 50 km² reservoir with seepage and a pumping well on the full Liard example for two years (reservoir identity, exact accounts), and the same set-up as a two-member ensemble (members identical to the single run) |
| `edge.py [--nolib]` | faulty set-ups (each must stop with a message naming the problem) and unusual valid ones (each must run), for generated and existing models |
| `fuzz_grids.py SEED N [lakes]` | N random set-ups of the subbasin-52 model over every grid type, with wells, boundaries, reservoirs, wetlands and lake refinement, checked with the accounting identities, MODFLOW's list-file budget and restarts; `lakes` puts a reservoir and lake refinement in every set-up |
| `budget_xcheck.py OUT [OUT ...]` | the coupler's budget against MODFLOW's own list-file budget, package by package (read by package name from the list file), for any output folders |

## Existing MODFLOW 6 models (`existing/`)

The USGS example tests need the MODFLOW 6 examples (`mf6examples.zip` from
https://github.com/MODFLOW-ORG/modflow6-examples/releases, about 21 MB); `PATH` is the zip, its unpacked folder or the
model's folder. `run_all.py` runs them when `RAVEN_USGS_EXAMPLES` points there.

The synthetic "existing" model of the Liard area (UTM zone 10N, rotated grid, four layers, monthly periods, wells, rivers,
a head boundary, its own recharge and ET) is built on first use by `make_ext_model.py` (FloPy and pyproj), in metres and
days and in feet and seconds, with an independent `:OverlapWeights` table from `make_weights.py`.

| Script | What it checks |
|---|---|
| `guards.py` | faulty set-ups of the existing-model mode; each must stop with a message naming the problem |
| `roundtrip.py` | a model Raven built, re-imported as an existing model, must reproduce Raven's own run |
| `restart_ext.py` | restarts inside a stress period and before a change of well rates against a continuous run |
| `fuzz_ext.py SEED N` | random set-ups (units, linking method, stream mapping, seepage, ET, coverage, restarts) against the accounting identities and MODFLOW's budget file |
| `crs_check.py` + `crstest.cpp` | the built-in map projections against PROJ (build `crstest` as described in the script) |
| `usgs_sagehen.py PATH` | the Sagehen Creek model of the MODFLOW 6 examples (a real watershed: Newton, UZF, SFR, drains, water mover, 399 daily periods): UZF taken over (mover entries removed), seepage on and off, the published and a tight solver, a restart inside the daily periods, a stream package that feeds the mover (refused), UZF kept |
| `usgs_capture.py PATH` | the stream-capture model of the MODFLOW 6 examples (steady state, seconds, RIV stream package, wells): one steady period stretched over Raven's run, exact accounts, a restart |
| `usgs_common.py` | helper: lays the Liard HRUs of subbasin 52 over an example model's active cells (:OverlapWeights) |
| `setup_case.py DEST MODELDIR` | helper: a Liard case coupled to one of the synthetic models |
| `run_standalone.py FOLDER` | helper: runs a MODFLOW 6 simulation through the library alone |
