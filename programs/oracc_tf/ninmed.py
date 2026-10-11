"""NINMED ORACC-only TF source experiment, independent of legacy Nino data.

This module does *not* derive from Nino-cunei/ninmed, copy its uniqueLemma
features, register a new dataset, or publish a release. It validates native
asbp/ninmed source identity and uses opt-in source-word preservation in the
existing Text-Fabric graph for the first two real-source witnesses.
"""

from __future__ import annotations

from pathlib import Path
import json
from typing import Iterable

from . import corpus, loader, metadata


class NINMEDSourceError(ValueError):
    """Native NINMED source bytes are not safe to represent without inference."""


def build_tf(
    out_dir: Path | str, *, source_paths: Iterable[Path | str]
) -> corpus.CorpusBuildReport:
    """Build an isolated, source-grounded TF sample from explicit ORACC files."""
    paths = sorted((Path(p) for p in source_paths), key=lambda p: p.as_posix())
    if not paths:
        raise NINMEDSourceError("NINMED conversion requires source files")

    editions: list[loader.Edition] = []
    seen: set[str] = set()
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise NINMEDSourceError(f"unreadable ORACC NINMED source {path}") from exc
        if not isinstance(doc, dict):
            raise NINMEDSourceError(f"{path}: source is not a JSON object")
        if doc.get("project") != "asbp/ninmed" or doc.get("type") != "cdl":
            raise NINMEDSourceError(f"{path}: wrong project or source type")
        text_id = doc.get("textid")
        if not isinstance(text_id, str) or not text_id.strip():
            raise NINMEDSourceError(f"{path}: missing native textid")
        if text_id in seen:
            raise NINMEDSourceError(f"{path}: duplicate native identity {text_id}")
        seen.add(text_id)
        try:
            count = loader.count_words(doc)
        except loader.SourceError as exc:
            raise NINMEDSourceError(f"{path}: invalid native CDL: {exc}") from exc
        editions.append(
            loader.Edition(
                subproject="asbp/ninmed",
                text_id=text_id,
                path=path,
                doc=doc,
                word_count=count,
            )
        )

    return corpus.build_tf(
        out_dir,
        editions=editions,
        metadata_index=metadata.MetadataIndex.empty(),
        dataset_title="ORACC-TF NINMED ORACC source vertical slice",
        preserve_source_word=True,
    )
