# Audit A6, phase 16: code

Phase 16 of the round-6 audit (issue list: `spec/audit_A6/AUDIT_A6_issues_and_phases.md`; brief:
`spec/audit_A6/phase16_17_brief.md`): CB6-1, CB6-2, CB6-3, CB6-4, SV6-1, SV6-2, IB6-1, IB6-2, IB6-3, IB6-4, IB6-5.
Reference build: the release build `wt/rel14_Raven.exe`; this build: `wt/p16/Raven_p16.exe`; base Raven:
`audit/CB/Raven_base.exe`. Worktrees `wt/p16/code` and `wt/p16/extra`; nothing is committed (patches, logs and the review
brief in `wt/p16/patches/`).

Each change has a regression test that fails with the reference build (or, for the audit tool, with the release's
`tools_audit.py`) and passes with this one. IB6-5 is a correction of the manual; its new check pins the documented
behaviour and passes with both builds.

## CB6-1: an EnKF member's boundary series and the model built for it

**Before.** `CEnKFEnsemble::UpdateModel` rebuilt the groundwater model (`CalculateInitialWaterStorage`) and only then read
the member's `:ExtraRVTFilename`. `SetBoundaryHeadSeries` re-linked the head series, but the placed layers, the fixed or
switched status of the specified-head columns, `_hruRchArea` and the soil-zone entries came from the series the model was
built with: the previous member's, or the base `.rvt`'s. With a series only in the members' files (`enkfbh.py`), member 1
kept a fixed specified-head column whose cells the series released: 200 m3/d booked as recharge onto CHD cells that were
not held (800 m3 over days 3-6), lost from Raven, while every identity closed.

**Change.** `EnKF.cpp/.h`: the read is a helper, `ReadExtraRVT`. In a coupled run it is called after the member's `.rvc`
and before `CalculateInitialWaterStorage`, so `Initialize` places and links the member's own series (`_active` is false
between members, so `SetBoundaryHeadSeries` and `SetWellFlowRateSeries` only store the series). Without groundwater the
order is base Raven's (reservoir series in an extra `.rvt` keep their place relative to `CReservoir::Initialize`), so runs
without groundwater are unchanged. The comment on the series setters says so.

**Test.** `soilzone/test_inputs.py` I17b: the auditor's case, 2 members, and a single run with the series in its `.rvt`.
Reference: largest relative difference of GWBudget.csv 1.0, member 1 books 200 m3/d onto the released cells. This build:
0 difference, nothing booked.

## CB6-2: ensemble members start from the first run's local outflow

**Before.** `RestoreInitialDynamicState` called `CSubBasin::SetQlatHist`, which recomputes `_Qlocal` from the history, and
the snapshot held neither `_Qlocal`/`_QlocLast` nor the irrigation and diversion memory. ROUTE_STORAGECOEFF,
ROUTE_HYDROLOGIC and ROUTE_TVD read `_Qlocal`, so every member, member 1 included, started its routing from another state
than the single run, also without groundwater, where base Raven's member 1 is exact.

