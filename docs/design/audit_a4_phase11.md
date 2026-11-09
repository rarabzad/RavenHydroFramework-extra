# Audit A4, phase 11: physics and water books

Phase 11 of the round-4 audit (issue list: `spec/audit_A4/AUDIT_A4_issues_and_phases.md`) corrects CB4-1, CB4-2, IB4-1,
SZ4-1, SZ4-2, VZ4-1, CB4-4, VZ4-2 and VZ4-3. All three critical issues of round 4 came from round-3 fixes, so each fix
here is the simplest one found that is correct for generated and existing models, NEWTON on and off, metres/days and
feet/seconds, restarts and ensembles; the alternatives considered and rejected are listed with each. Every fix has a
regression test that fails with the reference build (`wt/p9/Raven_p9.exe`) and passes with this one, and the matching
cases in `tests/combinations.py` must move the water they test. An independent reviewer checked the fixes before they were
handed over (section "Independent review").

## IB4-1: head boundaries placed by a `:BoundaryHead` series

**Cause.** Phase 9 placed a boundary in every layer whose bottom lay below the highest step value of its series over the
run's own steps, and on steps with a lower head held the cell at `bottom + 0.01`. Such a cell then held the water table
at the cell bottom (CHD) or fed water from a head the series did not have (GHB at 97.01 m into an aquifer at 95 m), and a
run restarted after the series had dropped got other cells than the continuous run (2 CHD cells against 4).

**Placement (BuildStresses).** The highest head `hp` and lowest head `hm` are taken over `HEAD` and every value of the
series (the whole series as read, not the run's steps), so a restarted run places the same cells. `HEAD` always counts:
it applies wherever the series has no value, and whether that happens depends on the run's window. `LAYERS ALL`: every
layer whose bottom lies below `hp`. `LAYERS TOP`: the highest such layer and the layers below it down to the first whose
bottom lies below `hm`. Without a series `hp = hm = HEAD`, so placement is unchanged.

**Switching (SetBoundaryArrays, every step and the steady-state period).** A placed cell whose bottom lies at or above the
step's head is switched off for the step; with `LAYERS TOP` only the highest placed layer whose bottom lies below the
step's head is used.
- GHB: conductance 0 (head kept at `max(h, bottom + 0.01)`; no flow).
- CHD: MODFLOW 6 keeps one stress period for the whole run and its CHD sets IBOUND only when it reads a period, so the
  entry is left out of `CHD_RAVEN`'s list through the API before the solve: `NODELIST` (reduced nodes, from 1), `HEAD`
  and `NBOUND` hold the entries used this step, and IBOUND is set for every placed cell (held: MODFLOW's value of a held
  cell, read once while the list is whole; off: 1, an ordinary active cell). `chd_ad` (in `prepare_solve`) then sets the
  heads of the held cells, the solution treats the others as active cells, and `SIMVALS` holds the flows of the listed
  entries (`_chdAct` maps them back). When every entry is held and the list was never packed, nothing is written: runs
  without switching are unchanged byte for byte.
- Booked: the boundary's flow in `GWBudget.csv` is the flow of the cells used; `GWModelSummary.txt` gets the run total
  `head boundaries off : N cell-steps` when a boundary has a series.
- For the coupling (`_colCHDTop`) a column whose top cell is a placed specified head stays a specified-head column on
  every step (recharge, soil zone, stores and the lake there go to the specified head), as before. Documented.

**Rejected.**
- *A GHB with a large conductance in place of a series-driven CHD:* changes every such boundary's physics and books (CHD
  column), approximates the specified head, and the conductance choice affects solver conditioning.
- *One MODFLOW stress period per step with CHD period blocks:* changes TDIS, OC frequencies and every output of such runs;
  far wider than the issue.
- *Placing a CHD only in layers below the series' lowest head:* never switches anything off, but a CHD with a head above
  its cell top holds a confined pressure under an ordinary top cell, and a series that dips below every cell leaves the
  boundary with no cells at all.
