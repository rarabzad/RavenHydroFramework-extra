# Running the two MODFLOW 6 examples, step by step

Two examples, both built on the Liard River Raven model (northern British Columbia and Yukon):

| Example | Folder | What it shows | Run time |
|---|---|---|---|
| **A. Raven builds the groundwater model** | `examples/Liard_groundwater` | Raven creates a MODFLOW 6 model under three subbasins from HRU polygons, river lines, a DEM and a bedrock surface | 20 years, about 10 minutes |
| **B. Raven couples an existing MODFLOW 6 model** | `examples/Liard_existing_model` | Raven links its HRUs to a MODFLOW 6 model built separately (`model/`) and takes over its recharge | 2 years, about 5 minutes |

The commands below are for **Windows (Command Prompt)**. Linux and macOS commands follow each step where they differ.

**With the Linux release package** (`Raven_MF6_linux`): Raven and the MODFLOW 6 library are ready in the package's
`bin/`, so skip Part 1 and set `RAVEN=<package>/bin/Raven`; the example folders are the package's `examples/`, the manual
is `Raven_MF6_Manual.pdf` beside them, and the repository files named below (the user guide in `docs/`, `tools/`) are in
`source/raven_extra_docs_tests.tar.gz` (it unpacks as `raven-mf6-extra/`). The package's `README.md` has the commands.

---

## Part 1: set up (once)

### Step 1. Install the tools

