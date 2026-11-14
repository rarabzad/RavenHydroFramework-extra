# Audit A9, phase 22: code and tests

Phase 22 of the round-9 audit (issue list: `spec/audit_A9/AUDIT_A9_issues_and_phases.md`; brief:
`spec/audit_A9/phase22_23_brief.md`): CB9-1/IB9-1, CB9-2/IB9-3, WS9-1, IB9-2, IB9-5, IB9-6, MT9-5 and the SV9-1 code
comment. Reference build: `wt/rel20_Raven.exe` (sources 93e5166); this build: `wt/p22/Raven_p22.exe`; base Raven:
`audit/CB/Raven_base.exe`. Worktrees `wt/p22/code` and `wt/p22/extra`; nothing is committed (diffs, logs, the
byte-identity script and the review brief in `wt/p22/patches/`). Ground truth for MODFLOW: the mf6 6.8.1 program
(`tools/mf6bin/mf6.8.1_linux/bin/mf6`), the 6.8.1 sources, and libmf6 6.8.1 queried with ctypes while a model is
initialised (`wt/p22/review/probe/q3.py`).

Each behaviour change has a regression test that fails with the reference build (the C++ harnesses: compiled from the
reference sources) and passes with this one.

## CB9-1/IB9-1: unnamed packages named as MODFLOW names them

**MODFLOW's rule** (6.8.1, `ModelPackageInputs.f90` `pkgtype_add`, `gwf.f90` `GWF_MULTIPKG`): a name-file row without a
third word is named `<type>-<n>`, n its place among all rows of its file type, named or not, when the type is one a GWF
model may hold several of (WEL, DRN, RIV, GHB, RCH, EVT, CHD, MAW, SFR, LAK, UZF, API); any other type is named by its
type (DIS, NPF, STO, IC, OC, HFB, CSUB, ...). Checked with libmf6: rows `CHD6 a.chd MYCHD`, `CHD6 b.chd`, `RIV6 r.riv`
give `PKGNAMES` = DIS, NPF, IC, RIV-1, MYCHD, CHD-2.