- *Making `_colCHDTop` follow the switched cells in generated models:* the soil-zone links over specified heads (`szc`)
  and the surface-store, reservoir and recharge areas are built once; making them dynamic is the existing-model
  machinery (VZ4-1 shows its gaps) and much more code. Holding the column as a specified head is consistent in the books
  (the water those columns send goes to the boundary, outside MODFLOW).

**Test (`test_inputs.py` I21; 4 HRUs, layer 1 100-97 m, layer 2 97-79 m, EDGE with HEAD 90 and a series 99 m on day 1,
then 90 m).**

| Case | Reference build | This build |
|---|---|---|
| (a) GHB `LAYERS TOP` against an aquifer at 95 m, days 2-6 | +659 to +895 m3/d (feeds the aquifer) | -7,915 to -2,275 m3/d (drains); a series of 90 m gives the outputs of HEAD 90 alone; 10 cell-steps off |
| (b) CHD `LAYERS TOP`, head of the outlet HRU days 2-6 | 97.50 to 97.41 m (held at the layer-1 bottom) | 93.83 to 92.91 m |
| (c) CHD `LAYERS ALL`, 99 m for 3 days then 90 m, restart on day 4 | 2 cells against 4; flows 3.2, heads 3.5 m apart | 4 against 4; flows and heads identical |

Also checked by runs: a steady-state first period with a packed list, a 2-member Monte Carlo ensemble (both members
byte-identical to the single run), and MODFLOW's balance (3e-6 m3/d, as the static boundary).

## CB4-1: lake seepage when some of the lake's cells cannot take it

**Cause.** Phase 8 sent the whole seepage to the cells that could take it, renormalising their overlap weights, and gave
the lake their level. A sliver of a neighbouring HRU's cell (0.06 m2 of 40,000 m2) then took the lake's whole seepage, at
its own level: 2,987 m3/d against 662 the day before, and about 13 m3/d when the sliver was also a specified head.

**Change (Exchange read-back and PrepareTimeStep's distribution).** Only the share of the lake's bed over cells that can
take seepage exchanges water.
- At the read-back the reservoir's seepage constant is set to `k_seep F`, with `F = A_r ws`: `ws` the share (of the
  entries' overlap weight) of the cells that can take seepage this step (1 when all can) and `A_r` the share of the lake
  HRU's linked area the entries cover (generated models leave out the columns of a `:SpecifiedHeadBoundary`: `A_r < 1`;
  otherwise exactly 1). The level `h_gw` is the overlap mean over those cells, as before. `F = 1` gives `k_seep * 1.0`,
  bit for bit the earlier constant.
- The seepage computed in the routing is delivered the next step. Its share `wk` (the `ws` it was computed with) is kept;
  each cell that can take seepage then gets `V w_e / max(wn, wk)` (`wn` the share now), at most its rate when computed,
  and the rest, `V (1 - wn / max(wn, wk))`, goes through the existing return path (`_resUnsent`: a loss returned to the
  subbasin and booked as *seepage not delivered*; a gain taken back and booked as *gain not supplied*). So the day the
  lake's cells become specified heads the seepage computed for the whole bed is returned, instead of being piled into the
  sliver.
- `:GWReservoirSeepage` in `solution.rvc` carries `wk` as a third value (read as 1 when absent), so a restart inside a
  specified-head period delivers exactly what the continuous run does.
- The constant is never set to 0 (`max(F, 1e-12)`): Raven's reservoir keeps its last seepage, uncomputed, when the constant
  is 0, and that stale volume would then count in Raven's balance and be sent to the aquifer.
- Ensembles: the reservoir object outlives the groundwater model, so the scaled constant would carry into the next member;
  `ResetState` gives each coupled reservoir back its own constant (`_resK0`) before the model is rebuilt.

**Rejected.**
- *Scale only the delivery (`Q_e = V w_e`, return the rest):* the lake would lose its full seepage in the routing every
  step and receive most of it back through its subbasin, the "not delivered" column and warning would fire every step, and
  a gain would be taken back from a reach that may not carry it.
- *Ignore usable weights below a threshold:* still discontinuous at the threshold, and the threshold is arbitrary.
- *Scale `h_gw` instead of the constant:* the seepage's dependence on the stage change within the step is not scaled, so
  it does not go to 0 with `F`.

