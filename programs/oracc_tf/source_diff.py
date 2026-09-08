"""Deterministic, policy-free source-state diffs for P-002 Phase 4.

This module reports observable differences between two already-acquired ORACC
source states.  It deliberately does not fetch archives, classify new source
shapes, decide whether a change is safe, rebuild corpora, or publish anything.
Those decisions belong to adjacent P-002 phases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
import re


_STATE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_ID_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TEXT_ID_RE = re.compile(r"^[PQX][0-9]+$")
_KNOWN_GDL_CHILD_KEYS = ("group", "seq", "qualified", "mods")


class SourceDiffError(ValueError):
    """Source state cannot be compared without guessing or losing identity."""


@dataclass(frozen=True)
class SourceDocument:
    """One source document paired with its qualified ORACC project identity."""

    subproject: str
    document: Mapping[str, object]


@dataclass(frozen=True)
class TextState:
    key: str
    subproject: str
    text_id: str
    content_sha256: str
    word_count: int
    lemma_count: int
    gdl_shapes: tuple[tuple[str, ...], ...]
    chunk_shapes: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class ArchiveSnapshot:
    dataset: str
    archive: str
    source_state: str
    oracc_utc_timestamp: str
    licence: str
    texts: Mapping[str, TextState]


@dataclass(frozen=True)
class SubprojectDelta:
    before_words: int
    after_words: int
    word_delta: int
    before_lemmas: int
    after_lemmas: int
    lemma_delta: int


@dataclass(frozen=True)
class SourceDiff:
    dataset: str
    archive: str
    before_source_state: str
    after_source_state: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]
    text_word_deltas: Mapping[str, int]
    subproject_deltas: Mapping[str, SubprojectDelta]
    new_gdl_shapes: tuple[tuple[str, ...], ...]
    new_chunk_shapes: tuple[tuple[str, str | None], ...]
    licence_before: str
    licence_after: str
    oracc_utc_timestamp_before: str
    oracc_utc_timestamp_after: str

    @property
    def empty(self) -> bool:
        """Whether the two states have no observable semantic/metadata delta."""
        return not (
            self.added
            or self.removed
            or self.modified
            or self.new_gdl_shapes
            or self.new_chunk_shapes
            or self.licence_before != self.licence_after
            or self.oracc_utc_timestamp_before != self.oracc_utc_timestamp_after
        )


def _safe_name(value: object, field: str, *, allow_slash: bool = False) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise SourceDiffError(f"{field} must be a non-empty trimmed string")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in value):
        raise SourceDiffError(f"{field} contains control characters")
    parts = value.split("/") if allow_slash else [value]
    if any(_ID_COMPONENT_RE.fullmatch(part) is None for part in parts):
        raise SourceDiffError(f"invalid {field}: {value!r}")
    return value


def canonical_document_sha256(document: Mapping[str, object]) -> str:
    """Hash JSON semantics: mapping order is neutral, list/source order is not."""
    if not isinstance(document, Mapping):
        raise SourceDiffError("document must be a mapping")
    try:
        payload = json.dumps(
            document,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SourceDiffError("document is not canonical JSON data") from exc
    return sha256(payload).hexdigest()


def _walk_mappings(value: object):
    if isinstance(value, Mapping):
        yield value
        children = value.get("cdl")
        if children is not None:
            if not isinstance(children, list):
                raise SourceDiffError("source 'cdl' field must be a list when present")
            for child in children:
                if not isinstance(child, Mapping):
                    raise SourceDiffError("source 'cdl' children must be objects")
                yield from _walk_mappings(child)


def _word_stats(document: Mapping[str, object]) -> tuple[int, int]:
    words = 0
    lemmas = 0
    for node in _walk_mappings(document):
        if node.get("node") != "l":
            continue
        words += 1
        features = node.get("f")
        if features is None:
            features = {}
        if not isinstance(features, Mapping):
            raise SourceDiffError("word 'f' field must be an object when present")
        # Match the established P-001 word-layer rule: normalization alone is
        # editorial evidence, not proof that ORACC supplied a lexical analysis.
        if any(features.get(key) is not None for key in ("cf", "gw", "sense")) or node.get("sig") is not None:
            lemmas += 1
    return words, lemmas


def _gdl_object_shapes(value: object) -> set[tuple[str, ...]]:
    shapes: set[tuple[str, ...]] = set()

    def visit(obj: object) -> None:
        if isinstance(obj, Mapping):
            shapes.add(tuple(sorted(str(key) for key in obj.keys())))
            # Preserve the established ORACC syntax contract for known child
            # containers while still descending generically through any future
            # mapping/list-valued keys so novelty cannot hide under new names.
            for key in _KNOWN_GDL_CHILD_KEYS:
                if key not in obj:
                    continue
                children = obj[key]
                if not isinstance(children, list):
                    raise SourceDiffError(f"GDL child field {key!r} must be a list")
                if any(not isinstance(child, Mapping) for child in children):
                    raise SourceDiffError(
                        f"GDL child field {key!r} must contain only objects"
                    )
            for child in obj.values():
                if isinstance(child, (Mapping, list)):
                    visit(child)
            return
        if isinstance(obj, list):
            for child in obj:
                if isinstance(child, (Mapping, list)):
                    visit(child)

    if value is None:
        return shapes
    if not isinstance(value, list):
        raise SourceDiffError("word GDL must be a list when present")
    for item in value:
        if not isinstance(item, Mapping):
            raise SourceDiffError("GDL entries must be objects")
        visit(item)
    return shapes


def _source_shapes(document: Mapping[str, object]) -> tuple[
    tuple[tuple[str, ...], ...], tuple[tuple[str, str | None], ...]
]:
    gdl: set[tuple[str, ...]] = set()
    chunks: set[tuple[str, str | None]] = set()
    for node in _walk_mappings(document):
        if node.get("node") == "l":
            features = node.get("f")
            if features is None:
                features = {}
            if not isinstance(features, Mapping):
                raise SourceDiffError("word 'f' field must be an object when present")
            gdl.update(_gdl_object_shapes(features.get("gdl")))
        if node.get("node") == "c":
            chunk_type = node.get("type")
            subtype = node.get("subtype")
            if not isinstance(chunk_type, str) or not chunk_type:
                raise SourceDiffError("source chunk must have a non-empty string type")
            if subtype is not None and not isinstance(subtype, str):
                raise SourceDiffError("source chunk subtype must be a string or null")
            chunks.add((chunk_type, subtype))
    return tuple(sorted(gdl)), tuple(sorted(chunks, key=lambda item: (item[0], item[1] or "")))


def _text_state(source: SourceDocument) -> TextState:
    if not isinstance(source, SourceDocument):
        raise SourceDiffError("documents must contain SourceDocument records")
    subproject = _safe_name(source.subproject, "subproject", allow_slash=True)
    document = source.document
    if not isinstance(document, Mapping):
        raise SourceDiffError("source document payload must be a mapping")
    text_id = document.get("textid")
    if not isinstance(text_id, str) or _TEXT_ID_RE.fullmatch(text_id) is None:
        raise SourceDiffError(f"invalid source text id: {text_id!r}")
    words, lemmas = _word_stats(document)
    gdl_shapes, chunk_shapes = _source_shapes(document)
    key = f"{subproject}:{text_id}"
    return TextState(
        key=key,
        subproject=subproject,
        text_id=text_id,
        content_sha256=canonical_document_sha256(document),
        word_count=words,
        lemma_count=lemmas,
        gdl_shapes=gdl_shapes,
        chunk_shapes=chunk_shapes,
    )


def snapshot_archive(
    *,
    dataset: str,
    archive: str,
    source_state: str,
    oracc_utc_timestamp: str,
    licence: str,
    documents: Sequence[SourceDocument],
) -> ArchiveSnapshot:
    """Measure one already-acquired archive into a deterministic comparison state."""
    dataset_id = _safe_name(dataset, "dataset")
    archive_id = _safe_name(archive, "archive")
    if not isinstance(source_state, str) or _STATE_RE.fullmatch(source_state) is None:
        raise SourceDiffError("source_state must be a canonical sha256: digest")
    if not isinstance(oracc_utc_timestamp, str) or _TIMESTAMP_RE.fullmatch(oracc_utc_timestamp) is None:
        raise SourceDiffError("oracc_utc_timestamp must use YYYY-MM-DDTHH:MM:SS")
    try:
        datetime.strptime(oracc_utc_timestamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError as exc:
        raise SourceDiffError("oracc_utc_timestamp is not a valid calendar timestamp") from exc
    if not isinstance(licence, str) or not licence or licence != licence.strip():
        raise SourceDiffError("licence must be a non-empty verbatim source string")
    if isinstance(documents, (str, bytes, bytearray)) or not isinstance(documents, Sequence):
        raise SourceDiffError("documents must be a sequence")

    measured: dict[str, TextState] = {}
    for source in documents:
        text = _text_state(source)
        if text.key in measured:
            raise SourceDiffError(f"duplicate qualified document identity: {text.key}")
        measured[text.key] = text
    ordered = {key: measured[key] for key in sorted(measured)}
    return ArchiveSnapshot(
        dataset=dataset_id,
        archive=archive_id,
        source_state=source_state,
        oracc_utc_timestamp=oracc_utc_timestamp,
        licence=licence,
        texts=ordered,
    )


def _all_shapes(snapshot: ArchiveSnapshot) -> tuple[set[tuple[str, ...]], set[tuple[str, str | None]]]:
    gdl: set[tuple[str, ...]] = set()
    chunks: set[tuple[str, str | None]] = set()
    for text in snapshot.texts.values():
        gdl.update(text.gdl_shapes)
        chunks.update(text.chunk_shapes)
    return gdl, chunks


def diff_snapshots(before: ArchiveSnapshot, after: ArchiveSnapshot) -> SourceDiff:
    """Report deterministic source facts without applying publication policy."""
    if not isinstance(before, ArchiveSnapshot) or not isinstance(after, ArchiveSnapshot):
        raise SourceDiffError("both inputs must be ArchiveSnapshot records")
    if before.dataset != after.dataset or before.archive != after.archive:
        raise SourceDiffError("source snapshots belong to different dataset/archive identities")

    before_keys = set(before.texts)
    after_keys = set(after.texts)
    added = tuple(sorted(after_keys - before_keys))
    removed = tuple(sorted(before_keys - after_keys))
    modified = tuple(
        key
        for key in sorted(before_keys & after_keys)
        if before.texts[key].content_sha256 != after.texts[key].content_sha256
    )

    changed = tuple(sorted(set(added) | set(removed) | set(modified)))
    text_word_deltas = {
        key: (after.texts[key].word_count if key in after.texts else 0)
        - (before.texts[key].word_count if key in before.texts else 0)
        for key in changed
    }

    subprojects = sorted(
        {text.subproject for text in before.texts.values()}
        | {text.subproject for text in after.texts.values()}
    )
    subproject_deltas: dict[str, SubprojectDelta] = {}
    for subproject in subprojects:
        before_words = sum(
            text.word_count for text in before.texts.values() if text.subproject == subproject
        )
        after_words = sum(
            text.word_count for text in after.texts.values() if text.subproject == subproject
        )
        before_lemmas = sum(
            text.lemma_count for text in before.texts.values() if text.subproject == subproject
        )
        after_lemmas = sum(
            text.lemma_count for text in after.texts.values() if text.subproject == subproject
        )
        subproject_deltas[subproject] = SubprojectDelta(
            before_words=before_words,
            after_words=after_words,
            word_delta=after_words - before_words,
            before_lemmas=before_lemmas,
            after_lemmas=after_lemmas,
            lemma_delta=after_lemmas - before_lemmas,
        )

    before_gdl, before_chunks = _all_shapes(before)
    after_gdl, after_chunks = _all_shapes(after)
    return SourceDiff(
        dataset=before.dataset,
        archive=before.archive,
        before_source_state=before.source_state,
        after_source_state=after.source_state,
        added=added,
        removed=removed,
        modified=modified,
        text_word_deltas=text_word_deltas,
        subproject_deltas=subproject_deltas,
        new_gdl_shapes=tuple(sorted(after_gdl - before_gdl)),
        new_chunk_shapes=tuple(
            sorted(after_chunks - before_chunks, key=lambda item: (item[0], item[1] or ""))
        ),
        licence_before=before.licence,
        licence_after=after.licence,
        oracc_utc_timestamp_before=before.oracc_utc_timestamp,
        oracc_utc_timestamp_after=after.oracc_utc_timestamp,
    )


def render_diff(diff: SourceDiff) -> bytes:
    """Serialize a diff as stable machine-readable JSON."""
    if not isinstance(diff, SourceDiff):
        raise SourceDiffError("diff must be a SourceDiff record")
    payload = {
        "schema_version": 1,
        "dataset": diff.dataset,
        "archive": diff.archive,
        "before": {
            "source_state": diff.before_source_state,
            "licence": diff.licence_before,
            "oracc_utc_timestamp": diff.oracc_utc_timestamp_before,
        },
        "after": {
            "source_state": diff.after_source_state,
            "licence": diff.licence_after,
            "oracc_utc_timestamp": diff.oracc_utc_timestamp_after,
        },
        "added": list(diff.added),
        "removed": list(diff.removed),
        "modified": list(diff.modified),
        "text_word_deltas": dict(sorted(diff.text_word_deltas.items())),
        "subproject_deltas": {
            key: asdict(diff.subproject_deltas[key]) for key in sorted(diff.subproject_deltas)
        },
        "new_gdl_shapes": [list(shape) for shape in diff.new_gdl_shapes],
        "new_chunk_shapes": [list(shape) for shape in diff.new_chunk_shapes],
        "empty": diff.empty,
    }
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


__all__ = [
    "ArchiveSnapshot",
    "SourceDiff",
    "SourceDiffError",
    "SourceDocument",
    "SubprojectDelta",
    "TextState",
    "canonical_document_sha256",
    "diff_snapshots",
    "render_diff",
    "snapshot_archive",
]
