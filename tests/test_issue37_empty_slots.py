"""Issue #37 — zero-span textual entities stay inside Text-Fabric.

These tests intentionally replace the earlier sidecar-first architecture with
ADR-0001's explicit empty-slot contract.  The RED commit must precede
production changes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata


def _word(text_id: str, suffix: str, form: str, utf8: str | None = None, *, lemma=False):
    features: dict[str, object] = {"form": form, "gdl": []}
    if utf8 is not None:
        features["gdl"] = [{"v": form, "utf8": utf8}]
    if lemma:
        features.update({"lang": "akk", "cf": "ana", "gw": "to", "pos": "PRP"})
    return {
        "node": "l",
        "id": f"{text_id}.{suffix}",
        "f": features,
    }


def _edition(text_id: str, body: list[dict[str, object]], *, subproject="test/unit"):
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": body,
        }],
    }
    words = sum(1 for item in body if item.get("node") == "l")
    # Count nested words too for the dedicated nested-container fixture.
    def count_words(node: object) -> int:
        if not isinstance(node, dict):
            return 0
        return int(node.get("node") == "l") + sum(
            count_words(child) for child in node.get("cdl", [])
        )

    words = sum(count_words(item) for item in body)
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=words,
    )


def _build(tmp_path: Path, edition: loader.Edition):
    return corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )


def _nodes_by_source(api, otype: str):
    return {
        api.F.source_id.v(node): node
        for node in api.F.otype.s(otype)
    }


def _slots(api, node: int) -> tuple[int, ...]:
    return tuple(api.L.d(node, otype="sign"))


def test_zero_sign_word_between_real_words_gets_one_empty_slot_in_source_order(tmp_path):
    edition = _edition("QORDER", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QORDER.1", "label": "1"},
        _word("QORDER", "l1", "a", "𒀀"),
        _word("QORDER", "l2", "*"),
        _word("QORDER", "l3", "ba", "𒁀"),
    ])

    report = _build(tmp_path, edition)
    assert report.signs == 2  # semantic/source signs only
    assert report.synthetic_slots == 1
    assert report.tf_slots == 3
    assert report.tf_node_counts["sign"] == 3
    assert report.unicode_signs == 2
    assert report.unicode_coverage == pytest.approx(1.0)

    api = corpus.load_tf(tmp_path)
    words = _nodes_by_source(api, "word")
    assert set(words) == {"QORDER.l1", "QORDER.l2", "QORDER.l3"}
    assert _slots(api, words["QORDER.l1"]) == (1,)
    assert _slots(api, words["QORDER.l2"]) == (2,)
    assert _slots(api, words["QORDER.l3"]) == (3,)

    assert api.F.synthetic.v(1) is None
    assert api.F.synthetic.v(2) == 1
    assert api.F.synthetic.v(3) is None
    assert api.F.word_id.v(2) == "QORDER.l2"
    assert api.F.utf8.v(2) is None
    assert api.F.readingu.v(2) is None
    assert api.F.sign_json.v(2) is None


def test_adjacent_zero_sign_words_get_distinct_positions_but_ancestors_reuse_them(tmp_path):
    edition = _edition("QADJ", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QADJ.1", "label": "1"},
        _word("QADJ", "l1", "*"),
        _word("QADJ", "l2", "*"),
    ])

    report = _build(tmp_path, edition)
    assert report.signs == 0
    assert report.synthetic_slots == 2
    assert report.tf_slots == 2

    api = corpus.load_tf(tmp_path)
    words = _nodes_by_source(api, "word")
    line = _nodes_by_source(api, "line")["QADJ.1"]
    face = next(iter(api.F.otype.s("face")))
    document = next(iter(api.F.otype.s("document")))

    assert _slots(api, words["QADJ.l1"]) == (1,)
    assert _slots(api, words["QADJ.l2"]) == (2,)
    assert _slots(api, line) == (1, 2)
    assert _slots(api, face) == (1, 2)
    assert _slots(api, document) == (1, 2)


def test_empty_nested_line_chunk_phrase_share_one_synthetic_anchor(tmp_path):
    edition = _edition("QNEST", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {
            "node": "c",
            "type": "phrase",
            "id": "QNEST.U1",
            "cdl": [
                {"node": "d", "type": "line-start", "ref": "QNEST.1", "label": "1"},
            ],
        },
    ])

    report = _build(tmp_path, edition)
    assert report.signs == 0
    assert report.synthetic_slots == 1
    assert report.tf_slots == 1
    assert report.zero_span_counts == {}

    api = corpus.load_tf(tmp_path)
    line = _nodes_by_source(api, "line")["QNEST.1"]
    chunk = _nodes_by_source(api, "chunk")["QNEST.U1"]
    phrase = _nodes_by_source(api, "phrase")["QNEST.U1"]
    face = next(iter(api.F.otype.s("face")))
    document = next(iter(api.F.otype.s("document")))
    assert _slots(api, line) == _slots(api, chunk) == _slots(api, phrase) == (1,)
    assert _slots(api, face) == _slots(api, document) == (1,)


def test_wholly_empty_document_gets_one_invisible_anchor_and_is_tf_loadable(tmp_path):
    edition = loader.Edition(
        subproject="test/unit",
        text_id="QEMPTYDOC",
        path=Path("/test/unit/corpusjson/QEMPTYDOC.json"),
        doc={"type": "cdl", "textid": "QEMPTYDOC", "cdl": []},
        word_count=0,
    )

    report = _build(tmp_path, edition)
    assert report.signs == 0
    assert report.synthetic_slots == 1
    assert report.tf_slots == 1
    assert report.tf_documents == 1
    assert report.zero_span_counts == {}

    api = corpus.load_tf(tmp_path)
    document = next(iter(api.F.otype.s("document")))
    assert api.F.document.v(document) == "test/unit:QEMPTYDOC"
    assert _slots(api, document) == (1,)
    assert api.F.synthetic.v(1) == 1
    assert api.F.utf8.v(1) is None


def test_zero_sign_lexeme_uses_occurrence_anchor_without_fabricated_text(tmp_path):
    edition = _edition("QLEX", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QLEX.1", "label": "1"},
        _word("QLEX", "l1", "*", lemma=True),
    ])

    report = _build(tmp_path, edition)
    assert report.signs == 0
    assert report.synthetic_slots == 1
    assert report.lexemes == 1
    assert report.tf_lexemes == 1

    api = corpus.load_tf(tmp_path)
    word = _nodes_by_source(api, "word")["QLEX.l1"]
    lex = next(iter(api.F.otype.s("lex")))
    assert _slots(api, word) == _slots(api, lex) == (1,)
    assert api.F.synthetic.v(1) == 1
    assert api.F.utf8.v(1) is None


def test_new_build_does_not_emit_zero_span_sidecar_when_every_node_is_in_tf(tmp_path):
    edition = _edition("QNOSIDE", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QNOSIDE.1", "label": "1"},
        _word("QNOSIDE", "l1", "*"),
    ])
    _build(tmp_path, edition)
    assert not (tmp_path / corpus.ZERO_SPAN_FILENAME).exists()


def test_empty_slot_build_is_byte_deterministic(tmp_path):
    edition = _edition("QDET", [
        {"node": "d", "type": "surface", "ref": "", "label": "o"},
        {"node": "d", "type": "line-start", "ref": "QDET.1", "label": "1"},
        _word("QDET", "l1", "a", "𒀀"),
        _word("QDET", "l2", "*"),
    ])
    left = tmp_path / "left"
    right = tmp_path / "right"
    _build(left, edition)
    _build(right, edition)

    left_files = {p.name: p.read_bytes() for p in left.glob("*.tf")}
    right_files = {p.name: p.read_bytes() for p in right.glob("*.tf")}
    assert left_files
    assert left_files == right_files
