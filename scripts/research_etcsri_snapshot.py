#!/usr/bin/env python3
"""Measure an ETCSRI derived-cache ZIP without claiming raw-source semantics.

This research helper intentionally supports only derived per-text CSV archives.
It records reproducible archive identity and column-population statistics while
marking that raw GDL/section/zero-span claims are *not* supported by this
artifact. Raw ORACC JSON requires a separate census before converter design.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


SCHEMA = "oracc-tf-etcsri-research-v1"
REQUIRED_MORPHOLOGY_COLUMNS = ("base", "morph", "morph2")
REPORTED_COLUMNS = (
    "id",
    "form",
    "base",
    "morph",
    "morph2",
    "cf",
    "gw",
    "pos",
    "lang",
    "para",
)


class CensusError(ValueError):
    """The derived cache cannot support the requested research census."""


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_populated(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def census_derived_zip(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise CensusError(f"derived ZIP not found: {path}")

    present_columns: set[str] = set()
    populated: dict[str, int] = defaultdict(int)
    distinct: dict[str, set[str]] = defaultdict(set)
    files = 0
    rows = 0

    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = sorted(
                name
                for name in archive.namelist()
                if not name.endswith("/") and name.lower().endswith(".csv")
            )
            if not members:
                raise CensusError("derived ZIP contains no CSV files")

            for member in members:
                with archive.open(member, "r") as raw:
                    text = (line.decode("utf-8-sig") for line in raw)
                    reader = csv.DictReader(text)
                    if reader.fieldnames is None:
                        raise CensusError(f"CSV has no header: {member}")
                    fieldnames = {name for name in reader.fieldnames if name}
                    present_columns.update(fieldnames)
                    files += 1
                    for row in reader:
                        rows += 1
                        for column in REPORTED_COLUMNS:
                            value = row.get(column)
                            if _is_populated(value):
                                assert value is not None
                                normalized = value.strip()
                                populated[column] += 1
                                distinct[column].add(normalized)
    except zipfile.BadZipFile as exc:
        raise CensusError(f"invalid derived ZIP: {path}") from exc
    except UnicodeDecodeError as exc:
        raise CensusError(f"derived CSV is not UTF-8: {path}") from exc

    missing = [name for name in REQUIRED_MORPHOLOGY_COLUMNS if name not in present_columns]
    if missing:
        raise CensusError(
            "required morphology columns missing: " + ", ".join(missing)
        )

    columns = {
        column: {
            "present": column in present_columns,
            "populated": populated.get(column, 0),
            "distinct": len(distinct.get(column, set())),
        }
        for column in REPORTED_COLUMNS
        if column in present_columns
    }

    return {
        "schema": SCHEMA,
        "evidence_kind": "derived-cache",
        "raw_source_claims_supported": False,
        "sha256": _archive_sha256(path),
        "files": files,
        "rows": rows,
        "columns": columns,
    }


def _write_report(path: Path, report: dict[str, object]) -> None:
    payload = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure an ETCSRI derived-cache ZIP for research evidence."
    )
    parser.add_argument("--derived-zip", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        report = census_derived_zip(args.derived_zip)
    except (CensusError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
