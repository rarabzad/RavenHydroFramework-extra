# Rebuild note: soil zone v2 (agent "v2")

Status (28 Oct 2026): soil zone v2 is rebuilt to its state at the end of turn 275 of conversation 45baf48d (v2 audit
rounds 1-10 and the manual subsection "Sloping and irregular land"), i.e. the original's branch `soil-zone-v2` before
the v3 hooks commit (turn 276, debb63a). Nothing of v3 is in it.

Branches: code `rb-v2` (worktree wt/v2/code; base = v1 merged with the MODFLOW build integration, 1b5d3fb), extra
`rb-v2-tests` (worktree wt/v2/extra; base = v1 tests/manual 3c1457d, then merged with `rb-merge1-tests` 24cf588 = v1
manual in the Phase 0 notation + CMake tests). Nothing pushed.

## How it was rebuilt

Every source, test and doc change was REPLAYED from the original tool calls, in order, with the "core" agent's replay
driver (copied and adjusted: /mnt/attach/outputs/rebuild/agents/v2_replay/, raw turns in
/home/claude/rebuild/spec/raw_v2/).

- Fetched with read_conversation (one turn per call; 17 calls): t248 (464 calls, saved to file, conv2raw), t250 (105),
  t251 (169) converted automatically. t252, t253, t255, t256, t257, t259, t263, t264, t266, t267 came back inline: their
  file-changing calls (python patch scripts, sed) were transcribed verbatim into raw format (t2NN.txt); the read-only
  calls (greps, runs, audits) were left out. t249, t254, t258, t260, t261, t262, t265 have no file changes (commits,
  audit launches, container restarts; notes in t2NN.notes). t271 (inline): the figure script is
  t271_make_v2_subgrid_figures.py = the original Write with the four recorded patch scripts and the sed applied by hand;
  the manual subsection is the verbatim final text of conv_220_330.md section 32.3 (same as t271's edits applied).
  Turns 246-247, 268-270, 272-275 (user requests, plan, answers) contain no file changes (per conv_220_330.md) and were
  not fetched.
- Replay adjustments: the original scratchpad path is mapped into a sandbox (it is the same path as this session's
  scratchpad); builds, git commits, pdflatex, sleep, binaries (watchdog.py kills any executable started under the
  replay) are stubbed; the scratch patch scripts v2a.py/v2c.py are allowed to run; crlfed.py (the core agent's
  reconstruction of the original eqtools helper) is placed where the original imported it from.
- Calls that failed in the original too and were redone in the next call: t248 #148 (parser edits with \r\n anchors,
  redone CRLF-aware in #149) and t248 #270 (reference card, redone in #272); t251 #65 (auditor harness only).
- One call ran in the wrong directory and was rerun in place (adapt.py): t251 #149 (ch5/ch6/ch8 doc updates, plain
  replace without asserts).
- Line-number seds of the original were checked against content: t256 `sed '191s/...'` (line 191 = the falling-branch
  bisection, the same line here) and t259 `sed '2381s;2393s;2403s'` (the three soil-zone hotstart setprecision lines,
  also at those lines here; reverted by t263 as in the original). This also shows GroundwaterModel.cpp has exactly the
  original's line numbering at that point.
- Commits: one per original commit group, messages "... (replay of tNNN)".

## Changes beyond the replay

1. `src/Raven.vcxproj(.filters)`: GWVadoseModel.cpp added (the original's v2 file lists had GWSoilZoneStep.cpp and
   GWVadose.cpp but not GWVadoseModel.cpp; CMake uses a GLOB and the Makefile builds all .cpp, so only Visual Studio
   was affected).
