"""ORACC TEI translation parsing for P-001 M9.

The parser is deliberately acquisition-agnostic: callers supply TEI bytes/text
and the already-qualified ORACC document key. This avoids guessing subproject
identity from Q-numbers (which are not globally unique in RINAP) and keeps the
ordinary corpus build network-independent.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path


XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_WS = re.compile(r"\s+")
_SHA256 = re.compile(r"[0-9a-f]{64}")


class TranslationSourceError(ValueError):
    """The TEI translation source cannot be mapped without inventing semantics."""


@dataclass(frozen=True)
class TranslationNote:
    """One serialized XTR/TEI note explicitly linked from a translation unit."""

    source_id: str
    text: str
    text_raw: str
    source_name: str | None = None
    source_sha256: str | None = None
    source_url: str | None = None
    source_license: str | None = None
    source_license_url: str | None = None


@dataclass(frozen=True)
class TranslationUnit:
    """One source translation unit aligned to an inclusive ORACC line range."""

    document_key: str
    text_id: str
    source_id: str
    subtype: str | None
    sref: str
    eref: str
    rows: int | None
    label: str | None
    se_label: str | None
    text: str
    text_raw: str
    source_name: str | None = None
    source_sha256: str | None = None
    source_url: str | None = None
    source_license: str | None = None
    source_license_url: str | None = None
    notes: tuple[TranslationNote, ...] = ()


@dataclass(frozen=True)
class TranslationArchive:
    """One verified TEI archive and its qualified translation-unit index."""

    source_name: str
    source_sha256: str
    units_by_document: Mapping[str, tuple[TranslationUnit, ...]]
    source_url: str | None = None
    source_license: str | None = None
    source_license_url: str | None = None

    @property
    def translation_units(self) -> int:
        return sum(len(units) for units in self.units_by_document.values())


def _local_name(name: str) -> str:
    return name.rsplit("}", 1)[-1] if "}" in name else name


def _attribute(element: ET.Element, local_name: str) -> str | None:
    """Read a namespaced or unnamespaced attribute by local name."""
    for name, value in element.attrib.items():
        if _local_name(name) == local_name:
            return value
    return None


def _normalise_plain_text(element: ET.Element) -> str:
    return _WS.sub(" ", "".join(element.itertext())).strip()


def _inner_xml(element: ET.Element) -> str:
    """Serialize inner XML deterministically while preserving editorial markup."""
    pieces = [element.text or ""]
    for child in element:
        pieces.append(ET.tostring(child, encoding="unicode", short_empty_elements=True))
    return "".join(pieces).strip()


def _range_text_id(ref: str, *, field: str) -> str:
    if "." not in ref:
        raise TranslationSourceError(
            f"translation {field} lacks a text-qualified line ref: {ref!r}"
        )
    text_id, _ = ref.split(".", 1)
    if not text_id:
        raise TranslationSourceError(f"translation {field} has an empty text id")
    return text_id


def _qualified_text_id(document_key: str) -> str:
    if ":" not in document_key:
        raise TranslationSourceError(
            "translation document identity must be qualified as subproject:Q"
        )
    subproject, text_id = document_key.rsplit(":", 1)
    if not subproject or not text_id:
        raise TranslationSourceError(
            "translation document identity must be qualified as subproject:Q"
        )
    return text_id


def _validate_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.lower()
    if not _SHA256.fullmatch(value):
        raise TranslationSourceError("translation source_sha256 must be 64 hex digits")
    return value


def qualified_key_map(
    editions: Iterable[object],
    *,
    excluded_subprojects: Iterable[str] = (),
) -> dict[str, str]:
    """Map a TEI Q-number to one source-qualified ORACC edition key.

    Translation archives align by Q-number, while the joined corpus does not:
    RINAP5P1 deliberately reuses Q-numbers from RINAP5. Any remaining
    ambiguity therefore fails closed. A known source gap may be declared by
    excluding the subproject that is absent from the translation archive.
    """
    excluded = set(excluded_subprojects)
    result: dict[str, str] = {}
    for edition in editions:
        subproject = getattr(edition, "subproject", None)
        text_id = getattr(edition, "text_id", None)
        key = getattr(edition, "key", None)
        if not isinstance(subproject, str) or not isinstance(text_id, str) or not isinstance(key, str):
            raise TranslationSourceError("edition lacks subproject/text_id/key identity")
        if subproject in excluded:
            continue
        previous = result.get(text_id)
        if previous is not None and previous != key:
            raise TranslationSourceError(
                f"ambiguous translation text id {text_id}: {previous!r} vs {key!r}"
            )
        result[text_id] = key
    return result


def parse_tei_text(
    xml_text: str,
    *,
    document_key: str,
    source_name: str | None = None,
    source_sha256: str | None = None,
    source_url: str | None = None,
    source_license: str | None = None,
    source_license_url: str | None = None,
) -> tuple[TranslationUnit, ...]:
    """Parse translation units from one TEI document.

    ``document_key`` is mandatory and qualified because the ORACC source corpus
    contains Q-number collisions across subprojects. Only ``div3`` elements
    with ``type=\"tr\"`` are materialised. Alignment refs are source facts and
    therefore mandatory; malformed or cross-document ranges fail explicitly.

    Translation notes are attached only through serialized ``notelink`` refs.
    Positional adjacency is deliberately not re-inferred, even though ATF input
    supports automatic note association, because the serialized XML is the
    provenance-bearing source consumed here.
    """
    text_id = _qualified_text_id(document_key)
    source_sha256 = _validate_sha256(source_sha256)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise TranslationSourceError(f"invalid TEI XML: {exc}") from exc

    note_elements: dict[str, ET.Element] = {}
    for element in root.iter():
        if _local_name(element.tag) != "div" or element.get("class") != "note":
            continue
        note_id = element.get(XML_ID)
        if not note_id:
            raise TranslationSourceError("translation note is missing xml:id")
        if note_id in note_elements:
            raise TranslationSourceError(f"duplicate translation note id {note_id!r}")
        note_elements[note_id] = element

    units: list[TranslationUnit] = []
    for element in root.iter():
        if _local_name(element.tag) != "div3" or element.get("type") != "tr":
            continue

        source_id = element.get(XML_ID)
        if not source_id:
            raise TranslationSourceError("translation div3 is missing xml:id")

        sref = _attribute(element, "sref")
        eref = _attribute(element, "eref")
        if not sref:
            raise TranslationSourceError(f"translation {source_id} is missing sref")
        if not eref:
            raise TranslationSourceError(f"translation {source_id} is missing eref")

        start_text = _range_text_id(sref, field="sref")
        end_text = _range_text_id(eref, field="eref")
        if start_text != end_text:
            raise TranslationSourceError(
                f"translation {source_id} range endpoints must belong to the same text"
            )
        if start_text != text_id:
            raise TranslationSourceError(
                f"translation {source_id} range text {start_text!r} does not match "
                f"qualified document {document_key!r}"
            )

        rows_raw = _attribute(element, "rows")
        if rows_raw is None or rows_raw == "":
            rows = None
        else:
            try:
                rows = int(rows_raw)
            except ValueError as exc:
                raise TranslationSourceError(
                    f"translation {source_id} has non-integer rows={rows_raw!r}"
                ) from exc
            if rows < 1:
                raise TranslationSourceError(
                    f"translation {source_id} has invalid rows={rows}"
                )

        note_refs: list[str] = []
        for descendant in element.iter():
            if descendant.get("class") != "notelink":
                continue
            note_ref = _attribute(descendant, "noteref")
            if not note_ref:
                raise TranslationSourceError(
                    f"translation {source_id} has a notelink without noteref"
                )
            if note_ref not in note_elements:
                raise TranslationSourceError(
                    f"translation {source_id} references missing note {note_ref!r}"
                )
            if note_ref not in note_refs:
                note_refs.append(note_ref)

        notes = tuple(
            TranslationNote(
                source_id=note_ref,
                text=_normalise_plain_text(note_elements[note_ref]),
                text_raw=_inner_xml(note_elements[note_ref]),
                source_name=source_name,
                source_sha256=source_sha256,
                source_url=source_url,
                source_license=source_license,
                source_license_url=source_license_url,
            )
            for note_ref in note_refs
        )

        units.append(
            TranslationUnit(
                document_key=document_key,
                text_id=text_id,
                source_id=source_id,
                subtype=element.get("subtype"),
                sref=sref,
                eref=eref,
                rows=rows,
                label=_attribute(element, "label") or element.get("n"),
                se_label=_attribute(element, "se_label"),
                text=_normalise_plain_text(element),
                text_raw=_inner_xml(element),
                source_name=source_name,
                source_sha256=source_sha256,
                source_url=source_url,
                source_license=source_license,
                source_license_url=source_license_url,
                notes=notes,
            )
        )

    return tuple(units)


def _tei_text_id(element: ET.Element) -> str | None:
    """Return the single text id referenced by translation units in a TEI node."""
    text_ids: set[str] = set()
    for descendant in element.iter():
        if _local_name(descendant.tag) != "div3" or descendant.get("type") != "tr":
            continue
        sref = _attribute(descendant, "sref")
        if not sref:
            source_id = descendant.get(XML_ID) or "<unknown>"
            raise TranslationSourceError(f"translation {source_id} is missing sref")
        text_ids.add(_range_text_id(sref, field="sref"))
    if not text_ids:
        return None
    if len(text_ids) != 1:
        raise TranslationSourceError(
            f"one TEI document references multiple translation texts: {sorted(text_ids)!r}"
        )
    return next(iter(text_ids))


def load_tei_zip(
    path: Path | str,
    *,
    document_keys: Mapping[str, str],
    source_url: str | None = None,
    source_license: str | None = None,
    source_license_url: str | None = None,
) -> TranslationArchive:
    """Parse a local TEI ZIP without extracting it or guessing corpus identity."""
    archive_path = Path(path)
    digest = hashlib.sha256()
    try:
        with archive_path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise TranslationSourceError(f"cannot read translation archive {archive_path}: {exc}") from exc
    source_sha256 = digest.hexdigest()

    units_by_document: dict[str, list[TranslationUnit]] = {}
    seen_source_ids: dict[str, set[str]] = {}
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = sorted(
                (
                    info
                    for info in archive.infolist()
                    if not info.is_dir() and Path(info.filename).suffix.lower() in {".xml", ".tei"}
                ),
                key=lambda info: info.filename,
            )
            if not infos:
                raise TranslationSourceError(f"translation archive {archive_path} contains no TEI/XML files")

            for info in infos:
                try:
                    with archive.open(info) as handle:
                        root = ET.parse(handle).getroot()
                except (ET.ParseError, OSError) as exc:
                    raise TranslationSourceError(
                        f"cannot parse translation XML {info.filename!r}: {exc}"
                    ) from exc

                candidates = (
                    [root]
                    if _local_name(root.tag) == "TEI"
                    else [node for node in root.iter() if _local_name(node.tag) == "TEI"]
                )
                for tei in candidates:
                    text_id = _tei_text_id(tei)
                    if text_id is None:
                        continue
                    document_key = document_keys.get(text_id)
                    if document_key is None:
                        raise TranslationSourceError(
                            f"unmapped translation text {text_id} in {info.filename!r}"
                        )
                    units = parse_tei_text(
                        ET.tostring(tei, encoding="unicode"),
                        document_key=document_key,
                        source_name=archive_path.name,
                        source_sha256=source_sha256,
                        source_url=source_url,
                        source_license=source_license,
                        source_license_url=source_license_url,
                    )
                    source_ids = seen_source_ids.setdefault(document_key, set())
                    duplicate = next((unit.source_id for unit in units if unit.source_id in source_ids), None)
                    if duplicate is not None:
                        raise TranslationSourceError(
                            f"duplicate translation unit {duplicate!r} for {document_key}"
                        )
                    source_ids.update(unit.source_id for unit in units)
                    units_by_document.setdefault(document_key, []).extend(units)
    except zipfile.BadZipFile as exc:
        raise TranslationSourceError(f"invalid translation ZIP {archive_path}: {exc}") from exc

    frozen = {
        key: tuple(units)
        for key, units in sorted(units_by_document.items())
    }
    return TranslationArchive(
        source_name=archive_path.name,
        source_sha256=source_sha256,
        units_by_document=frozen,
        source_url=source_url,
        source_license=source_license,
        source_license_url=source_license_url,
    )
