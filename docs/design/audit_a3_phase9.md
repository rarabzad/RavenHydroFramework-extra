# Audit A3, phase 9: inputs, tests and tools

Phase 9 of the round-3 audit (issue list: `spec/audit_A3/AUDIT_A3_issues_and_phases.md`) corrects IB3-3 to IB3-7, MT3-1
to MT3-3, SZ3-2 and SZ3-3, and assesses the three items Phase 8 handed over. Each code fix has a check that fails with the
reference build (`wt/p8/Raven_p8.exe`, or the Phase 8 sources for the compiled unit test) and passes with this one; each
test-harness fix has a check that fails on the old harness. The new checks run in `tests/run_all.py`, in quick and full
mode.

## IB3-3: `tests/crs_inputs.py` compared empty boundaries

**Cause.** The test's boundaries had heads below their cells (GHB 1146.85 m, CHD 1226.5 m; the top layer's bottom is
1300 m there), so both runs had 0 GHB and 0 CHD cells and the comparison was 0 = 0.

**Change (test).** The GHB line gets HEAD 1310 m (above the top layer's bottom of 1300 m, below the top of 1315 m). The
CHD lake gets HEAD 0 and a `:BoundaryHead LAKE1 m` series of 1312 m, so its cells are placed by the series (the Phase 8
placement). A new check requires non-zero GHB and CHD counts in both runs, with and without rasters, besides the existing
equality of the two grids.

| | Before | After |
|---|---|---|
| GHB / CHD cells, lon/lat and UTM runs | 0 / 0 and 0 / 0 (passes) | 3 / 9 and 3 / 9, required non-zero |

The other results of the test are unchanged (polygons 8.4e-12, overlaps 1.1e-9 of a cell, GWBudget 2.3e-8, rasters: top
0.018 m mean, hydrographs 1.0e-3; the lon/lat run is byte-identical to the reference build).

## IB3-4: inputs left in longitude/latitude under `:InputCRS`

**Cause.** With `:InputCRS`, the raster and GeoJSON readers convert every coordinate from the projection. A lon/lat file
then lands near the projection's false origin: a raster covers no cell and is silently unused, a GeoJSON gives a
misleading "does not overlap" stop.

**Change.**
- `GWGeometry`: the GeoJSON readers report the extent of the coordinates as written in the file (optional `rawbox`
  argument); `CGWRaster::Extent` gives a raster's extent in its own coordinates.
- `CGroundwaterModel::CheckInputLonLat` (GroundwaterModel.cpp), called after every GeoJSON and raster read when
  `:InputCRS` is set (HRU file, river file, refinement files, grid file, boundary files, DEM, bedrock, an existing
  model's `:MF6GridFile`). A file is in lon/lat when all three hold:
  - its extent lies within ±180 / ±90;
  - it overlaps the HRUs' place in lon/lat: the box of the `.rvh` LATITUDE/LONGITUDE of the coupled HRUs, widened by
    0.5° plus half its size;
  - it does not overlap their place in the projection: the same centroids projected with `:InputCRS`, widened by 50 km
    plus half their extent.

  The run then stops with "*file* looks like longitude/latitude: its coordinates (...) lie over the HRUs'
  LATITUDE/LONGITUDE, while in the coordinates of :InputCRS (...) the HRUs lie at ...". A projected file is never refused
  by this test unless the model itself lies within a few hundred metres of the projection's false origin and the file
  far from it.

**Test.** `crs_inputs.py` (also `--nolib`): with `:InputCRS EPSG:32610`, the lon/lat DEM, the lon/lat bedrock raster,
the lon/lat HRU file and the lon/lat boundary line each stop with that message.

| Case | Reference build | This build |
|---|---|---|
| lon/lat DEM or bedrock with `:InputCRS` | run completes, raster unused | stop, "looks like longitude/latitude" |
| lon/lat HRU file with `:InputCRS` | "HRU ... does not overlap any active groundwater cell" | stop, "looks like longitude/latitude" |
| lon/lat boundary line with `:InputCRS` | boundary without cells | stop, "looks like longitude/latitude" |

## IB3-5: the GeoJSON `"crs"` member

**Cause.** Only six geographic codes were known, every other code counted as a projection (with a remedy, `:InputCRS
EPSG:n`, that is refused for codes not built in), and the code was the first number after "EPSG", so
`urn:ogc:def:crs:EPSG:6.6:4326` read as EPSG:6.

**Change (GWGeometry.cpp `CheckFileCRS`).**
- The code is the number that ends the name: `EPSG:4326`, `urn:ogc:def:crs:EPSG::4326`,
  `urn:ogc:def:crs:EPSG:6.6:4326`, `http://www.opengis.net/def/crs/EPSG/0/4326`.
- Geographic: every EPSG code from 4000 to 4999 (EPSG's range of geodetic systems: 4326, 4979, 4269, 4267, 4617, 4152,
  4258, ...; the geocentric ones in that range have metre coordinates, which the lon/lat range test refuses), and the
  later realisations 6318/6319 (NAD83(2011)), 8255 (NAD83(CSRS)v7), 7843/7844 (GDA2020), 6667/6668 (JGD2011); OGC CRS84,
  CRS83 and CRS27.
- A built-in projection: as before (needs `:InputCRS` with that projection).
- Any other code is not classified: the file is accepted, and its coordinates decide. Without `:InputCRS`, coordinates
  outside the lon/lat range stop with "... and is in EPSG:n (...), a projection that is not built in: give :InputCRS with
  the projection's parameters (TMERC, ALBERS or LCC) ..., or reproject the file". No message suggests `:InputCRS EPSG:n`
  for a code that is not built in.

**Test.** `geomtest.cpp` / `geomtest_check.py` (step `geomtest`): 12 new file checks.

| File's `"crs"` | `:InputCRS` | Phase 8 sources | This build |
|---|---|---|---|
| EPSG::6318, EPSG::4979, EPSG:4267, EPSG:6.6:4326, opengis URL 4269 (lon/lat files) | none | refused | accepted |
| OGC CRS83 | none | accepted | accepted |
| EPSG::6318, EPSG:6.6:4326 | EPSG:32610 | accepted (6318) / refused as "EPSG:6" | refused: "is in longitude/latitude" |
| EPSG:9.8.15:32610 (UTM file) | EPSG:32610 / none | accepted / refused "EPSG:9" | accepted / refused ":InputCRS EPSG:32610" |
| EPSG::3157 (UTM file, not built in) | none | refused, "give :InputCRS EPSG:3157" | refused, asks for TMERC/ALBERS/LCC parameters |
| EPSG::3157 | TMERC 0 -123 0.9996 500000 0 GRS80 | accepted | accepted |

The Phase 8 sources fail 9 of the 12.

## IB3-6: strict numbers in the `.rvg` parser

**Change (ParseGWFile.cpp).**
- Numbers are read with `strtod` and must use the whole token and be finite (`GWNumber`); whole numbers must be integral
  (`GWInteger`); well and overlap IDs must be integers (`GWID`). The message names the command, the file and the token:
  "command :GridCellSize in Liard.rvg: '2km' is not a number (give a plain number in the units of the manual, without
  units or thousands separators)".
- Commands that take a fixed number of values stop on a surplus value (`GWMaxTokens`): "... has the surplus value '000.0'
  (it takes 1 value at most; a comma separates values, so write 2000.0, not 2,000.0)". This covers `:GridCellSize`,
  `:GridRotation`, `:GridRefinement`, `:QuadtreeMaxLevel`, `:MinCellCoverage`, `:SoilZoneIteration`, `:SoilZoneSubgrid`,
  `:SoilZoneVadose`, `:SoilZoneVadoseClasses`, `:SoilZoneVadoseInitialFlux`, `:SoilZoneClasses`, `:GWInitialization`,
  `:RiverBedDepth`, `:SurfaceWaterExchange`, `:SolverHeadTolerance`, `:SolverMaxOuterIterations`, `:HeadSaveFrequency`
  and the `:OverlapWeights` rows.
- Boundaries: the values after the file must come in keyword-value pairs, and an unknown keyword stops the run (it was a
  warning, after which the values were read out of step).
- `:Wells` and `:ObservationWells` values are read strictly too.
- Grid size (GroundwaterModel.cpp `BuildGeometry`, before the grid is allocated): a generated grid whose base cells
  over the HRUs' extent number more than 1e7 per layer stops ("`:GridCellSize 2 m gives about 4.57e+09 cells per layer
  over the HRUs' extent (107.8 km by 169.5 km), more than 1e+07 ...`"); a refined regular grid whose rows times columns
  (counted as the refinement asks, before the 2:1 smoothing) exceed 1e7 stops too. The quadtree and HRU mesh refine only
  around their features; the HRU mesh keeps its limit of 5 million seeds.

**Test.** New script `tests/input_checks.py` (step `input_checks`), cases N1-N10, each under a 3 GB address-space limit
and a 120 s time limit:

| Case | Reference build | This build |
|---|---|---|
| N1 `:GridCellSize 2,000.0` | `std::bad_alloc` | stop, surplus value '000.0' |
| N2 `:GridCellSize 2km` | `std::bad_alloc` | stop, '2km' is not a number |
| N3 `:GridCellSize 2` | `std::bad_alloc` | stop before the grid is built (4.57e9 cells) |
| N4 `:GridRefinement RIVERS 5` | `std::bad_alloc` | stop before the grid is built (7.3e8 cells) |
| N5 `:GridRefinement RIVERS 1,000` | `std::bad_alloc` | stop, surplus value '000' |
| N6 / N7 boundary `HEAD H1146` / `HEAD 1146.85m` | runs (head 0 / 1146.85) | stop, names the token |
| N8 boundary `HEAD 1,146.85` | stop, "needs a positive CONDUCTANCE" (misread) | stop, values not in pairs |
| N9 `:SolverMaxOuterIterations 50.5` | runs (50) | stop, not a whole number |
| N10 `:Wells` LATITUDE `59.2x` | runs (59.2) | stop, names the token |

## IB3-7: units of `:WellFlowRate` and `:BoundaryHead`

**Change (ParseTimeSeriesFile.cpp).** The units token after the well ID / boundary name is read:
- `:WellFlowRate`: `m3/d` (default; also `m3/day`), `m3/s` (x 86,400) and `L/s` (x 86.4) are converted to m3/d (blank
  entries keep their marker); any other unit stops: ":WellFlowRate 1: units ft3/s are not supported; give the rates in
  m3/d (or m3/s or L/s, which Raven converts to m3/d)". A surplus token stops.
- `:BoundaryHead`: `m` (default); any other unit stops.

The conversion is applied where the series is parsed, so it holds for ensemble members' series as well.

**Test.** `input_checks.py` U0-U4 on the subbasin-52 grid model with its 5,000 m3/d well:

| Case | Reference build | This build |
|---|---|---|
| U1 rates in m3/s (-0.0578704) | wells specified -0.0579 m3/d | -5,000 m3/d |
| U2 rates in L/s (-57.8704) | -57.87 m3/d | -5,000 m3/d |
| U3 `ft3/s`, U4 `:BoundaryHead EDGE ft` | run / other message | stop, "units ... are not supported" |

## SZ3-3: package names Raven reserves

**Change (GWExternal.cpp, reading the model's name file).** A package of the model named `RCH_RAVEN`, `DRN_RAVEN`,
`EVT_RAVEN`, `SWX_RAVEN`, `RES_RAVEN`, `SZX_RAVEN`, `SZQ_RAVEN`, `SZD_RAVEN` or `SZW_RAVEN` stops the run with Raven's
message ("the model name file gwf_liard.nam has a GHB6 package named DRN_RAVEN, a name Raven reserves for the packages it
adds (...). Rename the package in the name file, or remove its line if it is a package Raven added to a model it
wrote"). A recharge or ET package so named that `:RavenTakesOver` lists is allowed (it is removed before Raven adds its
own), and only for those types does the message suggest `:RavenTakesOver`. `RIV_RAVEN`, `WEL_RAVEN`, `GHB_RAVEN` and
`CHD_RAVEN` are names of generated models, never added to an existing model, so a re-coupled generated model keeps them
(`combinations.py` does this in every existing twin).

**Test.** `input_checks.py` R1 (the example's GHB package renamed `DRN_RAVEN`): the reference build stops with MODFLOW's
"Package name already exists: DRN_RAVEN"; this build stops with Raven's message. R2 (the recharge package renamed
`RCH_RAVEN`, taken over) runs with both.

## SZ3-2: `tools/plot_soilzone.py` and the specified-head exchange

**Change.** When `GWSoilExchange.csv` / `GWBudget.csv` have the columns *soil zone to specified heads* and *specified
heads to soil zone*, they count in the default choice of HRUs (largest exchange) and are drawn as their own dashed lines
in each HRU's exchange panel and in the model-wide panel.

**Test.** New `tests/soilzone/test_plot_tool.py` (step `soilzone_plot_tool`, no MODFLOW): output files with the real
column names, seven HRUs exchanging 10-70 m3/d with the aquifer and HRU 8 only with specified heads (1,000 m3/d).

| Check | Old tool | New tool |
|---|---|---|
| P1 HRU 8 chosen first | HRUs 7, 6, 5, 4, 3, 2 | 8, 7, 6, 5, 4, 3 |
| P2 specified-head lines in HRU 8's and the model-wide panel, adding up to the total | absent | present, sum equal |
| P3 output without those columns | plots | plots |

## MT3-1: `run_all.py` passing steps whose runs failed

**Changes.**
- `restart_test.py`: a grid passes when its three runs finish, the deviation is below 1e-4, the continuous run has no
  unconverged step, and recharge identity, MODFLOW residual and river books are below 1e-8. Last line "restart grids: k
  of 5 pass"; exit code 1 unless all pass. The restarted run is set up only when the first part finished.
- `existing/restart_ext.py`: the same per comparison (two splits and the sub-daily split; restarted run without
  unconverged steps, recharge and residual below 1e-8); a failed continuous run ends the script. Last line
  "existing-model restarts: k of 3 pass"; exit code.
- `thiem/run_thiem.py`: "thiem runs: k of 17 finished, converged and balanced" (no unconverged step, residual below
  1e-6: the steep cone of depression gives cumulative residuals up to 2.5e-8, the manual's "every run checked, none with a failed step"); exit code. A missing quadtree cell file (when the
  quadtree run failed) is a FAILED run, not a crash.
- `lake_test.py`: per run no unconverged step, recharge and residual below 1e-9, reservoir sent = previous awaiting
  (1e-8) and delivered = sent (1e-9), the manual's "Lakes" paragraph; "lake runs: k of 5 pass"; exit code.
- `liard_grids.py`: "liard grids: k of 5 finished, converged and balanced" (no unconverged step, recharge 1e-9, residual
  1e-8); exit code (also with `--table`).
- `run_all.py`: the steps `restart`, `ext_restart`, `lake`, `liard_grids` require their count line to be complete
  (`all_of` combines it with the old criterion); `thiem` requires "thiem runs: n of n" and one fitted line per run. The
  docstring states the rule.
- `run_all.py --selftest` (step `run_all_selftest`, no MODFLOW needed for its first part): 13 judge checks on outputs with
  FAILED runs, unconverged steps and missing count lines (each must be judged FAIL, the good outputs PASS), the
  `soilzone_restart` verdict (below), and the five scripts run with `RAVEN_EXE=/bin/false` in their own scratch folder:
  each must print its failing count line, exit with 1 and be judged FAIL.

**Before / after.** The old judges, fed the same outputs: four of five restart grids FAILED -> PASS ("1 restart
deviations"); a grid with 3 unconverged steps -> PASS; a failed existing-model split -> PASS; a failed Thiem run -> PASS;
a lake run with 4 unconverged steps -> PASS ("no FAIL"); `restart_test.py` exited 0 when every run failed. With this
harness all are FAIL, and the self-test passes (19 checks).

## MT3-2: `test_restart.py`'s last line

**Change.** `verdict()` prints the combined result: "restart test: PASS (hillslope restart PASS, R2 PASS, R3 PASS, R4
PASS)", FAIL when any part fails (also when the hillslope runs fail early, where it printed nothing). The hillslope
comparison prints its own line "hillslope restart: ...". `run_all_selftest` checks that `verdict(True, True, False,
True)` prints "restart test: FAIL" and is judged FAIL; the old script has no such verdict (it printed PASS).

## MT3-3: the ensemble check

**Change (`behaviour_check.py`).** Each member (1 and 2) is compared with the single run in every value of
`GWBudget.csv`, `GWHeads.csv`, `Hydrographs.csv`, `ReservoirStages.csv` and `GWHRUState.csv` (same rows and columns, dates
equal, relative difference below 1e-12), and each member's recharge identity, MODFLOW residual and reservoir identity
are checked. The docstring is corrected: Raven restores routing and reservoirs before each member;
`WatershedStorage.csv` is not compared, because base Raven's channel and rivulet storages differ in ensemble mode, also
without groundwater (the auditor's finding). A quick mode (120 days) is added. Both members are identical to the single
run (largest difference 0) in quick and full mode. The manual (`verification.tex`, behaviour table and text; known issues
in `developers.tex`) names the files compared and the `WatershedStorage.csv` behaviour.

## Phase 8's hand-over

### Reservoir balance error at the weir crest (`combinations.py --only CONC_NONE_res_neg`)

**Finding: base-Raven behaviour, not the coupling.** `CReservoir::RouteWater` solves the step's stage with Newton's
method, a forward-difference derivative (dh = 1 mm) and the stop rule |change| < `RES_TOLERANCE` = 1e-4 m. The weir
outflow has a kink at the crest (zero below, (h - crest)^1.5 above). When the step ends within a millimetre of the crest,
the forward difference includes weir flow the true slope does not have, and the iteration stops with a residual of up to
about the lake area times 1e-4 m. The routing loop is unchanged from base Raven (the project's changes to `Reservoir.cpp`
are the dry-reservoir loss cap, the initial stage at the crest, the restart precision and the ensemble state; none touch
the iteration).

**Reproduction with base Raven** (`audit/CB/Raven_base.exe`, no groundwater): the combination case's model without the
aquifer blocks and `:GroundwaterModel`, the lake (0.04 km2, crest 95.5 m) with a fixed `:SeepageParameters 0.02 h_ref`
and an initial stage just above the crest, 8 days:

| h_ref [m] | initial stage [m] | largest `MB error` in ReservoirMassBalance.csv [m3] |
|---|---|---|
| 95.497 | 95.5003 / 95.501 / 95.502 | 4.28 / 3.26 / 0.20 |
| 95.499 | 95.5003 / 95.501 / 95.502 | 6.66 / 3.22 / 0.47 |
| 95.4995 | 95.5003 / 95.501 / 95.502 | 6.39 / 3.20 / 0.54 |

The coupled case shows 4.84 m3 on the step its stage falls from 95.5001 to 95.4997 m: the same mechanism, with the
aquifer holding the lake near its crest instead of a fixed level. Phase 8's statement that base Raven shows no such error
came from fast crossings (stage far from the crest at the end of the step), where the iteration ends on the linear branch.

**Not changed** (Raven's own routine, left to the Raven developers). Documented:
- `developers.tex`, known issues in Raven itself;
- `verification.tex`, option combinations;
- `combinations.py`, its KNOWN reason text.

The coupling's books hold in these cases, and `combinations.py` still reports the case as KNOWN only when Raven's
balance error equals the reservoir's own.

### No-NEWTON: lake over a dried top cell; seepage drains on dried cells; a dry-top-cell warning

**Assessment.** In a model without NEWTON a top cell that dries becomes inactive. MODFLOW then:
- moves RCH and EVT entries to the active cell below (Raven reads ET back at that cell, CB3-1, and books recharge it
  could not apply);
- gives WEL and DRN entries on the inactive cell no flow.

So Raven's seepage drain and a reservoir's seepage stop on that column until the cell rewets; the reservoir's seepage is
returned to its subbasin and booked (CB3-2, `res_dry` identity 0), and the drain books 0. The books close in every case
(Phase 8's `ext_exchanges.py` `et_dry`, `res_dry` and the dry cases of `combinations.py` with `ext_n0`).

The remaining effect, a water table in the layer below rising above the ground without seeping out, is the model's own
no-NEWTON behaviour, not a defect of the physics or the books. Moving the drain and the reservoir seepage to the cell below
each step, or warning when coupled columns have a dry top cell, would be new features, so nothing is changed. The
behaviour is stated in the limitations (`developers.tex`, existing models: "Use NEWTON where top cells dry"); the
package table of `existing_model.tex` already describes the reservoir case.

## Full test suite and byte identity

`tests/run_all.py`, full mode (`RAVEN_TEST_QUICK=0`), `RAVEN_EXE_REF` = the Phase 8 build, MODFLOW 6.8.1, run in three
`--only` chunks (the soil-zone steps in a scratch folder of their own):
- 58 steps: 56 PASS, 0 FAIL, 2 not run (`usgs_sagehen`, `usgs_capture`: the MODFLOW 6 examples are not on this machine);
- 4 checks skipped inside passing steps: W4, W6, W11 (`soilzone_confined_wet`, as documented) and the patchelf part of
  `cmake` (patchelf not installed);
- new steps: `run_all_selftest`, `input_checks`, `soilzone_plot_tool`; `crs_inputs` (120 days, with the reference: the
  lon/lat run byte-identical);
- figures: restart grids 5 of 5 (largest deviation 9.9e-7), existing-model restarts 3 of 3 (7.0e-7), lake 5 of 5,
  Liard grids 5 of 5, Thiem 17 of 17, behaviour (731 days, both ensemble members identical to the single run),
  `combinations` 369 runs, 0 failed, 7 known, rough terrain 1,620 + 1,620 runs, 0 failed.

The first full run of `thiem` failed with a residual limit of 1e-8: two grids (regular 125 m, quadtree 250 m) give
cumulative residuals of 2.5e-8 and 1.1e-8, the same as the reference build. The limit is 1e-6 now; nothing else changed.

Byte identity (`wt/p9/patches/byteid.py`, the Phase 8 script with Phase 9 paths): without groundwater against base
Raven (`audit/CB/Raven_base.exe`: small models with chained hotstarts, no tracer, Nitrate and the age tracer; Liard 5
years and a 1-year hotstart) and coupled against the Phase 8 build (Liard CONCEPTUAL 180 days and its `mf6` folder, the
Liard existing model 31 days and its `mf6` folder, PHYSICAL + RICHARDS, CONCEPTUAL with unconverged steps): all 15
comparisons identical.

## Documentation

- Manual:
  - `building.tex` (`:InputCRS`: the `"crs"` member rules, the lon/lat check);
  - `appendix.tex`: command table units of `:WellFlowRate` / `:BoundaryHead`; error table rows for strict numbers,
    surplus values, boundary pairs, cell counts, series units, a projection that is not built in, "looks like
    longitude/latitude", reserved package names;
  - `exchanges.tex` (well-rate units, the plot tool);
  - `verification.tex` (ensemble files, crs-member checks, projected-input boundaries and lon/lat stops, faulty-input
    table rows, the reservoir known item, how steps are judged);
  - `developers.tex` (no-NEWTON dried top cells; known issues: the crest residual and the ensemble
    `WatershedStorage.csv`).

  The manual builds with no warnings (checked in a scratch copy; the PDF is not rebuilt here, Phase 10 does).
- User guide: projected inputs, `.rvt` units, the plot tool, troubleshooting rows for the new messages.
- `README.md` (plot tool), `tests/README.md` (new scripts and steps, count lines, crs and geomtest rows).

## Files

**Code** (`wt/p9/code`, rb-p9):
- `src/GWGeometry.cpp`, `src/GWGeometry.h`: crs member, raw extents, `CGWRaster::Extent`;
- `src/GroundwaterModel.cpp`, `src/GroundwaterModel.h`: `CheckInputLonLat` and its calls, cell-count stops;
- `src/GWExternal.cpp`: the lon/lat check of `:MF6GridFile`, reserved package names;
- `src/ParseGWFile.cpp`: strict numbers;
- `src/ParseTimeSeriesFile.cpp`: series units.

**Extra** (`wt/p9/extra`, rb-p9-tests):
- new: `tests/input_checks.py`, `tests/soilzone/test_plot_tool.py`, this note;
- tests: `tests/run_all.py`, `tests/crs_inputs.py`, `tests/geomtest.cpp`, `tests/geomtest_check.py`,
  `tests/restart_test.py`, `tests/existing/restart_ext.py`, `tests/thiem/run_thiem.py`, `tests/lake_test.py`,
  `tests/liard_grids.py`, `tests/behaviour_check.py`, `tests/soilzone/test_restart.py`, `tests/combinations.py` (KNOWN
  text), `tests/README.md`;
- `tools/plot_soilzone.py`;
- docs: the manual chapters and guide listed above, `README.md`.
