"""Adversarial hardening contracts for issue #71 Phase A."""

from __future__ import annotations

from pathlib import Path

import pytest
from tf.app import use

from oracc_tf import TF_VERSION, corpus, distribution, loader, metadata
from oracc_tf import app_generation


DATASET = "assyrian-royal-inscriptions"
BUILDER_COMMIT = "a" * 40
SOURCE_STATE = "sha256:" + "b" * 64


def _edition(text_id: str = "QHARDEN") -> loader.Edition:
    return loader.Edition(
        subproject="fixture",
        text_id=text_id,
        path=Path(f"/fixture/corpusjson/{text_id}.json"),
        doc={
            "type": "cdl",
            "textid": text_id,
            "cdl": [
                {
                    "node": "c",
                    "type": "text",
                    "id": f"{text_id}.U0",
                    "cdl": [
                        {"node": "d", "type": "surface", "ref": "obv", "label": "obv"},
                        {"node": "d", "type": "line-start", "ref": f"{text_id}.1", "label": "1"},
                        {
                            "node": "l",
                            "id": f"{text_id}.l1",
                            "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                        },
                    ],
                }
            ],
        },
        word_count=1,
    )


def _tf_root(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    corpus.build_tf(
        root,
        editions=[_edition()],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    return root


def _datasets(path: Path) -> Path:
    path.write_text(f"[{DATASET}]\narchives = [\"fixture\"]\n", encoding="utf-8")
    return path


def _source_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*.tf"))
        if path.is_file()
    }


@pytest.mark.parametrize("layout", ("same", "target-inside-source", "source-inside-target"))
def test_generator_rejects_source_target_overlap_without_mutating_tf_source(tmp_path, layout):
    datasets = _datasets(tmp_path / "datasets.toml")

    if layout == "source-inside-target":
        target = tmp_path / "container"
        source = target / "tf-source"
        corpus.build_tf(
            source,
            editions=[_edition()],
            metadata_index=metadata.MetadataIndex.empty(),
        )
    else:
        source = _tf_root(tmp_path)
        target = source if layout == "same" else source / "app"

    before = _source_bytes(source)
    with pytest.raises(app_generation.AppGenerationError, match="overlap|inside|source|target"):
        app_generation.generate_app(
            source,
            target,
            dataset=DATASET,
            tf_version=TF_VERSION,
            datasets_path=datasets,
        )
    assert source.is_dir()
    assert _source_bytes(source) == before


def test_generator_rejects_present_but_unloadable_warp_without_mutating_source(tmp_path):
    datasets = _datasets(tmp_path / "datasets.toml")
    source = tmp_path / "malformed"
    source.mkdir()
    (source / "otype.tf").write_text("@node\n@valueType=str\n\nnot-a-valid-otype\n", encoding="utf-8")
    (source / "oslots.tf").write_text("@edge\n\nnot-a-valid-edge\n", encoding="utf-8")
    (source / "otext.tf").write_text("@config\n@sectionTypes=document\n@sectionFeatures=document\n\n", encoding="utf-8")
    before = _source_bytes(source)

    with pytest.raises(app_generation.AppGenerationError, match="load|valid|TF|warp"):
        app_generation.generate_app(
            source,
            tmp_path / "app",
            dataset=DATASET,
            tf_version=TF_VERSION,
            datasets_path=datasets,
        )

    assert _source_bytes(source) == before
    assert not (source / ".tf").exists(), "validation must not write a Text-Fabric cache into source"


def test_manifest_owned_stage_is_discoverable_from_canonical_app_path_without_local_overrides(tmp_path):
    datasets = _datasets(tmp_path / "datasets.toml")
    source = _tf_root(tmp_path)
    generated = app_generation.generate_app(
        source,
        tmp_path / "generated-app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
    )
    stage = tmp_path / "stage"
    distribution.stage_distribution(
        source,
        stage,
        dataset=DATASET,
        release_id="release-a",
        tf_version=TF_VERSION,
        builder_commit=BUILDER_COMMIT,
        source_state=SOURCE_STATE,
        support_roots={"app": generated},
    )

    app = use(f"app:{stage / 'app'}", silent="deep")
    assert app is not None
    assert app.api is not None
    assert app.api.F.otype.maxSlot == 1
    assert app.context.version == TF_VERSION
    assert Path(app.context.appPath).resolve() == (stage / "app").resolve()
