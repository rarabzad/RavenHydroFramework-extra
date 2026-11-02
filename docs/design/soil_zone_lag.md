# Soil zone v3: `:SoilZoneVadose LAG` (linear storage cascade) — design note

Rebuild of the v3 LAG worker's work (original branch v3-lag, turn 277) in the final form after v3 audit rounds R1-R10.
Code: `src/GWVadoseLag.cpp` (rebuild branch rb-lag); tests `tests/soilzone/test_vz_lag.py`, `vadose_lag_unit.cpp`;
manual `docs/manual/chapters/ch4_vz_lag.tex` (Section sec:szvadoselag), figure `figures/make_vz_lag_figures.py`.

## 1. Model
- State: the Richards column (`gwvz::vz_column`: MakeGrid nodes, contents th with consistent psi), the hydrostatic
  reference (SetReference(0), as RICHARDS). S_i = (th_i - th_eq,i) dz_i is the store of a linear reservoir,
  k_i = t_m dz_i, outflow S_i/k_i (S_i > 0 only) to the next node, the last into the water table.
  Build, MoveBottom, RelStorage, VZStep's water-table following, the Sy release caps and the hotstart apply unchanged;
  a hotstart of any method can be read by any other.
- Why the shared column: one storage definition (unsaturated zone storage = water above equilibrium) for all methods,
  so the model side (booking, release caps, rule (i)/(ii) give-back, classes) needs nothing method-specific.

## 2. Travel time (eq. lagtm)
- `{parameter}` > 0: t_m [d/m] for all materials. 0/absent: per material from the kinematic-wave celerity at
  q_r = 1 mm/d with K = Ks Se^eps, Se = (th - ths + Sy)/Sy, eps = 2b + 3: t_m = Sy Se_r/(eps q),
  Se_r = (q/Ks)^(1/eps), q = min(q_r, Ks). Ks < q_r: t_m = Sy/(eps Ks) [R1 item 4: the manual once said Sy/(eps q_r);
  manual corrected to the code]. Sy <= 0: t_m = 0 (nothing held, passed on at once); Ks <= 0 guarded (1e-12).
- Exported as `gwvz::LagTravelTime(mat, par)` (declared in GWVadose.h) so the model side can report travel times.
- One parameter, grammar `LAG {parameter} {nodes}` (ParseGWFile.cpp validates par >= 0, hooks).

## 3. Step (`gwvz::StepLag`)
- n equal substeps, n = clamp(ceil(dt/kmin - 1e-9), 1, 50) computed in double BEFORE the int cast [R1 item 3: the int
  cast of dt/kmin overflowed for tiny kmin (N = 200, LAG 1e-6)]. kmin = 0 (Sy 0) gives 50.
- Per substep, nodes top down, exact exponential solution with the constant inflow the node above released in that
  substep (piecewise-constant transfer: the only approximation; 1.1 % of the impulse in the cumulative response of the
  default 16-node column, mean travel time within 0.4 %, test U). Nodes pass on exactly what they release: mass-exact.
  qbot = (qin dt - storage change)/dt as for RICHARDS (identity exact by construction), clamped >= 0 (round-off).
- S_i < 0 (below equilibrium): no outflow; inflow first fills it to equilibrium (time (−S0)/I), then the exponential.
  Arises only from a hotstart written by another method [R2 item 10 wording: not "after the water table has moved",
  MoveBottom remaps excess and equilibrium together].
- Capacity S_i <= Smax_i = (ths - th_eq,i) dz_i: the excess passes on within the substep; from the last node into the
  water table. Decision: the capillary fringe (th_eq ~ ths, no room) is crossed at once — limiting the last node's
  outflow to Smax_N/k_N would make the fringe a bottleneck of throughput (ths - th_eq,N)/t_m ~ 0 and pile the column
  up. Consequence: an active column takes any qtop >= 0, rejected = 0 (stated in the manual; the soil zone's
  percolation and the saturated fraction limit inflow). The total outflow of a node in a substep with clipping equals
  that of the exact clipped trajectory (S0 + I h - Smax), so clipping is exact over the substep.
