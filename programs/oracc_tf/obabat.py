"""Source-faithful OBABAT/atletters Text-Fabric adapter for issue #58.

The generic ORACC graph builder remains responsible for GDL, word, section,
metadata, lexeme, and Text-Fabric invariants. This module narrows the source to
``obabat/atletters``, preserves OBABAT-specific word properties, and attaches a
fail-closed comparison status against the exact pinned Nino Old Babylonian
reference used by issue #39.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from . import TF_VERSION, corpus, loader, metadata, paths, words


SOURCE_DATASET = "obabat/atletters"
PUBLICATION_SLUG = "obabat-atletters"
OVERLAP_SIDECAR = "overlap-provenance.json"
DEFAULT_OVERLAP_PATH = paths.DOCS / "research" / "issue-39-obabat-overlap.json"
DATASET_NAME = "ORACC-TF OBABAT / atletters"

EXPECTED_SOURCE_BLOB = "f3dae9f3e713683ebc4c49075ff8475a44e3b1f8"
EXPECTED_NINO_REVISION = "cd8ffe826a598af4715fd724387d9834ec1300d8"
EXPECTED_NINO_BLOB = "9d9d07d0f5f80f03aadae43e87bedddcc2d05ad1"
EXPECTED_DOCUMENTS = 121
EXPECTED_OVERLAP = 86
EXPECTED_UNMATCHED = 35

OVERLAP_STATUS = "exact-p-number-overlap"
UNMATCHED_STATUS = "not-in-pinned-nino-unverified"


class OBABATProvenanceError(ValueError):
    """OBABAT overlap/source provenance is missing, malformed, or inconsistent."""


@dataclass(frozen=True)
class OverlapProvenance:
    """Validated immutable source/reference identities and document partition."""

    source_blob: str
    nino_revision: str
    nino_blob: str
    overlap_ids: frozenset[str]
    unmatched_ids: frozenset[str]

    def status(self, text_id: str) -> str:
        if text_id in self.overlap_ids:
            return OVERLAP_STATUS
        if text_id in self.unmatched_ids:
            return UNMATCHED_STATUS
        raise OBABATProvenanceError(
            f"{text_id}: OBABAT member is outside the validated 86/35 partition"
        )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OBABATProvenanceError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _load_json(path: Path) -> Mapping[str, object]:
    try:
        with Path(path).open(encoding="utf-8") as handle:
            value = json.load(handle, object_pairs_hook=_unique_object)
    except OBABATProvenanceError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OBABATProvenanceError(f"cannot read provenance source {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise OBABATProvenanceError(f"{path}: expected a JSON object")
    return value


def _git_blob_sha(path: Path) -> str:
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise OBABATProvenanceError(f"cannot read OBABAT source blob {path}: {exc}") from exc
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _id_set(value: object, *, field: str) -> frozenset[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise OBABATProvenanceError(f"{field} must be a list of document ids")
    if len(value) != len(set(value)):
        raise OBABATProvenanceError(f"{field} contains duplicate document ids")
    if any(len(item) != 7 or not item.startswith("P") or not item[1:].isdigit() for item in value):
        raise OBABATProvenanceError(f"{field} contains an invalid CDLI P-number")
    return frozenset(value)


def load_overlap_provenance(
    data: Path | str = paths.DATA,
    overlap_path: Path | str = DEFAULT_OVERLAP_PATH,
) -> OverlapProvenance:
    """Validate issue #39 provenance against the exact current OBABAT corpus.

    P-number overlap is comparison/leakage metadata only. The 35 records absent
    from the pinned Nino feature remain explicitly unverified rather than being
    promoted to a clean or independent set.
    """
    data = Path(data)
    manifest = _load_json(Path(overlap_path))
    sources = manifest.get("sources")
    counts = manifest.get("counts")
    if not isinstance(sources, Mapping) or not isinstance(counts, Mapping):
        raise OBABATProvenanceError("overlap manifest is missing sources/counts")
    oracc_source = sources.get("oracc_tf")
    nino_source = sources.get("nino_oldbabylonian")
    if not isinstance(oracc_source, Mapping) or not isinstance(nino_source, Mapping):
        raise OBABATProvenanceError("overlap manifest is missing frozen source records")

    source_path = data / SOURCE_DATASET / "corpus.json"
    actual_blob = _git_blob_sha(source_path)
    manifest_blob = oracc_source.get("blob_sha")
    if manifest_blob != EXPECTED_SOURCE_BLOB or actual_blob != EXPECTED_SOURCE_BLOB:
        raise OBABATProvenanceError(
            "OBABAT corpus blob does not match the accepted issue #39 source pin"
        )
    if oracc_source.get("path") != "data/obabat/atletters/corpus.json":
        raise OBABATProvenanceError("overlap manifest has an unexpected OBABAT source path")

    nino_revision = nino_source.get("revision")
    nino_blob = nino_source.get("blob_sha")
    if nino_revision != EXPECTED_NINO_REVISION or nino_blob != EXPECTED_NINO_BLOB:
        raise OBABATProvenanceError("pinned Nino revision/blob does not match issue #39")
    if nino_source.get("path") != "tf/1.0.6/pnumber.tf":
        raise OBABATProvenanceError("overlap manifest has an unexpected Nino pnumber path")

    source_doc = _load_json(source_path)
    if source_doc.get("project") != SOURCE_DATASET:
        raise OBABATProvenanceError("OBABAT corpus project identity does not match source dataset")
    members = source_doc.get("members")
    if not isinstance(members, Mapping) or not all(isinstance(key, str) for key in members):
        raise OBABATProvenanceError("OBABAT corpus members are missing or malformed")
    member_ids = frozenset(members)

    overlap_ids = _id_set(manifest.get("overlap_ids"), field="overlap_ids")
    unmatched_ids = _id_set(
        manifest.get("not_in_pinned_nino_ids"), field="not_in_pinned_nino_ids"
    )
    if overlap_ids & unmatched_ids:
        raise OBABATProvenanceError("overlap partition contains document ids in both classes")
    if overlap_ids | unmatched_ids != member_ids:
        missing = sorted(member_ids - (overlap_ids | unmatched_ids))
        extra = sorted((overlap_ids | unmatched_ids) - member_ids)
        raise OBABATProvenanceError(
            f"overlap partition does not exactly cover 121 OBABAT members; "
            f"missing={missing[:5]!r}, extra={extra[:5]!r}"
        )

    expected_counts = {
        "oracc_documents": EXPECTED_DOCUMENTS,
        "overlap_documents": EXPECTED_OVERLAP,
        "not_in_pinned_nino_documents": EXPECTED_UNMATCHED,
    }
    for field, expected in expected_counts.items():
        if counts.get(field) != expected:
            raise OBABATProvenanceError(
                f"overlap manifest {field}={counts.get(field)!r}, expected {expected}"
            )
    if len(member_ids) != EXPECTED_DOCUMENTS:
        raise OBABATProvenanceError(
            f"OBABAT source has {len(member_ids)} members, expected {EXPECTED_DOCUMENTS}"
        )
    if len(overlap_ids) != EXPECTED_OVERLAP or len(unmatched_ids) != EXPECTED_UNMATCHED:
        raise OBABATProvenanceError("overlap partition cardinality is not the accepted 86/35 split")

    return OverlapProvenance(
        source_blob=actual_blob,
        nino_revision=str(nino_revision),
        nino_blob=str(nino_blob),
        overlap_ids=overlap_ids,
        unmatched_ids=unmatched_ids,
    )


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def project_word_features(word: words.WordRecord) -> dict[str, object]:
    """Project only source-supplied OBABAT properties not in the core word schema."""
    projected: dict[str, object] = {}
    if "props" in word.source:
        props = word.source["props"]
        projected["props_json"] = _canonical_json(props)
        if not isinstance(props, list):
            raise OBABATProvenanceError(
                f"{word.source_id}: source props is not a list"
            )
        discourse_values: set[str] = set()
        for item in props:
            if not isinstance(item, Mapping):
                raise OBABATProvenanceError(
                    f"{word.source_id}: source props contains a non-object"
                )
            if item.get("name") == "discourse":
                value = item.get("value")
                if value is not None and not isinstance(value, str):
                    raise OBABATProvenanceError(
                        f"{word.source_id}: discourse property is not text"
                    )
                if value:
                    discourse_values.add(value)
        if len(discourse_values) > 1:
            raise OBABATProvenanceError(
                f"{word.source_id}: conflicting discourse property values"
            )
        if discourse_values:
            projected["discourse"] = next(iter(discourse_values))

    for name in ("base", "morph", "morph2"):
        value = word.features.get(name)
        if value is not None:
            projected[name] = value
    return projected


def _write_overlap_sidecar(out_dir: Path, provenance: OverlapProvenance) -> None:
    payload = {
        "schema_version": 1,
        "source_dataset": SOURCE_DATASET,
        "source_blob": provenance.source_blob,
        "nino_reference": {
            "repository": "Nino-cunei/oldbabylonian",
            "revision": provenance.nino_revision,
            "pnumber_blob": provenance.nino_blob,
        },
        "statuses": {
            "overlap": OVERLAP_STATUS,
            "not_in_pinned_nino": UNMATCHED_STATUS,
        },
        "overlap_ids": sorted(provenance.overlap_ids),
        "not_in_pinned_nino_ids": sorted(provenance.unmatched_ids),
        "benchmark_policy": (
            "Exclude exact P-number overlaps from Nino-independent evaluation. "
            "Records absent from the pinned Nino pnumber feature remain unverified."
        ),
    }
    (out_dir / OVERLAP_SIDECAR).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_tf(
    out_dir: Path | str,
    *,
    data: Path | str = paths.DATA,
    overlap_path: Path | str = DEFAULT_OVERLAP_PATH,
) -> corpus.CorpusBuildReport:
    """Build all 121 OBABAT letters with validated overlap provenance."""
    data = Path(data)
    out_dir = Path(out_dir)
    provenance = load_overlap_provenance(data, overlap_path)
    subprojects = [SOURCE_DATASET]
    metadata_index = metadata.load_index(data, subprojects=subprojects)
    editions = loader.iter_editions(
        data,
        subprojects=subprojects,
        skip_unreadable=False,
    )

    def document_features(edition: loader.Edition) -> Mapping[str, object]:
        return {"nino_overlap_status": provenance.status(edition.text_id)}

    report = corpus.build_tf(
        out_dir,
        editions=editions,
        metadata_index=metadata_index,
        word_feature_projector=project_word_features,
        document_feature_projector=document_features,
        dataset_name=DATASET_NAME,
    )
    _write_overlap_sidecar(out_dir, provenance)
    return report
