"""Fail-closed, network-independent upstream discovery/change detection.

This module models inventory parsing, HTTP response interpretation, retry policy,
active-dataset selection, minimal archive type validation, and deterministic
content-state reconciliation. It deliberately does not perform live HTTP I/O or
inspect/extract ZIP members.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html.parser import HTMLParser
from io import BytesIO
import json
import re
import tomllib
from typing import Callable, Iterable, Mapping, TypeVar
from urllib.parse import urljoin, urlsplit
import posixpath
import zipfile


_ARCHIVE_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\.zip$")
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ZIP_MAGIC = b"PK\x03\x04"
T = TypeVar("T")


class UpstreamDiscoveryError(ValueError):
    """Base error for unsafe or ambiguous upstream observations."""


class UpstreamInventoryError(UpstreamDiscoveryError):
    """Inventory content is malformed or incomplete."""


class UpstreamUnavailable(UpstreamDiscoveryError):
    """A transient network/server observation prevents classification."""


class UpstreamProtocolError(UpstreamDiscoveryError):
    """An HTTP/protocol observation is invalid or unresolved."""


@dataclass(frozen=True, order=True)
class ArchiveEntry:
    name: str
    url: str


@dataclass(frozen=True)
class ProjectInventory:
    public: tuple[str, ...]


@dataclass(frozen=True)
class HeadMetadata:
    etag: str | None
    content_length: int | None
    last_modified: str | None


@dataclass(frozen=True)
class ProbeDecision:
    action: str
    requires_download: bool


@dataclass(frozen=True)
class ArchiveFingerprint:
    name: str
    sha256: str
    bytes: int
    etag: str | None
    last_modified: str | None

    def __post_init__(self) -> None:
        _validate_identity(self.name, self.sha256, self.bytes)


@dataclass(frozen=True)
class DownloadedArchive:
    name: str
    sha256: str
    bytes: int
    etag: str | None
    last_modified: str | None

    def __post_init__(self) -> None:
        _validate_identity(self.name, self.sha256, self.bytes)


@dataclass(frozen=True)
class ArchiveChange:
    kind: str
    requires_rebuild: bool
    name: str
    sha256: str
    bytes: int
    etag: str | None
    last_modified: str | None


class _HrefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for key, value in attrs:
            if key.lower() == "href" and value is not None:
                self.hrefs.append(value)
                return


def _validate_identity(name: str, digest: str, size: int) -> None:
    if not isinstance(name, str) or not name:
        raise UpstreamDiscoveryError("archive name must be a non-empty string")
    if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
        raise UpstreamDiscoveryError("archive sha256 must be 64 hex digits")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise UpstreamDiscoveryError("archive byte length must be a positive integer")


def parse_archive_inventory(html: str, index_url: str) -> tuple[ArchiveEntry, ...]:
    if not isinstance(html, str):
        raise UpstreamInventoryError("archive inventory must be text")
    if not isinstance(index_url, str) or not index_url:
        raise UpstreamInventoryError("archive inventory URL must be non-empty")
    parser = _HrefParser()
    parser.feed(html)
    parser.close()
    unique: dict[str, ArchiveEntry] = {}
    for href in parser.hrefs:
        name = posixpath.basename(urlsplit(href).path)
        match = _ARCHIVE_RE.fullmatch(name)
        if match is None:
            continue
        entry = ArchiveEntry(match.group("name"), urljoin(index_url, href))
        previous = unique.get(entry.url)
        if previous is not None and previous != entry:
            raise UpstreamInventoryError(f"conflicting archive inventory entry {entry.url!r}")
        unique[entry.url] = entry
    return tuple(sorted(unique.values()))


def parse_project_inventory(payload: str) -> ProjectInventory:
    if not isinstance(payload, str):
        raise UpstreamInventoryError("project inventory must be text")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise UpstreamInventoryError("project inventory is not valid JSON") from exc
    if not isinstance(value, Mapping) or value.get("type") != "projects":
        raise UpstreamInventoryError("project inventory type must be 'projects'")
    public = value.get("public")
    if not isinstance(public, list) or any(not isinstance(item, str) or not item for item in public):
        raise UpstreamInventoryError("project inventory public must be a list of non-empty strings")
    if len(set(public)) != len(public):
        raise UpstreamInventoryError("project inventory contains duplicate public paths")
    return ProjectInventory(public=tuple(sorted(public)))


def tracked_archives_from_datasets(payload: str) -> tuple[str, ...]:
    if not isinstance(payload, str):
        raise UpstreamInventoryError("datasets manifest must be text")
    try:
        raw = tomllib.loads(payload)
    except tomllib.TOMLDecodeError as exc:
        raise UpstreamInventoryError("datasets manifest is invalid TOML") from exc
    names: list[str] = []
    for dataset in raw.values():
        if not isinstance(dataset, Mapping):
            raise UpstreamInventoryError("dataset entry must be a table")
        archives = dataset.get("archives", [])
        if not isinstance(archives, list) or any(not isinstance(item, str) or not item for item in archives):
            raise UpstreamInventoryError("dataset archives must be a list of non-empty strings")
        names.extend(archives)
    if len(set(names)) != len(names):
        raise UpstreamInventoryError("tracked archive appears in more than one active dataset")
    return tuple(names)


def active_inventory_entries(
    inventory: Iterable[ArchiveEntry], tracked: Iterable[str]
) -> tuple[ArchiveEntry, ...]:
    by_name: dict[str, ArchiveEntry] = {}
    for item in inventory:
        if not isinstance(item, ArchiveEntry):
            raise UpstreamInventoryError("archive inventory contains an invalid entry")
        if item.name in by_name and by_name[item.name] != item:
            raise UpstreamInventoryError(f"multiple inventory URLs for archive {item.name!r}")
        by_name[item.name] = item
    tracked_items = tuple(tracked)
    missing = [name for name in tracked_items if name not in by_name]
    if missing:
        raise UpstreamInventoryError(
            "tracked archives missing from inventory: " + ", ".join(sorted(missing))
        )
    return tuple(by_name[name] for name in tracked_items)


def _casefold_headers(headers: Mapping[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in headers.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise UpstreamProtocolError("HTTP headers must be strings")
        folded = key.lower()
        if folded in result and result[folded] != value:
            raise UpstreamProtocolError(f"conflicting HTTP header {key!r}")
        result[folded] = value
    return result


def head_from_response(status: int, headers: Mapping[str, str]) -> HeadMetadata:
    if not isinstance(status, int):
        raise UpstreamProtocolError("HTTP status must be an integer")
    if 500 <= status <= 599:
        raise UpstreamUnavailable(f"upstream server returned HTTP {status}")
    if status != 200:
        raise UpstreamProtocolError(f"unexpected unresolved HTTP status {status}")
    normalized = _casefold_headers(headers)
    raw_length = normalized.get("content-length")
    content_length: int | None = None
    if raw_length is not None:
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise UpstreamProtocolError("Content-Length must be an integer") from exc
        if content_length < 0:
            raise UpstreamProtocolError("Content-Length must be non-negative")
    return HeadMetadata(
        etag=normalized.get("etag"),
        content_length=content_length,
        last_modified=normalized.get("last-modified"),
    )


def decide_probe(locked: ArchiveFingerprint, current: HeadMetadata) -> ProbeDecision:
    if not isinstance(locked, ArchiveFingerprint) or not isinstance(current, HeadMetadata):
        raise UpstreamDiscoveryError("probe decision requires typed lock and HEAD metadata")
    if (
        isinstance(locked.etag, str)
        and bool(locked.etag.strip())
        and isinstance(current.etag, str)
        and bool(current.etag.strip())
        and current.content_length is not None
        and locked.etag == current.etag
        and locked.bytes == current.content_length
    ):
        return ProbeDecision("unchanged", False)
    return ProbeDecision("download-required", True)


def with_retries(
    operation: Callable[[], T],
    *,
    attempts: int,
    sleep: Callable[[float], object],
) -> T:
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        raise ValueError("attempts must be a positive integer")
    for attempt in range(attempts):
        try:
            return operation()
        except UpstreamUnavailable:
            if attempt + 1 >= attempts:
                raise
            sleep(float(2**attempt))
    raise AssertionError("unreachable")


def verify_downloaded_archive(
    entry: ArchiveEntry,
    payload: bytes,
    current: HeadMetadata,
) -> DownloadedArchive:
    if not isinstance(entry, ArchiveEntry) or not isinstance(current, HeadMetadata):
        raise UpstreamDiscoveryError("download verification requires typed entry and HEAD metadata")
    if not isinstance(payload, bytes) or not payload:
        raise UpstreamDiscoveryError("downloaded archive payload must be non-empty bytes")
    if current.content_length is not None and current.content_length != len(payload):
        raise UpstreamProtocolError(
            f"downloaded archive {entry.name!r} length disagrees with HEAD Content-Length"
        )
    if not payload.startswith(_ZIP_MAGIC) or not zipfile.is_zipfile(BytesIO(payload)):
        raise UpstreamDiscoveryError(f"downloaded archive {entry.name!r} is not a ZIP payload")
    return DownloadedArchive(
        name=entry.name,
        sha256=sha256(payload).hexdigest(),
        bytes=len(payload),
        etag=current.etag,
        last_modified=current.last_modified,
    )


def reconcile_download(
    locked: ArchiveFingerprint,
    downloaded: DownloadedArchive,
) -> ArchiveChange:
    if not isinstance(locked, ArchiveFingerprint) or not isinstance(downloaded, DownloadedArchive):
        raise UpstreamDiscoveryError("download reconciliation requires typed archive states")
    if locked.name != downloaded.name:
        raise UpstreamDiscoveryError("cannot reconcile different archive names")
    if locked.sha256 == downloaded.sha256:
        if locked.bytes != downloaded.bytes:
            raise UpstreamDiscoveryError("same archive hash has inconsistent byte length")
        return ArchiveChange(
            kind="metadata-only",
            requires_rebuild=False,
            name=downloaded.name,
            sha256=downloaded.sha256.lower(),
            bytes=downloaded.bytes,
            etag=downloaded.etag,
            last_modified=downloaded.last_modified,
        )
    return ArchiveChange(
        kind="changed",
        requires_rebuild=True,
        name=downloaded.name,
        sha256=downloaded.sha256.lower(),
        bytes=downloaded.bytes,
        etag=downloaded.etag,
        last_modified=downloaded.last_modified,
    )
