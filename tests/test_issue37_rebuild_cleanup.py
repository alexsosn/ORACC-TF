"""Review regressions for rebuilding an issue-37 TF target in place."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata


def _edition(text_id: str, *, semantic_sign: bool) -> loader.Edition:
    word = {
        "node": "l",
        "id": f"{text_id}.l1",
        "f": {
            "form": "a" if semantic_sign else "*",
            "gdl": ([{"v": "a", "utf8": "𒀀"}] if semantic_sign else []),
        },
    }
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": "o"},
                {
                    "node": "d",
                    "type": "line-start",
                    "ref": f"{text_id}.1",
                    "label": "1",
                },
                word,
            ],
        }],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path(f"/test/unit/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def _build(target: Path, edition: loader.Edition):
    return corpus.build_tf(
        target,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )


def test_rebuild_removes_semantic_feature_files_absent_from_new_graph(tmp_path):
    _build(tmp_path, _edition("QOLD", semantic_sign=True))
    stale = ("utf8.tf", "readingu.tf", "sign_json.tf", "src_path.tf")
    assert all((tmp_path / name).exists() for name in stale)

    _build(tmp_path, _edition("QNEW", semantic_sign=False))

    assert all(not (tmp_path / name).exists() for name in stale)
    api = corpus.load_tf(tmp_path)
    assert not hasattr(api.F, "utf8")
    assert not hasattr(api.F, "readingu")
    assert not hasattr(api.F, "sign_json")
    assert {api.F.document.v(node) for node in api.F.otype.s("document")} == {
        "test/unit:QNEW"
    }


def test_rebuild_removes_stale_text_fabric_binary_cache(tmp_path):
    _build(tmp_path, _edition("QOLD", semantic_sign=True))
    corpus.load_tf(tmp_path)
    cache = tmp_path / ".tf"
    assert cache.exists(), "Text-Fabric load should materialise its binary cache"

    _build(tmp_path, _edition("QNEW", semantic_sign=False))

    assert not cache.exists()


def test_failed_rebuild_does_not_destroy_previous_valid_artifact(tmp_path, monkeypatch):
    _build(tmp_path, _edition("QOLD", semantic_sign=True))
    old_bytes = {
        path.name: path.read_bytes()
        for path in tmp_path.glob("*.tf")
    }
    assert "utf8.tf" in old_bytes

    def fail_save(*args, **kwargs):
        return False

    monkeypatch.setattr(corpus.Fabric, "save", fail_save)
    with pytest.raises(corpus.CorpusBuildError, match="Text-Fabric rejected"):
        _build(tmp_path, _edition("QNEW", semantic_sign=False))

    assert {
        path.name: path.read_bytes()
        for path in tmp_path.glob("*.tf")
    } == old_bytes
