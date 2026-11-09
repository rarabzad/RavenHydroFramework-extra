# Phase 12g: native GeoTIFF rasters, the EPSG longitude/latitude rule, rasters that cover no cell

Part of phase 12 of the round-4 audit (issue list: `spec/audit_A4/AUDIT_A4_issues_and_phases.md`): IB4-2 (EPSG codes
4000-4999 taken as longitude/latitude) and IB4-4 (a DEM or bedrock raster covering no cell is silently unused), and the
user's decision that `:LandSurface` and `:BedrockSurface` read GeoTIFF files with no external library (no GDAL, libtiff,
zlib or PROJ, at build or run time), everything in Raven's own C++11. ESRI ASCII grids are read as before.

## 1. GeoTIFF reader (`src/GWGeoTIFF.h/.cpp`)

**Placement.** A new module with no Raven dependencies (so the unit driver compiles it alone). `CGWRaster::Read` sends a
file whose name ends in `.tif`/`.tiff` (any case) to `CGWRaster::ReadTIFF`, which calls `GWGeoTIFF::Read`, applies the
CRS rules (section 3) and fills the same members the ESRI ASCII path fills (`_ncols`, `_nrows`, `_xll`, `_yll`, cell size,
NODATA, values row-major north row first). Sampling (`Sample`, `Valid`), the longitude/latitude range test
(`CheckLonLatRange`, moved out of `Read` unchanged) and the `:InputCRS` "looks like longitude/latitude" check of the caller
are shared, so a GeoTIFF and an ESRI ASCII grid with the same values give the same model.

**CGWRaster changes needed for GeoTIFF, with ESRI ASCII results unchanged.**
- The single cell size became `_dx`, `_dy` (GeoTIFF pixels may be rectangular; geographic DEMs often are). For ESRI ASCII
  both are `cellsize`, and `Sample`/`Extent` do the same floating-point operations as before (verified byte-identical).
- `_hasNodata`: a GeoTIFF without `GDAL_NODATA` has no NODATA value (every number valid, NaN never); ESRI ASCII keeps
  `-9999` by default, so `Valid` evaluates the same expression for it. A NaN `GDAL_NODATA` is the same as none (NaN pixels
  are invalid in both branches: `fabs(NaN - x) > 1e-6` is false).
- A size guard for both formats: at most 5e7 cells (400 MB of doubles). ESRI ASCII previously had none, so a header such as
  `ncols 1e6` ended in `bad_alloc`; valid grids below the guard read as before. GeoTIFF files over 1 GB stop before they are
  read. "Consistent with the grid guard": the grid stops at 5e6 cells per layer; a raster needs a few cells per model cell
  (each column averages 25 samples), so the raster guard is ten times the grid's, and a file at the pixel guard in 64-bit
  floats (400 MB) with overviews stays under the file guard.

