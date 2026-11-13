Raven-MODFLOW 6 workshops
Workshop 1: Getting started
===========================

Start with the PDF, Workshop_1_Getting_Started.pdf.
It gives every step: what to do, the exact command or file change, what you should see, and what to
check.

What this workshop covers
-------------------------
- Check that Raven runs and loads the MODFLOW 6 library (installation check).
- Run the Liard River example: a Raven model with a groundwater model that Raven builds.
- Read the groundwater outputs: GWModelSummary.txt, GWBudget.csv, GWHRUState.csv.
- Check the water balance with tools_audit.py and plot the results with plot_gw.py.

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
- Earlier workshops: None. This is the first workshop.

Time needed
-----------
About 30 minutes, plus about 11 minutes for the optional 20-year run.

How to start
------------
    cd ~
    unzip -q Workshop_1_Getting_Started.zip
    cd Workshop_1_Getting_Started
    export WS=$PWD
    export RAVEN=$WS/bin/Raven
    cp -r $WS/model/start $WS/work
    cd $WS/work
Then follow the PDF from Step 1 (it repeats these commands and explains them). In every new terminal, type
the two export lines again.

Folder map
----------
README.txt          this file
Workshop_1_Getting_Started.pdf
                    the workshop text (above)
bin/                Raven and libmf6.so for Linux; bin/README.txt gives their versions,
                    LICENSE-Raven.txt and NOTICE-MODFLOW6.txt their licences
model/start/        the Liard River example (Raven files, rasters, GeoJSON, forcing and observation data;
                    README.md and DATA_NOTICE.md describe it;
                    NOTICE.md is the copyright notice that DATA_NOTICE.md points to)
model/finished/     only the file this workshop changes (Liard.rvi, one year); its README.txt explains
scripts/            the helper scripts of this workshop:
    RavenMF6InstallCheck.py   the installation check
    tools_audit.py            checks the water balance of a coupled run
    plot_gw.py                plots the groundwater budget, water table and map of a run
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
The Liard River model inputs in model/ come from the original Liard River Raven model and remain the
property of their authors (see model/start/DATA_NOTICE.md).
Raven and MODFLOW 6 in bin/: see bin/README.txt.
