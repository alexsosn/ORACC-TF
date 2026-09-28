"""Deterministic source-to-Text-Fabric audit for the ORACC-TF 1.0 candidate.

The audit compares one explicit source snapshot to an already-built Text-Fabric
candidate.  It deliberately reuses the converter's accepted source semantics
instead of inventing a parallel classifier.
"""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
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



def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _source_state_evidence(
    data: Path,
) -> tuple[list[dict[str, object]], list[dict[str, object]], str]:
    """Enumerate in-scope source bytes independently of checkout-local paths."""
    members: list[dict[str, object]] = []
    for observation in loader.iter_source_observations(data):
        if isinstance(observation, loader.ReadableSource):
            members.append(
                {
                    "status": "readable",
                    "relative_path": observation.relative_path,
                    "subproject": observation.edition.subproject,
                    "document_key": observation.edition.key,
                    "bytes": observation.bytes,
                    "sha256": observation.sha256,
                }
            )
        else:
            members.append({"status": "hazard", **observation.evidence()})
    members.sort(key=lambda item: str(item["relative_path"]))

    catalogues: list[dict[str, object]] = []
    for subproject in loader.edition_subprojects(data):
        path = data / subproject / "catalogue.json"
        payload = path.read_bytes()
        catalogues.append(
            {
                "relative_path": path.relative_to(data).as_posix(),
                "subproject": subproject,
                "bytes": len(payload),
                "sha256": sha256(payload).hexdigest(),
            }
        )
    catalogues.sort(key=lambda item: str(item["relative_path"]))

    state = {"members": members, "catalogues": catalogues}
    digest = sha256(_canonical_json(state).encode("utf-8")).hexdigest()
    return members, catalogues, digest


def _stored_scalar(value: object) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (str, int)):
        return value
    return _canonical_json(value)


def _lexeme_identity(key: lexemes.LexemeKey) -> str:
    return _canonical_json([key.lang, key.cf, key.gw, key.pos])


