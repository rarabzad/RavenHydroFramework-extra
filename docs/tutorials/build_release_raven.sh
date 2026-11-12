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
# Needs git, make, strip, objdump (binutils), Python 3 and the zig compiler (C++ through clang and libc++, any glibc as target). Without zig on the
# PATH the script installs the Python package ziglang into BUILD_DIR/zig (pip, no root). The flags are those of the
# repository's optimized build (-O2 -std=c++11 -fPIC -Wno-deprecated, -ldl), plus -Wno-date-time (zig rejects __DATE__
# by default; the build date in Raven's banner then comes from __DATE__ as usual). At the end it prints the highest GLIBC
# symbol version the executable needs; the script fails if it is above 2.28.
set -euo pipefail
SRC=$(cd "$1" && pwd); B=$2; OUT=$(realpath -m "$3"); COMMIT=${4:-HEAD}
TARGET_GLIBC=2.28
mkdir -p "$B"; B=$(cd "$B" && pwd)
if command -v zig >/dev/null 2>&1; then
  ZIG="zig"
else
  if ! PYTHONPATH="$B/zig" python3 -m ziglang version >/dev/null 2>&1; then
    python3 -m pip install -q --target "$B/zig" ziglang
  fi
  ZIG="env PYTHONPATH=$B/zig python3 -m ziglang"
fi
echo "zig $($ZIG version)"
# the sources of the commit, flat in BUILD_DIR/src (as the repository's Makefile expects); files that did not change
# keep their date, so that a second build compiles only what changed
rm -rf "$B/export"; mkdir -p "$B/export" "$B/src"
git -C "$SRC" archive "$COMMIT" src | tar -x -C "$B/export"
for f in "$B"/export/src/*; do [ -f "$f" ] || continue; t="$B/src/$(basename "$f")"; cmp -s "$f" "$t" || cp "$f" "$t"; done
for f in "$B"/src/*.cpp "$B"/src/*.h; do [ -e "$B/export/src/$(basename "$f")" ] || rm -f "$f" "${f%.cpp}.o"; done
rm -rf "$B/export"
REV=$(git -C "$SRC" rev-parse --short "$COMMIT")
echo "building Raven $REV for x86_64-linux-gnu.$TARGET_GLIBC"
cd "$B/src"
make -j"$(nproc)" CXX="$ZIG c++ -target x86_64-linux-gnu.$TARGET_GLIBC" \
     CXXFLAGS="-Wno-deprecated -Wno-date-time -std=c++11 -fPIC -O2" LDLIBS="-ldl" > make.log 2>&1 \
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
