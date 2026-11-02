# Soil zone v3: rough-terrain stress suite (design note)

Files: `tests/soilzone/test_rough_terrain.py`, `rough_models.py`, `rough_ext.py`, `rough_cases/*.json`; manual
`docs/manual/chapters/ch8_rough_terrain.tex` (\label{sec:vrough}), figure script `docs/manual/figures/make_rough_figure.py`;
run_all step `soilzone_rough_terrain` (`--quick --methods NONE,RICHARDS,KINEMATIC,LAG`, judge "rough terrain: N runs, 0 failed").
This is the rebuilt suite (November 2026) in its final form after v3 audit rounds 1-10; the original was lost with the machine.

## 1. When a stop is justified (final rule)
A run that stops is not a failure only in three situations:
1. an outcrop case (`does not overlap any active groundwater cell`, and the spec says `outcrop`);
2. an existing model without NEWTON (`needs an existing model that uses the Newton-Raphson formulation`, spec `ext.newton`
   false);
3. a diverged solve (`heads are not finite` or `lies far outside the model`) that MODFLOW 6 repeats on its own
   (`mf6_alone_diverges`): the run's working MODFLOW model (out/mf6) without Raven's packages (RCH/DRN/SZX/SZQ/SZD/SZW, the
   specified heads kept), with a drain at the top of every column (top of the top active cell, conductance 1e4 m2/d) as the
   only outlet and no recharge, run through libmf6 (xmipy, in a subprocess) for the run's duration with the model's own
   OUTER_MAXIMUM; justified when its heads become non-finite or move by more than 1e6 m within the outer iterations.
A drained column (held 1 mm above its bottom) is only reported (a note), never a stop nor a failure.
Historical: the first-wave rule also accepted "heads are not finite" when a drained column had been seen (head within 1 cm
of the bottom); since the drained columns are held at bottom + 1 mm that rule would have accepted every divergence with a
kept-wet column, and it was retired (v3 audit round 1 item 13; round 10 item 9). The 1e6 m head-change criterion of
`mf6_alone_diverges` is the one the code always used; ch8 now states it (round 1 item 19).

## 2. Checks and limits
As the docstring of test_rough_terrain.py and files_spec 4.14. Decisions:
- Identities use `sz_check.ID_LIMITS` (fallback: the standard limits, decisions B.2) [R1 item 16]; the counters
  `iface_not_conv`/`mf6_not_conv` are judged by the conv check (MAXNC 5 %), not as identities.
