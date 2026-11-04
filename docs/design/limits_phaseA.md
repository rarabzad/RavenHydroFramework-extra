# Limitations plan, Phase A (agent p7a)

Plan: `spec/limits/LIMITS_plan.md` (inventory L1-L42, designs F1-F9). Phase A = DOC sweep of stale or contradicting text,
F1 `:InputCRS`, F9 dry-starting-layer diagnostic, F8 steady existing model Sy from `:SoilZoneAquiferClass` (approved by the
coordinator). Branches rb-p7a (code) and rb-p7a-tests (extra), changes left uncommitted; diffs in `wt/p7a/patches/`.

## F1 `:InputCRS` (L3, L4)

Code:
- `GWGeometry.h/.cpp`
  - `ReadGeoJSONPolygons` / `ReadGeoJSONLines` take `const CGWCRS *crs=NULL`. With a CRS every vertex goes through
    `crs->Inverse` as it is read (after the closing-vertex removal, before the ring orientation: TM, Albers and LCC do not
    mirror, so orienting in lon/lat gives the same rings). Everything downstream stays lon/lat.
  - `CheckFileCRS`: the GeoJSON `"crs"` member (`properties.name`, e.g. GDAL's `urn:ogc:def:crs:EPSG::32610`; `CRS84` read
    as 4326). Geographic codes (4326, 4269, 4617, 4258, 4167, 4283) with `:InputCRS` stop; a projected code without
    `:InputCRS` stops ("give :InputCRS EPSG:n"); a built-in projected code that is not `Same()` as `:InputCRS` stops; a code
    that is not built in is accepted with an `:InputCRS` (cannot be compared). No member, or a non-EPSG name: no check.
  - Without a CRS, a file whose largest |x| > 360 or |y| > 90 stops (projected metres read as degrees). This catches the
    silent case of a projected file without a `"crs"` member. Not added: the reverse check (lon/lat-looking coordinates with
    `:InputCRS`), because a small local TMERC domain can legitimately lie within +-360 m of its false origin.
  - `CGWCRS::Same()` (parameters within 1e-10 rad / 0.1 mm, same ellipsoid), so `TMERC 0 -123 0.9996 500000 0` equals EPSG:32610.
  - `CGWRaster`: `SetCRS()` before `Read()`; `Sample(lon,lat)` projects with `Forward` first and interpolates in the raster's
    own coordinates (same arithmetic; without a CRS the values are bit-identical). Without a CRS, `Read` refuses a raster
    whose extent lies outside +-360 / +-90 (+ one cell).
