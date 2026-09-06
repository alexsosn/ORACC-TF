"""Deterministic local staging for lightweight ORACC-TF distributions.

P-005 keeps semantic dataset identity separate from upstream archive layout,
Text-Fabric schema version, and immutable publication release identity. This
module deliberately stops at a validated local distribution tree; external
repository mutation belongs to a later phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import tempfile

from . import paths, releases


_REPOSITORY_DATASET_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_STATE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED_FILES = ("otype.tf", "oslots.tf", "otext.tf", "zero-span.json")


class DistributionError(ValueError):
    """Base class for invalid distribution input or state."""


class InvalidDistribution(DistributionError):
    """A source/staged tree cannot be accepted as a distribution."""


class ImmutableDistributionConflict(DistributionError):
    """An immutable release identity already exists with different state."""


@dataclass(frozen=True)
class DistributionIdentity:
    dataset: str
    repository: str
    archives: tuple[str, ...]

    @property
    def repositories(self) -> tuple[str, ...]:
        return (self.repository,)


def repository_name(dataset: str) -> str:
    """Return the generated repository locator for one semantic dataset."""
    if not isinstance(dataset, str) or not _REPOSITORY_DATASET_RE.fullmatch(dataset):
        raise ValueError(f"invalid dataset identifier: {dataset!r}")
    if ".." in dataset:
        raise ValueError(f"ambiguous dataset identifier: {dataset!r}")
    return f"ORACC-TF-{dataset}"


def distribution_identity(
    dataset: str,
    *,
    datasets_path: Path | str = paths.ROOT / "datasets.toml",
) -> DistributionIdentity:
    """Resolve a registered semantic dataset to exactly one distribution repo."""
    name = repository_name(dataset)
    config = releases.load_datasets(Path(datasets_path))
    try:
        inputs = config[dataset]
    except KeyError as exc:
        raise ValueError(f"unregistered dataset: {dataset!r}") from exc
    return DistributionIdentity(dataset=dataset, repository=name, archives=inputs.archives)


def distribution_root(output_base: Path | str, dataset: str, tf_version: str) -> Path:
    """Return the canonical dataset/version root inside a distribution tree."""
    repository_name(dataset)
    return paths.publishable_tf_root(output_base, dataset, tf_version)


def _validate_release_id(release_id: str) -> None:
    if not isinstance(release_id, str) or not release_id or release_id != release_id.strip():
        raise ValueError(f"invalid release id: {release_id!r}")
    if any(ord(char) < 0x20 for char in release_id):
        raise ValueError(f"invalid release id: {release_id!r}")


def _validate_source(source: Path) -> tuple[Path, ...]:
    if not source.is_dir():
        raise InvalidDistribution(f"TF source is not a directory: {source}")
    for required in _REQUIRED_FILES:
        if not (source / required).is_file():
            raise InvalidDistribution(f"TF source is missing required file: {required}")

    files: list[Path] = []
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise InvalidDistribution(f"TF source contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise InvalidDistribution(f"TF source contains unsupported entry: {path}")
        files.append(path)
    return tuple(files)


def _tree_digest(source: Path, files: tuple[Path, ...]) -> str:
    digest = sha256()
    for path in files:
        relative = path.relative_to(source).as_posix()
        payload = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return "sha256:" + digest.hexdigest()


def _validate_provenance(builder_commit: str, source_state: str | None) -> None:
    if not isinstance(builder_commit, str) or not _COMMIT_RE.fullmatch(builder_commit):
        raise ValueError(f"invalid builder commit: {builder_commit!r}")
    if source_state is not None and (
        not isinstance(source_state, str) or not _SOURCE_STATE_RE.fullmatch(source_state)
    ):
        raise ValueError(f"invalid source state: {source_state!r}")


def _release_record(
    *,
    tf_version: str,
    tf_root: str,
    builder_commit: str,
    source_state: str | None,
    tree_digest: str,
) -> dict[str, object]:
    return {
        "tf_version": tf_version,
        "tf_root": tf_root,
        "builder_commit": builder_commit,
        "source_state": source_state,
        "provenance_complete": source_state is not None,
        "tree_digest": tree_digest,
    }


def _manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _read_existing_manifest(stage: Path) -> dict[str, object] | None:
    path = stage / "manifest.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidDistribution(f"existing distribution manifest is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise InvalidDistribution("existing distribution manifest must be a JSON object")
    releases_value = value.get("releases")
    if releases_value is not None and not isinstance(releases_value, dict):
        raise InvalidDistribution("existing distribution releases ledger must be a JSON object")
    return value


def _current_manifest(
    *,
    dataset: str,
    repository: str,
    release_id: str,
    record: dict[str, object],
    ledger: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "dataset": dataset,
        "repository": repository,
        "release_id": release_id,
        **record,
        "releases": ledger,
    }


def stage_distribution(
    source: Path | str,
    stage: Path | str,
    *,
    dataset: str,
    release_id: str,
    tf_version: str,
    builder_commit: str,
    source_state: str | None,
) -> dict[str, object]:
    """Stage one immutable release into a minimal semantic-dataset tree.

    ``release_id`` identifies immutable publication state; ``tf_version`` only
    identifies the TF schema/layout. Replaying an earlier matching release is a
    no-op even when a newer release is current. A new release may replace bytes
    at the same TF-version root while the manifest ledger retains immutable
    digest/provenance evidence for older releases.
    """
    identity = distribution_identity(dataset)
    _validate_release_id(release_id)
    root_probe = distribution_root(Path("."), dataset, tf_version)
    _validate_provenance(builder_commit, source_state)

    source_path = Path(source)
    stage_path = Path(stage)
    files = _validate_source(source_path)
    tree_digest = _tree_digest(source_path, files)
    tf_root = root_probe.as_posix().removeprefix("./")
    record = _release_record(
        tf_version=tf_version,
        tf_root=tf_root,
        builder_commit=builder_commit,
        source_state=source_state,
        tree_digest=tree_digest,
    )

    existing = _read_existing_manifest(stage_path)
    ledger: dict[str, object] = {}
    if existing is not None:
        if existing.get("dataset") != dataset or existing.get("repository") != identity.repository:
            raise ImmutableDistributionConflict(
                f"staging tree already belongs to another distribution: {existing.get('dataset')!r}"
            )
        raw_ledger = existing.get("releases", {})
        assert isinstance(raw_ledger, dict)
        ledger = dict(raw_ledger)
        old_record = ledger.get(release_id)
        if old_record is not None:
            if old_record != record:
                raise ImmutableDistributionConflict(
                    f"immutable release {dataset}@{release_id} already exists with different state"
                )
            if existing.get("release_id") == release_id:
                existing_root = stage_path / tf_root
                existing_files = _validate_source(existing_root)
                if _tree_digest(existing_root, existing_files) != tree_digest:
                    raise ImmutableDistributionConflict(
                        f"current immutable release {dataset}@{release_id} has changed bytes"
                    )
            return existing

    ledger[release_id] = record
    manifest = _current_manifest(
        dataset=dataset,
        repository=identity.repository,
        release_id=release_id,
        record=record,
        ledger=ledger,
    )

    stage_path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{stage_path.name}.stage-", dir=stage_path.parent))
    try:
        if stage_path.exists():
            shutil.copytree(stage_path, temp, dirs_exist_ok=True)

        target_root = distribution_root(temp, dataset, tf_version)
        if target_root.exists():
            shutil.rmtree(target_root)
        target_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_path, target_root)

        target_files = _validate_source(target_root)
        if _tree_digest(target_root, target_files) != tree_digest:
            raise InvalidDistribution("staged TF bytes do not match the validated source tree")

        (temp / "README.md").write_text(
            f"# {dataset}\n\nGenerated ORACC-TF distribution.\n",
            encoding="utf-8",
        )
        (temp / "manifest.json").write_bytes(_manifest_bytes(manifest))

        if stage_path.exists():
            backup = stage_path.with_name(stage_path.name + ".old")
            if backup.exists():
                shutil.rmtree(backup)
            stage_path.replace(backup)
            try:
                temp.replace(stage_path)
            except Exception:
                backup.replace(stage_path)
                raise
            else:
                shutil.rmtree(backup, ignore_errors=True)
        else:
            temp.replace(stage_path)
        return manifest
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
