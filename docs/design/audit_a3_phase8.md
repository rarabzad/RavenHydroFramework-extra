# Audit A3, phase 8: physics and water books

Phase 8 of the round-3 audit (issue list: `spec/audit_A3/AUDIT_A3_issues_and_phases.md`) corrects CB3-1, CB3-2, SZ3-1,
VZ3-1, VZ3-2 and IB3-2. Each fix has a regression test that fails with the reference build (`wt/m7/Raven_m7.exe`) and
passes with this one. A new step, `tests/combinations.py`, runs small synthetic cases across a matrix of options and checks
every water identity on each run.

## CB3-1: water-table ET of an existing model without NEWTON, read back at a dry top cell

**Cause.** Without `FIXED_CELL`, MODFLOW's EVT package moves an entry whose cell is inactive to the highest active cell of
its column (`evt_cf`: `highest_active`) and computes the ET there. In a model without NEWTON a top cell that dries becomes
inactive. Raven read the flow back as `hcof*X - rhs` with the head of the fixed top cell, which is HDRY (-1e30). As a
result, `GWBudget.csv` booked about -4.6e34 m3/d.

**Choice: follow MODFLOW's node list rather than `FIXED_CELL`.**
- With `FIXED_CELL` a dried top cell gives no ET at all, even when the water table in the cell below is within the
  extinction depth.
- With NEWTON, a dry top cell stays active, its head is the water table, and the ET comes from that water table.
- Following the node list keeps MODFLOW's own physics (ET from the water table wherever it is, within the extinction depth
  of the surface). It is also the behaviour closest to the NEWTON model.

In the audit case, without NEWTON MODFLOW takes 638,337 m3/d on step 1, and the NEWTON twin 745,558 m3/d. With
`FIXED_CELL` it would be 0.

**Change (GroundwaterModel.cpp, EVT read-back).** The head is taken at `NODELIST[i]` of `EVT_RAVEN`, the reduced node
MODFLOW used. It falls back to the top node when the list is unavailable. On a column that is wholly inactive, MODFLOW sets
hcof = rhs = 0, so the flow is 0. With NEWTON, and in generated models, the node is the top node as before, so the results
are unchanged.

**Test.** `tests/existing/ext_exchanges.py` case `et_dry`: the md model without NEWTON, layer 1 4 m thick, heads 5 m
deep, EXTINCTION_DEPTH 6 m, 6 days (15 in the full mode).

| Check | Reference build | This build |
|---|---|---|
| Water-table ET | -4.58e34 to -1.88e34 m3/d | 3.65e5 to 6.38e5 m3/d, equal to MODFLOW's budget file (1.3e-10) |
| MODFLOW balance error | 4.6e34 | 5e-3 m3/d |
| HDRY in GWBudget.csv | yes | no |

## CB3-2: existing-model reservoir seepage on specified-head or dry cells

**Cause.** The RES read-back handled only a gain MODFLOW could not supply. A loss sent to a specified-head cell, or to an
inactive cell of a model without NEWTON, got act = 0 from MODFLOW's WEL. The difference was neither returned nor booked.

**Changes (GroundwaterModel.cpp/.h).**
1. **Cells that cannot take the seepage get none.** Each step, before the seepage is set, the reservoir's entries are
   flagged. An entry cannot take seepage if its column's top is a specified head this step (`_colCHDTop`, which
   `ExtUpdateCHDTop` refreshes after `PrepareTimeStep`), or if its cell is inactive in a model without NEWTON (IBOUND).
   - The seepage goes to the other entries by their overlap weights.
   - The arithmetic is untouched when every cell can take it, so generated models are byte-identical.
2. **A lake with no usable cell left exchanges nothing in that step.** Its seepage goes to no cell (`_resUnsent`), and the
   groundwater level Raven gives it after the solve is the level over its usable cells only. With no usable cell, that
   level is the lake stage, so the next seepage is 0. Before this change, such a lake kept computing seepage from the
   heads of specified-head cells, and with dry cells it computed a 7.4e6 m3/d gain that had to be taken back from the
   reach.
