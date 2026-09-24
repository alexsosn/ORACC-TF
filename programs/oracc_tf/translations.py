"""Parse ORACC TEI translation exports without guessing alignment.

P-001 M9 treats the TEI ``xtr:sref``/``xtr:eref`` line range as the source of
truth.  This module deliberately does not know about Text-Fabric slots; corpus
integration resolves those preserved source references against the already
validated section graph.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from html import escape
import io
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET
import zipfile


LICENSE = "ORACC default CC BY-SA 3.0; project-specific terms may differ"
LICENSE_URL = "https://oracc.museum.upenn.edu/doc/about/"
OFFICIAL_ARCHIVE_NAME = "riao-teiCorpus-20241202.zip"
OFFICIAL_ARCHIVE_URL = "https://oracc.museum.upenn.edu/riao/downloads/riao-teiCorpus-20241202.zip"
OFFICIAL_ARCHIVE_SHA256 = "b793d8920db58908e3a044b7f2d1a204c1ba0784e880007e0cd7941333e841bd"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


class TranslationParseError(ValueError):
    """A TEI translation export cannot be represented without guessing."""


@dataclass(frozen=True)
class TranslationUnit:
    """One source-aligned translation block from the TEI export."""

    sref: str | None
    eref: str | None
    rows: int | None
    subtype: str | None
    label: str | None
    se_label: str | None
    text: str
    text_raw: str
    notes: tuple[str, ...]
    document_key: str | None = None
    source_id: str | None = None
    source_name: str | None = None
    source_sha256: str | None = None
    source_url: str | None = None
    source_license: str | None = None
    source_license_url: str | None = None


@dataclass(frozen=True)
class TranslationRecord:
    """All translation blocks for one qualified ORACC document."""

    subproject: str
    text_id: str
    units: tuple[TranslationUnit, ...]
    source_archive: str | None = None
    source_sha256: str | None = None
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

    def as_document_map(self) -> dict[str, tuple[TranslationUnit, ...]]:
        """Return units keyed by the corpus builder's qualified document key."""
        return {record.key: record.units for record in self.records.values()}


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


def _all_text(element: ET.Element) -> str:
    """Plain text inside a note, including nested markup but not markup tags."""
    return " ".join("".join(element.itertext()).split())


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


def _record_from_root(
    root: ET.Element,
    *,
    subproject: str,
    text_id: str,
    source_archive: str | None = None,
    source_sha256: str | None = None,
    source_url: str | None = None,
) -> TranslationRecord:
    if not text_id:
        raise TranslationParseError(f"{subproject}: missing document id")

    units: list[TranslationUnit] = []
    for element in root.iter():
        if _local(element.tag) != "div3" or element.attrib.get("type") != "tr":
            continue
        sref = _attr_local(element, "sref")
        eref = _attr_local(element, "eref")
        explicit_ref = _attr_local(element, "ref")
        # ORACC's TEI export uses xtr:ref for explicitly single-line blocks
        # (including many `dollar` units). Preserve that source assertion as
        # an inclusive one-line range. Units with no source line assertion
        # remain unaligned and are reported as gaps by the build/audit path.
        if not sref and not eref and explicit_ref:
            sref = eref = explicit_ref
        if bool(sref) != bool(eref):
            raise TranslationParseError(
                f"{subproject}:{text_id}: translation block has a partial line range"
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
            _all_text(child)
            for child in element.iter()
            if _local(child.tag) == "note" and _all_text(child)
        )
        unit_source_id = element.attrib.get(_XML_ID)
        units.append(
            TranslationUnit(
                sref=sref,
                eref=eref,
                rows=rows,
                subtype=element.attrib.get("subtype"),
                label=_attr_local(element, "label"),
                se_label=_attr_local(element, "se_label"),
                text=text,
                text_raw=text_raw,
                notes=notes,
                document_key=f"{subproject}:{text_id}",
                source_id=unit_source_id,
                source_name=source_archive,
                source_sha256=source_sha256,
                source_url=source_url,
                source_license=LICENSE,
                source_license_url=LICENSE_URL,
            )
        )

    return TranslationRecord(
        subproject=subproject,
        text_id=text_id,
        units=tuple(units),
        source_archive=source_archive,
        source_sha256=source_sha256,
    )


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
    return _record_from_root(
        root,
        subproject=subproject,
        text_id=text_id,
        source_archive=source_archive,
    )


def _tei_source_path(root: ET.Element) -> str | None:
    for element in root.iter():
        if _local(element.tag) == "name" and element.attrib.get("type") == "file":
            value = (element.text or "").strip()
            if value:
                return value
    return None


def parse_tei_archive(
    path: Path | str,
    *,
    expected_sha256: str = OFFICIAL_ARCHIVE_SHA256,
) -> TranslationIndex:
    """Parse the pinned official RIAO TEI ZIP without extracting it to disk.

    The digest is checked before XML parsing. A changed archive fails closed so
    source identity and measured translation coverage cannot silently drift.
    """
    path = Path(path)
    try:
        archive_bytes = path.read_bytes()
    except OSError as exc:
        raise TranslationParseError(f"cannot read TEI archive {path}: {exc}") from exc
    source_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if source_sha256 != expected_sha256:
        raise TranslationParseError(
            f"TEI archive SHA-256 mismatch: expected {expected_sha256}, got {source_sha256}"
        )

    archive_name = path.name
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            xml_names = [name for name in archive.namelist() if name.lower().endswith(".xml")]
            if len(xml_names) != 1:
                raise TranslationParseError(
                    f"TEI archive must contain exactly one XML corpus, found {len(xml_names)}"
                )
            records: list[TranslationRecord] = []
            with archive.open(xml_names[0]) as stream:
                for _, root in ET.iterparse(stream, events=("end",)):
                    if _local(root.tag) != "TEI":
                        continue
                    if not any(
                        _local(item.tag) == "div3" and item.attrib.get("type") == "tr"
                        for item in root.iter()
                    ):
                        root.clear()
                        continue
                    source_path = _tei_source_path(root)
                    parts = Path(source_path or "").parts
                    if len(parts) < 3 or not parts[-1].endswith(".xtf"):
                        raise TranslationParseError(
                            f"TEI translation record has invalid source file path {source_path!r}"
                        )
                    subproject = "/".join(parts[:2])
                    text_id = Path(parts[-1]).stem
                    if subproject.split("/", 1)[0] not in {"riao", "rinap"}:
                        raise TranslationParseError(
                            f"unexpected translation subproject {subproject!r}"
                        )
                    records.append(_record_from_root(
                        root,
                        subproject=subproject,
                        text_id=text_id,
                        source_archive=archive_name,
                        source_sha256=source_sha256,
                        source_url=OFFICIAL_ARCHIVE_URL,
                    ))
                    root.clear()
    except (OSError, zipfile.BadZipFile, ET.ParseError) as exc:
        raise TranslationParseError(f"cannot parse TEI archive {path}: {exc}") from exc
    return TranslationIndex.from_records(records)
