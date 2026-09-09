#!/usr/bin/env python3
"""Deterministic repository-wide corpusjson census for ISSUE-102 research.

This is a research-only harness. It records readable source members and typed
byte/JSON/identity hazards without changing the production loader and without
inferring source identity from filenames.
"""

from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping


def _digest(payload: bytes) -> str:
    return sha256(payload).hexdigest()


def classify_source_bytes(payload: bytes, *, relative_path: str) -> dict[str, object]:
    """Classify one corpusjson member from its bytes only.

    A readable identity is accepted only from a non-empty embedded ``textid``.
    The path is retained as evidence, never promoted to scholarly identity.
    """
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("relative_path must be a non-empty string")

    base: dict[str, object] = {
        "relative_path": relative_path,
        "bytes": len(payload),
        "sha256": _digest(payload),
    }
    if not payload:
        return {"status": "hazard", "kind": "empty-file", **base}

    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "hazard", "kind": "invalid-utf8", **base}

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "hazard", "kind": "invalid-json", **base}

    if not isinstance(value, Mapping):
        return {"status": "hazard", "kind": "non-object-json", **base}

    source_id = value.get("textid")
    if not isinstance(source_id, str) or not source_id.strip():
        return {"status": "hazard", "kind": "missing-source-id", **base}

    return {
        "status": "readable",
        **base,
        "source_id": source_id.strip(),
    }


def _tree_name(data_root: Path, corpusjson: Path) -> str:
    return corpusjson.relative_to(data_root).as_posix()


def scan_repository(data_root: Path | str) -> dict[str, object]:
    """Census every checked-in ``**/corpusjson/*.json`` tree deterministically."""
    root = Path(data_root)
    if not root.is_dir():
        raise ValueError(f"data root does not exist: {root}")

    tree_dirs = tuple(sorted(path for path in root.glob("**/corpusjson") if path.is_dir()))
    trees: list[dict[str, object]] = []
    total_members = 0
    total_readable = 0
    total_hazards = 0
    duplicate_groups_total = 0

    for tree_dir in tree_dirs:
        members = tuple(sorted(path for path in tree_dir.glob("*.json") if path.is_file()))
        readable: list[dict[str, object]] = []
        hazards: list[dict[str, object]] = []
        by_source_id: defaultdict[str, list[str]] = defaultdict(list)

        for path in members:
            result = classify_source_bytes(path.read_bytes(), relative_path=path.name)
            if result["status"] == "readable":
                readable.append(result)
                source_id = result["source_id"]
                assert isinstance(source_id, str)
                by_source_id[source_id].append(path.name)
            else:
                hazards.append(result)

        duplicate_source_ids = tuple(
            {
                "source_id": source_id,
                "relative_paths": tuple(sorted(relative_paths)),
            }
            for source_id, relative_paths in sorted(by_source_id.items())
            if len(relative_paths) > 1
        )

        counts = {
            "source_members": len(members),
            "readable": len(readable),
            "hazards": len(hazards),
        }
        if counts["source_members"] != counts["readable"] + counts["hazards"]:
            raise AssertionError("corpusjson census does not reconcile")

        trees.append(
            {
                "tree": _tree_name(root, tree_dir),
                "counts": counts,
                "readable": tuple(readable),
                "hazards": tuple(hazards),
                "duplicate_source_ids": duplicate_source_ids,
            }
        )
        total_members += counts["source_members"]
        total_readable += counts["readable"]
        total_hazards += counts["hazards"]
        duplicate_groups_total += len(duplicate_source_ids)

    totals: dict[str, int] = {
        "source_members": total_members,
        "readable": total_readable,
        "hazards": total_hazards,
    }
    if duplicate_groups_total:
        totals["duplicate_identity_groups"] = duplicate_groups_total
    if totals["source_members"] != totals["readable"] + totals["hazards"]:
        raise AssertionError("repository corpusjson census does not reconcile")

    return {
        "schema_version": 1,
        "totals": totals,
        "trees": tuple(trees),
    }


def canonical_report_bytes(report: object) -> bytes:
    """Serialize derived census evidence deterministically."""
    return (
        json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


__all__ = ["canonical_report_bytes", "classify_source_bytes", "scan_repository"]
