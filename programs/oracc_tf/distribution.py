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

from . import corpus, paths, releases


_REPOSITORY_DATASET_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_STATE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_TREE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_REQUIRED_FILES = ("otype.tf", "oslots.tf", "otext.tf")
_FORBIDDEN_PAYLOAD_PARTS = frozenset({"data", "programs", "docs"})
_MANIFEST_SCHEMA_VERSION = 3
_RELEASE_RECORD_FIELDS = (
    "tf_version",
    "tf_root",
    "builder_commit",
    "source_state",
    "provenance_complete",
    "tree_digest",
)
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "dataset",
        "repository",
        "release_id",
        *_RELEASE_RECORD_FIELDS,
        "releases",
        "visible_roots",
    }
)


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


def _canonical_tf_root(dataset: str, tf_version: str) -> str:
    try:
        root = distribution_root(Path("."), dataset, tf_version)
    except (TypeError, ValueError) as exc:
        raise InvalidDistribution(f"invalid TF version in distribution manifest: {tf_version!r}") from exc
    return root.as_posix().removeprefix("./")


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
        relative = path.relative_to(source)
        if relative.parts and relative.parts[0] in _FORBIDDEN_PAYLOAD_PARTS:
            raise InvalidDistribution(
                f"TF source contains forbidden distribution payload path: {relative.as_posix()}"
            )
        if path.is_symlink():
            raise InvalidDistribution(f"TF source contains a symlink: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise InvalidDistribution(f"TF source contains unsupported entry: {path}")
        files.append(path)
    return tuple(files)


def _validate_loadable(source: Path) -> None:
    """Validate TF semantics without letting Text-Fabric mutate publishable bytes."""
    temp_root = Path(tempfile.mkdtemp(prefix=".oracc-tf-load-check-"))
    probe = temp_root / "tf"
    try:
        shutil.copytree(source, probe)
        corpus.load_tf(probe)
    except Exception as exc:
        raise InvalidDistribution(f"TF source is not loadable: {source}") from exc
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


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
    if stage.is_symlink():
        raise InvalidDistribution(f"existing distribution stage is a symlink: {stage}")
    if not stage.exists():
        return None
    if not stage.is_dir():
        raise InvalidDistribution(f"existing distribution stage is not a directory: {stage}")

    _validate_distribution_boundary(stage)
    path = stage / "manifest.json"
    if not path.exists():
        if any(stage.iterdir()):
            raise InvalidDistribution(
                f"existing distribution stage contains content but has no manifest: {stage}"
            )
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidDistribution(f"existing distribution manifest is unreadable: {path}") from exc
    if not isinstance(value, dict):
        raise InvalidDistribution("existing distribution manifest must be a JSON object")
    return value


def _validate_manifest_release_record(
    release_id: str,
    value: object,
    *,
    dataset: str,
) -> dict[str, object]:
    try:
        _validate_release_id(release_id)
    except ValueError as exc:
        raise InvalidDistribution(f"invalid release id in existing distribution: {release_id!r}") from exc
    if not isinstance(value, dict) or set(value) != set(_RELEASE_RECORD_FIELDS):
        raise InvalidDistribution(f"existing distribution release {release_id!r} has invalid fields")

    tf_version = value.get("tf_version")
    tf_root = value.get("tf_root")
    if not isinstance(tf_version, str) or not isinstance(tf_root, str):
        raise InvalidDistribution(f"existing distribution release {release_id!r} has invalid TF identity")
    if tf_root != _canonical_tf_root(dataset, tf_version):
        raise InvalidDistribution(f"existing distribution release {release_id!r} has non-canonical TF root")

    builder_commit = value.get("builder_commit")
    source_state = value.get("source_state")
    try:
        _validate_provenance(builder_commit, source_state)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise InvalidDistribution(f"existing distribution release {release_id!r} has invalid provenance") from exc

    provenance_complete = value.get("provenance_complete")
    if not isinstance(provenance_complete, bool) or provenance_complete != (source_state is not None):
        raise InvalidDistribution(
            f"existing distribution release {release_id!r} has inconsistent provenance state"
        )
    tree_digest = value.get("tree_digest")
    if not isinstance(tree_digest, str) or not _TREE_DIGEST_RE.fullmatch(tree_digest):
        raise InvalidDistribution(f"existing distribution release {release_id!r} has invalid tree digest")
    return dict(value)


def _discover_tf_roots(stage: Path) -> set[str]:
    if not stage.exists():
        return set()
    roots: set[str] = set()
    for otype in stage.rglob("otype.tf"):
        if not otype.is_file():
            continue
        try:
            relative = otype.parent.relative_to(stage).as_posix()
        except ValueError as exc:
            raise InvalidDistribution(f"discoverable TF root escapes staging tree: {otype}") from exc
        roots.add(relative)
    return roots


def _validate_distribution_boundary(stage: Path) -> None:
    """Reject injected build/research payload and symlinks anywhere in a staged tree."""
    if stage.is_symlink():
        raise InvalidDistribution(f"existing distribution stage is a symlink: {stage}")
    for path in sorted(stage.rglob("*")):
        relative = path.relative_to(stage)
        if path.is_symlink():
            raise InvalidDistribution(
                f"existing distribution contains a symlink: {relative.as_posix()}"
            )
        forbidden = _FORBIDDEN_PAYLOAD_PARTS.intersection(relative.parts)
        if forbidden:
            raise InvalidDistribution(
                "existing distribution contains forbidden payload path: "
                f"{relative.as_posix()}"
            )


def _is_owned_stage_path(relative: Path, visible_roots: dict[str, str]) -> bool:
    """Return whether a staged path is manifest metadata or part of an owned TF root."""
    if relative.as_posix() in {"README.md", "manifest.json"}:
        return True
    for tf_root in visible_roots:
        root = Path(tf_root)
        if relative == root or relative in root.parents or root in relative.parents:
            return True
    return False


def _validate_manifest_state(
    stage: Path,
    manifest: dict[str, object],
    *,
    dataset: str,
    repository: str,
) -> tuple[dict[str, object], dict[str, str]]:
    _validate_distribution_boundary(stage)
    if manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION:
        raise InvalidDistribution(
            f"unsupported existing distribution manifest schema: {manifest.get('schema_version')!r}"
        )
    if set(manifest) != _MANIFEST_FIELDS:
        raise InvalidDistribution("existing distribution manifest has invalid schema fields")
    if manifest.get("dataset") != dataset or manifest.get("repository") != repository:
        raise ImmutableDistributionConflict(
            f"staging tree already belongs to another distribution: {manifest.get('dataset')!r}"
        )

    raw_ledger = manifest.get("releases")
    if not isinstance(raw_ledger, dict) or not raw_ledger:
        raise InvalidDistribution("existing distribution releases ledger must be a non-empty JSON object")
    ledger: dict[str, object] = {}
    for release_id, raw_record in raw_ledger.items():
        if not isinstance(release_id, str):
            raise InvalidDistribution("existing distribution release ids must be strings")
        ledger[release_id] = _validate_manifest_release_record(
            release_id,
            raw_record,
            dataset=dataset,
        )

    current_id = manifest.get("release_id")
    if not isinstance(current_id, str) or current_id not in ledger:
        raise InvalidDistribution("existing distribution current release is absent from its ledger")
    current_record = ledger[current_id]
    assert isinstance(current_record, dict)
    for field in _RELEASE_RECORD_FIELDS:
        if field not in manifest or manifest[field] != current_record[field]:
            raise InvalidDistribution(
                f"existing distribution current fields do not match release {current_id!r}"
            )

    raw_visible = manifest.get("visible_roots")
    if not isinstance(raw_visible, dict) or not raw_visible:
        raise InvalidDistribution("existing distribution visible_roots must be a non-empty JSON object")
    visible_roots: dict[str, str] = {}
    for tf_root, owner_id in raw_visible.items():
        if not isinstance(tf_root, str) or not isinstance(owner_id, str):
            raise InvalidDistribution("existing distribution visible_roots entries must be strings")
        owner = ledger.get(owner_id)
        if not isinstance(owner, dict):
            raise InvalidDistribution(f"visible TF root {tf_root!r} references unknown release {owner_id!r}")
        if owner.get("tf_root") != tf_root:
            raise InvalidDistribution(
                f"visible TF root {tf_root!r} disagrees with release {owner_id!r}"
            )
        visible_roots[tf_root] = owner_id

    for path in sorted(stage.rglob("*")):
        relative = path.relative_to(stage)
        if not _is_owned_stage_path(relative, visible_roots):
            raise InvalidDistribution(
                f"existing distribution contains unowned content: {relative.as_posix()}"
            )

    current_root = current_record["tf_root"]
    assert isinstance(current_root, str)
    if visible_roots.get(current_root) != current_id:
        raise InvalidDistribution("existing distribution current release does not own its visible TF root")

    discovered = _discover_tf_roots(stage)
    if discovered != set(visible_roots):
        raise InvalidDistribution(
            "existing distribution visible_roots do not match discoverable TF roots: "
            f"manifest={sorted(visible_roots)!r}, filesystem={sorted(discovered)!r}"
        )

    for tf_root, owner_id in sorted(visible_roots.items()):
        owner = ledger[owner_id]
        assert isinstance(owner, dict)
        expected_digest = owner["tree_digest"]
        assert isinstance(expected_digest, str)
        root = stage / tf_root
        label = "current visible release" if owner_id == current_id else "visible release"
        try:
            files = _validate_source(root)
            actual_digest = _tree_digest(root, files)
            _validate_loadable(root)
        except InvalidDistribution as exc:
            raise ImmutableDistributionConflict(
                f"{label} {owner_id!r} at {tf_root!r} is invalid"
            ) from exc
        if actual_digest != expected_digest:
            raise ImmutableDistributionConflict(
                f"{label} {owner_id!r} at {tf_root!r} has changed bytes"
            )

    return ledger, visible_roots


def _current_manifest(
    *,
    dataset: str,
    repository: str,
    release_id: str,
    record: dict[str, object],
    ledger: dict[str, object],
    visible_roots: dict[str, str],
) -> dict[str, object]:
    return {
        "schema_version": _MANIFEST_SCHEMA_VERSION,
        "dataset": dataset,
        "repository": repository,
        "release_id": release_id,
        **record,
        "releases": ledger,
        "visible_roots": visible_roots,
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
    digest/provenance evidence for older releases. Manifest v3 additionally maps
    every discoverable TF root to the release that owns its currently visible
    bytes, so all coexisting versions are checked before replay or publication.
    """
    identity = distribution_identity(dataset)
    _validate_release_id(release_id)
    root_probe = distribution_root(Path("."), dataset, tf_version)
    _validate_provenance(builder_commit, source_state)

    source_path = Path(source)
    stage_path = Path(stage)
    source_resolved = source_path.resolve(strict=False)
    stage_resolved = stage_path.resolve(strict=False)
    if (
        source_resolved == stage_resolved
        or source_resolved in stage_resolved.parents
        or stage_resolved in source_resolved.parents
    ):
        raise InvalidDistribution(
            f"TF source and distribution stage overlap: source={source_path}, stage={stage_path}"
        )
    files = _validate_source(source_path)
    _validate_loadable(source_path)
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
    visible_roots: dict[str, str] = {}
    if existing is not None:
        ledger, visible_roots = _validate_manifest_state(
            stage_path,
            existing,
            dataset=dataset,
            repository=identity.repository,
        )
        old_record = ledger.get(release_id)
        if old_record is not None:
            if old_record != record:
                raise ImmutableDistributionConflict(
                    f"immutable release {dataset}@{release_id} already exists with different state"
                )
            return existing

    ledger = dict(ledger)
    visible_roots = dict(visible_roots)
    ledger[release_id] = record
    visible_roots[tf_root] = release_id
    manifest = _current_manifest(
        dataset=dataset,
        repository=identity.repository,
        release_id=release_id,
        record=record,
        ledger=ledger,
        visible_roots=visible_roots,
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
        _validate_loadable(target_root)

        (temp / "README.md").write_text(
            f"# {dataset}\n\nGenerated ORACC-TF distribution.\n",
            encoding="utf-8",
        )
        (temp / "manifest.json").write_bytes(_manifest_bytes(manifest))

        _validate_manifest_state(
            temp,
            manifest,
            dataset=dataset,
            repository=identity.repository,
        )

        if stage_path.exists():
            backup = stage_path.with_name(stage_path.name + ".old")
            if backup.exists() or backup.is_symlink():
                raise InvalidDistribution(
                    f"transaction backup path already exists: {backup}"
                )
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