**Test (`tests/reservoir_checks.py`, new run_all step `reservoir_checks`).**

| Case | Reference build | This build |
|---|---|---|
| R1 existing model, CHD on the lake's 4 cells in periods 3-5, seepage delivered days 3-5 | 661.7, 2,987, 2,860 m3/d | 0.0009, 0.0043, 0.0043 m3/d; day 3's 661.7 m3 returned |
| R1b the sliver cell a specified head too | 0, 0, 0 (2,987 m3/d from R1) | 0, 0, 0 (0.004 m3/d from R1) |
| R1c restart on day 5 (inside the period) | (equal: the bug is restart-consistent) | equal within 1.2e-8 |
| R2 generated lake half over a `:SpecifiedHeadBoundary`: constant used / own | 1.000 | 0.500 |
| R1 feet/seconds (full mode) | — | within 1e-5 of metres/days |

Ensemble (two members) and restarts at days 2, 3, 4 and 5 of the audit's case (`rc.py`) were also run: members
byte-identical; restarts equal in GWHRUState (1e-8) and the reservoir columns. A restart whose `solution.rvc` falls on a
day when returned seepage still flows through the subbasin shows base Raven's initial-storage artefact for reservoir
inflow (MT4-4, Phase 13): Raven's balance error of the restarted part is offset by half that inflow (0.1 mm here); the
states are identical.

## CB4-2: the lake bed under `:SoilZone PHYSICAL`

**Change.** The bed in `max(z_wt, min(z_bed, stage))` is the ground: the model top, or with `:SoilZone PHYSICAL` on a lake
HRU with a soil zone `SZBase(k, ic) + D_k` (generated: the land; existing: the model top + D), the rule of `SWXDatum`.
Without PHYSICAL the code path is the old one.

**Test (R3).** Seepage on day 2 with the lake at its HRU's ground: CONCEPTUAL 676.3 m3/d; PHYSICAL 2,198.6 (reference)
and 676.3 m3/d (this build), generated and existing.

## CB4-4: unsupplied reservoir gains

`_resShortVol` gets a warning for the first ten steps over 1e-6 m3 and a run total (`reservoir gain not supplied`,
written whenever a reservoir is coupled). The manual's column description now includes gains of lakes whose cells are
specified heads or inactive, and the outputs list of the reservoir section names both books. **Test (R4,
CONC_NONE_res_dry):** 5,073.9 m3 not supplied; the reference build has no run total and no warning.

## SZ4-1: a surface store filled above its maximum by groundwater

**Choice: exempt the store from the initial-condition clip** (`CGroundwaterModel::SWXStoreSV`, beside the seepage
target), because that is what the continuous run holds; spilling the excess each step would change the continuous run
too and add a new flow to book. **Test (`test_surface_stores.py` SW4):** SW3 restarted after 10 days with HRU 5's
depression at 64.57 mm (DEP_MAX 50): Depression and discharge into the stores equal the continuous run (2.5e-9; the
reference build loses 2.9 mm of watershed Depression, 583 m3, and the discharge is 9 % off).

## SZ4-2: extinction depth from the ground under PHYSICAL

The EVT surface is the land (generated: `_land`, as without PHYSICAL) or, for an existing model, the model top plus the
column's overlap-weighted soil-zone thickness (0 for HRUs without one), in model units. The `(1 - F)` reduction is
unchanged. **Test (`test_water_table.py` P11):** water table 2.2 m below the ground, extinction depth 1.5 m: ET 0 (the
reference build 39.3 m3/d); at 1.2 m: 39.34 m3/d, equal to CONCEPTUAL (reference: 170.5), existing twin within 2.8e-6.

## VZ4-1: unsaturated columns on an existing model's own specified heads

