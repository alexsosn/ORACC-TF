"""Upstream policy and deterministic lock model for P-002 Phase 1."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import tomllib
from zipfile import BadZipFile, ZipFile


_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ORACC_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_HTTP_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_TEXT_FILE_RE = re.compile(r"^([PQX][0-9]+)\.json$")


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


def sha256_bytes(value: bytes) -> str:
    """Return the lowercase SHA-256 hex digest of a byte string."""
    if not isinstance(value, bytes):
        raise UpstreamModelError("SHA-256 input must be bytes")
    return sha256(value).hexdigest()


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


def _archive_files(body: bytes) -> dict[str, bytes]:
    """Read a ZIP into a path→bytes map without extracting it to disk."""
    if not isinstance(body, bytes) or not body.startswith(b"PK"):
        raise UpstreamModelError("response body is not a valid ZIP archive")
    try:
        with ZipFile(BytesIO(body)) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise UpstreamModelError(f"ZIP member failed CRC validation: {bad}")
            files: dict[str, bytes] = {}
            for info in archive.infolist():
                if info.is_dir():
                    continue
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or not path.parts:
                    raise UpstreamModelError(f"invalid ZIP member path: {info.filename!r}")
                key = path.as_posix()
                if key in files:
                    raise UpstreamModelError(f"duplicate ZIP member: {key}")
                files[key] = archive.read(info)
    except (BadZipFile, OSError, RuntimeError) as exc:
        raise UpstreamModelError("response body is not a valid ZIP archive") from exc
    if not files:
        raise UpstreamModelError("ZIP archive contains no files")
    return files


def _metadata_roots(files: Mapping[str, bytes]) -> tuple[tuple[str, ...], list[Mapping[str, object]]]:
    roots: list[str] = []
    metadata_values: list[Mapping[str, object]] = []
    for path, body in sorted(files.items()):
        if not path.endswith("/metadata.json"):
            continue
        try:
            value = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UpstreamModelError(f"invalid metadata JSON: {path}") from exc
        if not isinstance(value, Mapping):
            raise UpstreamModelError(f"metadata must be a JSON object: {path}")
        project = value.get("project")
        if not isinstance(project, str) or not project or project.startswith("/"):
            raise UpstreamModelError(f"metadata has invalid project: {path}")
        expected = project.rstrip("/") + "/metadata.json"
        if path != expected:
            raise UpstreamModelError(
                f"metadata path/project mismatch: {path!r} declares {project!r}"
            )
        root = project.rstrip("/") + "/"
        if root in roots:
            raise UpstreamModelError(f"duplicate metadata root: {root}")
        roots.append(root)
        metadata_values.append(value)
    if not roots:
        raise UpstreamModelError("archive has no project metadata.json")
    return tuple(sorted(roots)), metadata_values


def inspect_archive_bytes(
    name: str,
    body: bytes,
    *,
    etag: str | None,
    last_modified: str | None,
) -> ArchiveLock:
    """Derive one lock record entirely from a downloaded ORACC ZIP and its HTTP validators."""
    files = _archive_files(body)
    roots, metadata_values = _metadata_roots(files)

    outside = [path for path in files if not any(path.startswith(root) for root in roots)]
    if outside:
        raise UpstreamModelError(
            "archive contains files outside declared project roots: " + ", ".join(outside[:3])
        )

    licences = {value.get("license") for value in metadata_values}
    if len(licences) != 1:
        raise UpstreamModelError("archive metadata has inconsistent licence strings")
    licence = next(iter(licences))
    if not isinstance(licence, str) or not licence.strip():
        raise UpstreamModelError("archive metadata has no licence string")

    timestamps = [value.get("UTC-timestamp") for value in metadata_values]
    for timestamp in timestamps:
        _valid_timestamp(timestamp, _ORACC_TS_RE, "%Y-%m-%dT%H:%M:%S", "ORACC UTC timestamp")
    if any(not isinstance(timestamp, str) for timestamp in timestamps):
        raise UpstreamModelError("archive metadata has no ORACC UTC timestamp")
    oracc_timestamp = max(timestamp for timestamp in timestamps if isinstance(timestamp, str))

    text_hashes: dict[str, str] = {}
    for path, value in sorted(files.items()):
        posix = PurePosixPath(path)
        if posix.parent.name != "corpusjson":
            continue
        match = _TEXT_FILE_RE.fullmatch(posix.name)
        if match is None:
            continue
        text_id = match.group(1)
        if text_id in text_hashes:
            raise UpstreamModelError(f"duplicate text id in archive: {text_id}")
        text_hashes[text_id] = sha256_bytes(value)

    return ArchiveLock(
        name=name,
        url=f"http://oracc.museum.upenn.edu/json/{name}.zip",
        sha256=sha256_bytes(body),
        bytes=len(body),
        etag=etag,
        last_modified=last_modified,
        oracc_utc_timestamp=oracc_timestamp,
        licence=licence,
        extract_paths=roots,
        text_ids_sha256=text_ids_digest(text_hashes),
    )


@dataclass(frozen=True)
class SnapshotDiff:
    added: tuple[str, ...]
    removed: tuple[str, ...]
    modified: tuple[str, ...]

    @property
    def exact(self) -> bool:
        return not (self.added or self.removed or self.modified)


def compare_archive_bytes_to_tree(body: bytes, data_root: Path) -> SnapshotDiff:
    """Compare ZIP bytes with the committed extraction without writing to the tree."""
    files = _archive_files(body)
    roots, _ = _metadata_roots(files)
    archive_paths = {
        path for path in files if any(path.startswith(root) for root in roots)
    }
    outside = set(files) - archive_paths
    if outside:
        raise UpstreamModelError(
            "archive contains files outside declared project roots: " + ", ".join(sorted(outside)[:3])
        )

    tree_paths: set[str] = set()
    for root in roots:
        local_root = data_root / PurePosixPath(root)
        if not local_root.is_dir():
            continue
        for local in local_root.rglob("*"):
            if local.is_file():
                tree_paths.add(local.relative_to(data_root).as_posix())

    added = tuple(sorted(archive_paths - tree_paths))
    removed = tuple(sorted(tree_paths - archive_paths))
    modified = tuple(
        path for path in sorted(archive_paths & tree_paths)
        if files[path] != (data_root / PurePosixPath(path)).read_bytes()
    )
    return SnapshotDiff(added=added, removed=removed, modified=modified)
