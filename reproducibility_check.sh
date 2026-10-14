#!/usr/bin/env bash
# Three untouched runs from a clean state; all outputs must be byte-identical.
set -e
cd "$(dirname "$0")"
for i in 1 2 3; do python -m freighttiger.run --out results/run_$i.csv >/dev/null; done
sha256sum results/run_1.csv results/run_2.csv results/run_3.csv
diff results/run_1.csv results/run_2.csv && diff results/run_2.csv results/run_3.csv && echo "IDENTICAL across 3 runs"
cp results/run_1.csv results/output.csv
