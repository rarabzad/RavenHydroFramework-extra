# Soil zone v3, worker "integ": interface iteration, negative recharge and the MODFLOW side (rebuild)

Final behaviour after v3 audit rounds 1-10 for everything except the KINEMATIC/LAG solvers, the depth classes / initial
flux and the rough-terrain suite. Sources: spec/files_spec.md 2.1-2.3, 2.8-2.12, decisions.md, code_fragments (SZIterate,
SZLinkFractions, shortfall functions, Exchange warnings, AppendRunTotals, WriteHotstart, GWExternal SY: copied verbatim).

## Reconstructed (no verbatim code survived) - decisions
- Head-dependent rejection term: SZRecharge stores the parts that follow the head (`_szxRl` = R_l of links without a
  carrying column; `_szxRqc`, `_szxF0` = rule (i) hand-back, K = 1); `SZRejRate(e,h)` evaluates them, `_szxRq/_szxRqP` at
  hc. SZLocalSolves makes s = max(tangent, chord to the head MODFLOW returned last) >= 0 (`_szxRs`; computed there so that
  the restore at convergence keeps the s MODFLOW solved with). SZSetArrays merges it with the line: Ct = Cg + s,
  Ht = (Cg Hg + s hc)/Ct (GHB, raised to bottom + 1 mm with the rest as SZQ rate); for rate links and kink drains a GHB of
  head hc and conductance s. With depth classes the class loop (cls worker) replaces the K = 1 parts.
- Kink drain (`_szxDrn`): for q < 0 (water rising into the soil) only when the column holds no free water at the start of
  the local solve (`_szxKink`): its exchange cannot reverse below the line's zero. A first version that used the drain for
  every q < 0 turned the exchange's slope on Liard's full-column link (entry 3648, the exemption (i) link) and left one
  step unconverged after 105 updates; with the free-water condition Liard T7 has 0 unconverged steps (3 509 outer
  iterations; 3 467 reference). Drain level max(Hg, bottom + 1 mm), conductance steepened there up to max(Cg, C); DDRN
  max(min(d_s/4, (h - H)/2), 1 mm) (one-sided drain of a supply-limited update: the v2 smoothing).
- SZ_WSH = 1 (B = max(10 % |Qc|, eps_h K)); constants not recovered.
- Supply-limited take reported as MODFLOW gets it: a slope at its floor (Cg <= 1e-6 C) is a rate (S4 would otherwise
  report 8.5e-5 m3/d from the 1e-9 C floor over 17 m).
- Not held (SZApply): the column's Apply shortfall of a negative rejection is taken from all the HRU's columns in
  proportion to their water; books: applied += shortfall - taken, not-held = shortfall - taken only when f >= 1.
- KeepColumnsWet: drained = every active cell convertible and the lowest cell at or below its bottom; set once per step,
  once more when the lowest cell is > 1 m below its bottom, and for non-finite heads; never in the last two iterations
  except non-finite heads. `_cellConv` from layer types (generated) / NPF ICELLTYPE memory (existing).
- Far-head rule: after flows, residual (one lambda) and gross flow (per-entry |q|, computed before the guard);
  `_xStart` updated only on converged steps; moved = position-based (as SZDivergedIterate).
- Recharge not applied (existing model without NEWTON): per bnd column `_Qcol - booked`, causes from IBOUND (all
  inactive / highest active IBOUND < 0), signed; GWBudget column only for such models.
- MF6Engine: `beforeSolve` hook (KeepColumnsWet + `_xPrevIt`); atexit handler reporting MODFLOW's STOP during a call
  (ExitGracefully(BAD_DATA_WARN) writes the error without a nested exit, then the banner).
- SY all zero with STO (R10 item 2): kept, floored at 0.01 with the "below 0.01 in n of m" warning (decisions.md C.5).
- VZStep (cls owns it; minimal K = 1 parts here): negative share passed to the cell up to the top cell's limit, counted
  in `_vzUsed`, the cut in `_vzRejV`; R7 item 3: upflow missing after air-dry taken off the column's capillary rise, the
  rest handed back as negative rejected recharge. NOT done here (left for the merge with cls): the top cell's own limit as
  the middle step of R7 item 3, the cell-room release cap (needs gwvz::SyRise).

## Outputs that change against the hooks build (Raven_v3h)
- CONCEPTUAL (Liard_groundwater, Liard_existing_model, 730 days): only GWBudget's "MF6 balance error [%]" (gross flow) and
  GWModelSummary.txt (run totals appended; paths/timings); every other CSV and Raven_errors.txt identical.
- PHYSICAL: results change by design (rejection term, kink drain, convergence tests, clipped bases); GWBudget gains
  "negative recharge the soil zone did not hold [m3]"; GWSoilExchange's F includes the columns over specified heads (X5).
