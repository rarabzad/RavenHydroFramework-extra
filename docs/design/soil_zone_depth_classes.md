# Soil zone v3: depth classes of the unsaturated columns, initial flux, final water-table rules (rebuild worker cls)

Final design after v3 audit rounds R1-R10 (files_spec 2.7, 2.2 SZRecharge/SZRejRate, 2.12, 3.3, 4.6-4.7), rebuilt on the
v3 hooks (rb-v3h). Code: src/GWVadoseModel.cpp, GroundwaterModel.h/.cpp, ParseInitialConditionFile.cpp, small edits in
GWSoilZoneModel.cpp (SZRecharge), GWSoilZoneStep.cpp (SZRepayRates) and ParseGWFile.cpp (`:SoilZoneVadoseInitialFlux`).

## 1. Depth classes (`:SoilZoneVadoseClasses K`, 1..10)

- **Grouping: least spread.** The DEM samples of a link (`_szxCell[e].zbs`, ascending soil-zone bases) are grouped into
  at most K contiguous classes minimising the sum of squared deviations from the class means (Fisher's optimal 1-D
  partition, dynamic programming O(K N^2), `VZGroups`). Equal-count groups (the first-wave design) put a hummock and the
  slope below it in one class when the relief is skewed; least spread separates real levels (terraces, pits). Equal
  bases (within 1e-9 m) are never split, so K is also capped by the number of distinct bases and by N
  (`:SoilZoneSubgrid 1` or no DEM: K = 1). Fixed for the run.
- **Class top: mean, shifted with the link's mean base**: z_c = zb + (mean_c - mean). The area-weighted mean of the tops
  is the link's mean base `_szxZb[e]` (the mean depth to the water table is conserved, the median would not), and K = 1
  is exactly the single column at the mean base (byte-identical to the hooks build, test C1). (`_szxZb` is the cell's
  land minus D, the samples' mean differs from it by the DEM sampling; the shift keeps that offset.)
- **Area share** a_c = n_c/N; **class saturated fraction** `VZClassF(e,i,h)` = gwsz::SatFraction on the class's own
  samples with the link's d_s, so sum_c a_c F_c = F up to round-off; the summary line reports the largest deviation found
  at start-up over a range of heads (1.1e-16 in the tests).
- **Storage**: `_vzcCol` (all class columns), offsets `_vzOff[e].._vzOff[e+1]`, `_vzcA`, `_vzcZt`, `_vzcZbs`; per class
  `_vzcUse`, `_vzcF0`, `_vzcOut`, `_vzcRq`. `_vzCol` is gone (every reader now loops over the classes).
- **Recharge split**: P_c = V share a_c (1 - F0_c) into class column c (F0_c at the start-of-step connection head; one
  class: `_linkF`). A class without a column this step: its unsaturated share a_c (1 - F_c(hc)) reaches the water table
  in the step and its saturated share is rejected with F_c(hc), inside the head-dependent part (SZRecharge evaluates it
  at every interface update; `SZRejRate(e,h)` returns it for the interface tests).
- **Shared limits**: the classes of a link are processed in turn; what earlier classes took from the source cell (moving
  bottoms' deficits and new nodes, upflow, passed negative recharge) is subtracted from SZUpCap for the later ones
  (`used`, m3/d, exact arithmetic so that K = 1 reproduces the single column bit for bit), and the room of the link's
  soil layers is shared by the capillary rise (`SZRiseLayers(..., taken)`). Per-link arrays are sums over the classes;
  the takes are kept apart (`_vzAbsN`, `_vzQN`) because with classes one column may release while another takes, and
  SZRecharge books a take by its source (specified head below, SZW_RAVEN, top cell) and a release as the top cell's.
- **Capillary rise**: RICHARDS from each class column's top node on a a_c (1 - F_c); from the water table to each class's
  own base where the class has no column (RICHARDS) or for every class (KINEMATIC, LAG), each through the material just
  below that class's base (`VZGapMat(e, z_c)`); the drawdown of the implicit rate is per class (an approximation: the
  classes draw down the same water table).
- **Sloping layers**: class columns use the link's `vz_strat`; tops below or above the cell top are handled by the strat
  (first material extends up, last down), the bottom clamp at zlow and the build at max(h, zlow) are per class.
- **Hotstart**: `:GWVadoseClassColumns` (code 59; HRU ID, cell, class, classes of the cell, water table, contents) only
  when K > 1, `:GWVadoseColumns` (57) for K = 1 (unchanged format). A line is used only when the class count of the cell
  and the node count match; lines of the other block kind, another class count or node count make the column start at
  its reference profile with the warning "... do not match the columns (another :SoilZoneVadose node count, or another
  :SoilZoneVadoseClasses?); they start at rest (their reference profile)". Codes 50..59 are skipped with a warning in
  runs without a groundwater model.
