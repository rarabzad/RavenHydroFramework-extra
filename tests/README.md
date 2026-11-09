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

    python3 run_all.py            # every test below and one report, full mode (needs the MODFLOW 6 library; about 1.5 hours on two cores)
    python3 run_all.py --quick    # quick mode: fewer randomized set-ups, RAVEN_TEST_QUICK=1 for every script (about 35 minutes)
    python3 run_all.py --nolib    # only the checks that need no MODFLOW library (a few minutes)
    python3 run_all.py --only thiem,liard_grids

The report goes to `<scratch>/run_all_report.md`, the full output of every step to `<scratch>/run_all_logs/`; the exit
code is the number of failed steps. A check a script could not make prints "SKIP <what>: <why>"; the step's result then
reads "PASS (k skipped)" (or FAIL) and the report lists those lines. The full mode runs the rough-terrain suite with 400
seeds and all four unsaturated-zone methods, and again with three depth classes (`soilzone_rough_terrain_k3`). With
`--only`, the report keeps the results of the other steps from their last run (each row shows when it ran). The report
lists which steps give the numbers quoted in the manual.

Quick mode (`--quick`, or `RAVEN_TEST_QUICK=1` for a single script): `run_all.py` runs fewer randomized set-ups
(`fuzz_grids` 8 instead of 72, `fuzz_lakes` 4 instead of 24, `ext_fuzz` 6 instead of 20, the rough-terrain suite 40
seeds instead of 400, T7 30 days instead of 365). The scripts with a quick mode run shorter cases, each described in its
header: every soil-zone script (`spike_xmi.py`, `test_hillslope.py`, `test_surface_stores.py` and `test_plot_tool.py`
run the same case in both modes), `behaviour_check.py`, `budget_file.py`, `combinations.py`, `crs_inputs.py`,
`input_checks.py`, `mf6version_check.py`, and `existing/ext_exchanges.py`, `ext_inputs.py` and `restart_ext.py` (its
sub-daily case). The other scripts run their usual cases in both modes: `edge.py`, `liard_grids.py`, `mf6files_check.py`,
`mf6lib_check.py`, `restart_test.py`, `lake_test.py`, `dry_start.py`, the Thiem test, `existing/guards.py` and
`roundtrip.py`, the USGS examples, the C++ unit tests, `cmake_checks.py` and `budget_xcheck.py`. Measured on two cores: quick
mode about 35 minutes (up to an hour on a busy machine); full mode about 1.5 hours (up to 2.5 hours on a busy machine,
with the USGS example steps).

The coupled tests of the sections below start from the shipped Liard examples (`examples/Liard_groundwater`,
`examples/Liard_existing_model`), copy them into the scratch folder and edit the copies; the examples themselves are never
changed. Each run is checked with the audit tool shipped with the example (`examples/Liard_groundwater/tools_audit.py`).
The soil-zone tests (`soilzone/`, last section) instead build small synthetic models (`soilzone/sz_models.py`,
`rough_models.py`, `rough_ext.py`) and check every run with `soilzone/sz_check.py` (except T7, which uses the Liard
example and the audit tool).

## Unit tests (no MODFLOW needed)

| Test | What it checks | Run |
|---|---|---|
| `gridtest.cpp` | every grid generator: cells tile the domain, neighbours symmetric, Voronoi faces orthogonal, quadtree balanced, concave and cocircular clipping, cache round trip | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src gridtest.cpp $RAVEN_SRC/src/GWGrid.cpp $RAVEN_SRC/src/GWGeometry.cpp -o gridtest && ./gridtest` |
| `geomtest.cpp` + `geomtest_check.py` | polygon clipping against shapely, the equal-area projection against PROJ, bilinear raster sampling; `:InputCRS`: a UTM raster sampled at lon/lat points and UTM GeoJSON polygons and lines read back in lon/lat against PROJ, and the files refused (a projected `"crs"` member without `:InputCRS`, another projection, a lon/lat file with `:InputCRS`, projected coordinates or a projected raster without `:InputCRS`); `"crs"` members with geographic codes (EPSG:6318, 4979, 4267, a versioned URN, an opengis.net URL, OGC CRS83) read as lon/lat, a versioned URN of a projection read by its code, and a projection that is not built in (EPSG:3157) asking for its parameters, which are then accepted | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src geomtest.cpp $RAVEN_SRC/src/GWGeometry.cpp -o geomtest && python3 geomtest_check.py` |

