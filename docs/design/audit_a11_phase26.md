# Audit A11, phase 26: code and its tests

Issues: CB11-1, CB11-2, CB11-3, SV11-2 (warning), IB11-1 to IB11-9, MT11-6. Base: code soil-zone 981da06, extra
c1835be. Reference build: wt/rel24_Raven.exe. Ground truth: mf6 6.8.1 (program and sources in tools/mf6bin/mf6.8.1_linux),
GDAL 3.12.2 through rasterio 1.5.2.

## CB11-1, CB11-2: one block reader for every MODFLOW text file

### The readers
Every place Raven reads MODFLOW 6 text now goes through `BlockLines` (GWExternal.cpp):

| Reader | File | Blocks read through OPEN/CLOSE | Writes a working copy |
|---|---|---|---|
| ExtReadSimulation | mfsim.nam, model name file | all | no |
| ExtWriteSimFile | mfsim.nam (CONTINUE) | all (scan) | yes, from the raw lines (the OPEN/CLOSE line stays valid; CONTINUE after it) |
| ExtRewriteTDIS | TDIS | all: OPTIONS (TIME_UNITS, START_DATE_TIME, ATS6), DIMENSIONS, PERIODDATA | yes, rewritten from the expanded lines: options and periods inline |
| single-period STO check (in ExtRewriteTDIS) | STO | PERIOD | no |
| ExtEditMover | MVR | all: OPTIONS, DIMENSIONS, PACKAGES, PERIOD | yes when it removes movers: rows inline, the OPEN/CLOSE line kept as a comment |
| ExtRenumberPeriods | every kept package | OPTIONS (TS6 FILEIN, TAS6, TVK6/TVS6, READASARRAYS) | yes, from the raw lines (an OPTIONS OPEN/CLOSE line stays valid; PERIOD blocks are moved as written) |
| ExtShiftTimeSeries | TS6 files | all: ATTRIBUTES, TIMESERIES | yes: rows inline, shifted |
| ExtEditNameFile | model name file | PACKAGES | yes: rows inline (as before) |
| ExtProbe | model name file (NEWTON) | all | no |
| ExtBuild (stream package AUXILIARY) | stream package | OPTIONS | no |

