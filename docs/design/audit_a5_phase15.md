# Audit A5, phase 15: inputs, GeoTIFF, tools and documentation

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Issues: IB5-1 to IB5-9, VZ5-3, MT5-1, MT5-3 to MT5-6, SZ5-2, SZ5-3 (findings in `spec/audit_A5/F_IB.md`, `F_VZ.md`,
`F_MT.md`, `F_SZ.md`). MT5-2 (commit-message history) waits for the user's decision; a tool for option (a) is prepared
outside the repositories (see the end). Code on top of `5f042ff`, extra on top of `a7de343`.

## Changes

### IB5-1 (S2) GeoTIFF prime meridian given by its longitude or by the datum
`GWGeoTIFF.cpp` now reads `GeogPrimeMeridianLongGeoKey` (2061) from `GeoDoubleParams` (tag 34736), the key GDAL writes for
a user-defined geographic system (`+pm=paris`, EPSG:4801 without its authority, `+pm=10`): a non-zero longitude stops the
run ("its prime meridian lies at longitude 2.33722917 from Greenwich"). `GeogPrimeMeridianGeoKey` 32767 (user-defined)
is accepted only when 2061 gives 0. `GeogGeodeticDatumGeoKey` (2050) is checked against a new table of the 27 EPSG datums
with another prime meridian (6801 Bern, 6807 Paris, ...), for a writer that gives the datum alone. The auditor's run
(`e1_pm.py`): the Paris file, accepted before with the model top 23.4 m wrong, now stops; the Greenwich twin runs as
before. A corrupt 2061 entry (index beyond `GeoDoubleParams`) stops as a corrupt GeoKeyDirectory.

### IB5-9 (S4) projected EPSG code in feet without ProjLinearUnitsGeoKey
`GWEPSGTable.h` gains `GW_EPSG_PROJECTED_NOT_METRE` (1,016 projected codes whose first axis is not in metres: US survey
foot, foot, Clarke's foot, German legal metre, links, yards, kilometre ...), written by the same generator
(`tools/dev/make_epsg_geographic.py`, pyproj 3.8.0, EPSG registry v12.029, PROJ 9.8.1; the earlier tables are unchanged
byte for byte). A GeoTIFF whose projected code is in the table and has no key 3076 stops; so does a GeoJSON `"crs"` member
naming such a code (the same defect class: it was "not classified" and read in metres). When key 3076 is present it
decides, as before.

### IB5-6 (S3) GDAL_METADATA scale, offset and unit
Tag 42112 is read (up to 1 MB; `<Item ... sample="0">`, entities decoded). `SCALE` and `OFFSET` of band 1 are applied
(value * scale + offset), as GDAL's `-unscale` and QGIS show the raster; no-data pixels (NaN, or within 1e-6 of
`GDAL_NODATA`, the rule of `CGWRaster::Valid`) become NaN first and the raster then has no NODATA value, so no scaled value
can be taken for NODATA. A scale of 0 or a value that is not a number stops. `UNITTYPE`: metres (`m`, `metre(s)`,
`meter(s)`, empty) pass; feet and other length units (ft, foot, feet, us-ft, cm, mm, dm, km, inch, yard, mile, ...) stop;
anything else gives a warning ("which Raven does not know; its elevations are read as metres"). The fill-value warnings
still look at the stored values. The encoding description names the scale applied. The auditor's file (int16 decimetres,
scale 0.1, unit ft) now stops on the unit; its metre twin is read as 100.0-103.0 m.

Choice: apply the scale rather than refuse it. Integer DEMs in decimetres or centimetres with a GDAL scale are common
(national DEMs, compressed exports), GIS programs show them scaled, and GDAL documents scale/offset as the way to get the
physical value; refusing would only send the user to `gdal_translate -unscale`, which gives the same numbers.

