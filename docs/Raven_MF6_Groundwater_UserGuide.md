# Raven–MODFLOW 6 groundwater coupling: user guide

This chapter describes how to add a groundwater system to any Raven model. Raven builds a standard
MODFLOW 6 groundwater-flow model from information in the usual Raven input files, runs it in lock-step
with Raven through the MODFLOW 6 shared library (`libmf6`), and exchanges water every time step.
You never edit MODFLOW files; Raven writes them to `<output>/mf6/` so you can inspect them with FloPy or ModelMuse.

## 1. How it works

- HRUs with a groundwater system are marked by `AQUIFER_PROFILE` in the `.rvh` file.
- HRU polygons (GeoJSON) are intersected with a grid that Raven lays over those HRUs (regular by default; rotated, refined, quadtree, HRU-following mesh or imported cells, section 4.3a).
- Aquifer profiles in the `.rvp` file define the layer stack and hydraulic properties; land surface and
  bedrock come from rasters. One MODFLOW 6 model holds all profiles, so lateral flow, leakage and flow
  through aquitards between different groundwater systems are computed by MODFLOW itself.
- Every time step, after Raven's vertical and lateral processes and before routing:
  1. whatever Raven processes put into `GROUNDWATER` in coupled HRUs becomes MODFLOW recharge;
  2. river stages come from Raven reach depths; well rates and boundary heads from `.rvt` time series;
  3. MODFLOW solves (Newton–Raphson, so cells dry and rewet automatically);
  4. seepage where the water table reaches the model top returns to a Raven store, and aquifer–river
     exchange is added to or taken from the reaches (a loss from the reach's runoff, then its inflow, then its
     routed outflow: the take lowers the outflow delivered downstream, while the reach's routing keeps its own water,
     with every routing method; a loss no reach water can supply is carried to the next step, warned about, and
     reported in the run totals when still carried at the end).

Raven owns the soil and vadose zone; MODFLOW owns the saturated zone. In coupled HRUs `GROUNDWATER` is a
pass-through store: its end-of-step value is the recharge sent to MODFLOW. Raven's water balance counts it as
storage at the end of the step (`Deep Groundwater` in `WatershedStorage.csv`) and as leaving Raven when the next step
empties it, so each volume is counted once. An initial `GROUNDWATER` value in the `.rvc` of a cold start (no `:GWHeads`)
is emptied by the first step before any exchange, so MODFLOW never receives it; Raven warns: set it to 0. Groundwater
storage itself is reported by the files in section 5.

## 2. Requirements and building

- The MODFLOW 6 shared library: `libmf6.so` (Linux), `libmf6.dll` (Windows) or `libmf6.dylib` (macOS); 6.5 or later,
  tested with 6.8.1 and 6.6.3, 6.8 or newer recommended. Get it with one command in this repository (RavenHydroFramework-extra):

      python tools/get_mf6.py            # MODFLOW 6.8.1 for this computer, into lib/mf6 of your Raven checkout

  (`--latest` or `--version 6.x.y` for another release, `--zip file` for a release zip downloaded by hand,
  `--raven PATH` when the Raven checkout is not beside this repository). The script downloads the release zip from
  https://github.com/MODFLOW-ORG/modflow6/releases and keeps only the library. MODFLOW 6.8 is released for Linux
  x86_64, Windows 64-bit and Apple Silicon Macs; Intel Macs need an earlier release.