**Before.** Raven counted only the unnamed rows of a type (`CHD-1` above) and named only DIS/DISV/DISU/NPF/STO/IC/OC by
their type. A kept package whose names differed was left out of the balance without a message (`ExtConnect` keeps a
name only if its `SIMVALS` exist). A second way to the same loss: the working copy comments out the rows Raven takes
over, so MODFLOW renumbered the unnamed rows after them (a kept `RCH6 r2.rcha` after a taken-over unnamed RCH became
MODFLOW's RCH-1 while Raven read RCH-2).

**Change** (`GWExternal.cpp`).
- `ExtReadSimulation`: every row of a type advances its count; an unnamed row of a multi-instance type is
  `<type>-<count>`, any other unnamed row is its type. `gw_ext_pkg.named` records whether the row named it.
- `ExtEditNameFile`: each unnamed row of a multi-instance type gets its name written after its file name in the working
  copy ("the name MODFLOW 6 gives this package in the model's name file"), so removing rows and adding Raven's rows does
  not change the names of the others. The second call (Raven's packages added) finds these rows already named.
- `ExtProbe`, right after `Initialize`: the model's package names are read from MODFLOW's memory
  (`__INPUT__/<model>/PKGNAMES`, through the new `CMF6Engine::GetStrings`); every multi-instance package not taken over
  must be there, else the run stops naming the package, its file and MODFLOW's packages ("give each package of the name
  file ... a name as the third word of its row"). Without `PKGNAMES` (a library that cannot give strings) the package's
  `INUNIT` in memory is the test.

**Tests** (`input_checks.py`, the existing-model example, 2 days in quick mode).
- E7 `WEL6 w0.wel W0` (rate 0), then `WEL6 gwf_liard.wel` unnamed. rel20: packages in balance `GHB_OUTLET W0`, MF6 balance
  error 11999.996 m3/d, the working-copy row unnamed: FAIL. p22: `GHB_OUTLET W0 WEL-2`, 0.0037 m3/d, the row names WEL-2.
- E8 `RCH6 gwf_liard.rcha` (unnamed, `:RavenTakesOver RCH-1`), then `RCH6 r2.rcha` (unnamed, `:KeepPackages RCH-2`).
  rel20: RCH-2 not in balance, MF6 balance error 1.31e6 m3/d: FAIL. p22: RCH-2 in balance, 0.0031 m3/d, row names RCH-2.

**Manual.** existing_model.tex: the naming rule, the names the user gives, the written names, the stop; one safeguard.

## CB9-2/IB9-3: two AUXILIARY lines in the stream package

**MODFLOW** keeps the names of the first AUXILIARY line (libmf6 with `AUXILIARY ZONE X` then `AUXILIARY SUBBASIN`:
`NAUX` 2, `AUXNAME_CST` ZONE, X; the CB and IB runs of the mf6 program agree).

**Before.** Each AUXILIARY line replaced the names, so the last line won; with equal counts the NAUX guard passed and
Raven read another auxiliary column as the subbasin ID (CB: every river cell of the Liard example mapped to subbasin 7,
"Successful Simulation").

**Change.** In the probe session `ExtProbe` reads the stream package's `NAUX` and `AUXNAME_CST`; `ExtBuild` takes the
subbasin's index and the stride from them. It still reads the file's AUXILIARY lines: a second line gives a warning
naming the names MODFLOW keeps; without the memory names it uses the first line, as MODFLOW does; the NAUX comparison
stays for that case. A missing auxiliary name now lists the names MODFLOW read.

**Tests.** E9 `auxiliary SUBBASIN` then `auxiliary ZONE`: p22 runs with the warning, GWBudget.csv and Hydrographs.csv
identical to the unmodified model's; rel20 stops ("no auxiliary variable SUBBASIN"). E10 `auxiliary ZONE` then
`auxiliary SUBBASIN` with a ZONE value 7 on every row: p22 stops ("has no auxiliary variable SUBBASIN (MODFLOW 6 reads
the auxiliary variables ZONE, from the first AUXILIARY line)"); rel20 completes ("Successful Simulation", every river
cell on subbasin 7).

## WS9-1: BMI queries only inside an initialised session

**Before.** The NAUX check ran after `ExtProbe` had finalised libmf6: `get_var_rank` failed, the check never ran, and
libmf6 wrote its error report to its closed output unit, which gfortran turned into `fort.1000` in the folder Raven was
started in.

**Change.** The NAUX and auxiliary-name reads moved into `ExtProbe` (above). `CMF6Engine::HasVar`, `GetVarSize`,
`GetDoublePtr`, `GetIntPtr` and `GetStrings` return failure without calling the library when no model is initialised
(the same results as before for such a call, without the file). While a model is initialised libmf6's reports go to
`mfsim.stdout` in the working copy. `GetStrings` checks rank (0 or 1) and type (`STRING`) first and passes the address
of its buffer pointer: `get_value_string`'s `c_ptr` argument is passed by reference (a buffer passed directly crashes
libmf6, checked with ctypes); a fixed-length character array is refused by libmf6 with status 1, not a crash.

**Tests.** E6 and E9 also require that no `fort.*` file is left in the run folder or `out/`: rel20 leaves `fort.1000`
(E6 FAIL), p22 none.

## IB9-2: ALBERS and LCC beyond 180 degrees from the central meridian

**Change.** `CGWCRS::Forward`: `l = lon*D2R - lon0`, reduced with `remainder(l, 2 pi)` only when `|l| > pi + 1e-12`,
as PROJ's `adjlon` does (review F2: an unconditional `remainder` flipped a point exactly 180 degrees from lon0, where `l`
lands one ulp above pi, to the other side of the cut). Every position up to 180 degrees from lon0 is bit for bit as before.
`Inverse` is unchanged (it may return lon -187.1 for a point west of 180; a polygon read back and projected again lands
at the same place).

**Tests** (geomtest_check.py, against pyproj): `ALBERS 55 65 50 -154 0 0` (EPSG:3338) at lon 172.9, lat 52.9 and
`LCC 33 45 23 -96 0 0` at lon 151.2: reference sources 3.75e6 m and 1.42e7 m from PROJ (FAIL), p22 within 1 mm; the
inverse round trip is compared modulo 360 degrees in longitude. `ALBERS 55 65 50 -154 0 0` at (26, 60), exactly 180
degrees from lon0: x = +1543006.08 as PROJ (the first p22 build gave -1543006.08; the reference sources pass).

## IB9-5: band units

