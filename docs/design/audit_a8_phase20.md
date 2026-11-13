# Audit A8, phase 20: code and tests

Phase 20 of the round-8 audit (issue list: `spec/audit_A8/AUDIT_A8_issues_and_phases.md`; brief:
`spec/audit_A8/phase20_21_brief.md`): IB8-1, IB8-2, IB8-3, IB8-4, IB8-5, IB8-6, CB8-1, the SV8-1 warning, WS8-1 and the
`SetQinHist` check. Reference build: `wt/rel18_Raven.exe` (sources 78d6c0b); this build: `wt/p20/Raven_p20.exe`; base
Raven: `audit/CB/Raven_base.exe`. Worktrees `wt/p20/code` and `wt/p20/extra`; nothing is committed (patches, logs, the
byte-identity script and the review brief in `wt/p20/patches/`).

Each behaviour change has a regression test that fails with the reference build (the C++ harnesses: compiled from the
reference sources) and passes with this one.

## IB8-1: a river line whose subbasin ID is not in the model

**Before.** `BuildRivers` skipped a line only when `GetSubBasinIndex` returned `DOESNT_EXIST` (-1); for an unknown ID it
returns `INDEX_NOT_FOUND` (-2), so `GetSubBasin(-2)` read outside the subbasin array: a segmentation fault before the
run started.

**Change.** `GroundwaterModel.cpp`: with an ID field, every line whose ID names no subbasin (any negative index) is left
out; one warning gives their number and IDs (at most 20); when no line is left the run stops, naming the ID field and the
IDs. Without an ID field the lines take the subbasin of the cell's dominant HRU, as before. Null or non-integer IDs stop
in the reader (IB8-5).

