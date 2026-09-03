"""Subproject-qualified catalogue metadata join for P-001 M5.

ORACC Q-numbers are not globally unique inside the joined RIAO/RINAP corpus.
In particular, rinap5p1 reuses 140 Q-numbers from rinap5 and some of those are
materially different editions. Catalogue records are therefore keyed by the
same stable identity as :class:`oracc_tf.loader.Edition`: ``subproject:Q``.

Catalogue fields and source-level licence provenance deliberately remain
separate. A missing catalogue member does not delete a document, and a
catalogue record cannot overwrite the licence fields shipped on corpusjson.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from . import loader, paths


class MetadataError(ValueError):
    """Base class for malformed or ambiguous metadata source data."""


class InvalidCatalogue(MetadataError):
    """A catalogue file does not have the ORACC catalogue shape M5 expects."""


class CatalogueProjectMismatch(MetadataError):
    """Catalogue provenance disagrees with the subproject being indexed."""


class DuplicateCatalogueKey(MetadataError):
    """Two catalogue records resolve to the same qualified document key."""


@dataclass(frozen=True)
class MetadataIndex:
    """Catalogue records keyed by ``subproject:Q``."""

    records: Mapping[str, Mapping[str, object]]

    @classmethod
    def empty(cls) -> "MetadataIndex":
        return cls(records={})


@dataclass(frozen=True)
class DocumentMetadata:
    """Metadata attached to one source edition without changing its identity."""

    key: str
    catalogue: Mapping[str, object]
    catalogue_present: bool
    license: str | None
    license_url: str | None
    license_type: str | None


@dataclass(frozen=True)
class MetadataCensus:
    """Whole-corpus M5 join and source-provenance measurements."""

    parseable_documents: int
    populated_documents: int
    catalogue_entries: int
    catalogue_attached_documents: int
    missing_catalogue_documents: int
    populated_with_ruler: int
    multiply_attached_records: int
    source_license_documents: int
    source_license_url_documents: int
    source_license_type_documents: int

    def report(self) -> str:
        ruler_pct = (
            100.0 * self.populated_with_ruler / self.populated_documents
            if self.populated_documents
            else 0.0
        )
        return "\n".join((
            f"parseable documents       : {self.parseable_documents:>8,}",
            f"populated documents       : {self.populated_documents:>8,}",
            f"catalogue entries         : {self.catalogue_entries:>8,}",
            f"catalogue attached docs   : {self.catalogue_attached_documents:>8,}",
            f"missing catalogue docs    : {self.missing_catalogue_documents:>8,}",
            f"populated with ruler      : {self.populated_with_ruler:>8,} ({ruler_pct:.2f}%)",
            f"multiply attached records : {self.multiply_attached_records:>8,}",
            f"source license docs       : {self.source_license_documents:>8,}",
            f"source license-url docs   : {self.source_license_url_documents:>8,}",
            f"source license_type docs  : {self.source_license_type_documents:>8,}",
        ))


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def index_catalogue(
    subproject: str,
    source: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    """Index one parsed ORACC ``catalogue.json`` by qualified document key.

    The catalogue root must identify the exact filesystem subproject. Member
    records are older/mixed provenance: some valid RIAO records state only the
    parent project (for example ``project='riao'`` inside ``riao/ria4``).
    Accept the exact subproject or its parent project, but fail closed on a
    sibling subproject such as ``rinap/rinap5p1`` inside ``rinap/rinap5``.
    The qualified key always comes from the catalogue file being indexed, not
    from the member's less-specific provenance field.
    """
    if source.get("type") != "catalogue":
        raise InvalidCatalogue(
            f"{subproject}: expected type='catalogue', got {source.get('type')!r}"
        )

    root_project = source.get("project")
    if root_project is not None and root_project != subproject:
        raise CatalogueProjectMismatch(
            f"{subproject}: catalogue root project is {root_project!r}"
        )

    members = source.get("members")
    if not isinstance(members, Mapping):
        raise InvalidCatalogue(f"{subproject}: catalogue members is not a mapping")

    parent_project = subproject.split("/", 1)[0]
    allowed_member_projects = {subproject, parent_project}

    indexed: dict[str, Mapping[str, object]] = {}
    for text_id, raw_record in members.items():
        if not isinstance(text_id, str) or not isinstance(raw_record, Mapping):
            raise InvalidCatalogue(
                f"{subproject}: invalid catalogue member {text_id!r}"
            )
        member_project = raw_record.get("project")
        if member_project is not None and member_project not in allowed_member_projects:
            raise CatalogueProjectMismatch(
                f"{subproject}:{text_id}: member project is {member_project!r}"
            )

        key = f"{subproject}:{text_id}"
        if key in indexed:
            raise DuplicateCatalogueKey(key)
        # Keep the member losslessly as a plain mapping. Consumers decide
        # which catalogue features become TF features at the build layer.
        indexed[key] = dict(raw_record)

    return indexed


def load_index(
    data: Path = paths.DATA,
    subprojects: Sequence[str] | None = None,
) -> MetadataIndex:
    """Load all in-scope catalogue files into one qualified-key index."""
    data = Path(data)
    if subprojects is None:
        subprojects = loader.edition_subprojects(data)

    records: dict[str, Mapping[str, object]] = {}
    for subproject in subprojects:
        catalogue_path = data / subproject / "catalogue.json"
        try:
            with open(catalogue_path, encoding="utf-8") as handle:
                source = json.load(handle)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise InvalidCatalogue(f"cannot read {catalogue_path}: {exc}") from exc
        if not isinstance(source, Mapping):
            raise InvalidCatalogue(f"{catalogue_path}: root is not a mapping")

        for key, record in index_catalogue(subproject, source).items():
            if key in records:
                raise DuplicateCatalogueKey(key)
            records[key] = record

    return MetadataIndex(records=records)


def join_edition(edition: loader.Edition, index: MetadataIndex) -> DocumentMetadata:
    """Attach catalogue data and preserve corpusjson licence provenance."""
    record = index.records.get(edition.key)
    catalogue_present = record is not None
    catalogue: Mapping[str, object] = {} if record is None else dict(record)

    doc = edition.doc
    # ORACC exports use ``license-url`` today; accept the underscore spelling
    # as a lossless compatibility fallback without deriving any value.
    license_url = _string_or_none(doc.get("license-url"))
    if license_url is None:
        license_url = _string_or_none(doc.get("license_url"))

    # M5 exposes a stable ``license_type`` feature name, but the raw source
    # spelling may be hyphenated or underscored. Absence remains None: never
    # infer a licence class from prose or a URL.
    license_type = _string_or_none(doc.get("license_type"))
    if license_type is None:
        license_type = _string_or_none(doc.get("license-type"))

    return DocumentMetadata(
        key=edition.key,
        catalogue=catalogue,
        catalogue_present=catalogue_present,
        license=_string_or_none(doc.get("license")),
        license_url=license_url,
        license_type=license_type,
    )


def census(data: Path = paths.DATA) -> MetadataCensus:
    """Measure the M5 catalogue join over every parseable source edition."""
    index = load_index(data)
    usage: dict[str, int] = {}
    parseable_documents = 0
    populated_documents = 0
    attached_documents = 0
    missing_documents = 0
    populated_with_ruler = 0
    source_license_documents = 0
    source_license_url_documents = 0
    source_license_type_documents = 0

    for edition in loader.iter_editions(data, skip_unreadable=True):
        parseable_documents += 1
        joined = join_edition(edition, index)

        if joined.catalogue_present:
            attached_documents += 1
            usage[joined.key] = usage.get(joined.key, 0) + 1
        else:
            missing_documents += 1

        if joined.license is not None:
            source_license_documents += 1
        if joined.license_url is not None:
            source_license_url_documents += 1
        if joined.license_type is not None:
            source_license_type_documents += 1

        if edition.populated:
            populated_documents += 1
            ruler = joined.catalogue.get("ruler")
            if isinstance(ruler, str) and ruler:
                populated_with_ruler += 1

    return MetadataCensus(
        parseable_documents=parseable_documents,
        populated_documents=populated_documents,
        catalogue_entries=len(index.records),
        catalogue_attached_documents=attached_documents,
        missing_catalogue_documents=missing_documents,
        populated_with_ruler=populated_with_ruler,
        multiply_attached_records=sum(count > 1 for count in usage.values()),
        source_license_documents=source_license_documents,
        source_license_url_documents=source_license_url_documents,
        source_license_type_documents=source_license_type_documents,
    )