- Raven with the coupling: the RavenHydroFramework source (the coupling is offered to the Raven team for inclusion;
  until it is part of Raven, use the `mf6-coupling` branch of https://github.com/rarabzad/RavenHydroFramework), cloned
  beside this repository
  (https://github.com/rarabzad/RavenHydroFramework-extra, branch `main`):

      git clone -b mf6-coupling https://github.com/rarabzad/RavenHydroFramework.git
      git clone https://github.com/rarabzad/RavenHydroFramework-extra.git

  Offline, the release package's `source/` folder holds both as git bundles (its README, "Restore the git history").
  Build it as usual: CMake
  (`cmake -S . -B build` and `cmake --build build --config Release`; a single-configuration generator without
  `CMAKE_BUILD_TYPE` builds Release) or `make` in `src/` (both link `-ldl`); on Windows also `src/Raven.sln`. CMake also
  gets the MODFLOW 6 library (option `RAVEN_MF6`): by default it builds it from source (`SOURCE`) when a Fortran compiler,
  meson, ninja and git are found and the MODFLOW repository answers at configure time, otherwise it downloads the official
  release library (`PREBUILT`), and without network it builds Raven alone (`OFF`, with a warning); `-DRAVEN_MF6=PATH
  -DRAVEN_MF6_PATH=...` uses a library you have. A library older than 6.5.0 stops the configure when its version is
  known there (`SOURCE`, `PREBUILT`, a zip or source folder); a `PATH` library's version is checked when Raven loads it,
  and an older one stops the run. Raven builds and runs without MODFLOW; the library is loaded only when
  `:GroundwaterModel MODFLOW6` is used.
- Raven finds the library by itself: next to its executable, or in `lib/mf6/` of its checkout (one to three folders
  above the executable, as for `src/Raven.exe`, `build/Raven`, `build/Release/Raven.exe` or Visual Studio's
  `src/x64/Release/Raven.exe`). `:MF6Library` in the `.rvg`
  file or the `RAVEN_MF6_LIB` environment variable override this; the system library path is searched last.
  `GWModelSummary.txt` names the library used and its version.

## 3. Quick start: four edits

1. `.rvh`: fill the `AQUIFER_PROFILE` column (`[NONE]` = no groundwater under this HRU).
2. `.rvp`: add `:AquiferClasses`, `:AquiferProfiles` and (optionally) `:AquiferProfileParameters`.
3. `.rvg`: at minimum `:HRUGeometry`; usually also `:LandSurface`, `:BedrockSurface`, `:RiverGeometry`, `:GridCellSize`.
4. `.rvi`: add `:GroundwaterModel MODFLOW6` and route recharge into `GROUNDWATER` for coupled HRUs, e.g.

```
:GroundwaterModel MODFLOW6
:DefineHRUGroups  AquiferHRUs
:HydrologicProcesses
  ...
  :Percolation PERC_CONSTANT FAST_RESERVOIR SLOW_RESERVOIR
    :-->Conditional HRU_GROUP IS_NOT AquiferHRUs
  :Percolation PERC_CONSTANT FAST_RESERVOIR GROUNDWATER
    :-->Conditional HRU_GROUP IS AquiferHRUs
:EndHydrologicProcesses
```

Raven stops with an error if a process removes water from `GROUNDWATER` in a coupled HRU (MODFLOW owns
that storage) or if no process sends water to `GROUNDWATER`.

## 4. Input reference

The groundwater file is `<model>.rvg` by default; `:rvg_Filename file` in the `.rvi` names another file (relative to the `.rvi`).

### 4.1 `.rvh`

`AQUIFER_PROFILE` (existing HRU column): profile name from `:AquiferProfiles`, or `[NONE]`.

### 4.2 `.rvp`

```
:AquiferClasses
  :Attributes, K_HORIZ, K_VERT, SPEC_STORAGE, SPEC_YIELD, POROSITY
  :Units,      m/d,     m/d,    1/m,          none,       none
  GRAVEL,      50.0,    5.0,    1.0E-5,       0.25,       0.30
:EndAquiferClasses
```

| Attribute | Default | Notes |
| --- | --- | --- |
| K_HORIZ | required | horizontal hydraulic conductivity [m/d] |
| K_VERT | K_HORIZ/10 | vertical hydraulic conductivity [m/d] |
| SPEC_STORAGE | 1e-5 | specific storage [1/m] |
| SPEC_YIELD | 0.1 | specific yield [-] |
| POROSITY | 0.3 | saturated water content of the unsaturated columns (`:SoilZoneVadose`, at least SPEC_YIELD); not used by MODFLOW's flow |
| CLAPP_B | 4 | Clapp-Hornberger exponent b of the unsaturated columns |
| AIR_ENTRY_PRESSURE | 0.3 m | air-entry suction of the unsaturated columns |

```
:AquiferProfiles
  # name, nLayers, {class, thickness [m] | TO_BEDROCK, layer type} x nLayers
  VALLEY_ALLUVIUM, 3, GRAVEL, 15.0, AQUIFER, CLAY_TILL, 5.0, AQUITARD, SAND, TO_BEDROCK, CONFINED_AQUIFER
:EndAquiferProfiles
```

| Layer type | MODFLOW 6 | Behaviour |
| --- | --- | --- |
| AQUIFER (UNCONFINED_AQUIFER) | ICELLTYPE 1, ICONVERT 1 | convertible: Sy and saturated-thickness transmissivity when unconfined |
| CONFINED_AQUIFER | ICELLTYPE 0, ICONVERT 0 | constant transmissivity, Ss only |
| AQUITARD | convertible, low K from class | explicit leaky layer |
| AQUICLUDE | IDOMAIN 0 | no-flow barrier; not allowed as the top layer |

Layers thinner than 0.5 m after clipping at bedrock become vertical pass-through cells. Layer k of one
profile connects laterally to layer k of a neighbouring profile, so list layers in the same stratigraphic
order where profiles meet.

```
:AquiferProfileParameters
  :Attributes,     INITIAL_HEAD_DEPTH, SEEPAGE_LEAKANCE, RECHARGE_DELAY
  :Units,          m,                  1/d,              d
  VALLEY_ALLUVIUM, 3.0,                1.0,              0.0
:EndAquiferProfileParameters
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| INITIAL_HEAD_DEPTH | 5.0 m | initial water-table depth below land surface |
| DEFAULT_BEDROCK_DEPTH | 50.0 m | bedrock depth where no bedrock raster is given |
| SOIL_ZONE_DEPTH | 0.0 m | model top below land surface (0 = land surface) |
| SEEPAGE_LEAKANCE | 1.0 1/d | seepage-face conductance per unit area |
| SEEPAGE_SMOOTHING_DEPTH | 0.5 m | seepage starts this far below the model top and reaches full conductance at it |
| RIVERBED_K | 0.5 m/d | riverbed hydraulic conductivity |
| RIVERBED_THICKNESS | 1.0 m | riverbed thickness |
| EXTINCTION_DEPTH | 0.0 m | water-table ET extinction depth (0 = no water-table ET) |
| RECHARGE_DELAY | 0.0 d | linear-reservoir lag between Raven and the water table (0 = direct) |

### 4.3 `.rvg`

| Command | Default | Meaning |
| --- | --- | --- |
| `:HRUGeometry file {id field}` | required; field `HRU_ID` | HRU polygons (GeoJSON, lon/lat or `:InputCRS`) |
| `:RiverGeometry file {subbasin field}` | none | river lines; without a field, each piece belongs to the subbasin of the dominant HRU in its cell |
| `:LandSurface file` | HRU ELEVATION | DEM, ESRI ASCII grid or GeoTIFF (`.tif`, `.tiff`) in lon/lat or `:InputCRS`; averaged over each cell |
| `:InputCRS EPSG:code` or `TMERC\|ALBERS\|LCC ...` | lon/lat | projection of every geometry and raster input file (grammar of `:MF6CRS`); wells may then be given by X, Y |
| `:BedrockSurface file` | DEFAULT_BEDROCK_DEPTH | bedrock elevation raster, same formats |
| `:GridCellSize m` | 1000 | base cell size [m] of the grid |
| `:MinCellCoverage f` | 0.25 | fraction of a cell covered by coupled HRUs needed to activate it |
| `:MF6Library path` | RAVEN_MF6_LIB | MODFLOW 6 shared library |
| `:SeepageReturnTo SV` | lowest soil layer | Raven store receiving groundwater seepage (HRUs without soil layers: SURFACE_WATER) |
| `:RiverBedDepth m` or `REFERENCE_FLOW` | REFERENCE_FLOW | channel bed depth below the DEM along rivers |
| `:GWInitialization STEADY_STATE r` | off | steady-state first stress period with uniform recharge r [mm/d] If the steady state does not converge (e.g. wells pumping more than the aquifer supplies), the run starts from the initial heads, with a warning. |
| `:SurfaceWaterExchange SV group LEAKANCE L` | none | Raven store (e.g. DEPRESSION, LAKE_STORAGE) of an HRU group exchanging with the aquifer; leakance L [1/d]; never draws more water than the store holds |
| `:ReservoirExchange` | off | couple Raven reservoirs that have :SeepageParameters and a lake HRU (:HRUID) with an AQUIFER_PROFILE: the water table under the lake (never below the lake bed, the ground: with :SoilZone PHYSICAL above the soil zone; a lake above a deep water table is disconnected) sets the reservoir's local groundwater head, only the share of the lake over cells that can take seepage (not specified heads) exchanges water, and its seepage enters the aquifer the next step; stages must be absolute (:AbsoluteCrestHeight) |
| `:WriteNetCDFHeads` | off | full head field to GWHeads.nc every :HeadSaveFrequency steps (Raven built with -Dnetcdf) |
| `:WriteGWBudgetFile` | off | generated models: MODFLOW budget file `mf6/gwf.cbc` (every package's flows, specific discharge, saturation) every :HeadSaveFrequency steps and `mf6/gwf.porosity` (class POROSITY per cell), for offline particle tracking with `tools/make_prt.py`; the solution is unchanged |
| `:LinkageCache file` | <output>/mf6/linkage.cache | cached HRU/grid intersection reused by later runs |
| `:SolverMaxOuterIterations n` | 500 | Newton outer iterations per step |
| `:SolverHeadTolerance m` | 0.00001 | Newton head-change tolerance (target); after 100 iterations MODFLOW continues with 10x this tolerance for the rest of that step (GWBudget `converged`=2) |
| `:HeadSaveFrequency n` | 30 | steps between saves of the full head field (`mf6/gwf.hds`) |
| `:Wells` table | none | NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT [m] (with `:InputCRS`: X, Y [m] instead of LATITUDE, LONGITUDE); rates from `.rvt` |
| `:ObservationWells` table | none | NAME, LATITUDE, LONGITUDE (or X, Y), SCREEN_ELEV [m] |
| `:GeneralHeadBoundary name file HEAD h CONDUCTANCE c {LAYERS ALL\|TOP}` | none | head-dependent boundary; c per cell [m2/d] |
| `:SpecifiedHeadBoundary name file HEAD h {LAYERS ALL\|TOP}` | none | fixed-head boundary |

Boundary files are GeoJSON: polygons select cells whose centre lies inside (holes excluded; overlapping features or parts
of a MultiPolygon add up, they never cancel); lines select cells they cross.
A boundary is placed only in layers whose bottom lies below its head. MODFLOW ignores recharge on a
specified-head cell: the recharge of an HRU's overlap with such cells goes to the specified head (`recharge onto CHD
cells` in `GWBudget.csv`), and its other cells receive the recharge of their own overlap.

```
:Wells
  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_TOP, SCREEN_BOT
  1, PW_1, 59.2731, -124.7346, 1199.7, 1188.7
:EndWells
:ObservationWells
  :Attributes, NAME, LATITUDE, LONGITUDE, SCREEN_ELEV
  101, OW_NEAR, 59.2731, -124.7306, 1192.7
:EndObservationWells
```

Well pumping is split over the screened layers by transmissivity; MODFLOW's AUTO_FLOW_REDUCE lowers
pumping as a cell dries (GWBudget.csv reports specified and actual rates).

**Projected inputs.** `:InputCRS EPSG:32610` (or another built-in code: UTM 326xx/327xx and NAD83 269xx, 3005, 5070,
3978, 3347, ESRI:102001; or `TMERC`, `ALBERS`, `LCC` by their parameters) says that every GeoJSON and raster input file
(`:HRUGeometry`, `:RiverGeometry`, `:GridFile`, refinement and boundary files, `:LandSurface`, `:BedrockSurface`, and
`:MF6GridFile` for an existing model) is in that projection; rasters are sampled in their own coordinates, without
resampling. Raven stops on a GeoJSON file whose `"crs"` member names a projection other than `:InputCRS` (or a projected
one without it, or lon/lat with it), and, without `:InputCRS`, on coordinates or raster extents outside the lon/lat range;
with `:InputCRS`, on a GeoJSON file or raster left in lon/lat ("looks like longitude/latitude": its coordinates lie over
the HRUs' LATITUDE/LONGITUDE, not near them in the projection). The `"crs"` member is read by the code that ends its name
(also a versioned URN such as `urn:ogc:def:crs:EPSG:6.6:4326`); geographic codes mean lon/lat: the geographic 2D and 3D
systems of the EPSG registry, a table compiled into Raven (e.g. 4326, 4979, 4269, 4617, NAD83(2011) 6318; not every code
of the 4000s: 4647, ETRS89 / UTM 32N, is a projection; geographic codes that are not degrees from Greenwich, such as 4801
Bern, are refused, and so are projected codes in feet or other units, such as 2227); a projection that is not built in is
accepted, and its coordinates decide. A file with a UTF-8 byte-order mark is read. `:InputCRS` and `:MF6CRS` parameters
are read strictly: plain numbers only (`O.9996` or `500km` stop the run), exactly five (TMERC) or six (ALBERS, LCC) of
them and at most an ellipsoid, nothing after an EPSG code. Outputs stay in lon/lat.

**Rasters.** `:LandSurface` and `:BedrockSurface` read ESRI ASCII grids, and GeoTIFF files when the name ends in `.tif`,
`.tiff` or `.gtiff` (any case), with Raven's own reader (no GDAL needed); both are sampled the same way. An ESRI ASCII grid
may give `xllcenter`/`yllcenter`, rectangular cells by `dx` and `dy` (as GDAL writes them) and `NODATA_value nan`; it must
hold exactly ncols x nrows numbers (an unknown header key, a value that is not a number, or too few or too many values
stop the run). GeoTIFF support: classic and
BigTIFF, either byte order, strips or tiles; no compression, LZW, DEFLATE or PackBits, with predictor 1, 2 or 3; one band
of 8-64 bit integers or 32/64-bit floats; north-up georeferencing (`ModelPixelScale` + `ModelTiepoint`, or a
`ModelTransformation` without rotation); `PixelIsPoint` (the tie point is a pixel centre, so the corner is half a pixel up
and left, as GDAL reads it); `GDAL_NODATA` and a GDAL internal mask as no-data (NaN is always no-data). Without either,
every value is an elevation, as GDAL reads it; Raven warns when such a file holds -9999 or a type's extreme value. GDAL's band
scale and offset (`GDAL_METADATA`) are applied, as GDAL's `-unscale` and GIS programs show the values. Other compressions (JPEG, ZSTD, LERC, ...),
several bands, palette or colour images, other bit depths, FillOrder 2, units other than metres or degrees (units keys),
a projected code in feet without its units key (e.g. EPSG:2227), a prime meridian other than Greenwich (also given only by
its longitude, as GDAL writes a user-defined system such as `+pm=paris`, or by the datum), a vertical coordinate system
in feet, a band unit whose first unit is feet or another length unit than metres (an unknown band unit gives a warning),
rotated or south-up rasters, files without georeferencing,
corrupt or truncated files and files over 1 GB or 50 million pixels stop the run with the reason; convert with
`gdal_translate -b 1 -co COMPRESS=DEFLATE`. The GeoTIFF's EPSG code is checked: a geographic code needs no `:InputCRS`, a
projected one needs `:InputCRS` with the same projection (a code that is not built in is accepted under `:InputCRS` given
by parameters, with a warning, and refused under `:InputCRS` given as a code, EPSG or ESRI); a user-defined CRS or none is checked by its extent, as an ESRI ASCII grid. A raster that
gives no value for any active column (another area, a wrong corner or projection, NODATA only) stops the run with the
raster's and the model's extents; one that misses some columns gives a warning with their number.

### 4.3a Grid options (`.rvg`)

| Command | Meaning (default) |
|---|---|
| `:GridType REGULAR\|QUADTREE\|HRU_MESH\|FILE` | kind of grid (`REGULAR`) |
| `:GridRotation deg` | rotation of regular and quadtree grids, counterclockwise (0) |
| `:GridRefinement RIVERS s` / `WELLS s` | cells of size `s` [m] along rivers / around wells and monitoring wells |
| `:GridRefinement LAKES 250` | finer cells in and around every reservoir's lake HRU (outline from `:HRUGeometry`) |
| `:GridRefinement LINES file s` / `POLYGONS file s` | cells of size `s` along lines / in and around polygons (GeoJSON, lon/lat or `:InputCRS`) |
| `:GridFile cells.geojson ID` | imported cells (one single-ring polygon per cell), with `:GridType FILE` |
| `:QuadtreeMaxLevel n` | maximum halvings of `:GridCellSize` (from the refinement sizes) |
| `:FlowCorrection AUTO\|XT3D\|XT3D_RHS\|NONE` | XT3D conductance tensor; `AUTO` = off (XT3D can slow convergence where cells dry and rewet) |
| `:LayerConnection INDEX\|ELEVATION` | connect neighbouring layers by number or by overlapping elevation (DISU) |

MODFLOW formats: regular grids are written as DIS, quadtrees as DISV, HRU meshes, imported cells and
`:LayerConnection ELEVATION` as DISU. Every run writes `mf6/grid_cells.geojson` (all cells, lon/lat) for mapping.
Rivers and boundary lines are clipped exactly by every cell; a boundary drawn along the edge of the active area is
attached to the nearest active cell. `RAVEN_GW_PROFILE=1` prints the time of each model-building stage.

### 4.3b Coupling an existing MODFLOW 6 model (`.rvg`)

Raven links its coupled HRUs (those with an `AQUIFER_PROFILE`) to the top active layer of the user's model and leaves the
model intact (it works on a copy in `<output>/mf6/`).

The model's files hold the layers and hydraulic properties, so profiles need no layers and no `:AquiferClasses` are
needed: write each profile as `name, 0`. A profile then only marks the coupled HRUs and carries the exchange settings
(`SEEPAGE_LEAKANCE`, `SEEPAGE_SMOOTHING_DEPTH`, `RECHARGE_DELAY`, `EXTINCTION_DEPTH`). Layers listed in a profile are ignored, with a warning.

```
:AquiferProfiles
  VALLEY_ALLUVIUM, 0
:EndAquiferProfiles
```

| Command | Meaning |
|---|---|
| `:MF6Simulation model/mfsim.nam` | the existing simulation (DIS or DISV) |
| `:MF6Model name` | the GWF model to couple, if the simulation holds several |
| `:MF6StartDate yyyy-mm-dd` | calendar date of the model's time zero (Raven may start later: restarts) |
| `:MF6CRS EPSG:32610` | projection of the model's coordinates; Raven reads the cell outlines from the model. Built in: UTM (EPSG 326xx/327xx, NAD83 269xx), 3005, ESRI:102001, 5070, 3978, 3347, or `TMERC`/`ALBERS`/`LCC` parameters |
| `:MF6GridFile cells.geojson CELL_ID` | alternative: top-layer cell polygons (lon/lat or `:InputCRS`), checked against MODFLOW's cell areas |
| `:OverlapWeights ... :EndOverlapWeights` | alternative: `[HRU ID] [cell] [A_overlap/A_cell]` rows (MODFLOW-USG coupling format) |
| `:RavenTakesOver p ...` / `:KeepPackages p ...` | every recharge, ET or UZF package must be declared one way or the other |
| `:StreamPackage p {AUX name / DOMINANT_HRU}` | RIV/DRN/GHB package whose flows go to Raven's reaches (subbasin from an auxiliary variable, default SUBBASIN) |
| `:SeepageToRaven ON/OFF` | DRN_RAVEN at the model top (default ON) |

Each HRU's recharge is split by its relative overlaps, so its volume reaches MODFLOW exactly whatever the delineation
quality. Units (feet, seconds, ...) are converted automatically. The model's own solver settings are used; allow at
least 500 outer iterations (OUTER_MAXIMUM), as the first coupled step (often a steady-state period) is the hardest. `GWBudget.csv` gains a column with the net flow of the
model's own packages (including the water they pass to the model's water mover). See the manual, chapter "Coupling an
existing MODFLOW 6 model".

- **Water mover (MVR):** movers from or to a package Raven takes over (for example a UZF package whose rejected
  infiltration goes to SFR) are removed from the working copy and counted in `GWModelSummary.txt`; a stream package that
  sends water through the mover is refused (its water would be counted twice).
- **Steady-state models** (no storage package, one stress period of any length): the period is stretched over Raven's
  run, so every Raven step is a steady-state solution; the storage column stays zero.
- **Exchanges as in a generated model:** water-table ET (`EXTINCTION_DEPTH` > 0; Raven adds `EVT_RAVEN` at the top active
  cells, so the model's own EVT/UZF must be taken over, not kept), `:SurfaceWaterExchange` (`SWX_RAVEN`) and
  `:ReservoirExchange` (`RES_RAVEN`), all in the model's units. Raven warns when the model has its own LAK or SFR package
  (the same lake must not be in both).
- **Reservoir seepage** (`:ReservoirExchange`): only the part of the lake over cells that can take seepage in the step
  exchanges water. Those are the lake HRU's linked cells that are not the model's specified heads in the step and (in a
  model without NEWTON) not inactive; with F their share of the lake's linked area, the reservoir's seepage is computed
  with the constant k F (k from `:SeepageParameters`; F = 1 when every cell can take seepage, and with none the lake
  exchanges nothing). The next step the volume is delivered (`RES_RAVEN`) to the cells that can take it then, each at
  most at the rate it had when the seepage was computed. A loss MODFLOW does not take (cells that have become specified
  heads or inactive, or the part beyond those rates) is returned to the reservoir's subbasin in the same step and flows
  on into the reservoir (`GWBudget.csv`: `reservoir seepage not delivered by MODFLOW [m3]`; a warning and a run total in
  `GWModelSummary.txt`); a gain (groundwater into the lake) MODFLOW does not supply is taken back from the water reaching
  the subbasin (`reservoir gain not supplied by MODFLOW [m3]`; a warning and a run total). The seepage in transit and its
  share F are saved in `solution.rvc` (`:GWReservoirSeepage`). Manual: "Reservoirs".
- **Later starts and restarts:** stress periods already simulated are dropped and the rest renumbered; TS6 time series are
  shifted to Raven's start (earlier entries keep negative times); TDIS and water-mover period data may sit in OPEN/CLOSE
  files; sub-daily steps work (the start must fall on a Raven step). TAS6, TVK6/TVS6, simulations with several models
  and a TS6 file whose TIMESERIES rows come from another file (OPEN/CLOSE or INTERNAL) stop a later start.
- **Budget file:** the model keeps its own output control; add `BUDGET FILEOUT` and `SAVE BUDGET` to its OC file for
  `gwf.cbc` (RCH_RAVEN, DRN_RAVEN, EVT_RAVEN, SWX_RAVEN and RES_RAVEN save their flows to it). `:WriteGWBudgetFile` is for generated models.
- Tested on USGS example models (Sagehen Creek with UZF, SFR and mover; a steady-state stream-capture model) with MODFLOW
  6.8.1 and 6.6.3: `tests/existing/usgs_sagehen.py`, `usgs_capture.py`.

### 4.3c The soil zone and the water table (`.rvg`)

By default (`:SoilZone CONCEPTUAL`) Raven's soil and the aquifer meet only through recharge and the seepage drain. With
`:SoilZone PHYSICAL` Raven owns the listed soil layers, MODFLOW starts below them (model top = land surface minus their
thickness, cell by cell, so it follows the slope), and the water table can rise into them, as in GSFLOW. It works with
a model Raven builds and with an existing MODFLOW model (`:MF6Simulation`), which must then use the `NEWTON`
formulation (Raven stops at start-up otherwise; MODFLOW also needs `LINEAR_ACCELERATION BICGSTAB`).

```
:SoilZone PHYSICAL SOIL[0] SOIL[1]      # soil-zone layers, from the top (default CONCEPTUAL; the last :SoilZone counts)
:SoilZoneIteration 100 1.0E-4 1.0E-6    # optional: interface updates (0 = explicit), head [m] and relative flow tolerances
:SoilZoneSubgrid 5                      # optional: DEM points per cell side (25 per cell) for sloping and irregular land
:SoilZoneOutput WetlandHRUs             # optional: GWSoilExchange.csv for one HRU group (default all soil-zone HRUs)
:SoilZoneVadose RICHARDS 0.02 16        # optional: unsaturated columns below the soil (default NONE), see below
:SoilZoneVadoseClasses 3                # optional: unsaturated columns per exchange column, one per depth class (1-10; default 1)
:SoilZoneVadoseInitialFlux 2            # optional: columns start steady for 2 mm/d on a cold start (default 0: at rest)
:SoilZoneCapillaryRise ON               # optional: default ON with RICHARDS, KINEMATIC or LAG, OFF with NONE
:SoilZoneExchangeTiming LAGGED          # optional: LAGGED (default) or AFTER
:SoilZoneClasses 3                      # optional: Raven's processes per wetness class of an HRU's columns (1-50; default 1)
:SoilZoneAquiferClass SAND              # existing models only: CLAPP_B, AIR_ENTRY_PRESSURE, POROSITY for the columns
```

| Command | Default | Meaning |
| --- | --- | --- |
| `:SoilZone CONCEPTUAL` / `PHYSICAL SOIL[0] ... SOIL[M-1]` | CONCEPTUAL | the soil zone owned by Raven, from the top; the last `:SoilZone` counts |
| `:SoilZoneIteration n {head tol} {flow tol}` | 100, 1e-4 m, 1e-6 | interface updates after MODFLOW's outer iterations (n >= 0; 0 = explicit coupling) and their tolerances (> 0) |
| `:SoilZoneSubgrid n` | 5 | DEM points per cell side (1-20); n x n points carry the land's relief into each cell |
| `:SoilZoneOutput group` | all | HRU group written to `GWSoilExchange.csv` |
| `:SoilZoneVadose NONE` / `RICHARDS {eps} {N}` / `KINEMATIC {eps} {N}` / `LAG {t_m} {N}` | NONE (eps 0.02, t_m 0, N 16) | unsaturated columns between the soil-zone base and a deeper water table: Richards' equation, a kinematic wave or a linear storage cascade; eps = largest content change in a substep (0, 0.2]; t_m = travel time per metre [d/m] (0: derived from each material); N = nodes per column, 3-200 |
| `:SoilZoneVadoseClasses K` | 1 | up to K unsaturated columns per exchange column, one per depth class of its DEM points (1-10); ignored (warning) with NONE |
| `:SoilZoneVadoseInitialFlux q` | 0 | cold start: each column starts at its steady profile for the flux it receives, (1-F) q [mm/d]; ignored (warning) on a groundwater hotstart and with NONE |
| `:SoilZoneCapillaryRise ON/OFF` | ON with an unsaturated column (RICHARDS, KINEMATIC, LAG), OFF with NONE | capillary rise from the water table (and, with RICHARDS, from the columns' top nodes) into soil-zone layers below field capacity |
| `:SoilZoneExchangeTiming LAGGED/AFTER` | LAGGED | LAGGED: last step's exchange is lent to the soil before Raven's processes and settled after the step's exchange (splitting error scales with the change of the exchange: 0.7 cm of head on the hillslope test against 1.8 cm with AFTER); AFTER: the exchange follows Raven's processes |
| `:SoilZoneClasses K` | 1 | Raven's processes run on up to K wetness classes of an HRU's columns (1-50); needs `:Method ORDERED_SERIES` |
| `:SoilZoneAquiferClass class` | b 4, psi_a 0.3 m, theta_s Sy+0.1 | existing models: retention of the cells for the unsaturated columns (conductivity and specific yield come from the model; a steady model without specific yield takes the class's SPEC_YIELD when given, else 0.2); ignored (warning) on a model Raven builds |

- Recharge must leave the soil zone from its bottom layer (`:Percolation ... SOIL[1] GROUNDWATER` here).
- Each soil-zone layer needs a positive thickness, `POROSITY` and `FIELD_CAPACITY` < 1 (drainable porosity); the soil
  class of the bottom soil-zone layer needs `HYDRAUL_COND` [mm/d], which with `K_VERT` of the top aquifer layer sets
  the soil-aquifer conductance. Capillary rise uses `CLAPP_B` and `AIR_ENTRY_PRESSURE` [mm] of the soil classes.
  `SEEPAGE_SMOOTHING_DEPTH` sets how smoothly a point comes into contact (through that depth below its base) and
  saturates; keep it at 0.1-0.5 m (below 0.1 m a warning). `RECHARGE_DELAY` must be 0 for soil-zone HRUs
  (`:SoilZoneVadose LAG` delays recharge below the soil zone instead); `SOIL_ZONE_DEPTH` and `SEEPAGE_LEAKANCE` are not used for them. A soil zone thicker than 20 m stops the run, over 5 m
  gives a warning.
- The soil zone of each HRU is kept per overlapping cell (columns, saved in `solution.rvc` as `:GWSoilZoneColumns`);
  Raven's `SOIL[m]` holds their mean. Where the water table is in the soil, recharge is rejected (stays in the soil),
  saturated soil drains to the aquifer, groundwater rises into the soil, and a full soil zone overflows to
  `SURFACE_WATER`. Rain falls alike on every column (overflowing where full) and an HRU's recharge leaves the columns that
  gave it up (not shared by area). Water-table ET is reduced on saturated ground; the seepage drain serves only HRUs
  without soil. Columns over specified-head cells exchange with the fixed head exactly.
- **Sloping and irregular land.** Between cells each column sees its own water table, so an HRU can be saturated at its
  foot and dry at its top. Within a cell the DEM points give each point its own soil-zone base: a rising water table
  saturates the low points first, and the saturated fraction F (the share of recharge rejected) grows smoothly with the
  water table. Saturated areas or seepage faces narrower than a cell need smaller cells. Manual: Section "Sloping and
  irregular land" and the rough-terrain verification.
- The soil zone and MODFLOW are iterated within each step until they agree. The saturated fraction that rejects recharge
  is recomputed on every interface update from MODFLOW's current head (a head-dependent term inside MODFLOW's iteration),
  so the rejection follows the converged head. The flows Raven applies are always those MODFLOW booked, so water is
  conserved even on a step that did not converge (reported in `Raven_errors.txt`, first ten warnings of each kind).
- Unsaturated columns (`:SoilZoneVadose`) carry the recharge from the soil-zone base down to a water table more than 5 cm
  below it, with its delay and spreading, and follow the water table as it moves (saved as `:GWVadoseColumns`, and
  `:GWVadoseClassColumns` with depth classes, each naming the method that wrote it). `RICHARDS` and `LAG` read each
  other's hotstarts (the same reference profile); `KINEMATIC` counts the water from another reference, so on a restart
  that switches to or from it the columns start at rest, and the run warns and reports the water dropped
  (`hotstart columns unused` in the run totals, as for hotstart lines that match no column of the run). Give the aquifer classes
  `POROSITY`, `CLAPP_B` and `AIR_ENTRY_PRESSURE`, and an `SPEC_YIELD` close to the drainable porosity their retention
  curve implies (a warning when they differ by more than a factor two). A rising water table takes from a column at most
  what MODFLOW stores for the rise (Sy dh, and no more than the room left in the top cell); the column keeps the rest for
  the next steps. This happens when the rise meets more water above equilibrium than Sy dh: water in transit in the
  column (the `LAG` store, a `RICHARDS` wetting front, a recharge pulse) or a nearly full top cell, and the more readily
  the smaller `SPEC_YIELD` is against the drainable porosity. A column at rest or under a small steady flux, and a water
  table raised by a boundary or lateral inflow, do not reach it, whatever `SPEC_YIELD`. Raven warns the first time in a
  run, and no water is lost. Column water goes back to the soil zone, as
  rejected recharge, where the water table rises during a step onto ground unsaturated at its start (rule (i)) and when a
  column vanishes beyond what MODFLOW stores for the rise (rule (ii)); it is subtracted from the unsaturated-zone inflow,
  which is therefore negative on steps where the columns hand back more than they receive (manual, "The unsaturated
  column").

Outputs: `GWBudget.csv` gains soil-zone exchange (both ways), rejected recharge, overflow, applied volume, shortfall (0
when the interface converges), interface updates, converged and change, layer redistribution, withheld discharge, and
negative recharge not held; with unsaturated columns also unsaturated-zone inflow, outflow to the aquifer, capillary rise
to the soil zone and storage; with capillary rise the rise from the water table; with LAGGED timing the lagged-exchange
debt and repayment; with columns over specified heads (or an existing model) the exchange with specified heads; for an
existing model without NEWTON (CONCEPTUAL only) the recharge not applied by MODFLOW. `GWSoilExchange.csv` gives per HRU
and step the soil-zone base, soil water level, water table, saturated fraction, exchange both ways, rejected recharge,
overflow, soil water and capacity, and two model-wide values of the step repeated on every row (interface updates and
change). `GWModelSummary.txt` ends with run totals
(unconverged steps, substeps, supply-limited updates, withheld discharge, ...). `tools/plot_soilzone.py OUTPUT_FOLDER`
plots the exchange (with specified heads too, where there are soil-zone columns over them). Manual: Section "The soil zone and the water table", the reference table of the soil-zone commands
(chapter "Inputs and outputs") and the setup guide "A water table in the soil, on sloping and irregular land".

### 4.4 `.rvt`

```
:WellFlowRate 1 m3/d             # well ID and units (m3/d; m3/s and L/s are converted); negative = pumping, positive = injection
  1985-10-01 00:00:00 1.0 1826
  0.0
  ...
:EndWellFlowRate
:BoundaryHead GHB1 m             # overrides HEAD of the named boundary (heads in m)
  ...
:EndBoundaryHead
:ObservationData GW_HEAD 101 m   # observation-well ID; scored in Diagnostics.csv
  ...
:EndObservationData
```

Observed heads at date D are compared with the simulated head at D (end of the previous step).

A boundary with a `:BoundaryHead` series is placed in the layers its series reaches (its highest value; `HEAD` as well
only where the series is blank), down to the series' lowest value with `LAYERS TOP`. On a step whose head lies at or
below a placed cell's bottom the cell is switched off (GHB conductance 0, CHD cell not held); the cell-steps switched
off, a steady-state first period included, are reported in `GWModelSummary.txt`. A column whose specified-head cells
are all switched off is an ordinary column on that step: its recharge, soil zone, surface stores and lake exchange with
its cells, and nothing is booked onto specified-head cells (manual, "Where boundaries go").

### 4.5 `.rvc`

```
:InitialGWHeads DEPTH_BELOW_SURFACE 5.0   # or FROM_PROFILE (default), or ELEVATION [m]
```

The value is a plain decimal number in metres (`98.5`), optionally followed by a `#` comment; `FROM_PROFILE` takes no
value. It is read strictly, as the numbers of the `.rvg`: `98,5` (a decimal comma: two values), `H98.5` or `0x62` stop
the run naming the command.

In a coupled run Raven's `solution.rvc` holds every value with 17 significant digits (the HRU states, the channel and
reservoir states and the groundwater blocks; a run without groundwater writes Raven's usual 5 decimals, and reservoir stages and flows with 12 digits, with or without groundwater). It also contains
`:GWHeads nlay nrow ncol` (the head of every cell), and when needed `:GWRechargeStore` (recharge-delay stores), `:GWReservoirSeepage` (reservoir
seepage in transit), `:GWRiverLossCarry` (river loss still to be taken), `:GWRiverTake` (the river loss taken from
reach inflows and outflows in the last step, which Raven's channel storage and balance book half in the next step, with
the time step of the takes: a restart with another `:TimeStep` still gives up exactly the take), `:GWRiverInflowTakes`
(the takes from each reach's inflow over the steps of Raven's inflow history, which a restart with a longer `:TimeStep`
averages as Raven averages the inflows; Raven's own averaging of the inflow history can still change its `MB Error` in
such a restart, also without groundwater: a known issue of Raven itself, section 9),
`:GWStartHeads` (after an unconverged step: the heads of the last converged step, for the far-head test), and with `:SoilZone PHYSICAL`
`:GWSoilZoneColumns` (soil-zone columns), `:GWVadoseColumns`, `:GWVadoseClassColumns` and `:GWVadoseColumnTops`
(unsaturated columns; the column lines name the method that wrote them; a column whose top, node count, classes or
method's reference profile differ starts at rest, and the water of lines no column uses is warned about and reported as
dropped) and `:GWSoilZoneLag` (LAGGED timing: last step's exchange and open debt; a restart with AFTER timing or without
`:SoilZone PHYSICAL` does not repay that debt, and warns and reports it), each closed by its `:End...` line. A corrupt
`:GWHeads` header, a value that is not a finite number in any of these blocks, or negative water in the soil-zone or
unsaturated columns stops the run with a message. In a coupled run, a run continued from `solution.rvc` (as the `.rvc`
of the next run) carries on exactly where the previous run stopped (the restarted run starts from the states as they
were, bit for bit): seepage held above the capacity of its target soil
layer (without `:SoilZone PHYSICAL`) and a surface store filled above its maximum by groundwater are kept, and the
unsaturated columns start with the contents as written (a run without columns warns and reports their water as dropped). With an age
tracer, `:StartTime` is the start of the run that wrote the file and `:AgeTracerDatum` (when earlier) the start of the
first run of the chain, from which the tracer's entry times count; a file without age-tracer masses (a spin-up without
the tracer) starts the ages at 0. A run without groundwater is base Raven's hotstart: its HRU and channel states are
written with 5 decimals (reservoir stages and flows with 12 digits), so it continues from rounded states. Raven's own `MB Error` of a restarted run whose reservoir spills is offset
by a constant (a known issue of Raven itself, section 9).

## 5. Outputs

| File | Content |
| --- | --- |
| `GWBudget.csv` | per step: Raven recharge, MODFLOW recharge, seepage, storage release, balance error (m3/d and % of the gross flow), returned to Raven, outer iterations and convergence, river leakage and discharge, river exchange applied to Raven, river loss carried to next step, water-table ET, wells (specified, actual), GHB, CHD, recharge-delay storage, recharge onto CHD cells, surface-store and reservoir exchange; existing models: other model packages; soil-zone columns (section 4.3c) |
| `GWHRUState.csv` | per coupled HRU: mean water-table head and depth below land surface |
| `GWSoilExchange.csv` | `:SoilZone PHYSICAL`: per soil-zone HRU and step, soil-zone base, soil water level and water table (means over all the HRU's soil-zone columns, those over specified heads included; empty for an HRU without a column; the soil water level of a column without free water is the lowest soil-zone base of its DEM points, which can lie below the mean base), saturated fraction, exchange with the aquifer both ways, rejected recharge, overflow, soil water and capacity; with specified heads also the exchange with them both ways. Summed over the HRUs, the exchange columns equal those of `GWBudget.csv`. Two model-wide values of the step, `interface updates` and `interface change [m]`, are repeated on every row |
| `GWHeads.csv` | head at each observation well, starting at t = 0 (a monitoring well whose screened cell is dry reports the missing value -1.2345) |
| `GWConnectivity.csv` | saturated fraction of the top layer per profile; number of connected saturated areas |
| `GWHeads.nc` | head(time, layer, y, x) with latitude/longitude (optional, :WriteNetCDFHeads) |
| `GWModelSummary.txt` | MODFLOW library and version, grid, active cells, profiles, river/well/boundary cells, HRU-to-grid linkage per HRU; run totals at the end (unconverged steps, discharge withheld on unconverged steps, soil-zone counts, river loss still carried, lagged-exchange debt open, hotstart columns and debt not used) |
| `mf6/` | the generated MODFLOW 6 model, list file (`mfsim.lst`) and head file (`gwf.hds`); with `:WriteGWBudgetFile` also `gwf.cbc` and `gwf.porosity` |
| `prt/` | written by `tools/make_prt.py OUTPUT [--backward] [--points file] [--run libmf6]`: a MODFLOW 6 PRT simulation on the run's flows (release points around the `:Wells`, or from a file), and after `--run` its tracks (`prt.trk.csv`) and `endpoints.csv` (release time, end point and travel time of each particle; one release per point, forward at the start of Raven's run, backward at its end, a steady-state initialization period left out of the window). PRT needs DIS or DISV grids (REGULAR, QUADTREE); PRT needs the flows of every step (`:HeadSaveFrequency 1`); the script stops with a message when steps are missing |

All rows are stamped with the date at the end of the step (with the time of day, e.g. `1985-10-01 12:00`, for sub-daily time steps). Groundwater discharge returned to Raven is
counted as input to Raven's water balance (`WatershedStorage.csv`), recharge as output (when the next step empties
`GROUNDWATER`; until then it is storage).