- **Git**: https://git-scm.com/download/win
- **CMake** 3.20 or newer: https://cmake.org/download/ (tick "Add CMake to the PATH" when installing)
- **A C++ compiler**: Visual Studio 2022 Community with the workload **Desktop development with C++**
  (https://visualstudio.microsoft.com/). On Linux, `g++`; on macOS, the Xcode command-line tools (`xcode-select --install`).
- **Python 3** (https://www.python.org/downloads/, tick "Add python.exe to PATH"), and for the audit tool:

      python -m pip install pandas

- *Optional*, to build the MODFLOW 6 library from source with Raven (otherwise CMake downloads the official one): a
  Fortran compiler (gfortran from MSYS2 or https://github.com/fortran-lang/setup-fortran on Windows; `gfortran` on Linux;
  `brew install gcc` on macOS), and `python -m pip install meson ninja`. Git (above) is also needed for it.

### Step 2. Get the two repositories, side by side

Raven itself (with the MODFLOW 6 coupling) and this repository (RavenHydroFramework-extra: examples, manual, tests, download script)
are separate. Put both in the same folder:

```
cd %USERPROFILE%
git clone -b mf6-coupling https://github.com/rarabzad/RavenHydroFramework.git
git clone https://github.com/rarabzad/RavenHydroFramework-extra.git
```

(RavenHydroFramework-extra's branch is `main`, the default. After the coupling is merged into Raven, clone
https://github.com/CSHS-CWRA/RavenHydroFramework without `-b mf6-coupling`.) Without network access, the release package's `source/` folder holds both repositories with their whole history as
git bundles; its README's section "Restore the git history" gives the two `git clone` commands, which make the same
two checkouts (`RavenHydroFramework` on `mf6-coupling`, `RavenHydroFramework-extra` on `main`).

### Step 3. Build Raven

```
cd %USERPROFILE%\RavenHydroFramework
cmake -S . -B build
cmake --build build --config Release
```

This builds `build\Release\Raven.exe`. Linux and macOS: the same commands; the program is `build/Raven`.
A warning that NetCDF was not found is normal; the examples do not need it.

The same commands also put the MODFLOW 6 library next to Raven (`build\Release\libmf6.dll`; `build/libmf6.so` or
`build/libmf6.dylib`): CMake builds it from the MODFLOW 6.8.1 source when it finds a Fortran compiler, meson >= 1.7,
ninja and git, and otherwise downloads the official release library (Windows x64, Linux x86_64, Apple Silicon Macs).
Then skip Step 4. On Linux other than x86_64 (e.g. aarch64), Windows on ARM64 and Intel Macs MODFLOW releases no library:
install the tools of Step 1 and add `-DRAVEN_MF6=SOURCE` to the first command (or give a library you have with
`-DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=...`); otherwise CMake warns and builds Raven alone.

*Other ways to build:* open `src\Raven.sln` in Visual Studio, pick **Release** and **x64**, and build
(`src\x64\Release\Raven.exe`); or run `make` in `src/` on Linux and macOS (`src/Raven.exe`).

### Step 4. Get the MODFLOW 6 library (only if Step 3 did not)

If `libmf6` is not next to `Raven.exe` (you built with Visual Studio's `src\Raven.sln`, with `make`, or with
`-DRAVEN_MF6=OFF`):

```
cd %USERPROFILE%\RavenHydroFramework-extra
python tools\get_mf6.py
```

It downloads MODFLOW 6.8.1 for your computer (about 130 MB, once) and ends with
`MODFLOW 6.8.1 library: ...\RavenHydroFramework\lib\mf6\libmf6.dll (48.1 MB)`. Running it again does nothing if the
library is already there. Linux and macOS: `python3 tools/get_mf6.py`. It has no library for Linux other than x86_64,
Windows on ARM64, or Intel Macs (there only `--version 6.6.3`): build Raven with `-DRAVEN_MF6=SOURCE` instead (Step 3).

Raven finds the library there by itself; nothing needs to be set. (If your Raven checkout is not beside RavenHydroFramework-extra, add
`--raven C:\path\to\RavenHydroFramework`.)

### Step 5. Tell the Command Prompt where Raven is

Raven and the examples are in different repositories, so set a variable for this Command Prompt window (repeat it
in every new window):

```
set RAVEN=%USERPROFILE%\RavenHydroFramework\build\Release\Raven.exe
```

Linux and macOS: `RAVEN=~/RavenHydroFramework/build/Raven`, then use `$RAVEN` where the steps below say `%RAVEN%`.

---

## Part 2: Example A – Raven builds the groundwater model

Raven reads the HRU polygons (`Liard_HRUs_standin.geojson`), river lines (`Liard_rivers.geojson`), land surface
(`Liard_dem_standin.asc`) and bedrock (`Liard_bedrock_standin.asc`), builds a 3-layer MODFLOW 6 grid of 2 km cells under
subbasins 52, 48 and 43, and runs MODFLOW 6 alongside Raven every day. The other 62 subbasins run as in the original model.

### Step A1. Go to the example

```
cd %USERPROFILE%\RavenHydroFramework-extra\examples\Liard_groundwater
```

### Step A2. Look at what makes it a groundwater model (optional)

- `Liard.rvi`: `:GroundwaterModel MODFLOW6`, and percolation from the coupled HRUs goes to `GROUNDWATER`
- `Liard.rvh`: the `AQUIFER_PROFILE` column says which HRUs sit on the aquifer
- `Liard.rvp`: `:AquiferClasses`, `:AquiferProfiles`, `:AquiferProfileParameters` at the end of the file
- `Liard.rvg`: the geometry files and the grid size (`:GridCellSize 2000.0`)

### Step A3. (Optional) Shorten the first run

The example runs 20 years: the `:Duration` line of `Liard.rvi` reads `:Duration           7305 00:00:00`. For a quick
first try, open `Liard.rvi` in a text editor and change 7305 on that line to 365 (one year, well under a minute). Change
it back for the full run.

### Step A4. Run

```
%RAVEN% Liard -o output\
```

Raven prints the date as it goes. The last lines should be:

    Exiting Gracefully: Successful Simulation

### Step A5. Look at the results

In `output\`:

| File | What it holds |
|---|---|
| `GWModelSummary.txt` | the grid built (layers, cells, active cells, river cells), the MODFLOW library and its version, how each HRU is linked |
| `GWBudget.csv` | every day: recharge from Raven, seepage back to Raven, river exchange, storage change, MODFLOW's balance error |
| `GWHRUState.csv` | every day: water-table depth under each coupled HRU |
| `Hydrographs.csv`, `Diagnostics.csv` | streamflow and fit statistics, as in any Raven run |
| `mf6\` | the MODFLOW 6 model Raven wrote (it can be opened in ModelMuse or FloPy) |

### Step A6. Check the water balance (optional)

```
python tools_audit.py output
```

Lines to look at: `recharge: (Raven - MF6 - dStore - toCHD)/Raven` should be 0, `MF6 cumulative residual / gross flow`
about 1e-10 or smaller, `unconverged steps` 0, and `ERROR lines` 0.

---

## Part 3: Example B – Raven couples an existing MODFLOW 6 model

`model\` holds a MODFLOW 6 model built separately from Raven: UTM zone 10N, 1.5 km cells rotated 15°, four layers, a
steady-state start and 24 monthly stress periods, two pumping wells, 239 river cells, a head boundary at the outlet, and
its own recharge and ET packages. Raven links its HRUs to the model's top layer through the model's map projection,
replaces the model's recharge and ET with its own, and sends the river exchange to its subbasins.

### Step B1. Go to the example

```
cd %USERPROFILE%\RavenHydroFramework-extra\examples\Liard_existing_model
```

### Step B2. Look at the coupling file (optional)

`Liard.rvg` is all it takes:

```
:HRUGeometry       Liard_HRUs_standin.geojson  HRU_ID
:MF6Simulation     model/mfsim.nam
:MF6CRS            EPSG:32610                  # the model's coordinates are UTM zone 10N
:MF6StartDate      1985-10-01                  # the calendar date of the model's time zero
:RavenTakesOver    RCH_MODEL EVT_MODEL         # Raven supplies recharge; the model's ET is replaced
:StreamPackage     RIV_STREAMS AUX SUBBASIN    # river cells carry their Raven subbasin ID
:SeepageToRaven    ON
```

The other Raven files are those of Example A; forcing and observations are read from `..\Liard_groundwater`, so keep
both folders side by side.

### Step B3. Run

```
%RAVEN% Liard -o output\
```

Two years; it ends with `Exiting Gracefully: Successful Simulation`. The run works on a copy of the model in
`output\mf6\`; `model\` is never changed.

### Step B4. Look at the results

The same files as in Example A. `output\GWModelSummary.txt` also describes the coupling:

    existing model        : GWF_LIARD in model/mfsim.nam (DIS, 4 layers x 11466 cells per layer; metres, days)
    cells linked by       : cell outlines from MODFLOW, Transverse Mercator (...)
    packages taken over   : RCH_MODEL EVT_MODEL
    packages in balance   : GHB_OUTLET WEL_PUMPS
    stream package        : RIV_STREAMS (subbasin from auxiliary SUBBASIN)
    HRU coverage          : 99.74% of the coupled HRUs' polygon area lies on active model cells

`GWBudget.csv` has an extra column, *other model packages*, with the net flow of the model's own wells and head boundary.

### Step B5. Check the water balance (optional)

```
python ..\Liard_groundwater\tools_audit.py output
```

Expected (from a test run): recharge identity 0, `MF6 cumulative residual / gross flow` about -1.9e-11,
`unconverged steps` 0, river bookkeeping about -5e-12, `ERROR lines` 0, `max outer iterations` 245 (the first step).
`river loss carried max` is about 1.06e+08 m3: the model's stream package keeps its own conductance and has no supply
limit, so its losing reaches take more than the channels hold (on 271 of the 731 days, from the first day); the part a
channel's runoff, inflow and outflow cannot supply is carried to the next step and taken then (`river loss carried at end`
0; Raven warns on the first ten such steps). The manual explains
this under "Limits" in the chapter "Coupling an existing MODFLOW 6 model".

---

## Part 4: if something goes wrong

| Message or problem | What to do |
|---|---|
| `'...Raven.exe' is not recognized` | The path in `%RAVEN%` is wrong; check with `dir %RAVEN%` and repeat Step 5 in the same window |
| `cannot load MODFLOW 6 library ...` | Run `python tools\get_mf6.py` in RavenHydroFramework-extra (Step 4), or rebuild Raven with CMake (Step 3). The message lists every place Raven looked |
| `MODFLOW 6.8.1 releases no library for Intel Macs` (get_mf6.py) | Use `python3 tools/get_mf6.py --version 6.6.3`, or build Raven with `-DRAVEN_MF6=SOURCE` (Step 3) |
| CMake warning `RAVEN_MF6: no way to get the MODFLOW 6 library ...` | No release library for this computer and no Fortran compiler, meson, ninja or git: install them (Step 1) and configure again with `-DRAVEN_MF6=SOURCE`, or give a library with `-DRAVEN_MF6=PATH -DRAVEN_MF6_PATH=...` |
| `the MODFLOW 6 library ... is version ...; the coupling needs MODFLOW 6 6.5.0 or newer` | An old library was found first: remove `:MF6Library`/`RAVEN_MF6_LIB` naming it, and get 6.8.1 (Step 3 or 4) |
| `ExitGracefully: ... Cannot find file` | Run from inside the example folder (Steps A1 / B1); Example B also needs `..\Liard_groundwater` |
| Some days say `MODFLOW 6 did not converge` | They are flagged in `GWBudget.csv`; see the manual, section "How MODFLOW solves each time step" |
| Anything else | `output\Raven_errors.txt` has the details |

More: the user guide `docs\Raven_MF6_Groundwater_UserGuide.md` and the manual `docs\manual\main.pdf` of the repository
(in the release package: `Raven_MF6_Manual.pdf`, and the user guide inside `source/raven_extra_docs_tests.tar.gz`), chapters
"Building the groundwater model", "Coupling an existing MODFLOW 6 model" and "Applying the coupling".
