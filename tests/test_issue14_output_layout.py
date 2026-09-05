"""Issue #14 — canonical publishable Text-Fabric output layout.

These tests intentionally land before the layout implementation.  The core
``build_tf(out_dir)`` serializer remains location-agnostic; this contract adds
one canonical publication/discovery root around it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths, releases


DATASET = "assyrian-royal-inscriptions"


def _edition(text_id: str = "QTEST") -> loader.Edition:
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": ""},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {
                            "form": "a",
                            "gdl": [{"v": "a", "utf8": "𒀀"}],
                        },
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path(f"/test/unit/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def _archive(name: str, byte: str) -> releases.ArchiveVersion:
    return releases.ArchiveVersion(
        name=name,
        sha256=byte * 64,
        oracc_utc_timestamp="2026-09-05T00:00:00",
    )


def test_canonical_root_has_dataset_tf_version_boundary(tmp_path):
    assert paths.dataset_tf_root(tmp_path, DATASET, "1.2.3") == (
        tmp_path / DATASET / "tf" / "1.2.3"
    )
    assert paths.dataset_tf_root(tmp_path, DATASET, "1.2.3-rc.1+build.5") == (
        tmp_path / DATASET / "tf" / "1.2.3-rc.1+build.5"
    )


@pytest.mark.parametrize(
    "dataset",
    ["", "../escape", "a/b", "a\\b", ".", "Assyrian-Royal-Inscriptions"],
)
def test_canonical_root_rejects_unsafe_or_ambiguous_dataset_ids(tmp_path, dataset):
    with pytest.raises(releases.ReleaseModelError):
        paths.dataset_tf_root(tmp_path, dataset, "1.2.3")


@pytest.mark.parametrize(
    "version",
    ["", "1", "1.2", "v1.2.3", "01.2.3", "../1.2.3", "1.2.3/x", "1.2.3\\x"],
)
def test_canonical_root_rejects_unsafe_or_non_semver_versions(tmp_path, version):
    with pytest.raises(releases.ReleaseModelError):
        paths.dataset_tf_root(tmp_path, DATASET, version)


def test_source_state_never_changes_stable_dataset_version_root(tmp_path):
    left = releases.ReleaseIdentity.from_archives(
        DATASET, "1.2.3", (_archive("riao-ria1", "a"),)
    )
    right = releases.ReleaseIdentity.from_archives(
        DATASET, "1.2.3", (_archive("riao-ria1", "b"),)
    )
    assert left.source_digest != right.source_digest
    assert left.tag != right.tag

    assert paths.dataset_tf_root(tmp_path, left.dataset, left.tf_version) == (
        paths.dataset_tf_root(tmp_path, right.dataset, right.tf_version)
    )
    assert "oracc" not in paths.dataset_tf_root(
        tmp_path, left.dataset, left.tf_version
    ).as_posix()


def test_registered_dataset_build_is_standalone_and_sidecar_is_version_local(tmp_path):
    config = releases.load_datasets(paths.ROOT / "datasets.toml")
    assert DATASET in config

    corpus.build_dataset_tf(
        tmp_path,
        DATASET,
        "1.2.3",
        editions=(_edition(),),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    root = paths.dataset_tf_root(tmp_path, DATASET, "1.2.3")

    assert {"otype.tf", "oslots.tf", "otext.tf"} <= {
        path.name for path in root.iterdir()
    }
    assert (root / corpus.ZERO_SPAN_FILENAME).is_file()

    api = corpus.load_tf(root)
    assert api.F.otype.s("sign") == (1,)
    assert api.F.form.v(api.F.otype.s("word")[0]) == "a"


def test_two_tf_versions_coexist_without_dataset_identity_collision(tmp_path):
    for version in ("1.2.3", "2.0.0-rc.1"):
        corpus.build_dataset_tf(
            tmp_path,
            DATASET,
            version,
            editions=(_edition(version.replace(".", "")),),
            metadata_index=metadata.MetadataIndex.empty(),
        )

    first = paths.dataset_tf_root(tmp_path, DATASET, "1.2.3")
    second = paths.dataset_tf_root(tmp_path, DATASET, "2.0.0-rc.1")
    assert first != second
    assert first.parent == second.parent == tmp_path / DATASET / "tf"
    assert (first / "otype.tf").is_file()
    assert (second / "otype.tf").is_file()
    assert corpus.load_tf(first).F.otype.s("sign") == (1,)
    assert corpus.load_tf(second).F.otype.s("sign") == (1,)