**Test.** `input_checks.py` N25 (the routed strip of combinations.py with a second line of SUBID 99: runs, the same 8
river cells as the first line alone, the warning names ID 99) and N26 (the only line has SUBID 99: stops, "no line of
the river file ..."). Reference: both end in a segmentation fault (return code -11).

## IB8-2: an existing model's input text read as MODFLOW 6 reads it

**MODFLOW 6's rules** (6.8.1 sources, `src/Utilities/InputOutput.f90`): `u9rdcom` skips blank lines and lines whose
first character other than a blank, comma or tab is `#` or `!`, or that begin with `//`; `urword` separates words at
blanks, commas and tabs, a quoted word ('...' or "...") holds them, and a real is read by Fortran list-directed input:
an exponent written with E, D or Q (either case, also without digits: `1.0e`) or with a sign alone (`1.0+1`), `5.`,
`.5`, a slash ending the value (`5.0/`) and a repeat count (`2*5.0` is 5.0); a period number is the whole part of such a
value (`2.0`, `2e0`, `2/`, `1*2`, `2.5` are period 2). All of these were checked by running mf6 6.8.1 (review R3).
Where MODFLOW reads a fixed number of words it ignores the rest of a line; where it reads every word (AUXILIARY names,
a name-file PACKAGES row) a word beginning with `#` or `!` is data (review R1).

**Before.** `Words()` cut each line at the first `#` or `!` anywhere, split only at blanks, and kept `//` lines;
the TDIS period lengths and the TS6 times were read with `atof`: `50.0D-1` became 50 (periods merged without a message),
`0.5D1` 0.5 and a `//` line an extra period of 0 d (misleading stops), `1.0x` silently 1. NPER was not compared with
the rows.

**Change.** `GWExternal.cpp`, used by every reading of the model's files (simulation and name files, TDIS, STO, the
period blocks of kept packages, TS6 files, the mover, the stream package's options):
- `Words()` follows u9rdcom/urword: comment lines (`#`, `!`, `//`), blanks, commas and tabs as separators, quoted words
  without their quotes; a word that begins with `#` or `!` ends the line where MODFLOW reads a fixed number of words,
  and is data on AUXILIARY lines and name-file PACKAGES rows (`Words(line, true)`), as for MODFLOW. The number of the
  stream package's auxiliary variables is checked against MODFLOW's memory (`NAUX`), the stride of their values.
- `MF6Real()` reads a real as Fortran does (E/D/Q exponents, sign-only exponents), finite values only; `MF6Int()` reads a
  period number. TDIS period lengths (inline and OPEN/CLOSE rows), TS6 times and `BEGIN PERIOD n` use them; a token that is
  not a number stops, naming the model's own file (not the working copy) and the line.
- NPER is compared with the PERIODDATA rows (MODFLOW 6 reads exactly NPER rows; the rewritten TDIS used to hide a
  mismatch).

**Test.** `input_checks.py` E1 (the existing-model example's TDIS with `10.0D-1`, `0.31d2`, a `//` row, a `!` row and
commas: the run completes and the working copy holds periods 1 d and DAYS-1 d), E2 (`1.0x` stops, naming the value),
E3 (NPER 25 with 24 rows stops). Reference: E1 does not complete (10.0D-1 is read as 10 d and 0.31d2 as 0.31 d), and E2 and E3 run without a message.

## IB8-3 and IB8-4: band units

**Before.** A metre word whose previous non-blank character was a digit counted as "after a number" (`CH1903 m` stopped
as chains, `NAVD88 m` warned); feet written in camel case or as one compound word (`SurveyFeet`, `USSurveyFoot`,
`esriSRUnit_SurveyFoot`, `DecimalFeet`) and `fasl` only warned.

**Change.** `GWGeoTIFF.cpp`: a metre word is "after a number" only when it starts a blank-separated token and the token
before it is a number as a whole; a lower-case letter followed by a capital starts a new word (`Survey|Feet`, `m|ASL`);
any word that ends in `feet` or `foot` is feet; `fasl` is feet; `micromet...` and `nanomet...` are other units.

**Test.** `geotiff/geotiff_check.py`: `CH1903 m`, `CH1903 metres`, `in CH1903 m`, `NAVD88 m`, `EGM96 m` and `mASL` are
metres; `SurveyFeet`, `InternationalFeet`, `USSurveyFoot`, `esriSRUnit_SurveyFoot`, `decimalfeet`, `fasl` and `Micrometer`
stop. Reference sources: the 13 cases fail; every earlier case is unchanged.

## IB8-5 and IB8-6: GeoJSON

**Change.** `GWGeometry.cpp`:
- IDs (`FeatureID`): a whole number (`7`, `7.0`) or a string holding one, with blanks around it or a decimal point
  followed by zeros (`"7"`, `" 7 "`, `"7.0"`, review note); `null`, `true`/`false`, `"7.5"`,
  `"7abc"`, `""`, `2.6` stop, naming the file, the feature and the value (polygons used to skip null/bool features and
  round or `atoll` the rest; lines turned null into 0).
- Nesting: a position must be an array of at least two numbers, and a ring, a polygon, a line or a MultiPolygon /
  MultiLineString member an array; anything else stops, naming the feature, ring and vertex (a Polygon nested one level
  too shallow was read as nothing; a vertex `[1]` dropped the ring, or the vertex of a line).
- `NaN`, `Infinity` and `-Infinity` are read as numbers (Python's json, geopandas and GDAL with
  WRITE_NON_FINITE_VALUES write them); a coordinate must still be finite ("its x (longitude) is NaN, not a finite
  number"); `\uXXXX` escapes, with surrogate pairs, are decoded to UTF-8 (they were `?`), so `"Höhe_ID"` matches;
  text after the root object is invalid JSON; the hint about hexadecimal numbers and leading zeros is given only where
  parsing stopped after such a 0, the hint about non-finite spellings only for a token like `nan`/`inf`.

**Test.** `geomtest_check.py`: 17 new or changed cases (IDs null/true/"7abc"/2.6/"" refused, "7" and 7.0 read; a line
with ID null; the shallow Polygon, the vertex `[1]` in a polygon and a line, a LineString whose coordinates are a number;
NaN/Infinity attributes read; the escaped field name; text after the root; a truncated file without the hint; NaN and
Infinity coordinates refused as not finite). Reference sources: all 17 fail.

## CB8-1: the river loss a run starts with

**Before.** The carry a run starts with (`:GWRiverLossCarry`, and after a restart with another `:TimeStep` the rest of
the last take plus the averaging adjustment) is taken in step 1 and booked in "river exchange applied to Raven", but no
output gave it, so `tools_audit.py`'s river identity of a restarted run was off by it on step 1 (0.097 in the auditor's
case).

**Change.** `GroundwaterModel.cpp` (`WriteSummary`, after `BuildRivers`/`InitRiverTakes`): a line
"river loss carried    : V m3 at the start (...)" in `GWModelSummary.txt` whenever the start carry is not 0 (17 digits,
as the recharge-delay line). `examples/Liard_groundwater/tools_audit.py` takes it as step 1's previous carry (0 without
the line). The workshop copies of `tools_audit.py` are written by `build_tutorials.py` (phase 21 regenerates them).
Documents: accounting.tex (the river identity from the first step), inputs_outputs.tex (the summary line).

