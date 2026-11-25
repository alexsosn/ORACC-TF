"""Convert a complete local ORACC project export with the existing TF graph.

The manifest is the authority for exported textual editions. Catalogue-only
members are metadata, not extra texts. There is no download or publication
side effect. This entry point is being validated first on AEMW/Amarna; other
CDL exports may need additional source-specific modeling.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
from typing import Iterator

from . import corpus, loader, metadata


class ProjectSourceError(ValueError):
    """An export is incomplete, ambiguous, or unsupported."""


def _read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ProjectSourceError(f"Missing or non-regular source file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectSourceError(f"Invalid source JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectSourceError(f"Source is not a JSON object: {path}")
    return data


def build_project(
    out_dir: Path | str, *, source_dir: Path | str, project: str
) -> corpus.CorpusBuildReport:
    """Build all editions named by a local corpus.json, without silent skips."""
    root = Path(source_dir).expanduser().resolve(strict=True)
    requested_output = Path(out_dir).expanduser()
    if requested_output.is_symlink():
        raise ProjectSourceError("TF output must not be a symbolic link")
    output = requested_output.resolve()
    if not root.is_dir():
        raise ProjectSourceError(f"Not an ORACC export directory: {root}")
    if output == root or output.is_relative_to(root) or root.is_relative_to(output):
        raise ProjectSourceError("TF output and source export must not overlap")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ProjectSourceError(f"TF output must be a new or empty directory: {output}")

    manifest = _read_json(root / "corpus.json")
    if manifest.get("type") != "corpus" or manifest.get("project") != project:
        raise ProjectSourceError(f"Expected corpus manifest for project {project!r}")
    members = manifest.get("members")
    if not isinstance(members, dict) or not members:
        raise ProjectSourceError("Corpus manifest contains no textual members")
    data = root / "corpusjson"
    if data.is_symlink() or not data.is_dir():
        raise ProjectSourceError("Missing regular corpusjson directory")
    sources: dict[str, Path] = {}
    for text_id, relative in sorted(members.items()):
        if (
            not isinstance(text_id, str)
            or not text_id
            or text_id in {".", ".."}
            or "/" in text_id
            or "\\" in text_id
            or relative != f"corpusjson/{text_id}.json"
        ):
            raise ProjectSourceError(f"Unsupported or unsafe member mapping: {text_id!r}: {relative!r}")
        path = data / f"{text_id}.json"
        if path.is_symlink() or not path.is_file():
            raise ProjectSourceError(f"Missing or non-regular edition: {path.name}")
        sources[text_id] = path
    extras = {p.name for p in data.glob("*.json")} - {p.name for p in sources.values()}
    if extras:
        raise ProjectSourceError(f"Unlisted corpusjson members: {', '.join(sorted(extras))}")

    catalogue = _read_json(root / "catalogue.json")
    index = metadata.MetadataIndex(metadata.index_catalogue(project, catalogue))

    def editions() -> Iterator[loader.Edition]:
        # Stream one edition at a time; keep only the graph in memory.
        for text_id, path in sources.items():
            doc = _read_json(path)
            if (
                doc.get("type") != "cdl"
                or doc.get("project") != project
                or doc.get("textid") != text_id
            ):
                raise ProjectSourceError(
                    f"{path.name}: expected CDL identity {project}:{text_id}, "
                    f"got {doc.get('project')!r}:{doc.get('textid')!r}"
                )
            try:
                count = loader.count_words(doc)
            except loader.SourceError as exc:
                raise ProjectSourceError(f"{path.name}: {exc}") from exc
            yield loader.Edition(project, text_id, path, doc, count)

    # Stage on the destination filesystem. A rejected source must not leave
    # apparently complete TF features at the requested destination.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".oracc-build-", dir=output.parent) as temp:
        stage = Path(temp) / "tf"
        report = corpus.build_tf(
            stage,
            editions=editions(),
            metadata_index=index,
            dataset_title=f"ORACC-TF {project}",
            preserve_source_word=True,
            preserve_source_document=True,
            preserve_source_markers=True,
        )
        if (
            report.documents != len(sources)
            or report.sign_word_membership_errors
            or report.word_line_membership_errors
            or report.section_path_errors
        ):
            raise ProjectSourceError(f"Source-to-TF conservation failed: {report.report()}")
        if output.exists():
            # rmdir refuses to delete any concurrently added user files.
            output.rmdir()
        stage.rename(output)
    return replace(
        report,
        source_members=len(sources),
        readable_source_members=len(sources),
        unreadable_source_members=0,
        source_hazards=(),
    )