**Change (VZStep).** On a link whose cell is a specified head this step, the link's active columns end: their water above
the reference profile (`RelStorage x area`, either sign) goes to the specified head, booked as column outflow and, in
`SZRecharge`'s branch for such links, as recharge onto CHD cells (`_vzAbsQ` of the link); run total `columns over specified
heads` (existing models with columns). A column forms again, at rest, when the cell is no longer a specified head.
Generated models never have exchange links on specified-head columns, so they are unchanged.

**Rejected.** Moving the column bottom to the specified head: the generated twin has no column there at all, and the
specified head absorbs whatever the column holds; refreshing IBOUND before the columns are built covers only heads known
at the start, not later stress periods.

**Test (`test_sz_existing.py` X9):** the combinations 'rise' case (LAG K=1; RICHARDS K=3 in the full mode): unsaturated
storage of the existing twin equals the generated run's (1.2e-6 and 5.6e-6 of its start; the reference build keeps 61.3 m3
frozen, 0.12 of its start); 2 columns / 61.3 m3 ended; no column line left in `solution.rvc`; every identity of
`combinations.check_run` holds.

## VZ4-2 and VZ4-3: column hotstarts

A new block `:GWVadoseColumnTops` (HRU ID, cell, depth class, column top [m], water above the reference profile [m3]) is
written with the column lines. Older files without it are read as before.
- **VZ4-3:** a line is used only when its column top matches within 1 mm (also the node count and classes, as before);
  otherwise the column starts at rest and the mismatch warning names the column top. **Test (`test_vz_initial.py` I8):**
  written with `:SoilZoneSubgrid 5` (7.37 m3), restarted with 8: 0 m3 at the start with the warning (reference: 18.2 m3,
  no warning); restarted with 5: 7.370579 m3 exactly.
- **VZ4-2:** a run without columns (`:SoilZoneVadose NONE` or no PHYSICAL) whose `.rvc` holds column lines warns, giving
  the line count and their water, and reports both in the run totals (`hotstart columns unused`). Refusing the run was
  rejected: switching the columns off on a restart is a legitimate choice, and a K or node mismatch is also handled by a
  warning. **Test (I7):** 34 lines, 506.873 m3 reported, equal to the first run's final unsaturated storage (reference: no
  warning).

## Combination cases (`tests/combinations.py`, moving-water group)

New exchange keys `resg` (lake crest and stage above the ground of its cells: it loses water) and `etw` (dry soil, no rain,
water table within the extinction depth), and stresses `bhs` (`:BoundaryHead` series on EDGE, `LAYERS TOP`, and GHB1:
0.5 m below the ground on days 1-3, 3 m on days 4-6, then 0.5 m) and `reschd` (existing twins: the model's own CHD on the
lake's 4 cells in periods 3-5). `check_run(..., need)` requires the flow: seepage delivered > 1 m3/d; seepage returned on
the day the specified heads start and none piled into the sliver after (1e-3); cell-steps switched off and a CHD flow on
every step; water-table ET > 0. Quick: 10 cases, 23 runs added (260 runs in all); full: 13 cases (398 runs).

## Existing tests changed by the fixes

- `existing/ext_exchanges.py` res_chd2 (2 of the lake's 5 cells become specified heads): it required every step's
  seepage to be delivered, the Phase 8 rule. Now, on the step the cells become specified heads, their share of the
  seepage computed the step before is returned (once), and from then on the other cells take their own share and all of
  it is delivered; the test checks exactly that.
- `test_vz_kinematic.py` K8, `test_vz_lag.py` B, `test_vz_classes.py` C1 compare outputs byte for byte with
  `RAVEN_EXE_REF`; `solution.rvc` of a run with unsaturated columns now has the `:GWVadoseColumnTops` block, so they
  compare it without that block (`sz_check.rvc_text`). Every other output stays byte-identical in those checks.

## Results

- `run_all.py --quick` (with `RAVEN_EXE_REF` = the reference build): 57 steps passed, 0 failed, 2 not run (the USGS
  examples, not installed); after the first pass the 4 steps above were corrected and re-run.
- Liard T7 (`test_liard_physical.py 365`): PASS (365 steps, 0 unconverged, 72 outer iterations at most, residual 8e-12).
- `combinations.py` full mode: 398 runs, 0 failed, 7 known (the reservoir weir-crest routing error of base Raven).
- `reservoir_checks.py` full mode (with the feet/seconds twin): all passed.
- Byte-identity (`wt/p11/patches/byteid.py`): no groundwater against base Raven (small model with chained hotstarts,
  Nitrate and AGE, Liard 5 years and a 1-year hotstart): identical. Liard CONCEPTUAL 180 d, the Liard existing model 31 d,
  CONCEPTUAL with unconverged steps, and both mf6 folders, against the reference build: identical. PHYSICAL + RICHARDS:
  every output identical except `solution.rvc`, which gains the `:GWVadoseColumnTops` block (intended, VZ4-3/VZ4-2).
- Combination cases against the reference build: a lake not over specified heads (CONC_NONE_res_plain) gives identical
  CSVs (`GWModelSummary.txt` gains the 'reservoir gain not supplied' line, `solution.rvc` the third value); the cases with a
  lake half over a specified head (ALL) change, as CB4-1/CB4-2 intend; PHYSICAL ET-alone and column 'rise' cases are
  identical apart from the summary path.

## Independent review

Not run by this phase: the agent that made the fixes had no tool to start another agent. The brief for the reviewer is in
`wt/p11/patches/review_brief.txt` (diffs `code_rb-p11.diff`, `extra_rb-p11-tests.diff`; review folder `wt/p11/review/`).
Its findings and the responses belong here before merge.

## Files

**Code** (`wt/p11/code`, branch rb-p11): `src/GroundwaterModel.cpp`, `src/GroundwaterModel.h`, `src/GWSoilZoneModel.cpp`,
`src/GWVadoseModel.cpp`, `src/GWExternal.cpp`, `src/ParseInitialConditionFile.cpp`.

**Extra** (`wt/p11/extra`, branch rb-p11-tests): `tests/reservoir_checks.py` (new), `tests/combinations.py`,
`tests/run_all.py`, `tests/README.md`, `tests/soilzone/test_inputs.py` (I21), `test_surface_stores.py` (SW4),
`test_water_table.py` (P11), `test_sz_existing.py` (X9), `test_vz_initial.py` (I7, I8); manual chapters `exchanges.tex`,
`existing_model.tex`, `appendix.tex`, `inputs_outputs.tex`, `accounting.tex`, `sz_vadose_classes.tex`, `developers.tex`,
`verification.tex`, `verification_soilzone.tex`; `docs/Raven_MF6_Groundwater_UserGuide.md`.

## For Phase 12

- CB4-3/MT4-1 is not fixed here: the original combination keys (`res`, `chd`, `ghb`, `wel`) still use `land()` at local x.
  The new keys `resg`, `etw`, `bhs`, `reschd` place the lake at world x and require their flows; Phase 12 can fold them
  into the corrected matrix.
- Recharge on an HRU whose linked area is mostly specified-head columns still piles onto the cells left
  (`_hruRchArea`), as the CB4-1 auditor noted; Raven fixes the volume, so it is not a water-book issue.
- A restart whose `solution.rvc` falls while returned reservoir seepage still flows into the reservoir shows base Raven's
  initial-storage artefact (MT4-4): Raven's balance error of the restarted part is offset by half the reservoir's
  inflow; worth naming in the MT4-4 known-issue text.
- `:SoilZoneVadose` columns ended over an existing model's specified heads give their water to the specified head; if
  Phase 12 adds a gen-vs-ext column-storage comparison to combinations.py (VZ4-1 suggestion), X9 already provides the
  pattern.

## Independent review

A separate reviewer re-ran the risky paths (CHD list packing at a switch step, restarts, ensembles, steady-state start, reservoir constant scaling and delivery, PHYSICAL datums in feet/seconds, store clip exemption, columns over existing-model CHD cells, column hotstarts, byte-identity). No S1 or S2 defects. Findings carried into Phase 12:

- **R11-1 (S3):** in generated models a column stays a specified-head column for the soil-zone books even on steps when every CHD cell placed in it is switched off; its recharge and soil-zone, store and lake water are booked as recharge onto CHD cells (books close, but the boundary is absent on those steps). Fix in Phase 12: treat such a column as an ordinary column on those steps.
- **R11-2 (S4):** `LAYERS TOP` with a series places lower layers counted from `HEAD` that are never switched on; the summary cell counts are inflated. Fix: base the lowest layer on the series values only when a series is given.
- **R11-3 (S4):** the "head boundaries off" run total leaves out the steady-state period.
