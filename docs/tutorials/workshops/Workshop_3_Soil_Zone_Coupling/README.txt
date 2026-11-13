Raven-MODFLOW 6 workshops
Workshop 3: The soil-zone coupling
==================================

Start with the PDF, Workshop_3_Soil_Zone_Coupling.pdf.
It gives every step: what to do, the exact command or file change, what you should see, and what to
check.

What this workshop covers
-------------------------
- Let the water table rise into Raven's soil (:SoilZone PHYSICAL) and compare with the default (CONCEPTUAL).
- Add unsaturated columns below the soil (:SoilZoneVadose RICHARDS, KINEMATIC, LAG) and depth classes.
- Read GWSoilExchange.csv and GWBudget.csv, plot with plot_soilzone.py, compare the runs.

What you need
-------------
- A Linux computer (x86_64) with a terminal and glibc 2.34 or newer: Ubuntu 22.04 or newer, Debian 12 or
  newer, RHEL/Rocky 9 or newer ("ldd --version" shows yours). Raven and the MODFLOW 6 library for Linux are
  in bin/. On an older Linux, Raven stops with "version `GLIBC_2.34' not found" (see bin/README.txt).
- Windows: use the Windows Subsystem for Linux (WSL). In PowerShell type "wsl --install", restart, open
  "Ubuntu" from the Start menu, and do the whole workshop in that Ubuntu terminal. If your WSL Ubuntu is
  older than 22.04, install a newer one: "wsl --install -d Ubuntu-24.04". Your Windows files are
  under /mnt/c/ (for example /mnt/c/Users/YOUR_NAME/Downloads). The programs in bin/ do not run in the
  Windows command prompt or in PowerShell.
- macOS: the programs in bin/ do not run on macOS; use a Linux computer.
- Python 3 with numpy, pandas and matplotlib (Step 2 of the PDF installs them).
- Earlier workshops: None; Workshop 2 is helpful (its finished model is the start model here).

Time needed
-----------
About 45 minutes.

How to start
------------
    cd ~
    unzip -q Workshop_3_Soil_Zone_Coupling.zip
    cd Workshop_3_Soil_Zone_Coupling
    export WS=$PWD
    export RAVEN=$WS/bin/Raven
    cp -r $WS/model/start $WS/work
    cd $WS/work
Then follow the PDF from Step 1 (it repeats these commands and explains them). In every new terminal, type
the two export lines again.

Folder map
----------
README.txt          this file
Workshop_3_Soil_Zone_Coupling.pdf
                    the workshop text (above)
bin/                Raven and libmf6.so for Linux; bin/README.txt gives their versions,
                    LICENSE-Raven.txt and NOTICE-MODFLOW6.txt their licences
model/start/        the finished model of Workshop 2 (Tutorial Creek with groundwater)
model/step_06/      the model as it is in Step 6 (soil zone PHYSICAL)
model/step_10/      the model as it is in Step 10 (unsaturated columns, RICHARDS)
model/finished/     the model at the end of the workshop
scripts/            the helper scripts of this workshop:
    compare_runs.py    compares the runs: budget means, water-table depth, streamflow
    plot_soilzone.py   plots the exchange between the soil zone and the aquifer
    plot_vadose.py     plots the unsaturated columns of several runs
tex/                the LaTeX source of the PDF:
    main.tex          the main file; it reads the parts below
    preamble.tex      the layout
    sections/         one file per section, in order (01_..., 02_..., ...)
    generated/        the numbers (values.tex), program outputs and file changes quoted in the text
    figures/          the figures
work/ and the out*/ folders inside it are made by you during the workshop.

How to rebuild the PDF
----------------------
Needs pdflatex (TeX Live; on Ubuntu: sudo apt install texlive-latex-extra texlive-fonts-extra).
    cd tex
    pdflatex main.tex
    pdflatex main.tex
The second run fills in the table of contents and the references. The result is tex/main.pdf.
The numbers, outputs and figures in tex/generated/ and tex/figures/ come from the actual runs. They are
made by build_tutorials.py in the RavenHydroFramework-extra repository (docs/tutorials/), which reruns every
step of every workshop.

Licences
--------
The text, model files and figures of this workshop: Creative Commons Attribution 4.0 International
(CC BY 4.0, https://creativecommons.org/licenses/by/4.0/). The scripts: Artistic License 2.0, as Raven.
Raven and MODFLOW 6 in bin/: see bin/README.txt.
Tutorial Creek is synthetic: its weather, maps and observations were generated for these workshops.