def _semantic_reconciliation(
    *,
    data: Path,
    api,
    metadata_index: metadata.MetadataIndex,
    synthetic_slots: set[int],
) -> dict[str, object]:
    """Compare source-bearing values and relations without relying on counts alone."""
    node_features = {name: api.Fs(name) for name in api.Fall()}
    edge_features = {name: api.Es(name) for name in api.Eall()}

    def value(name: str, node: int):
        feature = node_features.get(name)
        return feature.v(node) if feature is not None else None

    def edge(name: str, node: int) -> tuple[int, ...]:
        feature = edge_features.get(name)
        return tuple(feature.f(node)) if feature is not None else ()

    issues: list[dict[str, object]] = []
    mismatch_counts: Counter[str] = Counter()

    def issue(kind: str, **detail: object) -> None:
        mismatch_counts[kind] += 1
        issues.append({"kind": kind, **detail})

    tf_document_nodes: dict[str, int] = {}
    for node in api.F.otype.s("document"):
        key = value("document", node)
        if not isinstance(key, str) or not key:
            issue("document-identity", node=node, value=key)
            continue
        if key in tf_document_nodes:
            issue("duplicate-tf-document", identity=key)
            continue
        tf_document_nodes[key] = node

    tf_word_nodes: dict[str, int] = {}
    for node in api.F.otype.s("word"):
        try:
            key = _identity(value("document_key", node), value("source_id", node))
        except AuditError:
            issue(
                "word-identity",
                node=node,
                document_key=value("document_key", node),
                source_id=value("source_id", node),
            )
            continue
        if key in tf_word_nodes:
            issue("duplicate-tf-word", identity=key)
            continue
        tf_word_nodes[key] = node

    tf_line_counts: Counter[str] = Counter()
    tf_line_nodes: dict[str, int] = {}
    for node in api.F.otype.s("line"):
        document_key = value("document_key", node)
        source_id = value("source_id", node)
        if not isinstance(document_key, str) or not isinstance(source_id, str):
            issue(
                "line-identity",
                node=node,
                document_key=document_key,
                source_id=source_id,
            )
            continue
        key = f"{document_key}|{source_id}"
        tf_line_counts[key] += 1
        tf_line_nodes.setdefault(key, node)

    tf_lexeme_counts: Counter[str] = Counter()
    for node in api.F.otype.s("lex"):
        identity = value("lexeme", node)
        if not isinstance(identity, str) or not identity:
            issue("lexeme-identity", direction="invalid-tf", node=node, identity=identity)
            continue
        tf_lexeme_counts[identity] += 1

    tf_sign_counts: Counter[str] = Counter()
    tf_sign_slots: dict[str, int] = {}
    for slot in range(1, api.F.otype.maxSlot + 1):
        if slot in synthetic_slots:
            continue
        document_key = value("document_key", slot)
        word_id = value("word_id", slot)
        src_path = value("src_path", slot)
        if not all(isinstance(item, str) and item for item in (document_key, word_id, src_path)):
            issue(
                "semantic-sign-identity",
                slot=slot,
                document_key=document_key,
                word_id=word_id,
                src_path=src_path,
            )
            continue
        key = f"{document_key}|{word_id}|{src_path}"
        tf_sign_counts[key] += 1
        tf_sign_slots.setdefault(key, slot)

    source_line_counts: Counter[str] = Counter()
    source_lexeme_ids: set[str] = set()
    source_sign_counts: Counter[str] = Counter()

    word_feature_names = (
        "ref",
        "frag",
        "form",
        "lang",
        "cf",
        "gw",
        "sense",
        "norm",
        "pos",
        "epos",
        "inst",
        "sig",
        "lemmaknown",
        "gdl_json",
    )
    document_feature_names = (
        "document",
        "document_key",
        "source_id",
        "text_id",
        "subproject",
        "populated",
        "catalogue_present",
        "catalogue_json",
        "license",
        "license_url",
        "license_type",
    )

    for edition in loader.iter_editions(data, skip_unreadable=True):
        document_key = edition.key
        joined = metadata.join_edition(edition, metadata_index)
        document_node = tf_document_nodes.get(document_key)
        if document_node is not None:
            expected_document = {
                "document": document_key,
                "document_key": document_key,
                "source_id": edition.text_id,
                "text_id": edition.text_id,
                "subproject": edition.subproject,
                "populated": int(edition.populated),
                "catalogue_present": int(joined.catalogue_present),
                "catalogue_json": _canonical_json(joined.catalogue),
                "license": joined.license,
                "license_url": joined.license_url,
                "license_type": joined.license_type,
            }
            mismatches = {
                name: {"source": expected_document[name], "tf": value(name, document_node)}
                for name in document_feature_names
                if expected_document[name] != value(name, document_node)
            }
            if mismatches:
                issue(
                    "document-feature-mismatch",
                    identity=document_key,
                    features=mismatches,
                )

        section_view = sections.walk_document(edition.doc)
        for line in section_view.lines:
            source_line_counts[f"{document_key}|{line.source_id}"] += 1

        for word in words.iter_words(edition.doc):
            word_identity = f"{document_key}|{word.source_id}"
            word_node = tf_word_nodes.get(word_identity)
            if word_node is not None:
                expected_word = {
                    "ref": word.ref,
                    "frag": word.frag,
                    "form": word.form,
                    "lang": word.lang,
                    "cf": word.cf,
                    "gw": word.gw,
                    "sense": word.sense,
                    "norm": word.norm,
                    "pos": word.pos,
                    "epos": word.epos,
                    "inst": word.inst,
                    "sig": word.sig,
                    "lemmaknown": word.lemmaknown,
                    "gdl_json": roundtrip.source_gdl_json(word.features),
                }
                mismatches = {
                    name: {"source": expected_word[name], "tf": value(name, word_node)}
                    for name in word_feature_names
                    if expected_word[name] != value(name, word_node)
                }
                if mismatches:
                    issue(
                        "word-feature-mismatch",
                        identity=word_identity,
                        features=mismatches,
                    )

                source_line = section_view.word_to_line.get(word.source_id)
                expected_line_targets = (
                    [] if source_line is None else [f"{document_key}|{source_line}"]
                )
                actual_line_targets: list[str] = []
                for target in edge("word_line", word_node):
                    target_document = value("document_key", target)
                    target_source = value("source_id", target)
                    if isinstance(target_document, str) and isinstance(target_source, str):
                        actual_line_targets.append(f"{target_document}|{target_source}")
                    else:
                        actual_line_targets.append(f"<invalid:{target}>")
                if sorted(expected_line_targets) != sorted(actual_line_targets):
                    issue(
                        "word-line-relation",
                        identity=word_identity,
                        source=sorted(expected_line_targets),
                        tf=sorted(actual_line_targets),
                    )

                expected_lex_targets = sorted(
                    _lexeme_identity(key) for key in lexemes.keys_for_word(word)
                )
                actual_lex_targets = sorted(
                    identity
                    for target in edge("word_lex", word_node)
                    if isinstance((identity := value("lexeme", target)), str)
                )
                if expected_lex_targets != actual_lex_targets:
                    issue(
                        "word-lex-relation",
                        identity=word_identity,
                        source=expected_lex_targets,
                        tf=actual_lex_targets,
                    )

            for key in lexemes.keys_for_word(word):
                source_lexeme_ids.add(_lexeme_identity(key))

            for sign in word.signs:
                sign_identity = (
                    f"{document_key}|{word.source_id}|{sign.src_path}"
                )
                source_sign_counts[sign_identity] += 1
                slot = tf_sign_slots.get(sign_identity)
                if slot is None:
                    continue
                utf8 = sign.value.get("utf8")
                expected_sign = {
                    "utf8": utf8 if isinstance(utf8, str) else None,
                    "readingu": utf8 if isinstance(utf8, str) else None,
                    "sign_json": _canonical_json(sign.value),
                    "gdl_id": _stored_scalar(sign.value.get("id")),
                    "gdl_form": _stored_scalar(sign.value.get("form")),
                    "gdl_sexified": _stored_scalar(sign.value.get("sexified")),
                }
                mismatches = {
                    name: {"source": expected_sign[name], "tf": value(name, slot)}
                    for name in expected_sign
                    if expected_sign[name] != value(name, slot)
                }
                if mismatches:
                    issue(
                        "semantic-sign-payload-mismatch",
                        identity=sign_identity,
                        features=mismatches,
                    )

    missing_lines = _difference(source_line_counts, tf_line_counts)
    unexpected_lines = _difference(tf_line_counts, source_line_counts)
    for identity in missing_lines:
        issue("missing-line", identity=identity)
    for identity in unexpected_lines:
        issue("unexpected-line", identity=identity)
    for identity in _duplicates(source_line_counts):
        issue("duplicate-source-line", identity=identity)
    for identity in _duplicates(tf_line_counts):
        issue("duplicate-tf-line", identity=identity)

    source_lexeme_counts = Counter({identity: 1 for identity in source_lexeme_ids})
    missing_lexemes = _difference(source_lexeme_counts, tf_lexeme_counts)
    unexpected_lexemes = _difference(tf_lexeme_counts, source_lexeme_counts)
    for identity in missing_lexemes:
        issue("lexeme-identity", direction="missing-in-tf", identity=identity)
    for identity in unexpected_lexemes:
        issue("lexeme-identity", direction="unexpected-in-tf", identity=identity)
    for identity in _duplicates(tf_lexeme_counts):
        issue("duplicate-tf-lexeme", identity=identity)

    missing_signs = _difference(source_sign_counts, tf_sign_counts)
    unexpected_signs = _difference(tf_sign_counts, source_sign_counts)
    for identity in missing_signs:
        issue("missing-semantic-sign", identity=identity)
    for identity in unexpected_signs:
        issue("unexpected-semantic-sign", identity=identity)
    for identity in _duplicates(source_sign_counts):
        issue("duplicate-source-semantic-sign", identity=identity)
    for identity in _duplicates(tf_sign_counts):
        issue("duplicate-tf-semantic-sign", identity=identity)

    return {
        "issues": issues,
        "mismatch_counts": dict(sorted(mismatch_counts.items())),
        "lines": {
            "source_identities": len(source_line_counts),
            "tf_identities": len(tf_line_counts),
            "missing_in_tf": missing_lines,
            "unexpected_in_tf": unexpected_lines,
        },
        "lexemes": {
            "source_identities": len(source_lexeme_counts),
            "tf_identities": len(tf_lexeme_counts),
            "missing_in_tf": missing_lexemes,
            "unexpected_in_tf": unexpected_lexemes,
        },
        "signs": {
            "source_identities": len(source_sign_counts),
            "tf_identities": len(tf_sign_counts),
            "missing_in_tf": missing_signs,
            "unexpected_in_tf": unexpected_signs,
        },
    }


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

    members_manifest, catalogue_manifest, source_state_sha256 = _source_state_evidence(
        data_path
    )
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
    semantic = _semantic_reconciliation(
        data=data_path,
        api=api,
        metadata_index=metadata_index,
        synthetic_slots=synthetic_set,
    )

    missing_documents = _difference(source_documents, tf_documents)
    unexpected_documents = _difference(tf_documents, source_documents)
    missing_words = _difference(source_word_ids, tf_word_ids)
    unexpected_words = _difference(tf_word_ids, source_word_ids)

    semantic_signs = _count_reconciliation(source_words_census.signs, semantic_tf_slots)
    line_counts = _count_reconciliation(source_sections.source_lines, _node_count(api, "line"))
    line_counts.update(
        {
            "missing_in_tf": semantic["lines"]["missing_in_tf"],
            "unexpected_in_tf": semantic["lines"]["unexpected_in_tf"],
        }
    )
    lexeme_counts = _count_reconciliation(source_lexemes.lexemes, _node_count(api, "lex"))
    lexeme_counts.update(
        {
            "missing_in_tf": semantic["lexemes"]["missing_in_tf"],
            "unexpected_in_tf": semantic["lexemes"]["unexpected_in_tf"],
        }
    )

    missing_catalogue = sorted(set(source_documents) - set(metadata_index.records))
    unmatched_catalogue = sorted(set(metadata_index.records) - set(source_documents))

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

    readable_manifest = sum(
        item["status"] == "readable" for item in members_manifest
    )
    hazard_manifest = sum(item["status"] == "hazard" for item in members_manifest)
    if len(members_manifest) != source_survey.source_files:
        unexplained.append(
            {
                "kind": "source-member-manifest-census",
                "manifest_count": len(members_manifest),
                "survey_count": source_survey.source_files,
            }
        )
    if readable_manifest != source_survey.parseable:
        unexplained.append(
            {
                "kind": "readable-member-manifest-census",
                "manifest_count": readable_manifest,
                "survey_count": source_survey.parseable,
            }
        )
    if hazard_manifest != source_survey.unreadable:
        unexplained.append(
            {
                "kind": "hazard-member-manifest-census",
                "manifest_count": hazard_manifest,
                "survey_count": source_survey.unreadable,
            }
        )

    for kind, comparison in (
        ("semantic-sign-count", semantic_signs),
        ("line-count", line_counts),
        ("lexeme-count", lexeme_counts),
    ):
        if comparison["delta"] != 0:
            unexplained.append({"kind": kind, **comparison})

    unexplained.extend(semantic["issues"])

    if semantic["lines"]["source_identities"] != source_sections.source_lines:
        unexplained.append(
            {
                "kind": "source-line-census",
                "identity_count": semantic["lines"]["source_identities"],
                "census_count": source_sections.source_lines,
            }
        )
    if semantic["lexemes"]["source_identities"] != source_lexemes.lexemes:
        unexplained.append(
            {
                "kind": "source-lexeme-census",
                "identity_count": semantic["lexemes"]["source_identities"],
                "census_count": source_lexemes.lexemes,
            }
        )
    if semantic["signs"]["source_identities"] != source_words_census.signs:
        unexplained.append(
            {
                "kind": "source-sign-census",
                "identity_count": semantic["signs"]["source_identities"],
                "census_count": source_words_census.signs,
            }
        )
    if len(missing_catalogue) != source_metadata.missing_catalogue_documents:
        unexplained.append(
            {
                "kind": "catalogue-missing-census",
                "identity_count": len(missing_catalogue),
                "census_count": source_metadata.missing_catalogue_documents,
            }
        )

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
            "source_state_sha256": source_state_sha256,
            "subprojects": loader.edition_subprojects(data_path),
            "document_keys": sorted(source_survey.keys),
            "members_manifest": members_manifest,
            "catalogue_manifest": catalogue_manifest,
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
            "sign_identities": semantic["signs"],
            "lines": line_counts,
            "lexemes": lexeme_counts,
            "semantic_content_mismatches": semantic["mismatch_counts"],
            "gdl_unknown": source_gdl.unknown,
        },
        "catalogue": {
            "entries": source_metadata.catalogue_entries,
            "attached_documents": source_metadata.catalogue_attached_documents,
            "missing_documents": source_metadata.missing_catalogue_documents,
            "missing_document_keys": missing_catalogue,
            "unmatched_catalogue_keys": unmatched_catalogue,
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
