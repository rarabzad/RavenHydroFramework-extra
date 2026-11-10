# Audit A4, phase 12a: tests, inputs and tools

Phase 12 of the round-4 audit (issue list: `spec/audit_A4/AUDIT_A4_issues_and_phases.md`), the part that is not the
raster reader (IB4-2 and IB4-4 are phase 12g): CB4-3 = MT4-1, MT4-2, MT4-7, IB4-3, IB4-5, VZ4-4, SZ4-4, the MT4-10 checks,
MT4-3, and the three findings of the phase 11 review (R11-1, R11-2, R11-3). Reference build: phase 11
(`wt/p11/Raven_p11.exe`); this build: `wt/p12a/Raven_p12a.exe`. Every behaviour change has a test that fails with the
reference build (or, for a test tool, with the reference tool) and passes with this one; the numbers are below each item.

## CB4-3 = MT4-1: the option-combination matrix moves the water it claims

**Cause.** `tests/combinations.py` placed the lake, the specified head, the general-head boundary and the well with
`land(x)` at x measured from the strip's edge instead of the world x the function expects: the lake lay 4 m under its
HRU's ground and only gained, the boundaries were 4 m too low. Water-table ET was 0 in every ET-alone run (the soil met
the 5 mm/d PET), the reservoir exchanged nothing in the dry-cell cases, and the feet/seconds twin did not run for every
case. Phase 11 added a moving-water group with requirements (`need`) for its new keys only.

**Change.**
- Every height is taken at the feature's world x (`land(XS + ...)`): the lake on HRU 1 has its crest 0.5 m and its stage
  0.3 m above its ground (it loses water: the phase 11 `resg` is now `res`); with a specified head (and no dry top cells)
  the lake is a pit lake on the outlet HRU, half over the specified-head cells, its stage 0.5 m below the specified head
  (it gains water). The specified head is 2 m below the outlet's ground, the GHB 2.5 m below the upslope ground.
- `et`: PET 30 mm/d (more than the soil's evaporation meets) and EXTINCTION_DEPTH 6 m (the water table of every case,
  dry top cells included, lies within it); the phase 11 `etw` is folded into `et`. The rising-water-table column cases do
  not name `et` (their soil stays wet: no PET is left). `neg`: GR4J_X2 40 mm/d, so the negative recharge appears in every
  `neg` case, with ET too (20 and 30 mm/d left it out where ET dried the soil).
- Every case runs every model: generated, existing with NEWTON, without it (CONCEPTUAL) and in feet and seconds. The
  existing twin keeps the generated model's river and well as the model's own packages with real values (a stage 0.5 m
  above the river bed and 50 m2/d; the well pumping 150 m3/d: the generated files hold placeholders Raven overwrites each
  step), and `mf6_to_feet.py` converts the RIV, WEL and GHB lists as well as CHD, so the feet/seconds twin keeps them.
- `needs(case, model)` lists what each run must move, `check_run` measures it and lists the volumes on the run's line:
  et (water-table ET), riv, swx, wel, ghb, chd (generated: Raven's columns; existing: the package's volume in MODFLOW's
  list-file budget, `package_volumes`), res (losing lake: sent and delivered, or returned; gaining lake: sent and taken
  from the aquifer), dry (water table below the top layer at the start), neg (a negative recharge), rise (the columns
  vanish), columns (an unsaturated inflow), bhs and bho (cells switched off; bho: no CHD flow and nothing booked onto CHD
  cells on the off days), reschd (as phase 11). In an existing model without NEWTON with dry top cells MODFLOW takes those
  cells out of its solve: there the stores, the lake and the river must move nothing (`*_none`).
- A boundary group: `bhs` (phase 11), `bho` (every cell of the specified head switched off on days 4-6: the R11-1 path,
  CONCEPTUAL with a lake over the switched column, PHYSICAL NONE and LAG), and `reschd`.

