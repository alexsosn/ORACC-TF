"""Upstream policy and deterministic lock model for P-002 Phase 1."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import re
import tomllib


_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ORACC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_HTTP_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class UpstreamModelError(ValueError):
    """Invalid or ambiguous upstream configuration/lock input."""


@dataclass(frozen=True)
class UpstreamConfig:
    index: str
    projects: str
    user_agent: str
    poll_cron: str
    inventory_cron: str
    auto_publish: bool
    max_parallel_fetch: int


def load_config(path: Path) -> UpstreamConfig:
    """Load the strict hand-edited upstream policy."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise UpstreamModelError(f"cannot load upstream config {path}: {exc}") from exc
    if set(raw) != {"source", "policy"}:
        raise UpstreamModelError("upstream config must contain exactly source and policy tables")
    source = raw.get("source")
    policy = raw.get("policy")
    if not isinstance(source, Mapping) or set(source) != {"index", "projects", "user_agent"}:
        raise UpstreamModelError("source table has missing or unknown fields")
    if not isinstance(policy, Mapping) or set(policy) != {
        "poll_cron", "inventory_cron", "auto_publish", "max_parallel_fetch"
    }:
        raise UpstreamModelError("policy table has missing or unknown fields")
    strings = [source["index"], source["projects"], source["user_agent"], policy["poll_cron"], policy["inventory_cron"]]
    if not all(isinstance(value, str) and value for value in strings):
        raise UpstreamModelError("upstream source and cadence values must be non-empty strings")
    if not isinstance(policy["auto_publish"], bool):
        raise UpstreamModelError("auto_publish must be boolean")
    parallel = policy["max_parallel_fetch"]
    if not isinstance(parallel, int) or isinstance(parallel, bool) or parallel != 1:
        raise UpstreamModelError("max_parallel_fetch must be exactly 1")
    return UpstreamConfig(
        index=source["index"], projects=source["projects"], user_agent=source["user_agent"],
        poll_cron=policy["poll_cron"], inventory_cron=policy["inventory_cron"],
        auto_publish=policy["auto_publish"], max_parallel_fetch=parallel,
    )


def _sha(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise UpstreamModelError(f"invalid SHA-256 for {label}: {value!r}")


def text_ids_digest(text_hashes: Mapping[str, str]) -> str:
    """Hash sorted text-id/content-SHA pairs canonically."""
    if not isinstance(text_hashes, Mapping):
        raise UpstreamModelError("text hashes must be a mapping")
    pieces: list[str] = []
    for text_id, digest in sorted(text_hashes.items()):
        if not isinstance(text_id, str) or not text_id or "\0" in text_id or "\n" in text_id:
            raise UpstreamModelError(f"invalid text id: {text_id!r}")
        _sha(digest, text_id)
        pieces.append(f"{text_id}\0{digest}\n")
    return sha256("".join(pieces).encode("utf-8")).hexdigest()


def _valid_timestamp(value: str | None, pattern: re.Pattern[str], fmt: str, label: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise UpstreamModelError(f"invalid {label}: {value!r}")
    try:
        datetime.strptime(value, fmt)
    except ValueError as exc:
        raise UpstreamModelError(f"invalid {label}: {value!r}") from exc


@dataclass(frozen=True)
class ArchiveLock:
    name: str
    url: str
    sha256: str
    bytes: int
    etag: str | None
    last_modified: str | None
    oracc_utc_timestamp: str
    licence: str
    extract_paths: tuple[str, ...]
    text_ids_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not _NAME_RE.fullmatch(self.name):
            raise UpstreamModelError(f"invalid archive name: {self.name!r}")
        expected_url = f"http://oracc.museum.upenn.edu/json/{self.name}.zip"
        if self.url != expected_url:
            raise UpstreamModelError(f"archive URL must be canonical: {expected_url}")
        _sha(self.sha256, self.name)
        if not isinstance(self.bytes, int) or isinstance(self.bytes, bool) or self.bytes < 0:
            raise UpstreamModelError(f"invalid byte length for {self.name}: {self.bytes!r}")
        if self.etag is not None and not isinstance(self.etag, str):
            raise UpstreamModelError("etag must be a string or null")
        _valid_timestamp(self.last_modified, _HTTP_TS_RE, "%Y-%m-%dT%H:%M:%SZ", "Last-Modified")
        _valid_timestamp(self.oracc_utc_timestamp, _ORACC_TS_RE, "%Y-%m-%dT%H:%M:%S", "ORACC UTC timestamp")
        if not isinstance(self.licence, str) or not self.licence.strip():
            raise UpstreamModelError("licence must be a non-empty source string")
        if not isinstance(self.extract_paths, tuple) or not self.extract_paths:
            raise UpstreamModelError("extract_paths must be a non-empty tuple")
        if len(set(self.extract_paths)) != len(self.extract_paths):
            raise UpstreamModelError("duplicate extract path")
        for path in self.extract_paths:
            if not isinstance(path, str) or not path or path.startswith("/") or ".." in Path(path).parts:
                raise UpstreamModelError(f"invalid extract path: {path!r}")
        _sha(self.text_ids_sha256, "text_ids_sha256")


def serialize_lock(records: Iterable[ArchiveLock], *, allowed_archives: set[str] | frozenset[str]) -> bytes:
    """Serialize a complete active-archive lock deterministically."""
    values = tuple(records)
    names = [record.name for record in values]
    if len(set(names)) != len(names):
        raise UpstreamModelError("duplicate archive in lock")
    unexpected = set(names) - set(allowed_archives)
    if unexpected:
        raise UpstreamModelError(f"archive not tracked: {', '.join(sorted(unexpected))}")
    missing = set(allowed_archives) - set(names)
    if missing:
        raise UpstreamModelError(f"tracked archive missing from lock: {', '.join(sorted(missing))}")
    payload: dict[str, object] = {}
    for record in sorted(values, key=lambda item: item.name):
        data = asdict(record)
        data.pop("name")
        data["extract_paths"] = list(record.extract_paths)
        payload[record.name] = data
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