2. Notation (coordinator request): extra merged with `rb-merge1-tests`; the four conflicts in ch4_exchanges.tex were
   resolved keeping the v2 content; all v2-added manual lines were mapped to the Phase 0 symbols by
   v2_replay/notation_v2.py (diff against rb-merge1-tests, substitutions on v2 lines only) plus hand edits:
   z_{b,s}, w_s -> z_{b,g}, w_g; $N$ DEM points -> N_g; L_v -> h^sz; lambda -> b^sz (lambda/D -> b^sz/d_sz);
   D_k -> d_{sz,k}; a_c -> A_{k,i} (R_c -> R_{k,i}); soil layer j -> m (z_{m,j} -> z_{mid,m}, Q_m, psi_{s,m}, b_m, ...);
   Delta V -> Delta phi and q -> q^sz_{k,i} in the specified-head column equation; specified head h_s -> h^chd_i (h_s
   and s are the river stage); :SoilZoneClasses count K -> N_c in the text (K is conductivity; the command placeholder
   `:SoilZoneClasses K` in the appendix is left, as Phase 0 left placeholders); Delta S^uz -> Delta V^uz (ch5);
   k_sat -> K_sat (rise example). The notation table (A.14) got v2 rows: b, psi_a; h^chd_i; L_min; N, N_c; q_top,
   q_bot; theta, theta_s, psi; V^uz_in, V^uz_to aq, V^uz_cap, V^wt_cap, V^debt. fig_v2_subgrid.png labels use the new
   symbols (h^sz, b^sz, z_{b,g}, w_g). Symbols kept: b (Campbell exponent) next to b^sz and b_l (distinct by
   super/subscript, as in the Phase 0 table); D as the drawdown in T(D) of the implicit rise; N for column volumes.
3. Appendix: the `AIR_ENTRY_PRESSURE` row of the aquifer-class table made breakable (the one overfull box the
   original also had).

## Results (Raven_v2q = final code, optimized -O2, MODFLOW 6.8.1)

- Soil-zone suite steps (v1 and v2): soilzone_unit (57 checks, 0 failed), spike, column, hillslope, dynamics, restart,
  inputs, robustness, vadose_unit + vadose reference, v2 (V2a-V2j), v2_ext (round trips), Liard T7 365 days: all PASS
  (about 3 minutes in all). Numbers equal the original's: V2a recharge centroid day 6.06 -> 15.62, peak 2000 -> 1097
  m3/d; V2e head error AFTER 1.78 cm -> LAGGED 0.68 cm; V2f 10 classes vs 10 HRUs 6.5e-7 m; V2i 1765/1732/1732 m3.
- Liard T7 (365 days, :SoilZone PHYSICAL, v2 defaults): 0 unconverged steps, 0 interface non-convergence, 67-70 s
  (original: 69 s), identities ~1e-11.
- CONCEPTUAL byte-identity against bld_base/Raven_base.exe, full example durations: Liard_groundwater (7305 days, 32
  files) and Liard_existing_model (37 files): identical except the output path and the linkage time in
  GWModelSummary.txt and the end time / elapsed time in mfsim.lst and mfsim.stdout.
- Manual: pdflatex, bibtex, pdflatex x2: 0 errors, 0 undefined references, 0 overfull boxes, 130 pages (the original
  had 124 + the sloping-land subsection before the Phase 0 merge).
- Full suite in quick mode (RAVEN_TEST_QUICK=1, after the notation merge): 34 of 34 steps PASS (gridtest ... ext_fuzz,
  cmake checks, all soil-zone steps; the USGS examples step is not run without RAVEN_USGS_EXAMPLES), about 30 minutes.

## Uncertain / to check

- Inline turns were transcribed by hand from the read_conversation output (HTML-unescaped). Every transcribed patch
  that asserts its anchors applied; the results above match the original's reported numbers.
- Python patches with plain `s.replace` and no assert would miss silently; the build is clean, the tests pass with the
  original's numbers, and the grep checks done (V2j, NodeCHD, budget-column condition, rch_identity normalisation,
  NEWTON paragraph, dt in checks, _resZbot reset, setprecision lines) all show the edits present.
- ch8_verification has no v1 soil-zone test section (T1-T5): it is not in turns 246-275 (it came with the later audit
  rounds, conv_330_end.md), while ch4's worked example already cites "test T1". To add in a later stage.
- The original's 13-model Raven benchmark comparison (bench2.sh) was not available; the CONCEPTUAL check uses the two
  Liard examples only.
- MODFLOW 6.6.3 was not rerun for v2.
- Figures fig_v2_*.png were regenerated from this build's test outputs (make_v2_figures.py, make_v2_subgrid_figures.py);
  they are not byte copies of the original's.

## For stage 3 (v3)

Start at turn 276 (conv_220_330.md section 34: the shared hooks commit is verbatim there; worker briefs follow). The
code here corresponds to the original v2q commit ("audit round 10 fixes"); the original's extra repo at 5657c55
corresponds to rb-v2-tests before the notation merge (commit d5974b3); the merge and the notation mapping came after.
