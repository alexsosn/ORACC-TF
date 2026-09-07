from __future__ import annotations

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
def test_replay_rejects_forbidden_payload_added_to_existing_stage(
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

    with pytest.raises(distribution.InvalidDistribution, match="forbidden"):
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
