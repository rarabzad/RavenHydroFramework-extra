# Audit A2, phase 4: physics, restarts and books (agent p4)

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Issue list: spec/audit_A2/AUDIT_A2_issues_and_phases.md; findings F_CB, F_VZ, F_IB, F_SZ, F_MT (repro cases reused from
audit2/{CB,VZ,IB,SZ}). Code on rb-p4 (from a2133bf), tests and documents on rb-p4-tests (from 6b886d4). Builds compared:
the current build (wt/p3/pkg/Raven_MF6_linux/bin/Raven, "before") and Raven_p4.exe ("after"), both `make -O2`, MODFLOW
6.8.1; base Raven for byte identity: audit/CB/Raven_base.exe.

Each fix has a regression test that fails with the build before and passes with this one (quick mode supported; all
the new cases take seconds).

## CB1 (S1) restart kept the seepage water above soil capacity
- Cause: without `:SoilZone PHYSICAL`, step 4 of the exchange adds seepage to its target store (`_hruReturnSV`, by
  default the lowest soil layer) with no capacity limit; the core's start-up check of the `.rvc` cut every state above
  its maximum back to the maximum (warning only, booked nowhere).
- Choice: keep the coupled model's over-capacity water on restart rather than route or book it. The continuous run
  carries that water (it is legitimate state of the coupled model, and later flows depend on it), so the only way to
  continue the run exactly is to keep it; routing the excess elsewhere would change the restarted run's flows, and
  changing the exchange itself (overflow to SURFACE_WATER) would change every CONCEPTUAL result.
- Change: `CGroundwaterModel::SeepageTargetSV(k)` gives the seepage target of HRU k from the inputs alone (same rules as
  Initialize: `:SeepageReturnTo`, default lowest soil layer, SURFACE_WATER for soil-less HRUs; DOESNT_EXIST for HRUs
  that are not coupled), usable before Initialize (the `.rvc` is read first). ParseInitialConditionsFile skips the
  capacity check for that one state variable of each coupled HRU, only when the model is coupled
  (`MODELTYPE_COUPLED` and a groundwater model). Runs without groundwater take exactly the old path.
- Test: `test_restart.py` R3 (the auditor's case: 4 HRUs, rain 30 mm/d for 5 days, water table 0.2 m deep,
  PERC_GAWSER, CONCEPTUAL; 30 days against 12 + 18).
  - Before: SOIL[1] 198.670 mm at the restart (208.105 continuous), 2 "maximum state variable" warnings, soil storage
    deviation 4.5e-2, recharge 8.6e-2, seepage 7.8e-2 -> FAIL.
  - After: 208.105 mm, no warning, soil storage identical, recharge 3.4e-9, seepage 2.7e-9 -> ok.

## VZ1 (S2) KINEMATIC restart created water
- Cause: VZInit restored each content through theta -> psi -> theta with psi clamped at -1e5 m; KINEMATIC contents can
  be below theta(-1e5 m) (reference ths - Sy, 0 for Sy = porosity).
- Change: the content is restored as written, floored only where the method needs it: air-dry theta(-1e5 m) for
  RICHARDS and LAG (their solvers floor there; LAG contents are never below it), 0 for KINEMATIC (`GetReference()==1`),
  and capped at saturation only without specific storage; psi then follows from the content. (RICHARDS restarts now
  restore the written content exactly instead of its round trip: a round-off change.)
- Test: `test_restart.py` R4 (one HRU, water table 4 m deep, SPEC_YIELD = POROSITY = 0.3; 20 days against 10 + 10;
  KINEMATIC and LAG).
  - Before: KINEMATIC first part ends with 2000.0000 m3, restart starts with 3304.1371 m3, deviation 0.59 -> FAIL
    (LAG ok).
  - After: 2000.0000 -> 2000.0000 m3, restart identical to the continuous run (KINEMATIC and LAG).

## CB2/CB3 (S2) age-tracer datum
- One change fixes both: `:StartTime` in solution.rvc is again the start of the run that wrote the file (as base
  Raven), and the datum of the age-tracer entry times has its own line, `:AgeTracerDatum date time`, written only when an
  age tracer exists and its datum is before the run's start (a restarted run). The datum is stored as a date
  (CAgeTracer::SetDatum: Julian day and year as parsed), so it is written back without any negative-offset conversion
  (JulianConvert cannot step back across 1 January: CB2's `2000-01--06`).
- Reading: the offset of the run's start comes from `:AgeTracerDatum`; without it, from `:StartTime` only when the
  file's state table has columns of an age tracer (files written by base Raven or by the previous build, whose masses
  sit on `:StartTime`); a file without age-tracer masses (a spin-up without the tracer) gives offset 0: ages start at
  0, as in base Raven (CB3).
- Byte identity: files without an age tracer are unchanged (`:StartTime` is what base Raven writes); cold-started age
  tracers too. Only age-tracer hotstarts differ from base Raven (as before this phase).
