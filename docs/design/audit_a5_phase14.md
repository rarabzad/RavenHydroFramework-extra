# Audit A5, phase 14: physics and books

Phase 14 of the round-5 audit (issue list: `spec/audit_A5/AUDIT_A5_issues_and_phases.md`; brief:
`spec/audit_A5/phase14_15_brief.md`): CB5-1, CB5-2, CB5-3, CB5-4, VZ5-1, VZ5-2, VZ5-4, SZ5-1, SZ5-4, SZ5-5. Reference build:
the release build `wt/rel13_Raven.exe` (md5 `b0f670c6a854ed7646d8697f3538ffec`); this build: `wt/p14/Raven_p14.exe`.
Worktrees `wt/p14/code` (branch rb-p14) and `wt/p14/extra` (rb-p14-tests); nothing is committed (patches in
`wt/p14/patches/`).

Each behaviour change has a regression test that fails with the reference build and passes with this one (listed per
issue; the logs are in `patches/`).

## CB5-1: a river loss is taken from the reach's outflow

**Before.** A river loss was taken from the step's new runoff entering the in-catchment routing (`aRouted`) and then from
the flow entering the reach from upstream (`aQinnew`); the rest was carried to the next step and taken from the same two
sources. A headwater reach has no inflow, so on every dry step its whole leakage was carried, while the reach kept
flowing on water already in the channel and in the in-catchment routing. The auditor's headwater case (`rhead.py`,
TRI_CONVOLUTION, TIME_CONC 10 d): 283.6 of 309.5 m3 (92 %) still carried at the end, the hydrograph within 0.3 % of the
run without the river, no warning, no run total.

**Change.**
- `Solvers.cpp`: after `RouteWater`, before the irrigation demand, `CGroundwaterModel::TakeRiverLossFromOutflow(p,
  aQoutnew[last], tstep)` takes what is still unsupplied from the reach's routed outflow, keeping it at or above 0.
  Order: runoff, inflow, outflow.
- The take lowers only the outflow delivered (downstream, the outlet, the hydrograph). The routing state keeps the
  outflow before the take: `BeginReachRouting(p)`, called just before `RouteWater`, adds the last step's take T_{n-1}/dt
  back to the stored last-segment outflow (`SetQoutArray`, `_QoutLast` kept); `TakeRiverLossFromOutflow` restores the
  delivered value exactly before `UpdateOutflows`, so Raven books the delivered outflow (`_QoutLast` = delivered D_{n-1},
  `_aQout` = D_n). Raven's channel storage book `dV -= 0.5*(D_n+D_{n-1})*dt` is corrected by
  `-0.5*(T_n+T_{n-1})`: it then equals the book of the routing without the take (`-0.5*(U_n+U_{n-1})*dt`, U = D + T/dt).
  Net, for every routing method: channel storage follows the untaken routing, delivered = untaken - take, and the take
  goes to MODFLOW. Methods that do not read the stored outflow (ROUTE_NONE and every headwater, PLUG_FLOW,
  DIFFUSIVE_WAVE) are unaffected by the restore; Muskingum, Muskingum-Cunge (`c3*_aQout`), STORAGECOEFF
  (`c3*(_aQout-_Qlocal)`), ROUTE_HYDROLOGIC (`A(_aQout-_Qlocal)`) and TVD route the channel's own water as without the
  take; ROUTE_EXTERNAL keeps the untaken outflow as its overridden flow. `SubBasin.cpp` is not changed; the restore
  needs `_sbOutTakePrev`, which a hotstart restores from `:GWRiverTake`, so restarts stay exact.
