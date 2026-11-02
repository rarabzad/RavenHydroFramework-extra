# Rebuild note: merge of the five v3 workers (agent merge3)

Code rb-merge3 = soil-zone (v3 hooks) + rb-kin (fast-forward), rb-lag, rb-cls, rb-integ (rb-rough has no code commits).
Extra rb-merge3-tests = + rb-kin-tests, rb-lag-tests, rb-cls-tests, rb-integ-tests, rb-rough-tests.

## Conflicts and integration decisions
- GWVadose.h/.cpp: kin's and lag's additions merged without conflict (InitSteadyKinematic, KofKinematic, SyRise,
  LagTravelTime, InitSteadyLag, capped grid, reference mode).
- GWVadoseModel.cpp (kin vs cls): cls's class loop kept; kin's `_vzMode != 2` condition moved onto cls's `_vzSlowed`
  warning. cls's VZSteadyKinematicStub/VZSteadyLagStub replaced by gwvz::InitSteadyKinematic/InitSteadyLag (the
  "not available in this build" warning removed); VZSteadyRichards moved to gwvz::InitSteadyRichards (GWVadose.cpp, same
  code); cls's local VZSyRise replaced by gwvz::SyRise.
- GWModelSummary "unsaturated columns" line: LAG prints the travel times (t_m range in d/m, given or derived at 1 mm/d,
  and the columns' total travel times at the start) instead of the accuracy.
- Rejection (cls vs integ): one SZRejRate(e, h, slope) (integ's interface); for an entry whose columns carried the share
  it is class by class (cls's VZBackRate with _vzcRq per class column + R_l a_c F_c(h) for classes without a column,
  analytic slope); otherwise integ's R_l F(h). VZBackRate also hands back everything of a class with F0 = 1 (also in
  explicit coupling) and nothing that follows the head in explicit coupling (files_spec 2.7). _szxRl is set for column
  entries only when a class has no column (SZRejFollows stays false otherwise). SZNegCaps, the cut handed back and the
  not-held booking are integ's.
- VZStep (cls loop + integ): negative share not split by F, passed on (`_vzPass`) up to the top cell's limit (CHD: all;
  top cell holds the water table: SZUpCap - used; else nothing), counted in `used` -> `_vzUsed[e]` (read by SZNegCaps);
  the cut goes into `_vzRejV` (negative rejected recharge); never booked as negative capillary rise (kin R3 item 8).
  R7 item 3: air-dry, capillary rise, then the top cell as far as it can still give (topLeft, when the top cell is the
  source), rest handed back as negative rejected recharge (counted as column inflow, so vz_identity holds).
  Release cap: min(SyRise over the rise, cell room = SyRise over [h, min(zb, top of the top cell)]).
- SZRecharge: cls's K = 1 / K > 1 booking, plus integ's negative handling (`neg`: no F split, _szNegCutQ).
- GWBudget line: cls's hand-back corrections + integ's "not held" column.
- Tests: run_all steps of all workers kept; make_case accepts integ's `demf` and cls's `dem_fn`/`dem_res`; sz_check
  vz_identity scaled by the flows plus both column storages (CSV rounding); rough suite: saturated-fraction closure
  includes the links on specified-head cells at their (fixed) head (X5 convention), and the "rejected above recharge +
  storage" check uses the storage clipped at 0 (columns drier than their reference made 4 false failures);
  test_vz_kinematic K1 creates its work folder (failed on a fresh work folder).
- Manual: all \input chapters compile together; label sec:drained added (ch4_sz_interface) for the rough chapter.

## Results (Raven_m3, -O2, MODFLOW 6.8.1)
- Quick suite (logs/merge3_quick_suite_1.log): 41 of 43 steps PASS on the first run; the two failures were test issues
  (K1 work folder, rough check with negative storage), fixed; all 21 soil-zone steps rerun on the final build PASS
  (logs/merge3_quick_suite_2_soilzone.log; rough 180 runs, 0 failed; was 29 failures on the hooks build).
- Liard T7 (365 d): PASS, 0 unconverged steps, 0 interface non-convergence, max 33 interface updates, max 72 outer iterations.
- CONCEPTUAL byte-identity vs Raven_v3h.exe, Liard_groundwater and Liard_existing_model at 730 days: every CSV identical
  (GWBudget identical, incl. the balance-error column), GWModelSummary.txt differs only by path, linkage time and the
  appended run totals; Raven_errors.txt build date; mfsim.lst/stdout times.
- Manual: pdflatex, bibtex, pdflatex x2: 0 errors, 0 undefined references, 148 pages; rough-terrain results still \tbd.

## Open (beyond the merge)
- Byte-identity steps inside the worker tests (K8, B, C1, M3) SKIP without RAVEN_EXE_REF; RICHARDS results now differ
  from v3h by design (rule (i), rejection term), so v3h is not a valid reference for those.
- LAG summary reports "0 substeps and 0 Newton iterations" (StepLag does not fill vz_step_info substeps).
- Cell-room cap: reconstructed from files_spec 2.7 (no verbatim source).
- Rough-terrain manual table placeholders (\tbd) wait for the final default-suite rerun.
