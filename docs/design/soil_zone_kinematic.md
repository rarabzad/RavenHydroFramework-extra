# Soil zone v3: `:SoilZoneVadose KINEMATIC` (design note, rebuild worker "kin")

Final design after the v3 audit rounds R1-R10 (rebuild of the lost v3-kw work; spec files_spec.md 2.4, 2.5, 2.7, 4.6).
Code: src/GWVadoseKW.cpp (new), src/GWVadose.cpp/.h (reference handling, grid cap, inactive contract, SyRise),
two minimal edits in src/GWVadoseModel.cpp. Tests: tests/soilzone/vadose_kw_unit.cpp, test_vz_kinematic.py (K1-K8).
Manual: docs/manual/chapters/ch4_vz_kinematic.tex (`sec:szvadosekw`), figures/make_vz_kinematic_figures.py.

## 1. Conductivity: the column's Campbell curve shifted to vanish at ths - Sy
K(th) = Ks [(th/ths)^e - x0^e] / (1 - x0^e), e = 2b + 3, x0 = (ths - Sy)/ths; K = 0 below thr = ths - Sy, Ks at ths.
The first design (UZF form Ks ((th - thr)/(ths - thr))^e, measured from thr) is far too slow at recharge fluxes: the
V2a storm delivered nothing in 90 days. Shifting the curve keeps the column's own Campbell conductivity over almost all
of its range (Figure fig_vz_kinematic a), needs no new parameter ("KINEMATIC is Richards without capillarity") and has
a true no-flow state at the drained content. Accepted in the original v3 (turn 278).

## 2. Reference ths - Sy (gwvz::SetReference(1))
`ThRef(m, height)` returns ThEq (REFMODE 0: RICHARDS, LAG) or max(ths - Sy, 0) (REFMODE 1). Used by RelStorage,
ExcessIntegral, MoveBottom and Build (Build sets th = thr, psi = PsiOf(thr)). Consequences:
- a new column starts at thr (relative storage 0);
- falling water table: new nodes at thr, nothing exchanged; the lower clip is 0 (not air-dry) for REFMODE 1, so
  nothing is ever exchanged [audit R3 c1.1 / FINDINGS_R3 item 13]; the upper clip at ths stays (a node straddling two
  materials could average above the porosity of its new material: the excess drains to the aquifer);
- rising water table: the excess th - thr below it is released, <= integral of Sy dz over the rise (unit test).
REFMODE 0 code paths are unchanged (byte-identity K8, vadose_unit 35 checks).

## 3. StepKinematic
Backward Euler, first-order upwind, node by node top down: (th - th0) dz/h + K(th) - q_in = 0. g is increasing and
convex below ths, and the explicit guess th0 + (q_in - K0) h/dz is an upper bound when wetting (a lower bound when
draining), so Newton started at the upper end converges monotonically; a bracket and bisection guard it. Convergence:
Newton correction below 1e-12 ths (the first rebuild stopped only on bracket width and bisected for 40 iterations once
Newton had converged exactly; fixed: 3.7 iterations per node and substep). The outflow of each node is q_in less its
storage rate, so it is >= 0 by the choice of bracket and the column balance is exact; the flux into the water table is
(applied inflow - storage change)/dt as in Step (clip at 0 acts on round-off only).
- Saturation: when g(ths) <= 0 the node takes th = ths, passes Ks, and the excess backs up into the nodes above
  (their outflow was that much smaller); what the top node cannot hold is rejected (> 0). No node exceeds ths.
- qtop < 0: rejected entirely (rejected = qtop dt < 0); the column still drains in the step.
- Substeps: accepted when no content changes by more than the accuracy (default 0.02), halved otherwise (down to
  1e-6 d), grown by 1.5 when the change was below half of it. The first substep is predicted from the top node
  (dz0 acc / q), which removes most rejected substeps in storms; deterministic (no state carried between steps, so a
  restart from the 15-digit contents continues the run exactly).
- Inactive column: rejected = qtop dt, return 0 (the same contract for Step, fixed there too: it rejected max(qtop,0)
  and also returned it, a double count) [FINDINGS_R1 item 6].
