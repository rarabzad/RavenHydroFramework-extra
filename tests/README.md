# Tests

The tests used for the verification in the manual (chapter "Verification"). They run from any checkout: every script
reads its settings from `testconfig.py`, which finds the repository from its own location.

## Setting up

The tests run Raven from a separate RavenHydroFramework checkout (with the MODFLOW 6 coupling). Put the two side by
side, build Raven, and get the MODFLOW 6 library:

    <folder>/RavenHydroFramework         git clone -b mf6-coupling https://github.com/rarabzad/RavenHydroFramework.git
                                         cmake -S . -B build && cmake --build build   (or make in src/)
    <folder>/RavenHydroFramework-extra   this repository (git clone https://github.com/rarabzad/RavenHydroFramework-extra.git)
    python3 tools/get_mf6.py          # MODFLOW 6 library into RavenHydroFramework/lib/mf6
    pip install numpy pandas shapely pyproj flopy

Optional settings (see `testconfig.py`): `RAVEN_SRC` (the Raven checkout, if not beside this one), `RAVEN_EXE`,
`RAVEN_MF6_LIB`, `RAVEN_TEST_WORK` (scratch folder; default `tests/_work`), `RAVEN_EXE_REF` (a reference build for the
byte-identity checks; without it they are reported as skipped; their outputs must be byte-identical, and `solution.rvc`,
which a coupled run writes with 17 significant digits, the same state to the digits either file holds:
`testconfig.rvc_same`). `RAVEN_SRC` is needed whenever Raven's source is not in
`../RavenHydroFramework`: the C++ unit tests (gridtest, geomtest, crs, soilzone_unit, the vadose units) and the CMake checks
compile or configure it, also when `RAVEN_EXE` names a built Raven. With the release package, whose source archives
unpack as `raven-soil-zone/` and `raven-mf6-extra/` in one folder `<dir>`:

    cd <dir>/raven-mf6-extra/tests
    RAVEN_SRC=<dir>/raven-soil-zone RAVEN_EXE=<pkg>/bin/Raven RAVEN_MF6_LIB=<pkg>/bin/libmf6.so python3 run_all.py --quick

## Everything at once

    python3 run_all.py            # every test below and one report, full mode (needs the MODFLOW 6 library; about 2.5 hours on two cores)
    python3 run_all.py --quick    # quick mode: fewer randomized set-ups, RAVEN_TEST_QUICK=1 for every script (about 50 minutes)
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
seeds instead of 400, LP1 30 days instead of 365). The scripts with a quick mode run shorter cases, each described in its
header: every soil-zone script (`spike_xmi.py`, `test_hillslope.py`, `test_surface_stores.py` and `test_plot_tool.py`
run the same case in both modes), `behaviour_check.py`, `budget_file.py`, `combinations.py`, `crs_inputs.py`, `geotiff/geotiff_check.py`,
`input_checks.py`, `mf6version_check.py`, `existing/ext_exchanges.py`, `ext_inputs.py` and `restart_ext.py` (its
sub-daily case), and `tutorials_check.py` (the step `tutorials`: it rebuilds the tutorials and compares every number,
excerpt and file they quote; quick mode keeps the committed values of the 20-year Liard run and the calibration). The other scripts run their usual cases in both modes: `edge.py`, `liard_grids.py`, `mf6files_check.py`,
`mf6lib_check.py`, `restart_test.py`, `lake_test.py`, `dry_start.py`, the Thiem test, `existing/guards.py` and
`roundtrip.py`, the USGS examples, the C++ unit tests, `cmake_checks.py` and `budget_xcheck.py`. Measured on two cores: quick
mode about 50 minutes, the tutorials step about 5 of them (up to an hour and a quarter on a busy machine); full mode about
2.5 hours, the tutorials step about an hour of them (up to 3.5 hours on a busy machine, with the USGS example steps).

The coupled tests of the sections below start from the shipped Liard examples (`examples/Liard_groundwater`,
`examples/Liard_existing_model`), copy them into the scratch folder and edit the copies; the examples themselves are never
changed. Each run is checked with the audit tool shipped with the example (`examples/Liard_groundwater/tools_audit.py`).
The soil-zone tests (`soilzone/`, last section) instead build small synthetic models (`soilzone/sz_models.py`,
`rough_models.py`, `rough_ext.py`) and check every run with `soilzone/sz_check.py` (except LP1, which uses the Liard
example and the audit tool).

