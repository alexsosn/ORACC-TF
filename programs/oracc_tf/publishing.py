"""Publishable dataset layout and registered build entry points.

Low-level corpus builders intentionally accept arbitrary output directories for
fixtures and internal validation. Publication code must come through this
module so dataset identity and Text-Fabric schema version resolve to the single
repository-standard root.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from . import TF_VERSION, corpus, paths, releases, translations


_DATASET_BUILDERS: dict[str, str] = {
    "assyrian-royal-inscriptions": "build_full_tf",
}


def build_registered_tf(
    output_base: Path | str,
    dataset: str,
    *,
    tf_version: str = TF_VERSION,
    data: Path = paths.DATA,
    translations_archive: Path | str | None = None,
) -> tuple[Path, Any]:
    """Build one registered dataset into its canonical standalone TF root.

    Registration and builder support are checked separately so adding a dataset
    to ``datasets.toml`` without wiring a builder fails closed instead of
    silently publishing to an ad-hoc path. The current converter can publish
    only its own schema version; callers cannot relabel those bytes by choosing
    a different version directory.

    The pinned M9 TEI archive is required. Supply it explicitly or set
    ``ORACC_TF_M9_TEI_ARCHIVE``; its pinned SHA-256 is checked before parsing.
    """
    config = releases.load_datasets(paths.ROOT / "datasets.toml")
    if dataset not in config:
        raise ValueError(f"unregistered dataset: {dataset!r}")
    if tf_version != TF_VERSION:
        raise ValueError(
            f"TF version {tf_version!r} does not match converter schema {TF_VERSION!r}"
        )

    builder_name = _DATASET_BUILDERS.get(dataset)
    if builder_name is None:
        raise RuntimeError(f"registered dataset has no publishable builder: {dataset!r}")

    archive = translations_archive
    if archive is None:
        archive = os.environ.get("ORACC_TF_M9_TEI_ARCHIVE")
    if archive is None or not str(archive).strip():
        raise ValueError(
            "registered TF builds require the pinned TEI archive; pass "
            "translations_archive or set ORACC_TF_M9_TEI_ARCHIVE"
        )
    translation_index = translations.parse_tei_archive(archive)

    root = paths.publishable_tf_root(output_base, dataset, tf_version)
    builder: Callable[..., Any] = getattr(corpus, builder_name)
    report = builder(
        root,
        data=Path(data),
        translations_by_document=translation_index.as_document_map(),
    )
    return root, report