**Rejected.** Keeping the old matrix and adding moving-water rows (phase 11's approach): the bulk of the matrix would still
claim exchanges that move nothing. Requiring both a gain and a loss in every lake case: the direction is set by the
lake's placement, so each case requires the direction it is built for and the matrix holds both.

**Results.** Quick mode 311 runs (99 cases), full mode 393 runs (124 cases); every run of every case passes and moves its
water. Lake losses in 40 runs and gains in 29, returned seepage in 5 (the existing model's own specified heads under the
lake), water-table ET in 138 runs (at least 8,890 m3 in 8 days; the reference matrix: 0 in all 18 ET-alone runs). With the
reference build the new matrix fails in the PHYSICAL `bho` cases (R11-1: soil-zone water booked onto specified heads
while none is held); in the CONCEPTUAL one the outlet HRU's recharge goes to its other column on those days, which the
books cannot tell apart (test_inputs.py I21d, with an HRU wholly on the column, does).

## MT4-2: the known reservoir exception is bounded

**Cause.** A result was relabelled KNOWN whenever Raven's balance error equalled the lake's routing balance error, of any
size; an injected 5,000 m3 passed.

**Change.** `lake_error_known`: besides the equality (1e-4 mm), every step's routing error must be at most
`KNOWN_RES_TOL` = 2.5e-4 m times the lake's area (10 m3 for the test lake; Raven's reservoir routine stops its stage
iteration at 0.1 mm, with relaxation), and every step with an error must have its stage within `KNOWN_RES_CREST` = 5 mm of
the weir crest; otherwise the failure is reported with the reason. A self-test runs before the matrix (and alone with
`--selftest`): on a real run's outputs an unbooked 5,000 m3 (added to the lake's routing error and to Raven's balance
error, so the two still agree) fails, 2 m3 on a step 0.3 m below the crest fails, 2 m3 at the crest is KNOWN.

**Test.** The injected 5,000 m3: reference rule KNOWN ("the reservoir routing balance error, -5e+03 m3"), new rule FAIL
("the lake's routing error reaches 5e+03 m3 on one step, more than 10 m3"). The new matrix has no KNOWN run in quick mode.

## MT4-7: test C1 fails on any difference

The hummocky RICHARDS case of `test_vz_classes.py` C1 printed a difference from `RAVEN_EXE_REF` as informational (an
exception made for a reference build without rule (i)). C1 now fails on any difference, the docstring and the manual say
"K = 1 equals the reference build". Against the reference build: identical, pass. Against a "reference" that differs
from this build only in the hummocky RICHARDS case (`scratch/scripts/ref_mutant.sh`: 1 m3 more rejected recharge on one
step): C1 fails; the reference test printed "informational: rule (i) hand-back; rejected recharge differs by up to 1.0
m3" and passed.

## IB4-3: one grid-size limit, the quadtree estimated, no crash

**Cause.** The check before building allowed 1e7 cells per layer, the one after it 5e6, so a size between the two built
the whole grid (`:GridCellSize 50` on Liard, 7.3e6: `std::bad_alloc`); the quadtree had no estimate (`:GridRefinement
RIVERS 0.5`, 0.1: `std::bad_alloc`).

**Change.**
- One limit, `GW_MAX_CELLS_PER_LAYER` = 5e6, before (regular count, refined regular count, quadtree estimate) and after
  the build (all grid types).
- `CGWGrid::EstimateQuadtreeCells` (as revised after the review, F2 below): at each level the squares that split are
  counted as a set, each once however many features touch it: lines in pieces of a quarter square (each piece's padded
  box), polygons by their outline and their inside (row by row), points by their padded box; 3 leaves per split and the
  2:1 balance as a factor 1.2. (The first version summed per feature, from the length of its lines and the area of its
  polygons, and was 18 times too large on Liard before it was clipped to the extent; the review found it far too large
  for overlapping or adjacent features.)
- `MakeQuadtree` also stops refining beyond the limit (it counts its leaves) and returns false, so no estimate error can
  exhaust the memory through the quadtree itself.
- A grid within the limit can still need more memory than the computer has (Liard RIVERS 0.5: about 4.6e6 cells per
  layer by the estimate; the quadtree needs about 700 bytes per cell to build, more than 3 GB): the build (geometry,
  layers, links, rivers, stresses, and since the review the soil-zone entries, the MODFLOW files and the grid file, F3)
  catches `std::bad_alloc` and stops with "not enough memory to build the groundwater model (about N cells per layer, from
  :GridRefinement)".

**Rejected.** A lower limit (for example 4e6): a property of the computer, not of the model; MODFLOW itself reports its own
allocation failures. Capping the automatic quadtree level at 12: changes valid grids and still crashes at 12 levels.

**Test (`input_checks.py` N11-N14, 3 GB address space).**

