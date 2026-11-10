# Defects D1-D3 (found by the tutorials work, after phase 13)

Base: phase 13 merged (code 7c3de8e, extra 2f0b372 on soil-zone). Worktrees `wt/p13d/code` (rb-p13d) and `wt/p13d/extra`
(rb-p13d-tests); nothing committed (diffs in `wt/p13d/patches/`). This build: `wt/p13d/Raven_p13d.exe` (md5
`b0f670c6a854ed7646d8697f3538ffec`, with the review fixes); the build before: `wt/p13/Raven_p13.exe` (md5 `7ddfcc28ee4c9b990b06f8b2de52f5f9`);
base Raven 4.15: `audit/CB/Raven_base.exe`.

## D1: Raven's MB error in coupled runs counted the GROUNDWATER store twice

**Cause.** In a coupled HRU `GROUNDWATER` is a pass-through: Raven's processes fill it during a step, the coupling hands
its contents to MODFLOW, and `MassEnergyBalance` (Solvers.cpp, base Raven's "GW reboots each time step") empties it at
the start of the next step. `WatershedStorage.csv` counts the end-of-step store as storage (`Deep Groundwater`), and
`IncrementCumOutflow` (base Raven's branch for model types other than SURFACE, which the coupled type took) also booked
the same contents as outflow in the same step; negative contents were booked as input in `IncrementCumulInput`. So
`MB Error = true error + (G - G0)`, G the `Deep Groundwater` column: the MB error followed the store (Liard 0.52 mm,
the tutorial 2 model up to 7.4 mm, small synthetic models 10-20 mm).

**Fix** (Model.cpp, Model.h, ModelInitialize.cpp; coupled runs only). The store counts as storage at the end of a step
and is booked when the next step empties it: `IncrementCumOutflow` adds the previous step's positive contents to output
and the magnitude of its negative contents to input, then keeps the present contents (`_gwPassOut`, `_gwPassIn`,
area-weighted by `GWPassThrough` over the enabled HRUs, as Raven's storage counts them: a disabled HRU is not
simulated and keeps whatever `GROUNDWATER` the `.rvc` gave it, which is neither storage nor outflow). `CalculateInitialWaterStorage` sets them from the store as read, so a hotstart whose
`.rvc` holds `GROUNDWATER` (the last step's recharge) books it on the first step; a cold start has 0. Ensemble members
re-run `CalculateInitialWaterStorage`. The negative-recharge input of `IncrementCumulInput` is skipped for the coupled
type (now booked one step later). Models without groundwater (SURFACE) and other model types run base Raven's code
unchanged. Exactly: `MB_new = MB_old - (G - G0)`; `Cum. Outflow - Cum. Inputs` changes by `-(G - G0)`; the `Total`
column and every other output are unchanged.

**Result.**

| Run (`patches/d1_mb_numbers.log`, `byteid.log`) | before | after |
|---|---|---|
| Liard, 20 years (Example A) | max 0.52 mm | 0.431061 mm from step 1 to the end, raised on 34 days in six snowmelt seasons (the days with a take from an inflow) to at most 0.437054 mm, back on the day after each run of such days (43 days on which it moves) |
| Liard, 1 year restarted from the first year's `solution.rvc` | 0.060 mm | 0.000000 mm (1e-12) |
| subbasin 52, 1, 2, 4 km cells, 4 km default tolerance (1 year) | 0.456 mm (doc; 2 km rerun: max 0.515, last 0.455) | 0.431061 mm on every step |
| subbasin 52, 2 km, half-day steps | 0.219 mm | 0.215530 mm on every step |
| tutorial 2 finished model, 365 days | max 7.40 mm (= the store) | -0.00017 to 0.00046 mm (reservoir and river terms) |
| synthetic 4-HRU models (byteid) | 10 - 20 mm | 1e-13 mm |
| Example B (existing model), 2 years | (no number documented; 31 days in byteid: 0.459 mm) | max 0.437640 mm (step 1 0.434506, last 0.431061; every value is 0.431061 mm plus half that day's take from an inflow, to the file's 6 digits (reviewer's instrumented build, 300 days, 246 take days); step 1 is itself a take day) |

0.431061 mm (daily) and 0.215530 mm (half-day) are base Raven's first-step values for the Liard model: base Raven 4.15
without groundwater gives the same on its first step, and its MB error with the unbooked `GROUNDWATER` emptying added
back stays at 0.431061-0.431066 mm for the year. Two behaviours of base Raven itself are now in the known issues
(`developers.tex`, guide section 9): this first-step value, and that without `:GroundwaterModel` base Raven empties
`GROUNDWATER` every step without booking it (MB error -7.48 mm after one year of the Liard model without groundwater).

**The remaining rises (not changed).** They come from the river exchange: with `:RiverGeometry` left out the MB error
is 0.431061 mm on every step (300 days, which hold the first rise, 1986-05-24 to 05-26). On those days a river's loss
is larger than the runoff reaching the reach, and `TakeRiverLossFromInflow` takes the rest from the reach's upstream
inflow. The coupling books the whole loss in the step (`river exchange applied to Raven`), but Raven's channel storage
(`SubBasin.cpp`, `dV += 0.5*(_aQinHist[0]+_aQinHist[1])*dt`) takes a change of inflow half in the step and half in the
next, while the upstream reach's outflow term still holds the untaken flow; the difference is half the take of that step,
exactly (the review printed the takes: Liard 20 years, max |MB - 0.5 take/A - 0.431061| = 5.7e-7 mm over 7,305 steps;
Example B the same). Within a run it is gone on the step after a step without a take, and nothing is lost over the run.
Across a hotstart it is not: a run that ends on a take day has booked the whole take, and the second half enters the
restarted run's channel storage in its first step, so the restarted run's MB error is offset by -0.5 x take for the rest
of the run (Liard, restart on 1986-05-24 after a take of 591,414 m3: -0.0011006 mm; flows identical to the continuous
run). This is documented next to the reservoir hotstart offset (`developers.tex`, guide section 9) and in
`accounting.tex`. Booking the taken part the same way (half now, half next step, carried in
`solution.rvc`) would remove it; left as is and documented (`accounting.tex`, Raven's balance), since it is at most
0.006 mm over 20 years and changing it touches the restart file.

**Cold start with `GROUNDWATER` in the `.rvc`.** The first step empties the store before any exchange, so MODFLOW never
receives an initial `GROUNDWATER`; Raven's balance books it as leaving Raven in step 1 (right for Raven), but
`GWBudget.csv` does not show it. `CGroundwaterModel::Initialize` now warns when the `.rvc` holds no hotstart heads
(`:GWHeads`) and an enabled HRU has `GROUNDWATER` != 0 (number of HRUs, volume, what happens, the remedy); a coupled
hotstart (heads present) is not warned about, its store being the last step's recharge, already handed to MODFLOW.
Documented in `accounting.tex` and the guide.

**Tests.** New `tests/watershed_balance.py` (WB1-WB4: CONCEPTUAL, `:SoilZone PHYSICAL`, negative recharge with
`PERC_GR4JEXCH`, a hotstart from a `.rvc` whose `GROUNDWATER` holds 5 mm with 2 mm/d percolation after it; WB5: a disabled
HRU (own subbasin, `:DisableHRUGroup`) given 5 mm of `GROUNDWATER` in the `.rvc`; WB6: a cold start with
`:UniformInitialConditions GROUNDWATER 5.0` must warn, book 5 mm in step 1 and close; each needs the store to hold at
least 1 mm (or below -0.1 mm), limit 1e-6 mm): 6 of 6 with this build, 0 of 6 with the build before (WB5: 29 mm there;
without the disabled-HRU fix the D1 build's error grows by 1.25 mm a step in this set-up, as in the review's 25 mm case);
in `run_all.py` after `tools_check`. Test tools that allowed for the double count now test the balance itself:
`sz_check.raven_mb_mm` (largest |MB error - its value at the start| in mm), `combinations.lake_error_known` (the lake's
own routing error against the MB error), `test_vz_classes` C10 (the restart is checked for Raven's balance too).

**Documents.** `accounting.tex` (Raven's balance: how the store is counted, the Liard numbers, the rises; the audit
check list), `verification.tex` (behaviour table, the sentence after the audit table, the invariance table), the audit
table `tables/run_checks.tex` and `figures/make_tables.py` (Raven's balance column removed: its runs cannot be
regenerated here and the recorded values held the double count; the 20-year and restart values are in the text),
`developers.tex` and the guide (known issues of Raven), the guide's description of the pass-through store,
`examples/Liard_groundwater/README.md` (0.52 mm -> at most 0.437 mm, 0.431 mm on all but a few snowmelt days).

**Byte identity** (`patches/byteid.py`, log `byteid.log`): no-groundwater runs identical to base Raven (reservoir runs
differing only by the known reservoir corrections); coupled runs identical to the build before except
`WatershedStorage.csv`, which differs only in `Cum. Inputs`, `Cum. Outflow` and `MB Error`, by the relation above
(checked row by row); `mf6/` folders identical. The hotstart known issue's numbers are unchanged
(`mt44_restart_offset.log`: +7.3872 / +7.3875 / +14.9244 mm).

## D2: `tools/make_prt.py` released particles twice with a steady-state first period

PRT keeps a PRP period block's setting for the following periods. `BEGIN PERIOD 1 / FIRST` therefore released every
point again at the start of period 2; with `:GWInitialization STEADY_STATE` the flow model has a 1-day steady-state
period followed by Raven's run, so each point was released twice (and backward tracking also ran through the reversed
steady-state period). Now each point is released once: forward at the start of Raven's run (period 2 after a
steady-state first period, else period 1), backward at its end (reversed period 1); the next period gets an empty
`PERIOD` block, which stops releases. The tracking window is Raven's run: endpoints are taken from records within it,
`endpoints.csv` gains `release_time_d`, `travel_time_d` is end minus release, and `end` says whether PRT ended the track
('terminated', status other than 1 active or 10 end of simulation) or the window did. The script stops if the track file
holds other than one release per point at the window's start. Test `budget_file.py` BF7 (steady-state first period,
forward and backward: two flow periods, one release per point at the right time, 8 endpoints, travel time within the run).
The brief's case (tutorial 2 finished model, 365 days, `:WriteGWBudgetFile`, `:HeadSaveFrequency 1`, `make_prt.py out
--backward --run libmf6.so`): 8 particles, one release each at 0 d (backward) or 1 d (forward), travel times 365 d.

**Saved flows checked (review F5).** With `:HeadSaveFrequency` > 1 the flow files hold only some time steps, and the
script died inside PRT (forward: libmf6 ended the process, nothing printed) or FloPy (backward: `KeyError`). It now
compares the saved (time step, period) pairs of `gwf.cbc` and `gwf.hds` with the flow model's time steps before writing
the PRT files and stops with a message naming `:HeadSaveFrequency 1`; the docstring says so. Test `budget_file.py` BF8
(`:HeadSaveFrequency 5`, forward and backward: a message, no traceback, no PRT run).

## D3: `docs/ostrich_example` read the wrong column

Ostrich's `OST_NULL` response counts lines from 0 (the header is line 0) and columns from 1. `Diagnostics.csv` with
`:EvaluationMetrics NASH_SUTCLIFFE RMSE KLING_GUPTA` has columns 1 series, 2 file, 3 NSE, 4 RMSE, 5 KGE; `ostIn.txt` read
column 5 (KGE). Now column 4, with a comment on the counting and the lines (1-4 when the GW_HEAD series are the only
observations; 30-33 with four monitoring wells added to the Liard example, after its 29 streamflow series). Checked on a real `Diagnostics.csv`
(`patches/d3_ostrich_check.py`, log `d3_ostrich_check.log`). `applying.tex` (`OST_NULL 1 4` and the counting) and the
example's README (it cited `../calib.py` and `../calib_log.txt`, which do not exist; it now points to the manual's
synthetic calibration test) are corrected.

## Verification

`run_all.py --quick` (RAVEN_EXE_REF = the phase 13 build; `patches/run_all_quick.log`, `run_all_report.md`,
`run_all_logs/`): 52 passed, 9 failed, 2 not run (the USGS examples, no `mf6examples.zip`). Every check that fails is a
comparison with the reference build that names `WatershedStorage.csv` alone (crs_inputs, dry_start D3, ext_exchanges,
budget_file BF4, soilzone columns_mf6 M3, vz_kinematic K8, vz_lag LB, vz_classes C1, sz_existing X8), the expected D1
change. For the 11 such pairs kept in the scratch folder, `patches/ref_diff_check.py` (log `ref_diff_check.log`)
confirms that only `Cum. Inputs`, `Cum. Outflow` and `MB Error` differ and that `MB_ref - MB_new = G - G0` to round-off.
`watershed_balance` and `budget_file` BF7 pass. The manual builds without warnings, overfull boxes or undefined
references (173 pages; `patches/manual_build.log`).

After the review fixes (F1-F9 of `wt/p13d/review/REVIEW.md`; build md5 `b0f670c6a854ed7646d8697f3538ffec`):
`watershed_balance` 6 of 6; `budget_file` BF1-BF8 pass except BF4's reference comparison (`WatershedStorage.csv`, the D1
change); `run_all_selftest` and `tools_check` pass (`patches/run_all_review_fixes.log`; the report now names
RAVEN_EXE_REF); `byteid.py` again 0 comparisons with differences, the chained no-groundwater cases without and with a
tracer (Nitrate, AGE) and the reservoir cases included; the manual builds cleanly (174 pages) and `docs/manual/main.pdf`
is rebuilt from it. Wording: the river-loss rises are on 34 days (43 with the days they return), the Ostrich lines 30-33
are those of the Liard example with four monitoring wells added.