## Unit tests (no MODFLOW needed)

| Test | What it checks | Run |
|---|---|---|
| `gridtest.cpp` | every grid generator: cells tile the domain, neighbours symmetric, Voronoi faces orthogonal, quadtree balanced, concave and cocircular clipping, cache round trip; the grid-size stop names its cause (cell size, refinement, HRU-mesh seeds, imported grid, existing model) | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src gridtest.cpp $RAVEN_SRC/src/GWGrid.cpp $RAVEN_SRC/src/GWGeometry.cpp $RAVEN_SRC/src/GWGeoTIFF.cpp -o gridtest && ./gridtest` |
| `geomtest.cpp` + `geomtest_check.py` | polygon clipping against shapely, the equal-area projection against PROJ, bilinear raster sampling (and its no-data margin of half a cell); `:InputCRS`: a UTM raster sampled at lon/lat points and UTM GeoJSON polygons and lines read back in lon/lat against PROJ, and the files refused (a projected `"crs"` member without `:InputCRS`, another projection, a lon/lat file with `:InputCRS`, projected coordinates or a projected raster without `:InputCRS`); `"crs"` members with geographic codes (EPSG:4326, 4269, 4617, 6318, 4979, 4267, a versioned URN, an opengis.net URL, OGC CRS83) read as lon/lat, a versioned URN of a projection read by its code, and projections that are not built in (EPSG:3157, and 4647, a projected code among the geographic ones) asking for their parameters, which are then accepted; EPSG:2227 (US survey feet) refused; a file with a UTF-8 byte-order mark read; `:InputCRS` parameters read strictly (letters or units in a number, surplus or missing values, an unknown ellipsoid, `EPSG:32610x` refused; ALBERS and LCC parameters that define no cone refused); ALBERS and LCC against PROJ, also with the origin at the pole opposite the cone; GeoJSON coordinates that are strings, `null`, `true` or too large refused naming the feature, ring and vertex, `NaN` and `Infinity` coordinates refused, hexadecimal and leading zeros invalid JSON, a feature without `"properties"` refused only where an ID field is read; IDs that are `null`, `true`, `"7abc"`, `2.6`, `"7.5"` or `""` refused (`"7"`, `" 7 "`, `"7.0"` and `7.0` read; features of other geometry types skipped before their ID), mis-nested coordinates and a vertex `[1]` refused, `NaN`/`Infinity` attributes and `\u`-escaped field names read, text after the root object refused | `g++ -std=c++11 -O2 -I$RAVEN_SRC/src geomtest.cpp $RAVEN_SRC/src/GWGeometry.cpp $RAVEN_SRC/src/GWGeoTIFF.cpp -o geomtest && python3 geomtest_check.py` |
| `geotiff/geotiff_unit.cpp` + `geotiff/geotiff_check.py --nolib` | the GeoTIFF reader: 228 fixtures with twins written by GDAL and tifffile (`geotiff/fixtures`, made by `tools/dev/make_geotiff_fixtures.py`: every compression, predictor, sample type, byte order, strips and tiles, classic and BigTIFF, NODATA, PixelIsPoint, EPSG codes, GDAL's band scale and offset) against their ESRI ASCII twins, value for value and sample for sample; rectangular pixels against a bilinear sampler in the script; internal masks (no data where the mask is 0); a warning for -9999 pixels without a NODATA tag and for an unknown band unit; band units matched as whole words (`m (Admiralty datum)` and `in metres` read as metres, `feet above sea level` and `in` refused; fused US-foot spellings `ftUS`, `usft`, `USfeet`, `sft` refused; `'`, `?` and `µm` an unknown unit); ESRI ASCII grids with GDAL's `dx`/`dy` header and `NODATA_value nan` sampled as their twins, and with surplus, wrapped or missing values, an unknown header key, a key given twice, `xllcorner` with `xllcenter` or a value that is not a number refused; 34 unsupported, corrupt or truncated files (also FillOrder 2, units other than metres, feet vertical systems, prime meridians other than Greenwich, also given by their longitude or by the datum, a projected code in feet without its units key, a band unit in feet) and an oversized one refused with their reasons; the EPSG code against `:InputCRS`; the EPSG longitude/latitude table (4647 projected; 4326, 4269, 4617, 6318, 4979 lon/lat); damaged copies of every fixture and random decoder input read without a crash. Without `--nolib` (needs MODFLOW) also Raven runs: every fixture as `:LandSurface` and the tiled BigTIFF ones as `:BedrockSurface` give byte-identical outputs to their twins, projected rasters under `:InputCRS`, the CRS and format stops through Raven, and a DEM or bedrock raster that covers no active column (stop with both extents) or part of them (warning) | `python3 geotiff/geotiff_check.py --nolib` (compiles the driver itself) |

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
| `run_all.py --selftest` (`run_all_selftest`) | the pass criteria of `run_all.py` fail on outputs with failed or unconverged runs, `test_restart.py`'s last line fails when RS2-RS6 fail, and the restart, lake, Thiem, Liard-grid and existing-model restart scripts end with a failing count line and exit code 1 when Raven fails |
| `soilzone/test_plot_tool.py` (`soilzone_plot_tool`) | PT1-PT3: `tools/plot_soilzone.py` with soil-zone columns over specified heads: their exchange counts in the choice of HRUs and is drawn per HRU and model-wide |
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
| `input_checks.py` | N1-N26, U0-U4, RN1-RN2, E1-E6: strict reading of the inputs: malformed numbers in the `.rvg` (`:GridCellSize 2,000.0`, `2km`, `HEAD H1146`, `1146.85m`, ...); the grid-size limit of 5 million cells per layer, checked before the grid is built (`:GridCellSize 2`, `50` and `60` on Liard, refinement sizes on a regular grid, a quadtree's estimated size for `:GridRefinement RIVERS 0.1`) and a quadtree within it that needs more memory than 3 GB (`RIVERS 0.5`: a stop naming `:GridRefinement` and the estimated size, no crash); a quadtree of 200 copies of one line and one of 20 adjacent squares built (each square counted once in the estimate); an HRU mesh with a 0.1 m refinement line stopped before it is built, one with 2 m built within 120 s (N17, N18); a regular grid refined around 60 short lines whose 2:1 smoothing takes it over the limit, stopped before it is built with the exact count (N24); overlapping boundary polygons selecting their union (N19); malformed numbers in the `.rvp` aquifer tables (N20-N23); river lines whose subbasin ID is not in the model, left out with a warning, or a stop when no line is left (N25-N26); units of `:WellFlowRate` and `:BoundaryHead` series; reserved package names; an existing model's TDIS read as MODFLOW 6 reads it (`10.0D-1`, `0.31d2`, `2*1.0`, `31.0/`, `30.0e`, `//` and `!` comment rows, commas, period numbers `2.0` and `3/`; a period length `1.0x` and NPER against the rows stop; an AUXILIARY line with a comment read as MODFLOW reads it: E1-E6) (each stop case runs under a 3 GB address-space limit) |
| `edge.py [--nolib]` | faulty set-ups (each must stop with a message naming the problem) and unusual valid ones (each must run), for generated and existing models |
| `fuzz_grids.py SEED N [lakes]` | N random set-ups of the subbasin-52 model over every grid type, with wells, boundaries, reservoirs, wetlands and lake refinement, checked with the accounting identities, MODFLOW's list-file budget and restarts; `lakes` puts a reservoir and lake refinement in every set-up |
| `crs_inputs.py [--nolib]` | `:InputCRS`: the Liard example with every geometry and raster input in UTM zone 10 against the lon/lat example. Without rasters the grid, the HRU-cell overlaps (within 1e-6 of a cell), the monitoring well's cell (given by X and Y), the GHB and CHD cells (both non-zero: the GHB head lies above its cells, the CHD lake is placed by a `:BoundaryHead` series) and the outputs agree (Hydrographs and HRU states within 1e-6, GWBudget within 1e-5); with the DEM and bedrock resampled to UTM the model top agrees within the resampling (mean below 0.05 m). Input checks as in `--nolib`; with `RAVEN_EXE_REF` the lon/lat run equals the reference build |
| `dry_start.py` | the warning for a layer that starts completely dry (Liard with INITIAL_HEAD_DEPTH 25 m: layer 2 named, summary line), none with `:GWInitialization STEADY_STATE` or for the example as shipped (with `RAVEN_EXE_REF`: equal to the reference build) |
| `combinations.py` | option combinations: small synthetic models across a matrix (exchanges ET, river, surface stores, reservoir, well, GHB, CHD together and alone; plain, dry top cells, negative recharge, rising water table; CONCEPTUAL and `:SoilZone PHYSICAL` with `RICHARDS`/`KINEMATIC`/`LAG` and 1 or 3 depth classes; every case generated, existing with NEWTON, without it (CONCEPTUAL) and in feet/seconds); every run: MODFLOW, recharge, soil-zone and column identities, Raven's balance, river, surface-store and reservoir books, run totals, no HDRY or NaN, no groundwater into surface stores while the water table is below the ground; every run must move through each exchange and stress its case names at least half the volume recorded for it in `combinations_floors.json` (`--record`), so an exchange scaled down fails as one dropped (a losing lake on the ground and a pit lake gaining from a specified head, water-table ET, the river, well and boundaries, negative recharge, dry top cells, vanishing columns, `:BoundaryHead` series switching cells off and on and switching every cell of a column off, an existing model's specified heads switching on under a lake); the KNOWN reservoir exception only for the lake's own small routing error at its weir crest, with a self-test (an injected 5,000 m3 fails); quick 311 runs of 8 days, full 393 runs of 15 days with half-day steps |
| `reservoir_checks.py` | RV1-RV4: `:ReservoirExchange` on lakes whose cells cannot all take seepage: an existing model's own specified heads under a lake linked to a sliver of another HRU (seepage of the sliver's share only, the day's seepage returned, no jump when the sliver is a specified head too, feet/seconds, a restart inside the specified-head period), a generated lake half over a `:SpecifiedHeadBoundary` (seepage constant scaled by the bed left); the lake's bed on the ground under `:SoilZone PHYSICAL` (seepage equal to CONCEPTUAL); an unsupplied reservoir gain warned about and totalled |
| `budget_file.py` | BF1-BF8: `:WriteGWBudgetFile`: FloPy reads `mf6/gwf.cbc` (FLOW-JA-FACE, specific discharge, saturation, every package each step), its totals equal `GWBudget.csv`, `gwf.porosity` holds each cell's class POROSITY; without the option the solution and the `mf6` folder are unchanged (and, with `RAVEN_EXE_REF`, identical to the reference build); `tools/make_prt.py` builds and runs a PRT simulation through the MODFLOW 6 library, forward and backward, and with a steady-state first period releases each point once, within Raven's run (BF7), and stops with a message when the flows were not saved every step (BF8); the option is refused with an existing model |
| `tools_check.py` | TC1-TC9: the tools and comparison rules: `tools_audit.py` on runs of one, two and three steps, and its recharge identity on step 1 (a step-1 change found, with and without a recharge delay store, TC6); `mf6_to_feet.py` on whole-number heads and on GHB, RIV, WEL and DRN lists, and its stop for a time-series name in a list, a package it does not convert and a DISV grid; `testconfig.max_diff` (a NaN in one run is a difference), `restart_verdict` (the continuous run's unconverged steps fail a restart comparison) and `rvc_same` (`solution.rvc` against a reference build's, numbers written with the same decimals equal, others within the two roundings of one value; `:GWVadoseColumnTops` compared when both files hold it); `make_handover.found_note` (HANDOVER.md names the public branch's extra commits only when the public check found them, TC7); `tools_audit.py` on a run without aquifer flow (the residual ratio not 1, TC8); `tools/check_manual_pdf.py` on a stand-in manual (a PDF built from its chapters passes, a changed chapter fails, `--write` replaces the PDF, TC9) |
| `watershed_balance.py` | WB1-WB6: Raven's own balance in coupled runs (`WatershedStorage.csv` `MB Error [mm]` at round-off, 1e-6 mm, while the GROUNDWATER pass-through store holds water): CONCEPTUAL, `:SoilZone PHYSICAL`, negative recharge, a hotstart whose `.rvc` holds GROUNDWATER, a disabled HRU holding GROUNDWATER, and a cold start whose `.rvc` sets GROUNDWATER (warned, booked as leaving Raven in the first step); WB7-WB11 river losses: a loss taken from a reach's inflow (MB error at round-off, a restart on a take day with `:GWRiverTake`, a 2-member ensemble), a headwater reach whose loss comes from its outflow (the loss carried at the end at most 1 % of the leakage, the outflow lower by the loss applied, an exact restart), a reach that stops flowing (the carried loss warned about and in the run totals); WB10 every channel routing method (Muskingum, Muskingum-Cunge, storage coefficient, ROUTE_HYDROLOGIC, diffusive wave, plug flow), with and without an irrigation demand: the outflow leaving the watershed lower by exactly the loss taken, the channel storage unchanged; WB11 a ROUTE_EXTERNAL reach whose outflow a live file sets every step (the take comes out of the set outflow, the channel storage unchanged, a warning); WB12 2-member ensembles with ROUTE_HYDROLOGIC, ROUTE_STORAGECOEFF and ROUTE_TVD, with and without groundwater, and an irrigated reach (Demands.csv too): every member equals the single run; WB13 restarts with another `:TimeStep` right after a take: the outflow lower by the leakage, the channel storage unchanged; WB14 restarts with a longer `:TimeStep` right after takes from the inflow with ROUTE_DIFFUSIVE_WAVE (Raven averages the inflow history; also chains 0.25, 0.5, 1 d and with one 0.2-d step between 0.1 or 1 d and 1 d): MB error at round-off beyond the same runs without the river, the leakage equal to the lower outflow plus the lower channel storage; with RAVEN_EXE_REF a restart from the reference build's `solution.rvc` no worse than the reference's own; WB13 and WB14 also check `tools_audit.py`'s river identity of every part from its first step (the river loss a restarted run starts with, from GWModelSummary.txt); WB15: a restart with a longer step where the lateral-inflow history is longer than the inflow history completes, with the river identity and MB error as WB14; WB10 also checks that the run total 'river take in transit' is given only above 1e-6 m3 |
| `boundary_recharge.py` | BR1-BR3: an HRU over specified-head cells with a 10 m2 sliver in a neighbouring cell: the sliver receives only its own share of the HRU's recharge, the rest goes to the specified heads (CONCEPTUAL; `:SoilZone PHYSICAL`; an HRU without soil under `:SoilZone PHYSICAL`) |
| `tutorials_check.py` | runs `docs/tutorials/build_tutorials.py --check`: reruns every step of the six workshops and fails if any quoted number, output excerpt, diff, model file, helper-script copy, preamble copy or `bin/README.txt` no longer matches, or if a workshop's `tex/` does not compile standalone without LaTeX warnings (quick mode reuses the committed 20-year Liard values and the OSTRICH record; full mode with `RAVEN_OSTRICH` reruns the calibration; `RAVEN_SRC` names the Raven checkout whose `cmake/RavenMF6InstallCheck.py` workshop 1 ships; without pdflatex the compile is skipped) |
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
| `restart_ext.py` | restarts inside a stress period and before a change of well rates against a continuous run; a restart at 12:00 with 6-hour time steps; each comparison must finish with no unconverged step and exact accounts in the restarted and the continuous run, a value missing in one run failing ("existing-model restarts: k of 3 pass", exit code) |
| `ext_exchanges.py` | water-table ET (`EVT_RAVEN`), `:SurfaceWaterExchange` (`SWX_RAVEN`) and `:ReservoirExchange` (`RES_RAVEN`) with an existing model: flows non-zero, water-table ET at most the unmet PET, accounting identities, the packages' flows in MODFLOW's budget file and list file equal to `GWBudget.csv`, the feet/seconds model equal to the metres/days one, a restart with reservoir seepage in transit, a kept EVT package with EXTINCTION_DEPTH refused; dry and specified-head cells: water-table ET in a model without NEWTON whose top cells dry (equal to MODFLOW's budget file, no HDRY), a reservoir over cells that become specified heads (all, or 2 of 5) and over dry cells without NEWTON (reservoir books exact, seepage not delivered returned and booked); with `RAVEN_EXE_REF`, a run without these options identical to the reference build |
| `ext_inputs.py` | TDIS period data in an OPEN/CLOSE file (same result as inline, on a later start); wells driven by a TS6 time series, restarted between two of its entries, against a continuous run; TAS6 still refused on a later start; DIS6 and STO6 under names of their own in the name file (the same run as with the usual names, MODFLOW's storage flows read) |
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
scripts run shorter cases (for example LP1 30 days instead of 365, the restart hillslope 60 + 60 days instead of 150 + 150,
DY1 without the hourly step), and the scripts whose cases take a few seconds (`spike_xmi.py`, the HS1/HS2 hillslope,
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
| `test_column.py` (`soilzone_column`) | CT1/CT1b: flat column, the water table rising into the soil zone (50 / 125 mm/d below the base, 50 inside, full on day 41) |
| `test_hillslope.py --selftest` (`soilzone_hillslope`) | HS1/HS2: hillslope wetting and drying against a MODFLOW-only reference (`sz_reference.py`); HS2 drying checks and their self-test |
| `test_dynamics.py` (`soilzone_dynamics`) | DY1 time step (1 d, 6 h, 1 h), DY2 stiff contact (iterated vs explicit), SG sub-grid saturated fraction |
| `test_restart.py` (`soilzone_restart`) | RS1 the hillslope, 300 d against 150 + 150 d (`:GWSoilZoneColumns`); RS2 an existing model with specified heads, 10 d against 5 + 5; RS3 seepage holding the lowest soil layer above capacity (no `:SoilZone PHYSICAL`); RS4 KINEMATIC and LAG columns restored as written; RS5 a coupled restart continues exactly (RICHARDS columns with a reservoir, a specified head, negative recharge and a rising water table, CONCEPTUAL with every exchange, and LAGGED soil-zone exchange with negative recharge under a `:BoundaryHead` series that holds the outlet column on some days and switches every cell off on others, restarted at off-to-held and held-to-off switches: identical to the continuous run, limit 1e-9); RS6 a lagged-exchange debt open at a restart (reported at the end of the first part, repaid by a LAGGED restart, warned about and reported by an AFTER or CONCEPTUAL one) (`--rs3rs4`: only RS3-RS6) |
| `test_liard_physical.py [days]` (`soilzone_liard`) | LP1: the Liard example with `:SoilZone PHYSICAL`, one year (quick mode: 30 days) |

**The water table in every position, and existing models**

| Script (run_all step) | Tests |
|---|---|
| `test_water_table.py` (`soilzone_water_table`) | P1-P11: delay through a deep unsaturated zone, capillary rise, a water table through the column, restarts, LAGGED timing, classes, specified heads, restart with classes, the shortest column, upward flows out of a lower cell, water-table ET under `:SoilZone PHYSICAL` with its extinction depth from the ground (generated and existing) |
| `test_sz_existing.py` (`soilzone_existing`) | X1-X9: the soil zone with an existing MODFLOW model (round trip, feet and seconds, specified heads, outputs, NEWTON required, specific yield; a steady model takes SPEC_YIELD of `:SoilZoneAquiferClass`; unsaturated columns on the model's own specified heads end, their water to the specified heads) |

**The interface and MODFLOW's side**

| Script (run_all step) | Tests |
|---|---|
| `test_interface_stiff.py` (`soilzone_interface_stiff`) | S1-S8: low-K_v top layer, kink drain, supply limits, tiny budgets and outer limits, the connection test |
| `test_confined_wet.py` (`soilzone_confined_wet`) | W1-W13: confined layers below their bottoms, drained columns, heads far outside the model and the stop rule, restarts after unconverged steps keeping the heads the far-head test compares with (`:GWStartHeads`) (W4, W6, W11 reported as skipped) |
| `test_columns_mf6.py` (`soilzone_columns_mf6`) | M1-M4: drained columns kept wet, a column delivers its inflow, CONCEPTUAL against a reference build (`RAVEN_EXE_REF`) |
| `test_mf6_budget.py` (`soilzone_mf6_budget`) | B1-B9: MODFLOW's residual and gross flow as Raven books them, dated warnings, guard counts, B8 unconverged steps without a soil zone (only MODFLOW's negative residual withheld; the row residual is the withheld volume, also with rivers: the Liard example), B9 `GWSoilExchange.csv` per HRU sums to `GWBudget.csv` (specified heads included) |
| `test_robustness.py` (`soilzone_robustness`) | R1-R13 hard cases (stiff column, one HRU over ten cells, explicit mode, late updates, frozen boundaries, unconverged steps), R14-R22 negative recharge (R21 the hand-back of vanishing columns in a negative step, R22 the top-cell limit with depth classes), R15b a negative-recharge cut on a draining soil zone |
| `test_surface_stores.py` (`soilzone_surface_stores`) | SW1-SW4: `:SurfaceWaterExchange` on `DEPRESSION` of `:SoilZone PHYSICAL` HRUs: the stores' bed at the ground (model top + soil-zone thickness), no discharge into the stores while every water table is below the ground, generated and existing model, a control with the water table above the ground, a restart that keeps a store filled above DEP_MAX by groundwater |

**Unsaturated-zone methods, depth classes and steady starts**

| Script (run_all step) | Tests |
|---|---|
| `test_vz_kinematic.py`, `vadose_kw_unit.cpp` (`soilzone_vz_kinematic`) | `:SoilZoneVadose KINEMATIC` (unit and model tests K1-K8); K9: a column leak of 1e-5 m3 per step written into a run's `GWBudget.csv` fails the script's checks |
| `test_vz_lag.py`, `vadose_lag_unit.cpp` (`soilzone_vz_lag`) | `:SoilZoneVadose LAG` (LU unit tests, L1-L6, LS cost, LB byte identity); L8: the release-cap warning says that the cap binds while water is in transit, and names the specific yield only when it is below the drainable porosity; L7: a column leak of 1e-5 m3 per step written into a run's `GWBudget.csv` fails the script's checks |
| `test_vz_classes.py` (`soilzone_vz_classes`) | C1-C11: depth classes of the unsaturated columns (C1: K = 1 equals the reference build, any difference a failure); C9 RT20 with three classes; C10 hotstart after a dropped class column; C11 the columns' upflow and the rise from the water table share one source-cell limit |
| `test_vz_initial.py` (`soilzone_vz_initial`) | VI1, VI2, VI4-VI8: `:SoilZoneVadoseInitialFlux` steady starts (for (1-F) q; backed-up columns), hotstarts, the columns' balance from step 1, a restart without columns from a file with columns (warned, volume reported), a restart whose columns have other tops (not matched); VI9-VI12: a restart with another method's reference profile (KINEMATIC against RICHARDS: at rest, warned, volume reported; RICHARDS read by LAG: exact), hotstart lines on cells that are no longer exchange links (warned, volume reported), no columns on a generated model's cells held as specified heads at the start, columns over an existing model's specified heads counted once across a restart; VI13 a restart on the day before a `:BoundaryHead` series holds a generated model's cells again (equal to the continuous run) |

**Inputs and hotstarts**

| Script (run_all step) | Tests |
|---|---|
| `test_inputs.py` (`soilzone_inputs`) | I1-I24: missing HYDRAUL_COND, short `:SoilZoneIteration`, last `:SoilZone` counts, ignored options, mismatched and reordered hotstart columns, `.rvc` blocks without groundwater, surface exchange on a soil layer, damaged `:GWHeads` header, `:StartTime` under valgrind, orphan `:BoundaryHead`/`:WellFlowRate`, options that do nothing, messages, age tracer across chained hotstarts (I14, ages within 2e-4 d plus 1e-5 of the age); I15 chains across year boundaries; I16 age tracer from a spin-up without it; I17 EnKF members' extra `.rvt` series (I17b: a `:BoundaryHead` series given only there builds each member's boundary; I17c: an EnKF spin-up's `solution_EnKF.rvc` holds the members' groundwater blocks and full-precision states, and the closed loop and forecast continue the aquifer); I18 damaged soil-zone hotstart values; I19 `:Transport` in a coupled run stops; I20 a head boundary placed by its `:BoundaryHead` series, the warning for a boundary left with no cells; I21 boundary cells switched off on steps whose head is at or below their bottom (GHB drains as with HEAD alone, CHD not held at a cell bottom, the same cells on a restart; a column with no cell held is an ordinary column, nothing booked onto CHD cells; cells placed by the series alone; the steady-state period counted); I22 strict numbers in the `.rvc` (`:InitialGWHeads ELEVATION 98,5` and `H98.5` stop, a `:GWHeads` value `98.5x` stops); I23 two specified-head boundaries on one cell stop, naming both; I24 the factor-2 warning on Sy against the drainable porosity gives the ratios of the links it counts |

**Rough terrain**

| Script (run_all step) | Tests |
|---|---|
| `test_rough_terrain.py` (`soilzone_rough_terrain`, `_k3`) | regression cases RT1-RT20 and random rough-terrain seeds (quick 40, full 400) with all four methods; `_k3` with three depth classes |

A comparison with GSFLOW's Sagehen model is not part of the suite; the soil zone with existing models is covered by X1-X9
and the existing-model cases of the rough-terrain suite.