## Checks without MODFLOW

Raven writes every MODFLOW input file (and `grid_cells.geojson`) before it loads the MODFLOW library, and in the
existing-model mode it copies and prepares the model first. With `RAVEN_MF6_LIB` pointing at a file that does not exist the
run stops, with a message, right after that, so these checks need only Raven, Python and FloPy:

| Script | What it checks |
|---|---|
| `cmake_checks.py [--src DIR] [--selftest]` | the MODFLOW 6 build integration of Raven's CMake (option `RAVEN_MF6`), offline, about a minute, no compiling of Raven: 1 Linux aarch64 default without tools falls back to OFF with a warning naming `-DRAVEN_MF6=OFF`; 2 that default survives a reconfigure and becomes SOURCE when the tools appear and the repository answers (a reachable stand-in repository); 3 RPATH (private library from the build tree and a moved install, `$ORIGIN`); 4 PATH mode installs a symlinked or renamed library as `libmf6.so`; 5 `libmf6_version.txt` and package name (unknown for PATH, `meson.build` version for zips and sources); 6 offline options name the mode, other-mode options reported as ignored, unpinned zip warned; 7 meson gets `FC` (renamed link); 8 meson without a readable version named; 9 `DESTDIR` staged install gets `libgfortran.so.5`; 10 no git (default falls back, SOURCE stops, SOURCE_URL needs none); 11 replaced zip unpacked again, unchanged one not (sentinel); 12 Windows AMD64/ARM64 (emulated); 13 package version from a `v6.7.2.tar.gz` source URL, unpinned zip "not checked"; 14 a wrong `RAVEN_MF6_ZIP_SHA256` stops (local and downloaded zips); 15 offline default: tools but an unreachable repository fall back at configure time to PREBUILT or OFF, a reachable one gives SOURCE; 16 single-configuration generators default to Release; 17 a MODFLOW version below 6.5.0 (as `RAVEN_MF6_VERSION`, in a zip's or source folder's `meson.build`, in an archive name) stops the configure, 6.7.0 warns; 18 runtime bundling for macOS (Mach-O stand-ins, `@rpath` chains, `@loader_path`, signing) and Windows (stand-in `objdump`/`dumpbin`, recursive DLL imports), emulated on Linux; 19 messages for a folder as `RAVEN_MF6_PATH` and a malformed SHA-256; 20 PATH mode on Linux: a library without a run path gets `$ORIGIN` from patchelf (or a warning without it); 21 `RAVEN_MF6=OFF`: configure and install say that Raven is installed alone; 22 the offline fallback to OFF names the network when the source tools are installed. `--selftest` puts the defect each check guards against back into a copy of the source and shows that the check then fails |
| `mf6version_check.py` | Raven's MODFLOW 6 version guard with a stand-in library (`mf6version_stub.c`, compiled by the script): older than 6.5.0 refused, other versions, no version and unreadable versions (quoted) one warning, 6.8.1 with suffixes silent; a real 2-day run when a library is configured |
| `mf6lib_check.py [--unit]` | part 0 (`--unit`, no library needed): `tools/get_mf6.py` platform choice with faked platforms (Windows ARM64 and Linux aarch64 stop and point to `-DRAVEN_MF6=SOURCE`/`PATH`, `--zip` accepts win64 on Windows ARM64 with a note, Intel Mac needs `--version 6.6.3`); then getting and finding the MODFLOW 6 library: `tools/get_mf6.py --zip` unpacks a release-style zip (with version file, idempotent); Raven with no setting finds the library in `lib/mf6` one folder up and next to its executable; with none, the message lists the places searched |
| `mf6files_check.py [OLD_RAVEN]` | 16 generated set-ups (every grid type, rotation, refinement, layers by elevation, aquicludes, boundaries, wells, lakes, imported cells): FloPy reads the model; cells valid and not overlapping; DIS origin and rotation, DISV/DISU vertices, DISU symmetry and face angles against the cell file; no vertical connection through an aquiclude; drains inside the top cell; boundary polygons select the right cells. With an older Raven as argument, also shows which input files changed |
| `crs_inputs.py --nolib` | the input checks of `crs_inputs.py` (below): projected GeoJSON or rasters without `:InputCRS`, files in another projection than `:InputCRS`, wells given by X and Y without `:InputCRS`, and with `:InputCRS` a DEM, bedrock raster, HRU file or boundary line left in lon/lat stop Raven while it reads the geometry |
| `run_all.py --selftest` (`run_all_selftest`) | the pass criteria of `run_all.py` fail on outputs with failed or unconverged runs, `test_restart.py`'s last line fails when RS2-RS4 fail, and the restart, lake, Thiem, Liard-grid and existing-model restart scripts end with a failing count line and exit code 1 when Raven fails |
| `soilzone/test_plot_tool.py` (`soilzone_plot_tool`) | `tools/plot_soilzone.py` with soil-zone columns over specified heads: their exchange counts in the choice of HRUs and is drawn per HRU and model-wide |
| `edge.py --nolib` | the faulty and unusual set-ups of `edge.py` (below), judged by the message Raven stops with; valid existing-model preparations checked in detail (stress periods split at the start date, restart renumbering, original model untouched) |

