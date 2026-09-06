"""Publishable dataset layout and registered build entry points.

Low-level corpus builders intentionally accept arbitrary output directories for
fixtures and internal validation. Publication code must come through this
module so dataset identity and Text-Fabric schema version resolve to the single
repository-standard root.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from . import TF_VERSION, corpus, obabat, paths, releases


_DATASET_BUILDERS: dict[str, tuple[object, str]] = {
    "assyrian-royal-inscriptions": (corpus, "build_full_tf"),
    "obabat-atletters": (obabat, "build_tf"),
}


def build_registered_tf(
    output_base: Path | str,
    dataset: str,
    *,
    tf_version: str = TF_VERSION,
    data: Path = paths.DATA,
) -> tuple[Path, Any]:
    """Build one registered dataset into its canonical standalone TF root.

    Registration and builder support are checked separately so adding a dataset
    to ``datasets.toml`` without wiring a builder fails closed instead of
    silently publishing to an ad-hoc path. The current converter can publish
    only its own schema version; callers cannot relabel those bytes by choosing
    a different version directory.
    """
    config = releases.load_datasets(paths.ROOT / "datasets.toml")
    if dataset not in config:
        raise ValueError(f"unregistered dataset: {dataset!r}")
    if tf_version != TF_VERSION:
        raise ValueError(
            f"TF version {tf_version!r} does not match converter schema {TF_VERSION!r}"
        )

    target = _DATASET_BUILDERS.get(dataset)
    if target is None:
        raise RuntimeError(f"registered dataset has no publishable builder: {dataset!r}")
    module, builder_name = target

    root = paths.publishable_tf_root(output_base, dataset, tf_version)
    builder: Callable[..., Any] = getattr(module, builder_name)
    report = builder(root, data=Path(data))
    return root, report