| Input (Liard) | Reference build | This build |
|---|---|---|
| `:GridCellSize 60` (5.08e6) | grid built, then "grid exceeds 5 million cells per layer" | stops before the build ("about 5.08e+06 cells per layer ... more than 5e+06") |
| `:GridCellSize 50` (7.32e6) | `std::bad_alloc` | stops before the build |
| QUADTREE, `RIVERS 0.1` (15 levels) | `std::bad_alloc` | stops before the build ("quadtree grid of more than 1e+07 cells per layer (estimated)"; before the review "about 4.65e+07") |
| QUADTREE, `RIVERS 0.5` (12 levels) | `std::bad_alloc` after 41 s | stops after about 44 s: "not enough memory to build the groundwater model (about 4.59e+06 cells per layer, from :GridRefinement)" |

## IB4-5: strict numbers in the .rvc

`:InitialGWHeads` reads its value with the `.rvg`'s rule (`gwutil::StrictNumber`, now shared by `GWNumber` of
ParseGWFile.cpp) and stops on a surplus token; the values of every groundwater hotstart block (`GWHotValue`) are read by
the same rule (a value "98.5x" stopped nothing before). **Test (`test_inputs.py` I22):** `98,5` (reference: starts at
98 m) and `H98.5` (reference: 0 m) stop naming the command and the token; `98.5` starts at 98.5 m; a `:GWHeads` value
`98.099...x` stops naming the block (reference: runs).

## VZ4-4, SZ4-4: the tools

- `tools_audit.py` took the median step from `sorted(d)[len(tt)//2]`, one past the end for two rows (IndexError on every
  two-step run): now the median of the differences, and for a one-step run the first row's time.
- `mf6_to_feet.py` multiplied an integer field in place (`_UFuncOutputCastingError` when every CHD head is a whole
  number): each converted field is cast to float first; GHB, RIV and WEL are converted too.

**Test (`tests/tools_check.py`, new run_all step `tools_check`):** T1 tools_audit on runs of 1, 2 and 3 steps (reference
tool: IndexError on the two-step run); T2 mf6_to_feet on a model whose CHD heads are "94", with GHB, RIV and WEL lists
(reference tool: crashes); values within 1e-8 of the converted ones.

## MT4-10: NaN and the continuous run

- `testconfig.max_diff(a, b, scale)`: a value NaN or infinite in one run and not the other is an infinite difference
  (NaN in both, an empty observation column, is none). Used by every ensemble and restart comparison:
  `behaviour_check.py` (ensemble), `restart_test.py`, `existing/restart_ext.py`, `existing/fuzz_ext.py`, `fuzz_grids.py`,
  `reservoir_checks.py`, `test_inputs.py` I21, `test_surface_stores.py` SW4. Where `.max()` skipped NaN, a member whose
  rows were NaN compared as identical.
- `testconfig.restart_verdict`: a restart comparison also needs the continuous run without unconverged steps and with
  exact accounts; `restart_ext.py` uses it (it judged only the restarted run) and prints the continuous run's count.
- **Test (`tools_check.py` T3, T4):** NaN in one run gives inf (fails a comparison), in both 0; a continuous run with
  unconverged steps fails the verdict.

## MT4-3: a coupled restart continues exactly

**Cause.** Base Raven writes the HRU states with 5 decimals; the auditor's case (RICHARDS columns, a reservoir, a specified
head, negative recharge, a rising water table) switches its soil-zone redistribution on a change of 1e-5 mm, so the
restart drifted by up to 1.4 mm. With full-precision HRU states alone the restart was still not exact: three more things
were not restored as they were.

**Change (only with a groundwater model; a run without one writes what the reference build writes: base Raven's output,
apart from the corrections to Raven's reservoirs, Table "Where a model without groundwater differs from Raven 4.15" of the
manual: an absolute-stage reservoir without an initial stage starts at its crest, a drying reservoir books only the water
it has, and `solution.rvc` holds reservoir stages and flows with 12 digits).**
1. `StandardOutput.cpp`: in a coupled run the `:HRUStateVariableTable` rows and the `:BasinStateVariables` (channel
   storage, flows, reservoir) are written with 17 significant digits; the stream is set back to Raven's fixed 5 decimals
   afterwards, so everything after them is written as before. `CReservoir::WriteToSolutionFile` keeps its 12 decimals on
   a fixed stream and otherwise the stream's 17 digits.
2. `WriteHotstart`: every groundwater block with 17 significant digits. On Raven's fixed stream the heads had 12
   decimals without PHYSICAL, and the blocks written with `setprecision(15)` had 15 decimals, so small values (column
   contents, lagged exchanges) lost digits.
3. The starting heads MODFLOW reads from a hotstart (`gwf.ic` of a generated model, `raven.ic` of an existing one) with 17
   digits (they had 10 without PHYSICAL): the CONCEPTUAL case's heads were 1e-9 off after the restart.
