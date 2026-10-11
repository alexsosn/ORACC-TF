"""NINMED #33 RED: source-specific ORACC TF, not a Nino clone."""

from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import gdl, ninmed, paths, words


SOURCES = {
    "P285136": "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b",
    "P425685": "4df915aa78b3f701c77c7ee96b6b72708ce4eb29",
}


def primary(id: str) -> Path:
    path = paths.DATA / "asbp" / "ninmed" / "corpusjson" / f"{id}.json"
    payload = path.read_bytes()
    git_blob = sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()
    assert git_blob == SOURCES[id], f"NINMED witness {id} changed; re-review"
    return path


def _api(root: Path):
    tf = Fabric(locations=str(root), silent="deep")
    assert tf.loadAll(silent="deep")
    return tf.api


@pytest.mark.corpus
def test_real_ninmed_lexical_source_preservation_and_tf_query(tmp_path: Path) -> None:
    sources = [primary("P285136"), primary("P425685")]
    report = ninmed.build_tf(tmp_path / "tf", source_paths=sources)
    api = _api(tmp_path / "tf")
    assert report.documents == 2
    assert report.words == 376
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0

    nodes = {
        (api.F.document_key.v(n), api.F.source_id.v(n)): n
        for n in api.F.otype.s("word")
    }
    assert len(nodes) == 376
    example = nodes[("asbp/ninmed:P285136", "P285136.l003f2")]
    assert api.F.form.v(example) == "DU₃.DU₃.BI"
    assert api.F.cf.v(example) == "DÙ.DÙ.BI"
    assert api.F.gw.v(example) == "ritual (instructions)"
    assert api.F.pos.v(example) == "N"
    targets = api.E.word_lex.f(example)
    assert targets
    assert ("DÙ.DÙ.BI", "ritual (instructions)", "N") in {
        (api.F.cf.v(lex), api.F.gw.v(lex), api.F.pos.v(lex))
        for lex in targets
    }
    assert api.F.form.v(nodes[("asbp/ninmed:P425685", "P425685.l0fdd6")]) == "EN₂"
    assert "NINMED" in (tmp_path / "tf" / "otext.tf").read_text(encoding="utf-8")
    for path in sources:
        doc = json.loads(path.read_text(encoding="utf-8"))
        key = f"asbp/ninmed:{doc['textid']}"
        for word in words.source_words(doc):
            node = nodes[(key, word["id"])]
            assert json.loads(api.F.word_json.v(node)) == word
            assert api.F.document_key.v(node) == key
    expected_semantic_signs = sum(
        len(tuple(gdl.signs(word["f"].get("gdl", []), word_id=word["id"])))
        for source in sources
        for word in words.source_words(json.loads(source.read_text(encoding="utf-8")))
    )
    assert report.signs == expected_semantic_signs
    assert len(api.F.otype.s("sign")) == report.signs + report.synthetic_slots
    assert not (tmp_path / "tf" / "uniqueLemma.tf").exists()


def test_ninmed_rejects_foreign_project_before_output(tmp_path: Path) -> None:
    doc = json.loads(primary("P285136").read_text(encoding="utf-8"))
    doc["project"] = "riao/ria1"
    file = tmp_path / "P285136.json"
    file.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ninmed.NINMEDSourceError, match="project"):
        ninmed.build_tf(tmp_path / "tf", source_paths=[file])


def test_ninmed_does_not_invent_nino_lemma_analysis(tmp_path: Path) -> None:
    doc = json.loads(primary("P285136").read_text(encoding="utf-8"))
    first = next(words.source_words(doc))
    assert "uniqueLemma" not in first
    # Reference Nino uniqueLemma is not a substitute for ORACC cf/gw/pos.
    assert first["f"]["cf"] == "DÙ.DÙ.BI"
    assert first["f"]["gw"] == "ritual (instructions)"
    assert first["f"]["pos"] == "N"


@pytest.mark.corpus
def test_existing_assyrian_default_emits_no_ninmed_source_word_feature(
    tmp_path: Path,
) -> None:
    from oracc_tf import corpus, loader, metadata

    source = paths.DATA / "riao/ria1/corpusjson/Q001801.json"
    edition = loader.load_edition(source)
    root = tmp_path / "royal"
    report = corpus.build_tf(
        root,
        editions=[edition],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    assert report.documents == 1
    assert not (root / "word_json.tf").exists()
    assert "ORACC-TF RIAO + RINAP" in (root / "otext.tf").read_text(
        encoding="utf-8"
    )


@pytest.mark.corpus
def test_ninmed_document_source_license_timestamp_and_sha_are_queryable(
    tmp_path: Path,
) -> None:
    from hashlib import sha256

    sources = [primary("P285136"), primary("P425685")]
    ninmed.build_tf(tmp_path / "tf", source_paths=sources)
    api = _api(tmp_path / "tf")
    by_key = {
        api.F.document_key.v(n): n for n in api.F.otype.s("document")
    }
    for source in sources:
        doc = json.loads(source.read_text(encoding="utf-8"))
        node = by_key[f"asbp/ninmed:{doc['textid']}"]
        meta = {key: value for key, value in doc.items() if key != "cdl"}
        assert json.loads(api.F.document_meta_json.v(node)) == meta
        assert api.F.source_sha256.v(node) == sha256(source.read_bytes()).hexdigest()
        assert meta["license-url"].startswith("https://creativecommons.org/")
        assert meta["UTC-timestamp"].startswith("2024-07-05")