3. **Seepage MODFLOW does not take is returned.** A loss (spec > 0) that MODFLOW does not take (act < spec), or that no
   cell could take, has already left the lake. It is returned to the water reaching the reservoir's subbasin in the same
   step, through a negative `_sbLossCarry`, the same path the gain shortfall uses. That water flows on to the reservoir.
   The return is booked in:
   - a new `GWBudget.csv` column, *reservoir seepage not delivered by MODFLOW [m3]* (existing models with reservoir
     exchange only, written last);
   - a run total in `GWModelSummary.txt`, *reservoir seepage not delivered*;
   - a warning for the first ten steps.

   The river exchange applied to Raven includes the returned water, and the audit tool's river identity subtracts it.
   An unsent gain is booked as "gain not supplied", as before.
4. **Identity.** sent·dt = delivered·dt − gain not supplied + not delivered. The audit tool's
   `reservoir: (delivered + not supplied) / sent` now uses this signed form. Its earlier `(delivered + not supplied)`
   had the wrong sign for a gain shortfall.

**Tests.** `tests/existing/ext_exchanges.py` cases `res_chd`, `res_chd2` and `res_dry`:

| Case | Set-up | Reference build | This build |
|---|---|---|---|
| `res_chd` | CHD the model keeps on all 5 lake cells from stress period 2 | 3.18e6 m3 sent, 0 delivered, nothing booked: identity −1.0 | 6.36e5 m3 returned (the seepage computed before its cells became specified heads), then the lake is disconnected; warning; run total = column; identity 0 |
| `res_chd2` | 2 of the 5 lake cells specified heads | delivered/sent 0.32 | delivered = sent (2.92e6 m3) |
| `res_dry` | model without NEWTON, heads 25 m deep | — | identity 0; no HDRY |

**Note (Phase 9 candidate, not changed).** In a model without NEWTON, MODFLOW's WEL does not move an entry to the highest
active cell as EVT and RCH do. A lake over a dried top cell is therefore disconnected, rather than seeping to the water
table in the layer below. Sending the seepage to the highest active cell would need the RES node list rewritten each step.

## SZ3-1: `:SurfaceWaterExchange` on surface stores of `:SoilZone PHYSICAL` HRUs

**Cause.** The SWX bed and stage datum were the model top: `_top` in generated models (= land − D under PHYSICAL), and
`_extTopRaw` in existing models (the soil zone lies on the model top). Groundwater therefore filled the depressions while
the soil zone was still unsaturated.

**Change.** A new `CGroundwaterModel::SWXDatum(e)` (GWSoilZoneModel.cpp) gives each SWX entry its datum in model units:
- Without PHYSICAL: the model top, unchanged.
- With PHYSICAL: the overlap-weighted ground of the group's HRUs in the column. For an HRU with a soil zone, the ground is
  `SZBase(k, ic) + _szD[k]`. For an HRU without one, it is the model top, where its seepage drain is. For an existing
  model the datum is converted with `/_hf` from the model top.

This datum is used as RBOT and as the stage datum each step, and in `gwf.swx` / `raven.swx`. The `raven.swx` header names
the ground under PHYSICAL. The manual's example set-up (`inputs_outputs.tex`) is now correct as written; one sentence
explains where the store's bed is. `exchanges.tex` (ch:stores) and `existing_model.tex` (package table) describe the datum.

**Test.** `tests/soilzone/test_surface_stores.py` (new run_all step `soilzone_surface_stores`). It uses the audit's c3
set-up: 5 HRUs, D = 1 m, depressions with `ABST_FILL`, 20 days.

| Case | Reference build | This build |
|---|---|---|
| SW1, generated | discharge into the stores on days with every water table below the ground: up to 2,276 m3/d; bed 0 m above the model top | none on those days; leakage 6,135 m3; bed exactly D = 1.000000 m above the model top |
| SW2, existing twin | same failure | equal to SW1 within 5.4e-6 |
| SW3, control (water table above the ground at the outlet) | — | discharge 1,399 m3 |

## VZ3-1: rule (ii) hand-back lost in a negative-recharge step

**Change (GWSoilZoneModel.cpp, SZRecharge, negative path).** `_szxRej[e]` now also gets `_vzBackW[e]`, the water of a
column that vanished this step, beyond what goes to the aquifer. That water was already in the HRU's `rej` and in the
column books, but not in the link's rejected recharge that `SZApply` returns to the soil zone.

**Test.** `test_robustness.py` R21 (N8), the audit's t2_backneg case (RICHARDS, GR4J_X2 1e-4; in the full mode also 60
and KINEMATIC). The recharge identity is 0.31 with the reference build and 0 with this one.

## VZ3-2: negative recharge of depth classes without a column bypassed the top-cell limit

