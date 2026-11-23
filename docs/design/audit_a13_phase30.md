# Audit A13, phase 30: code and its tests

Issues: CB13-1 to CB13-5, IB13-1 to IB13-7, and the Workshop 3 generator guard of SV13-1. Base: code soil-zone 56e385b,
extra d2eb5f3. Reference build: wt/rel28_Raven.exe. Ground truth: mf6 6.8.1 (sources and libmf6 in
tools/mf6bin/mf6.8.1_linux), GDAL 3.12.2 through rasterio.

Rule of this round: what Raven cannot reproduce exactly it refuses with a clear message; what MODFLOW handles exactly
Raven does not refuse.

## CB13-1: READARRAYGRID

`ExtRenumberPeriods` treats a package with `READARRAYGRID` in its OPTIONS like one with `READASARRAYS`. In mf6 6.8.1
`GridArrayLoadType%rp` (Mf6FileGridArray.f90) resets only NBOUND and the read flags at a period block, so an array a later
block leaves out (an AUX array driving AUXMULTNAME, for example) keeps its earlier values. A later start is therefore safe
only when at most one period block comes before Raven's start, and stops otherwise ("its period blocks carry earlier
settings forward"). Test E38 (input_checks.py): the audit's well package (q in periods 1 and 2, MULT in period 1 only),
Raven 32 days late, stops. Before: the run ended "Successful" with the wells pumping 0 instead of 4,500 m3/d.

## CB13-2: HFB6 and CSUB6

`hfb_rp` (gwf-hfb.f90) and `csub_rp` (gwf-csub.f90) read a new list when a period block is given and otherwise reuse the
last one: list-package semantics. Both are added to the `latest` table of `ExtRenumberPeriods`, so the block in effect at
Raven's start becomes period 1. CSUB's own state on a hotstart is still refused by `ExtRestartState`. Test E39: HFB6 and
CSUB6 (STO SS 0) with a PERIOD 1 block, Raven 32 days late: runs, and the working copy's period 1 holds each block.
Before: "the period data of HFB (HFB6) cannot be renumbered safely".

## CB13-3 and CB13-4: paths inside the model's files

New `ExtLocalizePaths`, called at the end of `ExtLocalizeFiles` (before anything reads the working copy). It reads every
file of the working copy that MODFLOW reads: the simulation file, the TDIS file, the model name file, every kept package
file, and the solution files (SOLUTIONGROUP rows) and FILEIN files they name, in turn. Each path is rewritten in the
working copy where the copy would resolve it otherwise than the simulation folder:

- OPEN/CLOSE: a `../` path that leaves the folder, or a relative path to a file the copy lacks, is named by its absolute
  path and read in place (by MODFLOW and by `BlockLines`); an absolute path outside the folder stays; one inside it is
  named relative to it.
- FILEIN and solution files outside the folder are copied in as `raven_copy_f<n>_<name>` (one copy per original), so that
  the paths they name are rewritten too and a TS6 series can be shifted on a later start. An absolute path inside the
  folder is named relative to it. This lifts the former stop for a TS6 file outside the folder on a later start (E32c2).