**Change.** `SubBasin.h`: `GetRoutingMemory`/`SetRoutingMemory` (`_Qlocal`, `_QlocLast`, `_Qirr`, `_QirrLast`,
`_Qdiverted`, `_QdivLast`, then each water demand's `_aQdelivered` and `_aQreturned`, into a vector). `Model.h`: `_initRouteMem`. `ModelInitialize.cpp`: the first `CalculateInitialWaterStorage`
saves them with the histories; `RestoreInitialDynamicState` sets them back after `SetQlatHist`. A member's own `.rvc` is
read afterwards and still overrides them.

**Test.** `watershed_balance.py` WB12: the losing two-subbasin reach (30 km, bed conductivity 200 m/d), ROUTE_DUMP, with
ROUTE_HYDROLOGIC, ROUTE_STORAGECOEFF and ROUTE_TVD, with and without groundwater; a 2-member Monte Carlo ensemble against
the single run (Hydrographs.csv, and GWBudget.csv with groundwater): exactly 0 required without groundwater, 1e-12 with it.
An irrigated case (0.003 m3/s, ROUTE_HYDROLOGIC, TRI_CONVOLUTION, with groundwater) also compares Demands.csv: the
reference gives 0.099 (member 1) and 1.0 (member 2: its first row showed member 1's last delivery); this build 0. (The
demand columns of the first row are the demand objects' value before the first step, written as output, and are
compared from the second row.)
Reference (largest relative difference, members 1 and 2): HYDROLOGIC and STORAGECOEFF 2.9e-4 without groundwater, 0.77
with it; TVD 1.7e-3 and 0.083. This build: 0 in all twelve comparisons. `patches/cb62_base.py` runs base Raven on WB12's
folders without groundwater: for all three methods this build's single run and member 1 are byte-identical to base
Raven's (Hydrographs.csv and WatershedStorage.csv), and base Raven's member 1 hydrographs equal the single run's
(`patches/cb62_base.log`). (Base Raven's ensemble WatershedStorage.csv differs from its single run's, as it did before.)

## CB6-3: a restart with another :TimeStep after a river take

**Before.** `:GWRiverTake` held the last takes as volumes without their step. After a restart with another step,
`BeginReachRouting` added back T/dt_new instead of T/dt_old (the routing state was off), and the first step's trapezoid
lowered the outflow by T dt_new/(2 dt_old) while the channel correction and Raven's balance took off T/2: a phantom
channel storage (47.12 m3 = T/2 in the auditor's diffusive-wave case, 30.71 m3 with ROUTE_HYDROLOGIC). For a take from
the inflow the same happened through Raven's rescaled inflow history, and showed as Raven's MB error (0.85 mm, 1.2 mm).

**Change** (`GroundwaterModel.cpp/.h`, `ParseInitialConditionFile.cpp`).
- `:GWRiverTake` carries the time step of the takes on its header line (`:GWRiverTake 0.5   # ...`, 17 digits); the
  parser reads it when present (`SetHotstartRiverTakeStep`; read as a number, not a water amount, so a step of 0 or -1
  stops with "the time step of the takes must be positive", checked in WB7) and files without it are read as the run's
  own step. `ClearHotstartData` clears it.
- `_rivTakeDt`/`_rivTakePrevDt`: the step of this step's and the last step's takes (`InitRiverTakes`: the hotstart's step).
- `BeginReachRouting` adds back T/dt_old, so the routing state is exact.
- The second half of the last takes is booked as Raven's trapezoid integrates it: `_rivTakePrevBook` = T/2 x dt_new/dt_old
  (`GetStepReturnVolume` uses it; with the same step it is exactly 0.5*_rivTakePrev, so other runs are bit-identical), and
  the channel correction in `TakeRiverLossFromOutflow` uses the same factor.
- `InitRiverTakes` carries the rest, T/2 x (1 - dt_new/dt_old) per subbasin, in `_sbLossCarry` (negative, a return, when
  the step grows), so Raven gives up exactly T in all. For a take from the inflow the trapezoid's share depends on Raven's
  rescaling of the inflow history (averages when the step grows); the same factor is exact when the step shrinks and when
  the last takes were equal, as in WB13.
- Considered and not taken: stopping a restart that changes the step after a take (Raven allows such restarts), and
  writing a rescaled delivered outflow instead of the carry (it can turn negative when the step shrinks).

**Test.** `watershed_balance.py` WB13: the WB10 reach (inflow 0.05 m3/s on days 1-5, no rain), ROUTE_HYDROLOGIC and
ROUTE_STORAGECOEFF, :TimeStep 0.5 then 1 and 1 then 0.25, restarted after day 5 (last take from the outflow) and after
day 3 (from the inflow), with the same pair without the river: over both parts the outflow is lower by the leakage MODFLOW
received (less any loss carried at the end; 0.5 m3 + 1e-5, the file's digits), the channel storage ends the same (1e-5 of
the leakage) and |MB error| <= 1e-6 mm in all four runs. Reference, ROUTE_HYDROLOGIC: channel +110 m3 and outflow lower by
2998.56 against 2890.06 m3 (0.5 then 1, day 6); channel -910 m3, 2277.60 against 3186.03 m3 (1 then 0.25); MB error 0.85 and
1.2 mm for the inflow takes. This build: channel within 1e-11 m3, outflow against leakage within 0.2 m3, MB error at most
1.7e-13 mm. The auditor's `tsrst.py` (diffusive wave, 0.5 then 1 and 0.25): channel-book difference 6e-14 m3 (reference
47.12). Diffusive wave is not in WB13: base Raven's own restart of that method with another step is not conservative (the
run without the river shows an MB error of 3.4 mm), so the outflow comparison does not apply.

## CB6-4: round-off takes in the run totals

**Before.** The run total "river take in transit" was printed for any take > 0, e.g. 4.76e-44 m3 from the tail of a reach
that had stopped flowing.

**Change.** `AppendRunTotals` prints it only when half the last takes exceeds 1e-6 m3 (the threshold of the carry warning).
`solution.rvc` still holds such takes: they are state, and dropping them would make the restart differ from the
continuous run in its first step.

**Test.** WB10 now also checks the run total: given (equal to half of `:GWRiverTake`) when above 1e-6 m3, absent
otherwise; WB7's check requires a take above the threshold. Reference: STORAGECOEFF and ROUTE_HYDROLOGIC print 4.76e-44
and 4.17e-44 m3 (4 failures). This build: not given there; Muskingum's 0.00126 m3 still given.

## SV6-1: a restart before a boundary series holds a cell again

**Before.** `VZInit` built no column on a generated model's link whose cell was held at the start, before looking up the
link's hotstart lines. A restart from the `solution.rvc` written on the day before an off-to-held switch dropped those
columns' water as "unused" (2.6 m3 and 44.6 m3 in the auditor's runs), with a warning that named the wrong cause, while the
continuous run ended them in that step and sent their water to the specified head.

