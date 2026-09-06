from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import distribution


DATASETS = Path(__file__).parents[1] / "datasets.toml"


def _minimal_tf(root: Path, *, marker: str = "one") -> Path:
    root.mkdir(parents=True)
    (root / "otype.tf").write_text("@node\n@valueType=str\n\nword\n", encoding="utf-8")
    (root / "oslots.tf").write_text("@edge\n\n1\t1\n", encoding="utf-8")
    (root / "otext.tf").write_text("@config\n@sectionTypes=word\n\n", encoding="utf-8")
    (root / "zero-span.json").write_text("{}\n", encoding="utf-8")
    (root / "feature.tf").write_text(f"@node\n\n{marker}\n", encoding="utf-8")
    return root


def test_registered_aggregate_dataset_maps_to_one_distribution_identity() -> None:
    identity = distribution.distribution_identity(
        "assyrian-royal-inscriptions", datasets_path=DATASETS
    )
    assert identity.dataset == "assyrian-royal-inscriptions"
    assert identity.repository == "ORACC-TF-assyrian-royal-inscriptions"
    assert len(identity.archives) == 11
    assert identity.repositories == ("ORACC-TF-assyrian-royal-inscriptions",)


def test_multiple_tf_versions_have_distinct_roots_without_changing_dataset_identity(tmp_path: Path) -> None:
    v1 = distribution.distribution_root(tmp_path, "assyrian-royal-inscriptions", "0.2.0")
    v2 = distribution.distribution_root(tmp_path, "assyrian-royal-inscriptions", "0.3.0-rc.1")
    assert v1 == tmp_path / "assyrian-royal-inscriptions" / "tf" / "0.2.0"
    assert v2 == tmp_path / "assyrian-royal-inscriptions" / "tf" / "0.3.0-rc.1"
    assert v1 != v2


def test_stage_distribution_is_minimal_deterministic_and_provenance_bound(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    stage = tmp_path / "stage"
    manifest = distribution.stage_distribution(
        source,
        stage,
        dataset="assyrian-royal-inscriptions",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "b" * 64,
    )
    assert manifest["dataset"] == "assyrian-royal-inscriptions"
    assert manifest["tf_version"] == "0.2.0"
    assert manifest["builder_commit"] == "a" * 40
    assert manifest["source_state"] == "sha256:" + "b" * 64
    assert manifest["tf_root"] == "assyrian-royal-inscriptions/tf/0.2.0"
    assert (stage / manifest["tf_root"] / "otype.tf").is_file()
    assert (stage / manifest["tf_root"] / "zero-span.json").is_file()
    assert not (stage / "data").exists()
    assert not (stage / "programs").exists()
    assert not (stage / "docs").exists()
    disk = json.loads((stage / "manifest.json").read_text(encoding="utf-8"))
    assert disk == manifest


def test_stage_distribution_rejects_unregistered_semantic_dataset(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    with pytest.raises(ValueError, match="unregistered dataset"):
        distribution.stage_distribution(
            source,
            tmp_path / "stage",
            dataset="not-registered",
            tf_version="0.2.0",
            builder_commit="a" * 40,
            source_state=None,
        )


def test_same_identity_same_bytes_is_idempotent_but_different_bytes_conflict(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    first = _minimal_tf(tmp_path / "first")
    kwargs = dict(
        dataset="assyrian-royal-inscriptions",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state="sha256:" + "b" * 64,
    )
    manifest1 = distribution.stage_distribution(first, stage, **kwargs)
    manifest2 = distribution.stage_distribution(first, stage, **kwargs)
    assert manifest1 == manifest2

    changed = _minimal_tf(tmp_path / "changed", marker="two")
    with pytest.raises(distribution.ImmutableDistributionConflict):
        distribution.stage_distribution(changed, stage, **kwargs)


def test_incomplete_warp_never_becomes_visible(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "otype.tf").write_text("@node\n\nword\n", encoding="utf-8")
    stage = tmp_path / "stage"
    with pytest.raises(distribution.InvalidDistribution):
        distribution.stage_distribution(
            source,
            stage,
            dataset="assyrian-royal-inscriptions",
            tf_version="0.2.0",
            builder_commit="a" * 40,
            source_state=None,
        )
    assert not (stage / "manifest.json").exists()


def test_unavailable_source_state_is_explicit_not_fabricated(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    manifest = distribution.stage_distribution(
        source,
        tmp_path / "stage",
        dataset="assyrian-royal-inscriptions",
        tf_version="0.2.0",
        builder_commit="a" * 40,
        source_state=None,
    )
    assert manifest["source_state"] is None
    assert manifest["provenance_complete"] is False


@pytest.mark.parametrize(
    "dataset",
    ["../escape", "/absolute", "riao/ria1", "RIAO", "a..b", ""],
)
def test_distribution_identity_rejects_unsafe_or_ambiguous_dataset_names(dataset: str) -> None:
    with pytest.raises(ValueError):
        distribution.repository_name(dataset)