**Test.** `watershed_balance.py` WB13 and WB14: `tools_audit.py`'s river identity of every part, the restarted parts
included, within 1e-8. Reference: 0.10 to 2.0 in the 13 restarted cases; this build: 4.3e-11 to 4.0e-10. (WB14's
reference-file restart now prints SKIP when the reference build itself writes `:GWRiverInflowTakes`: rel18 does, so the
check needs rel16 as RAVEN_EXE_REF; with it the check passes, 0.01742 mm as before.)

## SV8-1 (warning) and WS8-1

**SV8-1.** `GWVadoseModel.cpp`: the release-cap warning no longer asks "(Sy below the drainable porosity?)". It says that
the column held more water above equilibrium than MODFLOW stores for the rise, releases at most Sy dh per step (or the
room left in the top cell) and the rest in the next steps, and that this is expected while water is in transit (the LAG
store, a wetting front); only when a column material has Sy below half its drainable porosity (`_vzSyLow`, from the
start-up check of `VZSetup`) does it add that the specific yield adds to it. The phrase "releases at most Sy dh per step"
is kept, which `build_tutorials.py` greps. The code comment that the cap "does not apply" with consistent parameters is
corrected. The manual's "never binds" is phase 21's.
**Test.** `test_vz_lag.py` L8: the auditor's set-up (one flat HRU, LAG, drainable porosity 0.078, Sy 0.078, 40 mm/d for
10 days from 6 m deep) warns with "expected while water is in transit ... (the LAG store)" and no Sy clause; L6's run
(Sy 0.02) adds the Sy clause. Reference: both give "(Sy below the drainable porosity?)".

**WS8-1.** `GWSoilZoneModel.cpp`: the factor-2 warning gives the ratio range of the links it counts (one value when they
are equal); `GWModelSummary.txt` keeps the range of all links.
**Test.** `test_inputs.py` I24: HRU 1 over SAND (ratio 1), HRU 2 over TILL (Sy 0.05, ratio 0.25): "on 4 links ...
(ratio 0.250000)", summary 0.25 to 1. Reference: "(ratio 0.250000 to 1.000000)".

## SetQinHist: ASan

`CSubBasin::SetQinHist` (base Raven, unchanged since e7e2868) rescales a restart's inflow history to another step with
loops over `_nQlatHist`, the lateral-inflow history length; `_aQinHist` holds `_nQinHist+1` entries. Case
(`patches/qinhist.py`): WB14's two 30-km reaches with ROUTE_DIFFUSIVE_WAVE and ROUTE_TRI_CONVOLUTION, TIME_CONC 10 d,
varying inflow; 3 days at 0.5 d, then 1 d from `solution.rvc` (`.rvc` histories: inflow 5, lateral 23; the 1-d run:
`_nQinHist` 4, `_nQlatHist` 13). ASan builds (`-O1 -g -fsanitize=address -fsanitize-recover=address`) of the base sources
and of this phase's sources (logs in `patches/logs/asan_*.txt`):
- **Base Raven, no groundwater: yes, it writes past the end.** `WRITE of size 8 ... 0 bytes after 40-byte region`
  allocated in `GenerateRoutingHydrograph` (`_aQinHist`), at `SubBasin.cpp:1512` (`_aQinHist[i]=0.0`) and `:1514`
  (`+=`): entries 5 to 12 of a 5-entry array. It also reads past the end of the `.rvc` arrays (`SetQinHist:1514`,
  `SetQlatHist:1465`), and the overwritten heap makes two later `delete[]` fail ("bad-free"). The normal base build
  (`Raven_base.exe`) ends this restart in a segmentation fault (in `CModel::ApplyProcess`).