- Guards [FINDINGS_R1 item 1]: a material with Sy <= 0 (or a degenerate 1 - x0^e <= 1e-12, or ths <= 0) is a "step"
  material (K = 0 below ths, Ks at ths): it stores up to ths and passes on up to Ks, no inverse, no division. The same
  in InitSteadyKinematic. POROSITY 0 is also stopped at start-up in VZSetup (":SoilZoneVadose ...: aquifer class X has
  POROSITY 0 ...", all methods), and psi is not evaluated for ths = 0 (Build, StepKinematic).

## 4. InitSteadyKinematic(c, S, q)
Steady profile for `:SoilZoneVadoseInitialFlux` (model wiring is the coordinator's step): f = min(q, smallest Ks of
the column's nodes); every node K(th) = f (th = ths (x0^e + f/A)^(1/e)); if q > f, the nodes from the top down to the
deepest node of that smallest Ks are saturated (the backed-up steady state of the scheme; the top rejects q - f)
[FINDINGS_R1 item 5]. Returns f. Unit test: K(th) = q to 1e-12, steady under StepKinematic for 30 days (changes <=
3e-17), backed-up case steady with flux = the slow layer's Ks and rejection q - Ks.

## 5. Column library items shared with the other methods
- MakeGrid cap [FINDINGS_R1 item 2]: weights 1.3^min(j, min(h, 8)): N <= 18 never reaches the cap, so their grids are
  bit for bit the hooks build's (unit test N = 3..18; N >= 19 differ); from N = 19 the middle fills at equal thickness
  ~L/(N-10); N = 200 over 10 m: thinnest node 6.5 mm (was 6e-12 m). Manual ch4 discretization text corrected.
- `gwvz::SyRise(S, z0, zt)`: integral of Sy dz across layers, for the release caps of VZStep [FINDINGS_R2 item 5];
  the classes worker (VZStep owner) wires it; KINEMATIC needs it because with a rise across a low-Sy/high-Sy boundary
  the single-material cap would hold the bottom back.

## 6. Model side (minimal, GWVadoseModel.cpp)
- VZSetup: POROSITY 0 stop; the Sy-vs-drainable-porosity warning skipped for _vzMode == 2 (meaningless with the
  reference ths - Sy) [files_spec 2.7].
- VZStep: the `_vzSlowed` warning not written for _vzMode == 2 [FINDINGS_R2 item 5] (the counter still counts).
Not done here (other owners), see the report: the VZInit "at rest (their reference profile)" text belongs to the
initial-flux warning [FINDINGS_R3 item 7]; a negative recharge share P on a KINEMATIC/LAG column is today booked as
negative capillary rise in VZStep (`if (rej<0.0){_vzCapV...}`): it must be passed on / handed back instead
[FINDINGS_R3 item 8, R5 e1.1].

## 7. Tests and numbers (rebuild, 2026-11)
- K1 unit (167 checks): random 16 000 steps, mass 8.5e-13 relative, bounds exact; analytical wave L 6 m, q 10 mm/d:
  arrival 57.21 d, half-flux time 57.23 (N=16) .. 57.21 (N=128); front width 1.35 / 0.37 / 0.15 / 0.08 d; tail error
  5.2 / 2.7 / 1.3 / 0.7 % of q; default grid/accuracy/daily steps 0.5 % late; sand over clay steady flux = clay Ks.
- K2 storm (V2a): columns wetted by 400 days of 2 mm/d: centroid delay RICHARDS 7.6 d, KINEMATIC 11.9 d (the original
  v3 numbers 7.6 / 12 d). Started at rest (plain V2a) KINEMATIC soaks up the storm (centroid +72 d, 15 % delivered in
  90 days; the known weakness that :SoilZoneVadoseInitialFlux addresses), RICHARDS +9.6 d.
- K3 collapse and re-forming (`after` in ok), K4 sand over clay (RICHARDS counted), K5 restart 1.9e-10, K6 existing
  model 2.7e-5, K7 run results returned (times reported only), K8 byte-identity (NONE, RICHARDS x2, CONCEPTUAL).
- vz_identity is computed in test_vz_kinematic.py relative to flows plus the storage itself: GWBudget.csv carries 10
  significant digits, so a column storage of 1.3e4 m3 is known only to ~1e-6 m3 (sz_check's version gave 8.8e-6 on
  K2 with a 1 m3 floor; the coordinator may want the same scale in sz_check).
