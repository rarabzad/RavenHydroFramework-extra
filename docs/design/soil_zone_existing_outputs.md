# Soil zone v3, group f3: existing models and the outputs of the soil zone (reconstruction)

The original note was lost with the machine reset (audit A1 MT13: test_v2_ext.py X5 and X6 referred to its sections 2
and 3). Reconstructed from the final code (GWExternal.cpp, GroundwaterModel.cpp WriteBudget / run totals), the manual
(sec:szexisting, appendix "Soil zone v3: outputs, run totals and messages") and test_v2_ext.py X1-X7.

## 1. Scope
:SoilZone PHYSICAL with an existing MODFLOW 6 model (:MF6Simulation): Raven adds raven.szx (GHB SZX_RAVEN), raven.szq
(WEL SZQ_RAVEN), raven.szd (DRN SZD_RAVEN) and, with more than one layer, raven.szw (WEL SZW_RAVEN) to the model's name
file; the soil-zone base is the top of the top active cell, the land d_sz higher, its relief from :LandSurface; K33 (else
K) and SY of the model; b, psi_a, theta_s of the unsaturated columns from :SoilZoneAquiferClass.

## 2. NEWTON required; MODFLOW's own input errors
- Without NEWTON a top cell that dries leaves MODFLOW's solve (HDRY): the recharge, the soil-zone exchange and the columns
  over it lose their cell. Rough-terrain runs of such models stopped or misbehaved, so NEWTON is required: Raven stops at
  start-up ("... needs an existing model that uses the Newton-Raphson formulation: add NEWTON to the OPTIONS of <nam>
  (MODFLOW 6 then also needs LINEAR_ACCELERATION BICGSTAB in its IMS file)"); decisions.md C.4. (The CONCEPTUAL coupling
  keeps accepting models without NEWTON; the recharge MODFLOW does not apply there is booked, "recharge not applied by
  MODFLOW".)
- An input error MODFLOW finds inside its library (for example LINEAR_ACCELERATION CG with NEWTON) makes the library
  return an error during initialisation: Raven reports "MODFLOW 6 stopped the run during <call>: <the error report of
  mfsim.lst>" instead of stopping without a message.
- Test X6: both stops.

## 3. Outputs
- GWSoilExchange.csv: the saturated fraction F of an HRU is over all its columns, those over specified heads included,
  as the rejected recharge is; recharge is rejected only where F > 0 (X5).
- GWModelSummary.txt ends with the run totals, written at the end of the run (they were written at the start and showed
  0 substeps): time steps, MODFLOW-unconverged steps, interface-unconverged steps, the columns' substeps (and Newton
  iterations except LAG), outer iterations, steps with drained columns kept 1 mm above their bottoms, supply-limited
  updates, connection-test drops, the negative recharge cut / not held, the recharge not applied (existing models
  without NEWTON, always written).
- Test X5 on the x3 runs (generated and existing, unsaturated columns, a specified-head toe, three classes).