**Change.** `GWVadoseModel.cpp`: the hotstart lines are looked up first; a held cell gets no column only when the file has
no line for its link. Columns with lines are built from them as before; columns of a held cell without a usable line stay
inactive. `VZStep`'s specified-head branch ends them in step 1, as in the continuous run. Lines on a held link that no
column uses (another method, node count or top) are counted as lines written for other columns, not as lines on cells
that are no longer exchange links.

**Test.** `soilzone/test_vz_initial.py` VI13: the auditor's `offheld.py` set-up (column case with CHD, SWX, ET; EDGE series
below the aquifer on days 1-3, near the ground from day 4; initial flux 30 mm/d), LAG K = 1 and KINEMATIC K = 3 LAGGED;
GWBudget.csv from day 4 of the continuous run against the restart from day 3, and no unused lines. Reference: day 4's
recharge onto CHD cells 49.92 against 51.79 m3/d (LAG; 2 lines, 1.87 m3 dropped) and 49.72 against 94.32 m3/d (KINEMATIC;
4 lines, 44.61 m3 dropped). This build: deviation 0, no unused lines. VI11 (cold start, no columns on held cells) still
passes.

## SV6-2: tools_audit on a run without aquifer flow

**Change.** `examples/Liard_groundwater/tools_audit.py`: MODFLOW's cumulative residual is divided by
`max(gross, 1)` (m3/d summed over the steps), as the tool's other ratios are.

**Test.** `tools_check.py` TC8: TC1's two-step output with every flow 0 except a storage term of 3.07e-9 and 3.29e-9 m3/d.
Release tool: 1.0 (`patches/scripts/tc8_ref.py`). This tool: 6.4e-9 (below 1e-8).

## IB6-1: conic projections without a cone

**Change.** `GWGeometry.cpp`, `CGWCRS::Parse`: ALBERS and LCC with standard parallels symmetric about the equator
(|lat1 + lat2| < 1e-10, so also 0 0) and LCC with a parallel at a pole are refused with a message naming the parallels;
then any non-finite cone constant (`_nc`, `_rho0`, `_C`, `_F`) is refused too. The message reaches `:InputCRS` and `:MF6CRS`.

**Test.** `geomtest_check.py`: `ALBERS 30 -30 ...`, `ALBERS 0 0 ...`, `LCC 30 -30 ...`, `LCC 0 0 ...`, `LCC 90 90 ...`.
Reference sources: all five accepted (5 failures). This build: refused with the message.

## IB6-2: two specified-head boundaries on one cell

**Change.** `GroundwaterModel.cpp`, `BuildStresses`: a CHD cell already held by an earlier `:SpecifiedHeadBoundary` stops
the run, naming both boundaries, the layer, the grid column and the cell centre's longitude and latitude (the grid file is
not written yet at that point). General-head boundaries may share cells, as MODFLOW allows. The manual's "Where
boundaries go" states the rule.

