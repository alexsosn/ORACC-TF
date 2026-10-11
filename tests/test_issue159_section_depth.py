"""RED-first section traversal tests: depth-safe with postorder chunk closure.

Synthetic in-memory depth is a stability boundary, not a statement about
the nesting depth of the published RIAO/RINAP corpus.
"""
from __future__ import annotations

import pytest

from oracc_tf import sections


def _word(word_id: str) -> dict:
    return {"node": "l", "id": word_id, "f": {"form": "x", "gdl": []}}


def test_1500_nested_chunks_preserve_inclusive_event_and_word_ranges() -> None:
    leaf: dict = _word("QDEEP.l1")
    for i in range(1500):
        leaf = {
            "node": "c",
            "type": "phrase" if i == 0 else "text",
            "id": f"QDEEP.U{i}",
            "cdl": [leaf],
        }
    root = {
        "type": "cdl", "textid": "QDEEP",
        "cdl": [
            {"node": "d", "type": "surface", "ref": "", "label": "obv"},
            {"node": "d", "type": "line-start", "ref": "QDEEP.1", "label": "1"},
            leaf,
        ],
    }
    result = sections.walk_document(root)
    assert result.source_events == 1504  # root, two markers, 1500 chunks, word
    assert result.source_lines == 1
    assert result.source_words == 1
    assert result.word_to_line == {"QDEEP.l1": "QDEEP.1"}
    assert result.lines[0].word_ids == ("QDEEP.l1",)
    assert result.anomalies == ()
    assert len(result.chunks) == 1500
    assert result.chunks[0].source_id == "QDEEP.U0"  # exit inner before outer
    assert result.chunks[-1].source_id == "QDEEP.U1499"
    assert all(c.word_ids == ("QDEEP.l1",) for c in result.chunks)
    assert all(c.source_end == 1504 for c in result.chunks)
    assert result.chunks[-1].source_start == 4
    assert result.chunks[0].source_start == 1503
    assert len(result.phrases) == 1
    assert result.phrases[0].source_id == "QDEEP.U0"
    assert result.phrases[0].word_ids == ("QDEEP.l1",)


def test_1500_nested_anonymous_cdl_wrappers_keep_word_and_anomalies() -> None:
    leaf: dict = _word("QWRAP.l1")
    for i in range(1500):
        leaf = {"cdl": [leaf]}
    result = sections.walk_document({"type": "cdl", "textid": "QWRAP", "cdl": [leaf]})
    assert result.source_events == 1502
    assert result.source_words == 1
    assert len(result.chunks) == 0
    assert result.word_to_line["QWRAP.l1"].startswith("QWRAP.synthetic.line.")
    assert {"word_before_line", "synthetic_line", "synthetic_face"} <= result.anomaly_kinds


def test_nested_chunk_postorder_and_consecutive_words_unchanged() -> None:
    doc = {
        "type": "cdl", "textid": "QORDER", "cdl": [
            {"node": "d", "type": "line-start", "ref": "QORDER.1"},
            {"node": "c", "type": "text", "id": "outer", "cdl": [
                _word("first"),
                {"node": "c", "type": "phrase", "id": "inner", "cdl": [_word("middle")]},
                _word("last"),
            ]},
            _word("after"),
        ],
    }
    result = sections.walk_document(doc)
    assert tuple(result.word_order) == ("first", "middle", "last", "after")
    assert [c.source_id for c in result.chunks] == ["inner", "outer"]
    assert [c.word_ids for c in result.chunks] == [
        ("middle",), ("first", "middle", "last")
    ]
    assert [(c.source_start, c.source_end) for c in result.chunks] == [
        (5, 6), (3, 7)
    ]
    assert result.phrases[0].source_start == 5
    assert result.phrases[0].source_end == 6
    assert result.lines[0].word_ids == ("first", "middle", "last", "after")


def test_nested_cdl_validation_stays_contextual_and_fails_closed() -> None:
    with pytest.raises(sections.InvalidSectionSource, match=r"QBAD/cdl\[0\]/cdl\[0\]: child is int"):
        sections.walk_document({
            "type": "cdl", "textid": "QBAD",
            "cdl": [{"node": "c", "type": "text", "cdl": [9]}],
        })
    with pytest.raises(sections.UnknownChunkType, match="mystery"):
        sections.walk_document({
            "type": "cdl", "textid": "QBAD",
            "cdl": [{"node": "c", "type": "mystery", "cdl": [_word("word")]}],
        })
