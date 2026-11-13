# Copyright and licensing (Workshop 1)

This folder holds the Liard River example of the Raven-MODFLOW 6 groundwater coupling, as Workshop 1 ships it.
Copyright (c) 2026 Rezgar Arabzadeh. All rights not granted by the licenses below are reserved.
Paths are given from the workshop folder (Workshop_1_Getting_Started/).

| Part | Copyright | License |
|---|---|---|
| Raven with the coupling (`bin/Raven`) | the Raven Development Team; the coupling and the changes to Raven by Rezgar Arabzadeh | Artistic License 2.0 (`bin/LICENSE-Raven.txt`) |
| MODFLOW 6 library (`bin/libmf6.so`, the unchanged library of the official release) | U.S. Geological Survey | public domain; licence and disclaimer in `bin/NOTICE-MODFLOW6.txt` |
| Scripts (`scripts/`; `RavenMF6InstallCheck.py` is part of RavenHydroFramework) | Rezgar Arabzadeh | Artistic License 2.0 (`bin/LICENSE-Raven.txt`) |
| Workshop text (the PDF and `tex/`) and the README files | Rezgar Arabzadeh | Creative Commons Attribution 4.0 International (https://creativecommons.org/licenses/by/4.0/) |
| Liard River model inputs (`model/start/`, `model/finished/`) | their original authors | not relicensed; see `model/start/DATA_NOTICE.md` |

## Differences from the Standard Version of Raven
As the Artistic License 2.0 asks for modified versions, the differences of `bin/Raven` from Raven 4.15 (v593) are
documented file by file in the manual of the coupling (chapter "Developer guide and limitations", "Changes to existing
Raven files", in https://github.com/rarabzad/RavenHydroFramework-extra) and in full in the branch `mf6-coupling` of
https://github.com/rarabzad/RavenHydroFramework. The modifications are offered to the Raven Development Team for
inclusion in Raven under the Artistic License 2.0.

## Third-party names
Raven and MODFLOW are the names of their respective projects; their use here describes compatibility only.