4. `SZInitColumns`: when the `.rvc` soil water equals the mean of its `:GWSoilZoneColumns` (1e-9 mm), the columns start as
   written. The redistribution of an HRU's soil water among its columns (`gwsz::Distribute`) is not additive: sharing a
   round-off difference at the start and then the step's change moved water across a full column's threshold that the
   continuous run never crossed (KINEMATIC: 953 against 1,324 m3 of redistribution in the first restarted step).

**Rejected.** Rebuilding the HRU layer states from `:GWSoilZoneColumns` on reading (the auditor's alternative): it covers
the soil zone only, not the channel, reservoir or CONCEPTUAL heads. Documenting the drift: the brief asks for exactness.

**Test (`test_restart.py` RS5, 8 days against 4 + 4, largest relative difference over every column of GWBudget.csv,
GWHRUState.csv and the stores of WatershedStorage.csv, limit 1e-9).**

| Case | Reference build | This build |
|---|---|---|
| PHYS_RICHARDS1_chd-res_neg-rise | 0.15 (soil-zone layer redistribution) | 0 |
| CONC_NONE_chd-et-ghb-res-riv-swx-wel_plain | 8.1e-10 (storage release) | 0 |

The auditor's case (the phase 11 matrix's placement) restarts with soil water identical and every GWBudget column
identical (reference: 1.42 mm of soil water with the full-precision HRU states alone, 0.25 relative in the redistribution
with the reference build). KINEMATIC and LAG versions of it: identical too.

**Byte-identity and reference comparisons.** `solution.rvc` of a coupled run differs from the reference build's in its
digits only. The tests that compare outputs with `RAVEN_EXE_REF` compare it with `testconfig.rvc_same` (the same text, and
numbers that agree to the digits the less precise file holds: 127.90182 and 127.90181815439453 agree; 127.90172 does not,
nor 199.6 against 200); every other output stays byte for byte. `sz_check.rvc_text` (which only dropped the column tops)
is replaced by it. Users of the `.rvc` see more digits, nothing else.

## R11-1: a column with no specified-head cell held is an ordinary column

