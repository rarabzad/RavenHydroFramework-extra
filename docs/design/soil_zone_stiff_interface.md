# Soil zone v3, group f2: the stiff interface (reconstruction)

The original note was lost with the machine reset (audit A1 MT13: test_interface_stiff.py referred to it). This
reconstruction is written from the final code (GWSoilZoneModel.cpp SZIterate / SZLinkFractions / SZLocalSolves), the
manual (Section "The interface iteration in detail", sec:szinterface; "Solving soil and aquifer together") and the
tests (tests/soilzone/test_interface_stiff.py S1-S8, test_robustness R10-R13). Section numbers follow the references
made to the original (sections 2.4-2.8 were cited in the v3 audit rounds).

## 1. Problem
Over a top aquifer layer of very low vertical conductivity (K_v < 0.01 m/d, confined above its top) the recharge
(1 - F) R is a valve of very high gain: a small rise of the head saturates more ground and rejects more recharge. With the
rejection fixed from the start of the step the interface failed on 10-100 % of the steps of S1, with 170-350 outer
iterations per step.

## 2. Design
### 2.1 Schedule
Interface updates after each of the first n_early = min(5, max(1, n_max/5)) outer iterations, later only after outer
iterations on which MODFLOW converged, at most :SoilZoneIteration max of them; the last tenth of the limit (at least two
outer iterations) is left to MODFLOW with a frozen boundary. :SoilZoneIteration 0 and an outer limit of 1 are explicit
coupling; with a limit of 2 or 3 the single update's flow test compares with the predictor's total exchange (S6, S7).

### 2.2 Rejection as a head-dependent term
With the connection head h_c of the update MODFLOW receives the link's recharge R (1 - F(h_c)) as a rate plus the
linearised rejection q_rej(h) = s (h_c - h), s = max(R F'(h_c), R (F(h*) - F(h_c)) / (h* - h_c)) >= 0, merged into the
exchange's GHB (SZX_RAVEN). The term is booked with the exchange, so mass is exact. F is recomputed on every update
(SZLinkFractions), so the rejection follows the converged head.

### 2.3 Column hand-back
On a link whose unsaturated column carries the step, the saturated share is rejected with F_0 (start of the step); the
water the column gives back on ground that saturated since then is in the term:
R_q min(max(F(h) - F_0, 0), 1 - F_0), R_q the column's outputs over 1 - F_0. (v3 audit round 5, e1.2: with one depth
class the fraction used for the hand-back must be the link's own F, test_robustness R16; the term remains, contrary to an
earlier sentence of this note.)

### 2.4 Supply limit of the boundary MODFLOW keeps
The last update (frozen boundary, explicit mode, the last one the budget allows) may not take more from a column than it
holds down to the lowest head the cell can reach (the bottom of the column's lowest active cell): the line's slope is
limited by the free water, line and term together are capped (S3-S5). GWModelSummary.txt reports "supply-limited updates"
and the largest take beyond the free water (must be 0).

### 2.5 Kink drain
Where water rises into a soil zone without free water the exchange has a kink at the level where contact ends; it is given
to MODFLOW as a drain (SZD_RAVEN) ending at the line's zero, at least the cell bottom + 1 mm, smoothed over >= 1 mm (S2).

### 2.6 Shortfall
Shortfall (water MODFLOW took that the soil did not hold) is 0 whenever the interface converges; it appears only on steps
whose interface did not converge, mostly at a low outer-iteration limit, also on MODFLOW-converged steps whose last update
was an early, unlimited one (R13_b1: 46,758 m3). Neither the shortfall nor MODFLOW's negative residual is handed to Raven:
the discharge is withheld in proportion (GWBudget "... withheld" columns).

### 2.7 Convergence test
An update is converged when every column's soil-level change is below the head tolerance, the total exchange changed by no
more than max(tol_Q G, sum F C max(eps_h, DVCLOSE)), and, per link in head units, the rejection at MODFLOW's head and at the
connection head differ by less than eps_h. (Round 9: a connection head further than d_s from MODFLOW's head with a
different fraction keeps the interface unconverged and drops the link's bracket; round 10: the next update is then plain,
and the warning names the connection test, its link and the two fractions, S8.)

### 2.8 Results
S1 4.0 (NONE) / 5.9 (RICHARDS) outer iterations per step, every step converged (170-350 before); S2 4.4 / 6.0. Numbers of the rebuilt code: manual Table "Soil zone v3: the
interface and the MODFLOW side".