Not read by Raven, so not concerned: OBS6 files, TAS6/TVK6/TVS6 files themselves (a later start that needs them stops),
IMS, DIS/NPF/IC (read from MODFLOW's memory). `ExtReadOpenClose` is removed.

MODFLOW's rule, checked in the 6.8.1 sources: LoadMf6File.f90 (`supportOpenClose = blockname /= 'GRIDDATA'`, every IDM
block: TDIS, name files, package OPTIONS and PERIOD blocks of IDM packages), gwf-mvr.f90:306/705/819/888 (MVR OPTIONS,
DIMENSIONS, PACKAGES, PERIOD), TimeSeries.f90:1100/1239 (ATTRIBUTES, TIMESERIES). With the real mf6 6.8.1: TDIS OPTIONS
through OPEN/CLOSE (`TIME_UNITS seconds`) gives "SIMULATION TIME UNIT IS SECONDS" (auditor's check), and an STO PERIOD
block through OPEN/CLOSE holding STEADY-STATE gives "STRESS PERIOD 1 IS STEADY-STATE"; period blocks beyond NPER are
ignored by mf6 (used by E29).

`BlockLines(file, dir, only, where, label)`: `only` limits the expansion to named blocks (others are returned as written,
so that a package's PERIOD blocks, whose array control records may hold OPEN/CLOSE after the block's first line, are not
misread); `where` gives "file (line n)" for messages, the external file's lines named by the file name as the model writes
it. The OPEN/CLOSE line is returned as the comment `# OPEN/CLOSE ...   # its rows written below by Raven`, so a working
copy written from the lines is valid for mf6 with the rows in place. New stop: an OPEN/CLOSE file marked binary in a block
Raven reads (Raven reads text).

### Second guard
After the probe initialises the model, `TDIS/ITMUNI` (0 undefined, taken as days, 1-5 seconds to years) must give the
factor Raven read (`_extTf`), and `TDIS/INATS` must be 0 (no ATS); otherwise the run stops ("MODFLOW 6 reads the time unit
of the model as ..., Raven read ... from the TDIS file ..."). This cannot be reached by input once the reader is right; it
was tested on a mutant whose TDIS reader skips OPEN/CLOSE in OPTIONS (patches/guard_time_unit_mutant.log: the mutant stops
with the guard on E24's model; rel24 does not stop).

### Tests (tests/input_checks.py), one per reader; each fails with rel24 and passes with p26
(patches/input_checks_new_rel24.log, input_checks_new_p26.log)

| Test | Reader | rel24 | p26 |
|---|---|---|---|
| E24 | TDIS OPTIONS (feet and seconds model, TIME_UNITS in OPEN/CLOSE) vs inline twin | summary "feet, days", results differ | identical to the inline twin, "feet, seconds" |
| E25 | MVR PACKAGES through OPEN/CLOSE naming the stream package | "Successful Simulation" | stops: "sends water through the model's water mover" |
| E26 | TS6 FILEIN in WEL OPTIONS through OPEN/CLOSE, later start | not shifted | shifted, identical to the inline twin |
| E27 | TS6 file TIMESERIES rows through OPEN/CLOSE, later start | stops (rows in another file) | shifted, identical to the inline twin |
| E28 | stream package OPTIONS through OPEN/CLOSE, two AUXILIARY lines | no warning | warning, identical to the unmodified model |
| E29 | STO PERIOD (STEADY-STATE) through OPEN/CLOSE, NPER 1 | stops: model ends before Raven's run | steady model stretched over the run |
| (existing) E13, E15, E19-E21 | name files, mfsim.nam, ExtWriteSimFile, ExtEditNameFile | | still pass |

### Two-way package stop
No input was found that reaches it once every reader follows MODFLOW: it needs a multi-type package that mf6 reads from
the model's name file and Raven does not. Raven and mf6 now read the same PACKAGES rows (same comment and word rules, same
OPEN/CLOSE rule; a nested OPEN/CLOSE or one after the first line stops before mf6 runs), and a second PACKAGES block or a
row Raven reads that mf6 does not gives the opposite case, which the first check ("MODFLOW 6 has no package named ...")
reports. The stop stays as a guard; no test was added.

## CB11-3: CSUB storage booked as MODFLOW books it
CSUB (gwf-csub.f90, csub_bd) adds four model-budget terms: CG_STOR, CELL_WCSTOR (nodes) and, with interbeds, STORAGEE,
STORAGEI (ninterbeds). ExtConnect lists the CSUB6 packages; the connect step reads those arrays from memory
(`<model>/<CSUB name>/...`, NINTERBEDS from memory) and the balance adds them to the storage flow and to the gross flow,
entry by entry, exactly as rate_accumulator does. GWBudget's "storage release" therefore includes CSUB storage;
GWModelSummary.txt adds "storage in balance : STO, CSUB (CSUB)"; the manual's package table gets a CSUB row.
- Converged (E30, 2 days): rel24 MF6 balance error up to 0.81 % (2.47 % on day 4 of the 5-day run); p26 4e-8 %, no
  warning (MODFLOW's discrepancy 0.00 %).
- Unconverged (patches/csub_unconverged.log, the auditor's csub_unc set-up, 5 days): rel24 balance error -87,941 ...
  -393,310 m3/d and 722,595 m3 withheld; p26 at most 0.003 m3/d and 0.003 m3 withheld.

## SV11-2: warning under KINEMATIC
GWVadoseModel.cpp: under KINEMATIC the first slowed release (only the room left in the top cell can hold it back, since
theta - theta_r <= Sy) writes "a rising water table met more mobile water in an unsaturated column than the room left in
the top cell above the water table; the column releases at most that room per step and the rest in the next steps". The
code comment on when the limit binds now names the smaller of Sy dh and the room (SV11-1's code part).
Test: soilzone/test_vz_kinematic.py K10 (the auditor's kwroom KINEMATIC 0.2 90 1.6 4 set-up): rel24 no warning (FAIL),
p26 warning, identities 0.

## IB11-2 to IB11-7: band units, closed world
`GWGeoTIFF::BandUnit` returns BU_METRE when the whole text, normalised, is one metre form; BU_NONE for no unit (read as
metres, as before); otherwise the run stops. Normalising: full-width ASCII, no-break (U+00A0, U+2007, U+202F) and
ideographic spaces as blanks, trim, runs of blanks as one, lower case (Greek capitals with and without tonos, accents
removed, so ΜΕΤΡΑ and ΜΈΤΡΑ are μέτρα), surrounding (), [], {} removed. Metre forms: the metre words of the former table,
m, the sea-level abbreviations (masl, m asl, m a.s.l., m.a.s.l., mamsl, m amsl, m a.m.s.l., moh, m.o.h., möh, m ö.h.,
mü, müNN, m ü. NN, m ü.NN, m ü. M., m ü.M.), Cyrillic м, мБС, м БС, the CJK metre words, and EPSG:9001 /
EPSG::9001 / EPSG 9001 / urn:ogc:def:uom:EPSG::9001.

The table of other lengths now only chooses the message: a text with another length unit among its words and no metre
form (BU_LENGTH; also EPSG length codes other than 9001 as the whole text, short ids as the whole text, CJK prefixed metres
joined across blanks) gives "its elevations are in X (the band unit, ...)"; any other text (BU_TEXT) gives "its band unit
is 'X' (...), which is not one of the metre forms ...: if its elevations are in metres, confirm it by writing METRES after
the file name (:LandSurface or :BedrockSurface <file> METRES); otherwise convert the values to metres and set the band
unit to m". Added to the lists for that message: case forms (футах, футів, дюймах, ярдах, милях, stopach, stopách, lábban,
Füße), prefixes (decí, decá, quiló, hectô, desi, sentti, мілі), CJK (釐米, 公釐, 百米, 十米, Japanese and Korean prefixed
metres).

**How a user confirms or converts.** No new dependency: an optional word after the file name, `:LandSurface dem.tif
METRES` (and `:BedrockSurface`), confirms that the elevations are in metres whatever band unit text a GeoTIFF gives (any
other word there stops). It is per file, explicit, and does not lift a unit of another length (that still stops, with
"METRES after the file name does not apply to a unit of another length"): such a raster must be converted (gdal_calc.py,
gdal_edit.py -units m, or any GIS). ESRI ASCII grids carry no unit; METRES is accepted and changes nothing.

Effect on the cases: every text of the auditor's units11.txt that is not a whole metre form now stops (65 with the
"elevations are in" message, the rest with the confirm message); "5 km grid, elevation in m", "ETRF90 (EPSG:9060) height
in m", "m/s", "m²", "kg m-2", scales with ·, ÷, NBSP or "times" all stop with the confirm message (IB11-4/5/6); ΜΕΤΡΑ,
ΜΈΤΡΑ, мБС are metres (IB11-7). band_units.tsv (first version): 440 texts, classes M (35), N (3), S (402), table-driven (after the review: 509 texts, M 115, N 3, S 156, F 165, X 70); on the reference
rule 240 of the S texts were read as metres (162 silently, 78 with a warning): patches/band_units_refsources.log.
The 24 workshop GeoTIFFs still read (no change).

Manual: building.tex (GeoTIFF table: units, new "side file" row, stop list, the Band unit paragraph, tab:bandunits),
appendix.tex (messages, the :LandSurface/:BedrockSurface rows), inputs_outputs.tex, existing_model.tex; user guide
(rasters, command table, messages).

## IB11-1: GDAL's side file
`GWGeoTIFF::Read` reads `<file>.aux.xml` when present (16 MB at most) and applies it as GDAL 3.12.2 does, verified with
rasterio on hand-made side files: in `PAMRasterBand band="1"` (element names in any case), a Scale or an Offset replaces
both of the file's (the missing one is 1 or 0); a UnitType that is not empty replaces the band unit; a NoDataValue
replaces GDAL_NODATA. Raven is stricter than GDAL where GDAL would silently take 0: a Scale/Offset/NoDataValue that is not a
number stops, and so does a side file that is not a PAM dataset. A file written with PROFILE=BASELINE keeps its
georeferencing only in the side file; Raven does not read that and stops ("no georeferencing").
Fixtures (tools/dev/make_geotiff_fixtures.py, all previous fixtures byte-identical): aux_geotiff_dm.tif (PROFILE=GeoTIFF,
scale 0.1 offset 50 unit m in the side file, against its twin, also in a Raven run), aux_geotiff_ft.tif (unit ft in the
side file: stops; the auditor's case read 1000 m), aux_baseline_dm.tif (stops), aux_over_dm.tif (side file Scale 0.2 and
UnitType m over a file with scale 0.1, offset 50, unit ft: values 0.2 v, as GDAL). geotiff_check.py adds side files written
by hand (Scale alone, Offset alone, lower-case names, UnitType ft, empty UnitType, a non-number, not a PAM dataset) and the
METRES cases; the fixture unit_height_meta.tif ("height") is now refused, and read with METRES (reader and Raven run).

## IB11-8: no area in the file's own coordinates
RingFromJSON tests the area before converting a projected file to longitude/latitude, with a tolerance of 1e-9 of the
ring's extent squared (was 1e-12, after conversion). geomtest: col_ulp (three vertices on one meridian but for one ulp,
the A10 reproduction) and col_utm (three collinear UTM vertices) are left out; thin_utm (a UTM sliver 100 m by 1 mm) is
kept. Reference sources: col_ulp and col_utm read (FAIL); p26: all pass.

## IB11-9
GWID takes the role: ":OverlapWeights ...: the cell number '...' is out of range", "the HRU ID '...'"; a non-number reads
"the ID '...' is not a whole number" (appendix updated). E18 and E22 still match.

## MT11-6
The antimeridian test A1 is AM1 (input_checks.py, tests/README.md).

## Byte-identity and tests
See patches/byteid.log and patches/run_all_quick.log. Coupled runs of the examples have no OPEN/CLOSE, CSUB or GeoTIFF band
unit, so no coupled difference is intended.

## Left open
- Georeferencing kept only in a side file (PROFILE=BASELINE) is refused rather than read.
- A user can still confirm a text such as "elevation in feet, converted" with METRES only if it also names a metre form;
  texts with another length and no metre cannot be confirmed (intended).
- The two-way package stop has no input that reaches it (see above).

## Review response
1. **(S2) Named CSUB.** MODFLOW 6 keeps the package at `<model>/CSUB` whatever the name file calls it
   (gwf-csub.f90:337, `set_names(1, name_model, 'CSUB', 'CSUB', ...)`). The connect step now looks up `CSUB` first and
   the name-file name second, as ExtProbe does for STO and DIS. Test E30b (`CSUB6 gwf_liard.csub subsid`): MF6 balance
   error 4e-8 %, "storage in balance : STO, SUBSID (CSUB)". On a build without the fix, and on rel24, it fails
   (patches/review_fixes_prefix_mutant.log, input_checks_new_rel24.log).
2. **(S3) CRLF in the rewritten mover.** ExtEditMover strips the carriage return from every line before it rewrites the
   file (LF line ends in the copy), so no carriage return is left inside a line it comments out or annotates. Test E25b: an
   MVR with CRLF line ends whose PACKAGES OPEN/CLOSE file (CRLF) lists WEL_PUMPS, MAW_1 and RCH_MODEL (taken over); the run
   completes and the copy has no carriage return inside a line; without the fix MODFLOW stops (return code 2).
3. **(S3) Common metre texts.** The closed vocabulary now has vertical datums after a metre form (alone, after a comma, in
   brackets, fused to m or m.; optionally ending in "geoid"): MSL, AMSL, ASL, a.s.l., a.m.s.l., above (mean) sea level,
   AHD, AOD, ODN, NAP, +NAP, TAW, NN, NHN, ü. NN, ü.NN, über NN, ü. NHN, ü.NHN, über NHN, ü. M., NN2000, RH2000, DVR90,
   NAVD88, NAVD 88, NGVD29, NGVD 29, CGVD2013, CGVD28, EGM96, EGM2008, s.l.m., slm, n.p.m., npm, s.n.m., snm, n. m., n.m.,
   ellipsoidal, above (the) ellipsoid; a metre form in brackets after a metre word ("meter (m)", "metre (EPSG:9001)");
   quantities before a metre form in brackets or after "in" (elevation(s), height(s), altitude, elevation/height above
   (mean) sea level, height above ellipsoid, ellipsoidal height, orthometric height); and "m.". All 89 texts of the
   review's list (review/drv/rw.txt) are in band_units.tsv: the 82 metre texts as M; "metric", "geopotential metre",
   "gpm", "m²", "m/s" as S; "m**2 s**-2" as X; "dam" as F. tab:bandunits lists the datums and quantities.
4. **(S4) Scaled metres.** A new class BU_SCALED (X in band_units.tsv): a metre text with a part or multiple ("m (in
   thousands)", "tenths of a metre", "m (in 1000s)"), a number with a factor sign or word (*, /, ^, ×, ÷, ·, x0.1, scale,
   scaled, times, multiplier, factor, divide, multiply, per, "of" after a number), or a number and a metre form as the whole
   text ("0.1 m", "1000 m"). It stops with "a metre with a number or a part (a scale, factor or exponent), so the values are
   not plain metres: write the elevations unscaled in metres, or give the scale as the band's scale and offset", and
   METRES does not lift it. Other numbers (datum years, resolutions: "m (NAVD 1988)", "SRTM 30 m, elevation in metres")
   stay in the liftable class. "()" and "[]" are a text (stop), not "no unit".
5. **(S4) Side-file reader.** Comments are removed; a UTF-8 byte-order mark stops the run (see below); a side file that is
   not XML, has no closing </PAMDataset> or an unclosed PAMRasterBand (or element) stops with the reason; another XML
   document without a PAMDataset is ignored, as by GDAL; the band attribute is read with blanks around "=" as an integer
   (band="01" is band 1); the last PAMRasterBand of band 1 is read, as by GDAL; entities (&amp; &lt; &gt; &quot; &apos;
   &#N; &#xN;) and CDATA are decoded; an element with no text (or only blanks) counts as absent, as for GDAL (an empty
   Scale no longer stops); NoDataValue takes le_hex_equiv when given, as GDAL does (-10112 for the review's case). All 22
   cases of review/scripts/pam.py agree with GDAL 3.12.2 or stop (patches/review_pam_p26.log).
   **Byte-order mark, a deviation from the request:** GDAL 3.12.2 does not read a side file that starts with a UTF-8 BOM
   (rasterio shows scale 1 for the review's xml_decl_bom case, whose side file says 2). Stripping the BOM and reading the
   file would give elevations twice what GDAL and GIS programs show, without a message; Raven therefore stops, naming the
   byte-order mark ("remove it, or let GDAL write the side file again").
6. **(S4) Messages.** The METRES advice names the command being read and the file as the .rvg writes it
   ("(:LandSurface dem.tif METRES)"; the reader takes them from :LandSurface / :BedrockSurface); METERS is documented as an
   accepted spelling (manual, appendix, user guide, the parser's message); a unit text is shown with bytes that are not
   UTF-8, and control characters, as \xNN.
