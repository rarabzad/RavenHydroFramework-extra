# Audit A15, phase 35: SW-1, SW-2, CB15-1, the manual's numbers, figures in Volume 1

Code: e840ae5 plus this change (GWExternal.cpp). Extra: fb04519 plus this change. Program: Raven_p35.exe, built with
tools/build_raven.sh.

## SW-1 (S3): K10 and K11 check the release limit

`tests/soilzone/test_vz_kinematic.py`: a new helper `release2` takes the release of step 2 as the step's
`unsaturated zone to aquifer [m3]` less its `unsaturated zone inflow [m3]`. By the column identity this is the drop of the
column's storage. The rest of what reaches the aquifer in that step is the column's ordinary drainage (K11: 3,092 m3 of
the 7,317 m3), so the raw column alone exceeds both limits and cannot be compared with them.

- K10: the release must be the room (1,208 m3) to 0.5 % and below Sy dh (3,592 m3). On this build it is 1,205.3 m3.
- K11: the release must be Sy dh (4,225 m3) to 0.5 % and below the room (6,575 m3). On this build it is 4,225.2 m3.

Mutant (GWVadoseModel.cpp, the bisected release `MoveBottom(col,S,zn,...)` replaced by `MoveBottom(col,S,min(zt,col.ztop),...)`,
the whole excess; built in a separate folder and deleted by path afterwards). The warning is still written and every
identity still closes, but:

- K10 releases 3,543.3 m3 and fails;
- K11 releases 4,352.1 m3 and fails.

Both pass on the fixed build.

## SW-2 (S4): the '#' hint in the "not a date" stop

`:MF6StartDate 1985-10-01# comment` has three tokens, which the command takes. The surplus-value check therefore never runs,
and the date stop gave no hint. The stop now adds "; a # glued to a value is part of it, as in '1985-10-01#': write a blank
before # to start a comment" when a word of the value holds a `#`.

- Test: E44f in input_checks.py.
- Documentation: an appendix row in Volume 2 (appendix.tex), a row in the user guide's message table, and the verification
  table's list.

## CB15-1 (S4): the one-model stop with no exchange

When the simulation has two or more models and no EXCHANGES rows, the reason now reads "so the water of any other model
would be outside Raven's balance, and Raven would not drive that model's solution". The text for a simulation with exchanges
is unchanged, so E42b still holds.

- Test: E42c (an OLF6 model beside the GWF model, no exchange) requires the new reason and requires that "exchange would"
  and "transport" are absent.
- Documentation: the appendix row and the user guide row now say both forms.

## The manual's numbers (manual_two_volumes.md, items 1-5)

Source: the 20-year run of the Liard example in /home/claude/rebuild/wt/p29/ws_work/Workshop_1_Getting_Started/work_full.
Its Liard.rvi, .rvg, .rvh and .rvp are byte-identical to examples/Liard_groundwater. It was run with the release binary
(e840ae5).

1. **15 June 1996.** The run's row is: seepage 19,087,047.44; storage release -3,925,211.504; recharge 21,365,037.27; river
   leakage 2,978,676.94; discharge to rivers 1,331,455.26; applied -1,647,221.68. These are accounting.tex's numbers (and
   Volume 1's). inputs_outputs.tex's sample row (19,087,056.98 and -3,925,200.44) was wrong and is corrected to 19,087,047.44
   and -3,925,211.50.
2. **13,800 against 13,000 km2.** The two numbers measure different things:
   - subbasins 52, 48 and 43 hold 13,793 km2 of HRU area (108 HRUs);
   - their 85 coupled HRUs (with an aquifer profile) hold 13,641 km2;
   - the 3,252 active 2 km columns cover 13,008 km2.

   The tutorial now gives the subbasins' area and the coupled HRUs' area. The cell-size paragraphs (u_build.tex,
   building.tex) say that the 13,000 km2 is the area of the active cells, a little less than the 13,600 km2 of the coupled
   HRUs.
3. **8,840 active cells against 3 x 3,252.** From GWModelSummary.txt: 3,252 active columns; 8,840 active cells; 916
   pass-through cells. The profiles are VALLEY_ALLUVIUM (3 layers, 2,794 columns) and UPLAND_TILL (1 layer, 458 columns).
   2,794 x 3 + 458 = 8,840, and 458 x 2 = 916. The tutorial now says so.
4. **Synthetic calibration.** No log of the calibration with unrounded estimates was found in the repositories. The table's
   errors are now those of the values shown: gravel S_y 0.239 against 0.25 is -4.4 %, and upland-till K 0.149 against 0.2
   is -25.5 % (it was -25 %). Gravel K 47.7 against 50, -4.6 %, was already right. The caption says that the error is that
   of the value shown.
5. **`:BedrockSurface file [METRES]`** in the .rvg table of inputs_outputs.tex, with "METRES as for :LandSurface".

## Figures in Volume 1

Each figure is shared through one file. The inline TikZ figures that were added are moved into figures/tikz_*.tex, and
both volumes now \input them. Volume 2's figures and labels are unchanged. Each figure in Volume 1 has a plain-language
caption, and the text refers to it.

| Volume 1 label | File | Chapter, section |
|---|---|---|
| fig:utimeline | figures/tikz_timeline.tex (from accounting.tex) | u_intro, One day of the coupled model |
| fig:uhrucells | figures/tikz_hrucells.tex (from building.tex) | u_build, HRU polygons |
| fig:ulayers | figures/tikz_layers.tex (from building.tex) | u_build, Describing the aquifer |
| fig:upotsurf | figures/tikz_potsurf.tex (from concepts.tex) | u_build, Describing the aquifer |
| fig:ulinking | figures/tikz_linking.tex | u_exchanges, Recharge |
| fig:ucurves | figures/fig_curves.png | u_exchanges, Seepage back to Raven |
| fig:uriver | figures/tikz_river.tex (from exchanges.tex) | u_exchanges, Rivers |
| fig:uszsubgrid | figures/fig_sz_subgrid.png | u_exchanges, A water table in the soil |
| fig:uvzkinematic | figures/fig_vz_kinematic.png | u_exchanges, The unsaturated zone |
| fig:uvzlag | figures/fig_vz_lag_cascade.png | u_exchanges, The unsaturated zone |
| fig:uvzclasses | figures/fig_vz_classes.png | u_exchanges, The unsaturated zone |
| fig:uplacing | figures/fig_placing.pdf | u_existing, Telling Raven where the model is |

Volume 1 already had "The same model on four grids" (fig:ugrids), the exchanges, the soil-zone regimes, the hillslope,
the working copy and the periods.

Left in the Reference only, as verification or result plots: the soil-zone test figures (fig_sz_caprise, delay,
drainage, rise, timing, classes), the hillslope figure (already in both), connectivity, hotstart, rough cases, and the
verification figures.
