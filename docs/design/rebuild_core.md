# Rebuild note: `:SoilZone PHYSICAL` version 1 (agent "core", stage 1)

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Status (28 Oct 2026): soil zone v1 is rebuilt to its final audited state (end of audit round 14, original builds
r38 / commits b4d2748 + "withheld gains split", turn 241 of conversation 45baf48d). Stage 2 (v2: Richards columns,
capillary rise, LAGGED timing, column classes, CHD columns, existing models; turns 246 onward) is not started.

Branches: code `rb-core` (worktree wt/core/code), extra `rb-core-tests` (worktree wt/core/extra). Base: code f12baab,
extra 253212f. Nothing pushed.

## How it was rebuilt

Every source, test and doc change was REPLAYED from the original tool calls, in the original order, against this base;
nothing was rewritten from a summary.

- t197, t199, t202, t204, t218: from /home/claude/rebuild/spec/raw_110_220/*.txt with a replay driver (Write/Edit
  applied as is; the python/sed patch scripts inside Bash calls executed with the paths mapped to the worktrees;
  builds, test runs, git, sleep and pkill stubbed out; `git checkout src` allowed in t218, where the original reverted
  three experimental variants to the r31 commit).
- t201, t205, t206, t208, t211, t214, t216, t224, t227, t229, t231, t233, t236, t238 (not in the raw dumps): fetched
  from the conversation (read_conversation, page_token tNNN) and transcribed to the same raw format (t224 converted
  automatically: a read_conversation result over the size limit is saved to a file, which `conv2raw.py` turns into
  raw format). Turns 200, 203, 207, 209-210, 212-213, 215, 217, 219-223, 225-226, 228, 230, 232, 234-235, 237,
  239-243 contain no file changes (runs, commits, audit briefs, messages).
- Replay tooling, the transcribed turns and the regression script are saved in
  /mnt/attach/outputs/rebuild/agents/core_replay/ (replay.py, parse.py, conv2raw.py, adapt.py, stubs/, turns/,
  eqtools/crlfed.py, regress.sh). CRLF files were edited with crlfed.py (line endings preserved; checked).
- One commit per original turn group, message "... (replay of tNNN)".

## Edits that could not apply as recorded (resolved by hand)

All are manual edits whose anchors were text written by the Phase 0 notation clean-up (another agent's task, not on
this branch). They were applied at the same places in the base notation:

1. t199 call 240 (ch4_exchanges.tex, ch3_building.tex): Phase 0's A4/A5 sentences were the anchors. ch4: the
   sentence "Under :SoilZone PHYSICAL (Section ch:soilzone) the drain serves only the HRUs without a soil zone ..." is
   appended after "as the water table approaches the surface." ch3: after "(default 0, so the top is the land
   surface)." the sentence "Under :SoilZone PHYSICAL (Section ch:soilzone) SOIL_ZONE_DEPTH is ignored: the soil-zone
   thickness is the sum of the listed soil layers." (wording reconstructed from the Phase 0 brief: the exact Phase 0
   wording is not in the spec). The notation agent's A4/A5 sentences will overlap these two: keep one of each.
2. t199 call 243 (ch5_accounting.tex): recharge identity written with the base symbol \Delta S^{delay} (Phase 0 renames
   it \Delta V^{dl}).
3. t199 call 247 (appendix.tex): the anchor row `:SurfaceWater Exchange SV group LEAKANCE L` / `$L>0$` in base notation
   (Phase 0: \Lambda).

Merging with the notation branch will conflict in these lines only (plus any symbol Phase 0 renames inside the new
soil-zone section, which uses the post-Phase-0 symbols as originally written, e.g. |\Omega_i|).

## Results on this build (Raven_v1.exe, optimized -O2)

- Soil-zone steps of tests/run_all.py, MODFLOW 6.8.1: soilzone_unit (57 checks, 0 failed: the original's final count),
  spike, column, hillslope (T2/T3: heads within 7 cm, outflow 0.04%, onset day 16 both), dynamics, restart, inputs
  (I1-I8), robustness (R1-R13; R9 4000 m3, R11 -0.1%, R13 x1.00, as recorded in the original), Liard T7 365 days
  (107 s): all PASS. Total about 3.5 minutes; the steps are fast enough that quick and full mode are the same
  (run_all.py now also takes RAVEN_TEST_QUICK=1 as --quick for the other steps).
- The same nine steps on MODFLOW 6.6.3 (/mnt/user-data/uploads/libmf663_linux.so, version 6.6.3 confirmed in
  GWModelSummary.txt): all PASS (Liard T7 110 s).
- CONCEPTUAL byte-identity against Raven_base.exe (tools: core_replay/regress.sh): Liard_groundwater (365 days, 32
  files) and Liard_existing_model (731 days, 37 files): identical except the output path and timings in
  GWModelSummary.txt and the elapsed time in mfsim.lst / mfsim.stdout.
- Manual: pdflatex, bibtex, pdflatex x2 clean (no errors, no undefined references, no overfull boxes).

## Uncertain / to check

- Python patch scripts that used plain `s.replace(old,new)` without an assert would have done nothing silently if
  their anchor was missing; every asserted edit applied, the build is warning-free in the soil-zone files and the
  results above match the numbers the original reported, so no silent miss is known.
- The Liard T7 run books a large gross exchange (aquifer to soil zone 3.75e10 m3, overflow 1.9e10 m3 in a year): this
  is the documented "churn with fast drainage" of v1 on the example's low-storage soils (net balances close to 1e-11);
  the original's absolute numbers for this run are not in the spec, so it could not be compared.
- tests/run_all.py: the soil-zone registration is the original's (9 steps); only the RAVEN_TEST_QUICK line was added.
- The original manual PDF was rebuilt in each round; main.pdf here is rebuilt from this branch.

## For stage 2 (v2)

Start from conv_220_330.md §10 onward (turn 247 plan, turn 248 code verbatim). Turn 248 is one very long turn: fetch
it with read_conversation (the result is saved to a file), convert it with core_replay/conv2raw.py and replay it with
core_replay/replay.py from this branch's HEAD, as for t224 here.
