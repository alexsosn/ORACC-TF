"""Deterministic source-to-Text-Fabric audit for the ORACC-TF 1.0 candidate.

The audit compares one explicit source snapshot to an already-built Text-Fabric
candidate.  It deliberately reuses the converter's accepted source semantics
instead of inventing a parallel classifier.
"""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Mapping

from . import corpus, gdl, lexemes, loader, metadata, roundtrip, sections, words


SCHEMA_VERSION = 1

_SIGN_PAYLOAD_FEATURES = (
    "utf8",
    "readingu",
    "sign_json",
    "gdl_id",
    "gdl_form",
    "gdl_sexified",
    "src_path",
    "cuneiform_trailer",
)


class AuditError(ValueError):
    """The requested audit cannot identify or compare its inputs safely."""


def _identity(document_key: object, source_id: object) -> str:
    if not isinstance(document_key, str) or not document_key:
        raise AuditError(f"TF word lacks document_key: {document_key!r}")
    if not isinstance(source_id, str) or not source_id:
        raise AuditError(f"TF word lacks source_id: {source_id!r}")
    return f"{document_key}|{source_id}"


def _node_count(api, otype: str) -> int:
    return len(api.F.otype.s(otype))


def _feature(api, name: str):
    return api.Fs(name) if name in set(api.Fall()) else None


def _synthetic_slots(api) -> tuple[int, ...]:
    synthetic = _feature(api, "synthetic")
    if synthetic is None:
        return ()
    return tuple(
        slot
        for slot in range(1, api.F.otype.maxSlot + 1)
        if synthetic.v(slot) == 1
    )


def _synthetic_payload_violations(api, synthetic_slots: tuple[int, ...]) -> list[dict[str, object]]:
    present = {
        name: feature
        for name in _SIGN_PAYLOAD_FEATURES
        if (feature := _feature(api, name)) is not None
    }
    violations: list[dict[str, object]] = []
    for slot in synthetic_slots:
        values = {
            name: feature.v(slot)
            for name, feature in present.items()
            if feature.v(slot) is not None
        }
        if values:
            violations.append({"slot": slot, "features": values})
    return violations


