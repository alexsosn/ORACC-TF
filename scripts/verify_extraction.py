#!/usr/bin/env python3
"""Verify extracted ORACC data against the ZIP manifests it came from.

Checks that every file listed in every archive exists on disk with a matching
uncompressed size. Catches truncated extractions and partial overwrites.

Usage: scripts/verify_extraction.py [DATA_DIR]      (default: ./data)
"""

import glob
import os
import sys
import zipfile


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data"
    archives = sorted(glob.glob(os.path.join(data_dir, "*.zip")))
    if not archives:
        sys.exit(f"no .zip archives in {data_dir}")

    checked = missing = mismatched = 0
    problems = []
    for archive in archives:
        with zipfile.ZipFile(archive) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                checked += 1
                path = os.path.join(data_dir, info.filename)
                if not os.path.isfile(path):
                    missing += 1
                    problems.append(f"MISSING  {info.filename}  (from {os.path.basename(archive)})")
                elif os.path.getsize(path) != info.file_size:
                    mismatched += 1
                    problems.append(f"SIZE     {info.filename}  (from {os.path.basename(archive)})")

    print(f"archives      : {len(archives)}")
    print(f"files checked : {checked:,}")
    print(f"missing       : {missing}")
    print(f"size mismatch : {mismatched}")
    for p in problems[:40]:
        print("  " + p)
    if len(problems) > 40:
        print(f"  ... and {len(problems) - 40} more")
    print("OK" if not problems else "FAILED")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