- Outflows set from outside the routing. Streamflow assimilation (`AssimilationOverride`, after `UpdateOutflows`), a live
  file (`:SetStreamflow`, before the step), BMI and EnKF state updates replace the stored outflow (`SetQout` also sets
  `_QoutLast`); `ROUTE_EXTERNAL` reaches are fed this way. `EndReachRouting(p)`, called right after `UpdateOutflows`
  (before assimilation), records the stored last-segment outflow (`_sbQoutRec`, written as a fourth value of
  `:GWRiverTake` so a restart keeps it). `BeginReachRouting` compares: when the stored outflow differs, it was set from
  outside; the last take is not added back (the outflow as set is the reach's state), `TakeRiverLossFromOutflow` neither
  restores it nor applies the T_{n-1} half of the channel correction (Raven's books start from the outflow as set:
  `_QoutLast` is that outflow), and Raven warns (first ten). The step's take is still taken from the outflow routed from
  the set one, so it stays visible in the flows. The other option (carrying the loss of such reaches) was not taken: the
  coupling would then take nothing from an assimilated or externally fed reach, which still carries water. Test WB11
  (`ROUTE_EXTERNAL` for both subbasins, a live file setting SB1's outflow to 0 and SB2's to 0.02 m3/s every step, no rain
  or inflow, so the whole loss comes from the set outflow): the delivered outflow is the set outflow less the step's take
  (220.37 m3/d, within 0.001 m3), the channel storage ends as without the river (4e-12 m3), and the warning is given.
  Without the detection: the take is added back, the delivered outflow stays 0.02 m3/s (the take hidden) and the channel
  storage ends 2,400 m3 lower (fails). The comparison is equality of the stored double with the recorded one: an outside
  setter that writes exactly the routed value is indistinguishable, and harmless.
- Raven's own irrigation withdrawal lowers the stored outflow too (base Raven): with the state-keeping methods it drains
  routing water the book still counts. That is left as it is; the take adds nothing to it (WB10, irrigated).
- The loss still not supplied is carried as before. `FinishBudgetLine` warns (first ten steps) with the volume, and
  `AppendRunTotals` writes `river loss carried : V m3 at the end of the run` when V > 0, and `river take in transit :
  T_last/2 m3` (the second half of the last step's take, which MODFLOW received and Raven books in the next step) when
  T_last > 0 (WB7 checks it against `:GWRiverTake`).
- The supply limit (conductance capped by the reach's start-of-step channel outflow) is unchanged.

**What is still carried.** A loss the outflow cannot supply: the reach's flow at the end of the step is smaller than
what is left, which happens on the step in which a reach stops flowing (its start-of-step flow allowed the loss). In
the headwater case 1.15 m3 of 302.1 m3 (day 13, the last day the reach flows); with `ROUTE_DUMP` (`rhead.py`, `CR=ROUTE_DUMP`)
day 4's 112.3 m3 (the reach goes from 3,728 m3/d to 0 in that step). Both are now warned about and in the run totals.
Taking it from the start-of-step flow would rewrite flows already booked (and the downstream reach's inflow history);
not done.

**Test.** `watershed_balance.py` WB10 (every routing method: MUSKINGUM and MUSKINGUM_CUNGE over 300 km, STORAGECOEFF,
ROUTE_HYDROLOGIC, DIFFUSIVE_WAVE, PLUG_FLOW over 30 km; SB2 losing, fed only by a 0.05 m3/s inflow on days 1-5, then 35
dry days): the outflow leaving the watershed is lower than without the river by the loss taken (0.5 m3 + 1e-5), and the
end channel storage is the same (1e-5 of the take); also with a 0.003 m3/s irrigation demand on SB2, the run without the
river given the irrigation the river run delivered. This build: Muskingum taken 6,539.87 m3, outflow lower by 6,539.84,
channel -0.007 m3 (water still in transit in the 300 km reach); STORAGECOEFF/HYDROLOGIC 3,069.77 / 3,069.76, channel 4e-12.
The build before the routing-state restore: Muskingum taken 5,870 m3, outflow lower by 11,790 m3, 5,900 m3 stuck in the
channel book; STORAGECOEFF/HYDROLOGIC 31 m3 stuck (fails); DIFFUSIVE_WAVE and PLUG_FLOW pass with both. The reference
build passes too (it never takes from the outflow; it carries instead). WB8 (headwater, TRI_CONVOLUTION: carried at the end <= 1 % of the leakage; the
outflow lower than the no-river run by the loss applied, within 1 %; MB at round-off; a restart on day 6, after an
outflow take, gives the continuous run's hydrographs and channel storage, 1e-9) and WB9 (`ROUTE_DUMP`: the carried loss
warned about and equal to the run total). Reference build: WB8 fails (283.62 m3 carried, outflow lower by 25.8 m3 for
309.5 m3 of leakage; no `:GWRiverTake`), WB9 fails (no warning, no run total). This build: leakage 302.1 m3, carried
1.15 m3, outflow lower by 300.9 m3 = the 300.9 m3 applied; WB9 112.337 m3 carried, warned, run total 112.337.

## CB5-2: Raven's balance books a take half in its step and half in the next

**Change (the auditor's design, in the books only).**
- New members `_rivTake`, `_rivTakePrev` (watershed totals of the takes from reach inflows and outflows in the step
  and the last) and per subbasin `_sbInTake`, `_sbOutTake`, `_sbOutTakePrev` [m3]. `ApplyRiverExchange` (called every
  coupled step before routing) shifts them; `TakeRiverLossFromInflow` and `TakeRiverLossFromOutflow` add to them.
- `GetStepReturnVolume()` adds `0.5*(_rivTake - _rivTakePrev)`: Raven's balance books each take half in the step and half
  in the next, as its channel storage (inflow term `0.5*(Qin0+Qin1)`) and outflow give it up. Over a run: sum T - T_last/2,
  what the channel has given up. GWBudget.csv's `river exchange applied to Raven` stays the whole take (MODFLOW's side).
- The outflow takes of CB5-1 are booked the same way (one total).
- Hotstart: `:GWRiverTake  {subbasin ID, inflow take, outflow take [m3]} :EndGWRiverTake` (17 digits, only when a take
  is non-zero), read by `ParseInitialConditionFile.cpp` (code 60; added to the range ignored without
  `:GroundwaterModel`). `InitRiverTakes()` (called by `BuildRivers` and `ExtBuild`) restores the takes (subbasins
  enabled); the first step's shift makes them the "last step". Per subbasin rather than the watershed total the auditor
  proposed: the outflow take's channel-storage trapezoid needs the subbasin's last take; the total is their sum.
- `ResetState` clears them; `ClearHotstartData` clears `_hotRivTake`.

**Tests.** `watershed_balance.py` WB7 (`rtake.py`'s set-up: SB2 losing, fed by a 0.02 m3/s inflow hydrograph):
|MB| <= 1e-6 mm on every step with takes on 12 steps; a restart on day 5 (a take day) with |MB| <= 1e-6 mm and the
continuous run's hydrographs; a 2-member Monte Carlo ensemble whose members equal the single run (GWBudget.csv,
Hydrographs.csv) with |MB| <= 1e-6 mm. Reference build: MB 0.36 mm on take days, the restart 0.0025 mm (= -1/2 take
offset), no `:GWRiverTake`. This build: 2.8e-14 mm, restart 3.9e-14 mm, members 5.7e-14 mm. `rtake.py` with
ROUTE_NONE, ROUTE_PLUG_FLOW and ROUTE_HYDROLOGIC (restart on day 4): MB 0 on every step, restarts identical
(`patches/scripts/rtake.py`).

**Documents.** The rises and the hotstart offset are removed from accounting.tex (Raven's balance), developers.tex
(known issues), verification.tex, the user guide's known issues and the Liard README.

## CB5-3: recharge of an HRU partly over specified-head cells

**Change.** `Exchange` spreads `V*(A_link/A_linked)` over the HRU's non-CHD links (`A_linked` = the HRU's whole linked
area, `_hruLinkedArea`) and books `V*(1 - A_rch/A_linked)` as recharge onto CHD cells (`_QrchCHD`), when the HRU has
CHD links (`_hruRchArea < _hruLinkedArea`; otherwise the old expression, so runs without such HRUs are byte-identical).
`SZRecharge`: an HRU without a soil zone under `:SoilZone PHYSICAL` uses the same shares (its CHD share is booked in
`Exchange`); a soil-zone HRU already shared over all its links (`Aall`). Continuous in the overlap; the recharge identity
(Raven = MF6 + CHD + delay) holds.

**Test.** BR3: HRU 4 without soil (a profile with no horizons, its ponded rain flushed to GROUNDWATER) under `:SoilZone
PHYSICAL`, the `SZRecharge` branch for HRUs without a soil zone: onto CHD 800 -> 799.8 m3/d with the sliver, recharge
identity 1e-10, HRU 3's head -1.1 cm (the soil-less HRU's seepage drain on the sliver's cell); the reference: 800 -> 0,
+0.43 m (fails). `boundary_recharge.py` BR1 (`rsliver.py`'s set-up, CONCEPTUAL): with the 10 m2 sliver the recharge onto CHD is
the no-sliver run's times (1 - 2.5e-4), MODFLOW's recharge grows by that share only, seepage within 1 %, HRU 3's head
within 1 mm. Reference: onto CHD 400 -> 0 m3/d, seepage 134.8 -> 701.5 m3/d, head +5.6 cm (fails); this build: 400.00 ->
399.90 m3/d, seepage 134.78 -> 135.05 m3/d, head +5e-5 m. BR2: the same under `:SoilZone PHYSICAL` (a guard; it passes
with both builds).

**Effect on other runs.** Every CONCEPTUAL model with an HRU partly over specified-head cells: the share over them now
goes to the specified heads instead of the HRU's other cells (the test models of `sz_models.make_case(chd=...)` whose
last HRU covers the specified-head column and one more; the `:BoundaryHead` cases of `crs_inputs.py`). The Liard example
as shipped has no specified head and is unchanged.

## CB5-4: restarts after an unconverged step keep the start heads of the far-head test

**Change.** `WriteHotstart` writes, when the last step did not converge, `:GWStartHeads n` with `_xStart` (MODFLOW's heads
of the active cells at the end of the last converged step, 17 digits) and `:EndGWStartHeads`; the parser (code 61) checks
the count; `Exchange` takes `_xStart` from it when its size matches MODFLOW's X (else from X, as before).

**Test.** `test_confined_wet.py` W13: W7's model as a generated model with `:SolverMaxOuterIterations 3` (steps 1-8
unconverged): the 3-day run's `solution.rvc` holds `:GWStartHeads`; a 1-day run restarted from it writes the same heads
value for value; a 10-day run (ending converged) writes none; a restart on day 4 equals the continuous run. Reference:
no block (fails); the restart comparison passes with both (the decision changes only with far heads that moved by more
than the margin).

## VZ5-1: the unsaturated-column method is saved with the columns

**Change.** The block line names the method: `:GWVadoseColumns RICHARDS|KINEMATIC|LAG` (and `:GWVadoseClassColumns`).
The parser reads it (a word that is not a method stops the run: a damaged file). `VZInit`: when the file's method has
another reference profile (KINEMATIC: ths - Sy; RICHARDS and LAG: hydrostatic), no line is used; the columns start at
rest and the lines' water (from `:GWVadoseColumnTops`) is warned about and reported as dropped (`hotstart columns
unused`), as for VZ5-2. RICHARDS and LAG read each other's lines (the same reference: the auditor found them exact).
Conversion (`th_new = ThRef_new + (th_old - ThRef_old)`, clipped) was not taken: the clip makes it inexact.

`testconfig.rvc_same` (the comparison of `solution.rvc` with a reference build's in K8, LB and C1) leaves the method word
out when only one file names it (tools_check TC5 has both cases); C6 and C10 of `test_vz_classes.py` look for the new
warning ("columns of the hotstart file are not used").

**Test.** `test_vz_initial.py` VI9: RICHARDS -> KINEMATIC and KINEMATIC -> RICHARDS start at rest (0 m3), warning naming
the writing method, run total = the first run's final storage (3.71994 and 490.955 m3); RICHARDS -> LAG starts with the
written 3.7199 m3. Reference: +3,668.6 and -3,627.9 m3 at the start, no warning (fails).

## VZ5-2: hotstart column lines no column uses

**Change.** `VZInit` marks the lines it uses (HRU, cell, class); after the loop every other line of `:GWVadoseColumns` /
`:GWVadoseClassColumns` is counted with its water from `:GWVadoseColumnTops`: those at a current link were written for
other columns (method, node count, classes, top), the rest are on cells that are no longer exchange links. One warning
gives both counts and the volume; the run total `hotstart columns unused` reports them (it existed for runs without
columns). The former mismatch warning (a count only) is replaced by it.

**Test.** `test_vz_initial.py` VI10 (`t6unmatched.py`: a specified head added over HRU 1 on the restart): 2 lines,
77.5262 m3 warned about and reported; start storage + that volume = the file's 122.6658 m3. Reference: no warning, no run
total (fails). VI8 (other tops) still passes.

## VZ5-4: columns on cells held at the start; columns counted once

**Change.**
1. `VZInit` builds no column on a generated model's link whose cell is a specified head at the start (`_colCHDTop`,
   set by `UpdateSwitchedCHDTop` before `SZInitColumns`); one forms, at rest, when the cell is released. An existing
   model's specified heads are known only after MODFLOW reads the first period: unchanged there.
2. `VZStep`'s specified-head branch counts in `_vzChdN` only columns that held water (R != 0): a column rebuilt at rest
   on a restart and ended in step 1 is not counted again.
3. Manual: `unsaturated zone to aquifer` includes the water of columns ended over specified heads and of negative uptakes
   (appendix); sec:szchd describes the ending of columns for `:BoundaryHead` series too, and that a generated model builds
   none on cells held at the start.

**Tests.** `test_vz_initial.py` VI11 (`t7combo.py LAG 1 chd+swx bhs`): start storage 839.0169 m3 = the fixed-head case;
step-1 recharge onto CHD = step 2's (49.92 m3/d). Reference: 958.8764 m3, 169.78 m3/d on day 1 (fails). VI12 (`t3extrs.py`,
KINEMATIC K = 3, existing model's own CHD in periods 3-5, restart on day 4): first part 18 columns, 225.75 m3, restarted
part 0, continuous 18. Reference: restarted part 18 (fails).

## SZ5-1: lagged-exchange debt at a restart and at the end

**Change.**
- `SZInitColumns` reads the debt of `:GWSoilZoneLag` only with LAGGED timing.
- `Initialize`: the debt of the file not taken up (AFTER timing, no `:SoilZone PHYSICAL`, or lines that match no link) is
  warned about with its volume and reported as `hotstart debt unused` (the aquifer keeps that water). The auditor's other
  option, repaying it in the first step as a fixed SZQ rate under AFTER, would need the LAGGED budget columns in an AFTER
  run; not taken.
- Run total `lagged debt open : V m3 at the end of the run ... W m3 of it on cells that are specified heads at the end`
  (LAGGED runs, when V > 0).
- exchanges.tex: "nothing is created or lost" replaced by: the debt is owed by the aquifer until repaid; the run totals.

**Test.** `test_restart.py` RS6 (`debt.py`'s set-up): the 2-day run reports 1.59381 m3 open (= `:GWSoilZoneLag`); a LAGGED
restart repays 1.5938 m3 in its first step; AFTER and CONCEPTUAL restarts warn and report 1.59381 m3 unrepaid.
Reference: no run total, no warnings (fails).

## SZ5-4: soil water level of a column without free water (wording)

inputs_outputs.tex, appendix.tex, the user guide (`GWSoilExchange.csv`) and `tools/plot_soilzone.py`'s docstring: the
level of a column without free water is the lowest soil-zone base of its DEM points, so it can lie below the (mean)
base; rejection starts when the water table reaches that lowest base.

## SZ5-5: DIS and STO read under MODFLOW's names

**Change.** `ExtProbe` (after MODFLOW is initialised) finds the memory names of the discretization and storage packages
by probing `NLAY` / `STRGSS`: MODFLOW's fixed `DIS` / `STO` first, then the name file's names (and `DISV` for a DISV
model, as before). `_disName`/`_stoName` then hold the memory names, used for NLAY/NROW/NCOL, the origin, STRGSS/STRGSY
and SY (`SY` was read with the literal `STO`).

**Test.** `existing/ext_inputs.py` package_names: the synthetic Liard model with `DIS6 ... grid_main` and
`STO6 ... storage_main`: runs, no "storage flows not accessible" warning, `GWBudget.csv` byte-identical to the usual names'
run. Reference: "cannot read NLAY" (fails).

## Reference comparisons in run_all

Two run_all checks compare a run with the reference build; their cases had the changed features, so they now use cases
without them:
- `crs_inputs.py`: the lon/lat Liard run with its specified-head lake has HRUs partly over the lake's cells (CB5-3: their
  recharge share goes to the lake). The comparison now uses the lon/lat run with the GHB boundary only (byte-identical to
  the reference); the CRS comparisons between the lon/lat and UTM runs keep the lake.
- `existing/ext_exchanges.py` plain: the Liard existing model's stream package loses water that the reaches now supply
  from their outflows (CB5-1, up to 4.5e5 m3 in the river columns over 10 days). The comparison now leaves out
  `:StreamPackage` (the river package stays the model's own), and is identical to the reference.
After the merge the reference build can be this one, and both can return to their full cases.

## Byte identity

`patches/byteid.py` (log `patches/byteid.log`): no-groundwater runs identical to base Raven (Liard 5 years and its
hotstart, the small model with chained hotstarts, Nitrate, AGE; the reservoir case identical to the reference and to base
Raven but for the reservoir corrections); CONCEPTUAL runs without rivers (one with 10 unconverged steps whose last step
converges) identical to the reference build, `mf6/` included; PHYSICAL with RICHARDS and KINEMATIC columns: only the
method on the `:GWVadoseColumns` line of `solution.rvc` differs. Runs with rivers are reported: Liard CONCEPTUAL 180 d
(no loss taken from an inflow in that period) identical; Liard existing model 31 d differs by the river changes.

## Numbers in the documents

`patches/p14_numbers.py` (log `patches/p14_numbers.log`), this build:
- Example A (Liard, 20 years): Raven's MB error 0.431061 mm on every step (reference: 0.431061, raised to 0.437054 mm on 34
  snowmelt days); no river loss carried at any step (as before: no outflow take was needed), so its flows and
  GWBudget.csv are unchanged; tools_audit MB max 0.4311 mm.
- Restart, second year from the first year's solution.rvc: 0.000000 mm (both builds).
- Grid-size table (one year under subbasin 52): 0.431061 mm for 1, 2, 4 km and the default tolerance, 0.215530 mm with
  half-day steps (unchanged).
- Example B (existing model, 2 years): MB error 0.431061 mm on every step (reference 0.431 to 0.4376 mm); river loss
  carried max 1.059e8 m3 (about 1.06e8 as before), on 271 days (reference 288), 0 at the end; 10 carry warnings.
  Hydrographs and GWBudget.csv river columns change (the losses now come partly from the reach outflows).
- Changed in the documents: accounting.tex (Raven's balance; the GWBudget checklist), verification.tex (Liard MB, the
  behaviour table, the fixed-head lake row, a new paragraph on river losses and boundary recharge), developers.tex
  (known issue removed), applying.tex (FAQ), exchanges.tex (rivers, recharge, LAGGED debt, columns over specified
  heads), appendix.tex, inputs_outputs.tex, sz_interface.tex, sz_vadose_*.tex, verification_soilzone.tex, the user
  guide, examples/README.md (Example B: 271 days), examples/Liard_groundwater/README.md (MB 0.431 mm on every step),
  tests/README.md.
- The run_all step `tutorials` fails: tutorial 2's model has HRUs partly over its specified heads (CB5-3: recharge onto
  CHD, MF6 recharge, heads and the quoted values of tutorials 2, 3, 5 and 6 change). Its committed numbers must be
  regenerated.
- Not regenerated: the tutorials (docs/tutorials, restructured elsewhere): every quoted Raven MB error of a run with a
  river loss taken from an inflow, and every Example B number (hydrographs, river columns, carry days), must be
  regenerated; the behaviour-test audit table (tables/run_checks.tex, "Fixed head, delay": round-off residuals) was not
  rerun.
