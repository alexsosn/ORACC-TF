"""Deterministic discovery and content-state selection for ORACC TEI exports.

This module deliberately stops before network acquisition and TEI parsing.  It
turns trusted download-listing documents and verified ZIP bytes into a stable
content identity.  Transport integrity, safe extraction, and translation
semantics remain separate concerns owned by the upstream/download and M9
layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from html.parser import HTMLParser
from io import BytesIO
import posixpath
import re
from urllib.parse import urljoin, urlsplit
import zipfile


_CANDIDATE_RE = re.compile(
    r"^(?P<prefix>[A-Za-z0-9][A-Za-z0-9._-]*)-teiCorpus-(?P<date>[0-9]{8})\.zip$"
)
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ZIP_LOCAL_FILE_MAGIC = b"PK\x03\x04"


class TeiDiscoveryError(ValueError):
    """A TEI source cannot be selected without weakening the discovery rules."""


class TeiListingUnavailable(TeiDiscoveryError):
    """A required download listing is unavailable."""


class AmbiguousTeiSource(TeiDiscoveryError):
    """The newest candidate cohort resolves to more than one content state."""


@dataclass(frozen=True, order=True)
class TeiCandidate:
    """One dated TEI archive link observed in an ORACC download listing."""

    published_date: date
    name: str
    url: str
    listing_url: str
    source_prefix: str


@dataclass(frozen=True)
class VerifiedTeiCandidate:
    """A candidate whose exact bytes have been verified by the acquisition boundary."""

    candidate: TeiCandidate
    sha256: str
    bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.candidate, TeiCandidate):
            raise TeiDiscoveryError("verified TEI candidate lacks a valid candidate identity")
        if not isinstance(self.sha256, str):
            raise TeiDiscoveryError("verified TEI candidate sha256 must be 64 hex digits")
        digest = self.sha256.lower()
        if not _SHA256_RE.fullmatch(digest):
            raise TeiDiscoveryError("verified TEI candidate sha256 must be 64 hex digits")
        if isinstance(self.bytes, bool) or not isinstance(self.bytes, int) or self.bytes <= 0:
            raise TeiDiscoveryError("verified TEI candidate byte length must be a positive integer")
        object.__setattr__(self, "sha256", digest)


@dataclass(frozen=True)
class TeiSourceState:
    """Accepted content identity for one logical TEI source."""

    logical_source: str
    sha256: str
    bytes: int
    published_date: date
    aliases: tuple[TeiCandidate, ...]


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value is not None:
                self.hrefs.append(value)
                return


def _candidate_from_href(href: str, listing_url: str) -> TeiCandidate | None:
    href_path = urlsplit(href).path
    name = posixpath.basename(href_path)

    # Unrelated files are not observations for this source.  A ZIP that looks
    # like a TEI corpus export, however, must obey the grammar exactly; silently
    # ignoring malformed lookalikes would let publication drift evade review.
    candidate_like = "teiCorpus" in name and name.lower().endswith(".zip")
    match = _CANDIDATE_RE.fullmatch(name)
    if match is None:
        if candidate_like:
            raise TeiDiscoveryError(f"malformed TEI archive candidate {name!r}")
        return None

    raw_date = match.group("date")
    try:
        published_date = date(
            int(raw_date[0:4]),
            int(raw_date[4:6]),
            int(raw_date[6:8]),
        )
    except ValueError as exc:
        raise TeiDiscoveryError(f"invalid TEI archive publication date in {name!r}") from exc

    return TeiCandidate(
        published_date=published_date,
        name=name,
        url=urljoin(listing_url, href),
        listing_url=listing_url,
        source_prefix=match.group("prefix"),
    )


def parse_download_listing(html: str | None, listing_url: str) -> tuple[TeiCandidate, ...]:
    """Parse dated TEI ZIP anchors deterministically from one listing document.

    The caller is responsible for acquiring ``html`` with the required transport
    policy.  ``None`` represents an unavailable listing and fails closed.
    Duplicate links are idempotent; source order never affects the result.
    """
    if html is None:
        raise TeiListingUnavailable(f"TEI download listing unavailable: {listing_url}")
    if not isinstance(html, str):
        raise TeiDiscoveryError("TEI download listing must be text")
    if not isinstance(listing_url, str) or not listing_url:
        raise TeiDiscoveryError("TEI listing URL must be a non-empty string")

    parser = _HrefParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # HTMLParser is permissive, but preserve a typed boundary.
        raise TeiDiscoveryError(f"cannot parse TEI download listing {listing_url!r}") from exc

    unique: dict[str, TeiCandidate] = {}
    for href in parser.hrefs:
        candidate = _candidate_from_href(href, listing_url)
        if candidate is None:
            continue
        previous = unique.get(candidate.url)
        if previous is not None and previous != candidate:
            raise TeiDiscoveryError(f"conflicting TEI candidate link {candidate.url!r}")
        unique[candidate.url] = candidate

    return tuple(sorted(unique.values()))


def newest_candidate_cohort(
    candidates: tuple[TeiCandidate, ...] | list[TeiCandidate] | object,
) -> tuple[TeiCandidate, ...]:
    """Return every candidate carrying the maximum publication date."""
    try:
        items = tuple(candidates)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TeiDiscoveryError("TEI candidate collection is not iterable") from exc
    if not items:
        raise TeiDiscoveryError("no dated TEI archive candidates were discovered")
    if any(not isinstance(item, TeiCandidate) for item in items):
        raise TeiDiscoveryError("TEI candidate collection contains an invalid item")

    newest_date = max(item.published_date for item in items)
    return tuple(sorted(item for item in items if item.published_date == newest_date))


def verify_candidate_bytes(candidate: TeiCandidate, payload: bytes) -> VerifiedTeiCandidate:
    """Validate that supplied bytes are a readable ZIP and record their identity.

    No extraction or member decompression occurs here.  This is a narrow type
    boundary preventing an HTTP soft-404 or other non-ZIP body from becoming a
    source state; stronger remote-download integrity and extraction checks
    remain owned by PH3.
    """
    if not isinstance(candidate, TeiCandidate):
        raise TeiDiscoveryError("verified payload lacks a valid TEI candidate")
    if not isinstance(payload, bytes):
        raise TeiDiscoveryError("TEI candidate payload must be bytes")
    if not payload:
        raise TeiDiscoveryError("TEI candidate payload is empty")
    if not payload.startswith(_ZIP_LOCAL_FILE_MAGIC):
        raise TeiDiscoveryError(
            f"TEI candidate {candidate.name!r} does not begin with ZIP local-file magic"
        )

    buffer = BytesIO(payload)
    if not zipfile.is_zipfile(buffer):
        raise TeiDiscoveryError(f"TEI candidate {candidate.name!r} is not a ZIP archive")
    try:
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            if not archive.infolist():
                raise TeiDiscoveryError(
                    f"TEI candidate {candidate.name!r} is an empty ZIP archive"
                )
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise TeiDiscoveryError(
            f"TEI candidate {candidate.name!r} is not a readable ZIP archive"
        ) from exc

    return VerifiedTeiCandidate(
        candidate=candidate,
        sha256=hashlib.sha256(payload).hexdigest(),
        bytes=len(payload),
    )


def resolve_verified_cohort(
    logical_source: str,
    cohort: tuple[TeiCandidate, ...] | list[TeiCandidate],
    verified: tuple[VerifiedTeiCandidate, ...] | list[VerifiedTeiCandidate],
) -> TeiSourceState:
    """Resolve one newest-date cohort into exactly one content state."""
    if not isinstance(logical_source, str) or not logical_source:
        raise TeiDiscoveryError("logical TEI source id must be a non-empty string")

    cohort_items = tuple(cohort)
    if not cohort_items:
        raise TeiDiscoveryError("cannot resolve an empty TEI candidate cohort")
    if any(not isinstance(item, TeiCandidate) for item in cohort_items):
        raise TeiDiscoveryError("TEI cohort contains an invalid candidate")
    dates = {item.published_date for item in cohort_items}
    if len(dates) != 1:
        raise TeiDiscoveryError("verified TEI cohort must contain one publication date")
    if len(set(cohort_items)) != len(cohort_items):
        raise TeiDiscoveryError("verified TEI cohort contains duplicate candidates")

    verified_items = tuple(verified)
    by_candidate: dict[TeiCandidate, VerifiedTeiCandidate] = {}
    for item in verified_items:
        if not isinstance(item, VerifiedTeiCandidate):
            raise TeiDiscoveryError("TEI verification collection contains an invalid item")
        if item.candidate in by_candidate:
            raise TeiDiscoveryError(
                f"duplicate verification for TEI candidate {item.candidate.name!r}"
            )
        by_candidate[item.candidate] = item

    cohort_set = set(cohort_items)
    if set(by_candidate) != cohort_set:
        missing = sorted(item.name for item in cohort_set - set(by_candidate))
        extra = sorted(item.name for item in set(by_candidate) - cohort_set)
        detail = []
        if missing:
            detail.append(f"missing={missing!r}")
        if extra:
            detail.append(f"unexpected={extra!r}")
        raise TeiDiscoveryError(
            "TEI newest cohort is not completely verified"
            + (f" ({', '.join(detail)})" if detail else "")
        )

    digests = {item.sha256 for item in verified_items}
    sizes = {item.bytes for item in verified_items}
    if len(digests) != 1 or len(sizes) != 1:
        raise AmbiguousTeiSource(
            "newest TEI candidate cohort resolves to different archive bytes"
        )

    aliases = tuple(sorted(cohort_items))
    return TeiSourceState(
        logical_source=logical_source,
        sha256=next(iter(digests)),
        bytes=next(iter(sizes)),
        published_date=next(iter(dates)),
        aliases=aliases,
    )


def compare_source_state(previous: TeiSourceState, current: TeiSourceState) -> str:
    """Classify a TEI source transition by content identity first."""
    if not isinstance(previous, TeiSourceState) or not isinstance(current, TeiSourceState):
        raise TeiDiscoveryError("TEI source comparison requires source-state records")
    if previous.logical_source != current.logical_source:
        raise TeiDiscoveryError("cannot compare different logical TEI sources")
    if previous.sha256 != current.sha256 or previous.bytes != current.bytes:
        return "changed"
    if previous == current:
        return "unchanged"
    return "metadata-only"