**Change (SZRecharge, `_vzUse` branch, `au > 0`, negative).** The share is limited like the one-class path:
`take = max(q, -_szxNegCap[e])`, and the cut `(q - take)·dt` goes back to the soil zone as negative rejected recharge
(`_szNegCutQ` counts it).

`_szxNegCap` is `SZUpCap − _vzUsed − capQ − repay`, computed once per update before `SZRecharge`. It therefore already
excludes what the active classes passed, the capillary rise and the repayment. `_vzUsed` is not increased here:
`SZRecharge` runs several times per step (predictor and every interface update), and nothing after it reads `_vzUsed` in
the step, so adding to it would accumulate across calls.

The manual (`sz_interface.tex`, `sz_vadose_classes.tex`) states the limit for the classes without a column.

**Test.** `test_robustness.py` R22 (N9), the audit's t1_negcls case (hummocks, top cell 0.6 m, GR4J_X2 250). The ratio of
MODFLOW's step-1 recharge to the limit:

| Case | Reference build | This build |
|---|---|---|
| K = 1 | 1.000000 | 1.000000 |
| K = 3 | 2.207873 | 1.000000; cut 2,620 m3 back to the soil zone |
| LAG, K = 3 (full mode) | — | — |

## IB3-2: a head boundary whose HEAD lies below its cells

**Changes (GroundwaterModel.cpp).**
- The `:BoundaryHead` series are initialised before the model is built.
- `BuildStresses` places each boundary with the highest head it has in the run. Without a series, that is `HEAD`. With a
  series, it is the highest step value over the run, evaluated as `SetBoundaryArrays` applies them (`GetAvgValue` per
  step, `HEAD` where the series is blank).
- A boundary that selects cells but has none left gets a warning naming the head and the highest cell bottom.
- `gwf.chd` and `gwf.ghb` write `max(head, bottom + 0.01)` only where the static head lies at or below a cell's bottom (a
  cell the series placed). MODFLOW checks the file values, and Raven sets each step's head before the solve.

Without a series, placement is unchanged.

**Test.** `test_inputs.py` I20:

| Case | Reference build | This build |
|---|---|---|
| HEAD 0 with a 99.5 m series | 0 cells, no warning | 2 CHD cells, flow 1,390 m3 |
| HEAD 0 alone | 0 cells, no warning | 0 cells and the warning |

`tests/crs_inputs.py`'s empty comparison (IB3-3) is left to Phase 9.

## Option combinations (`tests/combinations.py`, run_all step `combinations`)

**Set-up.** Small synthetic strips (4 HRUs of 200 x 200 m, 100 m cells) are built with `sz_models.make_case` plus option
edits. The matrix has two groups:
- **Exchange group.** ET, river (routed channel, `:RiverGeometry`), surface stores, a reservoir, a well, a GHB and a CHD,
  all together, each alone, and ET+SWX+RES+CHD. Each combination runs under plain conditions, dry top cells (1 m top layer
  above the water table) and negative recharge (dry+negative in the full mode), with CONCEPTUAL and PHYSICAL.
- **Column group.** RICHARDS, KINEMATIC and LAG, with K = 1 or 3, under plain conditions, negative recharge, a rising
  water table (flat, specified head 0.3 m below the ground, wet columns: the columns vanish), rise + negative, dry top
  cells, and dry + negative.

Every case runs generated and as an existing twin: with NEWTON, without NEWTON (CONCEPTUAL), and converted to
feet/seconds. With a CHD, the lake sits on the outlet HRU, half over specified-head cells.

**Checks on every run.**
- MODFLOW's balance on converged steps, and its cumulative residual.
- The recharge, soil-zone and column identities (`sz_check`), and Raven's balance.
- Per-step river, surface-store and reservoir books (sent(t) = awaiting(t−1); sent = delivered − gain not supplied + not
  delivered), each relative to its terms.
- Seepage returned = MODFLOW seepage.
- Run totals = their columns.
- No HDRY or NaN in the GW*.csv files and WatershedStorage.csv.
- A physics check: no groundwater discharge into the surface stores on a step with every HRU's water table below its
  ground.

**Size.** Quick: 237 runs of 8 days, about 50 s. Full: about 370 runs of 15 days, including half-day steps, about 2–3
minutes.

**Results.**