## 6. Calibration with Ostrich

Aquifer class and profile parameters live in the `.rvp` file, so Ostrich templates work as for any Raven
parameter. Example template lines (`Liard.rvp.tpl`):

```
  GRAVEL,      par_K_gravel, 5.0, 1.0E-5, par_Sy_gravel, 0.30
  UPLAND_TILL, par_K_till,   0.02, 1.0E-4, 0.08,          0.30
```

Head observations are scored like hydrographs (`GW_HEAD` rows in `Diagnostics.csv`), so they can enter
an Ostrich objective alongside streamflow. An example `ostIn.txt` is provided with the calibration test.
Calibrate hydraulic conductivity in log space.

## 7. Ensembles

Raven's Monte Carlo, DDS and EnKF modes re-initialize the model for every member; the groundwater model is
rebuilt and MODFLOW 6 restarted each time, with its files in each member's output folder. Every member starts from the
first run's routing memory (also the local outflow, irrigation and diversion memory), so member 1's hydrographs, flows,
groundwater books and Raven's balance error equal the single run's. The rivulet storage that `WatershedStorage.csv` and
`solution.rvc` report is base Raven's: Raven adds it again at every initialization of a member, so members report more
rivulet storage than the single run (a constant offset, also without groundwater and in base Raven; the balance error
is not affected; see the known issues in section 9).
An EnKF member's `:ExtraRVTFilename` is read before its groundwater model is built, so `:BoundaryHead` series given there
place and switch that member's boundaries. EnKF's `solution_EnKF.rvc` (spin-up and closed loop) holds each member's
groundwater blocks as its `solution.rvc` has them at the end of the member's run, and every state with 17 significant
digits, so closed-loop and forecast members continue the aquifer from there.

