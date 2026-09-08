"""Fail-closed archive acquisition and extraction primitives.

The live HTTP/TLS adapter is deliberately out of scope here.  This module accepts
byte streams supplied by that future adapter, corroborates previously unseen
bytes, validates ZIP structure before publication, and extracts only through an
isolated staging tree.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unicodedata
import zipfile


_ZIP_LOCAL_MAGIC = b"PK\x03\x04"
_SUPPORTED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_DRIVE_RE = re.compile(r"^[A-Za-z]:")
_PROJECT_COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_COPY_CHUNK = 64 * 1024


class ArchiveSecurityError(ValueError):
    """Base class for archive bytes that cannot be accepted safely."""


class ArchiveDownloadError(ArchiveSecurityError):
    """A supplied byte stream is malformed or cannot be persisted safely."""


class ArchiveVerificationMismatch(ArchiveSecurityError):
    """Independent fetches of an unpinned source did not identify the same bytes."""


class ArchiveStructureError(ArchiveSecurityError):
    """The ZIP structure or ORACC project mapping is unsafe or ambiguous."""


class ArchiveResourceLimitError(ArchiveSecurityError):
    """A configured download/decompression resource ceiling was exceeded."""


class ArchiveExtractionError(ArchiveSecurityError):
    """A validated archive could not be published as a complete extracted tree."""


@dataclass(frozen=True)
class ArchiveLimits:
    max_download_bytes: int
    max_members: int
    max_member_uncompressed_bytes: int
    max_total_uncompressed_bytes: int
    max_compression_ratio: float

    def __post_init__(self) -> None:
        integer_fields = (
            "max_download_bytes",
            "max_members",
            "max_member_uncompressed_bytes",
            "max_total_uncompressed_bytes",
        )
        for field in integer_fields:
            value = getattr(self, field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ArchiveResourceLimitError(f"{field} must be a positive integer")
        ratio = self.max_compression_ratio
        if isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or ratio <= 0:
            raise ArchiveResourceLimitError("max_compression_ratio must be positive")


@dataclass(frozen=True)
class StreamedArchive:
    path: Path
    sha256: str
    bytes: int


@dataclass(frozen=True)
class ArchiveLayout:
    project_roots: tuple[str, ...]
    members: tuple[str, ...]
    total_uncompressed_bytes: int


@dataclass(frozen=True)
class _Member:
    info: zipfile.ZipInfo
    path: str
    is_dir: bool


def _unlink(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # Cleanup is best-effort only when another exception is already in flight.
        pass


def stream_to_temp(
    chunks: Iterable[bytes], *, temp_dir: Path | str, limits: ArchiveLimits
) -> StreamedArchive:
    """Persist a finite byte stream while hashing exactly the bytes written."""
    if not isinstance(limits, ArchiveLimits):
        raise ArchiveDownloadError("limits must be an ArchiveLimits instance")
    directory = Path(temp_dir)
    if not directory.is_dir():
        raise ArchiveDownloadError("temporary directory does not exist")

    fd, raw_path = tempfile.mkstemp(prefix=".oracc-tf-download-", suffix=".zip", dir=directory)
    path = Path(raw_path)
    digest = sha256()
    total = 0
    try:
        with os.fdopen(fd, "wb") as handle:
            for chunk in chunks:
                if not isinstance(chunk, bytes):
                    raise ArchiveDownloadError("download chunks must be bytes")
                if total + len(chunk) > limits.max_download_bytes:
                    raise ArchiveResourceLimitError("download exceeds configured byte ceiling")
                handle.write(chunk)
                digest.update(chunk)
                total += len(chunk)
            handle.flush()
        if total == 0:
            raise ArchiveDownloadError("download stream is empty")
    except BaseException:
        _unlink(path)
        raise

    return StreamedArchive(path=path, sha256=digest.hexdigest(), bytes=total)


def acquire_unseen(
    fetch_once: Callable[[], Iterable[bytes]],
    *,
    temp_dir: Path | str,
    limits: ArchiveLimits,
) -> StreamedArchive:
    """Require two independently supplied byte streams to identify the same bytes."""
    if not callable(fetch_once):
        raise ArchiveDownloadError("fetch_once must be callable")
    first: StreamedArchive | None = None
    second: StreamedArchive | None = None
    try:
        first = stream_to_temp(fetch_once(), temp_dir=temp_dir, limits=limits)
        second = stream_to_temp(fetch_once(), temp_dir=temp_dir, limits=limits)
        if (first.bytes, first.sha256) != (second.bytes, second.sha256):
            raise ArchiveVerificationMismatch(
                "independent archive fetches disagree on byte length or SHA-256"
            )
        _unlink(second.path)
        return first
    except BaseException:
        _unlink(first.path if first is not None else None)
        _unlink(second.path if second is not None else None)
        raise


def _safe_components(value: str, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, str) or not value:
        raise ArchiveStructureError(f"{field} must be a non-empty path")
    if "\x00" in value or "\\" in value:
        raise ArchiveStructureError(f"{field} contains an unsafe path character")
    if value.startswith("/") or value.startswith("//") or _DRIVE_RE.match(value):
        raise ArchiveStructureError(f"{field} must be a relative POSIX path")
    if value != unicodedata.normalize("NFC", value):
        raise ArchiveStructureError(f"{field} is not Unicode NFC")
    parts = tuple(value.split("/"))
    if any(part in {"", ".", ".."} for part in parts):
        raise ArchiveStructureError(f"{field} contains an unsafe path component")
    return parts


def _member_path(info: zipfile.ZipInfo) -> tuple[str, bool]:
    raw = info.filename
    if not isinstance(raw, str) or not raw:
        raise ArchiveStructureError("ZIP member name must be non-empty")
    is_dir = raw.endswith("/")
    value = raw[:-1] if is_dir else raw
    if not value:
        raise ArchiveStructureError("ZIP root directory entry is invalid")
    _safe_components(value, field="ZIP member")
    return value, is_dir


def _validate_file_type(info: zipfile.ZipInfo, *, is_dir: bool) -> None:
    if info.flag_bits & 0x1:
        raise ArchiveStructureError(f"encrypted ZIP member is unsupported: {info.filename!r}")
    if info.compress_type not in _SUPPORTED_COMPRESSION:
        raise ArchiveStructureError(
            f"unsupported ZIP compression method for {info.filename!r}: {info.compress_type}"
        )

    if info.create_system == 3:
        mode = (info.external_attr >> 16) & 0xFFFF
        kind = stat.S_IFMT(mode)
        if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise ArchiveStructureError(f"ZIP special file is forbidden: {info.filename!r}")
        if is_dir and kind == stat.S_IFREG:
            raise ArchiveStructureError(f"directory entry declares regular-file mode: {info.filename!r}")
        if not is_dir and kind == stat.S_IFDIR:
            raise ArchiveStructureError(f"file entry declares directory mode: {info.filename!r}")


def _validate_resource_metadata(info: zipfile.ZipInfo, limits: ArchiveLimits) -> int:
    size = info.file_size
    compressed = info.compress_size
    if size < 0 or compressed < 0:
        raise ArchiveStructureError(f"negative ZIP size metadata: {info.filename!r}")
    if size > limits.max_member_uncompressed_bytes:
        raise ArchiveResourceLimitError(
            f"member exceeds uncompressed byte ceiling: {info.filename!r}"
        )
    if size > 0:
        if compressed == 0:
            raise ArchiveResourceLimitError(
                f"member has nonzero output with zero compressed bytes: {info.filename!r}"
            )
        if size / compressed > limits.max_compression_ratio:
            raise ArchiveResourceLimitError(
                f"member exceeds compression-ratio ceiling: {info.filename!r}"
            )
    return size


def _project_path(value: object, *, field: str) -> str:
    if not isinstance(value, str):
        raise ArchiveStructureError(f"{field} must be a string")
    parts = _safe_components(value, field=field)
    if any(_PROJECT_COMPONENT_RE.fullmatch(part) is None for part in parts):
        raise ArchiveStructureError(f"{field} contains an invalid ORACC project component")
    return "/".join(parts)


def _read_metadata(archive: zipfile.ZipFile, member: _Member) -> Mapping[str, object]:
    try:
        with archive.open(member.info, "r") as handle:
            payload = handle.read()
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ArchiveStructureError(f"cannot read metadata member {member.path!r}") from exc
    try:
        decoded = payload.decode("utf-8")
        value = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArchiveStructureError(f"metadata member is not valid UTF-8 JSON: {member.path!r}") from exc
    if not isinstance(value, Mapping) or value.get("type") != "metadata":
        raise ArchiveStructureError(f"metadata member has invalid type: {member.path!r}")
    return value


def _inspect_archive(path: Path | str, limits: ArchiveLimits) -> tuple[ArchiveLayout, tuple[_Member, ...]]:
    if not isinstance(limits, ArchiveLimits):
        raise ArchiveStructureError("limits must be an ArchiveLimits instance")
    archive_path = Path(path)
    try:
        with archive_path.open("rb") as handle:
            if handle.read(4) != _ZIP_LOCAL_MAGIC:
                raise ArchiveStructureError("archive does not start with a ZIP local-file header")
    except ArchiveStructureError:
        raise
    except OSError as exc:
        raise ArchiveStructureError("archive cannot be opened") from exc
    if not zipfile.is_zipfile(archive_path):
        raise ArchiveStructureError("archive is not a complete ZIP file")

    try:
        archive = zipfile.ZipFile(archive_path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ArchiveStructureError("archive central directory is invalid") from exc

    with archive:
        try:
            infos = archive.infolist()
        except zipfile.BadZipFile as exc:
            raise ArchiveStructureError("archive central directory is invalid") from exc
        if not infos:
            raise ArchiveStructureError("archive contains no members")
        if len(infos) > limits.max_members:
            raise ArchiveResourceLimitError("archive exceeds member-count ceiling")

        members: list[_Member] = []
        literal: dict[str, bool] = {}
        folded: dict[str, str] = {}
        file_paths: set[str] = set()
        total = 0

        for info in infos:
            name, is_dir = _member_path(info)
            _validate_file_type(info, is_dir=is_dir)

            if name in literal:
                raise ArchiveStructureError(f"duplicate ZIP member path: {name!r}")
            literal[name] = is_dir
            alias = name.casefold()
            previous = folded.get(alias)
            if previous is not None and previous != name:
                raise ArchiveStructureError(
                    f"cross-platform ZIP path alias collision: {previous!r} vs {name!r}"
                )
            folded[alias] = name

            if is_dir:
                if info.file_size != 0:
                    raise ArchiveStructureError(f"directory entry has payload bytes: {name!r}")
            else:
                total += _validate_resource_metadata(info, limits)
                if total > limits.max_total_uncompressed_bytes:
                    raise ArchiveResourceLimitError(
                        "archive exceeds aggregate uncompressed byte ceiling"
                    )
                file_paths.add(name)
            members.append(_Member(info=info, path=name, is_dir=is_dir))

        all_paths = set(literal)
        for file_path in file_paths:
            components = file_path.split("/")
            for index in range(1, len(components)):
                ancestor = "/".join(components[:index])
                if ancestor in file_paths:
                    raise ArchiveStructureError(
                        f"file/directory prefix collision: {ancestor!r} is a file"
                    )
            if literal.get(file_path) is True:
                raise ArchiveStructureError(f"path is both file and directory: {file_path!r}")

        roots: set[str] = set()
        metadata_members = [
            member
            for member in members
            if not member.is_dir and member.path.endswith("/metadata.json")
        ]
        if not metadata_members:
            raise ArchiveStructureError("archive contains no structural ORACC metadata.json")

        for member in metadata_members:
            value = _read_metadata(archive, member)
            config = value.get("config")
            if not isinstance(config, Mapping):
                raise ArchiveStructureError(f"metadata config is invalid: {member.path!r}")
            pathname = _project_path(config.get("pathname"), field="metadata config.pathname")
            declared_project = value.get("project")
            if declared_project is not None:
                project = _project_path(declared_project, field="metadata project")
                if project != pathname:
                    raise ArchiveStructureError(
                        f"metadata project disagrees with pathname: {member.path!r}"
                    )
            parent = member.path.rsplit("/", 1)[0]
            if parent != pathname:
                raise ArchiveStructureError(
                    f"metadata location disagrees with pathname: {member.path!r}"
                )
            roots.add(pathname)

        layout = ArchiveLayout(
            project_roots=tuple(sorted(roots)),
            members=tuple(sorted(all_paths)),
            total_uncompressed_bytes=total,
        )
        return layout, tuple(members)


def preflight_archive(path: Path | str, limits: ArchiveLimits) -> ArchiveLayout:
    """Validate archive structure/resources without writing an extraction tree."""
    layout, _ = _inspect_archive(path, limits)
    return layout


def extract_archive(
    path: Path | str, destination: Path | str, limits: ArchiveLimits
) -> ArchiveLayout:
    """Extract a fully preflighted archive through a sibling staging directory."""
    destination_path = Path(destination)
    if destination_path.exists() or destination_path.is_symlink():
        raise ArchiveExtractionError("destination must not already exist")
    parent = destination_path.parent
    if not parent.is_dir():
        raise ArchiveExtractionError("destination parent directory does not exist")

    layout, members = _inspect_archive(path, limits)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination_path.name}.staging-", dir=parent))
    published = False
    try:
        with zipfile.ZipFile(Path(path), "r") as archive:
            actual_total = 0
            for member in sorted(members, key=lambda item: item.path):
                target = stage.joinpath(*member.path.split("/"))
                if member.is_dir:
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                actual_member = 0
                try:
                    source = archive.open(member.info, "r")
                except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                    raise ArchiveExtractionError(
                        f"cannot open ZIP member during extraction: {member.path!r}"
                    ) from exc
                with source, target.open("xb") as output:
                    while True:
                        try:
                            chunk = source.read(_COPY_CHUNK)
                        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                            raise ArchiveExtractionError(
                                f"cannot decompress ZIP member: {member.path!r}"
                            ) from exc
                        if not chunk:
                            break
                        next_member = actual_member + len(chunk)
                        next_total = actual_total + len(chunk)
                        if (
                            next_member > member.info.file_size
                            or next_member > limits.max_member_uncompressed_bytes
                            or next_total > limits.max_total_uncompressed_bytes
                        ):
                            raise ArchiveResourceLimitError(
                                f"actual decompressed bytes exceed declared/configured bounds: {member.path!r}"
                            )
                        output.write(chunk)
                        actual_member = next_member
                        actual_total = next_total
                if actual_member != member.info.file_size:
                    raise ArchiveExtractionError(
                        f"decompressed length disagrees with ZIP metadata: {member.path!r}"
                    )
            if actual_total != layout.total_uncompressed_bytes:
                raise ArchiveExtractionError("aggregate decompressed length disagrees with preflight")

        if destination_path.exists() or destination_path.is_symlink():
            raise ArchiveExtractionError("destination appeared before atomic publication")
        os.rename(stage, destination_path)
        published = True
        return layout
    except ArchiveSecurityError:
        raise
    except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
        raise ArchiveExtractionError("archive extraction failed") from exc
    finally:
        if not published:
            shutil.rmtree(stage, ignore_errors=True)


__all__ = [
    "ArchiveDownloadError",
    "ArchiveExtractionError",
    "ArchiveLayout",
    "ArchiveLimits",
    "ArchiveResourceLimitError",
    "ArchiveSecurityError",
    "ArchiveStructureError",
    "ArchiveVerificationMismatch",
    "StreamedArchive",
    "acquire_unseen",
    "extract_archive",
    "preflight_archive",
    "stream_to_temp",
]
