"""Issue #37 RED contract for explicit zero-sign sidecar-only artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata


def _edition(text_id: str, *, slotted: bool) -> loader.Edition:
    gdl = [{"v": "a", "utf8": "𒀀"}] if slotted else []
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
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
                        "form": "a" if slotted else "*",
                        "gdl": gdl,
                        "lang": "akk",
                        "cf": "ana",
                        "gw": "to",
                        "pos": "PRP",
                    },
                },
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


def _build_sidecar_only(target: Path, *, monkeypatch=None):
    if monkeypatch is not None:
        def forbidden_fabric(*args, **kwargs):
            raise AssertionError("Text-Fabric must not be instantiated for sidecar-only output")

        monkeypatch.setattr(corpus, "Fabric", forbidden_fabric)
    return corpus.build_tf(
        target,
        editions=(_edition("QZERO", slotted=False),),
        metadata_index=metadata.MetadataIndex.empty(),
        allow_sidecar_only=True,
    )


def _write_json(path: Path, value: object) -> bytes:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    path.write_bytes(payload)
    return payload


def test_zero_sign_build_remains_opt_in(tmp_path):
    with pytest.raises(
        corpus.CorpusBuildError,
        match="Text-Fabric warp cannot be emitted without at least one sign slot",
    ):
        corpus.build_tf(
            tmp_path,
            editions=(_edition("QZERO", slotted=False),),
            metadata_index=metadata.MetadataIndex.empty(),
        )


def test_sidecar_only_preserves_every_node_relation_without_tf(tmp_path, monkeypatch):
    report = _build_sidecar_only(tmp_path, monkeypatch=monkeypatch)

    assert report.signs == 0
    assert report.tf_node_counts == {"sign": 0}
    assert report.zero_span_counts == {
        "chunk": 1,
        "document": 1,
        "face": 1,
        "lex": 1,
        "line": 1,
        "word": 1,
    }
    assert not list(tmp_path.glob("*.tf"))
    assert not (tmp_path / ".tf").exists()

    sidecar = corpus.load_zero_span(tmp_path)
    node_keys = {node["key"] for node in sidecar["nodes"]}
    assert {
        node["otype"] for node in sidecar["nodes"]
    } == {"document", "face", "line", "chunk", "word", "lex"}
    assert "document:test/unit:QZERO" in node_keys
    assert "word:test/unit:QZERO:QZERO.l1" in node_keys

    edge_features = {edge["feature"] for edge in sidecar["edges"]}
    assert {"face_document", "line_face", "word_line", "word_lex"} <= edge_features
    for edge in sidecar["edges"]:
        assert edge["source"] in node_keys
        assert set(edge["targets"]) <= node_keys


def test_sidecar_only_manifest_is_hash_bound_and_explicit(tmp_path):
    _build_sidecar_only(tmp_path)

    manifest = corpus.load_artifact_manifest(tmp_path)
    sidecar_bytes = (tmp_path / corpus.ZERO_SPAN_FILENAME).read_bytes()
    assert manifest == {
        "schema": corpus.ARTIFACT_MANIFEST_SCHEMA,
        "kind": "sidecar-only",
        "tf_loadable": False,
        "tf_version": corpus.TF_VERSION,
        "slot_type": "sign",
        "slot_count": 0,
        "documents": ["test/unit:QZERO"],
        "sidecar": {
            "path": corpus.ZERO_SPAN_FILENAME,
            "schema": corpus.ZERO_SPAN_SCHEMA,
            "sha256": hashlib.sha256(sidecar_bytes).hexdigest(),
        },
    }

    (tmp_path / corpus.ZERO_SPAN_FILENAME).write_text("{}\n", encoding="utf-8")
    with pytest.raises(corpus.CorpusBuildError, match="sidecar SHA-256 mismatch"):
        corpus.load_artifact_manifest(tmp_path)


def test_manifest_rejects_document_identity_drift(tmp_path):
    _build_sidecar_only(tmp_path)
    manifest_path = tmp_path / corpus.ARTIFACT_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"] = ["test/unit:OTHER"]
    _write_json(manifest_path, manifest)

    with pytest.raises(corpus.CorpusBuildError, match="document identities.*sidecar"):
        corpus.load_artifact_manifest(tmp_path)


def test_manifest_rejects_dangling_sidecar_relation(tmp_path):
    _build_sidecar_only(tmp_path)
    sidecar_path = tmp_path / corpus.ZERO_SPAN_FILENAME
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    sidecar["edges"][0]["targets"].append("word:test/unit:QZERO:missing")
    sidecar_bytes = _write_json(sidecar_path, sidecar)

    manifest_path = tmp_path / corpus.ARTIFACT_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sidecar"]["sha256"] = hashlib.sha256(sidecar_bytes).hexdigest()
    _write_json(manifest_path, manifest)

    with pytest.raises(corpus.CorpusBuildError, match="dangling sidecar relation"):
        corpus.load_artifact_manifest(tmp_path)


def test_sidecar_only_bytes_are_deterministic(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    _build_sidecar_only(left)
    _build_sidecar_only(right)

    for name in (corpus.ZERO_SPAN_FILENAME, corpus.ARTIFACT_MANIFEST_FILENAME):
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_load_tf_rejects_sidecar_only_artifact_explicitly(tmp_path):
    _build_sidecar_only(tmp_path)

    with pytest.raises(
        corpus.CorpusBuildError,
        match="sidecar-only artifact.*not loadable as Text-Fabric",
    ):
        corpus.load_tf(tmp_path)


@pytest.mark.parametrize("stale", ["otype.tf", ".tf"])
def test_sidecar_only_rejects_stale_tf_artifacts(tmp_path, stale):
    target = tmp_path / "out"
    target.mkdir()
    stale_path = target / stale
    if stale == ".tf":
        stale_path.mkdir()
    else:
        stale_path.write_text("stale\n", encoding="utf-8")

    with pytest.raises(corpus.CorpusBuildError, match="sidecar-only.*Text-Fabric"):
        _build_sidecar_only(target)


def test_opt_in_does_not_change_nonzero_tf_output(tmp_path):
    default_dir = tmp_path / "default"
    opt_in_dir = tmp_path / "opt-in"
    edition = _edition("QSLOT", slotted=True)

    corpus.build_tf(
        default_dir,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    corpus.build_tf(
        opt_in_dir,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
        allow_sidecar_only=True,
    )

    assert not (default_dir / corpus.ARTIFACT_MANIFEST_FILENAME).exists()
    assert not (opt_in_dir / corpus.ARTIFACT_MANIFEST_FILENAME).exists()
    default_files = sorted(path.name for path in default_dir.iterdir() if path.is_file())
    opt_in_files = sorted(path.name for path in opt_in_dir.iterdir() if path.is_file())
    assert default_files == opt_in_files
    for name in default_files:
        assert (default_dir / name).read_bytes() == (opt_in_dir / name).read_bytes()