- Layers: compared with an independent construction (`rough_models.geometry`) that uses the raster values as written and
  Raven's sampling rules (bilinear between raster-cell centres, no-data corners dropped and weights renormalised, points
  more than a raster cell outside: no data; 5 x 5 points per cell; fallback land = overlap-weighted .rvh ELEVATION). The
  spec values written to files are rounded in the spec itself (soil and layer thicknesses to 4 decimals), so the
  construction agrees to 5e-8 m (the 10 digits of MODFLOW's files). Tolerance 1e-6 m.
- Bases: existing models also honour `:MinCellCoverage` (a column covered less than that is not linked); found when the
  first ext runs disagreed by 0.09 m.
- Saturated fraction (NONE): per HRU, the reported F must lie within [sum a min(F(h0), F(h1)), sum a max(...)] / sum a over
  its links, F the closure at the top cell's head (manual eq.: mean over samples of smoothstep((h - z_b)/d_s)), sample
  bases clipped at the top cell's bottom + 1 mm (files_spec 2.1, R3 c2.2), h0/h1 the heads at the start and end of the
  step (step 1: the starting heads as built); only on steps where both MODFLOW and the interface converged; FTOL 0.02.
  (files_spec 2.1 writes sigma with full saturation at the base; the code and the manual use 0 at the base and 1 at
  base + d_s; the suite follows the manual.)
- Physics: the HRU recharge is the change of the running total of the custom output Between:SOIL[1].And.GROUNDWATER
  (it is cumulative); tolerance 1e-5 of that total (6 significant digits). HRUs touching a specified-head column are left
  out of the F-based rejection checks (the CHD columns' share of the rejection is not in the reported F).
- Heads: water table = highest head of the column's active cells; highest land sample = max of the 5 x 5 and sub-grid
  DEM samples. Column method: failure when > EXF (5 m) and > NONE's + 1 m.
- XFAIL: decided by `decide()` after all failures, and again after a regression case's own checks
  (`regression_checks`) [R10 item 6]; a shortfall is never XFAIL [R1 item 13]; KNOWN is empty (g350 fixed, R19);
  KNOWN_PATTERNS keeps "interface unconverged where land lies below the top cell's bottom" (condition `deep_links`).
  `--selftest` shows on constructed results: pattern alone XFAIL, with R20's own failure FAIL, shortfall FAIL.

## 3. Generator
Spec = JSON dict from `gen_spec(seed, family)` (numpy default_rng([seed, family, 20261028])); family_of(seed) = 'ext' every
fourth seed (seed % 4 == 0). Ranges: ch8 Table tab:vroughvary. The projection origin is fixed (every HRU carries
lat 55, lon -120 as its centroid) so that projected coordinates of the spec are those Raven computes; domain edges on cell
edges are moved 1 mm inside (Raven's floor/ceil of the extent). `_covered()` makes sure each HRU lies over a column the
HRUs cover by `:MinCellCoverage` (else min_cover 0.1, else no one-cell HRU): a "does not overlap" stop is then only
drawn in outcrop cases. Existing models are written as plain MODFLOW 6 text files (no flopy at build time), with the IMS
settings Raven writes for its own models, cells placed by `:MF6GridFile` (polygons from the same projection).

## 4. Stored cases (rough_cases/*.json)
The original stored specs were lost and the rebuilt generator draws other cases from the same seeds. Each file is
`{spec, meta, origin}`: `origin` records the seed, family and the overrides (CASE_SOURCES in test_rough_terrain.py) that
recreate the property the case's name refers to (e.g. lowkv: Kv 3.6 mm/d in the top class; band_e43: a 0.6 m top layer
under relief 2.5 D with 9 x 9 samples, so samples fall below the top cell's bottom and into the 1 mm band; nonewton_e14:
no NEWTON). `--make-cases` rewrites them. They are regression cases by construction (same configuration class as the
originals), not byte-for-byte the originals.

## 5. Results on the rebuilt base (Raven_v3h.exe, before the kin/lag/cls/integ merges)
Default run (400 seeds + regression, NONE and RICHARDS; 815 runs, 400 s): 235 failures, 4 known (XFAIL); layers 5.0e-8 m,
bases 5.0e-8 m everywhere; justified stops: 7 outcrop seeds and g178 (MODFLOW alone repeats the divergence); 100 existing
models, 6 without NEWTON. Quick run with all four methods (KINEMATIC/LAG still the hooks' pass-through placeholders): 180
runs (as the original quick suite), 29 failures (NONE 18, RICHARDS 10, LAG 1). The failures are rebuild gaps of the base,
each against a files_spec item (to be closed by the other workers' merges; the suite is the test):
1. Saturated fraction off the closure (121 NONE runs, R2, R10, R20): ~95 of them vanish when the closure leaves out the
   clip of the sample bases at the top cell's bottom + 1 mm, i.e. SZBuildEntries does not clip (files_spec 2.1, R3 c2.2);
   the rest are converged steps whose F (at the connection head) is far from the closure at MODFLOW's head: the round-9
   connection test and "rejection follows the converged head" (files_spec 2.2 SZIterate; R1: rejected share 0.081 above
   the closure).
2. vz_identity 1.2e-8 to 5.6e-6 in 66 RICHARDS runs: either the column balance or sz_check's v2 formula (final sz_check
   scaling, R1 item 16 / R7 g1.6) -- to check after the merge.
3. Rejected recharge above recharge + columns' storage in 42 RICHARDS runs (R6, R12): the columns' hand-back rules
   (files_spec 2.7, v3 audit R1 item 12).
4. Column water tables up to 30 m above NONE's (8 runs, g5): column injection into cells filled to the base.
5. Existing models without NEWTON run instead of stopping (files_spec 2.9): rch_identity 1 (recharge not applied is not
   booked), e356 heads 56 km above the land with NONE.
6. Interface unconverged on > 5 % of steps (17 runs), MODFLOW balance error up to 4.3 % (4 runs), one shortfall on a
   converged step (g86 NONE, 0.029 m3).