**Cause.** In a generated model a column whose top cell is a placed specified head stayed a specified-head column on
every step (phase 11), also when the `:BoundaryHead` series switched every one of its cells off: the HRU's recharge, soil
zone, stores and lake water there were booked as going to a specified head that did not exist (400 m3/d of recharge onto
CHD cells with a CHD flow of 0 in the review's case).

**Change.** A column whose specified-head cells all follow a series (`_colCHDSw`) is built as an ordinary column: its RCH and
DRN entries (always there), its soil-zone links (exchange links, not `szc` links), its surface-store and lake entries.
`UpdateSwitchedCHDTop` (before each step, and before the first) marks it a specified-head column (`_colCHDTop`) on the
steps one of its cells is held (the rule of `SetBoundaryArrays`, factored into `CHDEntriesOn`) and recomputes the HRUs'
recharge areas. This is the existing-model machinery for the model's own specified heads, which handles a `_colCHDTop`
that changes from step to step everywhere (recharge areas, soil-zone links over specified heads, columns ending, the lake's
usable share and its returned seepage, surface stores, whose MODFLOW entries carry nothing on held cells). So: the
seepage of a lake over such a column is returned on the step a cell is held again (booked as "reservoir seepage not
delivered by MODFLOW", whose column and run total a generated model then writes), and unsaturated columns there end when a
cell is held (run total "columns over specified heads"). Columns with a specified head that has no series, or a mix, are
unchanged; so is every model without a series-driven specified head, byte for byte.

**Rejected.** Reporting the volume booked onto unheld specified-head columns as a run total (the review's minimal
alternative): the books would close, the physics would stay wrong. Switching a column off already when its top placed
cell is off while a lower one is held: the water then still reaches a held specified head below; the brief and the
review ask for the case with no cell held.

**Test (`test_inputs.py` I21d, 8 HRUs, the last wholly on EDGE, LAYERS ALL, series 99, 99, 70, 70, 70, 70 m, rain 20 mm/d).**

| Days 3-6 | Reference build | This build |
|---|---|---|
| CONCEPTUAL: booked onto CHD cells | 400 m3/d (CHD flow 0) | 0; MODFLOW's recharge = Raven's |
| PHYSICAL: booked onto CHD cells | 1,144, 175, 0, 0 m3/d | 0; the column's soil-zone link exchanges 425 to 42 m3/d |

Every identity of `combinations.check_run` holds; the combination cases `bho` (also with a lake and with LAG columns) pass.

## R11-2: cells placed by the series

With a series, the highest and lowest heads are the series' (HEAD counts only where the series is blank), so layers only
HEAD reaches are not placed. **Test (I21e):** HEAD 90, a series of 99 m on every day, LAYERS TOP: 2 CHD cells and 2 GHB
cells (layer 1; reference 4 and 4, the layer-2 cells never used), as phase 9's placement gave (`ib_review.py nosw`:
GWBudget.csv and GWHRUState.csv identical to phase 9). The phase 11 cases (HEAD within the series' range) are unchanged.

## R11-3: the steady-state period in the cell-steps off

`RunSteadyState` adds its switched-off cells to the run total. **Test (I21f):** series 90, 99, 99, 90, 90, 99 m with a
steady-state first period: 8 cell-steps (reference 6, the same as without the steady period).

## Results

- `run_all.py --quick` with `RAVEN_EXE_REF` = the reference build: 58 steps passed, 0 failed, 2 not run (the USGS examples, not
  installed), 3 checks skipped (soilzone_confined_wet W4, W6, W11, as before); 40 minutes. The first pass failed one step,
  `test_vz_initial.py` I7: its matrix case (combinations.py's `neg` and `et` changed) now ends with 247.626 m3, and the
  test compared the run total, written with 6 significant digits, at 1e-6; the limit is 5e-6 (half the last digit) and the
  step passes (re-run with `--only`). Among the steps: `restart` gives restart deviations of 0 on every grid (the reference
  build: up to 9.9e-7), `reservoir_checks` R1c 0; every comparison with `RAVEN_EXE_REF` (C1, K8, LAG B, X8, M3, budget
  file B4, existing-model `plain`, dry start D3, crs lon/lat) passes with `solution.rvc` compared by `rvc_same`.
- `combinations.py` full mode: 393 runs, 0 failed, 0 known (296 s).
- Liard T7 (`test_liard_physical.py 365`): PASS (365 steps, 0 unconverged, 72 outer iterations at most, residual -8.3e-12, recharge identity -2.0e-12; the same numbers as the reference build).
- Byte-identity (`wt/p12a/patches/byteid.py`): no groundwater against base Raven (small model with chained hotstarts,
  Nitrate and AGE, Liard 5 years and its 1-year hotstart): identical. Liard CONCEPTUAL 180 d, the Liard existing model
  31 d, PHYSICAL + RICHARDS and CONCEPTUAL with unconverged steps against the reference build: identical, `solution.rvc`
  the same state at full precision; both mf6 folders identical.
- Against the reference build: `test_inputs.py` I21d, I21e, I21f, I22 fail; `test_restart.py` RS5 fails; `input_checks.py`
  N11-N14 fail; `tools_check.py` T1/T2 fail with the reference tools; the KNOWN self-test's 5,000 m3 is KNOWN by the
  reference rule. C1 with a reference that differs in the hummocky RICHARDS case fails
  (the reference test passes it as informational). Commands and outputs: `wt/p12a/patches/reference_runs.txt`,
  `scratch/scripts/refdemo.sh`, `mt42_old.py`, `mt43.py`.

## Files

**Code** (`wt/p12a/code`, branch rb-p12a): `src/GroundwaterModel.cpp`, `src/GroundwaterModel.h`, `src/GWGrid.cpp`,
`src/GWGrid.h`, `src/GWSoilZoneModel.cpp`, `src/GWSoilZoneStep.cpp`, `src/GWExternal.cpp`, `src/GWUtil.h`, `src/ParseGWFile.cpp`,
`src/ParseInitialConditionFile.cpp`, `src/StandardOutput.cpp`, `src/Reservoir.cpp`.

**Extra** (`wt/p12a/extra`, branch rb-p12a-tests): `tests/combinations.py`, `tests/combinations_floors.json` (new), `tests/tools_check.py` (new),
`tests/testconfig.py`, `tests/run_all.py`, `tests/input_checks.py`, `tests/reservoir_checks.py`,
`tests/behaviour_check.py`, `tests/restart_test.py`, `tests/fuzz_grids.py`, `tests/budget_file.py`, `tests/crs_inputs.py`,
`tests/dry_start.py`, `tests/existing/restart_ext.py`, `tests/existing/fuzz_ext.py`, `tests/existing/ext_exchanges.py`,
`tests/soilzone/test_inputs.py` (I21d-f, I22), `test_restart.py` (RS5), `test_vz_classes.py` (C1), `test_vz_kinematic.py`,
`test_vz_lag.py`, `test_sz_existing.py`, `test_columns_mf6.py`, `test_surface_stores.py`, `sz_check.py`,
`mf6_to_feet.py`, `tests/README.md`; `examples/Liard_groundwater/tools_audit.py`; manual chapters `accounting.tex`,
`appendix.tex`, `building.tex`, `developers.tex`, `exchanges.tex`, `sz_vadose_classes.tex`, `verification.tex`,
`verification_soilzone.tex`; `docs/Raven_MF6_Groundwater_UserGuide.md`.

## Independent review

The review (`wt/p12a/review/REVIEW.md`, scripts in `wt/p12a/review/scripts/`) found one S2, three S3 and five S4 items.
The responses follow; every change has a test that fails with the build before the review
(`scratch/Raven_p12a_prereview.exe`) and passes with this one, unless stated.

## Review responses

**F1 (S2): LAGGED restart at an off-to-held switch of a series-driven column.** As the review found: `SZLagApply` skipped
a link when its column was a specified head, and read `_colCHDTop` before the step's update in a continuous run but after
it in a restarted one (`Initialize` sets the first step's state). Change (the review's fix): at the end of each step
`_szxQprev` is set to 0 on the links whose column was a specified head in that step (`GWSoilZoneModel.cpp`, the value the
hotstart already wrote), and `SZLagApply` no longer tests `_colCHDTop` (`GWSoilZoneStep.cpp`). The lag of the next step
then depends only on the last step's state, in a continuous and a restarted run alike, for generated and existing models
(an existing model's `_colCHDTop` changes only in `Exchange`, so its lag is the same as before), for every link of the
column, and not at all under AFTER timing (`SZLagApply` runs only with LAGGED). Checks with the review's `r11.py`
(`HELD=91.9 ST=neg`, restarts at every switch): PHYS NONE (pattern 10100110 and 0011), PHYS RICHARDS, PHYS NONE with 3
classes and a river: every restart 0 (before: 0.159 and 15 at the off-to-held days); AFTER: 0. The continuous run's
GWBudget, GWHRUState, GWSoilExchange, WatershedStorage, Hydrographs and WatershedMassEnergyBalance are byte-identical to
the build before the review. **Test:** `test_restart.py` RS5 has a third case, PHYS_NONE_chd-et-swx_bho-neg with the series
held at 91.9 m (0.1 m below the outlet column's soil-zone base) or switched off in the pattern 10100110, restarted at
day 3 (off to held), 4 (held to off) and 6 (off to held): 0, 0, 0 (before the review: 0.16, 0, 15; limit 1e-9).

**F2 (S3): quadtree estimate for overlapping or adjacent features.** `EstimateQuadtreeCells` now counts, at each level,
the set of squares that split (each once however many features touch it; above). Against the cells built:

| Case | Estimate | Built | Estimate / built |
|---|---|---|---|
| Liard RIVERS 20 / 5 / 2 / 1 (2 km cells) | 156k / 612k / 1.15M / 2.30M | 163k / 644k / 1.23M / 2.45M | 0.96 / 0.95 / 0.94 / 0.94 |
| strip, 50 copies of one line, 0.5 m / 0.1 m | 7.1k / 28k | 10.3k / 41k | 0.68 / 0.68 |
| strip, 50 lines 0.5 m; 10 lines 1 m; 3 lines 0.1 m | 472k; 53k; 112k | 447k; 58k; 129k | 1.06; 0.91; 0.87 |
| strip, adjacent squares (50 of 10 m at 1 m; 20 of 30 m at 0.5 m) | 12.8k; 149k | 12.7k; 129k | 1.01; 1.16 |
| strip, separate squares (5 of 50 m at 0.5 m; 3 of 300 m at 2 m) | 106k; 118k | 90k; 98k | 1.18; 1.20 |

(the review's `qtest.py` cases; the estimate of the build before the review for 50 copies of one line at 0.1 m: 2.7e6,
66 times the 41k built). The estimate is within a third below and a fifth above, so it refuses a grid before the build
only beyond 1.5 times the limit; nearer the limit the grid is built and `MakeQuadtree`'s leaf counter stops it at the
limit ("give a quadtree grid of more than 5e+06 cells per layer (the build stopped there)"). The count stops at twice
the limit (Liard RIVERS 0.1: "more than 1e+07 cells per layer (estimated)", 7 s, 390 MB). **Test:** `input_checks.py`
N15 (200 copies of one line, LINES 0.1, on the 4-HRU strip: built, 46,852 cells per layer; before the review: refused,
"about 1.08e+07") and N16 (20 adjacent squares of 30 m, POLYGONS 0.5: built, 128,728 cells); N13 and N14 pass with the
new messages.

**F3 (S3): memory exhaustion.** The `try` now spans the whole build to the model's files (`ExtBuild` or the generated
build, `SZBuildEntries`, `WriteMF6Files`, `WriteGridCells`); the handler first frees the grid, the overlaps, the links and
the layer arrays (swapped with empty objects), then stops ("not enough memory to build the groundwater model (about N
cells per layer, from :GridCellSize)", or "... to couple the existing model"). The review's case, the 4-HRU strip with
`:GridCellSize 0.5` (640,000 cells per layer), under `ulimit -v`: 300, 350, 400 and 450 MB stop with that message (before:
`std::terminate` at 350 and 450 MB); 500 MB: Raven cannot map the MODFLOW library ("cannot load MODFLOW 6 library ...
failed to map segment"); 550 MB: MODFLOW's own allocation error, reported as MODFLOW's stop; 700 MB: SIGSEGV inside
libmf6 (MODFLOW's allocation in `sparsemodule`, not Raven's: left as the review notes); 2 GB runs (`scratch/scripts/f3.py`).
No test in the suite: the limits at which each part fails depend on the machine and the library build.

**F4 (S3): needs mechanism and flow floors.** `res_loss` now requires seepage delivered to the aquifer (more than 1 m3 on
some step; returned seepage alone no longer passes: the existing-model `*_res_reschd` twins). Every volume a run must
move (ET, stores, river, well, GHB, CHD, the model's own packages, the lake's delivered loss or gain, negative recharge,
unsaturated inflow, the rising columns' largest storage, the seepage returned under `reschd`) must be at least half
(`FLOOR`) of the volume recorded for that run in `tests/combinations_floors.json` (`--record`; quick and full sets,
recorded with this build). A mutant of this build (`scratch/srcmut`, the review's `mutant_exchanges.diff` with a scale:
`RAVEN_MUT` names the exchanges, `RAVEN_MUT_SCALE` the factor, 0 by default) on the quick matrix with
`RAVEN_MUT=evt,res,swx,riv,ghb,wel` (`scratch/scripts/mutcheck2.py`, logs `patches/mut_zero.txt`, `patches/mut_scale.txt`):

| Mutant | Runs | Missing a mutated exchange | Also another required (changed through the mutated ones: CHD in 18, negative recharge in 6) | Runs naming no mutated exchange that fail |
|---|---|---|---|---|
| zeroed | 311 | 0 | 24 | 0 of 70 |
| scaled by 0.1 | 311 | 0 | 24 | 0 of 70 |

The river of the all-exchange cases still moves 1.5 to 1.7 m3 over 8 days (its channel carries only the runoff the
depression stores leave); the floor makes a river scaled down fail all the same. An upstream inflow
(`:BasinInflowHydrograph`, 0.01 to 0.05 m3/s) made it move 43 to 270 m3, but the inflow then shows in Raven's balance
error, which `check_run` would have to book separately: not done.

**F5 (S4): no groundwater with a reservoir.** As the review found, a model without groundwater that has a reservoir differs
from base Raven by the corrections to Raven's reservoirs (made before this phase, in the reference build too): an
absolute-stage reservoir without an initial stage starts at its crest, a drying reservoir books only its water, and
`solution.rvc` holds reservoir stages and flows with 12 digits. The manual's table of these differences and its statements
were already accurate; the MT4-3 change above, the user guide's and `accounting.tex`'s "a run without groundwater writes
Raven's usual 5 decimals" now name the 12-digit reservoir values. `patches/byteid.py` has a no-groundwater model with a
reservoir (Nitrate, three chained hotstarts) compared with the reference build (must be identical) and with base Raven
(the files that differ must be among WatershedStorage.csv, solution.rvc, ReservoirMassBalance.csv and
ReservoirStages.csv).

**F6 (S4): Raven's balance error in a restarted run with returned or unsupplied seepage.** Not changed in this phase: the
restarted run's outputs equal the continuous run's, only Raven's own `MB Error` jumps on its first step (the seepage or
carry in transit is not part of Raven's initial storage at a hotstart). Phase 13 adds it to the known issue MT4-4.

**F7 (S4): comparison helpers and tools.** `rvc_same` compares `:GWVadoseColumnTops` when both files hold it (left out
only when one file lacks it). Numbers written with the same number of decimals must be equal (two 17-digit files agree
exactly); others may differ by the two roundings of one value, half a unit of the last digit of each, plus two units of
a double for reading them back (the relative term 1e-12 is gone). The first version of this rule (half a unit of the less
precise token only) failed the dry-start D3 comparison: the reference build's 481.457924970300 and this build's
481.4579249703005 are both roundings of one double, 5.1e-13 apart; the second (without the units of a double) failed LAG
B on 5.800584401338710 against 5.8005844013387104, 8.9e-16 apart once read back. `tools_check.py`'s own test value was wrong (98.0999047410 for 98.099904741067192, which rounds to ...411; the
relative term had hidden it). `mf6_to_feet.py` converts DRN lists (elevation, conductance) and
stops with a message for a DISV or DISU grid, a package whose lengths or rates it does not convert (EVT, RCH, MAW, LAK, SFR,
UZF, CSUB, HFB, MVR) and a list value given as a time-series name. **Test:** `tools_check.py` T2 (a drain; the three stops)
and T5 (two 17-digit heads 1e-13 m apart differ; 481.457924970300 and 481.4579249703005 agree; column tops compared
when both files hold them, left out when one does).

**F8 (S4): `:InitialGWHeads`.** A trailing comment is accepted (`98.5# note`, as `98.5 # note`); a hexadecimal value
(`0x62`) is not a number (`StrictNumber`, also for the `.rvg`); `FROM_PROFILE` with a value stops with "has the surplus
value '0' (FROM_PROFILE takes no value)" (the manual documents `FROM_PROFILE` without a value; the appendix and the user
guide now say so). **Test:** `test_inputs.py` I22 (`0x62` stops; `98.5# note` and `98.5 # note` start at 98.5 m;
`FROM_PROFILE 0` stops).

**F9 (S4): wording.** `accounting.tex` and `rvc_same` say "a file with fewer digits".

**After the review fixes** (this build, `wt/p12a/Raven_p12a.exe`; logs in `wt/p12a/patches/`):
- `run_all.py --quick` with `RAVEN_EXE_REF` = the reference build: 56 passed, 2 failed (dry_start D3 and LAG B, both
  `rvc_same` on two roundings of one value, see F7), 2 not run (the USGS examples); after the rule's fix the two steps and
  the other steps that compare `solution.rvc` with the reference (tools_check, vz_classes, vz_kinematic) re-run with
  `--only`: 58 passed, 0 failed, 2 not run, 3 checks skipped (soilzone_confined_wet W4, W6, W11, as before). Among them
  RS5 (5 restarts, 0), I22, N13-N16, T2 and T5, and the quick matrix with its floors (311 runs, 0 failed, 0 known).
- `combinations.py` full mode: 393 runs, 0 failed, 0 known (163 s), every run at least half its recorded volumes.
- Liard T7 (`test_liard_physical.py 365`): PASS, the same numbers as before (365 steps, 0 unconverged, 72 outer
  iterations at most, residual -8.3e-12, recharge identity -2.0e-12).
- Byte-identity (`patches/byteid.py`): every comparison as before, identical; the no-groundwater reservoir model is
  identical to the reference build in its three chained parts, and differs from base Raven only in WatershedStorage.csv,
  solution.rvc, ReservoirMassBalance.csv and ReservoirStages.csv (the reservoir corrections). 0 comparisons with
  differences.
- With the build before the review: RS5's switched case fails (0.16 and 15), I22 fails (`0x62` runs, `98.5# note` stops,
  `FROM_PROFILE 0` without the message), N15 fails (refused, "about 1.08e+07").

Files changed by the review fixes: code `src/GWSoilZoneModel.cpp`, `src/GWSoilZoneStep.cpp`, `src/GWGrid.cpp`,
`src/GWGrid.h`, `src/GroundwaterModel.cpp`, `src/GWUtil.h`, `src/ParseInitialConditionFile.cpp`; extra
`tests/combinations.py`, `tests/combinations_floors.json` (new), `tests/testconfig.py`, `tests/tools_check.py`,
`tests/input_checks.py`, `tests/README.md`, `tests/soilzone/test_restart.py`, `test_inputs.py`, `mf6_to_feet.py`,
`test_vz_classes.py`, `test_vz_kinematic.py`, `test_vz_lag.py` (comments); manual `accounting.tex`, `appendix.tex`,
`building.tex`, `exchanges.tex`, `verification.tex`, `verification_soilzone.tex`; the user guide; `patches/byteid.py`.
