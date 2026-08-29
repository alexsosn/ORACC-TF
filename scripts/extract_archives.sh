#!/usr/bin/env bash
# Extract ORACC project ZIPs into the project/subproject tree they already encode.
#
# ORACC distributes each project (and each subproject) as its own ZIP from
# http://oracc.org/doc/opendata/. Every archive already carries its correct
# path internally:
#
#     blms.zip        ->  blms/...              (top-level project)
#     atae-ctn1.zip   ->  atae/ctn1/...         (subproject of atae)
#     saao-saa01.zip  ->  saao/saa01/...
#
# So the hyphenated filenames do not need to be parsed: extracting in place
# reproduces the grouping. Parent and subproject archives write disjoint paths
# and merge cleanly (e.g. caspo.zip + caspo-akkpm.zip -> caspo/ + caspo/akkpm/).
#
# Usage: scripts/extract_archives.sh [DATA_DIR]     (default: ./data)

set -uo pipefail
DATA_DIR="${1:-data}"
cd "$DATA_DIR" || { echo "no such directory: $DATA_DIR" >&2; exit 1; }

shopt -s nullglob
archives=(*.zip)
if [ ${#archives[@]} -eq 0 ]; then
  echo "no .zip archives in $DATA_DIR" >&2; exit 1
fi

ok=0; fail=0
for z in "${archives[@]}"; do
  if unzip -o -q "$z" -d .; then
    ok=$((ok+1))
  else
    fail=$((fail+1)); echo "FAILED: $z" >&2
  fi
done

echo "extracted $ok archive(s), $fail failure(s)"
echo "run scripts/verify_extraction.py to check the result against the manifests"
[ "$fail" -eq 0 ]
