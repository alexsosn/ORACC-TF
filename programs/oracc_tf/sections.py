"""Stateful CDL section walk for P-001 M3.

ORACC ``d`` markers are siblings of words, not containers. A line therefore
contains the words seen after its ``line-start`` marker until the next section
transition. This module walks the CDL in source order while maintaining that
state explicitly.

The walk is deliberately source-faithful:

* every source ``c`` object becomes a generic ``chunk`` record;
* ``phrase`` chunks additionally get an ergonomic ``phrase`` record;
* no output node type is named ``sentence``;
* words encountered before required section markers are retained under
  explicitly synthetic ancestors and every recovery is reported;
* object/surface/column transitions reset downstream state rather than letting
  words leak into a previous physical section.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from . import loader, paths


CHUNK_TYPES = frozenset({"text", "discourse", "sentence", "phrase"})
MARKER_TYPES = frozenset({
    "object", "surface", "column", "line-start", "nonw", "nonx"
})


class InvalidSectionSource(ValueError):
    """Malformed CDL cannot be walked without guessing."""


class UnknownChunkType(InvalidSectionSource):
    """A source ``c`` object has a chunk type M3 does not know."""


class UnknownMarkerType(InvalidSectionSource):
    """A source ``d`` marker has an unrecognised type."""


@dataclass(frozen=True)
class SectionNode:
    """One intermediate section/chunk node destined for Text-Fabric."""

    otype: str
    source_id: str
    label: str = ""
    ref: str | None = None
    synthetic: int = 0
    face_id: str | None = None
    column_id: str | None = None
    chunk_type: str | None = None
    chunk_subtype: str | None = None
    implicit: str | None = None
    word_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Anomaly:
    """One explicit recovery from a section-state anomaly."""

    kind: str
    at: str


@dataclass(frozen=True)
class SectionWalk:
    """Materialised result of one document's streaming section walk."""

    text_id: str
    faces: tuple[SectionNode, ...]
    columns: tuple[SectionNode, ...]
    lines: tuple[SectionNode, ...]
    chunks: tuple[SectionNode, ...]
    phrases: tuple[SectionNode, ...]
    word_to_line: Mapping[str, str]
    anomalies: tuple[Anomaly, ...]
    source_lines: int
    source_words: int

    @property
    def nodes(self) -> tuple[SectionNode, ...]:
        return self.faces + self.columns + self.lines + self.chunks + self.phrases

    @property
    def line_by_id(self) -> Mapping[str, SectionNode]:
        return {line.source_id: line for line in self.lines}

    @property
    def anomaly_kinds(self) -> frozenset[str]:
        return frozenset(item.kind for item in self.anomalies)


@dataclass(frozen=True)
class SectionCensus:
    """Whole-corpus M3 membership and anomaly accounting."""

    source_lines: int
    real_lines: int
    synthetic_lines: int
    words: int
    words_assigned_once: int
    unassigned_words: int
    multiply_assigned_words: int
    anomalies: Mapping[str, int]

    def report(self) -> str:
        anomaly_text = ", ".join(
            f"{kind}={count}" for kind, count in sorted(self.anomalies.items())
        ) or "none"
        return (
            f"source lines            : {self.source_lines:>8,}\n"
            f"real lines              : {self.real_lines:>8,}\n"
            f"synthetic lines         : {self.synthetic_lines:>8,}\n"
            f"words                   : {self.words:>8,}\n"
            f"words assigned once     : {self.words_assigned_once:>8,}\n"
            f"unassigned words        : {self.unassigned_words:>8,}\n"
            f"multiply assigned words : {self.multiply_assigned_words:>8,}\n"
            f"anomalies               : {anomaly_text}"
        )


@dataclass
class _Builder:
    otype: str
    source_id: str
    label: str = ""
    ref: str | None = None
    synthetic: int = 0
    face_id: str | None = None
    column_id: str | None = None
    chunk_type: str | None = None
    chunk_subtype: str | None = None
    implicit: str | None = None
    word_ids: list[str] | None = None

    def freeze(self) -> SectionNode:
        return SectionNode(
            otype=self.otype,
            source_id=self.source_id,
            label=self.label,
            ref=self.ref,
            synthetic=self.synthetic,
            face_id=self.face_id,
            column_id=self.column_id,
            chunk_type=self.chunk_type,
            chunk_subtype=self.chunk_subtype,
            implicit=self.implicit,
            word_ids=tuple(self.word_ids or ()),
        )


def _optional_str(
    obj: Mapping[str, object], key: str, *, where: str, empty: str | None = None
) -> str | None:
    value = obj.get(key)
    if value is None:
        return empty
    if not isinstance(value, str):
        raise InvalidSectionSource(
            f"{where}: {key!r} is {type(value).__name__}, expected string"
        )
    return value


