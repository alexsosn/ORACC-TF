#!/usr/bin/env python3
"""Deterministic measurement helpers for ISSUE-33 NINMED A/B research.

This module is intentionally research-only. It compares source identities and
lexical evidence without treating either ORACC or the archived Nino-cunei
corpus as normative ground truth.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Mapping, Sequence
from hashlib import sha256
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


def _json_paths(directory: Path | str) -> tuple[Path, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise ResearchError(f"source directory does not exist: {root}")
    paths = tuple(sorted(root.glob("*.json")))
    if not paths:
        raise ResearchError(f"source directory contains no JSON documents: {root}")
    return paths


def _json_documents(directory: Path | str) -> tuple[Mapping[str, object], ...]:
    return tuple(_read_json_object(path) for path in _json_paths(directory))


def _scan_json_documents(
    directory: Path | str,
) -> tuple[tuple[Mapping[str, object], ...], tuple[dict[str, object], ...]]:
    """Read parseable objects while retaining byte-level evidence for bad members."""
    documents: list[Mapping[str, object]] = []
    hazards: list[dict[str, object]] = []
    for path in _json_paths(directory):
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ResearchError(f"cannot read source bytes {path}") from exc
        if not payload:
            hazards.append({"relative_path": path.name, "kind": "empty-file", "bytes": 0})
            continue
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            hazards.append(
                {"relative_path": path.name, "kind": "invalid-utf8", "bytes": len(payload)}
            )
            continue
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            hazards.append(
                {"relative_path": path.name, "kind": "invalid-json", "bytes": len(payload)}
            )
            continue
        if not isinstance(value, Mapping):
            hazards.append(
                {"relative_path": path.name, "kind": "non-object-json", "bytes": len(payload)}
            )
            continue
        documents.append(value)
    return tuple(documents), tuple(hazards)


def _ids_from_documents(
    documents: Iterable[Mapping[str, object]], field: str
) -> tuple[str, ...]:
    seen: set[str] = set()
    ids: list[str] = []
    for document in documents:
        value = document.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ResearchError(f"document missing non-empty {field}")
        source_id = value.strip()
        if source_id in seen:
            raise ResearchError(f"duplicate source identity {source_id!r}")
        seen.add(source_id)
        ids.append(source_id)
    return tuple(sorted(ids))


def _document_ids(directory: Path | str, field: str) -> tuple[str, ...]:
    return _ids_from_documents(_json_documents(directory), field)


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


def _layer_overlap(
    left_ids: Sequence[str],
    right_ids: Sequence[str],
    *,
    left_only_key: str,
    right_only_key: str,
) -> dict[str, tuple[str, ...]]:
    base = identity_overlap(left_ids, right_ids)
    return {
        "overlap": base["overlap"],
        left_only_key: base["oracc_only"],
        right_only_key: base["reference_only"],
    }


def _nonempty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (Sequence, Mapping)):
        return bool(value)
    return True


def oracc_catalogue_census(path: Path | str) -> dict[str, object]:
    """Census explicit ORACC catalogue membership without filename inference."""
    catalogue = _read_json_object(Path(path))
    if catalogue.get("type") != "catalogue":
        raise ResearchError("ORACC catalogue has invalid type")
    project = catalogue.get("project")
    if not isinstance(project, str) or not project.strip():
        raise ResearchError("ORACC catalogue project must be a non-empty string")
    members = catalogue.get("members")
    if not isinstance(members, Mapping):
        raise ResearchError("ORACC catalogue members must be an object")

    ids: list[str] = []
    metadata_nonempty: dict[str, int] = {}
    for key, raw_member in members.items():
        if not isinstance(key, str) or not key.strip() or not isinstance(raw_member, Mapping):
            raise ResearchError("ORACC catalogue member must have a string key and object value")
        member_id = key.strip()
        embedded = raw_member.get("id_text")
        if not isinstance(embedded, str) or embedded.strip() != member_id:
            raise ResearchError(f"catalogue member identity disagrees for {member_id!r}")
        ids.append(member_id)
        for field, value in raw_member.items():
            if field == "id_text" or not _nonempty(value):
                continue
            metadata_nonempty[field] = metadata_nonempty.get(field, 0) + 1

    if len(set(ids)) != len(ids):
        raise ResearchError("duplicate catalogue member identity")
    return {
        "project": project.strip(),
        "member_count": len(ids),
        "member_ids": tuple(sorted(ids)),
        "metadata_nonempty": dict(sorted(metadata_nonempty.items())),
    }


def reference_tf_document_ids(directory: Path | str) -> tuple[str, ...]:
    """Read document P-numbers from the archived TF ``pnumber`` node feature."""
    path = Path(directory) / "pnumber.tf"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise ResearchError(f"cannot read TF pnumber feature {path}") from exc

    seen: set[str] = set()
    values: list[str] = []
    in_data = False
    for raw in lines:
        line = raw.rstrip("\r\n")
        if not in_data:
            if not line:
                in_data = True
            continue
        if not line or line.startswith("@"):
            continue
        value = line.split("\t", 1)[1] if "\t" in line else line
        value = value.strip()
        if not value:
            raise ResearchError("TF pnumber contains an empty value")
        if value in seen:
            raise ResearchError(f"duplicate TF pnumber identity {value!r}")
        seen.add(value)
        values.append(value)
    if not values:
        raise ResearchError("TF pnumber feature contains no document identities")
    return tuple(sorted(values))


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


def _oracc_features(node: Mapping[str, object]) -> Mapping[str, object]:
    features = node.get("f")
    if features is None:
        return {}
    if not isinstance(features, Mapping):
        raise ResearchError("ORACC word f field must be an object when present")
    return features


def _reference_lines(document: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    text = document.get("text")
    if text is None:
        return ()
    if not isinstance(text, Mapping):
        raise ResearchError("reference text field must be an object")
    lines = text.get("allLines", [])
    if not isinstance(lines, list):
        raise ResearchError("reference text.allLines must be a list")
    if any(not isinstance(line, Mapping) for line in lines):
        raise ResearchError("reference lines must be objects")
    return tuple(lines)


def _reference_content(line: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    content = line.get("content", [])
    if not isinstance(content, list):
        raise ResearchError("reference line content must be a list")
    if any(not isinstance(item, Mapping) for item in content):
        raise ResearchError("reference content items must be objects")
    return tuple(content)


def oracc_lexical_census(documents: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Count word-level ORACC lexical fields independently and source-faithfully."""
    words = 0
    field_nonempty = {field: 0 for field in _ORACC_FIELDS}
    for document in documents:
        for node in _walk_cdl(document):
            if node.get("node") != "l":
                continue
            words += 1
            features = _oracc_features(node)
            for field in _ORACC_FIELDS:
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
        for line in _reference_lines(document):
            for item in _reference_content(line):
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


