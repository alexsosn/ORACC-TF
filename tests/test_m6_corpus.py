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

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths


def _edition(subproject: str, text_id: str, *, signless: bool = False) -> loader.Edition:
    words = []
    if signless:
        words.append({
            "node": "l",
            "id": f"{text_id}.l0",
            "f": {"form": "*", "gdl": []},
        })
    words.append({
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
                *words,
            ],
        }],
    }
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=len(words),
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
    assert report.slotless_words == 295
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0

    # Zero-span source entities remain part of source cardinalities but cannot
    # be warp nodes. At minimum this snapshot contains the 295 M2 signless
    # words and all 233 metadata-only stub documents.
    assert report.tf_words + report.zero_span_words == report.words
    assert report.zero_span_words == 295
    assert report.tf_documents + report.zero_span_documents == report.documents
    assert report.zero_span_documents >= 233
    assert report.zero_span_nodes >= report.zero_span_words + report.zero_span_documents

    # Diagnostic first freeze: implementation must report the measured exact
    # count, then this deliberate RED assertion is replaced with that value.
    assert report.unicode_signs == 0, report.report()

    api = corpus.load_tf(tmp_path)
    assert api.F.otype.maxSlot == 792651
    assert len(api.F.otype.s("document")) == report.tf_documents
    assert len(api.F.otype.s("word")) == report.tf_words
    assert len(api.F.otype.s("line")) == report.tf_lines
    assert len(api.F.otype.s("lex")) == report.tf_lexemes

    zero_span = corpus.load_zero_span(tmp_path)
    assert zero_span["schema"] == "oracc-tf-zero-span-v1"
    assert len(zero_span["nodes"]) == report.zero_span_nodes
