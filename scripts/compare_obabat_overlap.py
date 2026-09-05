#!/usr/bin/env python3
"""Reproduce document-ID overlap between OBABAT and a pinned Nino TF corpus.

This is a research utility, not converter code. It deliberately separates exact
identifier overlap from weaker content similarity and fails closed on malformed
or duplicated document identifiers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable


P_ID_RE = re.compile(r"^P[0-9]{6}$")


class ComparisonError(ValueError):
    """Raised when overlap input cannot be classified reproducibly."""


def normalize_p_id(raw: object) -> str:
    """Normalize surrounding whitespace while preserving identifier identity."""
    if raw is None:
        raise ComparisonError("missing CDLI P-number")
    value = str(raw).strip()
    if not value:
        raise ComparisonError("invalid CDLI P-number: empty value")
    if P_ID_RE.fullmatch(value) is None:
        raise ComparisonError(f"invalid CDLI P-number: {value!r}")
    return value


def unique_p_ids(values: Iterable[object], *, source: str) -> set[str]:
    """Validate and deduplicate an identifier stream, failing on duplicates."""
    out: set[str] = set()
    for raw in values:
        pid = normalize_p_id(raw)
        if pid in out:
            raise ComparisonError(f"duplicate CDLI P-number in {source}: {pid}")
        out.add(pid)
    if not out:
        raise ComparisonError(f"no CDLI P-numbers found in {source}")
    return out


def read_oracc_members(path: str | Path) -> set[str]:
    """Read exact document IDs from an ORACC corpus.json membership map."""
    path = Path(path)
    with path.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    members = payload.get("members")
    if not isinstance(members, dict) or not members:
        raise ComparisonError(f"missing non-empty members map in {path}")
    return unique_p_ids(members.keys(), source=str(path))


def read_tf_pnumbers(path: str | Path) -> set[str]:
    """Read values from a Text-Fabric node feature containing P-numbers.

    The pinned Nino feature starts with a sparse node-number prefix on the first
    value (``226669\tP509373``) followed by consecutive plain values. Metadata
    lines begin with ``@``. We care only about feature values, not node numbers.
    """
    path = Path(path)
    values: list[str] = []
    with path.open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("@"):
                continue
            if "\t" in line:
                node, value = line.split("\t", 1)
                if not node.isdigit():
                    raise ComparisonError(
                        f"invalid Text-Fabric node prefix in {path}: {node!r}"
                    )
            else:
                value = line
            values.append(value)
    return unique_p_ids(values, source=str(path))


def compare_id_sets(
    left_ids: Iterable[object], reference_ids: Iterable[object]
) -> dict[str, list[str]]:
    """Return exact overlap and both directional non-overlap sets."""
    left = unique_p_ids(left_ids, source="left identifiers")
    reference = unique_p_ids(reference_ids, source="reference identifiers")
    return {
        "overlap_ids": sorted(left & reference),
        "not_in_reference_ids": sorted(left - reference),
        "reference_only_ids": sorted(reference - left),
    }


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def validate_manifest_against_oracc(
    oracc_path: str | Path, manifest_path: str | Path
) -> dict[str, int]:
    """Verify that the committed manifest partitions the exact pinned ORACC blob."""
    oracc_path = Path(oracc_path)
    manifest_path = Path(manifest_path)
    with manifest_path.open(encoding="utf-8") as fh:
        manifest = json.load(fh)

    try:
        expected_blob = manifest["sources"]["oracc_tf"]["blob_sha"]
        counts = manifest["counts"]
        overlap_raw = manifest["overlap_ids"]
        unmatched_raw = manifest["not_in_pinned_nino_ids"]
    except (KeyError, TypeError) as exc:
        raise ComparisonError(f"malformed overlap manifest: missing {exc}") from exc

    actual_blob = _git_blob_sha(oracc_path)
    if actual_blob != expected_blob:
        raise ComparisonError(
            f"ORACC source blob SHA mismatch: expected {expected_blob}, got {actual_blob}"
        )

    oracc = read_oracc_members(oracc_path)
    overlap = unique_p_ids(overlap_raw, source="manifest overlap_ids")
    unmatched = unique_p_ids(
        unmatched_raw, source="manifest not_in_pinned_nino_ids"
    )
    collision = overlap & unmatched
    if collision:
        raise ComparisonError(
            "manifest classifications overlap: " + ", ".join(sorted(collision))
        )
    if overlap | unmatched != oracc:
        missing = sorted(oracc - (overlap | unmatched))
        extra = sorted((overlap | unmatched) - oracc)
        raise ComparisonError(
            f"manifest does not partition ORACC members; missing={missing}, extra={extra}"
        )

    actual_counts = {
        "oracc_documents": len(oracc),
        "overlap_documents": len(overlap),
        "not_in_pinned_nino_documents": len(unmatched),
    }
    for key, value in actual_counts.items():
        if counts.get(key) != value:
            raise ComparisonError(
                f"manifest count mismatch for {key}: {counts.get(key)!r} != {value}"
            )
    return actual_counts


def _normalized_text(text: str) -> str:
    return " ".join(text.split())


def classify_pair(
    left_id: object,
    right_id: object,
    *,
    left_text: str | None = None,
    right_text: str | None = None,
) -> str:
    """Classify pair evidence without turning similarity into document identity.

    Distinct IDs with identical normalized text remain explicitly distinct at
    the document-identity layer. The content match is useful for manual audit,
    but must not be promoted automatically to ``exact_identifier``.
    """
    left = normalize_p_id(left_id)
    right = normalize_p_id(right_id)
    if left == right:
        return "exact_identifier"
    if left_text is not None and right_text is not None:
        normalized_left = _normalized_text(left_text)
        normalized_right = _normalized_text(right_text)
        if normalized_left and normalized_left == normalized_right:
            return "content_match_distinct_ids"
    return "unresolved"


def build_report(oracc_path: str | Path, nino_path: str | Path) -> dict[str, object]:
    oracc = read_oracc_members(oracc_path)
    nino = read_tf_pnumbers(nino_path)
    sets = compare_id_sets(oracc, nino)
    overlap_count = len(sets["overlap_ids"])
    return {
        "match_key": "cdli_p_number",
        "counts": {
            "oracc_documents": len(oracc),
            "reference_documents": len(nino),
            "overlap_documents": overlap_count,
            "not_in_reference_documents": len(sets["not_in_reference_ids"]),
            "reference_only_documents": len(sets["reference_only_ids"]),
        },
        "fractions": {
            "oracc_overlapping": overlap_count / len(oracc),
            "reference_overlapping": overlap_count / len(nino),
        },
        **sets,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oracc_corpus_json", type=Path)
    parser.add_argument("nino_pnumber_tf", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    args = parser.parse_args()

    result = build_report(args.oracc_corpus_json, args.nino_pnumber_tf)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
