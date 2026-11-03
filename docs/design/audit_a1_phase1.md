# Audit A1, phase 1: physics and water books (agent p1)

Issue list: spec/audit_final/AUDIT_A1_issues_and_phases.md; findings F_CB, F_SZ, F_VZ, F_IB.

## CB1 (S1) unconverged steps without :SoilZone PHYSICAL
- Policy (decisions.md C.1, B.2): CONTINUE-like; every flow MODFLOW booked is given to Raven; only a negative residual
  is withheld, in proportion, from all discharge to Raven (seepage, gains of enabled subbasins, surface-store gains), as
  the PHYSICAL guard does. What the discharge cannot cover stays in the aquifer (in MODFLOW's balance error).
- The old cap at the step's inflow (storage release left out) is gone. A positive residual is not touched.
- Books: the withheld volume is the GWBudget row's residual (recharge + storage + other inflows - discharge - MF6
  balance error); its run total "discharge withheld" in GWModelSummary.txt, written only when such steps occurred (so
  converged CONCEPTUAL runs keep every file byte-identical; no new GWBudget column, which would change every CONCEPTUAL
  header). Warning per step, first ten per run (counter _szGuardN, shared with the PHYSICAL guard: the two paths are
  exclusive), text "... (MODFLOW unconverged): V m3 of discharge to Raven withheld for MODFLOW's negative residual".
- Test: test_mf6_budget.py B8 (CB auditor's case, limits 2 and 1).

## SZ1 (S2) negative rejected recharge in the local solve
- GWSoilZoneModel.cpp SZLocalSolves: gwsz::Apply instead of Fill (Fill ignores V < 0). Sibling: SZChdExchange
  (GWSoilZoneStep.cpp) gets the same (its rejV is >= 0 today: F = 0 for a negative recharge over CHD; Apply = Fill then).
  Other sites (SZApply, SZTrialShortfall, SZSolvedShortfall) already used Apply.
- Test: test_robustness.py R15b (soil zone after step 1 not below field capacity: 117.47 mm before, 126.08 after).

## VZ2 initial flux (1 - F) q
- VZInit: q_c = q0 (1 - VZClassF(e, i, h0)), h0 the initial top head (before the clamp at the aquifer's bottom);
  VZClassF with one class is the link's F. A column with q_c = 0 starts at rest.
- Test: test_vz_initial.py I5 (step-1 outflow = inflow; before 120.0 vs 100.8 m3).

## VZ3 RICHARDS steady start beyond capacity
- gwvz::InitSteadyRichards: if the profile for q has psi > 0 at the top node and Step's saturated top face (psi = 0 at
  the column top) would carry less than q, bisect on f for the profile whose top face carries f; start there with
  satTop. Optional *fw returns the flux into the water table. VZInit warns once (count of backed-up columns), also for
  KINEMATIC (InitSteadyKinematic returns f).
- Unit probe (audit/VZ/p4.cpp) against this source: step-1 storage change 0 (before -3.4e-4 m).
- Test: test_vz_initial.py I6 (K_VERT 1 mm/d under 2 mm/d: storage unchanged, outflow 40.000 m3, rejected 40.000).

## VZ1 hotstart class lines
- A class column missing from :GWVadoseClassColumns is a mismatch only if the link's lines carry another class count
  (or are malformed); otherwise it starts at rest silently, as the continuous run builds it.
- Test: test_vz_classes.py C10 (raven_mb_mm left out of the restart run: a 6-digit rounding artefact of the check's
  scale on a hotstart with a non-zero GROUNDWATER store, present before and after the fix).

## Core :StartTime (ParseInitialConditionFile.cpp case 19)
- tt_end = the run's start (JulianConvert(0, julian_start_day, julian_start_year)); time_diff = new start - old start
  (TimeDifference(old, new)), the shift that CAgeTracer::UpdateInitialConditions subtracts (mass = V x entry time).
- Note (not changed, upstream behaviour, would change age-tracer hotstarts of non-groundwater runs): the end of
  ParseInitialConditionsFile calls UpdateInitialConditions BEFORE SetInitialTimeOffset, so the offset never reaches the
  HRU masses. Reported for the user to decide.
- Test: test_inputs.py I10 (valgrind: no uninitialised value in TimeDifference / ParseInitialConditionsFile). The other
  valgrind reports of that run are base Raven's (RVPParameterWarning, CVegetationClass::RecalculateRootParams).

## IB3 :GWHeads header
- ExitGracefully (BAD_DATA) when a count is <= 0 or the product exceeds 1e9, before the reserve.
- Test: test_inputs.py I9.