- **Coupled run (this phase's sources without the guard, and rel18):** the same writes; rel18 runs the WB15 restart to
  the end with MB errors of 2.6e238 mm, and the qinhist.py case ends in a segmentation fault.

**Guard (applied in coupled runs only).** `SetQinHist(N, aQi, tstep_in, tstep, bounded=false)`: with `bounded` the
rescaling loops stop at `min(_nQlatHist, _nQinHist+1)`, the array's size. `ParseInitialConditionFile.cpp` sets it for
the `:Qin` line of a coupled run (`MODELTYPE_COUPLED` with a groundwater model); every other caller (EnKF, assimilation,
FEWS, ensemble restore) and every run without groundwater pass the default and run base Raven's code unchanged.
Justification:
- Every entry inside the array is computed exactly as before (same loop, same arithmetic, same order); only the writes
  past the end are dropped, so a coupled run that did not overflow is bit for bit the reference's (byte identity B
  below), and one that did no longer overwrites other data.
- The entries Raven uses are those below `_nQinHist` (UpdateInflow shifts `0.._nQinHist-1`), so nothing that routing
  reads changes.
- `InitRiverTakes` mirrors the rescaling of the take history only over `_sbInHist`, sized `_nQinHist`: it never
  depended on the entries past the end, so the river books are unchanged (WB14 unchanged; WB15 exact).
- With `bounded`, the entries past the end of the `.rvc` inflow history (k >= N) are also read as 0 (review R5): they
  were undefined memory (the reviewer saw 1e+88 and 1e+199 land in entries below `_nQinHist`), and 0 is what
  `InitRiverTakes` assumes for the take history there, so routing and the river books agree by construction. Without
  groundwater SetQinHist's reads are base Raven's. SetQlatHist's over-read of the `.rvc` lateral-inflow history remains
  in every run (base Raven; developers.tex).
- Without groundwater the write is left as base Raven has it, as the brief requires; developers.tex lists it among
  Raven's known issues for the Raven developers (the fix there would be the same bound, plus reads limited to N).
ASan with the guard (`patches/logs/asan_coupled_restart_guard.txt`, coupled restarts 0.5 then 1 d and 0.25 then 1 d):
SetQinHist neither reads nor writes past an array; the only report is SetQlatHist's read; both complete.