**Change** (`GWGeoTIFF.cpp`). Other units: the words `fuss`, `piedi`, `piede`, `fot`, `fod`; prefixes written as words
(`kilo`, `centi`, `milli`, `deci`, `micro`, `nano`) and parts of a metre (`tenth(s)`, `hundredth(s)`,
`thousandth(s)`), but only on the unit: directly before a metre word, also with `of` between ("kiloMeters", "Kilo Meter",
"tenths of metres"), or standing alone; "nano DEM m" and "m kilo" are metres (review F4); `pé`/`pés` as a word of its own
(UTF-8, either case of the e); every EPSG length-unit code other than 9001 (9002-9099, 9300-9302 (review F7), 1025 mm,
1033 cm). A number after a metre word makes it a scaled unit (the unknown-unit warning, as a number before it already
did) only when it is a scale (review F3): after a factor sign or word (`x`, `*`, `×`, `/`, `by`, `scale(d)`,
`factor`), with such a sign in front (`*0.1`, `×0.1`), or a fraction (a decimal point, or a comma, slash or exponent
between digits). Datum years, versions and other whole numbers after it are not ("m NAVD 88", "m CGVD 2013",
"Elevation, m, version 2", "m (2 m grid)": metres, silently, as in the reference).

**Tests** (geotiff_check.py, run with `--nolib`): Fuss, FUSS, piedi, pés, PÉS, fot, Fod, EPSG:9036, EPSG:1033,
EPSG:1025, EPSG:9030, EPSG:9093, EPSG:9301, kiloMeters, Kilo Meter and "tenths of metres" stop; m*0.1, "metres x 0.1",
"m (scaled by 0.1)", "m ×0.1" and "m / 10" warn. Reference sources: these read as metres (with the warning or silently):
FAIL. The reviewer's datum texts ("m NAVD 88", "m (NAVD 1988)", "m CGVD 2013", "m (RH 2000)", "metres NN 2016",
"m ü. NHN 2016", "m, EGM 2008", "height m 2020", "m above datum 1", "Elevation, m, version 2", "m (2 m grid)",
"m, 1 m resolution") and "nano DEM m", "m kilo" are metres without a note, as in the reference. The reviewer's 51
texts (`review/r/bu.py`) against the reference sources: the same result for every text except the intended ones (pé
stops; "m*0.1", "metres x 0.1" and the fractions "m +/- 0.5", "m (accuracy 0.5)", "m, vertical accuracy 0.15" warn).

**Manual.** building.tex's band-unit cell.

## IB9-6: messages and degenerate rings

- A whole JSON number beyond 9e15 as an ID: "the number 9007199254740993, larger than 9e15, the largest ID Raven reads
  as a number (write it as a string: "9007199254740993")" (`IDRefused`). Before: "..., not a whole number". The string
  advice is given only for a number written as an optional minus and at most 18 digits; otherwise (`1e+16`, review F5):
  "write the ID as a string of at most 18 digits".
- A missing ID field when the feature has an `"id"` member: the message adds that GDAL's ID_FIELD option puts the field
  there and to write the file without it (`IDMissing`).
- A ring has an area only with 3 or more distinct vertices. An outline without area drops its polygon with its holes
  (before: the hole stayed alone, a clockwise ring). The reader does not stop (review F1): an ID none of whose polygons
  has an area (or whose geometry is an empty Polygon) is left out of the shapes and returned, with the feature and why,
  in the new optional `noArea` map of `ReadGeoJSONPolygons`. The callers stop only for IDs they use: the HRU file for an
  HRU with an aquifer profile ("HRU 1 has an AQUIFER_PROFILE but no polygon in hru.geojson (GeoJSON file hru.geojson,
  feature 1 (HRU_ID 1): it has no polygon (its coordinates are empty))", or "...: its polygon has no outline of 3 or
  more distinct vertices, so no area"); the grid-cell files (`:GridFile`, `:MF6GridFile`), where every ID is a cell,
  for any such ID ("grid cell 2 of ... has no area: ..."). Unused features without area are ignored, as before. A
  MultiPolygon part without area beside a proper part is read as before.
- A negative TDIS period length stops: "the length of stress period 1 in model/ext.tdis is -5; a stress period cannot
  be shorter than 0 (MODFLOW 6: PERLEN cannot be less than 0.0)". Before: "... is not a whole number of Raven time
  steps".

