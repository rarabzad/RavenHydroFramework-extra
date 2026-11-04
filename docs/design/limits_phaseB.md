# Limitations plan, Phase B (agent p7b)

Plan: `spec/limits/LIMITS_plan.md` (designs F2, F3, F4, stretch F6, F7). Phase A: `limits_phaseA.md`. Branches rb-p7b (code)
and rb-p7b-tests (extra), changes left uncommitted; diffs in `wt/p7b/patches/`. Reference build for the byte-identity
checks: `wt/p7a/Raven_p7a.exe` (Phase A).

## F2 water-table ET with an existing model (L20)

Code check: `_evtCol` is built in `BuildLinks` for both modes, the pointers (`RefreshPointers`) and the flow read-back
(`(HCOF*X-RHS)*_qf` at `TopNode`) are generic, and the PHYSICAL reduction (`GWSoilZoneModel.cpp`, `_evtBase`) works on the
rate in model units. As the plan says.

- `GroundwaterModel.cpp` `ValidateInputs`: the stop "water-table ET (EXTINCTION_DEPTH) is not yet available with an existing
  model" is removed.
- `GWExternal.cpp` `ExtReadSimulation`: new stop when any aquifer profile has EXTINCTION_DEPTH > 0 and the model keeps
  (`:KeepPackages`) an EVT* or UZF* package ("... counted twice. List X in :RavenTakesOver, or set EXTINCTION_DEPTH 0"). It
  lives here, not in `ValidateInputs`, because the package types are known only after the name file is read.
- `ExtWritePackages`: `raven.evt` (SAVE_FLOWS; per `_evtCol` column the top active cell, SURFACE `_extTopRaw`, RATE 0,
  DEPTH `extinction_depth*_extLf`); `ExtEditNameFile`: `EVT6 raven.evt EVT_RAVEN`.
- Rate: `_evtRate = _work/MF6CellArea(ic)*_rf`. For generated models `MF6CellArea==_grid.area` and `_rf==1.0`, exact.
- Deviation: the plan's "skip columns with `_colCHDTop`" is not needed: at set-up an existing model's `_colCHDTop` is all zero
  (it is read from MODFLOW each step), and MODFLOW books no EVT flow on a specified-head cell (hcof = rhs = 0), which the
  read-back reports. Documented in ch4_existing "Current limits".
- `GWModelSummary.txt` (existing models only, only when used): "water-table ET cells : n (EVT_RAVEN, raven.evt)".

## F3 surface-water and reservoir exchange with an existing model (L21)

Code check: the reservoir set-up (`_resNode`, `_resZbot` from `_botm`/`_idomain`) runs in `Initialize` after `ExtBuild`
(which runs `ExtProbe`), so the order is right; `_top`, `_botm` are metres in both modes. The SWX/RES flow read-backs already
multiply by `_qf`. The plan is right that only package writing and the step-code unit factors were missing; one more
factor was needed: the RES read-back compares MODFLOW's actual flow with the specified rate `_resQ`, which is now in model
units, so `spec=_resQ*_qf`.

- Stop removed (`ValidateInputs`: ":SurfaceWaterExchange and :ReservoirExchange (not yet available ...)").
- Step code: SWX stage `zt + sbar/_hf` with `zt = _extTopRaw` (existing) or `_top` (generated), RBOT `zt`, COND `C*_hf/_qf`;
  RES `Q = q/_qf`; generated factors are 1.0 (exact). Using `_extTopRaw` rather than `_top/_hf` keeps the bed exactly equal
  to the value written in the file and to the stage of an empty store.
- `ExtWritePackages`: `raven.swx` (RIV6, SAVE_FLOWS, stage = cond 0 = rbot = `_extTopRaw` at the top active cell) and
  `raven.res` (WEL6, AUTO_FLOW_REDUCE 0.1, SAVE_FLOWS, at `_resNode`); name-file entries `SWX_RAVEN`, `RES_RAVEN`.
- Warning when SWX or RES is used and the model has LAK6/SFR6 packages (the same lake must not be in both).
- Specified-head columns in later periods: as for EVT, MODFLOW books no flow, the read-back reports it; a reservoir gain not
  supplied goes to the existing "reservoir gain not supplied by MODFLOW" path.

Test `tests/existing/ext_exchanges.py` (run_all `ext_exchanges`; quick 31 days, full 120 days):
- the example's wetland HRUs are not coupled (no wetland HRU has an AQUIFER_PROFILE), so the plan's DEPRESSION/WetlandHRUs
  case had no SWX cells; the test uses `:SurfaceWaterExchange SOIL[0] AquiferHRUs LEAKANCE 0.001` (as `fuzz_grids.py`).
- et (md): ET 3.5e6 m3 over 31 days (5.1e6 over 120), at most 3.6% (120 days: 4.9%) of the unmet PET of the coupled HRUs
  on any day (custom outputs PET and AET by HRU, polygon areas from pyproj Geod); identities exact (residual 2e-11); budget
  file RCH/DRN/EVT_RAVEN <= 3.5e-10, list file <= 6e-10.
