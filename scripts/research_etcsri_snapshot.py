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
from io import BytesIO
from collections import Counter
from pathlib import PurePosixPath
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



# These are research input limits, not linguistic corpus-size expectations.
MAX_PROJECT_ZIP_BYTES = 256 * 1024 * 1024
MAX_DOCUMENT_BYTES = 24 * 1024 * 1024
MAX_TOTAL_DOCUMENT_BYTES = 512 * 1024 * 1024
RAW_WORD_FEATURES = ("base", "morph", "morph2", "para", "cf", "gw", "pos", "lang")


def _safe_zip_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Reject ambiguous paths and duplicate members before reading any content."""
    import stat

    seen: set[str] = set()
    members = archive.infolist()
    for member in members:
        name = member.filename
        path = PurePosixPath(name)
        if (not name or name.startswith("/") or "\\\\" in name
                or ".." in path.parts or "." in path.parts):
            raise CensusError(f"unsafe ZIP member path: {name!r}")
        if name in seen:
            raise CensusError(f"duplicate ZIP member: {name!r}")
        seen.add(name)
        if stat.S_IFMT(member.external_attr >> 16) == stat.S_IFLNK:
            raise CensusError(f"ZIP symlink is not source data: {name!r}")
    return members


def _walk_gdl_shapes(node: object, shapes: Counter[str]) -> None:
    """Census source objects, without inventing a sign ontology."""
    pending = [node]
    while pending:
        item = pending.pop()
        if isinstance(item, list):
            pending.extend(item)
            continue
        if not isinstance(item, dict):
            raise CensusError("GDL tree contains non-object/non-array elements")
        shapes[",".join(sorted(item))] += 1
        for value in item.values():
            if isinstance(value, (dict, list)):
                pending.append(value)


def _observe_document(
    document: object,
    *,
    chunk_types: Counter[str],
    marker_types: Counter[str],
    features: dict[str, Counter[str]],
    gdl_shapes: Counter[str],
    anomalies: Counter[str],
) -> int:
    if not isinstance(document, dict):
        raise CensusError("corpusjson root must be a JSON object")
    if not isinstance(document.get("textid"), str) or not document["textid"].strip():
        raise CensusError("corpusjson member lacks a textid")
    if document.get("type") not in (None, "cdl"):
        raise CensusError("corpusjson member has unsupported source type")
    words = 0
    pending = [document]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict):
            raise CensusError("CDL tree contains non-object child")
        kind = node.get("node")
        if kind == "c":
            label = node.get("type")
            chunk_types[str(label) if label is not None else "<missing>"] += 1
        elif kind == "d":
            label = node.get("type")
            marker_types[str(label) if label is not None else "<missing>"] += 1
        elif kind == "l":
            words += 1
            word = node.get("f")
            if word is None:
                word = {}
            if not isinstance(word, dict):
                raise CensusError("word f must be an object")
            for field in RAW_WORD_FEATURES:
                if field in word:
                    features[field]["present"] += 1
                    value = word[field]
                    if value is not None and (not isinstance(value, str) or value.strip()):
                        features[field]["populated"] += 1
            gdl = word.get("gdl")
            if gdl is None:
                anomalies["words_without_gdl"] += 1
            elif not isinstance(gdl, list):
                raise CensusError("word gdl must be an array")
            elif not gdl:
                anomalies["words_with_empty_gdl"] += 1
            else:
                _walk_gdl_shapes(gdl, gdl_shapes)
        children = node.get("cdl")
        if children is not None:
            if not isinstance(children, list):
                raise CensusError("CDL cdl must be an array")
            pending.extend(children)
    return words


def census_raw_cache(path: Path) -> dict[str, object]:
    """Survey raw ORACC JSON from a pinned nested-cache ZIP.

    A raw-source census can establish which source structures actually occur;
    it does not certify a future Text-Fabric converter or its sign rendering.
    The source ZIPs are read in memory and never extracted onto the filesystem.
    """
    if not path.is_file():
        raise CensusError(f"raw cache not found: {path}")
    try:
        with zipfile.ZipFile(path) as outer:
            outer_members = _safe_zip_members(outer)
            candidates = [member for member in outer_members
                          if member.filename == "jsonzip/etcsri.zip"]
            if len(candidates) != 1:
                raise CensusError("expected exactly one jsonzip/etcsri.zip bundle")
            nested = candidates[0]
            if nested.file_size > MAX_PROJECT_ZIP_BYTES:
                raise CensusError("ETCSRI source ZIP exceeds research byte limit")
            project_bytes = outer.read(nested)
        chunk_types: Counter[str] = Counter()
        marker_types: Counter[str] = Counter()
        gdl_shapes: Counter[str] = Counter()
        anomalies: Counter[str] = Counter()
        features = {field: Counter() for field in RAW_WORD_FEATURES}
        documents = 0
        corpusjson_files = 0
        words = 0
        source_ids: set[str] = set()
        bytes_seen = 0
        with zipfile.ZipFile(BytesIO(project_bytes)) as project:
            inner_members = _safe_zip_members(project)
            members = sorted(
                (member for member in inner_members
                 if len(PurePosixPath(member.filename).parts) == 3
                 and PurePosixPath(member.filename).parts[:2] == ("etcsri", "corpusjson")
                 and member.filename.endswith(".json") and not member.is_dir()),
                key=lambda member: member.filename,
            )
            if not members:
                raise CensusError("ETCSRI bundle contains no corpusjson/*.json")
            for member in members:
                corpusjson_files += 1
                if member.file_size > MAX_DOCUMENT_BYTES:
                    raise CensusError(f"oversized corpusjson document: {member.filename}")
                bytes_seen += member.file_size
                if bytes_seen > MAX_TOTAL_DOCUMENT_BYTES:
                    raise CensusError("ETCSRI cumulative JSON exceeds research byte limit")
                raw = project.read(member)
                if not raw:
                    anomalies["empty_corpusjson_files"] += 1
                    continue
                try:
                    doc = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    anomalies["invalid_corpusjson_files"] += 1
                    continue
                if not isinstance(doc, dict):
                    anomalies["non_object_corpusjson_files"] += 1
                    continue
                textid = doc.get("textid")
                if not isinstance(textid, str) or not textid.strip():
                    anomalies["missing_textid"] += 1
                    continue
                if textid in source_ids:
                    raise CensusError(f"duplicate ETCSRI source textid {textid!r}")
                source_ids.add(textid)
                words += _observe_document(
                    doc, chunk_types=chunk_types, marker_types=marker_types,
                    features=features, gdl_shapes=gdl_shapes, anomalies=anomalies,
                )
                documents += 1
        return {
            "schema": SCHEMA,
            "evidence_kind": "raw-oracc-json-cache",
            "raw_source_claims_supported": True,
            "cache_sha256": _archive_sha256(path),
            "project_zip_sha256": hashlib.sha256(project_bytes).hexdigest(),
            "corpusjson_files": corpusjson_files,
            "parseable_documents": documents,
            "words": words,
            "word_features": {
                name: {
                    "present": count["present"],
                    "populated": count["populated"],
                } for name, count in sorted(features.items())
            },
            "chunk_types": dict(sorted(chunk_types.items())),
            "marker_types": dict(sorted(marker_types.items())),
            "gdl_object_keys": dict(sorted(gdl_shapes.items())),
            "anomalies": dict(sorted(anomalies.items())),
        }
    except (zipfile.BadZipFile, RuntimeError, EOFError) as exc:
        raise CensusError("invalid ETCSRI raw ZIP cache") from exc


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
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--derived-zip", type=Path)
    source.add_argument("--raw-cache", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        report = (census_raw_cache(args.raw_cache) if args.raw_cache is not None
                  else census_derived_zip(args.derived_zip))
    except (CensusError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    _write_report(args.output, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