- Tests (`test_inputs.py`):
  - I14 (updated): the parts' `:StartTime` are their starts, `:AgeTracerDatum` 2000-01-01 in parts 2 and 3; ages
    within 1e-4 d. Before: fails (the old format).
  - I15: chain 1999-12-25 (7 + 7 + 6 d) and 1998-12-20 (quick 12 + 400 + 8 d; full 400 + 380 d) against one run.
    Before: part 3 stops ("Invalid date format used: 2000-01--06", "1999-01--11") -> FAIL. After: all parts run, ages
    within 1e-4 d, datum 1999-12-25 / 1998-12-20.
  - I16: spin-up 30 d without the tracer, 5 d with it. Before: ages 30 d at the start, 31 d after a day -> FAIL. After:
    0 and 1 d, no `:AgeTracerDatum`.
- Also: the stale comment of CB6 (ParseInitialConditionFile.cpp) went with the rewritten block.

## CB4 = MT-2 (S2) withheld discharge booked per step with rivers and stores
- Without `:SoilZone PHYSICAL`, on an unconverged step with a negative residual, the guard scaled seepage, subbasin
  gains and store discharge, but only "seepage to Raven" was written after scaling.
- Change: the guard also takes the withheld river and store shares out of `_Qriv_out` and `_Qswx_out`
  ((1 - f) gR and (1 - f) gS), so the GWBudget columns "aquifer discharge to rivers" and "aquifer discharge to surface
  stores" give, on such steps, the discharge handed to Raven, as "seepage to Raven" already did. The row residual
  (recharge + storage release + other inflows - discharge - MF6 balance error) is then the whole withheld volume of the
  step. Header unchanged; converged steps and runs without rivers/stores byte-identical (checked). The river identity
  (river exchange applied = net river flow + carry) now also holds on those steps.
- Alternative not taken: extra "withheld" columns for CONCEPTUAL runs (would change the header of every CONCEPTUAL
  GWBudget.csv).
- Test: `test_mf6_budget.py` B8 Liard (example, `:SolverMaxOuterIterations 2`, 10 days quick / 60 full): every row's
  residual over all columns lies in [0, max(-balance error, 0)] (equal on every row where the discharge covers it) and
  sums to the run total.
  - Before: rows 0.0 m3 against the run total 58,564.5 m3 (all of it withheld from river gains, step 3) -> FAIL.
  - After: rows 58,564.5 m3 = run total, 10 of 10 rows equal -> ok.

## IB1 (S2) EnKF member series
- The member's `:ExtraRVTFilename` is parsed after the member's groundwater model was built and linked. Rather than
  moving that parse (it also carries Raven's own series; the order is base Raven's), SetWellFlowRateSeries and
  SetBoundaryHeadSeries now (out of line) delete the series they replace and, once the model is built (`_active`),
  initialise the new series (start, duration and step stored at Initialize) and link it to its well or boundary; a
  series naming no well or boundary stops the run there (the ValidateInputs message).
- Test: `test_inputs.py` I17 (ENKF_OPEN_FORECAST, 3 members, one well, extra files -100/-200/-300 m3/d; then an extra
  file naming well 7). Before: members pumped 0, -100, -200 -> FAIL. After: -100, -200, -300; the orphan stops the run.
  (Member 1 still warns "has no :WellFlowRate" before its extra file is read, when the main .rvt has none: harmless.)

## VZ2 (S3) source-cell cap of the capillary rise from the water table
- SZCapRiseWT now subtracts `_vzUsed[e]` (uptakes of moving bottoms, passed negative recharge and the columns' bottom
  upflow, for both sources), as SZNegCaps does.
- Test: `test_vz_classes.py` C11 (RICHARDS K = 4, hummocks +-0.8 m, aquifer 0.15 m of water above the top cell's
  bottom, S_y 0.05, PET, dry soil): per step, columns' upflow + rise from the water table against
  0.5 S_y A (h - z_bot). Before: 2.0000 (step 1: 231.2 of 150.0 m3) -> FAIL. After: 1.0000 -> ok.

## SZ2 (S3) GWSoilExchange.csv
- Base, soil water level and water table: area means over all the HRU's soil-zone columns, those over specified-head
  cells included (their base SZBase, their level from their column, their water table the specified head). An HRU
  without any column writes these four fields (and the saturated fraction) empty.
- Exchange columns under GWBudget's headings: "soil zone to aquifer" / "aquifer to soil zone" only links on active
  cells (as `_Qsz_in/_Qsz_out`); new columns "soil zone to specified heads" / "specified heads to soil zone" (written
  when GWBudget has them, `SZChdColumns()`): columns over specified-head cells (`_szcQ`, their capillary rise
  `_szcCapL`), exchange links whose cell is a specified head this step (existing models; `_szxQ`, their rise), and the
  rise a specified head below a dried top cell supplies. Summed over the HRUs each equals GWBudget.csv's column.
