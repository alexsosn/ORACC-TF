"""Issue #14 — publishable Text-Fabric output layout contract.

The filesystem identity is ``<base>/<dataset>/tf/<tf_version>/``. Dataset
identity, TF schema version, and upstream/source state remain distinct.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import TF_VERSION, corpus, loader, metadata, paths, publishing, releases


def _edition() -> loader.Edition:
    text_id = "Q000001"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {"node": "d", "type": "line-start", "ref": f"{text_id}.1", "label": "1"},
                {
                    "node": "l",
                    "id": f"{text_id}.l1",
                    "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                },
            ],
        }],
    }
    return loader.Edition(
        subproject="fixture",
        text_id=text_id,
        path=Path(f"/fixture/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def test_publishable_root_uses_dataset_tf_version_boundary(tmp_path):
    root = paths.publishable_tf_root(
        tmp_path, "assyrian-royal-inscriptions", "0.2.0"
    )
    assert root == tmp_path / "assyrian-royal-inscriptions" / "tf" / "0.2.0"


def test_source_state_is_not_part_of_stable_root(tmp_path):
    first = paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", "0.2.0")
    second = paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", "0.2.0")
    assert first == second


def test_multiple_tf_versions_coexist_without_identity_collision(tmp_path):
    v1 = paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", "0.2.0")
    v2 = paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", "0.3.0-rc.1")
    assert v1 != v2
    assert v1.parent == v2.parent == tmp_path / "assyrian-royal-inscriptions" / "tf"


@pytest.mark.parametrize(
    "dataset",
    ["", "../escape", "a/b", "/absolute", "Assyrian Royal Inscriptions", ".hidden"],
)
def test_unsafe_or_ambiguous_dataset_identifiers_are_rejected(tmp_path, dataset):
    with pytest.raises(ValueError):
        paths.publishable_tf_root(tmp_path, dataset, "0.2.0")


@pytest.mark.parametrize(
    "version",
    ["", "2", "0.2", "v0.2.0", "../0.2.0", "0.2.0/other", "/0.2.0", "01.2.3"],
)
def test_unsafe_or_non_semver_tf_versions_are_rejected(tmp_path, version):
    with pytest.raises(ValueError):
        paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", version)


def test_every_registered_dataset_has_a_distinct_publishable_root(tmp_path):
    config = releases.load_datasets(paths.ROOT / "datasets.toml")
    roots = {
        dataset: paths.publishable_tf_root(tmp_path, dataset, TF_VERSION)
        for dataset in config
    }
    assert len(set(roots.values())) == len(config)
    assert all(root.parts[-2] == "tf" for root in roots.values())
    assert all(root.name == TF_VERSION for root in roots.values())


def test_registered_builder_resolves_the_canonical_root(tmp_path, monkeypatch):
    calls = []
    sentinel = object()

    def fake_build(out_dir, *, data):
        calls.append((Path(out_dir), Path(data)))
        return sentinel

    monkeypatch.setattr(corpus, "build_full_tf", fake_build)
    root, report = publishing.build_registered_tf(
        tmp_path, "assyrian-royal-inscriptions", tf_version=TF_VERSION
    )

    assert root == paths.publishable_tf_root(
        tmp_path, "assyrian-royal-inscriptions", TF_VERSION
    )
    assert calls == [(root, paths.DATA)]
    assert report is sentinel


def test_registered_builder_rejects_unregistered_dataset(tmp_path):
    with pytest.raises(ValueError):
        publishing.build_registered_tf(tmp_path, "not-registered", tf_version=TF_VERSION)


def test_registered_builder_cannot_mislabel_the_converter_schema(tmp_path, monkeypatch):
    def should_not_build(*args, **kwargs):
        raise AssertionError("builder must not run for a mismatched TF schema version")

    monkeypatch.setattr(corpus, "build_full_tf", should_not_build)
    with pytest.raises(ValueError, match="TF version"):
        publishing.build_registered_tf(
            tmp_path, "assyrian-royal-inscriptions", tf_version="0.3.0"
        )


def test_version_root_is_standalone_loadable_and_owns_sidecar(tmp_path):
    root = paths.publishable_tf_root(tmp_path, "assyrian-royal-inscriptions", TF_VERSION)
    corpus.build_tf(root, editions=[_edition()], metadata_index=metadata.MetadataIndex.empty())

    assert {"otype.tf", "oslots.tf", "otext.tf", "zero-span.json"} <= {
        path.name for path in root.iterdir()
    }
    api = corpus.load_tf(root)
    assert api.F.otype.maxSlot == 1
