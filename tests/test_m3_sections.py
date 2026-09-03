"""P-001 M3 - streaming section walk.

The source CDL is not a section tree: ``d`` markers and words are siblings,
so section membership is stateful. These tests pin the source-faithful walk
before ``oracc_tf.sections`` exists.
"""

from __future__ import annotations

import pytest

from oracc_tf import loader, paths, sections

FIXTURE = paths.DATA / "riao/ria4/corpusjson/Q004473.json"


def test_real_line_one_has_exact_source_words_and_empty_face_label():
    edition = loader.load_edition(FIXTURE)
    result = sections.walk_document(edition.doc)

    line1 = next(line for line in result.lines if line.ref == "Q004473.1")
    assert line1.label == "1"
    assert line1.synthetic == 0
    assert line1.word_ids == (
        "Q004473.l02ae0",
        "Q004473.l02ae1",
        "Q004473.l02ae2",
    )

    assert len(result.faces) >= 1
    assert result.faces[0].label == ""
    assert result.faces[0].synthetic == 0
    assert all(result.word_to_line[word_id] == line1.source_id for word_id in line1.word_ids)


def test_every_source_c_is_generic_chunk_and_sentence_is_never_an_otype():
    edition = loader.load_edition(FIXTURE)
    result = sections.walk_document(edition.doc)

    sentence = next(chunk for chunk in result.chunks if chunk.source_id == "Q004473.U2")
    assert sentence.otype == "chunk"
    assert sentence.chunk_type == "sentence"
    assert sentence.implicit == "yes"
    assert "sentence" not in {node.otype for node in result.nodes}


def test_phrase_is_both_generic_chunk_and_ergonomic_phrase_node():
    doc = {
        "type": "cdl",
        "textid": "QTEST",
        "cdl": [{
            "node": "c", "type": "text", "id": "QTEST.U0", "cdl": [
                {"node": "d", "type": "surface", "ref": ""},
                {"node": "d", "type": "line-start", "ref": "QTEST.1", "label": "1"},
                {"node": "c", "type": "phrase", "id": "QTEST.U1", "cdl": [
                    {"node": "l", "id": "QTEST.l1", "f": {"form": "a", "gdl": []}},
                    {"node": "l", "id": "QTEST.l2", "f": {"form": "b", "gdl": []}},
                ]},
            ]
        }],
    }

    result = sections.walk_document(doc)
    chunk = next(node for node in result.chunks if node.source_id == "QTEST.U1")
    phrase = next(node for node in result.phrases if node.source_id == "QTEST.U1")

    assert chunk.otype == "chunk"
    assert chunk.chunk_type == "phrase"
    assert phrase.otype == "phrase"
    assert chunk.word_ids == phrase.word_ids == ("QTEST.l1", "QTEST.l2")


def test_word_before_first_line_gets_explicit_synthetic_face_and_line():
    doc = {
        "type": "cdl", "textid": "QTEST", "cdl": [
            {"node": "c", "type": "text", "id": "QTEST.U0", "cdl": [
                {"node": "l", "id": "QTEST.l1", "f": {"form": "a", "gdl": []}},
            ]}
        ],
    }

    result = sections.walk_document(doc)

    assert len(result.faces) == 1
    assert result.faces[0].synthetic == 1
    assert len(result.lines) == 1
    assert result.lines[0].synthetic == 1
    assert result.lines[0].word_ids == ("QTEST.l1",)
    assert result.word_to_line["QTEST.l1"] == result.lines[0].source_id
    assert "word_before_line" in result.anomaly_kinds
    assert "synthetic_face" in result.anomaly_kinds
    assert "synthetic_line" in result.anomaly_kinds


def test_line_before_surface_and_column_before_surface_are_explicit():
    line_doc = {
        "type": "cdl", "textid": "QLINE", "cdl": [
            {"node": "c", "type": "text", "id": "QLINE.U0", "cdl": [
                {"node": "d", "type": "line-start", "ref": "QLINE.1", "label": "1"},
            ]}
        ],
    }
    column_doc = {
        "type": "cdl", "textid": "QCOL", "cdl": [
            {"node": "c", "type": "text", "id": "QCOL.U0", "cdl": [
                {"node": "d", "type": "column", "ref": "", "label": "1"},
            ]}
        ],
    }

    line_result = sections.walk_document(line_doc)
    column_result = sections.walk_document(column_doc)

    assert line_result.faces[0].synthetic == 1
    assert line_result.lines[0].synthetic == 0
    assert "line_before_surface" in line_result.anomaly_kinds
    assert "synthetic_face" in line_result.anomaly_kinds

    assert column_result.faces[0].synthetic == 1
    assert column_result.columns[0].synthetic == 0
    assert "column_before_surface" in column_result.anomaly_kinds
    assert "synthetic_face" in column_result.anomaly_kinds


def test_object_and_surface_transitions_reset_downstream_state():
    doc = {
        "type": "cdl", "textid": "QRESET", "cdl": [
            {"node": "c", "type": "text", "id": "QRESET.U0", "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": "o"},
                {"node": "d", "type": "column", "ref": "", "label": "1"},
                {"node": "d", "type": "line-start", "ref": "QRESET.1", "label": "1"},
                {"node": "l", "id": "QRESET.l1", "f": {"form": "a", "gdl": []}},
                {"node": "d", "type": "surface", "ref": "", "label": "r"},
                {"node": "l", "id": "QRESET.l2", "f": {"form": "b", "gdl": []}},
                {"node": "d", "type": "object", "ref": ""},
                {"node": "l", "id": "QRESET.l3", "f": {"form": "c", "gdl": []}},
            ]}
        ],
    }

    result = sections.walk_document(doc)
    l1 = result.word_to_line["QRESET.l1"]
    l2 = result.word_to_line["QRESET.l2"]
    l3 = result.word_to_line["QRESET.l3"]

    assert len({l1, l2, l3}) == 3
    assert result.line_by_id[l2].synthetic == 1
    assert result.line_by_id[l3].synthetic == 1
    assert result.line_by_id[l2].face_id != result.line_by_id[l1].face_id
    assert result.line_by_id[l3].face_id != result.line_by_id[l2].face_id


def test_unknown_chunk_type_fails_closed():
    doc = {
        "type": "cdl", "textid": "QBAD", "cdl": [
            {"node": "c", "type": "mystery", "id": "QBAD.U0", "cdl": []}
        ],
    }

    with pytest.raises(sections.UnknownChunkType, match="mystery"):
        sections.walk_document(doc)


@pytest.mark.corpus
def test_whole_corpus_line_and_word_membership_invariants():
    result = sections.census(paths.DATA)

    assert result.source_lines == 56226
    assert result.real_lines == result.source_lines
    assert result.words == 320975
    assert result.words_assigned_once == result.words
    assert result.unassigned_words == 0
    assert result.multiply_assigned_words == 0
    assert result.synthetic_lines == 0, result.report()
    # Measured by the diagnostic RED run 33780195914. These are source-state
    # anomalies, not lost text: all 320,975 words still map to exactly one real
    # line, while 14 line-start markers occur before any surface marker and
    # therefore require an explicitly synthetic face.
    assert result.anomalies == {
        "line_before_surface": 14,
        "synthetic_face": 14,
    }, result.report()
