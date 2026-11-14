# Audit A12, phase 28: code and its tests

Issues: CB12-1 to CB12-4, SV12-1 to SV12-3 (warnings and code comments), IB12-1 to IB12-6. Base: code soil-zone f8c3d0f,
extra bb37878. Reference build: wt/rel26_Raven.exe. Ground truth: mf6 6.8.1 (sources in tools/mf6bin/mf6.8.1_linux/src),
GDAL 3.12.2 through rasterio 1.5.2.

Rule of this round: what Raven cannot reproduce exactly, it refuses with a message naming the cause and the remedy. Each
refusal has a test and a message row in the manual's appendix and the user guide.

## CB12-1: one MODFLOW model

`ExtReadSimulation` (GWExternal.cpp) counts every row of the MODELS block and every row of the EXCHANGES block of mfsim.nam
(read through `BlockLines`, so OPEN/CLOSE files count). More than one model, or any exchange, stops:

> the MODFLOW 6 simulation ... holds 2 models (gwf_liard (GWF6), gwf_b (GWF6)) and 1 exchange (GWF6-GWF6 ab.exg); Raven
> couples one MODFLOW 6 groundwater-flow model and books only that model's water, so the flow across an exchange would be
> outside Raven's balance. Couple a simulation that holds the one GWF model alone, with no EXCHANGES rows

This also closes the exchange-level mover and the other model's time series (both need a second model). The stops that
only applied to several models (a later start renumbering several models, TS6 with several models, several GWF models
without `:MF6Model`) are unreachable and removed. `:MF6Model` still names the one GWF model. The shipped examples and the
USGS Sagehen model have one model and an empty EXCHANGES block; both run (Sagehen: short run of every case of
usgs_sagehen.py, restart included, patches/sagehen_short_p28.log).

Before: the A12 case ran "Successful" with a balance error of -603,483 m3/d (the exchange flow) and 1.2e6 m3 withheld on
unconverged steps. After: E31 (exchange) and E31b (two models without exchange) stop.

## CB12-2: files named outside the simulation folder

New `ExtLocalizeFiles` (called in `ExtBuild` after the copy, before anything reads a package file):

- the TDIS file and the model name file, which Raven rewrites, must lie in the simulation folder (absolute, `../` or
  missing: stop, naming the file);
- a kept package whose name-file row names its file by an absolute path inside the simulation folder is named there by
  its relative path (review response 5);
