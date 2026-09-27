#!/usr/bin/env python3
"""Emit the ISSUE-124 source-to-TF audit for an existing candidate."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from oracc_tf import audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--tf-dir", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--fail-on-unexplained", action="store_true")
    args = parser.parse_args()

    report = audit.build_report(
        data=args.data,
        tf_dir=args.tf_dir,
        source_revision=args.source_revision,
        dataset=args.dataset,
    )
    sys.stdout.buffer.write(audit.canonical_bytes(report))
    return int(args.fail_on_unexplained and report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