### IB5-7 (S3) ESRI ASCII
`CGWRaster::Read` reads the header keys in any order until the first value: `dx`/`dy` (GDAL's rectangular pixels;
`xllcenter`/`yllcenter` shift by half of each), `NODATA_value nan` (no NODATA value; `nan` cells are no-data, as with a
GeoTIFF), strict numbers (`gwutil::StrictNumber`) for every header value, positive whole `ncols`/`nrows`, and a missing
`xllcorner`/`yllcorner` stops (it was taken as 0). Cell values are read as tokens: a value that is not a number stops with
its row and column; `nan` is NaN. After `ncols*nrows` values another token stops ("has more values than ncols*nrows
... check ncols and nrows"); too few gives the count read. Values parse with `strtod`, as `istream >> double` did, so every
valid grid gives the same doubles (byte-identity below).

### IB5-8 (S4) GeoJSON with a UTF-8 BOM
`ReadGeoJSONPolygons` and `ReadGeoJSONLines` skip a leading `EF BB BF`.

### IB5-4 (S3) :InputCRS / :MF6CRS parameters
`CGWCRS::Parse`: `TMERC` takes exactly 5 numbers, `ALBERS`/`LCC` 6, then at most the ellipsoid; each parameter must be a
whole-token finite number (`StrictNumber`), latitudes within +-90, |lon0| <= 360, k0 > 0; `EPSG:` must be followed by
digits only and nothing after it; an unknown ellipsoid is named. Messages name the parameter and the token as written.
The optional check of HRU centroids against the `.rvh` coordinates was not added: the existing "looks like
longitude/latitude" check covers the common mistake, and a 50 km rule would refuse legitimate models whose `.rvh`
coordinates are approximate.

### IB5-5 (S3) .rvp aquifer tables
`ParsePropertyFile.cpp`: `GWTableNumber` (strict, naming the table, the row and the column) for every value of
`:AquiferClasses`, the layer thicknesses and the layer count of `:AquiferProfiles`, and `:AquiferProfileParameters`.
Refusing `SPEC_YIELD 0` for convertible layers was considered and left: 0 is a legal MODFLOW value and the strict read
already stops the reported typo.

### IB5-3 (S3) overlapping boundary polygons
`ReadGeoJSONPolygons` can return, per ring, the polygon it belongs to (a Polygon, or one part of a MultiPolygon). In
`SelectColumns` the even-odd rule runs within each polygon (outline and holes) and the polygons are united. A file whose
polygons do not overlap selects the same cells as before. Auditor's case (`xor.py`): A, A+B, A twice and a MultiPolygon
A+B now all give A's four cells (before: 4, 2 and 0 cells).

### IB5-2 (S3) HRU mesh with a refinement size in the wrong unit
Measured on the auditor's case (4 HRUs of 5 x 5 km, 500 m cells, one short `LINES` line), the time went to three places:
(1) the seed spacing test of the interior lattice used the hash sized by the finest refinement (the auditor's diagnosis);
(2) `CGWGrid::MakeVoronoi` clipped every cell against every seed in the scanned buckets, allocating two vectors per seed,
although almost all of them cannot cut the cell; (3) the size itself: the HRU boundaries take seed pairs at the smallest
line size everywhere (a design choice of the mesh, kept: changing it would change every existing HRU mesh with `LINES`
refinement), so a 0.5 m line gives 261,000 sliver cells reaching 250 m inland.
- `MeshSeeds`: a second, coarser hash (0.25 x cell size); each query uses the hash that scans fewer squares. Both find every
  seed within the radius, so the seeds are the same.
- `MakeVoronoi`: a seed farther than twice the cell's farthest vertex is skipped, and before clipping, a seed with no
  vertex beyond its bisector is skipped (the clip would copy the cell). The cells are identical bit for bit (harness over
  three seed sets, 2,860 to 32,760 seeds); 4 m: 5.1 s -> 0.95 s.
- An estimate before seeding (boundary pairs, line, point and polygon seeds, interior lattice): it stops beyond 1.5 x the
  5 million limit, or when building the cells would take more than a few minutes (boundary seeds x half the cell size /
  spacing > 2.5e8, about five minutes on one core), with a message naming the smallest size, the spacing, the boundary
  length and "too slow to build".
Times (`mesh2.py`, one core, busy machine): 2 m 42 s -> 14 s, 1 m 48 s, 0.5 m > 300 s (not finished) -> 185 s (built,
261,238 cells), 0.1 m: stops at once.

### VZ5-3 (S3) tools_audit.py step 1
`GWModelSummary.txt` gains one line, `recharge delay storage: <V> m3 at the start`, written only when a profile has
`RECHARGE_DELAY` > 0 or the hotstart holds a store (so the summaries of all other runs are unchanged). `tools_audit.py`
takes the store at the start from that line, or 0 when the run has no store in use, and so checks step 1; only for an
output without the line and with a store in use does it back-compute the start (now including the first step's
`recharge not applied by MODFLOW`), and it adds the entry `recharge: step 1 not checked (...)` (only then, so the
tool's usual output, quoted in the tutorials, is unchanged). With 500 m3/d more onto CHD cells on
step 1 of a two-step run (TC6) the identity is -0.156; the reference tool gives 0 on the same file.

### MT5-1 (S3) block 4-keep-push
4-keep-push stops, pushing nothing, while `CHERRY_PICK_HEAD` exists, when the clone has uncommitted changes, and when
`release` holds no commit beyond the kit (after `--skip` or `--abort`). 4-merge stops in an unfinished cherry-pick. The kit's
self-check now rehearses step 4: a public commit that applies (published on top of the kit, backup made) and one that
conflicts (4-keep stops; 4-keep-push and 4-merge stop and push nothing, also after `git cherry-pick --abort`).

### MT5-3 (S4) Windows line endings
1B-archive and 2-extra-files add the files with `git -c core.autocrlf=false -c core.safecrlf=false add -A -f`; both notes
say that on Windows the executable bits can still differ (the block then stops, nothing pushed) and name the bundle form.
The self-check runs both blocks again with `core.autocrlf=true` in the global configuration: the kit's tree.

### MT5-4 (S4) 1A-replace wording
The paragraph names the public branch's extra commits (ID and subject, at most three and a count) only when the public
check found them; otherwise it says nothing about them (`found_note`, TC7).

### MT5-5, MT5-6, SZ5-2, SZ5-3 (S4) documentation
- `sz_vadose_lag.tex`: unit test LU; `verification.tex`: the `:BoundaryHead` series cases run only the generated model;
  `test_restart.py`: 17 significant digits.
- `cmake_checks.py` prints a skipped part also as `SKIP cmake check n, ...: why`, the line `run_all.py` counts: the step
  reads "PASS (1 skipped)" without patchelf, and the report lists it.
- `run_all.py` docstring, `tests/README.md`, `README.md` and the manual: the tutorials step is described, the run times
  are the ones measured with this change set, `geotiff_check` is in the README's quick-mode list; HANDOVER 3-build names
  its requirements (CMake, a C++ compiler, g++, numpy, pandas, shapely, pyproj, flopy).
- `verification_soilzone.tex` P11 and SW4 in conditional form.
- `GWVadoseModel.cpp`: the two comments point to the manual (sec:szvadose, rule (i)).

## Tests (each fails on the reference build or the old tool, passes here)
- `geotiff_check.py`: new fixtures (`make_geotiff_fixtures.py`, the existing ones regenerated byte for byte):
  `stop_pm_paris_userdef`, `stop_pm_bern_noauth`, `stop_datum_bern_key`, `stop_proj_2227_nounits`, `stop_unit_ft_meta`
  (refused, 34 in all), `scaled_int16_dm` (twin of the scaled values; reader, sampling and a Raven run byte-identical),
  `unit_height_meta` (warning); ESRI ASCII: `dx`/`dy` (corner and centre) against the rectangular-pixel GeoTIFF, `nan`
  against the -9999 twin, seven malformed grids refused.
- `geomtest_check.py`: EPSG:2227 refused, a BOM file read, eight malformed `:InputCRS` specifications refused (the old
  source: 10 failures).
- `input_checks.py`: N17 (HRU mesh 0.1 m stops), N18 (2 m built within 120 s), N19 (overlapping boundary polygons), N20-N23
  (`.rvp` tables).
- `tools_check.py`: TC6 (tools_audit step 1, with and without a delay store), TC7 (`found_note`).
- `make_handover.py` self-check: the new blocks; with the old blocks the same rehearsal fails five times
  (`patches/mt5_handover_old_blocks.log`).

## Byte-identity
No change touches a run without groundwater. Coupled runs without the affected inputs are byte-identical to the reference
build: the ESRI ASCII reader gives the same doubles, the HRU mesh the same cells, boundary files without overlaps the same
cells, and the summary line appears only with a recharge delay store (`patches/byteid.log`).

## MT5-2 (not applied)
`/home/claude/rebuild/wt/p15/tools/dev/neutral_messages.py` (outside the repositories): `propose` lists every coupling
commit (78 after e7e2868 in the code repository, all 116 of the extra repository) with a rule-based neutral message to
review; `apply` rewrites them in new clones only (`git clone --no-local`), each new commit the old object with only its
message changed (tree, author and committer kept; parents mapped; signatures dropped), writes the old-to-new ID map and
verifies trees, authors, parent mapping, the identical tip tree and the unchanged set of upstream commits; a message that
still matches the wording pattern fails unless `--allow-flagged`. Tested on throwaway clones only
(`patches/mt5_2_neutral_messages_test.log`). It should run after every phase is merged, before the kit is made.

## Review findings and responses (`wt/p15/review/REVIEW.md`)
- **F1 (S3)** GDAL_METADATA items were matched by name; GDAL takes an item as the band scale, offset or unit only with
  `role="scale|offset|unittype"`. `GDALBandItems` now keys on the role and ignores other items. Fixture
  `scale_norole_int16.tif` (SCALE 0.5, OFFSET 7, UNITTYPE ft written as plain band metadata by rasterio): read as stored,
  no stop, against the int16 twin; the reviewer's `role1`-`role4` files read unscaled, `role5` (a role unit in mm) stops.
- **F2 (S3)** 4-keep-push (and 4-merge) also stop while the cherry-pick sequencer directory exists (a conflict finished
  with `git commit` leaves the later picks in `.git/sequencer`). Self-check: two kept commits, the first conflicting and
  finished with `git commit`: 4-keep-push stops, nothing pushed. HANDOVER says to finish with `--continue`.
- **F3 (S4)** a scaled value beyond the range of a double becomes NaN (no data), as infinite pixels are.
- **F4 (S4)** the GDAL_METADATA limit is 16 MB; a longer tag stops the run (its scale and unit could not be checked).
- **F5 (S4)** ESRI ASCII centre/corner shift per axis (`xllcenter` with `yllcorner` shifts x only).
- **F6 (S4)** ESRI ASCII: a trailing Ctrl-Z (or NUL), also attached to the last value, is ignored as GDAL does; a UTF-8
  byte-order mark before the header is skipped. Tests: `ctrlz.asc`, `bom.asc`, `mixed.asc` sample as the twin.
- **F7 (S4)** 4-merge run again in its own unfinished merge prints "STOP: the merge is not finished ..." (self-check case).
- **F8 (S4)** `neutral_messages.py apply` now leaves only the rewritten branch in its output clones (origin remote, other
  branches and tags removed, reflogs expired, old objects pruned; checked that no old commit is left), drops the
  `encoding` header of a rewritten message (written in UTF-8), and its docstring says to bundle the rewritten branch
  only, never `--all`, and never to publish a folder that still holds the old commits.
Reruns after the fixes: geomtest, geotiff (--nolib and with Raven runs: 228 twins, 186 Raven runs byte-identical),
input_checks, tools_check PASS (`patches/run_all_review_fixes.log`); hand-over self-check PASS with the two new cases
(`patches/handover_selfcheck.log`); byte-identity 0 differences (`patches/byteid.log`); the neutral-messages test on
throwaway clones PASS, one ref left per clone (`patches/mt5_2_neutral_messages_test.log`).