- a kept package whose name-file row names its file by an absolute path outside the folder, or by a relative path that leaves the folder
  (`LeavesFolder`, lexical), is copied into the working copy as `raven_copy_<n>_<name>`, and `ExtEditNameFile` writes the
  row with the copy and the package's name ("# Raven's copy of ..., which lies outside the simulation folder"). From then on
  every reader (STO check, mover, renumbering, OPTIONS, stream AUXILIARY) handles it as a relative file, at any start.
  MODFLOW reads the same text: relative names inside the file are relative to the simulation folder either way.
  GWModelSummary.txt counts the copies ("package files : n named outside the simulation folder, copied into the working
  copy");
- a package file that does not exist stops, naming it;
- a TS6 file named outside the folder stops a later start (its series would be shifted in the working copy, and the
  FILEIN line may lie in an OPEN/CLOSE file): "... names the time-series file ... outside the simulation folder";
- `BlockLines` itself stops on a file it cannot open ("cannot open the MODFLOW 6 file ..."), and `ExtRenumberPeriods`
  stops instead of `continue` on a package file it cannot open: no reader skips a file silently. A search of the GW sources
  for other opens that skip found none (the remaining opens are the cache and hash reads of Raven's own files).

Before: `WEL6 /abs/gwf_liard.wel` on a start 32 days late kept the old period 1 rates (7,500 m3/d more pumping), silently.
After: E32 (absolute) and E32b (`../shared/...`) give GWBudget.csv and Hydrographs.csv identical to the twin with the file
in the folder; E32c (absolute TS6, later start) and E32d (missing file) stop.

## CB12-3: TVK6/TVS6 on any later start

The `tv` stop in `ExtRenumberPeriods` moved before the `_extDrop==0` test: any start after the model's time zero with a
package whose OPTIONS name TVK6 or TVS6 stops ("uses time-varying properties (TVK6/TVS6), whose period data and time series
count from the model's time zero; Raven does not shift them ..."). This is what the manual already states (Later starts
and restarts refuse ... TVK6/TVS6). Before: the A12 case (start inside a 32-day first period) ran with k.ts unshifted.
After: E33 stops.

## CB12-4: restarts with packages that hold their own state

Which packages carry state from step to step, from the mf6 6.8.1 sources (the `*_ad` advance routines that keep values of
the previous step): LAK (`lak_ad`: stages, XOLDPAK), MAW (`maw_ad`: well heads), UZF (`uzf_ad`: water content), CSUB
(`csub_ad`: stresses, preconsolidation stresses, delay-bed heads) and SFR only with its STORAGE option (`sfr_ad` copies
stage and flows to their old values only when `istorage == 1`; without it "there is no old stage or storage effects in the
stream"). STO carries storage through the heads, which a restart carries; MVR, NPF, BUY/VSC (need another model, refused
by CB12-1), TVK/TVS, CHD, WEL, DRN, RIV, GHB, RCH, EVT, HFB, GNC and API keep no state of their own.

New `ExtRestartState` (in `ExtBuild`): a restart with hotstart heads (`:GWHeads`, which is how every restart path reaches
the existing model: solution.rvc, ensembles and EnKF members, which re-run `ExtBuild`) and a kept package of those types
stops, naming the package and its state. Carrying the state exactly (lake stages into STRT, MAW heads, CSUB stresses) was
not done: UZF water content and CSUB delay-bed heads have no exact input form. The manual's sentence "A restarted run
reproduces a continuous one" now names this condition.

Before: the A12 lake case refilled the lake with 1.1e7 m3 on restart, no message. After: E34 (LAK) and E34b (CSUB) stop;
E34c (the example, no such package) restarts and runs; Sagehen's restart (UZF taken over, SFR without STORAGE kept) runs
with a deviation of 0.

## SV12-1 to SV12-3: release-limit warnings and comments

`VZStep` (GWVadoseModel.cpp) now keeps both limits, `syDh` and `room`, and the warning (once a run) names the one that
bound: "than the room left in the top cell above the water table (less than what MODFLOW stores for the rise, Sy dh)" or
"than MODFLOW stores for the rise (Sy dh)". For KINEMATIC the Sy dh text adds "(with KINEMATIC this happens where a column
crosses aquifer classes of different specific yield)"; the KINEMATIC node-material counting was not changed (option 2 of
the brief: the warning names the limit that bound). Rule (ii) (a vanishing column) writes no warning: a warning was tried
and fires in ordinary runs wherever the water table rises into the soil zone (Workshop 3's RICHARDS and KINEMATIC runs),
so it would be noise; the hand-back is booked as rejected recharge in GWBudget.csv. The documents should say that rule (ii)
writes no warning (phase 29). The code comments of rule (ii) (GWVadoseModel.cpp, GWSoilZoneModel.cpp, GroundwaterModel.h)
name both limits and the hand-back.

Tests (test_vz_kinematic.py): K11 (SAND Sy 0.25 over SILT Sy 0.05, the auditor's kw3 set-up): the warning names Sy dh and
not the room; K12 (the auditor's kw2 set-up, KINEMATIC and RICHARDS): the vanishing column releases at most the room
(5.355 m3) and hands the rest back as rejected recharge, with no release warning (it documents rule (ii); the behaviour
is unchanged, so K12 also passes with rel26). L8 (test_vz_lag.py) matches the common start of the warning. Before (rel26):
K11's warning named the room. Water books unchanged (identities 0). Workshop 3's excerpt t3_warn_lag.txt holds the old
LAG warning text, so tutorials_check fails until the workshops are regenerated with this build (phase 29).

## IB12-1: ESRI ASCII side files

`GWGeoTIFF::ReadSideFile` and `GWGeoTIFF::BandMeta` (new, public) hold what `ReadMemory` did for GDAL's metadata: the side
file, GDAL_METADATA, GDAL's precedence, the band-unit rule and METRES. `CGWRaster::Read` (GWGeometry.cpp) calls them for an
ESRI ASCII grid: its side file's Scale and Offset are applied (no-data cells stay no data) and its UnitType goes through the
band-unit rule. GDAL's AAIGrid driver keeps the header's NODATA_value and takes no NoDataValue from the side file (checked
with rasterio: header -9999 and side file 7 gives -9999; no header value and side file 7 gives none), so neither does Raven.
Before: `dem.asc` with a side file in ft read as metres. After: geotiff_check "ESRI ASCII with a side file" cases (scaled
values sample as the grid scaled by hand; ft stops; METRES reads with the warning; a side NoDataValue is ignored; a side
file not in GDAL's form stops).

## IB12-2: GDAL's metadata only in the form GDAL writes it

`GXDocument`/`GXElement` (GWGeoTIFF.cpp) accept exactly what CPLSerializeXMLTree writes (cpl_minixml.cpp): one element per
line, indented two blanks a level; attributes ` name="value"` in double quotes; `<name>text</name>`, `<name ... />`, or
child elements and `</name>` at the element's indentation; text escaped by CPLEscapeString (&lt; &gt; &amp;, &quot; in
attributes, &#xFEFF; for a byte-order mark, other control characters left out); nothing else (no comments, declarations,
CDATA or other entities), one root element, an optional final line end (the TIFF tag has none). Checked against GDAL's
output: GDAL_METADATA and side files written by rasterio, and the fixtures.

- GDAL_METADATA: root `GDALMetadata`, only `Item` children with attributes `name`, `sample`, `role`, `domain` in GDAL's
  order, `sample` an integer as `%d` writes it, roles in lower case, one item per role of band 1; the value is unescaped a
  second time (GDAL escapes item values with CPLES_XML before serialising: `f&t<"x` is written `f&amp;amp;t&amp;lt;&amp;quot;x`).
- Side file: root `PAMDataset`; `PAMRasterBand` only directly under it, with exactly `band="n"` (an integer as GDAL
  writes it), one per band; band 1's `Scale`, `Offset`, `UnitType`, `NoDataValue` at most once each, with text, no other
  attribute than `le_hex_equiv` (16 hex digits) on NoDataValue. A name GDAL reads in any case (EQUAL) written in another
  case is not GDAL's form.
- A text not in that form: if it holds any of the words GDAL takes band values from (side file: PAMRasterBand, Scale,
  Offset, UnitType, NoDataValue; GDAL_METADATA: scale, offset, unittype, or a character reference that could spell them),
  in any case, or a NUL byte, the run stops ("... is not in the form GDAL writes (why) and names ...: rewrite it with GDAL:
  copy the raster with gdal_translate, or set the values with gdal_edit.py ..."). Otherwise it is ignored: GDAL takes band
  values only from PAMRasterBand elements and from items with those roles, so a text without them provably gives none.

The auditor's scripts (pam.py, pam2.py, pam3.py, gmeta.py; 54 cases) rerun against a driver built from these sources:
50 stop, 4 agree with GDAL, none differs silently (patches/ib12_gdal_vs_p28_summary.txt). The BOM message (IB12-4's code
part) is gone: a byte-order mark is simply not GDAL's form. geotiff_check.py: the hand-written side-file table rewritten to
the new rule (GDAL's form read with GDAL's precedence; 18 other forms stop; two files naming no band value ignored) and
seven GDAL_METADATA cases.

## IB12-3: METRES is the user's statement for texts Raven cannot place

`BandMeta`: METRES lifts a band unit text of class S (a text the classifier cannot place) and is accepted for N and M; a
recognised other length (F) or scaled metre (X) stops also with METRES ("METRES after the file name does not apply to a
unit of another length / a scaled unit"). With METRES every run writes a warning naming the file's own unit ("read as
metres because METRES follows the file name (:LandSurface dem.tif METRES); the file's own band unit is 'height' ...", or
"the file gives no band unit"). Without METRES the stops are unchanged. The classifier now places the auditor's misses:
`epsg n`, `epsg: n` (an EPSG length code after blanks or a colon), a signed exponent or a leading dot in a number and metre
(`1e-2 m`, `.1 m`: X), Greek SI-prefixed metres (χιλιόμετρα, εκατοστόμετρα, χιλιοστόμετρα, δεκατόμετρα), santi-/senti-/etto-,
公厘, ft/feet fused with a listed datum (`ftMSL`, `ftasl`), and another length named with its metre conversion as the
whole text (`ft (0.3048 m)`, `US survey foot (0.3048006 m)`, `M (feet)`: a length text followed by a bracketed number and
metre form, or a metre form followed by a bracketed length text). Texts that only mention another length beside a metre
(`Elevation (m), 1 km grid`) stay S. band_units.tsv: those rows are F or X; every row is checked with METRES (F and X stop,
S, N and M read with the warning naming the text).

## IB12-5: near-twins

`BUMetreForm` and `BUDatum` accept a dotted abbreviation with or without its final dot, `above` before a datum, and a
blank before a datum's year; `BUMetreText` accepts a quantity followed by a comma. New datums: `s. n. m.`, EGM08, OD, MLLW,
MLW, MHW, MHHW, LAT, HAE, orthometric, NGF, IGN69, N2000, NZVD2016, T.P., (the) WGS84 ellipsoid; quantity
`height_above_ellipsoid`; metre form `http(s)://www.opengis.net/def/uom/EPSG/0/9001` (and the same URI with another length
code is another length). band_units.tsv: 27 new M rows; four rows that were S become M (m above NAVD88, m CGVD 2013,
m (RH 2000), m, EGM 2008).

## IB12-6: surplus tokens

`:HRUGeometry`, `:RiverGeometry` and `:GridFile` take `GWMaxTokens(s,Len,3)`: a surplus value stops ("has the surplus
value '2'"). Tests E35, E35b, E35c.

## Tests

- input_checks.py E31-E35c (patches/input_checks_new_p28.log; with rel26 every new case fails except E34c, which passes on
  both: patches/input_checks_new_rel26.log).
- test_vz_kinematic.py K11, K12; test_vz_lag.py L8 (patches/vz_*_p28.log; rel26: K11, K12, L8 fail).
- geotiff_check.py (patches/geotiff_nolib_p28.log; against the f8c3d0f sources the new cases fail:
  patches/geotiff_nolib_refsources.log).
- run_all --quick (patches/run_all_quick.log), byte identity (patches/byteid.py, byteid.log), Sagehen short run
  (patches/sagehen_short_p28.log).

## Messages and documents

Message rows (appendix.tex, user guide): one model, files outside the folder, TS6 outside the folder, restart with a
package that keeps state, TVK6/TVS6, GDAL's form, the METRES warning, the release-limit warning; the METRES "does not
apply" clauses removed. building.tex: side file row (GDAL's form, ESRI ASCII), METRES paragraph, band-unit table (datums,
quantity, URI). existing_model.tex: the one-model safeguard, files outside the folder, the restart condition, "several
models" removed from the later-start limits.

## Review response

1. (S2) METRES: the rule above (S lifted with a warning, N and M warned, F and X stop also with METRES), and the
   classifier extensions; code (BandMeta, headers, parser comment), docs (building.tex, appendix, user guide) and tests
   (geotiff_check table and ESRI ASCII cases, band_units.tsv) follow it.
2. (S3) A file named by several packages: `ExtRenumberPeriods` reads each package file once, by its resolved path
   (`gwutil::NormPath`), from its original lines, checks every package that names it, and writes it once. Test E36 (two WEL
   packages of one file, 32 days late: the file's period 1 is the old period 3, results as two copies). Before: renumbered
   twice (the reviewer's late_two_ref2).
3. (S3) A TS6 file named in two ways (`wel.ts`, `./wel.ts`): the shifted files are keyed by their resolved path, so each is
   shifted once. Test E37 (first time 0 becomes -32, one shift header). Before: shifted twice (late_ts_dot).
4. (S3) Georeferencing in a side file: a side file that holds GeoTransform, SRS or GCPs, in any form or case, stops ("holds
   georeferencing ..., which GDAL may take in place of the raster's own: rewrite it with gdal_translate"); also for an ESRI
   ASCII grid. Test: geotiff_check "a side file with georeferencing"; the reviewer's georef.py file stops.
5. (S4) Paths: a package file named by an absolute path inside the simulation folder is named there relative to it (row
   rewritten, no copy); a TS6 file named so is rewritten relative in the package file's OPTIONS (a TS6 line read through an
   OPEN/CLOSE file stops) and shifted. A package file in a folder that holds Raven's output folder (left out of the copy)
   stops naming that cause. Tests E32a, E32c (as the relative twins), E32c2 (outside: stops), E32e (output folder).
6. (S4) A metadata value that starts with a line end (GDAL writes it so) is read: an element whose content up to the next
   `<` is its own closing tag is a text element. Test: GDAL_METADATA case "an item whose value starts with a line end";
   the reviewer's gdalforms.py: every GDAL-written single-band form agrees with GDAL or stops for a unit (ft) or several
   bands (patches/review_gdalforms_p28.log).
7. (S4) CRLF side files: the stop names "CRLF line ends; GDAL writes LF". Test: geotiff_check CRLF case.
8. (S4) Message rows: "its band scale in GDAL_METADATA / in ....aux.xml is 0 (every value would be the offset)", "GeoTIFF
   file / raster" where an ESRI ASCII side file can give the message, the METRES rows, the georeferencing and no-NODATA rows.
9. (S4) ESRI ASCII without NODATA_value: aligned with GDAL (every number is a value; -9999 cells reported in a warning).
   No test model or workshop grid lacks the line (all write NODATA_value -9999), so no output changes. Test: geotiff_check
   "ESRI ASCII without NODATA_value".
10. Restart wording: "the run starts the MODFLOW 6 model from the heads of :GWHeads (a hotstart), which set only the heads
   ... Remove :GWHeads from the .rvc file (every package then starts from its input), or, to continue an earlier run,
   simulate the whole period in one run"; this also fits a spin-up start at :MF6StartDate with :GWHeads.
