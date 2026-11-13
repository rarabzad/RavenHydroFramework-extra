# Rebuild note: soil zone v3 shared hooks (agent v3h)

*Commit IDs in this record are those of the development repositories. For publishing, the commit messages are made
neutral in new clones, so the published history holds the same changes, with the same trees, under new IDs; base
Raven's commits (e7e2868 and its ancestors) and commits that are already public keep theirs.*

Replay of the original v3 hooks commit debb63a (turn 276), from the verbatim edit scripts in
spec/conv_220_330.md section 34, applied with tools/ed.py (CRLF-preserving) to rb-v3h (soil zone v2 merged).

- All `rep()` calls applied with exactly one match each; nothing reconstructed: GroundwaterModel.h/.cpp (`_vzPar`,
  `_vzClasses`, SetSoilZoneVadose(mode,acc,n,par), SetSoilZoneVadoseClasses, VZOwnRise, VZName, VZColStep decl.,
  messages with VZName()), GWVadoseModel.cpp (VZColStep dispatch, rise only from the column top for RICHARDS,
  SetReference((_vzMode==2)?1:0)), ParseGWFile.cpp (`:SoilZoneVadose NONE|RICHARDS|KINEMATIC|LAG`,
  `:SoilZoneVadoseClasses K` 1..10), GWVadose.h/.cpp (StepKinematic/StepLag contract, SetReference/GetReference,
  REFMODE), new placeholder GWVadoseKW.cpp and GWVadoseLag.cpp (pass-through; qtop < 0 rejected).
- File lists: Makefile and CMakeLists.txt glob src/*.cpp (no change); Raven.vcxproj and .filters gained the two files
  (the original's vcxproj state is not in the transcript; added next to GWVadose.cpp, Groundwater filter).
- Only output change: the GWModelSummary.txt line "unsaturated columns : Richards" now reads "RICHARDS" (VZName()).
  test_v2.py (all V2a-V2j) and test_hillslope.py: every other output file byte-identical to the v2 build.
- Parse checks: KINEMATIC, `LAG 4 8`, RICHARDS + `:SoilZoneVadoseClasses 3` run with identities at round-off;
  `LAG -1`, `:SoilZoneVadoseClasses 11` and an unknown method stop with their messages.
- Worker briefs for the next step (final behaviour after audits R1-R10): spec/v3_briefs/{common,kinematic,lag,classes,rough}.md.
- Quick suite (RAVEN_TEST_QUICK=1) on the hooks build: 34/34 steps PASS, 1599 s.
