"""RED-first source-semantic gates for the isolated ETCSRI TF vertical slice.

These assertions exercise real checked-in editions, never fabricated ORACC text.
No ETCSRI dataset is considered complete/publishable by these two witnesses.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest
from tf.fabric import Fabric

from oracc_tf import etcsri, gdl, paths


Q935 = paths.DATA / "etcsri/corpusjson/Q000935.json"
Q376 = paths.DATA / "etcsri/corpusjson/Q000376.json"


def _source(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _words(doc: dict) -> list[dict]:
    out: list[dict] = []
    def walk(node: dict) -> None:
        if node.get("node") == "l":
            out.append(node)
        for child in node.get("cdl", []):
            walk(child)
    for child in doc["cdl"]:
        walk(child)
    return out


def _source_sign_count(doc: dict) -> int:
    return sum(
        len(tuple(gdl.signs(word["f"].get("gdl", []), word_id=word["id"])))
        for word in _words(doc)
    )


def _api(root: Path):
    tf = Fabric(locations=str(root), silent="deep")
    assert tf.loadAll(silent="deep")
    return tf.api


@pytest.mark.corpus
def test_etcsri_real_morphology_is_separately_queryable_and_roundtrips(tmp_path: Path) -> None:
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[Q935])
    api = _api(tmp_path / "tf")
    words = {api.F.source_id.v(n): n for n in api.F.otype.s("word")}
    assert report.words == 7
    assert report.lines == 4
    assert report.sentences == 1
    assert report.semantic_signs == _source_sign_count(_source(Q935))
    assert len(words) == 7
    king = words["Q000935.l04855"]
    assert api.F.base.v(king) == "ur-{d}namma"
    assert api.F.morph.v(king) == "N1=Urnammak"
    assert api.F.morph2.v(king) == "N1=NAME"
    assert api.F.form.v(king) == "ur-{d}namma"
    assert api.F.document_key.v(king) == "etcsri:Q000935"
    source_words = {n["id"]: n for n in _words(_source(Q935))}
    for word_id, node in words.items():
        source = source_words[word_id]
        assert json.loads(api.F.f_json.v(node)) == source["f"]
        assert json.loads(api.F.props_json.v(node)) == source["props"]
        if "para" in source:
            assert json.loads(api.F.para_json.v(node)) == source["para"]
        else:
            assert api.F.para_json.v(node) is None
    assert len(api.F.otype.s("discourse")) == 1
    assert len(api.F.otype.s("sentence")) == 1
    first_line = next(n for n in api.F.otype.s("line")
                      if api.F.line.v(n) == "Q000935.1")
    enclosing = api.E.line_chunk.f(first_line)
    assert len(enclosing) == 1
    assert api.F.otype.v(enclosing[0]) == "sentence"
    assert api.F.source_id.v(enclosing[0]) == "Q000935.U2"


@pytest.mark.corpus
def test_etcsri_determinative_wrapper_is_not_second_sign_slot(tmp_path: Path) -> None:
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[Q935])
    api = _api(tmp_path / "tf")
    words = {api.F.source_id.v(n): n for n in api.F.otype.s("word")}
    king = words["Q000935.l04855"]
    signs = api.L.d(king, otype="sign")
    assert len(signs) == 3   # ur, semantic {d}, namma
    assert report.semantic_signs == 14
    assert len(api.F.otype.s("sign")) == report.semantic_signs + report.synthetic_slots
    pre = [
        node for node in api.F.otype.s("determinative")
        if api.F.det_kind.v(node) == "semantic"
        and api.F.det_pos.v(node) == "pre"
        and api.F.document_key.v(node) == "etcsri:Q000935"
        and "l04855/gdl[1]" in api.F.src_path.v(node)
    ]
    assert len(pre) == 1
    owned = api.E.det_sign.f(pre[0])
    assert len(owned) == 1 and api.F.utf8.v(owned[0]) == "𒀭"
    assert api.F.src_path.v(owned[0]).endswith("/gdl[1]/seq[0]")
    assert json.loads(api.F.det_json.v(pre[0]))["det"] == "semantic"


@pytest.mark.corpus
def test_etcsri_source_sentence_phrase_para_and_lines_are_not_lost(tmp_path: Path) -> None:
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[Q935, Q376])
    api = _api(tmp_path / "tf")
    assert report.documents == 2
    assert report.words == 293
    assert report.sentences == 52
    assert report.phrases == 17
    assert report.lines == 132
    assert report.semantic_signs == (
        _source_sign_count(_source(Q935)) + _source_sign_count(_source(Q376))
    )
    assert len(api.F.otype.s("sentence")) == 52
    assert len(api.F.otype.s("phrase")) == 17
    assert len(api.F.otype.s("line")) == 132
    para_source = next(n for n in _words(_source(Q376)) if n.get("para"))
    node = next(
        n for n in api.F.otype.s("word")
        if api.F.source_id.v(n) == para_source["id"]
    )
    assert json.loads(api.F.para_json.v(node)) == para_source["para"]
    assert api.F.document_key.v(node) == "etcsri:Q000376"
    assert len(api.L.u(node, otype="sentence")) >= 1
    # Distinct structural parent relations must be explicit, not inferred from morphology.
    assert api.E.chunk_parent.f(next(iter(api.F.otype.s("sentence"))))


@pytest.mark.corpus
def test_etcsri_rebuild_produces_identical_feature_bytes(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    etcsri.build_tf(first, source_paths=[Q935])
    etcsri.build_tf(second, source_paths=[Q935])
    a = {p.name: sha256(p.read_bytes()).hexdigest() for p in first.glob("*.tf")}
    b = {p.name: sha256(p.read_bytes()).hexdigest() for p in second.glob("*.tf")}
    assert a and a == b


def test_etcsri_unknown_cdl_shape_fails_closed(tmp_path: Path) -> None:
    doc = _source(Q935)
    doc["cdl"][0]["cdl"][0]["cdl"].insert(
        0, {"node": "d", "type": "unrecognized-glyph-control"}
    )
    fake = tmp_path / "Q000935.json"
    fake.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="unknown|unsupported"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[fake])


def test_etcsri_missing_morph2_is_preserved_as_absence_not_invented(tmp_path: Path) -> None:
    doc = _source(Q935)
    next(n for n in _words(doc) if n["id"] == "Q000935.l04855")["f"].pop("morph2")
    fake = tmp_path / "Q000935.json"
    fake.write_text(json.dumps(doc), encoding="utf-8")
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[fake])
    assert report.words == 7
    api = _api(tmp_path / "tf")
    node = next(n for n in api.F.otype.s("word")
                if api.F.source_id.v(n) == "Q000935.l04855")
    assert api.F.morph.v(node) == "N1=Urnammak"
    assert api.F.morph2.v(node) is None
    assert json.loads(api.F.f_json.v(node)) == next(
        n["f"] for n in _words(doc) if n["id"] == "Q000935.l04855"
    )


def test_etcsri_duplicate_chunk_identity_fails_closed(tmp_path: Path) -> None:
    doc = _source(Q935)
    sentence = doc["cdl"][0]["cdl"][0]["cdl"][0]
    sentence["id"] = doc["cdl"][0]["id"]
    fake = tmp_path / "Q000935.json"
    fake.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="duplicate chunk"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[fake])


def test_etcsri_zero_sign_word_uses_nontextual_anchor_not_fabricated_sign(tmp_path: Path) -> None:
    doc = _source(Q935)
    first_word = next(n for n in _words(doc) if n["id"] == "Q000935.l04855")
    first_word["f"]["gdl"] = []
    fake = tmp_path / "Q000935.json"
    fake.write_text(json.dumps(doc), encoding="utf-8")
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[fake])
    assert report.synthetic_slots == 1
    assert report.semantic_signs == _source_sign_count(doc)
    api = _api(tmp_path / "tf")
    node = next(n for n in api.F.otype.s("word")
                if api.F.source_id.v(n) == "Q000935.l04855")
    slots = api.L.d(node, otype="sign")
    assert len(slots) == 1
    assert api.F.synthetic.v(slots[0]) == 1
    assert api.F.utf8.v(slots[0]) is None


def test_etcsri_unknown_gdl_shape_fails_closed(tmp_path: Path) -> None:
    doc = _source(Q935)
    first_word = next(n for n in _words(doc) if n["id"] == "Q000935.l04855")
    first_word["f"]["gdl"] = [{"unknown_sign_shape": "unreadable"}]
    fake = tmp_path / "Q000935.json"
    fake.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="unsupported GDL"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[fake])


def test_etcsri_rejects_nonempty_output_to_avoid_stale_tf_features(tmp_path: Path) -> None:
    output = tmp_path / "tf"
    output.mkdir()
    (output / "stale-feature.tf").write_text("@node\\n", encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="non-empty|not empty"):
        etcsri.build_tf(output, source_paths=[Q935])
    assert (output / "stale-feature.tf").is_file()


@pytest.mark.corpus
def test_etcsri_real_q000376_linkbase_is_preserved_without_word_or_sign_inflation(
    tmp_path: Path,
) -> None:
    """Actual corpusjson carries a top-level linkbase outside its CDL node grammar."""
    doc = _source(Q376)
    raw_links = [entry for entry in doc["cdl"] if "linkbase" in entry]
    assert len(raw_links) == 1
    assert len(raw_links[0]["linkbase"]) == 17
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[Q935, Q376])
    api = _api(tmp_path / "tf")
    node = next(
        n for n in api.F.otype.s("document")
        if api.F.document_key.v(n) == "etcsri:Q000376"
    )
    assert json.loads(api.F.linkbase_json.v(node)) == raw_links[0]["linkbase"]
    assert report.words == 293
    assert report.semantic_signs == (
        _source_sign_count(_source(Q935)) + _source_sign_count(doc)
    )


def test_etcsri_rejects_ambiguous_or_malformed_linkbase(tmp_path: Path) -> None:
    doc = _source(Q376)
    original = next(entry for entry in doc["cdl"] if "linkbase" in entry)
    doc["cdl"].append(original.copy())
    source = tmp_path / "Q000376.json"
    source.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="duplicate linkbase"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[source])

    doc["cdl"].pop()
    original["linkbase"] = {"links": "not the actual list"}
    source.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="linkbase"):
        etcsri.build_tf(tmp_path / "tf2", source_paths=[source])


@pytest.mark.corpus
def test_etcsri_real_document_provenance_survives_as_source_metadata(
    tmp_path: Path,
) -> None:
    report = etcsri.build_tf(tmp_path / "tf", source_paths=[Q935, Q376])
    assert report.documents == 2
    api = _api(tmp_path / "tf")
    documents = {
        api.F.document_key.v(n): n for n in api.F.otype.s("document")
    }
    for source in (Q935, Q376):
        doc = _source(source)
        node = documents[f"etcsri:{doc['textid']}"]
        expected = {key: value for key, value in doc.items() if key != "cdl"}
        assert json.loads(api.F.source_meta_json.v(node)) == expected
        assert api.F.source_url.v(node) == doc["source"]
        assert api.F.source_license_url.v(node) == doc["license-url"]
        assert api.F.source_timestamp.v(node) == doc["UTC-timestamp"]
        assert api.F.source_license.v(node) == doc["license"]


def test_etcsri_malformed_provenance_does_not_silently_coerce(tmp_path: Path) -> None:
    doc = _source(Q935)
    doc["UTC-timestamp"] = {"date": "not the actual source string"}
    path = tmp_path / "Q000935.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="UTC-timestamp"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[path])


def test_duplicate_real_line_identity_is_rejected_before_tf_save(tmp_path: Path) -> None:
    """Q000935 has four distinct source line refs; corrupt one into a collision."""
    doc = _source(Q935)
    stack = [doc]
    line_markers = []
    while stack:
        entry = stack.pop()
        if entry.get("node") == "d" and entry.get("type") == "line-start":
            line_markers.append(entry)
        stack.extend(reversed(entry.get("cdl", [])))
    assert len(line_markers) == 4
    assert len({m["ref"] for m in line_markers}) == 4
    line_markers[1]["ref"] = line_markers[0]["ref"]
    changed = tmp_path / "Q000935.json"
    changed.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(etcsri.ETCSRISourceError, match="duplicate line"):
        etcsri.build_tf(tmp_path / "tf", source_paths=[changed])