**Tests.** geomtest_check.py (the harness prints the IDs read and the IDs left out): `id_big`, `id_bigexp`, `gdalid`,
`degen` (outline [[-123,49],[-123,49]] with a hole: ID 7 left out, with why), `degen3` (4 vertices, 2 distinct),
`degen_part` (ID 7 read with one ring), `empty` (ID 1 read, ID 2 "has no polygon"); the reference sources fail all
seven (`degen_part`: the lone hole is kept, two rings). input_checks.py N27 (unused features with an empty Polygon and
a one-point ring: the run completes; passes with rel20 too, it guards the review's case), N28 (HRU 1's Polygon empty:
the stop above; rel20 stops with "HRU 1 does not overlap any active groundwater cell": FAIL), E11 (rel20 stops with the
old message: FAIL).

## Review responses (review/REVIEW.md)

- F1, F2, F3, F4, F5, F7: in the sections above.
- F6 (CRLF name file with `:RavenTakesOver`): `ExtEditNameFile` writes a taken-over row as a comment with the row's
  carriage return moved to the end of the line, so MODFLOW finds no isolated carriage return. Test input_checks.py E12
  (the example's name file with CRLF line ends, RCH_MODEL and EVT_MODEL taken over): rel20 stops in MODFLOW (return code
  2): FAIL; p22 completes.
- Byte identity is compared exactly (below).

## MT9-5 and SV9-1

- E5 reads `BEGIN period 0.2D1` (2 for MODFLOW; `atoi` gives 0) and `3/`: rel18 (atoi) FAIL, rel20 and p22 pass.
- `GWVadoseModel.cpp`: the comment on the Sy dh limit states the one condition (a rise meeting more water above
  equilibrium than Sy dh) and the cases that do and do not reach it. Code unchanged.

## Byte identity (`patches/byteid.py`, log `patches/byteid.log`)

Text files (`.txt`, `.lst`, `mfsim.stdout`) are compared line by line, exactly, after each run's own folder is
replaced by `<RUN>`; only the build-date line and the lines that report timings are left out (the log lists them).
No groundwater, p22 against base Raven: the small model in three chained hotstarts (no tracer, Nitrate) and with the age
tracer, Liard without groundwater for 5 years and a 1-year hotstart, and the seven benchmark models of the code
repository. Coupled, p22 against rel20: Liard CONCEPTUAL 180 d, the existing-model example 31 d (outputs and the mf6
folder, its `.lst` files and `mfsim.stdout` included), PHYSICAL + RICHARDS (4 HRUs, 20 d), CONCEPTUAL with 10
unconverged steps. Result (`byteid.log`, the build with the review responses): every comparison identical; benchmarks
Alouette (17 files), Irondequoit (4), Salmon_HBV (6), Salmon_GR4J (6), Revelstoke (17) and LaJoie (17) identical. Nith
stops in its own input in both builds (":AggregatedVariable - invalid HRU Group used"), with the same messages (the
script counts it as a difference because no output is written). Lines left out: the build date, "Elapsed run time",
"Run start/end date and time" (mfsim.lst) and "HRU/grid linkage: computed in ... s".

## Test suite

- `run_all.py --quick` with the first build of this phase (`patches/run_all_quick.log`, report
  `run_all_quick_report.md`): 63 steps passed, 0 failed, 2 not run (the USGS examples, not installed); 5 checks skipped
  inside passing steps (patchelf, the WB14 restart from a reference-build file, W4/W6/W11 of a soil-zone script). The
  tutorials step passes.
- After the review responses, with the final build: geomtest_check.py ALL PASSED (`geomtest_new.log`; reference
  sources: 9 FAILED, `geomtest_refsources.log`), geotiff_check.py --nolib ALL PASSED, input_checks.py: every case passes
  (`input_checks_p22.log`, whose one failure, E12, was an error in the test itself, fixed and rerun in
  `input_checks_subset_p22.log` with N27, N28, RN1-RN2 and E1-E12; rel20 on the same subset: 8 FAILED,
  `input_checks_subset_rel20.log`), byte identity as above.
- The manual builds in a scratch copy (latexmk, no errors).

## Left for phase 23 and later

- verification.tex: the new input checks N27-N28, E7-E12 and the GeoJSON/geometry cases (MT9-4 lists E1-E6).
- Workshops regenerated with this build (W4: no `fort.1000`).
