# Copyright and licensing

## Raven–MODFLOW 6 groundwater coupling
Copyright (c) 2026 Rezgar Arabzadeh. All rights not granted by the licenses below are reserved.

This repository (RavenHydroFramework-extra) holds the documentation, examples, tests and tools of the coupling. Its source code is
part of Raven (RavenHydroFramework), offered to the Raven Development Team as pull requests.

| Part | Copyright | License |
|---|---|---|
| Coupling source code in RavenHydroFramework: `GroundwaterModel.*`, `GWExternal.cpp`, `GWGeometry.*`, `GWGrid.*`, `GWSoilZone*`, `GWUtil.h`, `GWVadose*`, `MF6Engine.*`, `ParseGWFile.cpp`; the CMake modules `cmake/RavenMF6*` | Rezgar Arabzadeh | Artistic License 2.0 (`LICENSE`) |
| Changes to existing Raven files (marked "Modified 2026 by Rezgar Arabzadeh") | the Raven Development Team; changes by Rezgar Arabzadeh | Artistic License 2.0 |
| Tests and tools (`tests/`, `tools/`, `examples/Liard_groundwater/tools_*.py`) | Rezgar Arabzadeh | Artistic License 2.0 (`LICENSE`) |
| Manual and user guide (`docs/`) | Rezgar Arabzadeh | Creative Commons Attribution 4.0 International (`docs/LICENSE-docs.md`) |
| Liard River model inputs (`examples/Liard_groundwater/`) | their original authors | not relicensed; see `examples/Liard_groundwater/DATA_NOTICE.md` |
| Synthetic MODFLOW 6 example model (`examples/Liard_existing_model/model/`) | Rezgar Arabzadeh | Artistic License 2.0 (`LICENSE`) |
| MODFLOW 6 | U.S. Geological Survey | not included; downloaded by `tools/get_mf6.py` from the MODFLOW 6 releases |

## Differences from the Standard Version of Raven
As the Artistic License 2.0 asks for modified versions, the differences from Raven 4.15 (v593) are documented file by
file in the manual (chapter "Developer guide and limitations", "Changes to existing Raven files") and in full in the
pull requests to RavenHydroFramework. The modifications are offered to the Raven Development Team for inclusion in
Raven under the Artistic License 2.0.

## Third-party names
Raven and MODFLOW are the names of their respective projects; their use here describes compatibility only.