- **Summary**: "depth classes : up to K per soil-zone link (least-spread grouping ...), n class columns on m links; class
  saturated fractions sum to the link's within x"; "unsaturated storage : V m3 at the start" (15 digits, all runs with
  columns; v3 audit R9 item 3), read by sz_check.vz_start so vz_identity is checked from step 1.

## 2. `:SoilZoneVadoseInitialFlux q` [mm/d]

- Parsed in ParseGWFile.cpp (q >= 0; negative stops). Applied in VZInit only on a cold start: a groundwater hotstart
  (:GWHeads, :GWSoilZoneColumns or a vadose block read) ignores it with the warning "... ignored: the run starts from a
  groundwater hotstart; n unsaturated columns the hotstart file does not hold start at rest (their reference profile)"
  (R1 item 7, R2 item 6, R3 item 7): in the run that wrote the hotstart those columns formed at rest or did not exist.
- RICHARDS: `VZSteadyRichards` solves the finite volumes of gwvz::Step node by node from the water table up (each face
  K_f (dpsi/dz + 1) = q, K_f the mean of the nodes' conductivities, Ks at the water table); the face flux increases with
  the upper node's pressure head where the gradient is downward, so bisection to round-off gives the unique root; a node
  above a layer with Ks < q builds positive pressure (perched saturated zone; R1 item 5). The discrete start is steady:
  step 1 of I1 has outflow = inflow to round-off. It lives in GWVadoseModel.cpp because GWVadose.cpp is not this
  worker's file; files_spec names it gwvz::InitSteadyRichards: move it there at the merge if wanted.
- KINEMATIC and LAG: their steady starts belong to their solvers (gwvz::InitSteadyKinematic; LAG S_i = min(q k_i,
  Smax_i)). Not merged when this was written: `VZSteadyKinematicStub` / `VZSteadyLagStub` leave the column at rest and
  the run warns "the steady start of ... columns is not available in this build"; test I1 prints SKIP for them. At the
  merge replace the two stub bodies by the solvers' calls.

## 3. Final water-table following rules (per class column, also K = 1)

- Release cap Sy dh integrated across the layers the rise crosses (`VZSyRise`; R2 item 5; gwvz::SyRise of the final
  library, kept local). The cell-room cap (integral of Sy over [h, min(zb, ztc)]) of the final code is NOT rebuilt (no
  verbatim source; open point).
- Rule (i) (R1 items 9, 10, 12; R5 item 5): outputs of a class column on ground saturated since the start of the step go
  back to the soil zone: R_q,c clip(F_c(h) - F0_c, 0, 1 - F0_c) with R_q,c = max(outputs, 0)/(1 - F0_c) (`_vzcRq`,
  `VZBackRate`), evaluated at the connection head in every SZRecharge; one class: F at the connection head = `_linkF`.
  It reduces the columns' inflow and outflow in GWBudget (both by `_vzBackV`).
- Rule (ii): a column that vanishes under a rising water table releases at most Sy dh to the aquifer; the rest
  (`_vzBackW`) goes back to the soil zone as rejected recharge and reduces only the columns' inflow.
- Columns built at max(h, zlow) (VZStep and VZInit; R2 item 7).
- Negative recharge share (P < 0) never enters a column (it was booked as negative capillary rise, R3 item 8): passed on
  to the cell (`_vzPass`), counted in `used` (R5 item 4). Not done here: the limit by what the top cell can still give
  and the cut back to the soil zone (needs SZNegCaps and negative rejection in SZApply, the interface worker's part).
- RICHARDS upflow beyond the source's limit: after the bottom node down to air-dry, the rest is taken off the column's
  capillary rise (R7 item 3, first part). The further steps (top cell as far as it can give, rest as negative rejected
  recharge) need the negative-rejection booking and are not done.
- These rules change PHYSICAL RICHARDS results wherever the water table reaches, within a step, ground unsaturated at its
  start (rule (i)); NONE, CONCEPTUAL and RICHARDS without such steps stay byte-identical to the hooks build (C1).

## 4. Tests (tests/soilzone/test_vz_classes.py C1-C9, test_vz_initial.py I1, I2, I4)
See the report in the commit history and the manual section sec:vzclasses for the numbers. C9 (band_e43 LAG K = 3
connection test) belongs to the interface iteration and prints SKIP here. The original numbers of C2/C3 (0.514 / +1.15 d;
squares 0.27 -> 0.0006) came from cases that were not recovered; the rebuilt cases are new and their numbers differ.