def oracc_structure_census(documents: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Measure ORACC source-native structural units without mapping them to Nino units."""
    document_count = 0
    line_starts = 0
    words = 0
    gdl_entries = 0
    empty_gdl = 0
    missing_gdl = 0
    for document in documents:
        document_count += 1
        for node in _walk_cdl(document):
            if node.get("node") == "d" and node.get("type") == "line-start":
                line_starts += 1
            if node.get("node") != "l":
                continue
            words += 1
            features = _oracc_features(node)
            if "gdl" not in features or features.get("gdl") is None:
                missing_gdl += 1
                continue
            gdl = features.get("gdl")
            if not isinstance(gdl, list):
                raise ResearchError("ORACC word gdl field must be a list when present")
            if not gdl:
                empty_gdl += 1
            gdl_entries += len(gdl)
    return {
        "documents": document_count,
        "line_starts": line_starts,
        "words": words,
        "gdl_top_level_entries": gdl_entries,
        "words_with_empty_gdl": empty_gdl,
        "words_without_gdl": missing_gdl,
    }


def reference_structure_census(documents: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Measure Nino JSON native lines, words and word-part structures independently."""
    document_count = 0
    line_count = 0
    words = 0
    word_parts = 0
    empty_parts = 0
    empty_lines = 0
    for document in documents:
        document_count += 1
        lines = _reference_lines(document)
        line_count += len(lines)
        for line in lines:
            content = _reference_content(line)
            if not content:
                empty_lines += 1
            for item in content:
                if item.get("type") != "Word":
                    continue
                words += 1
                parts = item.get("parts", [])
                if parts is None:
                    parts = []
                if not isinstance(parts, list):
                    raise ResearchError("reference Word parts must be a list when present")
                if not parts:
                    empty_parts += 1
                word_parts += len(parts)
    return {
        "documents": document_count,
        "lines": line_count,
        "words": words,
        "word_parts": word_parts,
        "words_with_empty_parts": empty_parts,
        "empty_lines": empty_lines,
    }


def _source_id(document: Mapping[str, object], field: str) -> str:
    value = document.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ResearchError(f"document missing non-empty {field}")
    return value.strip()


def _oracc_forms(document: Mapping[str, object]) -> tuple[str | None, ...]:
    forms: list[str | None] = []
    for node in _walk_cdl(document):
        if node.get("node") != "l":
            continue
        value = _oracc_features(node).get("form")
        if value is not None and not isinstance(value, str):
            raise ResearchError("ORACC word form must be a string or null")
        forms.append(value)
    return tuple(forms)


def _reference_forms(document: Mapping[str, object]) -> tuple[str | None, ...]:
    forms: list[str | None] = []
    for line in _reference_lines(document):
        for item in _reference_content(line):
            if item.get("type") != "Word":
                continue
            value = item.get("cleanValue") if "cleanValue" in item else item.get("value")
            if value is not None and not isinstance(value, str):
                raise ResearchError("reference word value must be a string or null")
            forms.append(value)
    return tuple(forms)


def paired_transliteration_witness(
    oracc_document: Mapping[str, object], reference_document: Mapping[str, object]
) -> dict[str, object]:
    """Compare exact source word sequences without transliteration normalization."""
    oracc_id = _source_id(oracc_document, "textid")
    reference_id = _source_id(reference_document, "cdliNumber")
    if oracc_id != reference_id:
        raise ResearchError(
            f"paired source identities disagree: {oracc_id!r} != {reference_id!r}"
        )
    oracc_words = _oracc_forms(oracc_document)
    reference_words = _reference_forms(reference_document)
    first_difference: int | None = None
    for index, (left, right) in enumerate(zip(oracc_words, reference_words)):
        if left != right:
            first_difference = index
            break
    if first_difference is None and len(oracc_words) != len(reference_words):
        first_difference = min(len(oracc_words), len(reference_words))
    return {
        "text_id": oracc_id,
        "oracc_words": oracc_words,
        "reference_words": reference_words,
        "same_word_count": len(oracc_words) == len(reference_words),
        "exact_sequence_equal": oracc_words == reference_words,
        "first_difference": first_difference,
    }


def tf_feature_names(directory: Path | str) -> tuple[str, ...]:
    """Inventory TF feature files by filename only, without semantic inference."""
    root = Path(directory)
    if not root.is_dir():
        raise ResearchError(f"TF directory does not exist: {root}")
    return tuple(
        sorted(path.stem for path in root.iterdir() if path.is_file() and path.suffix == ".tf")
    )


def _json_tree_sha256(directory: Path | str) -> str:
    paths = _json_paths(directory)
    digest = sha256()
    for path in paths:
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise ResearchError(f"cannot read source bytes {path}") from exc
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256(payload).digest())
    return digest.hexdigest()