- `GroundwaterModel.h/.cpp`: member `_inCRS`, `SetInputCRS`, `InCRS()` (NULL when not set) passed to every GeoJSON read
  (refinement LINES/POLYGONS/RIVERS, HRUs, grid file, rivers, boundary files via `SelectColumns`) and to the DEM and
  bedrock rasters (the DEM member also serves the soil zone's subgrid samples). `GridSpec()` appends `:incrs:<Describe>`
  only when set (cache key unchanged otherwise). Summary line "input coordinates" only when set.
- `GWExternal.cpp`: the `:MF6GridFile` read takes `InCRS()` (the second read inside `BuildGeometry` already does).
- `ParseGWFile.cpp`: `:InputCRS spec` (grammar of `:MF6CRS`); `:Wells` / `:ObservationWells` accept `X`, `Y` when there is
  no `LATITUDE` (stored in lat/lon with a flag `xy`); `ResolveInputCRS()` at the end of the file converts them (so
  `:InputCRS` may come after the tables) and stops when X/Y are given without `:InputCRS`.
- `:InputCRS` is allowed with an existing model (it applies to `:HRUGeometry`, `:MF6GridFile`, `:LandSurface`), so it is not
  in `_genOnly`.

Plan deviations / notes:
- The plan listed call sites by line; all eight GeoJSON reads plus the external one are covered, and the raster call sites
  need no change because the CRS lives in the raster object.
- Added the lon/lat range checks (GeoJSON vertices and raster extent) beyond the plan's `"crs"` member check: they cost
  nothing for valid lon/lat inputs and turn the most common silent error into a stop.
- With `:InputCRS`, a lon/lat file without a `"crs"` member is not detected (documented: every input file must then be
  projected).

Tests:
- `tests/geomtest.cpp` + `geomtest_check.py`: UTM raster with a plane sampled at 300 lon/lat points against the plane at
  PROJ's position (3e-10); UTM GeoJSON polygons (clockwise in the file) and lines read back against the lon/lat originals
  (1.1e-11 degrees, outer rings CCW); 12 accept/refuse cases of the file checks and `Same()`.
- `tests/crs_inputs.py [--nolib]` (run_all steps `crs_inputs_nolib`, `crs_inputs`): the Liard example converted to EPSG:32610
  with pyproj (HRUs, rivers, GHB line, CHD polygon with a `"crs"` member; DEM and bedrock resampled to 300 m UTM grids by
  Raven's own bilinear rule; a monitoring well by X/Y). Without rasters: same grid, polygon areas 8.4e-12, overlaps 1.1e-9
  of a cell, Hydrographs identical, GWBudget 2.3e-8, GWHRUState 3.0e-7. With rasters: top/bottoms mean difference 0.018 m
  (resampling), hydrographs 1.0e-3 (120 days). Four stops. With `RAVEN_EXE_REF` the lon/lat run equals the reference.
  Quick mode 10 days, full 120 days (about 1 minute).
- Before (reference build p4): `:InputCRS` is an unrecognized command; the UTM GeoJSON run gives polygon areas of 1e7 km2
  and stops with "does not overlap any active groundwater cell"; the UTM raster run deactivates 1694 columns and stops
  the same way; X/Y wells stop with "missing attribute LATITUDE". 6 checks of crs_inputs fail; geomtest does not compile.

## F9 dry-starting layer (L8)

- `CGroundwaterModel::CheckDryStart`, called in `Initialize` right after `_doSteady` is decided (so a steady-state period
  suppresses it; hotstart heads are already in `_strt`). Generated models only (an existing model's initial heads are its
  own IC package). Per layer: active (`idomain>0`) cells of the column's profile layers that are not `CONFINED_AQUIFER`
  (ICELLTYPE 0 never dries); when all of them have `strt <= botm`: one warning (`WriteWarning`) naming the layer, the cell
  count, the cause (INITIAL_HEAD_DEPTH / `:InitialGWHeads`, or hotstart heads) and the remedies, plus a summary line
  "dry at the start". Nothing is written otherwise, so outputs of models without a dry layer are unchanged.
- Test `tests/dry_start.py` (run_all `dry_start`): Liard with VALLEY_ALLUVIUM INITIAL_HEAD_DEPTH 25 m -> layer 2 (clay till,
  2794 cells) named, layer 1 (upland till wet) and layer 3 (confined) not; with `:GWInitialization STEADY_STATE` no warning;
  the shipped example no warning, and with `RAVEN_EXE_REF` its outputs incl. Raven_errors.txt and GWModelSummary.txt equal
  the reference build's. Before: no warning (D1 fails).

## F8 steady existing model: Sy from `:SoilZoneAquiferClass` (L28; coordinator approved)

- `gw_aquifer_class::syGiven` (set in ParsePropertyFile when SPEC_YIELD is in the class's `:Attributes`). The class default
  of 0.1 is not used: a class without SPEC_YIELD keeps the 0.2 (and the old warning text), so existing runs that name a class
  without SPEC_YIELD stay byte-identical. This is narrower than the plan's "use its SPEC_YIELD" (which would have turned the
  0.2 into the class default 0.1 silently).
- `GWExternal.cpp` ExtProbe: no SY (no STO or no SY array) and the class gives SPEC_YIELD -> `_extSy` = that value, warning
  "SPEC_YIELD s of :SoilZoneAquiferClass C is used for the soil-zone checks, the release limits and the unsaturated columns".
- Test `soilzone/test_v2_ext.py` X8: the X7 no-STO model + class SYCLASS (SPEC_YIELD 0.1) -> warning, Sy/drainable-porosity
  range 1.0 -> 0.5 in GWModelSummary, identities hold; a class without SPEC_YIELD -> 0.2, outputs identical to X7; X7 run
  against `RAVEN_EXE_REF` identical. Before: the warning is missing and the range stays 1.0 (X8 class fails).

## DOC sweep

Done (manual chapters, user guide, tests README, Liard README):
- L6: ch3 watch box and ch9 list: `:LayerConnection ELEVATION` named (new label `sec:layerconn`); an existing model keeps its
  own connections.
- L9: ch9, ch7 troubleshooting, UG: MODFLOW's error report is copied into Raven's message and Raven_errors.txt (verified in
  MF6Engine.cpp `MF6ExitHandler`).
- L15: "importing an existing model" removed from planned extensions; ch9 "Planned extensions" became "Not available".
- L16, L17: ch1 scope lists all grid types and the PHYSICAL interface iteration.
- L18: ch4 recharge refcard and FAQ rewritten (negative recharge from exchange processes such as PERC_GR4JEXCH; label
  `sec:negrecharge` on the soil-zone paragraph).
- L32: RECHARGE_DELAY remedy rows (appendix, ch4 refcard, ch6, UG troubleshooting and section 4.3c) point to
  `:SoilZoneVadose LAG`.
- L42: UG section 9 rewritten to match ch9.
- L3/L4/L8/L28 results in ch3 (new subsection "Projected input files", dry-layer paragraph), ch4_existing (`:MF6GridFile`,
  label `sec:mf6crs`, `sec:extlimits`), ch4_exchanges / ch4_sz_interface / appendix_sz_v3 / ch6 / appendix (Sy), ch6 and
  appendix command tables and error rows, ch7 (data preparation, checklist, troubleshooting, frozen-ground FAQ), ch8
  (geometry table rows, crs and dry-start paragraph, X8 row), UG sections 4.3, 4.3a, 4.3b, 8, 9.
- L5 (datum, the reservoir stop as only check), L14 (frozen ground: ch7 FAQ, ch9, UG), L27, L29, L33-L37 (ch9/UG lists):
  done in the lists. L1, L2, L40: already accurate.
- Left for Phase B: ch4_existing "Current limits" (F2, F3, F5-F7). The ch9 existing-model item lists only limits that Phase B
  does not touch, plus TS6 (F6 will remove it) and refers to `sec:extlimits` for the exchanges.

## Byte identity

- Every new code path runs only with `:InputCRS`, X/Y wells, a whole dry layer, or a steady existing model with a class that
  gives SPEC_YIELD. Raster sampling without a CRS uses the same doubles; the range checks only refuse inputs that could not
  have run correctly before.
- `wt/p7a/scratch/byteid.py` (p4's script with the paths of this worktree; reference for coupled runs = `wt/p4/Raven_p4.exe`,
  for runs without groundwater = `audit/CB/Raven_base.exe`; its text filter extended by "Build date" and "HRU/grid
  linkage" timing): results in the final report below.

- `SelectColumns` (boundary files): a polygon file refused for its coordinates stops with that message instead of falling
  through to the line reader ("no LineString features"); other polygon-reader errors give the same message as before.
  Checked by crs_inputs ("UTM boundary polygons without a crs member").

## Results

- `run_all.py --quick` (RAVEN_EXE_REF = wt/p4/Raven_p4.exe): 48 passed, 0 failed, 2 not run (USGS examples, no zip),
  3 SKIP lines (W4, W6, W11, as before); 3221 s. After the last code change (SelectColumns) the affected steps were run
  again: geomtest, crs_inputs_nolib, crs_inputs, dry_start, mf6files, edge_nolib, edge (53 of 53), soilzone_v2_ext,
  soilzone_liard (T7, 365 days): all PASS.
- byteid.py (2 years): 13 of 13 comparisons identical (no groundwater against base Raven incl. Nitrate/AGE and hotstarts;
  Liard CONCEPTUAL 180 d, Liard existing model 31 d, PHYSICAL+RICHARDS, CONCEPTUAL with unconverged steps against p4).
- crs_inputs full mode (120 days): all 19 checks pass, numbers as above.
- LaTeX: latexmk of a copy of docs/manual compiles without errors or undefined references.