def _children(obj: Mapping[str, object], *, where: str) -> list[Mapping[str, object]]:
    value = obj.get("cdl")
    if value is None:
        return []
    if not isinstance(value, list):
        raise InvalidSectionSource(
            f"{where}: 'cdl' is {type(value).__name__}, expected list"
        )
    children: list[Mapping[str, object]] = []
    for index, child in enumerate(value):
        if not isinstance(child, Mapping):
            raise InvalidSectionSource(
                f"{where}/cdl[{index}]: child is {type(child).__name__}, expected object"
            )
        children.append(child)
    return children


def walk_document(doc: Mapping[str, object]) -> SectionWalk:
    """Walk one parsed ``corpusjson`` document in source order.

    Real section markers never inherit stale downstream state. When source
    order is incomplete (for example a word appears before any line marker),
    a synthetic face/line is created only as far as necessary to retain that
    source word, and the recovery is recorded in ``anomalies``.
    """
    if not isinstance(doc, Mapping):
        raise InvalidSectionSource("document root must be an object")
    text_id = _optional_str(doc, "textid", where="document")
    if not text_id:
        raise InvalidSectionSource("document: missing non-empty 'textid'")

    faces: list[_Builder] = []
    columns: list[_Builder] = []
    lines: list[_Builder] = []
    chunks: list[_Builder] = []
    phrases: list[_Builder] = []
    anomalies: list[Anomaly] = []
    words_seen: list[str] = []
    word_to_line: dict[str, str] = {}

    current_face: _Builder | None = None
    current_column: _Builder | None = None
    current_line: _Builder | None = None
    source_line_count = 0

    face_seq = 0
    column_seq = 0
    line_seq = 0
    chunk_seq = 0

    def anomaly(kind: str, at: str) -> None:
        anomalies.append(Anomaly(kind=kind, at=at))

    def new_face(
        *, label: str = "", ref: str | None = None, synthetic: int = 0, at: str
    ) -> _Builder:
        nonlocal face_seq, current_face, current_column, current_line
        face_seq += 1
        source_id = f"{text_id}.face.{face_seq}"
        if synthetic:
            source_id = f"{text_id}.synthetic.face.{face_seq}"
        face = _Builder(
            otype="face", source_id=source_id, label=label, ref=ref,
            synthetic=synthetic,
        )
        faces.append(face)
        current_face = face
        current_column = None
        current_line = None
        if synthetic:
            anomaly("synthetic_face", at)
        return face

    def ensure_face(*, at: str, cause: str) -> _Builder:
        nonlocal current_face
        if current_face is None:
            anomaly(cause, at)
            return new_face(synthetic=1, at=at)
        return current_face

    def new_column(
        *, label: str = "", ref: str | None = None, synthetic: int = 0, at: str
    ) -> _Builder:
        nonlocal column_seq, current_column, current_line
        face = ensure_face(at=at, cause="column_before_surface")
        column_seq += 1
        source_id = f"{text_id}.column.{column_seq}"
        if synthetic:
            source_id = f"{text_id}.synthetic.column.{column_seq}"
        column = _Builder(
            otype="column", source_id=source_id, label=label, ref=ref,
            synthetic=synthetic, face_id=face.source_id,
        )
        columns.append(column)
        current_column = column
        current_line = None
        if synthetic:
            anomaly("synthetic_column", at)
        return column

    def new_line(
        *, label: str = "", ref: str | None = None, synthetic: int = 0, at: str
    ) -> _Builder:
        nonlocal line_seq, current_line
        face = ensure_face(at=at, cause="line_before_surface")
        line_seq += 1
        if not synthetic and ref:
            source_id = ref
        else:
            source_id = f"{text_id}.line.{line_seq}"
        if synthetic:
            source_id = f"{text_id}.synthetic.line.{line_seq}"
        line = _Builder(
            otype="line", source_id=source_id, label=label, ref=ref,
            synthetic=synthetic, face_id=face.source_id,
            column_id=current_column.source_id if current_column else None,
            word_ids=[],
        )
        lines.append(line)
        current_line = line
        if synthetic:
            anomaly("synthetic_line", at)
        return line

    def ensure_line(*, at: str) -> _Builder:
        nonlocal current_line
        if current_line is None:
            anomaly("word_before_line", at)
            # A missing face is a consequence of the same incomplete source
            # state; record the synthetic ancestor, but do not mislabel this
            # as a literal line marker appearing before a surface marker.
            if current_face is None:
                new_face(synthetic=1, at=at)
            return new_line(synthetic=1, at=at)
        return current_line

    def walk(node: Mapping[str, object], *, where: str) -> None:
        nonlocal current_face, current_column, current_line
        nonlocal source_line_count, chunk_seq

        kind = node.get("node")

        if kind == "c":
            chunk_type = _optional_str(node, "type", where=where)
            if chunk_type not in CHUNK_TYPES:
                raise UnknownChunkType(
                    f"{where}: unknown chunk type {chunk_type!r}"
                )
            chunk_seq += 1
            source_id = _optional_str(node, "id", where=where)
            if not source_id:
                source_id = f"{text_id}.chunk.{chunk_seq}"
            before = len(words_seen)
            for index, child in enumerate(_children(node, where=where)):
                walk(child, where=f"{where}/cdl[{index}]")
            chunk_words = list(words_seen[before:])
            chunk = _Builder(
                otype="chunk",
                source_id=source_id,
                label=_optional_str(node, "label", where=where, empty="") or "",
                chunk_type=chunk_type,
                chunk_subtype=_optional_str(node, "subtype", where=where),
                implicit=_optional_str(node, "implicit", where=where),
                word_ids=chunk_words,
            )
            chunks.append(chunk)
            if chunk_type == "phrase":
                phrases.append(_Builder(
                    otype="phrase",
                    source_id=source_id,
                    label=chunk.label,
                    word_ids=list(chunk_words),
                ))
            return

        if kind == "d":
            marker = _optional_str(node, "type", where=where)
            if marker not in MARKER_TYPES:
                raise UnknownMarkerType(
                    f"{where}: unknown marker type {marker!r}"
                )
            label = _optional_str(node, "label", where=where, empty="") or ""
            ref = _optional_str(node, "ref", where=where)

            if marker == "object":
                current_face = None
                current_column = None
                current_line = None
            elif marker == "surface":
                new_face(label=label, ref=ref, at=where)
            elif marker == "column":
                if current_face is None:
                    anomaly("column_before_surface", where)
                    new_face(synthetic=1, at=where)
                # Avoid reporting column_before_surface twice: new_column sees
                # the face we just materialised.
                new_column(label=label, ref=ref, at=where)
            elif marker == "line-start":
                source_line_count += 1
                if current_face is None:
                    anomaly("line_before_surface", where)
                    new_face(synthetic=1, at=where)
                new_line(label=label, ref=ref, at=where)
            # nonw/nonx are textual markers, not section transitions.
            return

        if kind == "l":
            word_id = _optional_str(node, "id", where=where)
            if not word_id:
                raise InvalidSectionSource(f"{where}: word has no non-empty 'id'")
            if word_id in word_to_line:
                raise InvalidSectionSource(
                    f"{where}: duplicate word id {word_id!r} would make line membership ambiguous"
                )
            line = ensure_line(at=where)
            assert line.word_ids is not None
            line.word_ids.append(word_id)
            words_seen.append(word_id)
            word_to_line[word_id] = line.source_id
            return

        if kind is None:
            # The top-level corpusjson object has no CDL node kind; recurse
            # through its cdl list exactly once.
            for index, child in enumerate(_children(node, where=where)):
                walk(child, where=f"{where}/cdl[{index}]")
            return

        raise InvalidSectionSource(f"{where}: unknown CDL node kind {kind!r}")

    walk(doc, where=text_id)

    return SectionWalk(
        text_id=text_id,
        faces=tuple(item.freeze() for item in faces),
        columns=tuple(item.freeze() for item in columns),
        lines=tuple(item.freeze() for item in lines),
        chunks=tuple(item.freeze() for item in chunks),
        phrases=tuple(item.freeze() for item in phrases),
        word_to_line=dict(word_to_line),
        anomalies=tuple(anomalies),
        source_lines=source_line_count,
        source_words=len(words_seen),
    )


