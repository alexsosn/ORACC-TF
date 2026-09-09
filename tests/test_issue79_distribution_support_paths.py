from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import distribution


DATASET = "assyrian-royal-inscriptions"


def _minimal_tf(root: Path, *, marker: str = "one") -> Path:
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
        f"@node\n@valueType=str\n\n1\t{marker}\n", encoding="utf-8"
    )
    return root


def _support(root: Path, name: str, filename: str, *, payload: str | None = None) -> Path:
    support = root / name
    support.mkdir(parents=True)
    (support / filename).write_text(payload or f"{name}\n", encoding="utf-8")
    return support


def _kwargs() -> dict[str, object]:
    return {
        "dataset": DATASET,
        "release_id": "release-a",
        "tf_version": "0.3.0",
        "builder_commit": "a" * 40,
        "source_state": "sha256:" + "1" * 64,
    }


def _release_kwargs(
    release_id: str, tf_version: str, marker: str
) -> dict[str, object]:
    return {
        "dataset": DATASET,
        "release_id": release_id,
        "tf_version": tf_version,
        "builder_commit": marker * 40,
        "source_state": "sha256:" + marker * 64,
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


@pytest.mark.parametrize("layout", ["same", "app-parent", "docs-parent"])
def test_typed_support_sources_must_be_pairwise_disjoint(
    tmp_path: Path, layout: str
) -> None:
    source = _minimal_tf(tmp_path / "source")
    shared = _support(tmp_path, "shared", "root.txt")
    if layout == "same":
        app = shared
        docs = shared
    elif layout == "app-parent":
        app = shared
        docs = _support(shared, "nested-docs", "index.md")
    else:
        docs = shared
        app = _support(shared, "nested-app", "config.yaml")

    with pytest.raises(distribution.InvalidDistribution, match="support.*overlap"):
        distribution.stage_distribution(
            source,
            tmp_path / "stage",
            support_roots={"app": app, "docs": docs},
            **_kwargs(),
        )


def test_current_support_digest_corruption_fails_closed(tmp_path: Path) -> None:
    source = _minimal_tf(tmp_path / "source")
    app = _support(tmp_path, "app-source", "config.yaml", payload="original\n")
    stage = tmp_path / "stage"
    distribution.stage_distribution(
        source, stage, support_roots={"app": app}, **_kwargs()
    )

    (stage / "app" / "config.yaml").write_text("corrupted\n", encoding="utf-8")

    with pytest.raises(distribution.ImmutableDistributionConflict, match="support"):
        distribution.stage_distribution(
            source, stage, support_roots={"app": app}, **_kwargs()
        )


def test_new_release_removes_stale_support_roots_but_keeps_ledger_digest(
    tmp_path: Path,
) -> None:
    first = _minimal_tf(tmp_path / "first", marker="one")
    second = _minimal_tf(tmp_path / "second", marker="two")
    app = _support(tmp_path, "app-source", "config.yaml")
    docs = _support(tmp_path, "docs-source", "index.md")
    stage = tmp_path / "stage"

    first_manifest = distribution.stage_distribution(
        first,
        stage,
        support_roots={"app": app, "docs": docs},
        **_release_kwargs("release-a", "0.2.0", "a"),
    )
    second_manifest = distribution.stage_distribution(
        second,
        stage,
        **_release_kwargs("release-b", "0.2.0", "b"),
    )

    assert second_manifest["support_roots"] == {}
    assert not (stage / "app").exists()
    assert not (stage / "docs").exists()
    assert second_manifest["releases"]["release-a"]["support_roots"] == first_manifest[
        "support_roots"
    ]


def test_failed_support_update_preserves_previous_visible_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = _minimal_tf(tmp_path / "first", marker="one")
    second = _minimal_tf(tmp_path / "second", marker="two")
    old_app = _support(tmp_path, "old-app", "config.yaml", payload="old\n")
    new_app = _support(tmp_path, "new-app", "config.yaml", payload="new\n")
    stage = tmp_path / "stage"
    distribution.stage_distribution(
        first,
        stage,
        support_roots={"app": old_app},
        **_release_kwargs("release-a", "0.2.0", "a"),
    )
    original_manifest = (stage / "manifest.json").read_bytes()
    original_app = (stage / "app" / "config.yaml").read_bytes()

    real_copytree = distribution.shutil.copytree

    def fail_new_support_copy(src: object, dst: object, *args: object, **kwargs: object):
        if Path(src) == new_app and Path(dst).name == "app":
            raise OSError("injected support-copy failure")
        return real_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr(distribution.shutil, "copytree", fail_new_support_copy)

    with pytest.raises(OSError, match="support-copy failure"):
        distribution.stage_distribution(
            second,
            stage,
            support_roots={"app": new_app},
            **_release_kwargs("release-b", "0.2.0", "b"),
        )

    assert (stage / "manifest.json").read_bytes() == original_manifest
    assert (stage / "app" / "config.yaml").read_bytes() == original_app
    assert json.loads(original_manifest)["release_id"] == "release-a"


def test_multiple_tf_versions_coexist_while_support_tracks_only_current_release(
    tmp_path: Path,
) -> None:
    first = _minimal_tf(tmp_path / "first", marker="one")
    second = _minimal_tf(tmp_path / "second", marker="two")
    app = _support(tmp_path, "app-source", "config.yaml")
    docs = _support(tmp_path, "docs-source", "index.md")
    stage = tmp_path / "stage"

    release_a = distribution.stage_distribution(
        first,
        stage,
        support_roots={"app": app},
        **_release_kwargs("release-a", "0.2.0", "a"),
    )
    release_b = distribution.stage_distribution(
        second,
        stage,
        support_roots={"docs": docs},
        **_release_kwargs("release-b", "0.3.0", "b"),
    )

    assert release_b["visible_roots"] == {
        "tf/0.2.0": "release-a",
        "tf/0.3.0": "release-b",
    }
    assert (stage / "tf" / "0.2.0" / "otype.tf").is_file()
    assert (stage / "tf" / "0.3.0" / "otype.tf").is_file()
    assert release_b["support_roots"] == release_b["releases"]["release-b"][
        "support_roots"
    ]
    assert release_b["releases"]["release-a"]["support_roots"] == release_a[
        "support_roots"
    ]
    assert not (stage / "app").exists()
    assert (stage / "docs" / "index.md").is_file()

    replay = distribution.stage_distribution(
        first,
        stage,
        support_roots={"app": app},
        **_release_kwargs("release-a", "0.2.0", "a"),
    )
    assert replay["release_id"] == "release-b"
    assert not (stage / "app").exists()
    assert (stage / "docs" / "index.md").is_file()
