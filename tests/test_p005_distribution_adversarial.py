from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import distribution


def _minimal_tf(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "otype.tf").write_text(
        "@node\n@valueType=str\n\n1\tword\n2\tline\n", encoding="utf-8"
    )
    (root / "oslots.tf").write_text(
        "@edge\n@valueType=str\n\n1\n", encoding="utf-8"
    )
    (root / "otext.tf").write_text(
        "@config\n@sectionTypes=line\n@sectionFeatures=label\n", encoding="utf-8"
    )
    (root / "label.tf").write_text(
        "@node\n@valueType=str\n\n2\t1\n", encoding="utf-8"
    )
    (root / "feature.tf").write_text(
        "@node\n@valueType=str\n\n1\tone\n", encoding="utf-8"
    )
    return root


@pytest.mark.parametrize(
    "relative",
    [
        Path("data"),
        Path("programs"),
        Path("docs"),
        Path("assyrian-royal-inscriptions") / "docs",
    ],
)
def test_replay_rejects_forbidden_or_unowned_payload_added_to_existing_stage(
    tmp_path: Path, relative: Path
) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    kwargs = dict(
        dataset="assyrian-royal-inscriptions",
        release_id="release-a",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "1" * 64,
    )
    distribution.stage_distribution(source, stage, **kwargs)

    leaked = stage / relative
    leaked.mkdir(parents=True)
    (leaked / "must-not-survive.txt").write_text("forbidden\n", encoding="utf-8")

    with pytest.raises(distribution.InvalidDistribution, match="forbidden|unowned"):
        distribution.stage_distribution(source, stage, **kwargs)


def test_replay_rejects_symlink_added_to_existing_stage(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    kwargs = dict(
        dataset="assyrian-royal-inscriptions",
        release_id="release-a",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "1" * 64,
    )
    distribution.stage_distribution(source, stage, **kwargs)

    (stage / "leaked-link").symlink_to(source / "feature.tf")

    with pytest.raises(distribution.InvalidDistribution, match="symlink"):
        distribution.stage_distribution(source, stage, **kwargs)


def test_preexisting_unowned_stage_content_fails_closed(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    stage.mkdir()
    marker = stage / "unknown.txt"
    marker.write_text("unowned\n", encoding="utf-8")

    with pytest.raises(distribution.InvalidDistribution, match="manifest"):
        distribution.stage_distribution(
            source,
            stage,
            dataset="assyrian-royal-inscriptions",
            release_id="release-a",
            tf_version="0.2.0",
            builder_commit="a" * 40,
            source_state="sha256:" + "1" * 64,
        )

    assert marker.read_text(encoding="utf-8") == "unowned\n"
    assert not (stage / "manifest.json").exists()


def test_preexisting_unowned_stage_symlink_is_not_dereferenced(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    stage.mkdir()
    link = stage / "leaked-link"
    link.symlink_to(source / "feature.tf")

    with pytest.raises(distribution.InvalidDistribution, match="symlink"):
        distribution.stage_distribution(
            source,
            stage,
            dataset="assyrian-royal-inscriptions",
            release_id="release-a",
            tf_version="0.2.0",
            builder_commit="a" * 40,
            source_state="sha256:" + "1" * 64,
        )

    assert link.is_symlink()
    assert not (stage / "manifest.json").exists()


def test_publish_does_not_delete_preexisting_backup_sibling(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    first = dict(
        dataset="assyrian-royal-inscriptions",
        release_id="release-a",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "1" * 64,
    )
    distribution.stage_distribution(source, stage, **first)
    original_manifest = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))

    foreign_backup = stage.with_name(stage.name + ".old")
    foreign_backup.mkdir()
    marker = foreign_backup / "foreign.txt"
    marker.write_text("must survive\n", encoding="utf-8")

    with pytest.raises(distribution.InvalidDistribution, match="backup"):
        distribution.stage_distribution(
            source,
            stage,
            dataset="assyrian-royal-inscriptions",
            release_id="release-b",
            tf_version="0.2.0",
            builder_commit="b" * 40,
            source_state="sha256:" + "2" * 64,
        )

    assert marker.read_text(encoding="utf-8") == "must survive\n"
    assert json.loads((stage / "manifest.json").read_text(encoding="utf-8")) == original_manifest


@pytest.mark.parametrize("layout", ["same", "stage-inside-source", "source-inside-stage"])
def test_source_and_stage_overlap_fails_before_recursive_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    if layout == "source-inside-stage":
        stage = tmp_path / "stage"
        source = _minimal_tf(stage / "source")
    else:
        source = _minimal_tf(tmp_path / "source")
        stage = source if layout == "same" else source / "stage"

    source_resolved = source.resolve()
    real_copytree = distribution.shutil.copytree

    def guarded_copytree(src: object, dst: object, *args: object, **kwargs: object):
        src_path = Path(src).resolve()
        dst_path = Path(dst).resolve(strict=False)
        if src_path == source_resolved and (
            dst_path == source_resolved or source_resolved in dst_path.parents
        ):
            raise AssertionError("recursive copy attempted")
        return real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(distribution.shutil, "copytree", guarded_copytree)

    with pytest.raises(distribution.InvalidDistribution, match="overlap"):
        distribution.stage_distribution(
            source,
            stage,
            dataset="assyrian-royal-inscriptions",
            release_id="release-a",
            tf_version="0.2.0",
            builder_commit="a" * 40,
            source_state="sha256:" + "1" * 64,
        )

    assert (source / "otype.tf").is_file()


def test_replay_rejects_unowned_content_added_to_valid_stage(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    kwargs = dict(
        dataset="assyrian-royal-inscriptions",
        release_id="release-a",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "1" * 64,
    )
    distribution.stage_distribution(source, stage, **kwargs)

    marker = stage / "notes.txt"
    marker.write_text("unowned payload\n", encoding="utf-8")

    with pytest.raises(distribution.InvalidDistribution, match="unowned"):
        distribution.stage_distribution(source, stage, **kwargs)

    assert marker.read_text(encoding="utf-8") == "unowned payload\n"


@pytest.mark.parametrize("mutation", ["missing", "directory"])
def test_replay_requires_root_readme_regular_file(tmp_path: Path, mutation: str) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    kwargs = dict(
        dataset="assyrian-royal-inscriptions",
        release_id="release-a",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "1" * 64,
    )
    distribution.stage_distribution(source, stage, **kwargs)

    readme = stage / "README.md"
    readme.unlink()
    if mutation == "directory":
        readme.mkdir()

    with pytest.raises(distribution.InvalidDistribution, match="README"):
        distribution.stage_distribution(source, stage, **kwargs)