def census(data: Path = paths.DATA) -> SectionCensus:
    """Measure M3 section membership over all parseable RIAO+RINAP editions."""
    source_lines = 0
    real_lines = 0
    synthetic_lines = 0
    words = 0
    words_assigned_once = 0
    unassigned_words = 0
    multiply_assigned_words = 0
    anomaly_counts: Counter[str] = Counter()

    for edition in loader.iter_editions(data, skip_unreadable=True):
        result = walk_document(edition.doc)
        source_lines += result.source_lines
        real_lines += sum(line.synthetic == 0 for line in result.lines)
        synthetic_lines += sum(line.synthetic == 1 for line in result.lines)
        words += edition.word_count
        assigned = len(result.word_to_line)
        words_assigned_once += assigned
        unassigned_words += max(0, edition.word_count - assigned)
        # Duplicate word ids fail inside walk_document, so a successful walk
        # cannot silently multiply-assign a source word.
        multiply_assigned_words += 0
        anomaly_counts.update(item.kind for item in result.anomalies)

    return SectionCensus(
        source_lines=source_lines,
        real_lines=real_lines,
        synthetic_lines=synthetic_lines,
        words=words,
        words_assigned_once=words_assigned_once,
        unassigned_words=unassigned_words,
        multiply_assigned_words=multiply_assigned_words,
        anomalies=dict(anomaly_counts),
    )
