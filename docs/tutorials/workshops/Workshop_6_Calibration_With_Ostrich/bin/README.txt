bin/ - the programs of this workshop
====================================

Raven                 Raven with the MODFLOW 6 groundwater coupling, for Linux (x86_64).
libmf6.so             The MODFLOW 6 library, for Linux (x86_64). Raven loads it from this folder:
                      keep the two files together.
LICENSE-Raven.txt     the licence of Raven (Artistic License 2.0, full text)
NOTICE-MODFLOW6.txt   the licence and disclaimer of MODFLOW 6 (public domain, U.S. Geological Survey)

The programs and the two licence files are not kept in the source repository: they are put here when the
workshop zips are made (build_tutorials.py --package), and this file then lists the versions.

Which Linux: x86_64 with glibc 2.34 or newer, for example Ubuntu 22.04 or newer, Debian 12 or newer, RHEL/Rocky 9
or newer, Fedora 35 or newer, and the Ubuntu of the Windows Subsystem for Linux (WSL). The limit is set by libmf6.so
(the official MODFLOW 6 build needs glibc 2.34); Raven itself needs glibc 2.28 and contains its own C++ runtime. On
Windows, run the programs in WSL: see the README.txt of this workshop. They do not run on macOS.

If Raven does not start
-----------------------
- "Permission denied": make it executable with   chmod +x bin/Raven
- A message with "version `GLIBC_2.34' not found" (for example after "cannot load MODFLOW 6 library"): your Linux
  is older than the programs need (glibc 2.34). Check yours with   ldd --version   Use a newer Linux; on Windows install a current Ubuntu in WSL:
      wsl --install -d Ubuntu-24.04
- "cannot load MODFLOW 6 library": libmf6.so is not in the same folder as Raven.

Licences
--------
Raven: Copyright 2008-2026 the Raven Development Team; the groundwater coupling Copyright 2026 Rezgar
Arabzadeh. Licensed under the Artistic License 2.0: full text in LICENSE-Raven.txt (a copy of the LICENSE file of
the Raven source code). This Raven is a modified version of Raven: its source code, with the changes documented, is
in the RavenHydroFramework repository (https://github.com/rarabzad/RavenHydroFramework, branch mf6-coupling) and its
documentation in RavenHydroFramework-extra (https://github.com/rarabzad/RavenHydroFramework-extra). It was compiled
with docs/tutorials/build_release_raven.sh of RavenHydroFramework-extra (zig/clang, libc++ linked statically).

MODFLOW 6: software of the U.S. Geological Survey, in the public domain (licence "Public Domain, CC0-1.0"); see
NOTICE-MODFLOW6.txt. libmf6.so is the unchanged library of the official release.

Raven and MODFLOW are the names of their projects; they are used here to describe the programs only.