- qtop < 0: rejected entirely (rejected = qtop dt), the cascade still drains; capillary rise for LAG comes from the
  water table (hooks: VZOwnRise false, SZCapRiseWT).
- Inactive column: rejected = qtop dt (either sign), qbot 0 [R1 item 6, all methods reject].
- Fast path: no inflow and no node above equilibrium: state untouched (a hotstart state stays bit for bit).
- `info`: substeps = n, newton 0, fails 0.

## 4. Steady start (`gwvz::InitSteadyLag(c, S, q, par)`)
- S_i = min(q k_i, Smax_i) above the equilibrium of the column's current bottom; returns RelStorage. The next step
  under q delivers q to round-off (test U). Model-side wiring of `:SoilZoneVadoseInitialFlux` is the coordinator's
  (VZInit: call InitSteadyLag when _vzMode == 3).

## 5. N_eff and node count
N_eff = (sum k)^2/sum k^2. One material, capped grid (R1 item 2: weights 1.3^min(j,8)): N 3,4,6,8,12,16,24,32,50,100
-> 2.95, 3.93, 5.74, 7.38, 10.1, 12.0, 17.7, 25.3, 43.1, 93.0; beyond 18 nodes N_eff ~ N - 7. Node-count wording
"ceil(L/0.05 m) nodes but at least 3 and at most N" [R10 item 5]. The cap is the column library's (MakeGrid,
GWVadose.cpp, KINEMATIC worker); on a branch without it the unit test checks N <= 18 and prints SKIP for N > 18.

## 6. Known physics and limits
- No conductivity limit, no suction: the delay does not depend on the flux. With 3 depth classes the water table can
  be lower during rain (long upper-class columns hold more water) [decisions C.15]: the method's own.
- Sloping layers: each node its own material's t_m (L3: SAND over a larger-Sy class delays by +2.9 d).

## 7. Tests (test_vz_lag.py; "LAG tests: ALL PASSED"; run_all step soilzone_vz_lag; ~15 s full, same quick)
U (41 unit checks + 4 impulse responses against the exact cascade by matrix exponential), L1 storm (centroids +7.9 /
+15.0 / +34.9 d for LAG 2 / 4 / derived; RICHARDS +9.6 d), L2 rise/fall through the columns, L3 layered, L4 restart
60+60 vs 120 (2e-8), L5 existing-model round trip (2.4e-4), S speed (400 columns x 365 d: NONE 1.7 s, LAG 3.1 s,
RICHARDS 4.0 s), B byte-identity of b_hill_none, b_hill_ric, b_conceptual vs RAVEN_EXE_REF ("the build of the commit
before your change"; diagnostic column `interface change [m]` excluded; SKIP without reference) [R1 items 14, 16; R2
item 11; R3 item 10]. Identities at the standard limits; vz_identity in this script is scaled by the step's flows and
the two storages (GWBudget.csv's 10 significant digits of a 1e4 m3 store give 1e-5 m3 of rounding).

## 8. Outside this file (for the coordinator)
- GWVadose.h: declarations of LagTravelTime and InitSteadyLag added after StepLag (minimal).
- GWModelSummary "unsaturated columns" line prints "accuracy" for LAG; files_spec 3.3 wants "accuracy or travel times"
  (GroundwaterModel.cpp; could use gwvz::LagTravelTime per class).
- FINDINGS_R3 items 7 (warning text "at rest (their reference profile)") and 8 (negative P on KINEMATIC/LAG columns
  never booked as negative capillary rise) are in GWVadoseModel.cpp (shared with KINEMATIC).
- sz_check.vz_identity's scale (in + out + 1e-9 |S|, clipped at 1 m3) does not cover CSV rounding of large stores.
- Raven core: an empty .rvt segfaults (found while debugging the test); C.16 (:StartTime in a hotstart) not touched.
