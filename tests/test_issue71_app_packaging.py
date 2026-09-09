"""Issue #71 — generated per-dataset Text-Fabric app packaging contracts.

These tests intentionally precede ``oracc_tf.app_generation``.  Phase A owns
only deterministic app generation/discovery and manifest-owned publication;
text-format, presentation, provenance-link, and browser E2E semantics remain in
issues #72-#75.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import pytest
import yaml
from tf.app import use

from oracc_tf import TF_VERSION, corpus, distribution, loader, metadata


DATASET = "assyrian-royal-inscriptions"
BUILDER_COMMIT = "a" * 40
SOURCE_STATE = "sha256:" + "b" * 64


def _app_generation():
    spec = importlib.util.find_spec("oracc_tf.app_generation")
    assert spec is not None, "issue #71 app generator has not been implemented"
    return importlib.import_module("oracc_tf.app_generation")


def _edition(text_id: str = "Q000001") -> loader.Edition:
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "obv", "label": "obv"},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="fixture",
        text_id=text_id,
        path=Path(f"/fixture/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def _tf_root(tmp_path: Path, version: str = TF_VERSION) -> Path:
    root = tmp_path / f"source-{version}"
    corpus.build_tf(
        root,
        editions=[_edition()],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    return root


def _datasets(path: Path, *names: str) -> Path:
    path.write_text(
        "\n".join(f"[{name}]\narchives = [\"fixture\"]" for name in names) + "\n",
        encoding="utf-8",
    )
    return path


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_registered_dataset_generates_minimal_deterministic_app_without_manual_tree(tmp_path):
    module = _app_generation()
    tf_root = _tf_root(tmp_path)
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)

    first = module.generate_app(
        tf_root,
        tmp_path / "app-a",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    second = module.generate_app(
        tf_root,
        tmp_path / "app-b",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )

    assert _tree_bytes(first) == _tree_bytes(second)
    assert set(_tree_bytes(first)) == {"config.yaml"}
    assert not (first / "app.py").exists()
    config = yaml.safe_load((first / "config.yaml").read_text(encoding="utf-8"))
    assert config == {
        "apiVersion": 3,
        "provenanceSpec": {
            "corpus": DATASET,
            "relative": "/tf",
            "version": TF_VERSION,
        },
    }


def test_generation_fails_closed_for_unregistered_dataset_or_missing_warp(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    tf_root = _tf_root(tmp_path)

    with pytest.raises(ValueError, match="unregistered"):
        module.generate_app(
            tf_root,
            tmp_path / "unknown-app",
            dataset="unknown-dataset",
            tf_version=TF_VERSION,
            datasets_path=datasets,
        )

    broken = tmp_path / "broken-tf"
    broken.mkdir()
    (broken / "otype.tf").write_text("@node\n", encoding="utf-8")
    with pytest.raises(ValueError, match="TF|warp|oslots|otext"):
        module.generate_app(
            broken,
            tmp_path / "broken-app",
            dataset=DATASET,
            tf_version=TF_VERSION,
            datasets_path=datasets,
        )


def test_override_is_narrow_and_cannot_replace_generated_identity(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    tf_root = _tf_root(tmp_path)

    app = module.generate_app(
        tf_root,
        tmp_path / "styled-app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
        override={"display_css": ".txtu { font-size: 1.1em; }\n"},
    )
    assert (app / "display.css").read_text(encoding="utf-8").startswith(".txtu")

    for bad in (
        {"unknown": "x"},
        {"apiVersion": 99},
        {"provenanceSpec": {"version": "9.9.9"}},
        {"display_css": "@import '../secret.css';\n"},
    ):
        with pytest.raises(ValueError):
            module.generate_app(
                tf_root,
                tmp_path / "bad-app",
                dataset=DATASET,
                tf_version=TF_VERSION,
                datasets_path=datasets,
                override=bad,
            )


def test_failed_regeneration_preserves_previous_valid_app(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    tf_root = _tf_root(tmp_path)
    target = tmp_path / "app"
    module.generate_app(
        tf_root,
        target,
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    before = _tree_bytes(target)

    with pytest.raises(ValueError):
        module.generate_app(
            tf_root,
            target,
            dataset=DATASET,
            tf_version=TF_VERSION,
            datasets_path=datasets,
            override={"apiVersion": 99},
        )
    assert _tree_bytes(target) == before


def test_second_registered_dataset_generates_independent_app_without_copying_first(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", "dataset-one", "dataset-two")
    tf_root = _tf_root(tmp_path)

    one = module.generate_app(
        tf_root,
        tmp_path / "app-one",
        dataset="dataset-one",
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    two = module.generate_app(
        tf_root,
        tmp_path / "app-two",
        dataset="dataset-two",
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    one_cfg = yaml.safe_load((one / "config.yaml").read_text(encoding="utf-8"))
    two_cfg = yaml.safe_load((two / "config.yaml").read_text(encoding="utf-8"))
    assert one_cfg["provenanceSpec"]["corpus"] == "dataset-one"
    assert two_cfg["provenanceSpec"]["corpus"] == "dataset-two"
    assert _tree_bytes(one) != _tree_bytes(two)


def test_generated_app_loads_through_supported_local_app_path(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    tf_root = _tf_root(tmp_path)
    app_root = module.generate_app(
        tf_root,
        tmp_path / "app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )

    app = use(
        f"app:{app_root}",
        locations=[str(tf_root)],
        modules=[""],
        silent="deep",
    )
    assert app is not None
    assert app.api is not None
    assert app.api.F.otype.maxSlot == 1
    assert app.context.version == TF_VERSION


def test_generated_app_is_manifest_owned_by_distribution_transaction(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    tf_root = _tf_root(tmp_path)
    app_root = module.generate_app(
        tf_root,
        tmp_path / "generated-app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    stage = tmp_path / "stage"
    manifest = distribution.stage_distribution(
        tf_root,
        stage,
        dataset=DATASET,
        release_id="release-a",
        tf_version=TF_VERSION,
        builder_commit=BUILDER_COMMIT,
        source_state=SOURCE_STATE,
        support_roots={"app": app_root},
    )

    assert (stage / "app" / "config.yaml").read_bytes() == (app_root / "config.yaml").read_bytes()
    assert manifest["support_roots"]["app"]["path"] == "app"
    assert manifest["releases"]["release-a"]["support_roots"]["app"] == manifest["support_roots"]["app"]


def test_new_release_replaces_stale_app_while_old_tf_version_remains_visible(tmp_path):
    module = _app_generation()
    datasets = _datasets(tmp_path / "datasets.toml", DATASET)
    source_v1 = _tf_root(tmp_path, TF_VERSION)
    source_v2 = tmp_path / "source-0.2.1"
    corpus.build_tf(
        source_v2,
        editions=[_edition("Q000002")],
        metadata_index=metadata.MetadataIndex.empty(),
    )

    app_v1 = module.generate_app(
        source_v1,
        tmp_path / "app-v1",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
        override={"display_css": ".old { display: block; }\n"},
    )
    stage = tmp_path / "stage"
    distribution.stage_distribution(
        source_v1,
        stage,
        dataset=DATASET,
        release_id="release-a",
        tf_version=TF_VERSION,
        builder_commit=BUILDER_COMMIT,
        source_state=SOURCE_STATE,
        support_roots={"app": app_v1},
    )

    app_v2 = module.generate_app(
        source_v2,
        tmp_path / "app-v2",
        dataset=DATASET,
        tf_version="0.2.1",
        datasets_path=datasets,
    )
    manifest = distribution.stage_distribution(
        source_v2,
        stage,
        dataset=DATASET,
        release_id="release-b",
        tf_version="0.2.1",
        builder_commit="c" * 40,
        source_state="sha256:" + "d" * 64,
        support_roots={"app": app_v2},
    )

    assert (stage / "tf" / TF_VERSION / "otype.tf").is_file()
    assert (stage / "tf" / "0.2.1" / "otype.tf").is_file()
    assert not (stage / "app" / "display.css").exists()
    config = yaml.safe_load((stage / "app" / "config.yaml").read_text(encoding="utf-8"))
    assert config["provenanceSpec"]["version"] == "0.2.1"
    assert manifest["release_id"] == "release-b"
    assert manifest["visible_roots"] == {
        f"tf/{TF_VERSION}": "release-a",
        "tf/0.2.1": "release-b",
    }