- Runs without specified heads: GWSoilExchange.csv byte-identical (same header and values).
- Test: `test_mf6_budget.py` B9 (a generated model with HRU 2 wholly over specified heads; the existing B1 hillslope
  with a specified-head toe). Before: the columns are missing (and existing models booked the specified-head exchange
  as aquifer exchange) -> FAIL. After: sums equal GWBudget within 1.6e-10 of the gross flow; HRU 2 base 99.000 m.
- Tests changed accordingly: test_rough_terrain's base check uses the links over specified heads too (its "flinks").
  test_vz_kinematic K8 `ric_c` (a specified head at 97 m) differs from the build before only in GWSoilExchange.csv
  (the two new columns, and level and water table now averaged with the column over the specified head): intended;
  K8 passes with this build as the reference.

## IB4 (S3) damaged soil-zone restart values
- GWHotValue (ParseInitialConditionFile.cpp) stops with BAD_DATA on a value that is not finite in any groundwater
  block (:GWHeads, :GWRechargeStore, :GWReservoirSeepage, :GWRiverLossCarry, :GWSoilZoneColumns, :GWVadoseColumns,
  :GWVadoseClassColumns, :GWSoilZoneLag), and on negative water below -1e-6 in :GWSoilZoneColumns and the node contents
  of :GWVadoseColumns / :GWVadoseClassColumns. Message: "<block>: the value nan is not a finite number; is the .rvc
  file damaged?" / "... is negative (a water amount)".
- Test: `test_inputs.py` I18 (nan and -50 in :GWSoilZoneColumns, nan in :GWHeads, the undamaged file). Before: all
  run -> FAIL. After: the three stop with their messages, the undamaged one runs.

## Documents
Manual (no PDF rebuild): ch5_accounting (restart details: seepage target kept, columns restored as written,
`:AgeTracerDatum`, damaged values; withheld discharge in the GWBudget columns; EnKF member series), ch4_vz_kinematic
(restart), ch4_vz_classes (one source-cell limit, C11), ch4_exchanges and ch6_reference (GWSoilExchange columns; the
discharge columns on unconverged steps; table label tab:outputs), appendix (hotstart table: `:AgeTracerDatum`, damaged
values; output files), ch8 tables (I14 text, I15-I18, R3/R4, B8 Liard, B9), ch8_verification (age-tracer datum).
User guide (hotstart paragraph, GWSoilExchange row) and tests/README (new tests).

## Results
- Quick soil-zone tier (`run_all.py --quick --only soilzone_*` without soilzone_liard, RAVEN_EXE_REF = the build
  before): 21 of 22 steps PASS (3 permanent skips in soilzone_confined_wet). soilzone_vz_kinematic fails only in K8
  `ric_c` against the build before (GWSoilExchange.csv, the intended SZ2 change); K8 is byte-identical with this build
  as the reference. The two rough-terrain steps first failed on the base check (columns over specified heads now in
  the mean); after the test update: 180 runs, 0 failed, and 180 with three classes, 0 failed.
- New cases in full mode: test_inputs I14-I18 pass (I15 multi-year chain 400 + 380 d); B8 Liard 60 days: 60
  unconverged steps, rows 559,615.9 m3 = run total 559,616 m3 (the auditor's figure); B9 passes.
- Liard T7 (365 days, PHYSICAL): PASS (62 s; identities 2e-12 / 8e-12 / 5e-11, no unconverged step), and its
  GWBudget, GWSoilExchange, GWHRUState, WatershedStorage, Hydrographs and solution.rvc are byte-identical to the build
  before (the Liard soil zone has no columns over specified heads).
- Other restart checks: tests/restart_test.py (Liard CONCEPTUAL, five grids, 30 + 30 d): deviations 8e-8 to 1e-6;
  existing/restart_ext.py: 9e-8.
- Byte identity (scratch script byteid.py; only paths and timings differ in the .txt files):
  - without groundwater, this build against base Raven: the small model (cold start + two chained hotstarts) without
    tracer and with Nitrate, an age tracer cold start, the Liard model without :GroundwaterModel 5 years and a 1-year
    hotstart from it: all files identical;
  - coupled, against the build before: Liard CONCEPTUAL 180 d, Liard existing model 31 d, a PHYSICAL + RICHARDS 4-HRU
    case and the B8 CONCEPTUAL case with 10 unconverged steps (no rivers): identical.
  - Intended differences: age-tracer hotstarts (format, CB2/CB3), restarts of coupled models whose seepage target is
    above capacity (CB1), KINEMATIC restarts below air-dry (VZ1; RICHARDS restarts at round-off), unconverged steps
    with rivers or stores (CB4, columns only), GWSoilExchange.csv of models with specified heads (SZ2), runs where the
    source-cell cap of VZ2 binds.
