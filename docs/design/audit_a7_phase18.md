# Audit A7, phase 18: code and tests

Phase 18 of the round-7 audit (issue list: `spec/audit_A7/AUDIT_A7_issues_and_phases.md`; brief:
`spec/audit_A7/phase18_19_brief.md`): CB7-1, CB7-2, IB7-1, IB7-2, IB7-3, IB7-4, IB7-5, MT7-5 and the test part of MT7-6.
Reference build: the release build `wt/rel16_Raven.exe` (sources d47888a); this build: `wt/p18/Raven_p18.exe`; base Raven:
`audit/CB/Raven_base.exe`. Worktrees `wt/p18/code` and `wt/p18/extra`; nothing is committed (patches, logs and the review
brief in `wt/p18/patches/`).

Each behaviour change has a regression test that fails with the reference build (the C++ unit tests: compiled from the
reference sources) and passes with this one. MT7-5 and MT7-6 change test scripts only.

## CB7-1: EnKF's solution_EnKF.rvc without the groundwater state

**Before.** `CEnKFEnsemble::FinishEnsembleRun` writes each member's `solution_EnKF.rvc` (ENKF_SPINUP and ENKF_CLOSED_LOOP)
after the last member, when the groundwater model of every member is closed (`CloseOutputs` finalizes MODFLOW and sets
`_active` false). `WriteMajorOutput` wrote the groundwater blocks and the 17 digits of a coupled run only while the model
was active, so the file held no `:GW*` block and 5-decimal states. Closed-loop and forecast members started MODFLOW from the
initial heads, the initial GROUNDWATER store was warned about as never reaching MODFLOW, and the river take, carries,
stores in transit and soil-zone columns were dropped. In the auditor's case the day-1 heads of the closed loop were those
of a cold start (0.48 m below a restart from the spin-up's end in the test case below).

**Change.**
- `GroundwaterModel.cpp/.h`: `_closed` (set by `CloseOutputs` when the model ran, cleared by `Initialize`) and
  `_hotRvcFile` (the `.rvc` being read, set by `ParseInitialConditions` in a coupled run). `WriteHotstart` of a closed model
  writes the groundwater blocks of that `.rvc` unchanged: every block from its `:GW...` line to its `:EndGW...` line.
  `FinishEnsembleRun` has just read the member's `solution.rvc`, written at the end of the member's run, so the blocks are
  the state as it stood then, at full precision (the same bytes). Text is copied rather than the hotstart maps rewritten,
  so the file cannot drift from `WriteHotstart`'s format.
- `StandardOutput.cpp`: the 17-digit HRU and basin states apply whenever `:ModelType` is coupled (or the model is active);
  `WriteHotstart` is called whenever there is a groundwater model and decides itself (nothing without one).
- A run without groundwater is unchanged (its model never becomes active, so it is never closed): byteid's EnKF spin-up
  without groundwater gives every member's files, `solution_EnKF.rvc` included, byte-identical to base Raven's.
- The EnKF update changes only Raven's HRU states; the assimilated states are not fed back into the aquifer (as before).

**Test.** `soilzone/test_inputs.py` I17c: a 2-member ENKF_SPINUP (4 HRUs, CONCEPTUAL, SOIL[0] assimilated), then
ENKF_CLOSED_LOOP and ENKF_FORECAST from its `solution_EnKF.rvc` files. Reference: no `:GW*` block, states at 5 decimals,
the "MODFLOW never receives" warning, day-1 heads 0.48 m from a single run restarted from the member's `solution.rvc` with
the EnKF states. This build: the blocks equal the member's `solution.rvc`'s, the non-assimilated states equal it to 17
digits, no warning, day-1 heads equal (0 m).

## CB7-2: restart with a longer :TimeStep after takes from a reach's inflow

**Before.** When the inflow history changes length with the step, Raven's `CSubBasin::SetQinHist` averages the last
fac = dt_new/dt_old inflows (copies them when the length stays, repeats them when the step shrinks). The start-of-step
inflow of the restarted run is then lowered by the average of the last fac takes' rates, while `InitRiverTakes` booked
the last take's rate only: Raven's MB error was half the difference of the last two takes (auditor: -0.2335 mm,
ROUTE_DIFFUSIVE_WAVE, 0.5 then 1 d).

**Change.** `GroundwaterModel.cpp/.h`, `ParseInitialConditionFile.cpp`:
- `_sbInHist`: per subbasin, the takes from the inflow as rates (take / step, m3/d) over the length of Raven's inflow
  history, latest first; it moves on one step in `ApplyRiverExchange` as Raven's history does in `UpdateInflow`, and
  `TakeRiverLossFromInflow` adds the step's take to its first entry.
- `solution.rvc`: `:GWRiverInflowTakes` (subbasin ID, then the rates, 17 digits; written whenever an entry is non-zero,
  so a missing block with a take from the inflow means a file of an earlier build).
- The parser records, for each reach's `:Qin` line, how `SetQinHist` rescales it (copied, repeated n times, averaged over
  n steps; the same tests on the history length and on the `:TimeStep` line Raven uses). `InitRiverTakes` rescales the
  hotstart's take history the same way: when Raven rescales (repeats or averages), only the entries below the
  lateral-inflow history length (`GetLatHistorySize`), as `SetQinHist` loops, and the entries after them are 0 (Raven
  leaves its own there, which hold no take). A file without the block but with a take from the inflow (written by the
  release build) is read as the reference read it: the earlier takes equal to the last one, no adjustment. It books the first
  step's inflow part as half the new step times the rescaled first entry; the rest of half the last take is carried
  (`_rivTakeBookAdj` adds the difference to `_rivTakePrevBook` in the first step). Where Raven does not average, the
  rescaled first entry is the last take's rate and the books are as before.
