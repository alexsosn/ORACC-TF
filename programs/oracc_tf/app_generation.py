"""Deterministic generated Text-Fabric app shells for registered datasets.

Phase A owns packaging/discovery only.  Text formats, detailed presentation,
release/source-link provenance, and browser E2E behavior are layered on by
later P-006 phases.
"""

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
import tempfile

from tf.fabric import Fabric
import yaml

from . import paths, releases
from .distribution import repository_tf_root


_REQUIRED_WARP = ("otype.tf", "oslots.tf", "otext.tf")
_ALLOWED_OVERRIDE_KEYS = frozenset({"display_css"})


class AppGenerationError(ValueError):
    """A generated app request is unsafe, ambiguous, or incomplete."""


def _validate_registered_dataset(dataset: str, datasets_path: Path) -> None:
    try:
        datasets = releases.load_datasets(datasets_path)
    except Exception as exc:
        raise AppGenerationError(f"cannot load dataset registry: {datasets_path}") from exc
    if dataset not in datasets:
        raise AppGenerationError(f"unregistered dataset: {dataset!r}")


def _validate_disjoint_paths(tf_root: Path, target: Path) -> None:
    source = tf_root.resolve(strict=False)
    output = target.resolve(strict=False)
    if (
        source == output
        or source in output.parents
        or output in source.parents
    ):
        raise AppGenerationError(
            f"TF source and app target overlap: source={source}, target={output}"
        )


def _validate_tf_loadable(tf_root: Path) -> None:
    """Load the source through Text-Fabric without creating cache files in it."""
    with tempfile.TemporaryDirectory(prefix="oracc-tf-app-validate-") as temp_dir:
        isolated = Path(temp_dir) / "tf"
        isolated.mkdir()
        for source_file in sorted(tf_root.glob("*.tf")):
            if not source_file.is_file():
                continue
            target_file = isolated / source_file.name
            try:
                os.link(source_file, target_file)
            except OSError:
                shutil.copy2(source_file, target_file)

        try:
            tf = Fabric(locations=str(isolated), silent="deep")
            good = tf.loadAll(silent="deep")
        except Exception as exc:
            raise AppGenerationError(f"Text-Fabric could not load TF source: {tf_root}") from exc
        if not good or tf.api is None:
            raise AppGenerationError(f"Text-Fabric could not load valid TF warp: {tf_root}")


def _validate_tf_root(tf_root: Path, tf_version: str) -> None:
    try:
        repository_tf_root(Path("."), tf_version)
    except (TypeError, ValueError) as exc:
        raise AppGenerationError(f"invalid TF version: {tf_version!r}") from exc

    if tf_root.is_symlink() or not tf_root.is_dir():
        raise AppGenerationError(f"TF root is not a regular directory: {tf_root}")
    for name in _REQUIRED_WARP:
        path = tf_root / name
        if path.is_symlink() or not path.is_file():
            raise AppGenerationError(f"TF root is missing required warp feature: {name}")
    _validate_tf_loadable(tf_root)


def _validate_override(override: Mapping[str, object] | None) -> str | None:
    if override is None:
        return None
    if not isinstance(override, Mapping):
        raise AppGenerationError("app override must be a mapping")
    unknown = set(override) - _ALLOWED_OVERRIDE_KEYS
    if unknown:
        raise AppGenerationError(
            f"unsupported app override keys: {', '.join(sorted(str(key) for key in unknown))}"
        )
    css = override.get("display_css")
    if css is None:
        return None
    if not isinstance(css, str):
        raise AppGenerationError("display_css override must be text")
    if "\x00" in css or "@import" in css.lower() or ".." in css or "url(" in css.lower():
        raise AppGenerationError("display_css contains unsupported external/path syntax")
    return css


def _config_bytes(*, dataset: str, tf_version: str) -> bytes:
    config = {
        "apiVersion": 3,
        "provenanceSpec": {
            "corpus": dataset,
            "relative": "/tf",
            "version": tf_version,
        },
    }
    return yaml.safe_dump(
        config,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).encode("utf-8")


def _validate_target(target: Path) -> None:
    if target.is_symlink():
        raise AppGenerationError(f"app target is a symlink: {target}")
    if target.exists() and not target.is_dir():
        raise AppGenerationError(f"app target is not a directory: {target}")


def _replace_tree(temp: Path, target: Path) -> None:
    """Atomically replace ``target`` without deleting a foreign backup path."""
    if not target.exists():
        temp.replace(target)
        return

    backup = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
    )
    backup.rmdir()
    target.replace(backup)
    try:
        temp.replace(target)
    except Exception:
        backup.replace(target)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


def generate_app(
    tf_root: Path | str,
    target: Path | str,
    *,
    dataset: str,
    tf_version: str,
    datasets_path: Path | str = paths.ROOT / "datasets.toml",
    override: Mapping[str, object] | None = None,
) -> Path:
    """Generate one minimal deterministic Text-Fabric app directory.

    The ordinary app is entirely generated from registered dataset identity and
    the explicit TF schema-version root.  The only Phase-A override is literal
    CSS text; it cannot replace generated config/release identity.

    Generation is transactional: all inputs are validated and a complete
    sibling temp tree is built before the existing target is replaced.
    """
    source = Path(tf_root)
    output = Path(target)
    registry = Path(datasets_path)

    _validate_disjoint_paths(source, output)
    _validate_registered_dataset(dataset, registry)
    _validate_tf_root(source, tf_version)
    css = _validate_override(override)
    _validate_target(output)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    try:
        (temp / "config.yaml").write_bytes(
            _config_bytes(dataset=dataset, tf_version=tf_version)
        )
        if css is not None:
            (temp / "display.css").write_text(css, encoding="utf-8")

        # Keep Phase A deliberately declarative.  An app.py may be introduced
        # only by a later ticket with a demonstrated non-declarative need.
        _replace_tree(temp, output)
        return output
    finally:
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)


__all__ = ["AppGenerationError", "generate_app"]