def _file_sha256(path: Path | str) -> str:
    try:
        payload = Path(path).read_bytes()
    except OSError as exc:
        raise ResearchError(f"cannot read source bytes {path}") from exc
    return sha256(payload).hexdigest()


def _sequence_sha256(values: Sequence[str | None]) -> str:
    payload = json.dumps(
        list(values), ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _compact_witness(witness: Mapping[str, object]) -> dict[str, object]:
    oracc_words = witness["oracc_words"]
    reference_words = witness["reference_words"]
    if not isinstance(oracc_words, tuple) or not isinstance(reference_words, tuple):
        raise ResearchError("paired witness word sequences must be tuples")
    first_difference = witness["first_difference"]
    if first_difference is not None and not isinstance(first_difference, int):
        raise ResearchError("paired witness first_difference must be an integer or null")
    left_value = None
    right_value = None
    if first_difference is not None:
        if first_difference < len(oracc_words):
            left_value = oracc_words[first_difference]
        if first_difference < len(reference_words):
            right_value = reference_words[first_difference]
    return {
        "text_id": witness["text_id"],
        "oracc_word_count": len(oracc_words),
        "reference_word_count": len(reference_words),
        "same_word_count": witness["same_word_count"],
        "exact_sequence_equal": witness["exact_sequence_equal"],
        "first_difference": first_difference,
        "first_difference_oracc": left_value,
        "first_difference_reference": right_value,
        "oracc_sequence_sha256": _sequence_sha256(oracc_words),
        "reference_sequence_sha256": _sequence_sha256(reference_words),
    }


def build_report(
    *,
    oracc_dir: Path | str,
    reference_dir: Path | str,
    reference_tf_dir: Path | str,
    oracc_revision: str,
    reference_revision: str,
    oracc_licence: str,
    reference_repository_licence: str,
    reference_source_provenance: str,
    oracc_catalogue: Path | str | None = None,
) -> dict[str, object]:
    """Assemble deterministic A/B evidence without merging the two source models."""
    for field, value in (
        ("oracc_revision", oracc_revision),
        ("reference_revision", reference_revision),
        ("oracc_licence", oracc_licence),
        ("reference_repository_licence", reference_repository_licence),
        ("reference_source_provenance", reference_source_provenance),
    ):
        if not isinstance(value, str) or not value:
            raise ResearchError(f"{field} must be a non-empty string")

    oracc_documents, oracc_hazards = _scan_json_documents(oracc_dir)
    reference_documents, reference_hazards = _scan_json_documents(reference_dir)
    oracc_ids = _ids_from_documents(oracc_documents, "textid")
    reference_ids = _ids_from_documents(reference_documents, "cdliNumber")
    identity = identity_overlap(oracc_ids, reference_ids)

    oracc_by_id = {_source_id(document, "textid"): document for document in oracc_documents}
    reference_by_id = {
        _source_id(document, "cdliNumber"): document for document in reference_documents
    }
    if len(oracc_by_id) != len(oracc_documents) or len(reference_by_id) != len(reference_documents):
        raise ResearchError("duplicate source identity while assembling report")

    paired = tuple(
        _compact_witness(
            paired_transliteration_witness(oracc_by_id[text_id], reference_by_id[text_id])
        )
        for text_id in identity["overlap"]
    )

    report: dict[str, object] = {
        "schema_version": 1,
        "pins": {
            "oracc_revision": oracc_revision,
            "reference_revision": reference_revision,
        },
        "input_digests": {
            "oracc_json_sha256": _json_tree_sha256(oracc_dir),
            "reference_json_sha256": _json_tree_sha256(reference_dir),
        },
        "licences": {
            "oracc": oracc_licence,
            "reference_repository": reference_repository_licence,
        },
        "reference_source_provenance": reference_source_provenance,
        "source_hazards": {
            "oracc": oracc_hazards,
            "reference": reference_hazards,
        },
        "identity": identity,
        "oracc_lexical": oracc_lexical_census(oracc_documents),
        "reference_lexical": reference_lexical_census(reference_documents),
        "oracc_structure": oracc_structure_census(oracc_documents),
        "reference_structure": reference_structure_census(reference_documents),
        "reference_tf_features": tf_feature_names(reference_tf_dir),
        "paired_witnesses": paired,
    }

    if oracc_catalogue is not None:
        catalogue = oracc_catalogue_census(oracc_catalogue)
        catalogue_ids = catalogue["member_ids"]
        if not isinstance(catalogue_ids, tuple):
            raise ResearchError("catalogue census member ids must be a tuple")
        tf_ids = reference_tf_document_ids(reference_tf_dir)
        report["oracc_catalogue"] = catalogue
        digests = report["input_digests"]
        if not isinstance(digests, dict):
            raise ResearchError("internal report digest container is invalid")
        digests["oracc_catalogue_sha256"] = _file_sha256(oracc_catalogue)
        report["identity_layers"] = {
            "oracc_body_vs_catalogue": _layer_overlap(
                oracc_ids,
                catalogue_ids,
                left_only_key="oracc_body_only",
                right_only_key="catalogue_only",
            ),
            "reference_json_vs_catalogue": _layer_overlap(
                reference_ids,
                catalogue_ids,
                left_only_key="reference_json_only",
                right_only_key="catalogue_only",
            ),
            "reference_tf_vs_oracc_body": _layer_overlap(
                tf_ids,
                oracc_ids,
                left_only_key="reference_tf_only",
                right_only_key="oracc_body_only",
            ),
            "reference_tf_vs_reference_json": _layer_overlap(
                tf_ids,
                reference_ids,
                left_only_key="reference_tf_only",
                right_only_key="reference_json_only",
            ),
        }

    return report


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


def main(argv: Sequence[str] | None = None) -> int:
    """Generate one canonical report from explicit, already-pinned inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oracc-dir", required=True)
    parser.add_argument("--oracc-catalogue")
    parser.add_argument("--reference-dir", required=True)
    parser.add_argument("--reference-tf-dir", required=True)
    parser.add_argument("--oracc-revision", required=True)
    parser.add_argument("--reference-revision", required=True)
    parser.add_argument("--oracc-licence", required=True)
    parser.add_argument("--reference-repository-licence", required=True)
    parser.add_argument("--reference-source-provenance", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    report = build_report(
        oracc_dir=args.oracc_dir,
        oracc_catalogue=args.oracc_catalogue,
        reference_dir=args.reference_dir,
        reference_tf_dir=args.reference_tf_dir,
        oracc_revision=args.oracc_revision,
        reference_revision=args.reference_revision,
        oracc_licence=args.oracc_licence,
        reference_repository_licence=args.reference_repository_licence,
        reference_source_provenance=args.reference_source_provenance,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.write_bytes(canonical_report_bytes(report))
    except OSError as exc:
        raise ResearchError(f"cannot write report {output}") from exc
    return 0


__all__ = [
    "ResearchError",
    "build_report",
    "canonical_report_bytes",
    "identity_overlap",
    "main",
    "oracc_catalogue_census",
    "oracc_document_ids",
    "oracc_lexical_census",
    "oracc_structure_census",
    "paired_transliteration_witness",
    "reference_document_ids",
    "reference_lexical_census",
    "reference_structure_census",
    "reference_tf_document_ids",
    "tf_feature_names",
]


if __name__ == "__main__":
    raise SystemExit(main())
