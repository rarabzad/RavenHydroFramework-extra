# Audit A10, phase 24: code and tests

Phase 24 of the round-10 audit (issue list: `spec/audit_A10/AUDIT_A10_issues_and_phases.md`; brief:
`spec/audit_A10/phase24_25_brief.md`): CB10-1, CB10-2, IB10-1, IB10-2/IB10-3 (the band-unit redesign), IB10-4, IB10-5
and the SV10-1 code comment. Reference build: `wt/rel22_Raven.exe` (sources 5b49d0a); this build: `wt/p24/Raven_p24.exe`;
base Raven: `audit/CB/Raven_base.exe`. Worktrees `wt/p24/code` and `wt/p24/extra`; nothing is committed (diffs, logs,
the byte-identity script and the review brief in `wt/p24/patches/`). Ground truth: the mf6 6.8.1 program and libmf6
6.8.1 (queried with ctypes while a model is initialised), PROJ 9.8.1 through pyproj.

Each behaviour change has a regression test that fails with the reference build (the C++ harnesses: compiled from the
reference sources) and passes with this one.

## IB10-2 / IB10-3: band units, redesigned

**Before.** `metre = firstM || (anyM && !other)`: a text was metres if its first word was a metre word, or if it named a
metre word and no other unit anywhere. Any other-unit word or EPSG number in 9002-9099/9300-9302 anywhere in a text that
did not start with a metre word refused it ("Elevation (m), converted from feet", "Elevation in metres (EPSG:9057)"),
while parts and multiples not directly before the metre word ("tenths of a metre", "thousands of metres", "m
(thousands)") and other units in unlisted languages or scripts ("Zentimeter", "centímetres", "dam", "фут", "英尺") were
read as metres, some silently. Each round moved the boundary.

**Design (`GWGeoTIFF::BandUnit`, `src/GWGeoTIFF.cpp`).** The first unit expression of the text decides, matched against
one fixed table:
- words: runs of letters of any alphabet (UTF-8 decoded; ASCII, Latin-1, Latin Extended-A, Greek and Cyrillic capitals
  lowered), split also at a lower-case ASCII letter followed by a capital and where a Chinese/Japanese/Korean run meets
  other letters; a word directly followed by a digit is a name (CH1903, NAVD88, LN02), no unit;
- **metre**: the metre written out in the European languages listed in the code and in Cyrillic and Greek (with endings), `m`, `м`, `masl`, `mamsl`, `moh`, `möh`, 米, 公尺,
  メートル, メーター, 미터, `EPSG:9001`;
- **another length** (stop): feet, inches, yards, miles, fathoms, chains, furlongs in English and other languages
  and scripts; fused feet (`ftUS`, `usft`, `...feet`, `...foot`); `km`, `cm`, `mm`, `dm`, `nm`, `µm`, `μm`, `kms`,
  `cms`, `mms` (also Cyrillic); SI prefixes written out (multilingual, also Cyrillic) joined to a metre word, right
  before one or alone; the parts and multiples `tenth(s)`, `hundredth(s)`, `thousandth(s)`, `tens`, `hundreds`,
  `thousands` before a unit word (with `of` and one of `a`, `an`, `the`, `one` between), right after a metre word
  (`m (thousands)`, `m (in 1000s)`) or alone; the EPSG length-unit codes of PROJ's `unit_of_measure` table in
  9002-9099 and 9300-9302 (coordinate-system codes in those ranges, such as 9057, are no unit) and 1025, 1033;
- **short ids** `in`, `ch`, `mi`, `fath`, `link(s)`, `dam`, `hm`: a unit only as the first word (or after `us`, `ind`,
  `int`, `intl`) of a text with no other unit;
- a metre with a number before it, or a scale after it (a number after a factor sign or word, or a fraction, in the
  tokens right after the metre word), and any text without a unit give the unknown-unit warning.

Review additions: the scale scan skips tokens made only of `)]},;:-` and strips edge punctuation before the number and
factor tests ("Elevation (m) x 0.1", "m, scaled by 0.1", "height [m] /10", "m: scale 0.1", "m, 1/10" warn); `per`,
`divide(d)`, `multiply/multiplied` are factor words; a number then `x`, `*`, `×` or "of a/an/the/one" before the metre word
is a number before it ("10 x m", "10*m", "0.1 of a metre" warn); full-width ASCII (U+FF01-FF5E) and the ideographic space
are read as ASCII; a camel-case split also follows a lower-case non-ASCII letter ("müNN": mü, a metre abbreviation);
`méterben` is a metre word; `quilo`, `quilô`, `chilo`, `hectó`, `кіло` are prefixes; `NM` written in capitals, and `nm`
before "state plane", is New Mexico, not the nanometre; "m3" stays a warning.

The tokenizer, the scale rule and the fused-feet rule are those of the earlier code; the scale is now looked for only in
the tokens directly after the metre word (factor words and signs, then a number), so "m, accuracy +/- 0.5 m" and "m
(version 2.1)" are metres. A Chinese, Japanese or Korean run is searched for its own entries, the longest first at each
place (米国 is no metre).

**Compatibility, checked text by text** (scratch `bucmp.py`: every text of the earlier geotiff_check list, A9's
`units.txt`, A10's `units10*.txt`, read with the unit driver compiled from the reference and the new sources): no text
that was read as metres is refused other than the IB10-3 parts ("tenths of a metre", "thousands of metres", "m
(thousands)", "m (in 1000s)"), and no feet text that stopped is read as metres. Changes in class: the IB10-2 metre texts
(stop → metres); the IB10-3 texts (metres or warning → stop); `µm` (warning → stop: the micrometre); `MASL`, `moh`,
`metros`, `metri`, `Metern`, `Höhe in Metern`, `Высота (м)`, "m (version 2.1)" (warning → metres); `CH1903+ LN02`,
`EPSG:9057` (stop → warning: a datum and a coordinate-system code, no unit). Accepted limits: "m (stored as cm)" is
metres (the first unit decides); "Meter (x 1000)" warns (a scaled metre); "dam crest elevation" without a metre word
stops (`dam` first); part words are English only ("Тысячи метров" is metres).

**Test.** `tests/geotiff/band_units.tsv` (235 texts: class M/F/W and the text) read by `geotiff_check.py` (each text
written into a GDAL_METADATA UNITTYPE and read through `CGWRaster::Read`). It holds every text of the earlier inline list
(µm now F). Reference sources: 98 of the 235 fail (`patches/geotiff_nolib_refsources.log`); this build: all pass.

## IB10-1: a model across the antimeridian

**Before.** The projection origin was the arithmetic mean of the HRU centroid longitudes: 179.998 and −179.998 gave 0,
the far side of the globe; the grid was stretched 3.6 times (lat −16.8) and half of a lon/lat DEM across 180 gave no
value.

**Change.** `BuildGeometry` (`GroundwaterModel.cpp`): the longitudes are averaged as written; when they span more than
180° as written and taking those west of 0 as +360 gives a smaller span, they are averaged so and the mean is taken back
within ±180. A model whose centroids span at most 180° (every model not across 180) gets the same origin as before, bit
for bit, so its runs are unchanged. The 180° condition is needed: comparing the spans alone took Liard's
longitudes (near −125) as +360 whenever rounding at that magnitude made their span an ulp smaller, which moved the
origin in its last bits and broke the byte identity of crs_inputs against the reference (found in testing, fixed
before the final build). The cached HRU/grid linkage is used only when its origin equals this one (a cache of an antimeridian model
written before is rebuilt). `CGWProjection::Inverse` returns longitudes within ±180 (unchanged within that range), and
`CGWRaster::Sample` without a CRS tries a longitude 360° east or west when it lies outside the raster (a lon/lat raster
written beyond ±180).

**Test.** `input_checks.py` A1: sz_models' two-HRU case with its shared edge on 180 (longitudes within ±180, the DEM
across 180) against the same case at longitude 0. Reference: 56 active cells against 32, CHD flows 56 % apart, a DEM
without values; this build: 32 cells, recharge, storage and CHD flows identical (difference 0).

## IB10-4: rings without area

**Before.** `RingFromJSON` counted distinct vertices only: a collinear ring or a square traced out and back passed (the
grid-cell file then held a cell of area 9e-10; an HRU whose only polygon is collinear got "does not overlap any active
groundwater cell").

**Change.** A ring of 3 or more distinct vertices also needs an area above 1e-12 of the square of its extent (computed
from its first vertex, so collinear points give 0 without cancellation). The reason reads "its polygon has no area (its
outline has fewer than 3 distinct vertices, lies on one line or encloses no net area)" (a figure eight of equal lobes
also has none).

**Test.** `geomtest_check.py`: `col` (3 collinear vertices), `retrace` (out and back), `eight` (a figure eight) reported without area; `col_part`
(a collinear MultiPolygon part beside a square) read. Reference sources fail all four.

## IB10-5: edge cases

- **CGWCRS::Forward**: the longitude is reduced within ±180 first, then its difference from the central meridian, both
  with PROJ's `adjlon` (an angle within π + 1e-12 is left as it is, else `v - 2π floor((v+π)/2π)`). Unchanged within
  ±180. Test (geomtest): `ALBERS 55 65 50 -154` at lon −334 and `ALBERS 60 90 90 0` at lon −540 against PROJ (reference:
  3.1e6 m and 9.6e5 m off; now 3e-7 m).
- **Southern Lambert cone at its apex**: ρ = 0 when φ is within 1e-12 of −π/2 for n < 0. Test: `LCC -30 -10 -20 -170
  500000 0` at lat −90 (reference 51.8 m off; now 2e-7 m).
- **`:OverlapWeights` cell numbers**: a value outside 1..INT_MAX stops ("the cell number 4294967297 is not between 1 and
  the number of cells per layer"), and `GWID` stops on `strtoll` overflow either way ("is out of range (beyond 9223372036854775807)", or -9223372036854775808).
A row of weight 0 is skipped before its cell number is read (test E23: weight 0 with cell 4294967297 runs; E22: a
negative 20-digit cell stops as out of range). Tests: `input_checks.py` E17
  (reference: runs, reading cell 1) and E18 (reference: "cell -1 is outside the model layer").

## CB10-1: OPEN/CLOSE in the name files

**MODFLOW 6.8.1** reads an OPEN/CLOSE file in place of the line in any block of the name file and of mfsim.nam (checked
with the mf6 program: PACKAGES, OPTIONS, MODELS, SOLUTIONGROUP), but only as the block's first line other than comments;
OPEN/CLOSE as a later line, or twice in a block, is refused ("Input file tag not found"). A first test of an OPTIONS
block had OPEN/CLOSE as its second line and was refused for that reason.

**Change** (`GWExternal.cpp`).
- `BlockLines`: the lines of a MODFLOW input file with each OPEN/CLOSE file of a block (not GRIDDATA) in place of its
  line (path relative to the simulation folder, or absolute: `/`, `\`, a drive letter; a nested OPEN/CLOSE stops; as for
  MODFLOW, OPEN/CLOSE after a block's first line stops). Used for mfsim.nam and the model name file in
  `ExtReadSimulation`, so the package list, takeover and keep rules, `_extNoSto`, the stream package and the balance list
  see the rows; for the NEWTON detection in `ExtProbe` (an OPTIONS block that starts with OPEN/CLOSE); and in
  `ExtWriteSimFile`, which finds a CONTINUE also in an OPEN/CLOSE file and, when the OPTIONS block starts with
  OPEN/CLOSE, writes its CONTINUE after that line (before it, mf6 refuses the file). `ExtReadOpenClose` (TDIS, mover)
  takes absolute paths too.
- `ExtEditNameFile`: the rows of an OPEN/CLOSE file of the PACKAGES block are written into the working copy in place of
  the line (which stays as a comment), so taken-over rows are commented out and unnamed rows named as for inline rows.
- PKGNAMES check, the other way: with `PKGTYPES`, every package MODFLOW read of a multi-instance type (other than
  `*_RAVEN`) must be one Raven read; else the run stops naming it.
- A converged step whose MF6 balance error is above 1 % of the gross flow gives a warning once a run.
- Manual: existing_model.tex (OPEN/CLOSE rows and the warning); appendix messages.

**Tests** (`input_checks.py`, review additions E19-E21): E19 the OPTIONS blocks of the name file (SAVE_FLOWS, NEWTON)
and of mfsim.nam starting with OPEN/CLOSE: identical results (reference: NEWTON missed, GWBudget.csv with the
"recharge not applied" column, and mf6 refusing the CONTINUE line written before OPEN/CLOSE); E20 OPEN/CLOSE after the
PACKAGES block's first row stops with MODFLOW's rule; E21 an absolute OPEN/CLOSE path: identical results. E13 RCH and
EVT rows in an OPEN/CLOSE file, taken over: runs, GWBudget.csv and
Hydrographs.csv identical to the inline model's (reference: "package RCH_MODEL is not in the model name file"); E14 the
same without `:RavenTakesOver` stops with the "beside Raven's" message (reference: ran with a −33 % MF6 balance error);
E15 MODELS and SOLUTIONGROUP through OPEN/CLOSE: identical results (reference: "no GWF6 model"); E16 loose solver
tolerances (DVCLOSE 10, RCLOSE 1e8): the warning (step 1, −1.45 %; reference: none).

## CB10-2: channel storage of ensemble members

**Before.** For each later member `InitializeBasins(Options,true)` recomputed `_channel_storage` from the autocalculated
flows, and `RestoreInitialDynamicState` did not set it back: member 2's channel storage was offset by −1.05 mm (Liard
without groundwater) and −0.49 mm (coupled), and its `:ChannelStorage` in solution.rvc differed in 36 of 65 subbasins.

**Change** (`ModelInitialize.cpp`, `Model.h`): the channel storage of each subbasin is saved with the routing memory at
the first `CalculateInitialWaterStorage` and set back in `RestoreInitialDynamicState` (a member's own .rvc still
overrides it). The rivulet storage keeps its documented offset (base Raven adds it at every initialization, also for
member 1). Member 1 and single runs are unchanged.

**Tests.** `behaviour_check.py` (ensemble): each member's channel storage (WatershedStorage.csv and each subbasin's
`:ChannelStorage`) equals the single run's. `patches/byteid.py` (4): no-groundwater ensemble, member 1 byte-identical
to base Raven's, member 2's hydrographs, channel storage and `:ChannelStorage` identical to the single run's. Before:
offset −1.04842 mm (`audit10/CB` ensng.py); after: 0.

## SV10-1 (code comment only)

`GWVadoseModel.cpp`: the comment states the condition (water above equilibrium in the band a rise crosses: in transit,
a steady-flux column's excess when a small Sy makes the water table rise fast, or a nearly full top cell), that a smaller
Sy makes it more likely, and that a column at rest raised by a boundary or lateral inflow does not bind. The manual and
user guide are phase 25's.

## Byte identity (`patches/byteid.py`, log `patches/byteid.log`)

0 comparisons with differences: without groundwater against base Raven (small model with chained hotstarts, no
tracer, Nitrate, AGE; Liard 5 years and a 1-year hotstart; the 7 benchmark models of the code repository; member 1 of a
Monte Carlo ensemble), coupled runs against rel22 (Liard CONCEPTUAL 180 d, the existing-model example 31 d, both mf6
folders, PHYSICAL + RICHARDS, 10 unconverged steps); member 2 of the ensemble equal to the single run in hydrographs and
channel storage. `crs_inputs` and `dry_start` compare more coupled runs with rel22 byte for byte (pass).

## Test suite

`run_all.py --quick` (`patches/run_all_quick.log`): 63 passed, 0 failed, 2 not run (usgs_sagehen and usgs_capture need
RAVEN_USGS_EXAMPLES). The new cases against rel22: `patches/input_checks_new_cases_rel22.log` (E13-E22 and A1
fail; E23, a row of weight 0 skipped, passes there too: it guards the reading order of this change), against the reference sources `patches/geotiff_nolib_refsources.log` (98 band-unit texts fail) and
`patches/geomtest_refsources.log` (9 cases fail, the figure eight included).
