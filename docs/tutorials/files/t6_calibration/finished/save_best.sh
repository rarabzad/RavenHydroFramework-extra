#!/bin/bash
# save_best.sh - Ostrich runs this after every run that is the best so far
set -e
mkdir -p best
cp model/Creek.rvp               best/Creek.rvp
cp model/output/Diagnostics.csv  best/Diagnostics.csv
cp model/output/Hydrographs.csv  best/Hydrographs.csv
cp model/output/GWHeads.csv      best/GWHeads.csv
exit 0