- A chain of restarts stays exact: the rescaled history is kept, so a part shorter than the next part's averaging window
  (0.25 d, then 0.5 d for one step, then 1 d) passes the earlier takes on; with a one-step part between two step changes
  (0.1, 0.2, 1 d and 1, 0.2, 1 d) only the entries Raven itself rescales hold takes.
- Base Raven's `SetQinHist` reads past the end of the `.rvc` history when the step grows (its loop runs over the
  lateral-inflow history length): the runs without the river carry that error (up to 2.2 mm in WB14's one-step chains).
  It is left as it is (byte identity with base Raven) and listed among Raven's known issues in developers.tex.
- Documents: accounting.tex (the limitation sentence replaced by the mechanism), appendix (the block), the user guide's
  list of blocks, developers.tex.

**Test.** `watershed_balance.py` WB14: the WB13 reach with ROUTE_DIFFUSIVE_WAVE restarted after day 3 (takes from the
inflow, unequal): 0.5 then 1 d, 0.25 then 1 d, and 0.25, 0.5 (half a day), 1 d; restarted after day 4: 0.1, 0.2 (one
step), 1 d and 1, 0.2 (one step), 1 d; with the runs without the river. The MB criterion is the river run's MB error
beyond the run's without the river, step by step (1e-6 mm), since the latter carry base Raven's own rescaling error.
Reference: MB 0.017, 0.024 and 0.21 mm on the first three, leakage minus (lower outflow + lower channel storage) 2.8,
-3.8 and -33.6 m3. This build: MB beyond the run without the river 2.8e-14 to 5.7e-14 mm, the same balance within 0.1 m3
(the outflow file's digits); the one-step chains gave 0.93 and 1.0 mm before the rescaling was limited to the
lateral-inflow history length (review R18-1). With RAVEN_EXE_REF, WB14 also restarts (0.5 then 1 d) from a
`solution.rvc` the reference build wrote: MB 0.01742 mm, equal to the reference build's own restart (before the fallback,
2.56 mm in the reviewer's case, R18-2). The criterion is the
leakage against the lower outflow plus the lower channel storage at the end, not the lower outflow alone as in WB13: the
restart re-routes Raven's averaged inflow history with the new unit hydrograph, which leaves another part of the takes in
the channel at the end (the same in base Raven without groundwater). The auditor's `tsrst.py` case: MB -0.2335 mm ->
5.7e-14 mm; ROUTE_HYDROLOGIC, ROUTE_PLUG_FLOW, ROUTE_MUSKINGUM and the shrinking step (0.5 then 0.25) stay at round-off.

## IB7-1: LCC with its origin at the pole opposite the cone

**Change.** `GWGeometry.cpp`: `_rho0 = 0` when |lat0| = 90 degrees (within 1e-10 rad), as PROJ sets it; both hemispheres
are finite and equal to PROJ. ALBERS already agreed.

**Test.** `geomtest_check.py`: ten conic cases against pyproj (forward within 1 mm, inverse round trip 1e-9 degrees),
among them LCC 50 60 -90, LCC -50 -60 90, LCC 50 60 90, LCC -50 -60 -90 and ALBERS at both poles. Reference sources: LCC
50 60 -90 off by 2.3e20 m, LCC -50 -60 90 refused (1e9 in the report). This build: all within 5e-7 m.

## IB7-2: US-foot band units written as one word; unit texts without letters

**Change.** `GWGeoTIFF.cpp` (UNITTYPE): a word that begins with ft, feet or foot (ftus, ftint, footus), or that is ft,
feet or foot after a qualifier (us, s, m, i, int, intl, ind, uk, br: usft, sft, usfeet), is feet. Also refused as other
units: mile(s), fathom(s), chain(s), kmi. PROJ's short ids ch, mi, fath, link(s) and in count as another unit only as the
first word, or the second after us, ind, int or intl (us-in, us-ch), and only without a metre word: "Elevation in m
(CH1903+)", "Elevation (m) see link" and "height in metres, mi" are metres, "hauteur à mi-marée" an unknown unit. A
non-empty text without a word (`'`, `?`, `-`) gives the unknown-unit warning instead of silent metres; an empty text is no
unit. A word glued to a digit or a non-ASCII byte (`µm`, `10m`), or after a number (`0.1 m`, a scaled unit), is no metre
word (unknown unit, warning). Every case of the IB6-4 test is unchanged
(`in metres`, `in m`, `m (Admiralty datum)` metres; `in`, `in feet` refused).

**Test.** `geotiff/geotiff_check.py`: ftUS, usft, us-ft, USfeet, foot_us, Foot_US, foot_survey_us, NAVD88 ftUS, sft,
ind-ft, fathom, us-in, us-ch, mi and link stop; `'`, `?`, `µm`, `0.1 m` and "hauteur à mi-marée" warn; metre, "m above
NAVD88", "Elevation in m (CH1903+)", "elevation [m] CH", "Höhe in m ü. M. (CH)", "Elevation (m) see link" and "height in
metres, mi" read as metres. Reference sources: ftUS, usft,
USfeet, NAVD88 ftUS, sft and fathom only warn, `'`, `?` and `µm` are silent metres (9 failures).

## IB7-3: the grid-size stop names what decides the grid's size

**Change.** `GWGrid.cpp/.h`: `CGWGrid::CellLimitMessage(what, n, limit, file)` words the stop for the cell size, the
refinement (regular grid), an HRU mesh (its seeds; with refinement: "the :GridRefinement sizes give an HRU mesh of N
seeds"), an imported grid (names the file) and an existing model ("the existing model has N cells per layer, more than the
5000000 Raven couples"); `GroundwaterModel.cpp` uses it at both stops. building.tex and existing_model.tex state the limit
for imported grids and existing models; the appendix lists the printed messages.

**Test.** `gridtest.cpp`: each kind's message names its remedy and only the cell-size kinds mention `:GridCellSize`
(a grid above the limit costs minutes and a gigabyte to reach, so the wording is tested at the function). The reference
sources have no such function (the test does not compile).

## IB7-4: GeoJSON coordinates that are not numbers

**Change.** `GWGeometry.cpp`:
- The JSON number branch accepts only JSON's grammar (`-?(0|[1-9][0-9]*)(.[0-9]+)?([eE][+-]?[0-9]+)?`), so `NaN`,
  `Infinity`, hexadecimal and leading zeros make the file invalid JSON. The message names the line, the column and the
  text of the token where parsing stopped, and says that NaN, Infinity, hexadecimal and leading zeros are not JSON
  (Python's `json.dump` writes `NaN`).
- Polygon rings and lines read each coordinate through `JCoords::Pair`: a string, `null`, `true`/`false` or a number too
  large for a double stops with "GeoJSON file F, feature n (ID i), ring r (outline|hole), vertex k: its x (longitude) is
  ..., not a number".
- A feature without `"properties"` is read when no ID field is needed (boundary and refinement files) and refused,
  naming the feature, when one is (before, the polygon reader skipped it and the line reader gave it ID -1).

**Test.** `geomtest_check.py`: 14 GeoJSON cases (string, null, true, NaN, Infinity, 0x10, -0122.9, 1e999, -1.229E2,
features without properties with and without an ID field, lines). Reference sources: 12 of the 14 fail (the string and
null are read as 0, NaN/Infinity/hex accepted, features without properties skipped).

## IB7-5: a repeated ESRI ASCII header key

**Change.** `GWGeometry.cpp`: a header key given twice, or `xllcorner` with `xllcenter` (or the `y` pair), stops the run
naming the keys. building.tex and the appendix say so.

**Test.** `geotiff/geotiff_check.py`: `dupcs.asc` (cellsize 1, then 2) and `both.asc` (xllcenter, then xllcorner) are
refused; the reference reads both (last value wins).

## MT7-5 and MT7-6 (tests)

- `watershed_balance.py` `no_groundwater`: the AQUIFER_PROFILE column is found from the `:Attributes` line (it was the
  SOIL_PROFILE column); the function asserts that some HRU was changed. WB12's runs without groundwater now have HRUs
  without an aquifer profile, as its docstring says, and still equal their members exactly.
- WB12's TVD skip prints through `testconfig.skip` ("SKIP WB12 ...: the single run stops: ..."), which run_all counts.

## Left for phase 19

- verification.tex's WB12/WB13 limits (MT7-6 docs). Phase 18 adds a WB14 sentence after WB13's in the same paragraph and
  changes "WB7--WB13" to "WB7--WB14": the two edits meet there.
- developers.tex's EnKF row (MT7-7); phase 18 changes only the `StandardOutput.cpp` and `ParseInitialConditionFile.cpp`
  rows.
- The workshops are regenerated with this build in phase 19.

## Review responses (review/REVIEW.md)

- R18-1: the take history is rescaled only over the lateral-inflow history length when Raven repeats or averages; WB14
  gains the reviewer's two one-step chains.
- R18-2: `:GWRiverInflowTakes` is written whenever an entry is non-zero; a file without it falls back to the reference's
  assumption; WB14 restarts from a reference-build file.
- R18-3: PROJ's short ids count only first, after a qualifier, and without a metre word; the reviewer's metre texts are
  test cases.
- R18-4: us-in (and in after us, ind, int, intl) is inches; a number before the metre word gives the unknown-unit warning.
- R18-5: invalid JSON names the line and column of the token.
- Base Raven's `SetQinHist` over-read: one item in developers.tex's known issues of Raven itself.