- Output files (FILEOUT anywhere, also in an OBS6 `BEGIN CONTINUOUS FILEOUT` line, and the name file's LIST) named by an
  absolute path or one that leaves the folder are written in the working copy: at their place relative to the folder
  when they lie there, else as `raven_out_<n>_<name>`. Each is named in GWModelSummary.txt ("output file : ... written
  as ..."), with counts of the files copied and the OPEN/CLOSE files read in place.

Only the path word changes (in quotes if it holds a blank or comma); line ends are kept. Rows that other code checks
(TIMING, MODELS, EXCHANGES of the simulation file; PACKAGES of the name file) are left to it, except an OPEN/CLOSE line.
A file that does not exist is left to MODFLOW's message (a `../` path then appears as its absolute path).

Tests E40 and E40b: the wells' period-1 rows by `OPEN/CLOSE ../shared/wel_p1.txt`, a TS6 series and OBS6 observations
named `../shared/...`, the observations written to `../obs_out.csv`. Raven at the model's time zero and 32 days late:
GWBudget.csv and Hydrographs.csv identical to the twin with the files in the folder; the observations are written to
`out/mf6/raven_out_1_obs_out.csv`, nothing beside the user's folder. The same model run by libmf6 6.8.1 from its own folder
ends normally (E40b). Before: Raven stopped with MODFLOW's "Could not open ../shared/wel_p1.txt". E41: the OC head file
named by its absolute path in the simulation folder, over a file of the user's, and the budget file by `../budget_out.cbc`:
both written in the working copy, the user's file unchanged, results identical to the example's. Before: the user's head
file was overwritten (734,240 bytes).

## CB13-5: transport, energy and particle-tracking models

`ExtReadSimulation` stops first on any model of the MODELS block other than GWF6 ("holds the model ... (GWT6) beside its
groundwater-flow model; Raven drives one MODFLOW 6 groundwater-flow model and does not solve transport, energy or
particle-tracking models with it ... run transport or particle tracking separately"). The check for more than one
solution follows the one-model check and is reworded for what can still reach it, a second SOLUTIONGROUP row beside the
one model (edge.py EE06: "has 2 solutions in its SOLUTIONGROUP block (IMS6 ext.ims, IMS6 other.ims) for its one model").
The manual's Safeguards list both stops. Test E42. Before: a GWT model beside the flow model stopped with the exchange text.

## IB13-1, IB13-5, IB13-7: band units

- Feet fused with a datum are read on the whole normalised text and on each word between blanks, commas and brackets,
  digits kept (`BUFeetDatum`: ft, feet, foot, usft, usfeet, usfoot, then a datum): `ftNAVD88`, `ftNAVD 88`,
  `ftNAVD88 geoid`, `usftNAVD88`, `elevation (ftNAVD88)` are class F.
- Other lengths: inch, mile, yard and fathom words of the listed languages (Portuguese, Polish, Czech, Hungarian, Finnish,
  Scandinavian, Romanian, Greek, French, Italian, Spanish, German, Dutch, Russian), verst and arshin, micron, rod, perch,
  league, kft; ESRI `Link_*`, `Chain_*`, `Rod_*`; CJK 尺, 市尺, 寸, 丈, 里, 間. Scaled forms: a number with an exponent
  (`m 1e-2`, `m E-2`), an ordinal (`100ths`), the factor words Faktor, facteur, fattore, fator, and unit/units next to a
  number.
- Metre forms: `;`, `/`, `-`, `_` and a bracket without a blank between a metre form and its datum (`m(NAVD88)`,
  `m-NAVD88`); a metre-datum form in brackets (`metros (msnm)`); a geoid model after a datum (`m NAVD88 GEOID18`); "over" as
  "above"; the datums NAVD, NGVD, EVRF2000/2007, DHHN92/2016, NHN2016, LN02, ü. A., Bpv, NGF-IGN69, t.o.v. NAP, N60, DNN,
  AHD71, CD, chart datum, OSGM15, Ordnance Datum, geoid, WGS84, TP; m.ö.h., m o.h., mt, mts, mtr, mtrs; quantity words in
  the listed languages and elev, z, DEM, DTM, DSM, read in normalised form, also joined by `_` (`Elevation_m`).

band_units.tsv gains 123 rows; 24 rows that were class S move to M or F (the quantity words of other languages, `mil`,
`micron(s)`, `市尺`). The audit's lists, before/after (texts not in the class the audit expects): fused 13/1, other
lengths 88/17, metre texts 77/16. The texts left are outside the issue's lists and stay class S (they stop unless METRES).

## IB13-2: the time of day of :MF6StartDate

`:MF6StartDate yyyy-mm-dd` takes a time of day `hh:mm[:ss]` after a blank or a T. The date must be exactly ten
characters; any other text stops ("is not a date yyyy-mm-dd, with a time of day hh:mm:ss after it if the model's time
zero is not at midnight"). The time of day is subtracted from the offset of Raven's start (unchanged when it is
midnight), and a start before it stops. Tests E43 to E43d. Before: the time was dropped, shifting time zero by 12 h.

## IB13-3: ESRI ASCII side files with georeferencing

`BandMeta` takes `georef` (default true); `CGWRaster::Read` passes false for ESRI ASCII, whose GDAL driver takes the
geotransform from the header and the CRS from the .prj only. The GeoTIFF stop is kept. geotiff_check.py: an ESRI ASCII side
file with a GeoTransform, and one with an SRS as GDALSetProjection writes it, read with Scale and Offset as the grid scaled
by hand; a GeoTIFF side file with a GeoTransform stops. The audit's ascsrs.py case now reads (Raven OK, GDAL CRS None).

## IB13-4: GDAL-written xml: metadata domains

`GXElement` follows CPLSerializeXMLNode: comments and literals (`<!DOCTYPE ...>`, internal subset in brackets) on their own
line at an element's indentation are passed over; processing instructions `<?name attributes?>` are read as elements named
`?name`; mixed content is read as GDAL writes it (a text, a line end before the first child, a text after a child, the
closing tag at its indentation after the last text). This supersedes the A12 statement that GDAL writes no comments or
declarations. geotiff_check.py: the five side files GDAL 3.12 wrote for the audit (comment, XMP processing instructions,
mixed text, DOCTYPE, band-level domain) read as GDAL reads them (0.01 x + 5); a comment indented otherwise still stops;
a commented-out Scale on its own line, as GDAL writes a comment, gives the file's values, as GDAL. The audit's real.py
cases: all 5 stopped before, all read 15 (as GDAL) after.

## IB13-6: surplus tokens

`GWCommandArity` gives each .rvg command's most tokens (by its form where it has several: `:StreamPackage`,
`:GridRefinement`, `:SoilZone CONCEPTUAL`); one `GWMaxTokens` call before the dispatch checks every command, and the
per-command calls are removed. List commands (`:RavenTakesOver`, `:KeepPackages`, `:MF6CRS`, `:InputCRS`, boundaries,
`:SoilZone PHYSICAL`) are not limited. `:MF6StartDate` takes the date and an optional time. Tests E44 to E44d.

## SV13-1: Workshop 3 generator guard

build_tutorials.py checks that the LAG run's release warning names Sy dh ("than MODFLOW stores for the rise (Sy dh)") and
the depth-class run's the room ("than the room left in the top cell"), and writes the depth-class warning as the excerpt
`t3_warn_classes.txt` for the workshop text (phase 31).

## Review response

- **F1 (S3), OPEN/CLOSE files were not searched.** `ExtLocalizePaths` now reads each OPEN/CLOSE file of a block other
  than GRIDDATA (not one marked binary) as that block's own lines, with the same rules (FILEIN, FILEOUT, solution rows, the
  name file's LIST). When it names a path to rewrite:
  - one inside the folder is rewritten in Raven's working copy, which is Raven's own copy;
  - one outside the folder is written to the working copy as `raven_copy_o<n>_<name>`, and the OPEN/CLOSE line is
    pointed at it.
  The user's file is never written. Tests: E41b (OC OPTIONS through `OPEN/CLOSE ../shared/oc_opts.txt`) and E41c (the same
  file inside the folder). Both fail on rel28 (patches/review_tests_on_rel28.log) and pass with this build
  (patches/review_tests_on_p30.log). Before the fix, the reviewer's case A overwrote userfile.hds.
- **F2 (S4), unit words and ordinals.** Punctuation now splits the text into groups. `unit`/`units` counts as a scale
  word only next to a number of its own group: `0.1 units`, `units of 0.1 m`, `0.1 m units`. An ordinal counts only as
  `<n>th(s) of` or `in <n>ths`. The reviewer's four texts are class S rows of band_units.tsv: `metres, NAVD 1988 (units)`,
  `Elevation units: m, NAVD 1988`, `m above 19th century datum` and `height in m, epoch 2010, units`. Two further X rows
  were added: `in 100ths of a metre` and `m (in 100ths)`. The reviewer's t1.txt list was rerun with the band-unit driver
  built from this source: only those four texts change class (S to unplaced text). Every scaled form of the table stays X.
- **F3 (S4), binary FILEIN targets.** Only the text FILEIN types are read in turn or copied in: TS6, TAS6, OBS6, TVK6,
  TVS6, ATS6, HPC6, MVR6, MVE6, MVT6, GNC6 and NCF6, the FILEIN records of the mf6 6.8.1 dfns other than NETCDF. Any other
  FILEIN target (NETCDF) is never opened. A path to it that leaves the folder is written as its absolute path. No run
  test: the test models have no NETCDF input.
- **F4 (S4), quotes.** `MF6Word` writes a path that holds `'` in double quotes and one that holds `"` in single quotes.
  A path that holds both stops the run with a message. MODFLOW 6.8.1 reads either quote (`URWORD`, InputOutput.f90: a
  word that begins with char(34) or char(39) ends only at the same character), and so does Raven's own reader (`Words`).
  No run test: checked by reading the code.
- **F5 (S4), a missing TS6 file.** `ExtRenumberPeriods` first checks that each TS6 file exists, and stops with "names the
  time-series file <path>, which does not exist". A missing file named by a `../` path is written by its absolute path
  with `.` and `..` removed (`LexPath`), so the message and MODFLOW's own name the file where the user would look for it.
  Test: E41d, which fails on rel28.

## Manual and user guide

- existing_model.tex: the time of day of `:MF6StartDate`; HFB, CSUB and READARRAYGRID in "Starting later"; the paths inside
  the model's files (Safeguards paragraph on OPEN/CLOSE); the Safeguards bullets on transport models and on several
  solutions; the TS6-outside-the-folder refusal removed from the later-start bullet.
- building.tex: GDAL's xml: domain content; ESRI ASCII side-file georeferencing ignored (GeoTIFF only stops); the band-unit
  text and Table tab:bandunits: feet fused with a datum and its year (`ftNAVD88`, `usftNGVD29`, also as a word of a longer
  text), the other lengths of the listed languages with micron, rod, perch, league, kft, ESRI `Link_`/`Chain_`/`Rod_` and the
  Chinese and Japanese units (named, not printed: the manual is built with pdflatex), the scaled forms (power of ten,
  ordinal, factor words, unit(s) next to a number), the metre forms `m.ö.h.`, `m o.h.`, `mt(s)`, `mtr(s)`, the datum
  separators `; / - _` and a bracket without a blank, the new datums and geoid models, "over", and the quantity words of the
  listed languages, `elev`, `z`, `DEM`, `DTM`, `DSM` and `_`.
- appendix.tex: the `:MF6StartDate` syntax row; message rows for the transport-model stop, the several-solutions stop, the
  malformed `:MF6StartDate`, the working-copy copy failure; the renumbering row with "its period blocks carry earlier
  settings forward" and READARRAYGRID; the surplus-value row for every .rvg command; the side-file georeferencing row
  limited to GeoTIFF.
- User guide: the `:MF6StartDate` row; the side-file sentence (ESRI ASCII georeferencing ignored, xml: domain content read
  past); band-unit examples; later starts (HFB6, CSUB6, READASARRAYS/READARRAYGRID); a bullet on paths inside the model's
  files; the limits line (transport models); troubleshooting rows for the new stops and the one surplus-value check.
- verification.tex: E32c2 and rows for E38 to E44.

## Tests against the reference build

E41 reads the user's head file as bytes (with rel28 MODFLOW overwrites it with a binary head file, which made the text read
raise instead of report). The new and changed existing-model checks (E32c2, E38 to E44d), run on wt/rel28_Raven.exe
(patches/new_tests_on_rel28*.log): E32c2, E38, E39, E40 (both starts), E41, E42, E43, E43b, E43c and E44 to E44d fail; E40b (MODFLOW 6 alone) and E43d (midnight written out, the same time zero) pass, as they should with either build. With this build all pass. geotiff_check.py built from the base source (56e385b) with rel28
(patches/geotiff_check_on_base.log): 155 checks fail, among them every new band_units.tsv row whose class changed, the five
GDAL-written xml: domain side files, the commented-out Scale, and the two ESRI ASCII side files with georeferencing; the
same checks pass with this build.

## Byte identity

tmp/byteid.py (wt/p28/patches/byteid.py with this phase's paths): runs without groundwater against base Raven (Liard 5 years and a 1-year hotstart, the small model with and without tracers in three chained parts, the seven benchmarks, an ensemble) and coupled runs against rel28 (Liard CONCEPTUAL 180 d, the existing model 31 d, PHYSICAL + RICHARDS, an unconverged CONCEPTUAL run, with their mf6 folders): 0 comparisons with differences. The coupled examples name no path outside their simulation folders, so the working copy and GWModelSummary.txt are unchanged.

## Test run

run_all --quick with this build (patches/run_all_quick_final.log): 63 steps passed, 0 failed, 2 not run (as in every quick run);
input_checks, geotiff, edge, ext_guards and the tutorials check among them. The manual builds in a scratch copy.
