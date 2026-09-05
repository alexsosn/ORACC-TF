"""Parse ORACC TEI translation exports without guessing alignment.

P-001 M9 treats the TEI ``xtr:sref``/``xtr:eref`` line range as the source of
truth.  This module deliberately does not know about Text-Fabric slots; corpus
integration resolves those preserved source references against the already
validated section graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET


LICENSE = "CC BY-SA 3.0"
LICENSE_URL = "https://oracc.org/doc/about/licensing/"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


class TranslationParseError(ValueError):
    """A TEI translation export cannot be represented without guessing."""


@dataclass(frozen=True)
class TranslationUnit:
    """One source-aligned translation block from the TEI export."""

    sref: str
    eref: str
    rows: int | None
    subtype: str | None
    text: str
    text_raw: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class TranslationRecord:
    """All translation blocks for one qualified ORACC document."""

    subproject: str
    text_id: str
    units: tuple[TranslationUnit, ...]
    source_archive: str | None = None
    license: str = LICENSE
    license_url: str = LICENSE_URL

    @property
    def key(self) -> str:
        return f"{self.subproject}:{self.text_id}"


@dataclass(frozen=True)
class TranslationIndex:
    """Qualified-document lookup that cannot collide across subprojects."""

    records: dict[str, TranslationRecord]

    @classmethod
    def from_records(cls, records: Iterable[TranslationRecord]) -> "TranslationIndex":
        by_key: dict[str, TranslationRecord] = {}
        for record in records:
            if record.key in by_key:
                raise TranslationParseError(f"duplicate translation key {record.key}")
            by_key[record.key] = record
        return cls(records=by_key)

    def get(self, key: str) -> TranslationRecord | None:
        return self.records.get(key)


def _local(name: str) -> str:
    return name.rsplit("}", 1)[-1]


def _attr_local(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local(key) == name:
            return value
    return None


def _clean_text(element: ET.Element) -> str:
    """Plain translation text, excluding editorial notes."""
    chunks: list[str] = []

    def visit(node: ET.Element) -> None:
        if _local(node.tag) == "note":
            return
        if node.text:
            chunks.append(node.text)
        for child in node:
            visit(child)
            if child.tail:
                chunks.append(child.tail)

    visit(element)
    return " ".join("".join(chunks).split())


def _render_element(element: ET.Element) -> str:
    """Render source markup canonically without namespace prefixes."""
    tag = _local(element.tag)
    attrs = "".join(
        f' {_local(key)}="{escape(value, quote=True)}"'
        for key, value in sorted(element.attrib.items(), key=lambda item: _local(item[0]))
    )
    parts = [f"<{tag}{attrs}>"]
    if element.text:
        parts.append(escape(element.text))
    for child in element:
        if _local(child.tag) != "note":
            parts.append(_render_element(child))
        if child.tail:
            parts.append(escape(child.tail))
    parts.append(f"</{tag}>")
    return "".join(parts)


def _raw_text(element: ET.Element) -> str:
    """Canonical inner XML for translation prose, excluding note elements."""
    parts: list[str] = []
    if element.text:
        parts.append(escape(element.text))
    for child in element:
        if _local(child.tag) != "note":
            parts.append(_render_element(child))
        if child.tail:
            parts.append(escape(child.tail))
    return " ".join("".join(parts).split())


def _translation_content(unit: ET.Element) -> tuple[str, str]:
    prose = [child for child in unit if _local(child.tag) != "note"]
    if not prose:
        return _clean_text(unit), _raw_text(unit)
    plain = " ".join(filter(None, (_clean_text(child) for child in prose)))
    raw = " ".join(filter(None, (_raw_text(child) for child in prose)))
    return plain, raw


def parse_tei_file(
    path: Path | str,
    *,
    subproject: str,
    source_archive: str | None = None,
) -> TranslationRecord:
    """Parse one ORACC TEI document into loss-minimising translation records."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise TranslationParseError(f"cannot parse TEI {path}: {exc}") from exc

    text_id = root.attrib.get(_XML_ID) or path.stem
    if not text_id:
        raise TranslationParseError(f"TEI {path}: missing document id")

    units: list[TranslationUnit] = []
    for element in root.iter():
        if _local(element.tag) != "div3" or element.attrib.get("type") != "tr":
            continue
        sref = _attr_local(element, "sref")
        eref = _attr_local(element, "eref")
        if not sref or not eref:
            raise TranslationParseError(
                f"{subproject}:{text_id}: translation block missing sref/eref"
            )
        rows_raw = _attr_local(element, "rows")
        try:
            rows = int(rows_raw) if rows_raw not in (None, "") else None
        except ValueError as exc:
            raise TranslationParseError(
                f"{subproject}:{text_id}: invalid rows {rows_raw!r}"
            ) from exc
        text, text_raw = _translation_content(element)
        notes = tuple(
            _clean_text(child)
            for child in element.iter()
            if _local(child.tag) == "note" and _clean_text(child)
        )
        units.append(
            TranslationUnit(
                sref=sref,
                eref=eref,
                rows=rows,
                subtype=element.attrib.get("subtype"),
                text=text,
                text_raw=text_raw,
                notes=notes,
            )
        )

    return TranslationRecord(
        subproject=subproject,
        text_id=text_id,
        units=tuple(units),
        source_archive=source_archive,
    )
