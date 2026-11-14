Raven-MODFLOW 6 workshops
Workshop 6: Calibration with OSTRICH (DDS)
==========================================

Start with the PDF, Workshop_6_Calibration_With_Ostrich.pdf.
It gives every step: what to do, the exact command or file change, what you should see, and what to
check.

What this workshop covers
-------------------------
- Calibrate the groundwater model of Tutorial Creek against streamflow and heads with OSTRICH (DDS).
- Learn which parameters the observations can see, and why a first attempt failed.
- Validate the calibrated parameters on two years the calibration has not seen.

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
- No Python is needed.
- OSTRICH, the calibration program, is not included. Get it from
  https://www.civil.uwaterloo.ca/envmodelling/Ostrich.html (the Raven-OSTRICH tutorial files) or
  https://www.eng.buffalo.edu/~lsmatott/Ostrich/OstrichMain.html (source code). The workshop was made with
  Ostrich_v20171219_GCC_Linux.exe from Demo_C1 of the Raven-OSTRICH tutorial files (OSTRICH version
  18.04.27). That program must be started through the system loader:
      export OSTRICH="/lib64/ld-linux-x86-64.so.2 $HOME/ostrich/Ostrich_v20171219_GCC_Linux.exe"
  Step 2 of the PDF explains this.
- Earlier workshops: None; Workshop 2 is helpful.

Time needed
-----------
About 30 minutes of work, plus about 28 minutes of computing for the calibration.

How to start
------------
Open Workshop_6_Calibration_With_Ostrich.pdf and follow it from Step 1. Step 1 unpacks this zip in your home
folder and sets the variables WS and RAVEN; a later step copies model/start to the folder work, where you
run the model. If you have already unpacked the zip in your home folder, skip the unzip line of Step 1
(typed again, unzip asks whether to replace each file). In every new terminal, type the two export lines of
Step 1 again.

Folder map
----------
README.txt          this file
Workshop_6_Calibration_With_Ostrich.pdf
                    the workshop text (above)
bin/                Raven and libmf6.so for Linux; bin/README.txt gives their versions,
                    LICENSE-Raven.txt and NOTICE-MODFLOW6.txt their licences
model/start/        the calibration folder: ostIn.txt, Creek.rvp.tpl, Ost-RAVEN.sh, save_best.sh, and the
                    Raven model with the observations in model/
model/finished/     the calibration as it ended: OstOutput0.txt, OstModel0.txt, best/, validation/, and the
                    record of a first attempt in first_attempt/
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