**Test.** `soilzone/test_inputs.py` I23 (`dupchd.py`'s case, and the same pair as GHB boundaries). Reference: "MODFLOW 6
stopped the run during prepare_time_step: 1. Cell is already a constant head ((1,2,4))...". This build: "CGroundwaterModel:
:SpecifiedHeadBoundary EDGE2 and :SpecifiedHeadBoundary EDGE both select the cell in layer 1 of grid column 9 (centre at
longitude ..., latitude ...)"; the GHB pair runs.

## IB6-3: the regular-grid refinement count

**Before.** The estimate counted ceil(cs/target) columns and rows per base cell, without the 2:1 smoothing that
`RefineAxis` adds; the built grid was up to 1.4-1.8 times larger, and the post-build stop advised a larger `:GridCellSize`.

**Change.** `GWGrid.cpp/.h`: `CGWGrid::RegularAxisCounts` runs `RefineAxis` on both axes (the build's own function).
`BuildGeometry` keeps the cheap count first; when that is within the limit (the smoothing only adds cells) it takes the
exact count from `RegularAxisCounts`, so the stop before the build is exact and the `bad_alloc` message reports the real
size. The post-build stop names `:GridRefinement` (larger sizes, QUADTREE or HRU_MESH) when refinement set the size, and
gives the count. The cost is that of the build's own axis step.

**Test.** `input_checks.py` N24: 400 x 300 km, `:GridCellSize 2000`, 60 short lines refined to 100 m, under the 3 GB limit.
Reference: the estimate (4.76e6) passes, the build runs out of memory: "not enough memory ... (about 4.76e+06 cells per
layer ...)" (without the limit it builds 6.3 million cells and stops with "increase :GridCellSize"). This build: stops
before the build, "about 6.31e+06 cells per layer (2918 columns by 2161 rows) ... QUADTREE or HRU_MESH". The manual's
"exact" is now true and says what is counted.

## IB6-4: band units matched as words

**Change.** `GWGeoTIFF.cpp`: the UNITTYPE text is split into words (letters only, lower case). It is metres when empty,
when its first word is m/metre(s)/meter(s), or when a metre word appears and no other length unit does; another unit
(ft, foot, feet, cm, mm, dm, km, inch(es), yard(s), yd(s), mile(s), centimet*/millimet*/decimet*/kilomet*, or "in" as the
first word when no metre word follows, so "in metres" is metres) stops; anything else is the warning of an unknown unit, as before.

**Test.** `geotiff/geotiff_check.py --nolib`: `unit_height_meta.tif` with its GDAL_METADATA text rewritten (the tag moved to
the end of the file): "m (Admiralty datum)", "metres above Hydrographic Datum", "elevation in metres", "in metres", "in m", "in meters above sea level" read as metres;
"hydraulic head" read with the warning; "feet above sea level", "US survey foot", "kilometres", "in" stop. Reference
sources: 4 failures (the first two and "hydraulic head" stop; "elevation in metres" warns).

## IB6-5: the no-data margin of a raster

**Change.** `building.tex`: "more than half a raster cell beyond the map's edge (one cell beyond the outermost cell
centres)", as `GWGeometry.cpp` samples. **Check.** `geomtest`: a point 0.4 cell beyond the edge has a value, 0.6 cell
beyond has none (passes with both builds; it pins the documented behaviour).

## Documents

Manual: accounting.tex (ensembles, the restart with another step), exchanges.tex (run total threshold, columns of held
cells on a restart, two CHD boundaries), building.tex (exact regular count, cone check, band-unit words, raster margin),
existing_model.tex (`:MF6CRS` cone check), appendix.tex (`:GWRiverTake` header), verification.tex (WB12, WB13, N24),
verification_soilzone.tex (VI13, I17b, I23), developers.tex (the changed base files `EnKF.cpp/.h`, `SubBasin.h`,
`ModelInitialize.cpp`). The user guide (hotstart and ensembles) and tests/README.md. The tutorials are not touched; their
numbers are regenerated in phase 17.

## Byte identity

`patches/byteid.py` (`byteid.log`): runs without groundwater against base Raven, and coupled runs without rivers against
the reference build, see the log. Coupled runs with rivers differ only by the `:GWRiverTake` header (the step) and, where
a take is below 1e-6 m3, the run total.
