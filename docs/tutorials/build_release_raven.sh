#!/bin/bash
# SPDX-License-Identifier: Artistic-2.0
# build_release_raven.sh - builds the Raven that the workshop zips ship in bin/: a Linux x86_64 executable that runs on
# glibc 2.28 or newer (Ubuntu 20.04, Debian 10, RHEL 8 and later, and current WSL images). It links the C++ runtime
# statically and the C library dynamically (glibc 2.28 symbol versions), so it can still load libmf6.so with dlopen.
#
#     build_release_raven.sh RAVEN_CHECKOUT BUILD_DIR OUT_EXE [COMMIT]
#
#   RAVEN_CHECKOUT  a git checkout of RavenHydroFramework with the coupling (its src/ and Makefile are used, unchanged)
#   BUILD_DIR       scratch folder for the objects (created)
#   OUT_EXE         the executable to write (pass it to build_tutorials.py --package --raven OUT_EXE)
#   COMMIT          the commit to build (default HEAD); it is exported with git archive, so the checkout is not touched
#
# Needs git, make, strip, objdump (binutils), Python 3 and the zig compiler ZIG_VERSION below (C++ through clang and
# libc++, any glibc as target). The zips are built with that version. A zig of that version on the PATH is used;
# otherwise the script installs the Python package ziglang==ZIG_VERSION into BUILD_DIR/zig (pip, no root). The compiler
# flags are the script's own: -O2 -std=c++11 -fPIC -Wno-deprecated and -ldl, plus -Wno-date-time (zig rejects __DATE__
# by default). They are not those of the repository's builds (CMake Release uses -O3 -DNDEBUG; the Makefile sets no
# optimisation). The build date in Raven's banner (__DATE__) is the commit's date: the script sets SOURCE_DATE_EPOCH to
# the commit's committer time (git log -1 --format=%ct COMMIT), which clang uses for __DATE__ and __TIME__. So the same
# commit gives the same executable, byte for byte, on any day. zig keeps compiled objects in its cache without regard to
# SOURCE_DATE_EPOCH, so the script also passes the date as a macro (-DRAVEN_SOURCE_DATE_EPOCH=...; Raven does not use
# it): an object compiled with another date is then not taken from the cache. The order of the objects on the link
# line enters the executable's bytes, so the script gives make the source files sorted by name (LC_ALL=C) instead of
# the Makefile's $(wildcard *.cpp), whose order depends on the version of GNU make. At the end it prints the highest
# GLIBC symbol version the executable needs; the script fails if it is above 2.28.
set -euo pipefail
SRC=$(cd "$1" && pwd); B=$2; OUT=$(realpath -m "$3"); COMMIT=${4:-HEAD}
TARGET_GLIBC=2.28
ZIG_VERSION=0.17.1
mkdir -p "$B"; B=$(cd "$B" && pwd)
if command -v zig >/dev/null 2>&1 && [ "$(zig version)" = "$ZIG_VERSION" ]; then
  ZIG="zig"
else
  if [ "$(PYTHONPATH="$B/zig" python3 -m ziglang version 2>/dev/null)" != "$ZIG_VERSION" ]; then
    python3 -m pip install -q --upgrade --target "$B/zig" "ziglang==$ZIG_VERSION"
  fi
  ZIG="env PYTHONPATH=$B/zig python3 -m ziglang"
fi
echo "zig $($ZIG version)"
if [ "$($ZIG version)" != "$ZIG_VERSION" ]; then
  echo "ERROR: zig $ZIG_VERSION is needed, found $($ZIG version)"; exit 1
fi
# the sources of the commit, flat in BUILD_DIR/src (as the repository's Makefile expects); every object is compiled
# again (the Makefile does not track headers, so an object of an earlier commit could be linked)
rm -rf "$B/export"; mkdir -p "$B/export" "$B/src"
git -C "$SRC" archive "$COMMIT" src | tar -x -C "$B/export"
for f in "$B"/export/src/*; do [ -f "$f" ] || continue; t="$B/src/$(basename "$f")"; cmp -s "$f" "$t" || cp "$f" "$t"; done
for f in "$B"/src/*.cpp "$B"/src/*.h; do [ -e "$B/export/src/$(basename "$f")" ] || rm -f "$f" "${f%.cpp}.o"; done
rm -rf "$B/export"
REV=$(git -C "$SRC" rev-parse --short "$COMMIT")
# the build date of the banner: the commit's date, so that a rebuild on another day gives the same bytes
SOURCE_DATE_EPOCH=$(git -C "$SRC" log -1 --format=%ct "$COMMIT"); export SOURCE_DATE_EPOCH
rm -f "$B"/src/*.o "$B/src/Raven.exe"
echo "building Raven $REV for x86_64-linux-gnu.$TARGET_GLIBC (build date $(date -u -d "@$SOURCE_DATE_EPOCH" '+%b %e %Y'), the commit's date)"
cd "$B/src"
SRCFILES=$(LC_ALL=C ls -- *.cpp | tr '\n' ' ')   # sorted: the link order, and so the bytes, do not depend on make
make -j"$(nproc)" srcfiles="$SRCFILES" CXX="$ZIG c++ -target x86_64-linux-gnu.$TARGET_GLIBC" \
     CXXFLAGS="-Wno-deprecated -Wno-date-time -std=c++11 -fPIC -O2 -DRAVEN_SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" LDLIBS="-ldl" > make.log 2>&1 \
  || { grep -m20 -B2 -A5 "error" make.log; exit 1; }
cp Raven.exe "$OUT"
strip "$OUT"                     # zig keeps the symbol tables; the release does not need them
MAXV=$(objdump -T "$OUT" | grep -o 'GLIBC_[0-9.]*' | sed 's/GLIBC_//' | sort -V | tail -1)
echo "built $OUT (Raven $REV); highest GLIBC symbol version needed: $MAXV"
if [ "$(printf '%s\n%s\n' "$MAXV" "$TARGET_GLIBC" | sort -V | tail -1)" != "$TARGET_GLIBC" ]; then
  echo "ERROR: $OUT needs GLIBC_$MAXV, more than $TARGET_GLIBC"; exit 1
fi
if objdump -p "$OUT" | grep -q 'NEEDED.*libstdc++'; then
  echo "ERROR: $OUT links libstdc++ dynamically"; exit 1
fi
