"""Release identity and dataset input policy for P-002 Phase 0.

ORACC has no upstream release identifier. We therefore keep two distinct
notions: a human-readable maximum upstream date and a content identity derived
from the complete set of contributing archive SHA-256 values. The latter is
part of release build metadata so equal dates cannot alias different bytes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
import re
import tomllib


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class ReleaseModelError(ValueError):
    """Invalid or ambiguous release-model input."""


@dataclass(frozen=True)
class ArchiveVersion:
    """Content identity and upstream timestamp for one ORACC archive."""

    name: str
    sha256: str
    oracc_utc_timestamp: str

    def __post_init__(self) -> None:
        if not _NAME_RE.fullmatch(self.name):
            raise ReleaseModelError(f"invalid archive name: {self.name!r}")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ReleaseModelError(f"invalid SHA-256 for {self.name}: {self.sha256!r}")
        if not _TIMESTAMP_RE.fullmatch(self.oracc_utc_timestamp):
            raise ReleaseModelError(
                f"invalid ORACC UTC timestamp for {self.name}: {self.oracc_utc_timestamp!r}"
            )
        try:
            datetime.strptime(self.oracc_utc_timestamp, "%Y-%m-%dT%H:%M:%S")
        except ValueError as exc:
            raise ReleaseModelError(
                f"invalid ORACC UTC timestamp for {self.name}: {self.oracc_utc_timestamp!r}"
            ) from exc


@dataclass(frozen=True)
class DatasetInputs:
    """Declared upstream inputs for one published TF dataset."""

    archives: tuple[str, ...]
    tei: tuple[str, ...] = ()


@dataclass(frozen=True)
class _SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...]
    build: tuple[str, ...]


def _parse_semver(value: str) -> _SemVer:
    match = _SEMVER_RE.fullmatch(value)
    if match is None:
        raise ReleaseModelError(f"invalid SemVer: {value!r}")
    major, minor, patch, prerelease_raw, build_raw = match.groups()
    prerelease = tuple(prerelease_raw.split(".")) if prerelease_raw else ()
    build = tuple(build_raw.split(".")) if build_raw else ()
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
            raise ReleaseModelError(f"invalid SemVer numeric prerelease identifier: {value!r}")
    return _SemVer(
        major=int(major),
        minor=int(minor),
        patch=int(patch),
        prerelease=prerelease,
        build=build,
    )


def semver_precedence_key(value: str) -> tuple[object, ...]:
    """Return a key implementing SemVer precedence; build metadata is ignored."""
    parsed = _parse_semver(value)
    if not parsed.prerelease:
        prerelease_key: tuple[object, ...] = (1, ())
    else:
        identifiers: tuple[tuple[object, ...], ...] = tuple(
            (0, int(identifier)) if identifier.isdigit() else (1, identifier)
            for identifier in parsed.prerelease
        )
        prerelease_key = (0, identifiers)
    return (parsed.major, parsed.minor, parsed.patch, *prerelease_key)


def _validated_archives(archives: Iterable[ArchiveVersion]) -> tuple[ArchiveVersion, ...]:
    values = tuple(archives)
    if not values:
        raise ReleaseModelError("release identity requires at least one archive")
    seen: set[str] = set()
    duplicates: set[str] = set()
    for archive in values:
        if archive.name in seen:
            duplicates.add(archive.name)
        seen.add(archive.name)
    if duplicates:
        raise ReleaseModelError(f"duplicate archive identity: {', '.join(sorted(duplicates))}")
    return values


def source_set_digest(archives: Iterable[ArchiveVersion]) -> str:
    """Hash the complete archive-name/SHA mapping in canonical name order."""
    values = _validated_archives(archives)
    canonical = "".join(
        f"{archive.name}\0{archive.sha256}\n"
        for archive in sorted(values, key=lambda archive: archive.name)
    ).encode("utf-8")
    return sha256(canonical).hexdigest()


def _oracc_state(values: Iterable[ArchiveVersion]) -> str:
    latest = max(archive.oracc_utc_timestamp for archive in values)
    return latest[:10]


def _version_with_oracc_metadata(tf_version: str, oracc_state: str, digest: str) -> str:
    parsed = _parse_semver(tf_version)
    metadata = [*parsed.build, "oracc", oracc_state, digest[:12]]
    core = f"{parsed.major}.{parsed.minor}.{parsed.patch}"
    if parsed.prerelease:
        core += "-" + ".".join(parsed.prerelease)
    return core + "+" + ".".join(metadata)


@dataclass(frozen=True)
class ReleaseIdentity:
    """Immutable identity of one dataset build."""

    dataset: str
    tf_version: str
    oracc_state: str
    source_digest: str
    tag: str

    @classmethod
    def from_archives(
        cls,
        dataset: str,
        tf_version: str,
        archives: Iterable[ArchiveVersion],
    ) -> "ReleaseIdentity":
        if not _NAME_RE.fullmatch(dataset):
            raise ReleaseModelError(f"invalid dataset name: {dataset!r}")
        _parse_semver(tf_version)
        values = _validated_archives(archives)
        digest = source_set_digest(values)
        state = _oracc_state(values)
        version = _version_with_oracc_metadata(tf_version, state, digest)
        return cls(
            dataset=dataset,
            tf_version=tf_version,
            oracc_state=state,
            source_digest=digest,
            tag=f"{dataset}/v{version}",
        )


def _string_tuple(value: object, *, field: str, dataset: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ReleaseModelError(f"{dataset}.{field} must be a list of strings")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise ReleaseModelError(f"{dataset}.{field} contains duplicate entries")
    if any(not _NAME_RE.fullmatch(item) for item in result):
        raise ReleaseModelError(f"{dataset}.{field} contains an invalid input name")
    return result


def load_datasets(path: Path) -> dict[str, DatasetInputs]:
    """Load and validate the Phase-0 dataset-to-upstream mapping."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseModelError(f"cannot load dataset config {path}: {exc}") from exc
    if not isinstance(raw, Mapping) or not raw:
        raise ReleaseModelError("dataset config must define at least one dataset")

    result: dict[str, DatasetInputs] = {}
    for dataset, value in raw.items():
        if not isinstance(dataset, str) or not _NAME_RE.fullmatch(dataset):
            raise ReleaseModelError(f"invalid dataset name: {dataset!r}")
        if not isinstance(value, Mapping):
            raise ReleaseModelError(f"dataset {dataset!r} must be a TOML table")
        unknown = set(value) - {"archives", "tei"}
        if unknown:
            raise ReleaseModelError(
                f"dataset {dataset!r} has unknown fields: {', '.join(sorted(unknown))}"
            )
        archives = _string_tuple(value.get("archives"), field="archives", dataset=dataset)
        if not archives:
            raise ReleaseModelError(f"dataset {dataset!r} must declare at least one archive")
        tei = _string_tuple(value.get("tei", []), field="tei", dataset=dataset)
        result[dataset] = DatasetInputs(archives=archives, tei=tei)
    return result


def tracked_archives(config: Mapping[str, DatasetInputs]) -> frozenset[str]:
    """Return exactly the archive names a discovery sweep should poll."""
    return frozenset(
        archive
        for dataset in config.values()
        for archive in dataset.archives
    )
