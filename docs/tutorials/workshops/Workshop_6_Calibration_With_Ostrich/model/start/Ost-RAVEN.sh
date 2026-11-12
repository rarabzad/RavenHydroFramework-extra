#!/bin/bash
# Ost-RAVEN.sh - runs the model once for Ostrich, which has just written Creek.rvp from Creek.rvp.tpl
set -e
cp ./Creek.rvp model/Creek.rvp
cd model
rm -f output/Diagnostics.csv          # a run that fails then stops Ostrich instead of reusing old results
"$RAVEN" Creek -o output/ > /dev/null
cd ..
exit 0