def _source_word_identities(data: Path) -> tuple[Counter[str], int]:
    identities: Counter[str] = Counter()
    total = 0
    for edition in loader.iter_editions(data, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            total += 1
            identities[f"{edition.key}|{word.source_id}"] += 1
    return identities, total


def _tf_document_keys(api) -> Counter[str]:
    result: Counter[str] = Counter()
    for node in api.F.otype.s("document"):
        value = api.F.document.v(node)
        if not isinstance(value, str) or not value:
            raise AuditError(f"TF document node {node} lacks qualified document value")
        result[value] += 1
    return result


def _tf_word_identities(api) -> Counter[str]:
    result: Counter[str] = Counter()
    for node in api.F.otype.s("word"):
        result[_identity(api.F.document_key.v(node), api.F.source_id.v(node))] += 1
    return result


def _duplicates(counts: Mapping[str, int]) -> list[str]:
    return sorted(key for key, count in counts.items() if count != 1)


def _difference(left: Mapping[str, int], right: Mapping[str, int]) -> list[str]:
    return sorted(set(left) - set(right))


def _count_reconciliation(source: int, tf: int) -> dict[str, int]:
    return {"source": source, "tf": tf, "delta": tf - source}


def _append_identity_discrepancies(
    unexplained: list[dict[str, object]],
    *,
    kind: str,
    identities: list[str],
) -> None:
    unexplained.extend({"kind": kind, "identity": identity} for identity in identities)


def build_report(
    *,
    data: Path | str,
    tf_dir: Path | str,
    source_revision: str,
    dataset: str,
) -> dict[str, object]:
    """Compare source data to an existing TF candidate and return a JSON-safe report."""
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise AuditError("source_revision must be a non-empty explicit revision")
    if not isinstance(dataset, str) or not dataset.strip():
        raise AuditError("dataset must be a non-empty identifier")

    data_path = Path(data)
    tf_path = Path(tf_dir)

    source_survey = loader.survey(data_path)
    source_gdl = gdl.census(data_path)
    source_words_census = words.census(data_path)
    source_sections = sections.census(data_path)
    source_lexemes = lexemes.census(data_path)
    source_metadata = metadata.census(data_path)
    source_roundtrip = roundtrip.census(data_path)
    metadata_index = metadata.load_index(data_path)

    source_documents = Counter(source_survey.keys)
    source_word_ids, source_word_total = _source_word_identities(data_path)

    api = corpus.load_tf(tf_path)
    tf_documents = _tf_document_keys(api)
    tf_word_ids = _tf_word_identities(api)
    synthetic_slots = _synthetic_slots(api)
    synthetic_set = set(synthetic_slots)
    semantic_tf_slots = sum(
        slot not in synthetic_set
        for slot in range(1, api.F.otype.maxSlot + 1)
    )
    payload_violations = _synthetic_payload_violations(api, synthetic_slots)

    missing_documents = _difference(source_documents, tf_documents)
    unexpected_documents = _difference(tf_documents, source_documents)
    missing_words = _difference(source_word_ids, tf_word_ids)
    unexpected_words = _difference(tf_word_ids, source_word_ids)

    semantic_signs = _count_reconciliation(source_words_census.signs, semantic_tf_slots)
    line_counts = _count_reconciliation(source_sections.source_lines, _node_count(api, "line"))
    lexeme_counts = _count_reconciliation(source_lexemes.lexemes, _node_count(api, "lex"))

    missing_catalogue = sorted(set(source_documents) - set(metadata_index.records))

    unexplained: list[dict[str, object]] = []
    _append_identity_discrepancies(
        unexplained, kind="missing-document", identities=missing_documents
    )
    _append_identity_discrepancies(
        unexplained, kind="unexpected-document", identities=unexpected_documents
    )
    _append_identity_discrepancies(
        unexplained, kind="missing-word", identities=missing_words
    )
    _append_identity_discrepancies(
        unexplained, kind="unexpected-word", identities=unexpected_words
    )

    for identity in _duplicates(source_documents):
        unexplained.append({"kind": "duplicate-source-document", "identity": identity})
    for identity in _duplicates(tf_documents):
        unexplained.append({"kind": "duplicate-tf-document", "identity": identity})
    for identity in _duplicates(source_word_ids):
        unexplained.append({"kind": "duplicate-source-word", "identity": identity})
    for identity in _duplicates(tf_word_ids):
        unexplained.append({"kind": "duplicate-tf-word", "identity": identity})

    if source_word_total != source_words_census.words:
        unexplained.append(
            {
                "kind": "source-word-census",
                "identity_count": source_word_total,
                "census_count": source_words_census.words,
            }
        )

    for kind, comparison in (
        ("semantic-sign-count", semantic_signs),
        ("line-count", line_counts),
        ("lexeme-count", lexeme_counts),
    ):
        if comparison["delta"] != 0:
            unexplained.append({"kind": kind, **comparison})

    if source_gdl.unknown:
        unexplained.append({"kind": "gdl-unknown", "count": source_gdl.unknown})
    if source_metadata.multiply_attached_records:
        unexplained.append(
            {
                "kind": "multiply-attached-catalogue",
                "count": source_metadata.multiply_attached_records,
            }
        )
    for violation in payload_violations:
        unexplained.append({"kind": "synthetic-source-payload", **violation})

    roundtrip_total = source_roundtrip.exact + sum(source_roundtrip.exceptions.values())
    if roundtrip_total != source_roundtrip.words:
        unexplained.append(
            {
                "kind": "roundtrip-accounting",
                "words": source_roundtrip.words,
                "accounted": roundtrip_total,
            }
        )

    tf_node_counts = {
        otype: _node_count(api, otype)
        for otype in (
            "document",
            "face",
            "column",
            "line",
            "chunk",
            "phrase",
            "word",
            "lex",
        )
    }
    tf_node_counts["sign"] = api.F.otype.maxSlot

    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "dataset": dataset,
        "source": {
            "repository_revision": source_revision,
            "subprojects": loader.edition_subprojects(data_path),
            "members": source_survey.source_files,
            "readable_documents": source_survey.parseable,
            "populated_documents": source_survey.populated,
            "stubs": source_survey.stubs,
            "hazards": [hazard.evidence() for hazard in source_survey.hazards],
            "words": source_words_census.words,
            "semantic_signs": source_words_census.signs,
            "lines": source_sections.source_lines,
            "lexemes": source_lexemes.lexemes,
            "gdl": {
                "slot": source_gdl.slot,
                "structural": source_gdl.structural,
                "modifier": source_gdl.modifier,
                "rendering": source_gdl.rendering,
                "unknown": source_gdl.unknown,
            },
        },
        "tf": {
            "documents": _node_count(api, "document"),
            "words": _node_count(api, "word"),
            "semantic_signs": semantic_tf_slots,
            "synthetic_slots": len(synthetic_slots),
            "total_slots": api.F.otype.maxSlot,
            "lines": _node_count(api, "line"),
            "lexemes": _node_count(api, "lex"),
            "node_counts": dict(sorted(tf_node_counts.items())),
        },
        "reconciliation": {
            "documents": {
                "missing_in_tf": missing_documents,
                "unexpected_in_tf": unexpected_documents,
            },
            "words": {
                "missing_in_tf": missing_words,
                "unexpected_in_tf": unexpected_words,
            },
            "semantic_signs": semantic_signs,
            "lines": line_counts,
            "lexemes": lexeme_counts,
            "gdl_unknown": source_gdl.unknown,
        },
        "catalogue": {
            "entries": source_metadata.catalogue_entries,
            "attached_documents": source_metadata.catalogue_attached_documents,
            "missing_documents": source_metadata.missing_catalogue_documents,
            "missing_document_keys": missing_catalogue,
            "multiply_attached_records": source_metadata.multiply_attached_records,
        },
        "roundtrip": {
            "words": source_roundtrip.words,
            "exact": source_roundtrip.exact,
            "exceptions": dict(sorted(source_roundtrip.exceptions.items())),
        },
        "synthetic": {
            "slots": len(synthetic_slots),
            "source_payload_violations": payload_violations,
        },
        "unexplained": unexplained,
    }
    report["status"] = "pass" if not unexplained else "fail"
    return report


def canonical_bytes(report: Mapping[str, object]) -> bytes:
    """Serialize a report deterministically without checkout-local paths."""
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
