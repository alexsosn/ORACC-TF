from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import distribution


DATASET = "assyrian-royal-inscriptions"


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
    return root


def _support(root: Path, name: str, filename: str) -> Path:
    support = root / name
    support.mkdir(parents=True)
    (support / filename).write_text(f"{name}\n", encoding="utf-8")
    return support


def _kwargs() -> dict[str, object]:
    return {
        "dataset": DATASET,
        "release_id": "release-a",
        "tf_version": "0.3.0",
        "builder_commit": "a" * 40,
        "source_state": "sha256:" + "1" * 64,
    }


def test_dedicated_distribution_root_does_not_repeat_dataset_identity(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "local-output" / DATASET

    manifest = distribution.stage_distribution(source, stage, **_kwargs())

    assert manifest["tf_root"] == "tf/0.3.0"
    assert (stage / "tf" / "0.3.0" / "otype.tf").is_file()
    assert not (stage / DATASET).exists()


def test_manifest_owned_app_and_docs_are_staged_at_repository_root(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    app = _support(tmp_path, "app-source", "config.yaml")
    docs = _support(tmp_path, "docs-source", "index.md")
    stage = tmp_path / "stage"

    manifest = distribution.stage_distribution(
        source,
        stage,
        support_roots={"app": app, "docs": docs},
        **_kwargs(),
    )

    assert manifest["schema_version"] == 4
    assert manifest["support_roots"]["app"]["path"] == "app"
    assert manifest["support_roots"]["docs"]["path"] == "docs"
    assert (stage / "app" / "config.yaml").read_text(encoding="utf-8") == "app-source\n"
    assert (stage / "docs" / "index.md").read_text(encoding="utf-8") == "docs-source\n"
    assert not (stage / DATASET / "app").exists()
    assert not (stage / DATASET / "docs").exists()


@pytest.mark.parametrize("name", ["app", "docs"])
def test_unowned_support_root_still_fails_closed(tmp_path: Path, name: str) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    distribution.stage_distribution(source, stage, **_kwargs())

    leaked = stage / name
    leaked.mkdir()
    (leaked / "foreign.txt").write_text("foreign\n", encoding="utf-8")

    with pytest.raises(distribution.InvalidDistribution):
        distribution.stage_distribution(source, stage, **_kwargs())
