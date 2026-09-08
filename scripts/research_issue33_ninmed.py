#!/usr/bin/env python3
"""Deterministic measurement helpers for ISSUE-33 NINMED A/B research.

This module is intentionally research-only.  It compares source identities and
lexical evidence without treating either ORACC or the archived Nino-cunei
corpus as normative ground truth.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import json
from pathlib import Path


class ResearchError(ValueError):
    """Research input is malformed or would require an unsafe guess."""


_ORACC_FIELDS = ("cf", "gw", "pos", "epos", "sense", "norm", "inst")


def _read_json_object(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ResearchError(f"cannot read JSON object {path}") from exc
    if not isinstance(value, Mapping):
        raise ResearchError(f"JSON root is not an object: {path}")
    return value


def _document_ids(directory: Path | str, field: str) -> tuple[str, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise ResearchError(f"source directory does not exist: {root}")

    seen: set[str] = set()
    ids: list[str] = []
    for path in sorted(root.glob("*.json")):
        document = _read_json_object(path)
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"{path}: missing non-empty {field}")
        source_id = value.strip()
        if source_id in seen:
            raise ResearchError(f"duplicate source identity {source_id!r}")
        seen.add(source_id)
        ids.append(source_id)
    return tuple(sorted(ids))


def oracc_document_ids(directory: Path | str) -> tuple[str, ...]:
    """Return exact ORACC ``textid`` identities, independent of filenames."""
    return _document_ids(directory, "textid")


def reference_document_ids(directory: Path | str) -> tuple[str, ...]:
    """Return exact archived-source ``cdliNumber`` identities."""
    return _document_ids(directory, "cdliNumber")


def identity_overlap(
    oracc_ids: Sequence[str], reference_ids: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    """Partition two source-ID collections without filename heuristics."""
    if isinstance(oracc_ids, (str, bytes)) or isinstance(reference_ids, (str, bytes)):
        raise ResearchError("identity inputs must be sequences of source ids")
    left = tuple(oracc_ids)
    right = tuple(reference_ids)
    if len(set(left)) != len(left) or len(set(right)) != len(right):
        raise ResearchError("duplicate source identity in overlap input")
    if not all(isinstance(value, str) and value for value in left + right):
        raise ResearchError("source identities must be non-empty strings")
    left_set = set(left)
    right_set = set(right)
    return {
        "overlap": tuple(sorted(left_set & right_set)),
        "oracc_only": tuple(sorted(left_set - right_set)),
        "reference_only": tuple(sorted(right_set - left_set)),
    }


def _walk_cdl(node: object):
    if not isinstance(node, Mapping):
        raise ResearchError("ORACC CDL nodes must be objects")
    yield node
    children = node.get("cdl")
    if children is None:
        return
    if not isinstance(children, list):
        raise ResearchError("ORACC cdl field must be a list when present")
    for child in children:
        yield from _walk_cdl(child)


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Sequence, Mapping)):
        return bool(value)
    return True


def oracc_lexical_census(documents: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Count word-level ORACC lexical fields independently and source-faithfully."""
    words = 0
    field_nonempty = {field: 0 for field in _ORACC_FIELDS}

    for document in documents:
        for node in _walk_cdl(document):
            if node.get("node") != "l":
                continue
            words += 1
            features = node.get("f")
            if features is None:
                features = {}
            if not isinstance(features, Mapping):
                raise ResearchError("ORACC word f field must be an object when present")

            for field in _ORACC_FIELDS:
                # Real ORACC occurrence signatures commonly keep ``inst`` on the
                # word object, while fixtures/derived representations may expose
                # it inside ``f``.  Count presence once per word, without moving
                # or normalizing the source value.
                value = features.get(field)
                if field == "inst" and not _nonempty(value):
                    value = node.get("inst")
                if _nonempty(value):
                    field_nonempty[field] += 1

    return {"words": words, "field_nonempty": field_nonempty}


def reference_lexical_census(documents: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Measure archived JSON ``uniqueLemma`` coverage without flattening multiplicity."""
    words = 0
    words_with_unique_lemma = 0
    assignments = 0
    maximum = 0

    for document in documents:
        text = document.get("text")
        if text is None:
            continue
        if not isinstance(text, Mapping):
            raise ResearchError("reference text field must be an object")
        lines = text.get("allLines", [])
        if not isinstance(lines, list):
            raise ResearchError("reference text.allLines must be a list")
        for line in lines:
            if not isinstance(line, Mapping):
                raise ResearchError("reference line must be an object")
            content = line.get("content", [])
            if not isinstance(content, list):
                raise ResearchError("reference line content must be a list")
            for item in content:
                if not isinstance(item, Mapping):
                    raise ResearchError("reference content item must be an object")
                if item.get("type") != "Word":
                    continue
                words += 1
                lemmas = item.get("uniqueLemma", [])
                if lemmas is None:
                    lemmas = []
                if not isinstance(lemmas, list):
                    raise ResearchError("reference uniqueLemma must be a list when present")
                nonempty = [value for value in lemmas if _nonempty(value)]
                count = len(nonempty)
                if count:
                    words_with_unique_lemma += 1
                assignments += count
                maximum = max(maximum, count)

    return {
        "words": words,
        "words_with_unique_lemma": words_with_unique_lemma,
        "unique_lemma_assignments": assignments,
        "max_unique_lemmas_per_word": maximum,
    }


def tf_feature_names(directory: Path | str) -> tuple[str, ...]:
    """Inventory TF feature files by filename only, without semantic inference."""
    root = Path(directory)
    if not root.is_dir():
        raise ResearchError(f"TF directory does not exist: {root}")
    return tuple(sorted(path.stem for path in root.iterdir() if path.is_file() and path.suffix == ".tf"))


def canonical_report_bytes(report: object) -> bytes:
    """Serialize research evidence deterministically as canonical UTF-8 JSON."""
    try:
        text = json.dumps(
            report,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ResearchError("report is not canonical JSON data") from exc
    return (text + "\n").encode("utf-8")


__all__ = [
    "ResearchError",
    "canonical_report_bytes",
    "identity_overlap",
    "oracc_document_ids",
    "oracc_lexical_census",
    "reference_document_ids",
    "reference_lexical_census",
    "tf_feature_names",
]
