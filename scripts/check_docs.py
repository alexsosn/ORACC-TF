#!/usr/bin/env python3
"""Fail closed when generated reference documentation drifts.

Phase 0 establishes two contracts: manual regions must never disappear or be
silently edited by generation, and a checked-in feature reference must be
byte-identical to regeneration from the same TF dataset. Later phases can add
more generated reports without changing this ownership boundary.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from gen_docs import DocsGenerationError, generate, manual_regions


def _manual_map(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for block in manual_regions(text):
        first = block.splitlines()[0]
        name = first.removeprefix("<!-- manual:begin ").removesuffix(" -->")
        result[name] = block
    return result


def check_manual(generated: Path, baseline: Path) -> list[str]:
    problems: list[str] = []
    try:
        current = _manual_map(generated.read_text(encoding="utf-8"))
        expected = _manual_map(baseline.read_text(encoding="utf-8"))
    except (OSError, DocsGenerationError) as exc:
        return [f"manual region check failed: {exc}"]

    for name, block in expected.items():
        if name not in current:
            problems.append(f"manual region {name!r} was removed")
        elif current[name] != block:
            problems.append(f"manual region {name!r} changed")
    return problems


def check_regeneration(tf_location: Path, generated: Path) -> list[str]:
    if not generated.is_file():
        return [f"generated reference is missing: {generated}"]
    with tempfile.TemporaryDirectory(prefix="oracc-tf-docs-") as tmp:
        candidate = Path(tmp) / generated.name
        candidate.write_bytes(generated.read_bytes())
        try:
            generate(tf_location, candidate)
        except DocsGenerationError as exc:
            return [str(exc)]
        if candidate.read_bytes() != generated.read_bytes():
            return [f"generated reference drift: rerun scripts/gen_docs.py for {generated}"]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--manual-regions-only", action="store_true")
    parser.add_argument("--tf", type=Path)
    args = parser.parse_args()

    problems: list[str] = []
    if args.manual_regions_only:
        if args.generated is None or args.baseline is None:
            parser.error("--manual-regions-only requires --generated and --baseline")
        problems.extend(check_manual(args.generated, args.baseline))
    else:
        if args.generated is None or args.tf is None:
            parser.error("full drift check requires --generated and --tf")
        problems.extend(check_regeneration(args.tf, args.generated))

    for problem in problems:
        print(problem)
    print("FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