**Supported.** Classic TIFF (42) and BigTIFF (43), II and MM; the first IFD for the image (GDAL writes overviews after it; a first
IFD flagged reduced-resolution or mask stops; the chain is followed for an internal mask, see Review responses); strips (`RowsPerStrip` default = image height, a shorter last strip) and
tiles (partial edge tiles, predictor over the tile width); compression 1, 5 (LZW, MSB-first, early change), 8 and 32946
(zlib stream with header check and Adler-32), 32773 (PackBits); predictor 2 (integer differences of the sample word in the
file's byte order, for any sample format, as libtiff does, so GDAL's `PREDICTOR=2` on floats works) and 3 (byte
differences, then byte planes most significant first: the samples come out big-endian whatever the file's byte order);
the predictor is ignored for none and PackBits, as libtiff ignores it; samples uint/int 8/16/32/64, float 32/64;
`SamplesPerPixel` 1 (planar configuration then irrelevant); photometric 0 or 1 (values used as stored). Sparse blocks
(offset and count 0, GDAL `SPARSE_OK`) are filled with NODATA, or stop when there is none.

**Decoders.** Inflate is a canonical-Huffman decoder bit by bit (the method of zlib's `puff` reference decoder, written
anew): stored, fixed and dynamic blocks; over-subscribed or incomplete codes refused except the single-code case DEFLATE
allows; distances checked against the output; output capped at the block size (a "zip bomb" cannot grow it), extra data
ignored, a short output is an error. LZW: table of 4096 entries with prefix/suffix/first/length, KwKwK case, code width
9-12 bits growing one code early (at 511, 1023, 2047), codes beyond the table refused, old-style (pre-5.0 libtiff,
LSB-first) LZW refused with its name. PackBits: literal and repeat runs, `-128` no-op, overruns refused.

**Georeferencing.** `ModelPixelScale` + first `ModelTiepoint`: `x_ul = X - I*sx`, `y_ul = Y + J*sy`; a negative y scale
(south-up) stops. `ModelTransformation`: accepted when the rotation/shear terms are within `1e-10` of the scale and
`a > 0`, `f < 0`; otherwise it stops. Tie points without a pixel scale (control points) stop. `PixelIsPoint`
(`GTRasterTypeGeoKey` 2): the tie point is the centre of the pixel, so the corner is half a pixel left and up
(`x_ul -= sx/2`, `y_ul += sy/2`), which is how GDAL reads it by default (`GTIFF_POINT_GEO_IGNORE=NO`) and how GDAL writes
it (the fixtures check that GDAL's and tifffile's PixelIsPoint files give the corner of the PixelIsArea ones).

**NODATA.** `GDAL_NODATA` (42113, ASCII): a number, or `nan`; for 32-bit float rasters rounded to float as GDAL does (and
values just beyond the float range taken as the largest float). Infinite pixel values are stored as NaN (never valid).

**Robustness.** Every offset and count is checked against the file size before use (`In(off,len)` with overflow-safe
arithmetic; value counts bounded by file size / type size; at most 4096 directory entries); missing required tags,
strip/tile counts below the number of blocks, zero or oversized tiles and too little data for the claimed image (by the
codec's largest compression ratio) stop before the raster is allocated. Every decoder writes at most the block size and
reads only its input. Fuzzing (unit driver `fuzz`) under `-fsanitize=address,undefined`: about 1.3 million damaged copies
of the fixtures (bytes changed anywhere or in the directory, cut, inserted, random after the header) and random decoder
inputs, no report; the test suite repeats 100 (quick) or 1,000 copies per fixture with the normal build.

**Clear stops.** Each message names the file and the reason, and says what to do (`gdal_translate -b 1 -co
COMPRESS=DEFLATE`, `gdalwarp`, resample): unsupported compression by name and code (JPEG, ZSTD, LERC, ...), more than one
band, photometric other than grey (palette, RGB, ...), unsupported bit depth/format (1, 12, float16, complex), rotation or
shear, south-up, control points, no georeferencing, geocentric model type, truncated/corrupt structure or data,
decompression errors (with the decoder's reason), size guards.

**Rejected.**
- Reading the file by seeking per block instead of loading it: lower peak memory, but the in-memory form makes every bound
  check one comparison and lets the fuzz test drive the reader from memory; the file guard caps the buffer.
- Accepting rotated rasters by sampling through the affine transform: the ESRI ASCII path and the "extent" checks
  (`CheckInputLonLat`, coverage) assume north-up; a rotated DEM is better warped once outside Raven.
- Supporting several bands by taking band 1: a multi-band file is usually not an elevation raster (RGB hillshade, a
  stack); a clear stop avoids silently using the wrong band.

## 2. IB4-2: EPSG longitude/latitude rule (`src/GWEPSGTable.h`, `GWGeom::GeographicEPSG`)

The range rule (every code 4000-4999, plus seven later codes) is replaced by a sorted table of the EPSG registry's
geographic 2D and 3D CRS codes (962 codes, deprecated ones included, EPSG v12.029 through pyproj 3.8.0 / PROJ 9.8.1),
searched with `std::binary_search`. 243 of the 878 codes in 4000-4999 are projected in this registry version (4647
ETRS89 / UTM 32N zE-N, 4839, 4087, 4026, ...); they now count as "not classified", so the file's coordinates decide, as
for any projected code that is not built in: with `:InputCRS` given by parameters they are accepted, without it the
message asks for the projection's parameters. Geocentric codes (4978, metres) are not in the table either.

Generator: `extra/tools/dev/make_epsg_geographic.py` (dev only, pyproj), its docstring the note; the header records the
registry and PROJ versions. Raven needs nothing at build or run time.

The GeoTIFF reader does not need the table: the key itself says geographic (`GeographicTypeGeoKey` with
`GTModelTypeGeoKey` 2) or projected (`ProjectedCSTypeGeoKey` with model type 1). With the model type missing, a
projected key wins, a geographic one alone means geographic. A projected raster's GeoKeys also hold its base geographic
CRS (GDAL writes 2048 = 4326 under a user-defined projection), which is why the model type decides.

## 3. GeoTIFF CRS against the run

The brief: a code present must agree with the run's expectation, `:InputCRS` when set, otherwise the ASCII rule
(longitude/latitude). Implemented in `CGWRaster::ReadTIFF`, mirroring the GeoJSON `"crs"` rule:
- geographic code: accepted without `:InputCRS`; with it, stop ("is in longitude/latitude (EPSG:n in its GeoTIFF keys),
  but :InputCRS is EPSG:m (...)");
- projected code without `:InputCRS`: stop, asking for `:InputCRS EPSG:n` or reprojection;
- projected code with `:InputCRS`: the same EPSG code (`CGWCRS::EPSG()`, new: the code `:InputCRS` was given by) is
  accepted; a different built-in code is accepted only if it is the same projection (`CGWCRS::Same`, so `TMERC` parameters
  equal to 32611 pass), otherwise stop naming both; a code that is not built in is refused when `:InputCRS` was given as
  another EPSG code (they differ), and accepted with a warning when `:InputCRS` was given by parameters (it cannot be
  compared; the coordinates are then checked by the existing "looks like longitude/latitude" test);
- user-defined (32767) or no code: no CRS information, the ASCII behaviour (range test or "looks like longitude/latitude").
  Documented in the manual and user guide.

## 4. IB4-4: raster covering no cell

**Decision: stop when a given raster covers no active column; warn when it covers some.** `:LandSurface` and
`:BedrockSurface` are optional, but a user who names a file means it to be used; a raster that gives no value anywhere is
always a wrong file, a wrong corner, a wrong `:InputCRS` or NODATA over the whole model, and the run with the fallback
(HRU ELEVATION, DEFAULT_BEDROCK_DEPTH) is a different model. Partial cover is legitimate (NODATA over lakes, a DEM ending
at the basin edge), so it is a warning with the count. "Covers" = `MeanRaster` found at least one of the column's 25
samples (the existing fallback test), counted over the active columns in `BuildGeometry` (DEM) and `BuildVertical`
(bedrock, before thin columns are dropped).

The stop message (`CGroundwaterModel::CheckRasterCover`) gives the raster's extent and the extent of the active columns'
sample points, both in the raster's coordinates (longitude/latitude, or the `:InputCRS` projection), so a shifted corner
or a wrong projection is visible at once.

**Existing models.** With `:MF6CRS`/`:MF6GridFile` the DEM is read and checked in `BuildGeometry` as for generated models.
With `:OverlapWeights` (no cell outlines) the DEM was accepted under `:SoilZone PHYSICAL` and never read; a warning now
says it is not used.

**Not done: a coverage line in `GWModelSummary.txt`.** It would change the summary of every run with a raster, against
the byte-identity requirement for the CONCEPTUAL Liard run; the warning and the stop carry the information when it matters.

## 5. Tests

- `tests/geotiff/fixtures`: 257 fixtures, 285 files, 1.3 MB (largest 27.8 KB), written once by
  `tools/dev/make_geotiff_fixtures.py` with GDAL 3.12 (rasterio) and tifffile 2026.9 (imagecodecs), each read back with
  tifffile and compared before it is kept. Matrix: compression {none, LZW, DEFLATE 8, DEFLATE 32946, PackBits} x predictor
  {1; 2 and 3 for LZW/DEFLATE, 3 floats only} x 10 sample types x 2 byte orders = 173 files, layout (strips/tiles) and
  container (classic/BigTIFF) in turn so each appears with every compression, predictor and byte order, writers in turn
  (GDAL does not write 32946: tifffile, or GDAL's DEFLATE with the tag set to 32946 for float predictor 2, which tifffile
  does not write). Plus integer extremes (32), NODATA (4: int16, float32 lowest, NaN tag, NaN untagged), PixelIsPoint (2:
  GDAL tie point, tifffile ModelTransformation), rectangular pixels (2: twice as wide, twice as high; no ESRI ASCII twin is
  possible, so their values and corner are compared with what was written and 3,000 samples with a bilinear sampler in the
  check script), CRS (5), a raster 1 degree east, 24 stop files; added after review: internal masks (3), tiles of 2048 x 2048
  (1), no NODATA tag with -9999 pixels (1).
- ESRI ASCII twins: the same values as the shortest decimal that parses to the same double; corners and cell size dyadic
  (1/1024 degree, 64 m), so every corner computation is exact and the twin's header gives the same doubles.
- `tests/geotiff/geotiff_unit.cpp` (driver) and `geotiff_check.py` (run_all steps `geotiff_nolib`, `geotiff`; needs
  only Raven, its source and Python at run time): every value and the corner against the twin; CGWRaster sampling at 4,000
  points bit for bit; each stop with its reason; the 1 GB guard on a sparse file; CRS cases; the EPSG table; fuzzing; Raven
  runs: 184 fixtures as `:LandSurface` and 43 as `:BedrockSurface` byte-identical to their twins (the run's `gwf.dis` holds
  the sampled elevations; file names in warnings replaced by a placeholder), projected rasters under `:InputCRS`
  (EPSG:32611, the same projection by parameters, user-defined, not built in), CRS and format stops through Raven, IB4-4
  stops (GeoTIFF and ASCII DEM 1 degree east, ASCII bedrock east, NODATA-only DEM) and the partial-cover warning.
- `tests/geomtest_check.py`: "crs" members EPSG:4326, 4269, 4617 read as lon/lat (4617 and 4979 refused with
  `:InputCRS`), EPSG:4647 asks for its projection's parameters without `:InputCRS` and is accepted with `TMERC`; the 4647
  cases fail with the previous build's range rule.
- The stand-alone compile lines of `gridtest`, `geomtest`, `crstest` (run_all.py, README, file headers) add
  `GWGeoTIFF.cpp`, which `GWGeometry.cpp` now calls.

## 6. Byte identity and builds

- `patches/byteid.py` (copy of the p11 script, new build against base Raven and p11): no-groundwater runs (small model with
  hotstarts, Nitrate, AGE; Liard 5 years and hotstart) identical to base Raven; Liard CONCEPTUAL 180 d, Liard existing
  model 31 d (both with mf6 folders), PHYSICAL + RICHARDS and the unconverged CONCEPTUAL case identical to p11.
- Make (`tools/build_raven.sh`, wildcard sources) and CMake (`file(GLOB src/*.cpp)`) pick up `GWGeoTIFF.cpp`; the Visual
  Studio project and filters list `GWGeoTIFF.cpp/.h` and `GWEPSGTable.h`; `tools/package_sources.py` archives the git tree
  and lists no sources.

## Files

Code: `src/GWGeoTIFF.h`, `src/GWGeoTIFF.cpp`, `src/GWEPSGTable.h` (new); `src/GWGeometry.h/.cpp` (CGWRaster GeoTIFF path,
`_dx/_dy`, `_hasNodata`, size guard, `CheckLonLatRange`, `GeographicEPSG` table, `CGWCRS::EPSG`);
`src/GroundwaterModel.h/.cpp` (`ReadRaster`, `CheckRasterCover`, counts in `BuildGeometry`/`BuildVertical`);
`src/GWExternal.cpp` (`:OverlapWeights` warning); `src/Raven.vcxproj(.filters)`.
Extra: `tools/dev/make_epsg_geographic.py`, `tools/dev/make_geotiff_fixtures.py`, `tests/geotiff/` (driver, check script,
fixtures), `tests/run_all.py`, `tests/README.md`, `tests/geomtest_check.py` and the compile lines of `geomtest.cpp`,
`gridtest.cpp`, `existing/crs_check.py`; manual `building.tex` (Raster maps, GeoTIFF files, the EPSG rule),
`inputs_outputs.tex`, `appendix.tex` (commands, errors), `applying.tex`, `developers.tex`, `verification.tex`,
`exchanges.tex`; user guide (commands, Rasters paragraph, EPSG rule, errors, limitations).

## Review responses

The independent review (`wt/p12g/review/REVIEW.md`) found no S1/S2 defect; the S3 and S4 points were handled as follows.

- **S3-1 FillOrder.** Tag 266 other than 1 stops ("FillOrder 2 (bits of each byte in reverse order) is not supported");
  the mask reader refuses it too. Fixture `stop_fillorder2.tif` (written byte by byte by the generator, since tifffile does
  not write tag 266; GDAL reads it correctly, so it is a valid file Raven refuses rather than misreads).
- **S3-2 GDAL internal mask.** The chain of image directories is followed from the first one (`ReadIFD`, the same bounds
  checks as the first directory, at most 64 directories, a loop or an unreadable directory stops as corrupt). The first
  directory with `NewSubfileType & 4`, without the reduced-resolution bit, and the raster's width and height is the mask:
  1 bit (MSB first, rows padded to a byte; tiles must be a multiple of 8 wide) or 8 bits, any supported compression,
  predictor 2 only for 8 bits; its blocks go through the same layout, plausibility and decoding code as the image
  (`Layout`, `Plausible`, `DecodeBlock`, factored out of `ReadMemory`). Mask 0 sets the pixel to NaN, which is no data in
  both NODATA branches. A mask Raven cannot read (other bit depths, empty blocks, FillOrder 2, ...) stops with
  "save the raster with a NODATA value instead (gdalwarp -dstnodata -9999)". Overview masks (NewSubfileType 5) are skipped.
  Fixtures: GDAL 1-bit mask in strips (`GDAL_TIFF_INTERNAL_MASK=YES`), tifffile 1-bit mask in 16 x 16 PackBits tiles
  (BigTIFF, big-endian), tifffile 8-bit mask with LZW and predictor 2; masked pixels hold 0, the twin has NODATA there;
  70 masked pixels each (GDAL's own mask count), byte-identical Raven runs.
- **S3-3 no GDAL_NODATA.** GDAL's semantics stay (every value is valid). When a file without the tag holds -9999, the
  lowest/highest float32 (float rasters), the lowest/highest float64 (64-bit floats) or the signed type's minimum, the reader
  counts each and Raven writes a warning with the counts and values and how to declare the NODATA value
  (`gdal_translate -a_nodata -9999`). Unsigned types are not checked (0 and the maximum are ordinary values there).
  Values are not changed. Fixture `fill_f32_nonodata.tif` (6 pixels of -9999 and 1 float32-lowest away from the model):
  the Raven run equals its twin and carries the warning. The manual's gdalwarp example now has `-dstnodata -9999`.
- **S4-1 tile size.** The bound is now the pixel guard (5e7 pixels per tile, 400 MB at 8 bytes); the plausibility check
  still runs before any allocation. Fixture `bigtile_int16_deflate.tif` (2048 x 2048 tiles on 37 x 29) reads and runs as
  its twin.
- **S4-2 advice for a projected code without :InputCRS.** `:InputCRS EPSG:n` is suggested only when `CGWCRS::Parse` accepts
  the code; otherwise the message asks for the TMERC, ALBERS or LCC parameters and says the code is not built in. Manual
  and user-guide error tables match.
- **S4-3 ESRI:102001.** Chosen: treated as a code, like EPSG codes (`CGWCRS::Code()` holds "EPSG:n" or "ESRI:102001", empty
  only for parameters). A GeoTIFF in a code that is not built in is then refused under `:InputCRS ESRI:102001`, as under any
  EPSG code: two different codes name different coordinate systems, and only parameters cannot be compared. Messages show
  the code. Test case `crs_2955_f32.tif` under `ESRI:102001`.
- **S4-4 stricter than GDAL** (negative pixel height refused, more than 4,096 tie-point values, GDAL_NODATA over 256
  characters ignored, LZW without table clears): documented in one manual sentence (the LZW case reads correctly, so it
  needs none). No code change.
- **S4-5 units.** `ProjLinearUnitsGeoKey` (3076) and `GeogLinearUnitsGeoKey` (2052) other than metre (9001), and
  `VerticalUnitsGeoKey` (4099) other than metre, stop with the unit's name. Also `GeogAngularUnitsGeoKey` (2054) other
  than degree (9102, 9122) for a geographic raster (a grad raster would otherwise be read as degrees); for projected rasters
  that key belongs to the base geographic system and is not used. Fixtures: projection in feet, elevations in US survey
  feet, geographic linear units in feet, angles in grads.
- **S4-6.** `.gtiff` is read as GeoTIFF (any case); tested with `dem_int16.GTiff` through Raven. Format sniffing was not
  added: both misnamed cases already stop cleanly.
- **S4-7.** The error tables list the empty-block, non-numeric GDAL_NODATA and reduced-resolution/mask first-image
  messages, and the new FillOrder, units, mask, corrupt-chain and no-NODATA-warning messages.
- **S4-9.** Accepted by the reviewer; unchanged.
- **S4-10.** The 69 table codes in other angular units or with a non-Greenwich prime meridian (e.g. 4807 NTF (Paris),
  grads) stay in the table (they are geographic, and the previous rule also read them as degrees); one manual sentence
  says to convert such files to EPSG:4326. GeoTIFF rasters in such units now stop through the angular-units check.

### Follow-up review

The follow-up review found no S1-S3 point; its three S4 points and the CPU note:

- **Vertical units implied by codes.** `GWEPSGTable.h` (same generator, `make_epsg_geographic.py`) now also holds the EPSG
  vertical CRS codes with heights in metres (283) and in feet (16: foot, US survey foot, British foot), from pyproj's axis
  units. A `VerticalCSTypeGeoKey` (4096; GDAL writes it for a compound CRS such as `EPSG:26911+6360`) in the feet table
  stops ("its elevations are in US survey foot (vertical coordinate system EPSG:6360)"). A code in neither table, or
  user-defined (32767), gives a warning that the heights are read as metres, unless `VerticalUnitsGeoKey` says metre.
  Geographic 3D codes in that key (GDAL writes 4979 there) are ellipsoidal heights in metres and give no warning.
  Fixtures: `stop_navd88ft.tif` (GDAL, EPSG:4269+6360; also through Raven), `vert_userdef_f32.tif` (warning; the run
  equals its twin), `crs_4326_egm96_f32.tif` (EPSG:4326+5773, read silently).
- **Prime meridian.** The same generator lists the 27 geographic codes whose prime meridian is not Greenwich and the 50
  whose angles are not degrees (grads, degrees-minutes-seconds); the two lists overlap. A GeoTIFF in such a code, or with
  `GeogPrimeMeridianGeoKey` (2051) other than Greenwich (8901), stops; so does a GeoJSON `"crs"` member with such a code
  (this replaces the earlier manual advice to convert such files: refusing is the only safe reading). Fixtures and cases:
  `stop_bern_pm.tif` (GDAL EPSG:4801, also through Raven), `stop_paris_pm_key.tif` (the key), `stop_dms_4035.tif`;
  geomtest: EPSG:4801 and 4035 refused.
- **IFD chain.** A damaged, looping or over-long chain after a good first image no longer stops: the mask search ends,
  the raster is read without a mask and a warning says why (as GDAL reads the image and prints errors). A mask that is
  found but cannot be read still stops. The bound is now 4,096 directories (a `std::set` of seen offsets; each directory
  holds at most 4,096 entries, so the work stays small). Fixtures: `mask_f32_after_100_pages.tif` (mask after 101
  directories: found, 70 pixels) and `chain_damaged_f32.tif` (next-directory pointer past the end: warning, twin without
  the mask).
- **Decoding work.** `Layout` refuses strips or tiles whose padded area exceeds 4 x the pixel guard (200 million pixels),
  for the image and the mask, before anything is decoded: a crafted 1 GB file can no longer ask for thousands of
  400 MB tiles. Fixture `stop_block_area.tif` (five 7056 x 7056 tiles on a 35280 x 1 raster).