- keep_evt: stops with the new message.
- all (ET + SWX + RES, md and fs): SWX gross 3.2e6 m3, reservoir seepage 1.9e7 m3 (120 days: 1.7e7, 7.5e7); every audit identity incl. surface
  stores and reservoir sent/awaiting/delivered exact; budget file EVT/SWX/RES_RAVEN <= 4e-10; list file <= 1.4e-6 (fs: the
  list file prints ft3/s to 7 digits, limit 1e-5); fs vs md GWBudget.csv within 6.9e-7 of each column's largest value.
  Deviation from the plan's "same results within 1e-6": the exchange columns (recharge, water-table ET, surface-store and
  reservoir columns) are compared at 1e-6 (120 days: 1.0e-7), every other column at 1e-4: the two models are solved
  separately to the same tolerance, and in the 120-day run one step (1985-12-06) differs by 1.7e-5 in seepage and storage
  (median 5e-8; the first, steady step takes 224 and 350 outer iterations). ch8 reports 4.6e-6 for the earlier existing
  feet/seconds test.
- restart at day 15 from solution.rvc (heads, `:GWReservoirSeepage` in transit): 16 days within 2.8e-7 (full: day 60, 6.8e-8); the audit's river
  identity is not checked on the restarted part (it starts the carried loss at zero, not at the hotstart's).
- plain (RAVEN_EXE_REF): the coupled case without the options: outputs and mf6 folder identical to the reference build.
- Before (p7a build): et and all stop with "not yet available" (3 FAIL lines; the rest not reached).

## F4 budget file, porosity and make_prt.py (L12)

- `:WriteGWBudgetFile` (ParseGWFile.cpp; `SetWriteBudgetFile` adds it to `_genOnly`, so an existing model stops with the
  generated-options message).
- Deviation: instead of adding SAVE_FLOWS to every Raven boundary package, the generated name file gets the model-level
  `SAVE_FLOWS` option (MODFLOW then saves every package's flows), and NPF gets `SAVE_SPECIFIC_DISCHARGE` (already there for
  DISU) and `SAVE_SATURATION`, which PRT (and MODPATH) need. OC: `BUDGET FILEOUT gwf.cbc`, `SAVE BUDGET FREQUENCY n`
  (n = `:HeadSaveFrequency`).
- `mf6/gwf.porosity`: class POROSITY per cell (0.3 in inactive cells), written as the GRIDDATA block of a PRT MIP6 file.
- Summary line "budget file : gwf.cbc every n steps ... (:WriteGWBudgetFile)" only with the option.
- `extra/tools/make_prt.py OUTPUT [--backward] [--points CSV] [--radius f] [--run LIBMF6]`: PRT simulation in
  `OUTPUT/prt/` (DIS/DISV only: PRT has no DISU), release points 8 around each `:Wells` cell (from `gwf.wel`) or from a CSV,
  periods of `sim.tdis` (reversed for backward), FMI on `../mf6/gwf.hds|cbc` or FloPy-reversed copies; `--run` drives the
  library through ctypes (`initialize/update/finalize`, no mf6 executable needed) and writes `endpoints.csv`.
  Findings: PRT reads release points in the grid's local frame (before XORIGIN/YORIGIN/ANGROT), so the script converts with
  FloPy's `get_local_coords` and converts the end points back; `STOP_AT_WEAK_SINK` stopped every particle released in the
  well cell at once, so it is not set.
- Test `tests/budget_file.py` (run_all `budget_file`; quick 10 days, full 60): FLOW-JA-FACE, DATA-SPDIS, DATA-SAT, STO-SS/SY
  and RCH/DRN/RIV/WEL_RAVEN at every step; package totals vs GWBudget.csv <= 3.5e-10; porosity matches the classes (by K) in
  all 8840 active cells; without the option GWBudget.csv and gwf.hds identical, only gwf.nam/npf/oc change and gwf.cbc,
  gwf.porosity are added; without the option identical to the reference build (outputs and mf6 folder); PRT forward and
  backward through the library, 8 particles each, opposite displacements (cosine -1.000); existing model stops. Before: B1
  fails (no gwf.cbc; `:WriteGWBudgetFile` unknown).

## F6 TDIS / MVR OPEN/CLOSE and TS6 on later starts (L24, L25)

- `ExtReadOpenClose(name)`: rows of an OPEN/CLOSE text file of the working copy (path relative to the simulation folder,
  quotes stripped, comments/blank lines dropped).
- `ExtRewriteTDIS`: `OPEN/CLOSE file` rows read (BINARY refused); INTERNAL still refused, message names both alternatives.
  The rewritten TDIS is inline anyway.
- `ExtEditMover`: PERIOD `OPEN/CLOSE file` rows read and written inline (the OPEN/CLOSE line kept as a comment), with the
  same removal of movers from or to taken-over packages; INTERNAL still refused.
- `ExtRenumberPeriods`: `TS6 FILEIN f` collected per kept package; each file shifted once (`ExtShiftTimeSeries`: every time
  in its TIMESERIES block minus `_extOffset*_extTf`). MODFLOW 6.8.1 accepts the negative times (verified by the test), so the
  plan's fallback (one row at 0) is not needed. TAS6 and the old TIMESERIESFILE keyword stay refused (message now names
  TAS6); TS6 with several models in the simulation is refused (their series would not be shifted). Summary line "time series
  : n TS6 files shifted ..." only when it happens.
