# Soil zone v3, group q1 (audit round 10, code): restart of specified-head links, specific yield of existing models,
# interface warnings (reconstruction)

The original note was lost with the machine reset before round 10 was merged; the rebuild implemented FINDINGS_R10 group
q1 from its description (spec conv_330_end.md section 7). Audit A1 MT13: test_v2_ext.py X7 refers to section 2.

## 1. Restart of an existing model with specified-head top cells (R10 item 1)
WriteHotstart's :GWSoilZoneLag block wrote the specified-head links' exact exchange as the last step's exchange; on the
restart's step 1 the lagged source ran before the existing model's specified heads were known (they are read with the
step's period data), so the stored exchange was applied as a lagged source (GWSoilExchange deviated up to 9e-2; balances
held). Now the hotstart writes 0 for links whose column is over a specified head at the end of the run. Test:
test_restart.py R2 (10 days against 5 + 5: 2.5e-7).

## 2. Specific yield of an existing model (R10 item 2)
- No STO package or no SY: 0.2 is assumed for the soil-zone checks, the release limits and the unsaturated columns, with a
  warning naming all three.
- STO with SY below 0.01 (for example ICONVERT 0 everywhere, where MODFLOW holds SY 0): the model's SY is kept (outputs
  unchanged), floored at 0.01 for the release limits and the columns, with a warning giving the number of cells and the
  floor. The manual (sec:szexisting) says so.
- Test: test_v2_ext.py X7 (confined STO without SY; no STO); every identity holds.

## 3. Interface warnings and the connection-test drop (R10 items 3, 4)
- A step left unconverged only by the connection test (or the shortfall test) names that test and its link: "connection
  head X m from MODFLOW's head (F a against b)" or the soil-zone shortfall, instead of the head residual of the
  largest-residual link.
- At the connection-test drop the link's bracket and its last residual are reset, so the next update is the plain one
  (h_c = h). Test: test_interface_stiff.py S8.

## 4. Precision (R10 item 5)
With :SoilZone PHYSICAL the hotstart's :GWHeads carries 17 significant digits (12 otherwise), so a restart starts from
MODFLOW's heads as they were. Columns of existing models use S_s 1e-5 (not the model's SS); the manual says so.