## 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| "cannot load MODFLOW 6 library" | run `python tools/get_mf6.py` in RavenHydroFramework-extra, or set `:MF6Library` or `RAVEN_MF6_LIB` to the full path of libmf6; the message lists the places searched |
| "MODFLOW 6 stopped the run during ..." | MODFLOW found an input error inside its library; the message quotes the error report of `<output>/mf6/mfsim.lst` |
| "HRU ... has an AQUIFER_PROFILE but no polygon" | HRU IDs in the GeoJSON do not match the `.rvh`; check the ID field name |
| "does not overlap any active groundwater cell" | reduce `:GridCellSize` or `:MinCellCoverage`, or check bedrock depth |
| Warnings "polygon area ... differs from .rvh AREA" | informational; fluxes are mapped mass-conservatively regardless |
| "MODFLOW 6 did not converge" | start from `:GWInitialization STEADY_STATE` or realistic `:InitialGWHeads`; raise `:SolverMaxOuterIterations`; increase `SEEPAGE_SMOOTHING_DEPTH`. Raven continues with MODFLOW's flows; on such a step only MODFLOW's negative residual is withheld from the discharge to Raven ("... m3 of discharge to Raven withheld for MODFLOW's negative residual", first ten per run; run total "discharge withheld" in `GWModelSummary.txt`) |
| ":WellFlowRate id / :BoundaryHead name in the .rvt file names no well / boundary" | the ID or name does not match `:Wells` or a boundary of the `.rvg` (the message lists those there are) |
| ":MF6Model ... apply only to an existing model" | `:MF6Model`, `:MF6StartDate`, `:KeepPackages`, `:SeepageToRaven` are for `:MF6Simulation` only; remove them |
| "EXTINCTION_DEPTH > 0 ... the model keeps its EVT ... package" | water-table ET from Raven and the model's own ET would both act: list the model's EVT/UZF package in `:RavenTakesOver`, or set EXTINCTION_DEPTH 0 |
| "uses time-array series (TAS6) ... start Raven at :MF6StartDate" | a later start cannot shift TAS6 series; start at the model's time zero |
| "the time-series file ... reads its rows from another file" | a later start shifts the times of TS6 files; list the rows of the TIMESERIES block in the file itself (no OPEN/CLOSE or INTERNAL), or start at the model's time zero |
| ":SoilZone PHYSICAL needs an existing model that uses the Newton-Raphson formulation" | add `NEWTON` to the model's name file OPTIONS (and `LINEAR_ACCELERATION BICGSTAB` to its IMS file) |
| "process ... sends water to GROUNDWATER in HRU ... which has no AQUIFER_PROFILE" | that water leaves the model; restrict the process with :-->Conditional |
| well rate is zero ("has no :WellFlowRate time series") | the `:WellFlowRate` block is missing or its well ID does not match an ID in `:Wells` |
| "running more time steps than the MODFLOW 6 simulation holds" | `:Duration` or `:TimeStep` changed after the model files were built; rerun |
| "soil class ... of SOIL[M-1] ... needs HYDRAUL_COND" | `:SoilZone PHYSICAL`: give `HYDRAUL_COND` for the class of the bottom soil-zone layer |
| "soil-zone interface did not converge" | rare; raise `:SoilZoneIteration` or `:SolverMaxOuterIterations` (keep it at 20 or more), increase `SEEPAGE_SMOOTHING_DEPTH`, or shorten the time step |
| warning "m3 that MODFLOW took from the soil zone was not in it" | `:SoilZone PHYSICAL` on steps whose interface did not converge (mostly at a low `:SolverMaxOuterIterations`): raise it (default 500; keep it at 20 or more) |
| warning "... ignored" for a `:SoilZone*` command | the command has no effect here (without `:SoilZone PHYSICAL`; depth classes or initial flux with `:SoilZoneVadose NONE`; `:SoilZoneAquiferClass` on a model Raven builds) |
| "RECHARGE_DELAY ... cannot be used with :SoilZone PHYSICAL" | set `RECHARGE_DELAY` to 0 in the profiles of HRUs with a soil zone; for a delay through a deep unsaturated zone use `:SoilZoneVadose LAG` |
| "GeoJSON file ... is in EPSG:n" / "... outside the longitude/latitude range" / "well ... is given by X and Y" | a projected input file: give `:InputCRS` with its projection (all input files in that projection; a projection that is not built in by its TMERC, ALBERS or LCC parameters) |
| "... looks like longitude/latitude" | with `:InputCRS` a GeoJSON file or raster is still in lon/lat: reproject it (or remove `:InputCRS` if every input is lon/lat) |
| "raster ... is in EPSG:n (a projection, in its GeoTIFF keys)" / "... is in longitude/latitude (EPSG:n in its GeoTIFF keys), but :InputCRS is ..." | give `:InputCRS` with the raster's projection (`EPSG:n` when the message offers it; a code that is not built in by its TMERC, ALBERS or LCC parameters), or every raster in the projection of `:InputCRS` |
| "GeoTIFF file ...: compression ... is not supported" / "... samples (bands) per pixel" / "samples of ... bits" / "not north-up" / "rotates or shears" | save one north-up band, uncompressed or LZW/DEFLATE/PackBits: `gdal_translate -b 1 -co COMPRESS=DEFLATE` (`gdalwarp` for rotated rasters) |
| "GeoTIFF file ...: ... (truncated or corrupt file)" / "decompression error" / "the chain of image directories is corrupt" | export the file again |
| "GeoTIFF file ...: FillOrder 2 ..." | re-save the file with `gdal_translate` |
| "GeoTIFF file ...: the linear units of its projection ... are foot" / "its angular units ..." / "its elevations are in ..." (also a vertical system such as EPSG:6360) | Raven reads metres and degrees: reproject (`gdalwarp -t_srs`) or convert the elevations to metres |
| "... is in EPSG:n, whose longitudes count from the prime meridian of ..." / "whose angles are in ..." / "its prime meridian ... is not Greenwich" | reproject the GeoTIFF or GeoJSON file to EPSG:4326 |
| "GeoTIFF file ...: its n tiles of ... pixels cover more than 200 million pixels" | export the file again |
| "GeoTIFF file ...: its prime meridian lies at longitude ... from Greenwich" / "its geodetic datum EPSG:n ... counts longitudes from the prime meridian of ..." | reproject the raster to EPSG:4326 |
| "... is in EPSG:n, a projection whose coordinates are in ..." | reproject the GeoTIFF or GeoJSON file to a projection in metres |
| "GeoTIFF file ...: its elevations are in ... (the band unit, UNITTYPE in GDAL_METADATA)" / "its band SCALE ... is 0" / warning "... has the band unit '...', which Raven does not know" | convert the values to metres and set the unit (`gdal_edit.py -units m`); save unscaled elevations (`gdal_translate -unscale`) |
| "raster ...: unknown header key" / "... is not a number" / "has ... values, fewer than ncols*nrows" / "has more values than ncols*nrows" (ESRI ASCII) | correct the grid's header or values |
| warning "raster ... has a vertical coordinate system (...) whose unit Raven does not know" | check that the elevations are in metres |
| warning "raster ...: its chain of image directories is damaged after the raster ..." | the raster is read without its internal mask; export the file again if it has one |
| "GeoTIFF file ...: the file has an internal mask ... that Raven cannot read" | save it with a no-data value: `gdalwarp -dstnodata -9999 in.tif out.tif` |
| "GeoTIFF file ...: strip/tile n is empty and the file has no NODATA value" | give it a no-data value (`gdal_translate -a_nodata`) or write it without SPARSE_OK |
| "GeoTIFF file ...: its GDAL_NODATA tag (...) is not a number" | set a numeric no-data value: `gdal_translate -a_nodata -9999` |
| "GeoTIFF file ...: the first image of the file is a reduced-resolution copy or a mask" | export the full-resolution raster again |
| warning "raster ... has no NODATA value (GDAL_NODATA) but holds k pixels of -9999 ..." | if they are no data, declare it: `gdal_translate -a_nodata -9999 in.tif out.tif` |
| ":LandSurface raster ... gives no value for any of the n active columns" | the raster does not cover the model (another area, wrong corner or `:InputCRS`, or NODATA only); the message gives both extents |
| warning ":LandSurface / :BedrockSurface raster ... gives no value for k of the n active columns" | extend the raster or fill its no-data cells; those columns use the HRU ELEVATION / DEFAULT_BEDROCK_DEPTH |
| "command ... '...' is not a number" / "... has the surplus value ..." / "values ... must come in keyword-value pairs" | give plain numbers in the `.rvg`, and for `:InitialGWHeads` in the `.rvc`, without units or thousands separators (a comma separates values: 2000.0, not 2,000.0; 98.5, not 98,5) |
| ":GridCellSize ... gives about ... cells per layer" / "the :GridRefinement sizes give a regular grid (or a quadtree grid) of about ..." | more than 5 million cells per layer, before the grid is built (a quadtree's size is estimated from the squares the refinement features touch, and refused before the build only beyond 1.5 times the limit; the build stops at the limit: "... of more than 5e+06 cells per layer (the build stopped there)"): give the sizes in metres as plain numbers; refine locally with QUADTREE or HRU_MESH, or limit the levels with `:QuadtreeMaxLevel` |
| "not enough memory to build the groundwater model (about ... cells per layer, from ...)" / "... to couple the existing model" | the grid is within the limit but the computer's memory is not enough for it (or for the model's files): larger `:GridCellSize` or `:GridRefinement` sizes; for an existing model, more memory |
| ":WellFlowRate ...: units ... are not supported" / ":BoundaryHead ...: units ..." | well rates in m3/d, m3/s or L/s; heads in m |
| ":AquiferClasses / :AquiferProfiles / :AquiferProfileParameters, row ...: ... '...' is not a number" | give plain numbers in the `.rvp` tables (10, not 1O; 3, not 3m) |
| ":InputCRS - TMERC parameter ...: '...' is not a number" / "TMERC takes ... and an optional ellipsoid" / "surplus value ... after EPSG:n" | give the projection's parameters as plain numbers, exactly as many as it takes |
| "the :GridRefinement sizes (smallest ... m) give an HRU mesh of about ... cells per layer (estimated) ... too slow to build" | an HRU mesh's boundaries take seeds at the smallest LINES/RIVERS size: give the sizes in metres (500, not 0.5); for very fine features use QUADTREE |
| "... a name Raven reserves for the packages it adds" | an existing model's package is named like one of Raven's (RCH_RAVEN, DRN_RAVEN, EVT_RAVEN, SWX_RAVEN, RES_RAVEN, SZ*_RAVEN): rename it, or remove the line if Raven wrote it |
| warning "layer ... starts dry" | the initial heads leave a whole layer dry (INITIAL_HEAD_DEPTH deeper than the layers above); start from `:GWInitialization STEADY_STATE`, a smaller INITIAL_HEAD_DEPTH or `:InitialGWHeads` |
| warning "soil-zone base of the HRU lies ... from the model top" | cells shared with lakes or with HRUs of a different soil-zone thickness; between the two levels soil and aquifer both store water (or neither does) |