**Test.** `watershed_balance.py` WB15: the case above as a coupled run with the river (and without, for the MB
comparison): both restarts complete, `tools_audit.py`'s river identity 2.4e-13, MB beyond the run without the river
2.8e-14 mm (Raven's own 1.9 mm). Reference: MB 2.6e238 mm.

## Other places that read an existing model's text

All of them go through `Words()` (simulation file, name file, TDIS, STO period blocks, kept packages' period blocks,
TS6 files, the mover, the stream package's AUXILIARY option, the probe of NEWTON); numbers are read only in TDIS
(period lengths, NPER), TS6 (times) and `BEGIN PERIOD n`, all now as MODFLOW reads them. Raven's own files (`.rvg`,
`:OverlapWeights`, `.rvc`) keep Raven's strict readers.

## Byte identity (`patches/byteid.py`, log `patches/logs/byteid.log`)

A, without groundwater, against base Raven: the benchmark models Alouette (16 files), Irondequoit (3), Salmon_HBV (5),
Salmon_GR4J (5), Revelstoke (16) and LaJoie (16) are identical (Nith stops in both builds before writing outputs); the
qinhist.py restart without groundwater is identical in both parts (part 2 ends in base Raven's segmentation fault in
both builds: the guard is not applied without groundwater).

B, coupled, against rel18: combinations.py's CONCEPTUAL case with every exchange (36 files), its existing-model twin
(36), PHYSICAL + RICHARDS with 3 classes (35), PHYSICAL + LAG with half-day steps (33), the existing-model example for 2
days (37) and the first part of the coupled qinhist.py restart (28) are identical apart from the folder and timing lines.
The restarted part differs only because rel18 overwrites memory there and ends in a segmentation fault, while this
build completes it. The new summary line and the changed warnings do not occur in these cases. They do occur in the
tests above.

## Tests

`run_all.py --quick` (`patches/logs/run_all_quick.log`, report `work_new/run_all_report.md`): 62 steps pass, 2 are not
run (the USGS examples are not available), and 1 fails: `tutorials`. The workshops hold the outputs of the reference
build and must be regenerated with this build. That is phase 21. The failure lists only the workshop copies of
`tools_audit.py` and Workshop 3's two changed warnings (`t3_warn_lag.txt`, `t3_warnings.txt`). `build_tutorials.py`
reads the factor-2 warning's ratio with a pattern that also takes the single ratio this build prints (`t3:syratio`).
RAVEN_EXE_REF is rel18 in `env_new.sh`, so WB14's reference-file restart prints SKIP. With rel16 it passes.

## Left for phase 21

- Regenerating the workshops with this build. The tutorials check then passes again.
- exchanges.tex's "never binds" (SV8-1 manual); Workshop 3's text about the release-cap warning, and the regenerated
  `t3_warnings.txt` / `t3_warn_lag.txt` (both warnings changed text).
- The workshop copies of `tools_audit.py` (regenerated by build_tutorials.py).
- verification.tex's list of the WB tests (WB15, the tools_audit identity in WB13/WB14).
- developers.tex: phase 20 adds one sentence to the SetQinHist known issue and the SubBasin row; CB8-2 edits the same
  paragraph.

## Review responses (review/REVIEW.md)

- R1: AUXILIARY lines and name-file PACKAGES rows read every word (a word beginning with `#` or `!` is data there, as
  for MODFLOW); the auxiliary count is checked against MODFLOW's `NAUX` of the stream package; existing_model.tex
  corrected. Test `input_checks.py` E6 (the reviewer's `auxiliary SUBBASIN # id` with two more values per river row):
  GWBudget.csv and Hydrographs.csv identical to the unmodified model's; rel18 and the first phase-20 build stop ("subbasin
  ID 0").
- R2: a token before a metre word is a number when it holds a digit and no letter other than an exponent `e`/`E` after a
  digit or a leading factor `x` (after `([{=*:`). `[0.1 m]`, `(0.1 m)`, `1,5 m`, `1/1000 m`, `x0.1 m` and `1:1000 m` warn
  again; `CH1903 m`, `NAVD88 m`, `EGM2008 m` stay metres (geotiff_check.py; the reviewer's 87 texts: none newly refused,
  the scaled ones warn).
- R3: MF6Real/MF6Int as in the table of R3, each form checked with the mf6 6.8.1 program: an exponent letter without
  digits is exponent 0 (a sign without digits stays an error), a slash ends the value, `r*c` is `c` (also `0*5`, which
  mf6 reads; `2*` without a value is refused: mf6 reads garbage), a period number is the whole part of the value. Test
  `input_checks.py` E4 (`2*1.0`, `31.0/`, `30.0e`: rel18 reads 2*1.0 as 2 d) and E5 (`BEGIN period 2.0`, `3/` with a
  start a day after time zero).
- R4: both GeoJSON readers skip features of another geometry type before reading their properties and ID
  (geomtest_check.py `mixed`: a Point with a null ID in a polygon file is skipped).
- R5: see the guard above; WB14 and WB15 unchanged (MB beyond the runs without the river 2.8e-14 to 5.7e-14 mm, river
  identity 4e-11 to 4e-10); ASan rerun.
- Notes: band units `EPSG:9002`, `9003`, `9005`, `9070`, `9080` (feet codes; `EPSG:9001` is metres), `fmsl`, `pies`,
  `pie`, `pieds`, `pied`, `Fuß` and `voet` stop as feet (geotiff_check.py). String IDs are trimmed and may end in `.0`.