## Generated models (Raven builds the groundwater model)

The smaller grid tests use subbasin 52 of the Liard example (`testconfig.sb52`); `testconfig.grid_base()` builds their base
case once (3 km cells, half-day steps, a pumping and a monitoring well).


| Script | What it checks |
|---|---|
| `thiem/run_thiem.py`, `thiem/fit_thiem.py` | a well pumping a confined aquifer against the exact Thiem solution, on every grid type and several cell sizes; `quad.py` checks symmetry, `ownsolve.py` solves a DISU model independently |
| `restart_test.py` | a 60-day run against 30 days restarted from `solution.rvc`, on every grid type; each grid must finish with the deviation below 1e-4, no unconverged step and exact accounts (last line "restart grids: k of 5 pass", exit code 1 otherwise) |
| `lake_test.py` | `:GridRefinement LAKES` (and `POLYGONS`) around a reservoir on each refinable grid: cell sizes near the lake, water accounts, reservoir identity, no unconverged step ("lake runs: k of 5 pass", exit code) |
| `liard_grids.py [--table]` | the Liard example on every grid type for two years, and the manual's grid table (cells, run time, NSE, seepage, rivers); every grid must converge with exact accounts ("liard grids: k of 5 ...", exit code) |
| `behaviour_check.py` | a 50 km² reservoir with seepage and a pumping well on the full Liard example for two years (reservoir identity, exact accounts), and the same set-up as a two-member ensemble: each member equal to the single run in GWBudget, GWHeads, Hydrographs, ReservoirStages and GWHRUState. Quick mode: 120 days |
| `input_checks.py` | strict reading of the inputs: malformed numbers in the `.rvg` (`:GridCellSize 2,000.0`, `2km`, `HEAD H1146`, `1146.85m`, ...) and cell or refinement sizes giving more than 1e7 cells stop before the grid is built, naming the command and the value; `:WellFlowRate` in m3/s and L/s converted to m3/d, other units of well and head series stop; an existing model's package named like Raven's (`DRN_RAVEN`) stops with Raven's message, a recharge package so named and taken over runs. Quick mode: 2-day runs |
| `edge.py [--nolib]` | faulty set-ups (each must stop with a message naming the problem) and unusual valid ones (each must run), for generated and existing models |
| `fuzz_grids.py SEED N [lakes]` | N random set-ups of the subbasin-52 model over every grid type, with wells, boundaries, reservoirs, wetlands and lake refinement, checked with the accounting identities, MODFLOW's list-file budget and restarts; `lakes` puts a reservoir and lake refinement in every set-up |
| `crs_inputs.py [--nolib]` | `:InputCRS`: the Liard example with every geometry and raster input in UTM zone 10 against the lon/lat example. Without rasters the grid, the HRU-cell overlaps (within 1e-6 of a cell), the monitoring well's cell (given by X and Y), the GHB and CHD cells (both non-zero: the GHB head lies above its cells, the CHD lake is placed by a `:BoundaryHead` series) and the outputs agree (Hydrographs and HRU states within 1e-6, GWBudget within 1e-5); with the DEM and bedrock resampled to UTM the model top agrees within the resampling (mean below 0.05 m). Input checks as in `--nolib`; with `RAVEN_EXE_REF` the lon/lat run equals the reference build |
| `dry_start.py` | the warning for a layer that starts completely dry (Liard with INITIAL_HEAD_DEPTH 25 m: layer 2 named, summary line), none with `:GWInitialization STEADY_STATE` or for the example as shipped (with `RAVEN_EXE_REF`: equal to the reference build) |
| `combinations.py` | option combinations: small synthetic models across a matrix (exchanges ET, river, surface stores, reservoir, well, GHB, CHD together and alone; plain, dry top cells, negative recharge, rising water table; CONCEPTUAL and `:SoilZone PHYSICAL` with `RICHARDS`/`KINEMATIC`/`LAG` and 1 or 3 depth classes; generated, existing with and without NEWTON, feet/seconds); every run: MODFLOW, recharge, soil-zone and column identities, Raven's balance, river, surface-store and reservoir books, run totals, no HDRY or NaN, no groundwater into surface stores while the water table is below the ground; quick 237 runs of 8 days, full a larger matrix of 15 days with half-day steps |
| `budget_file.py` | `:WriteGWBudgetFile`: FloPy reads `mf6/gwf.cbc` (FLOW-JA-FACE, specific discharge, saturation, every package each step), its totals equal `GWBudget.csv`, `gwf.porosity` holds each cell's class POROSITY; without the option the solution and the `mf6` folder are unchanged (and, with `RAVEN_EXE_REF`, identical to the reference build); `tools/make_prt.py` builds and runs a PRT simulation through the MODFLOW 6 library, forward and backward; the option is refused with an existing model |
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
| `restart_ext.py` | restarts inside a stress period and before a change of well rates against a continuous run; a restart at 12:00 with 6-hour time steps; each comparison must finish with no unconverged step and exact accounts ("existing-model restarts: k of 3 pass", exit code) |
| `ext_exchanges.py` | water-table ET (`EVT_RAVEN`), `:SurfaceWaterExchange` (`SWX_RAVEN`) and `:ReservoirExchange` (`RES_RAVEN`) with an existing model: flows non-zero, water-table ET at most the unmet PET, accounting identities, the packages' flows in MODFLOW's budget file and list file equal to `GWBudget.csv`, the feet/seconds model equal to the metres/days one, a restart with reservoir seepage in transit, a kept EVT package with EXTINCTION_DEPTH refused; dry and specified-head cells: water-table ET in a model without NEWTON whose top cells dry (equal to MODFLOW's budget file, no HDRY), a reservoir over cells that become specified heads (all, or 2 of 5) and over dry cells without NEWTON (reservoir books exact, seepage not delivered returned and booked); with `RAVEN_EXE_REF`, a run without these options identical to the reference build |
| `ext_inputs.py` | TDIS period data in an OPEN/CLOSE file (same result as inline, on a later start); wells driven by a TS6 time series, restarted between two of its entries, against a continuous run; TAS6 still refused on a later start |
| `fuzz_ext.py SEED N` | random set-ups (units, linking method, stream mapping, seepage, ET, coverage, restarts) against the accounting identities and MODFLOW's budget file |
| `crs_check.py` + `crstest.cpp` | the built-in map projections against PROJ (build `crstest` as described in the script) |
| `usgs_sagehen.py PATH` | the Sagehen Creek model of the MODFLOW 6 examples (a real watershed: Newton, UZF, SFR, drains, water mover, 399 daily periods): UZF taken over (mover entries removed), seepage on and off, the published and a tight solver, a restart inside the daily periods, a stream package that feeds the mover (refused), UZF kept |
| `usgs_capture.py PATH` | the stream-capture model of the MODFLOW 6 examples (steady state, seconds, RIV stream package, wells): one steady period stretched over Raven's run, exact accounts, a restart |
| `usgs_common.py` | helper: lays the Liard HRUs of subbasin 52 over an example model's active cells (:OverlapWeights) |
| `setup_case.py DEST MODELDIR` | helper: a Liard case coupled to one of the synthetic models |
| `run_standalone.py FOLDER` | helper: runs a MODFLOW 6 simulation through the library alone |

## Soil zone (`soilzone/`)

The tests of `:SoilZone PHYSICAL` (manual, chapter "Verification", sections "The soil zone" and "Rough terrain"). Each
script supports the quick mode (`RAVEN_TEST_QUICK=1`, which `run_all.py --quick` sets) and the full mode: in quick mode the
scripts run shorter cases (for example T7 30 days instead of 365, the restart hillslope 60 + 60 days instead of 150 + 150,
T4 without the hourly step), and the scripts whose cases take a few seconds (`spike_xmi.py`, the T2/T3 hillslope,
`test_surface_stores.py`, `test_plot_tool.py`) run the same case in both modes; each script's header lists its quick mode. Every coupled run is checked by `sz_check.py`
at the standard limits (`sz_check.ID_LIMITS`: recharge identity 5e-9, soil-zone and unsaturated-zone identities 1e-8 from
the first step, the negative recharge not held), MODFLOW's and Raven's balance, and no shortfall.

**Building blocks**

| Script (run_all step) | Tests |
|---|---|
| `soilzone_unit.cpp` (`soilzone_unit`) | the interface functions of `GWSoilZone.cpp`: filling and draining, sub-grid level and inverse, contact weights, flux derivatives, local solve, Robin slope; 20 000 random cases |
| `sz_check.py` (`soilzone_check_selftest`) | self-test of the column identity (exact books 0; a 1e-4 m3/step leak fails) |
| `spike_xmi.py` (`soilzone_spike`) | three checks that values written through XMI between outer iterations reach MODFLOW's solver |
| `vadose_unit.cpp`, `vadose_ref.py` (`soilzone_vadose_unit`) | the Richards column against independent solutions (retention, steady infiltration, mass, perched water, drainage against a method-of-lines reference) and the capillary-rise relation |

**The column, the hillslope and the Liard model**

| Script (run_all step) | Tests |
|---|---|
| `test_column.py` (`soilzone_column`) | T1/T1b: flat column, the water table rising into the soil zone (50 / 125 mm/d below the base, 50 inside, full on day 41) |
| `test_hillslope.py --selftest` (`soilzone_hillslope`) | T2/T3: hillslope wetting and drying against a MODFLOW-only reference (`sz_reference.py`); T3 drying checks and their self-test |
| `test_dynamics.py` (`soilzone_dynamics`) | T4 time step (1 d, 6 h, 1 h), T5 stiff contact (iterated vs explicit), SG sub-grid saturated fraction |
| `test_restart.py` (`soilzone_restart`) | RS1 the hillslope, 300 d against 150 + 150 d (`:GWSoilZoneColumns`); RS2 an existing model with specified heads, 10 d against 5 + 5; RS3 seepage holding the lowest soil layer above capacity (no `:SoilZone PHYSICAL`); RS4 KINEMATIC and LAG columns restored as written (`--rs3rs4`: only these two) |
| `test_liard_physical.py [days]` (`soilzone_liard`) | T7: the Liard example with `:SoilZone PHYSICAL`, one year (quick mode: 30 days) |

**The water table in every position, and existing models**

| Script (run_all step) | Tests |
|---|---|
| `test_water_table.py` (`soilzone_water_table`) | P1-P10: delay through a deep unsaturated zone, capillary rise, a water table through the column, restarts, LAGGED timing, classes, specified heads, restart with classes, the shortest column, upward flows out of a lower cell |
| `test_sz_existing.py` (`soilzone_existing`) | X1-X8: the soil zone with an existing MODFLOW model (round trip, feet and seconds, specified heads, outputs, NEWTON required, specific yield; a steady model takes SPEC_YIELD of `:SoilZoneAquiferClass`) |

**The interface and MODFLOW's side**

| Script (run_all step) | Tests |
|---|---|
| `test_interface_stiff.py` (`soilzone_interface_stiff`) | S1-S8: low-K_v top layer, kink drain, supply limits, tiny budgets and outer limits, the connection test |
| `test_confined_wet.py` (`soilzone_confined_wet`) | W1-W12: confined layers below their bottoms, drained columns, heads far outside the model and the stop rule (W4, W6, W11 reported as skipped) |
| `test_columns_mf6.py` (`soilzone_columns_mf6`) | M1-M4: drained columns kept wet, a column delivers its inflow, CONCEPTUAL against a reference build (`RAVEN_EXE_REF`) |
| `test_mf6_budget.py` (`soilzone_mf6_budget`) | B1-B9: MODFLOW's residual and gross flow as Raven books them, dated warnings, guard counts, B8 unconverged steps without a soil zone (only MODFLOW's negative residual withheld; the row residual is the withheld volume, also with rivers: the Liard example), B9 `GWSoilExchange.csv` per HRU sums to `GWBudget.csv` (specified heads included) |
| `test_robustness.py` (`soilzone_robustness`) | R1-R13 hard cases (stiff column, one HRU over ten cells, explicit mode, late updates, frozen boundaries, unconverged steps), R14-R22 negative recharge (N1-N9: N8 the hand-back of vanishing columns in a negative step, N9 the top-cell limit with depth classes), R15b a negative-recharge cut on a draining soil zone |
| `test_surface_stores.py` (`soilzone_surface_stores`) | SW1-SW3: `:SurfaceWaterExchange` on `DEPRESSION` of `:SoilZone PHYSICAL` HRUs: the stores' bed at the ground (model top + soil-zone thickness), no discharge into the stores while every water table is below the ground, generated and existing model, a control with the water table above the ground |