| Build | Quick | Full |
|---|---|---|
| This build | 237 runs, 0 failed, 5 known (about 50 s) | 369 runs, 0 failed, 7 known (122 s) |
| Reference build (quick) | 70 failed | — |

The 70 reference-build failures by cause:

| Failures | Issue | Check |
|---|---|---|
| 69 | SZ3-1 | discharge into stores below the ground |
| 19 | VZ3-1 | recharge identity in rise+negative cases |
| 1 | CB3-1 | HDRY 8e31 in GWBudget.csv, MODFLOW balance |

**What the matrix uncovered beyond the listed issues.**
1. *Known, outside the coupling's books (Phase 9: investigate in Raven's reservoir routing).* In the CONCEPTUAL/PHYSICAL
   `res`+`neg` cases, Raven's balance error is 4.8 m3 and 2.2 m3 on two steps. It equals exactly the reservoir's own
   routing balance error (`ReservoirMassBalance.csv` "MB error") on the steps the lake's stage falls back below the weir
   crest while groundwater feeds it.
   - The coupling's books hold.
   - With base Raven and a fixed `:SeepageParameters` level, crest crossings show no such error, so the trigger is the
     groundwater level changing between steps near the crest (`Reservoir.cpp` `RouteWater` / `UpdateMassBalance`,
     project-modified file).
   - The script reports it as KNOWN only when Raven's balance error equals the reservoir's own, so any other balance
     error still fails.
   - Reproduce: `python3 tests/combinations.py --only CONC_NONE_res_neg` (or `:WriteReservoirMBFile`).
2. The audit tool's reservoir identity had the wrong sign for a gain shortfall; corrected (above).
3. Nothing else failed: the river, surface-store, recharge-not-applied and soil-zone books held in every combination,
   including no NEWTON, dry cells, specified heads under every exchange, feet/seconds and half-day steps.

## Byte identity

See the final report: `wt/p8/patches/byteid.py` (the p7b script with p8 paths; reference `wt/m7/Raven_m7.exe`). Expected
results:
- **No groundwater against base Raven:** identical.
- **CONCEPTUAL Liard and the Liard existing model against the reference:** identical. They use none of the changed paths:
  - no `:ReservoirExchange`;
  - no `:SurfaceWaterExchange` under PHYSICAL;
  - water-table ET only with NEWTON;
  - no `:BoundaryHead`.
- **PHYSICAL + RICHARDS (t1) and CONCEPTUAL unconverged (b8):** identical.

## Files

**Code** (`wt/p8/code`, branch rb-p8):
- `src/GroundwaterModel.cpp`: EVT node list, reservoir cells/return/books, SWX datum use, boundary placement, CHD/GHB
  file heads, run total, warning.
- `src/GroundwaterModel.h`: members, `SWXDatum`.
- `src/GWSoilZoneModel.cpp`: `SWXDatum`; VZ3-1 and VZ3-2 in `SZRecharge`.
- `src/GWExternal.cpp`: `raven.swx` datum and header.

**Extra** (`wt/p8/extra`, branch rb-p8-tests):
- Tests:
  - `tests/combinations.py` (new);
  - `tests/soilzone/test_surface_stores.py` (new);
  - `tests/existing/ext_exchanges.py` (et_dry, res_chd, res_chd2, res_dry);
  - `tests/soilzone/test_robustness.py` (R21, R22);
  - `tests/soilzone/test_inputs.py` (I20);
  - `tests/run_all.py` (steps `combinations` and `soilzone_surface_stores`);
  - `tests/README.md`.
- `examples/Liard_groundwater/tools_audit.py`: reservoir identity and river identity with the returned seepage.
- Manual chapters: `existing_model.tex`, `exchanges.tex`, `appendix.tex`, `inputs_outputs.tex`, `sz_interface.tex`,
  `sz_vadose_classes.tex`, `verification.tex`, `verification_soilzone.tex`.

## Handed to Phase 9

- The reservoir routing balance error at the weir crest with a coupled groundwater level (above).
- In a model without NEWTON, reservoir seepage over a dried top cell could go to the highest active cell (as EVT and RCH
  do), instead of disconnecting the lake.
- The audit's note on CB3-1: in a model without NEWTON, seepage drains sit on dried, inactive layer-1 cells, and heads can
  rise far above the ground (the model's own behaviour). A warning when coupled columns have a dry top cell in a model
  without NEWTON would help users.
- IB3-3 (crs_inputs boundaries with heads above their cells) can now also check the series placement.