## 9. Limitations

- Refinement of a regular grid spans whole rows and columns (use QUADTREE or HRU_MESH for local refinement); XT3D
  (optional, off by default) costs more per iteration and can slow convergence.
- Inputs are GeoJSON, ESRI ASCII grids and single-band GeoTIFF files (uncompressed, LZW, DEFLATE or PackBits; north-up),
  in lon/lat or in one projection given by `:InputCRS` (Transverse Mercator, Albers, Lambert conformal conic); imported
  grid cells are single-ring polygons. DEM, bedrock, reservoir stages, boundary
  heads and well screens must share one vertical datum (only a reservoir below its aquifer is detected).
- By default layer l connects sideways only to layer l of the neighbouring columns; `:LayerConnection ELEVATION` connects
  overlapping cells (an existing model keeps its own connections).
- River stage comes from Raven's depth at the start of the step; reservoirs exchange with a one-step lag
  (`:ReservoirExchange`); both are exactly accounted.
- A layer that starts completely dry can leave the first steps unconverged; Raven warns at start-up ("layer ... starts dry").
- MODFLOW stops the program on invalid input; Raven copies the error report of `mf6/mfsim.lst` into its message and
  `Raven_errors.txt`.
- `:SoilZone PHYSICAL`: recharge comes from SOIL[M-1] by a vertical process; RECHARGE_DELAY is refused (use
  `:SoilZoneVadose LAG`); SOIL_ZONE_DEPTH is not used; the soil zone is at most 20 m thick; between cells soil water moves
  only through the aquifer.