**Unsaturated-zone methods, depth classes and steady starts**

| Script (run_all step) | Tests |
|---|---|
| `test_vz_kinematic.py`, `vadose_kw_unit.cpp` (`soilzone_vz_kinematic`) | `:SoilZoneVadose KINEMATIC` (unit and model tests K1-K8); K9: a column leak of 1e-5 m3 per step written into a run's `GWBudget.csv` fails the script's checks |
| `test_vz_lag.py`, `vadose_lag_unit.cpp` (`soilzone_vz_lag`) | `:SoilZoneVadose LAG` (unit tests, L1-L6, cost, byte identity); L7: a column leak of 1e-5 m3 per step written into a run's `GWBudget.csv` fails the script's checks |
| `test_vz_classes.py` (`soilzone_vz_classes`) | C1-C11: depth classes of the unsaturated columns; C9 RT20 with three classes; C10 hotstart after a dropped class column; C11 the columns' upflow and the rise from the water table share one source-cell limit |
| `test_vz_initial.py` (`soilzone_vz_initial`) | I1, I2, I4-I6: `:SoilZoneVadoseInitialFlux` steady starts (for (1-F) q; backed-up columns), hotstarts, the columns' balance from step 1 |

**Inputs and hotstarts**

| Script (run_all step) | Tests |
|---|---|
| `test_inputs.py` (`soilzone_inputs`) | I1-I19: missing HYDRAUL_COND, short `:SoilZoneIteration`, last `:SoilZone` counts, ignored options, mismatched and reordered hotstart columns, `.rvc` blocks without groundwater, surface exchange on a soil layer, damaged `:GWHeads` header, `:StartTime` under valgrind, orphan `:BoundaryHead`/`:WellFlowRate`, options that do nothing, messages, age tracer across chained hotstarts (I14, ages within 2e-4 d plus 1e-5 of the age); I15 chains across year boundaries; I16 age tracer from a spin-up without it; I17 EnKF members' extra `.rvt` series; I18 damaged soil-zone hotstart values; I19 `:Transport` in a coupled run stops; I20 a head boundary placed by its `:BoundaryHead` series, the warning for a boundary left with no cells |

**Rough terrain**

| Script (run_all step) | Tests |
|---|---|
| `test_rough_terrain.py` (`soilzone_rough_terrain`, `_k3`) | regression cases RT1-RT20 and random rough-terrain seeds (quick 40, full 400) with all four methods; `_k3` with three depth classes |

A comparison with GSFLOW's Sagehen model is not part of the suite; the soil zone with existing models is covered by X1-X8
and the existing-model cases of the rough-terrain suite.