- edge.py E10 changed from TS6 to TAS6 (TS6 on a later start is valid).
- Test `tests/existing/ext_inputs.py` (run_all `ext_inputs`; quick 50 days / split 23, full 120 / 53): TDIS OPEN/CLOSE twin on
  a start 34 days in: TDIS and GWBudget.csv byte-identical; MVR (WEL_PUMPS -> LAK_1 plus a mover from RCH_MODEL) with the rows
  in an OPEN/CLOSE file: rows inline, the taken-over mover removed, GWBudget.csv identical to the inline twin, identities
  exact; TS6-driven wells restarted between two entries: series shifted (-23, -7.75, 7.5, ...), restarted run within 4.2e-7
  of the continuous one; TAS6 refused. Before: all four fail (TDIS and MVR refused, TS6 refused; TAS6 refused with the older
  wording).
- TS6 shift with an existing ensemble (several members): each member copies the model again, so each shifts its own copy.

## F7 sub-daily restarts of existing models (L23)

- The guard "runs starting after the model's time zero need daily or longer time steps" is removed. The offset already
  includes the time of day and the TDIS rewrite accepts any start on a Raven step. `START_DATE_TIME` gets the time of day
  (`yyyy-mm-ddThh:mm:ss`) when the start is not at midnight (unchanged otherwise).
- Test: `tests/existing/restart_ext.py`, new last block: 6-hour steps, run to day 10.5, restart at 1985-10-11 12:00 from
  solution.rvc: 38 steps (quick, 20 days) compared, max deviation 2.3e-6 (the restart tolerance is 1e-4), audit exact,
  `START_DATE_TIME 1985-10-11T12:00:00`. Before: the restarted run stops with the guard message.
  The deviation is larger than for daily steps (1.4e-7); not investigated further (within tolerance).

## Not done

- F5 (stream supply limit for an existing model's stream package): not started (plan: only if everything else is done).
- W6/W11 test gaps (L41): not started.

## Byte identity

- `wt/p7b/scratch/byteid.py 2` (p7a's script with this worktree's paths; mf6 folders of the two Liard coupled runs added;
  a symlink `work_bi/Liard_groundwater` so the existing-model example finds `../Liard_groundwater/data_forcing`, and a check
  that a compared run actually produced Hydrographs.csv): 15 of 15 identical (no groundwater against base Raven, incl.
  Nitrate/AGE and hotstarts; Liard CONCEPTUAL 180 d and Liard existing model 31 d against p7a, outputs and mf6 folders;
  PHYSICAL+RICHARDS; CONCEPTUAL with unconverged steps). Note: without the symlink the existing-model example does not run
  in that script's work folder, and both builds' failed runs compared as identical; the check added above catches that.
- Every new path runs only with EXTINCTION_DEPTH, `:SurfaceWaterExchange` or `:ReservoirExchange` with `:MF6Simulation`,
  `:WriteGWBudgetFile`, OPEN/CLOSE period data, TS6 on a later start, or a sub-daily later start. Generated-model factors are
  1.0 (`x/1.0`, `x*1.0` exact).

## Test runs

- New tests, quick mode: ext_exchanges 62 checks, 4.5 min; ext_inputs 19 checks (with the mover case), 2.5 min;
  budget_file 24 checks, 15 s; restart_ext with the sub-daily block 8 min (its daily splits run 200 days in both modes).
- Full mode: ext_exchanges 77 checks ALL PASSED (7 min); ext_inputs ALL PASSED (4 min).
- Before (p7a build): ext_exchanges, ext_inputs, budget_file and the sub-daily restart fail as listed above.
- byteid.py: 15 of 15 identical. LaTeX: latexmk on a copy of docs/manual, no errors or undefined references.
- `run_all.py --quick` (RAVEN_EXE_REF = p7a): 51 passed, 0 failed, 2 not run (USGS examples, no zip), 3 SKIP lines
  (W4, W6, W11 in soilzone_confined_wet, as before). Run in three parts: the first (gridtest .. lake, 16 steps, all PASS)
  was stopped by the session's 30-minute limit for background commands inside liard_grids, the rest ran with `--only`
  (14 steps, 41 min; 23 soil-zone steps, 10 min). Logs: `wt/p7b/patches/run_all_quick_part*.txt`, report
  `run_all_report_quick.md` (it lists the steps of the two `--only` parts).
