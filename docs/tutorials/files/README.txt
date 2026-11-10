Raven-MODFLOW 6 tutorials: tutorial files
==========================================

Six click-by-click tutorials for the groundwater coupling of Raven (Raven + MODFLOW 6). The PDFs are in pdf/ (one per
tutorial, and Raven_MF6_Tutorials.pdf with all six). Each tutorial folder holds its start state (what you begin with)
and its finished state (every file as it is at the end of the tutorial).

  scripts/                           plot_gw.py, compare_runs.py, plot_tracks.py (Python 3, numpy, pandas, matplotlib)
  t2_own_model/                      Tutorial Creek: a Raven model, and the groundwater model Raven builds for it
  t3_soil_zone/                      the soil-zone coupling (:SoilZone PHYSICAL, unsaturated columns)
  t4_existing_model/                 coupling an existing MODFLOW 6 model (in feet)
  t5_restarts_ensembles_particles/   hotstarts from solution.rvc, a Monte Carlo ensemble, particle tracking
  t6_calibration/                    calibration with OSTRICH (DDS) against streamflow and heads; validation

Tutorial 1 (getting started) has no files of its own: it uses the package's examples/Liard_groundwater.

Needs the Linux release package of Raven with the MODFLOW 6 coupling that comes with these files (Raven_MF6_package.zip;
Windows: use WSL). The tutorials were made with the package built from Raven code commit f8ee662 and
RavenHydroFramework-extra commit 7be65a6; the package's source/COMMITS.txt names its commits (they must be these or later
ones). With an older package some numbers differ from those in the tutorials and some tools are missing.
Tutorial 6 needs OSTRICH, which is not included: get it from https://www.civil.uwaterloo.ca/envmodelling/Ostrich.html
or https://www.eng.buffalo.edu/~lsmatott/Ostrich/OstrichMain.html (documentation: https://usbr.github.io/ostrich).
The tutorial was made with Ostrich_v20171219_GCC_Linux.exe of the Raven-Ostrich tutorial files (it reports OSTRICH version 18.04.27).

Start with Tutorial 1. Tutorial Creek is synthetic: its weather, maps and observations were generated for these
tutorials. The files are licensed under CC BY 4.0, the scripts under the Artistic License 2.0 (as Raven).