- Existing models (section 4.3b): no DISU, ATS6, several solutions or non-Gregorian calendars; later starts refuse
  time-array series (TAS6), TVK6/TVS6, simulations with several models and array or advanced packages with several period
  entries before the start (TS6 series are shifted; their rows must be listed in the TS6 file itself); TDIS and mover period data given as INTERNAL are refused (OPEN/CLOSE
  files are read); the stream package keeps the model's stage and has no conductance (supply) limit; undefined length or
  time units are taken as metres and days; monitoring wells and GWHeads.nc need `:MF6CRS` or `:MF6GridFile`.
  Water-table ET, `:SurfaceWaterExchange` and `:ReservoirExchange` work as with a generated model, except on cells that
  are the model's specified heads in a step (and, without NEWTON, inactive cells): they move no water there, and the
  reservoir seepage those cells cannot take is returned to the reservoir's subbasin (section 4.3b). The stream package's
  loss the channel cannot supply is carried to the next step (`river loss carried to next step`), for months in Example B.
- Not available: groundwater transport, particle tracking during the run (offline tracking: `:WriteGWBudgetFile` and
  `tools/make_prt.py`, DIS/DISV grids), demand-driven wells. Frozen ground acts on recharge only through Raven's own
  processes.
- Raven's `:Transport` (tracers, nutrients, the age tracer, temperature) is not available in a coupled run: the coupling exchanges water, not constituent mass, so a coupled run with a `:Transport` command stops with a message naming the constituent.
- Known issues in Raven itself (also without groundwater; left to the Raven developers): channel storage in
  `solution.rvc` can be negative in some subbasins; on the day after a reservoir has been drawn empty by a minimum flow its
  outflow still averages in the previous release rate (most of such a reservoir's balance error); the reservoir's stage
  iteration stops once its change falls below 0.1 mm, so on a step whose stage ends within a millimetre of the weir
  crest, where the outflow curve has its kink, the reservoir's `MB error` (`ReservoirMassBalance.csv`) and Raven's
  balance show up to about the lake area times 0.1 mm (3 to 7 m3 on a 0.04 km2 lake whose stage falls slowly through the
  crest, in base Raven without groundwater; with `:ReservoirExchange` where the aquifer holds a lake near its crest);
  valgrind reports
  uninitialised reads in `RVPParameterWarning` and `CVegetationClass::RecalculateRootParams` while the `.rvp` file is read;
  Raven's `MB Error` of the first step is not zero in some models and stays at that value (0.431 mm in the Liard example,
  0.216 mm with half-day steps, also in base Raven 4.15); without `:GroundwaterModel`, Raven empties the `GROUNDWATER`
  store every step without booking it as an output, so `MB Error` falls by the store's content each step (-7.48 mm after
  the first year of the Liard example without groundwater; the flows are not affected); in ensemble mode every member's
  `WatershedStorage.csv` and `solution.rvc` show a larger rivulet storage (and total) than a single run, by a constant,
  because Raven adds the rivulet storage again at every initialization (the flows, channel storage and balance error
  equal the single run's);
  a restart with another `:TimeStep` (as the `.rvc` of a run with a longer or shorter step): Raven's `CSubBasin::SetQinHist`
  rescales a reach's inflow history only over the length of its lateral-inflow history and, when the step grows, reads past
  the end of the inflow history in the `.rvc`, so the restarted run's `MB Error` is off by what those entries hold (up to
  2.2 mm in test WB14's runs without the river, the same with the coupling); when the lateral-inflow history is the longer
  one (a long catchment routing such as `ROUTE_TRI_CONVOLUTION` with a large `TIME_CONC`), the rescaling also writes past
  the end of the inflow history's array, which overwrites other data and can crash Raven (base Raven ends such a
  restart in a segmentation fault); in a coupled run the rescaling stays within the array and the entries past the end
  of the `.rvc` history are read as 0 (test WB15); Raven's `CSubBasin::SetQlatHist` also reads past the end of the
  `.rvc` lateral-inflow history, and coupled runs do not guard that read; and when the step grows after the inflows
  varied, Raven averages a reach's inflow history to the new step while the reach upstream books its first outflow from
  its last outflow, so the first step's `MB Error` changes by half the new step times the difference between the averaged
  and the last outflow, for every such reach (-1.42 mm in a 0.16 km2 test watershed whose inflow varied, without
  groundwater; in a coupled run river takes on an upstream reach make its outflow vary in the same way: 0.071 mm in that
  watershed restarted from 0.5 to 1 d; the take itself is restored exactly, and a restart with the same `:TimeStep` is
  exact);
  after a hotstart of a model whose reservoir spills, Raven's `MB Error` (`WatershedStorage.csv`) is offset by a
  constant, half the water that crossed the reservoir in the step before the restart (its outflow, and reservoir seepage
  returned to the subbasin or a gain MODFLOW did not supply on its way into the reservoir), because Raven's initial storage
  at a hotstart leaves that half step out (base Raven 4.15 too): +7.39 mm for a 0.16 km2 test watershed whose lake spills
  2,364 m3 in that step (without groundwater, in base Raven and with the coupling alike), +14.92 mm coupled (4,776 m3), about 50 mm for a
  lake spilling 16,100 m3/d, 0.1 to 0.6 mm for seepage in transit. The restarted run's states, flows and stages are the
  continuous run's (exactly in a coupled run); only that column, and the Raven balance `tools_audit.py` reports, is offset.
