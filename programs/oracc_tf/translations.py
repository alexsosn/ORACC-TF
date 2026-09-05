"""ORACC TEI translation parsing for P-001 M9.

The parser is deliberately acquisition-agnostic: callers supply TEI bytes/text
and the already-qualified ORACC document key.  This avoids guessing subproject
identity from Q-numbers (which are not globally unique in RINAP) and keeps the
ordinary corpus build network-independent.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass


XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_WS = re.compile(r"\s+")


class TranslationSourceError(ValueError):
    """The TEI translation source cannot be mapped without inventing semantics."""


@dataclass(frozen=True)
class TranslationUnit:
    """One source translation unit aligned to an inclusive ORACC line range."""

    document_key: str
    text_id: str
    source_id: str
    subtype: str
    sref: str
    eref: str
    rows: int | None
    label: str | None
    se_label: str | None
    text: str
    text_raw: str
    source_name: str | None = None


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
        raise TranslationSourceError(f"translation {field} lacks a text-qualified line ref: {ref!r}")
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


def parse_tei_text(
    xml_text: str,
    *,
    document_key: str,
    source_name: str | None = None,
) -> tuple[TranslationUnit, ...]:
    """Parse translation units from one TEI document.

    ``document_key`` is mandatory and qualified because the ORACC source corpus
    contains Q-number collisions across subprojects.  Only ``div3`` elements
    with ``type=\"tr\"`` are materialised.  Alignment refs are source facts and
    therefore mandatory; malformed or cross-document ranges fail explicitly.
    """
    text_id = _qualified_text_id(document_key)
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise TranslationSourceError(f"invalid TEI XML: {exc}") from exc

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

        units.append(
            TranslationUnit(
                document_key=document_key,
                text_id=text_id,
                source_id=source_id,
                subtype=element.get("subtype") or "tr",
                sref=sref,
                eref=eref,
                rows=rows,
                label=_attribute(element, "label") or element.get("n"),
                se_label=_attribute(element, "se_label"),
                text=_normalise_plain_text(element),
                text_raw=_inner_xml(element),
                source_name=source_name,
            )
        )

    return tuple(units)
