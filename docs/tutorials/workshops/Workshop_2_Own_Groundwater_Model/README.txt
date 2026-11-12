Raven-MODFLOW 6 workshops
Workshop 2: Your own groundwater model
======================================

Start with the PDF, Workshop_2_Own_Groundwater_Model.pdf.
It gives every step: what to do, the exact command or file change, what you should see, and what to
check.

What this workshop covers
-------------------------
- Add a groundwater model to an ordinary Raven model (Tutorial Creek).
- Write aquifer classes and profiles, and the groundwater file Creek.rvg.
- Read a DEM and a bedrock surface (GeoTIFF and ESRI ASCII); give the projection with :InputCRS.
- Add head boundaries, a pumping well and observation wells; refine the grid.
- Run the coupled model and check its water budget.

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
- Earlier workshops: None; Workshop 1 is helpful.

Time needed
-----------
About one hour.

How to start
------------
    cd ~
    unzip -q Workshop_2_Own_Groundwater_Model.zip
    cd Workshop_2_Own_Groundwater_Model
    export WS=$PWD
    export RAVEN=$WS/bin/Raven
    cp -r $WS/model/start $WS/work
    cd $WS/work
Then follow the PDF from Step 1 (it repeats these commands and explains them). In every new terminal, type
the two export lines again.

Folder map
----------
README.txt          this file
Workshop_2_Own_Groundwater_Model.pdf
                    the workshop text (above)
bin/                Raven and libmf6.so for Linux; bin/README.txt gives their versions,
                    LICENSE-Raven.txt and NOTICE-MODFLOW6.txt their licences
model/start/        Tutorial Creek: a Raven model without groundwater, with the data a groundwater model needs
model/finished/     the same model at the end of the workshop (with Creek.rvg)
scripts/            the helper scripts of this workshop:
    plot_gw.py           plots the groundwater budget, water table, map and observation wells of a run
    plot_hydrograph.py   plots the streamflow of two runs
    tools_audit.py       checks the water balance of a coupled run
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
