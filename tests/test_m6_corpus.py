"""P-001 M6 - joined whole-corpus invariants and Text-Fabric warp load.

Acceptance criteria from P-001 §5 M6:
- 320,975 source words; 2,078 parseable documents / 1,845 populated / 233 stubs;
- composite document keys are unique;
- every sign belongs to exactly one word and every word to exactly one line;
- every populated document has a valid document/face/line section path;
- the M1 sign count stays pinned and Unicode coverage is frozen here;
- generated ``otype``/``oslots`` load cleanly in Text-Fabric;
- source entities with zero sign extent remain losslessly queryable in a
  deterministic sidecar because Text-Fabric warp nodes cannot have empty
  ``oslots``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths, words


def _edition(subproject: str, text_id: str, *, signless: bool = False) -> loader.Edition:
    source_words = []
    if signless:
        source_words.append({
            "node": "l",
            "id": f"{text_id}.l0",
            "f": {"form": "*", "gdl": []},
        })
    source_words.append({
        "node": "l",
        "id": f"{text_id}.l1",
        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
    })
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
                *source_words,
            ],
        }],
    }
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=len(source_words),
    )


def _mixed_span_edition(subproject: str, text_id: str) -> loader.Edition:
    """One zero-span line followed by a slotted line on the same face."""
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
                    "id": f"{text_id}.l0",
                    "f": {"form": "*", "gdl": []},
                },
                {
                    "node": "d",
                    "type": "line-start",
                    "ref": f"{text_id}.2",
                    "label": "2",
                },
                {
                    "node": "l",
                    "id": f"{text_id}.l1",
                    "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                },
            ],
        }],
    }
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=2,
    )


def _canonical_source_gdl(features: object) -> str | None:
    if not isinstance(features, dict) or "gdl" not in features:
        return None
    return json.dumps(
        features["gdl"],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def test_slotless_source_word_survives_losslessly_without_fabricated_slot(tmp_path):
    edition = _edition("test/unit", "QTEST", signless=True)
    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.documents == 1
    assert report.populated_documents == 1
    assert report.words == 2
    assert report.signs == 1
    assert report.slotless_words == 1
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    # Text-Fabric 13.1 has a hard warp invariant that every non-slot node maps
    # to at least one slot. The source word with an empty sign span therefore
    # must not be assigned an invented/borrowed sign just to enter otype/oslots.
    assert report.tf_words == 1
    assert report.zero_span_words == 1

    api = corpus.load_tf(tmp_path)
    word_nodes = api.F.otype.s("word")
    by_source = {api.F.source_id.v(node): node for node in word_nodes}
    assert set(by_source) == {"QTEST.l1"}
    assert api.T.sectionFromNode(1) == (
        "test/unit:QTEST",
        "QTEST.face.1",
        "QTEST.1",
    )

    zero_span = corpus.load_zero_span(tmp_path)
    nodes = [node for node in zero_span["nodes"] if node["otype"] == "word"]
    assert len(nodes) == 1
    slotless = nodes[0]
    assert slotless["features"]["source_id"] == "QTEST.l0"
    assert slotless["features"]["document_key"] == "test/unit:QTEST"
    assert slotless["features"]["gdl_json"] == "[]"

    relation_edges = [
        edge for edge in zero_span["edges"]
        if edge["source"] == slotless["key"] and edge["feature"] == "word_line"
    ]
    assert len(relation_edges) == 1
    assert len(relation_edges[0]["targets"]) == 1
    assert relation_edges[0]["targets"][0].endswith(":QTEST.1")


def test_persisted_gdl_distinguishes_absent_empty_and_null(tmp_path):
    absent = _edition("test/unit", "QABSENT", signless=True)
    empty = _edition("test/unit", "QEMPTY", signless=True)
    null = _edition("test/unit", "QNULL", signless=True)

    absent_word = absent.doc["cdl"][0]["cdl"][2]
    null_word = null.doc["cdl"][0]["cdl"][2]
    del absent_word["f"]["gdl"]
    null_word["f"]["gdl"] = None

    corpus.build_tf(
        tmp_path,
        editions=(absent, empty, null),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    zero_span = corpus.load_zero_span(tmp_path)
    by_document = {
        node["features"]["document_key"]: node["features"]
        for node in zero_span["nodes"]
        if node["otype"] == "word"
    }

    assert "gdl_json" not in by_document["test/unit:QABSENT"]
    assert by_document["test/unit:QEMPTY"]["gdl_json"] == "[]"
    assert by_document["test/unit:QNULL"]["gdl_json"] == "null"


def test_zero_span_relation_chain_crosses_sidecar_and_tf_losslessly(tmp_path):
    edition = _mixed_span_edition("test/unit", "QCHAIN")
    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.signs == 1
    assert report.zero_span_counts["word"] == 1
    assert report.zero_span_counts["line"] == 1
    assert report.tf_node_counts["face"] == 1

    zero_span = corpus.load_zero_span(tmp_path)
    side_nodes = {node["key"]: node for node in zero_span["nodes"]}
    word_key = "word:test/unit:QCHAIN:QCHAIN.l0"
    line_key = "line:test/unit:QCHAIN:QCHAIN.1"
    face_key = "face:test/unit:QCHAIN:QCHAIN.face.1"

    assert side_nodes[word_key]["features"]["gdl_json"] == "[]"
    assert side_nodes[line_key]["features"]["source_id"] == "QCHAIN.1"

    side_edges = {
        (edge["feature"], edge["source"]): tuple(edge["targets"])
        for edge in zero_span["edges"]
    }
    assert side_edges[("word_line", word_key)] == (line_key,)
    assert side_edges[("line_face", line_key)] == (face_key,)

    # The sidecar target key is reproducibly resolvable back to the slotted TF
    # face using the same qualified document identity + source id.
    api = corpus.load_tf(tmp_path)
    tf_faces = [
        node for node in api.F.otype.s("face")
        if api.F.document_key.v(node) == "test/unit:QCHAIN"
        and api.F.source_id.v(node) == "QCHAIN.face.1"
    ]
    assert len(tf_faces) == 1


def test_zero_span_sidecar_is_byte_deterministic(tmp_path):
    edition = _edition("test/unit", "QTEST", signless=True)
    left = tmp_path / "left"
    right = tmp_path / "right"
    for target in (left, right):
        corpus.build_tf(
            target,
            editions=(edition,),
            metadata_index=metadata.MetadataIndex.empty(),
        )

    assert (left / corpus.ZERO_SPAN_FILENAME).read_bytes() == (
        right / corpus.ZERO_SPAN_FILENAME
    ).read_bytes()


def test_same_q_number_in_two_subprojects_stays_two_documents(tmp_path):
    editions = (
        _edition("test/a", "QDUPE"),
        _edition("test/b", "QDUPE"),
    )
    report = corpus.build_tf(
        tmp_path,
        editions=editions,
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.documents == 2
    assert report.unique_document_keys == 2
    assert report.document_key_collisions == 0

    api = corpus.load_tf(tmp_path)
    document_nodes = api.F.otype.s("document")
    assert {api.F.document.v(node) for node in document_nodes} == {
        "test/a:QDUPE",
        "test/b:QDUPE",
    }


@pytest.mark.corpus
def test_joined_corpus_invariants_and_tf_warp_load(tmp_path):
    report = corpus.build_full_tf(tmp_path, data=paths.DATA)

    assert report.documents == 2078
    assert report.populated_documents == 1845
    assert report.stub_documents == 233
    assert report.unique_document_keys == report.documents
    assert report.document_key_collisions == 0

    assert report.words == 320975
    assert report.signs == 792651
    assert report.unicode_signs == 778873
    assert report.unicode_coverage == pytest.approx(778873 / 792651)
    assert report.slotless_words == 295
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    assert report.tf_node_counts == {
        "chunk": 13388,
        "column": 723,
        "document": 1842,
        "face": 2036,
        "lex": 8023,
        "line": 56084,
        "phrase": 4499,
        "sign": 792651,
        "word": 320680,
    }
    assert report.zero_span_counts == {
        "chunk": 256,
        "column": 35,
        "document": 236,
        "face": 276,
        "lex": 2,
        "line": 142,
        "word": 295,
    }
    assert report.zero_span_nodes == 1242
    assert report.tf_words + report.zero_span_words == report.words
    assert report.tf_documents + report.zero_span_documents == report.documents
    assert report.tf_lines + report.zero_span_counts["line"] == report.lines
    assert report.tf_lexemes + report.zero_span_counts["lex"] == report.lexemes

    api = corpus.load_tf(tmp_path)
    assert api.F.otype.maxSlot == 792651
    assert len(api.F.otype.s("document")) == 1842
    assert len(api.F.otype.s("word")) == 320680
    assert len(api.F.otype.s("line")) == 56084
    assert len(api.F.otype.s("lex")) == 8023

    zero_span = corpus.load_zero_span(tmp_path)
    assert zero_span["schema"] == "oracc-tf-zero-span-v1"
    assert len(zero_span["nodes"]) == 1242

    populated_zero_span_documents = sorted(
        node["features"]["document"]
        for node in zero_span["nodes"]
        if node["otype"] == "document" and node["features"].get("populated") == 1
    )
    assert populated_zero_span_documents == [
        "rinap/rinap1:Q003633",
        "rinap/rinap2:Q006646",
        "rinap/rinap4:Q003344",
    ]

    # M7 source-preservation contract: the persisted word domain is the union
    # of TF warp words and sidecar words, and every stored GDL serialisation
    # must match the source representation exactly. Bare source ids are not
    # sufficient because rinap5/rinap5p1 reuse Q-numbers.
    stored_gdl: dict[tuple[str, str], str | None] = {
        (api.F.document_key.v(node), api.F.source_id.v(node)): api.F.gdl_json.v(node)
        for node in api.F.otype.s("word")
    }
    stored_gdl.update({
        (node["features"]["document_key"], node["features"]["source_id"]):
            node["features"].get("gdl_json")
        for node in zero_span["nodes"]
        if node["otype"] == "word"
    })
    assert len(stored_gdl) == report.words

    checked = 0
    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            expected = _canonical_source_gdl(dict(word.features))
            assert stored_gdl[(edition.key, word.source_id)] == expected
            checked += 1
    assert checked == report.words
