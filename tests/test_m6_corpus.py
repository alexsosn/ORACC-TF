"""P-001 M6 - joined whole-corpus invariants and Text-Fabric warp load.

Acceptance criteria from P-001 §5 M6:
- 320,975 source words; 2,078 parseable documents / 1,845 populated / 233 stubs;
- composite document keys are unique;
- every semantic sign belongs to exactly one word and every word to exactly one line;
- every populated document has a valid document/face/line section path;
- the M1 semantic sign count and Unicode coverage remain source-facing invariants;
- generated ``otype``/``oslots`` load cleanly in Text-Fabric;
- source entities with zero semantic sign extent remain losslessly queryable in
  TF through explicit synthetic empty slots, never a sidecar fallback.
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
    """One zero-sign line followed by a semantic-sign line on the same face."""
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


def _nodes_by_source(api, otype: str) -> dict[str, int]:
    return {
        api.F.source_id.v(node): node
        for node in api.F.otype.s(otype)
    }


def _slots(api, node: int) -> tuple[int, ...]:
    return tuple(api.L.d(node, otype="sign"))


def test_slotless_source_word_survives_losslessly_inside_tf(tmp_path):
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
    assert report.synthetic_slots == 1
    assert report.tf_slots == 2
    assert report.slotless_words == 1
    assert report.sign_word_membership_errors == 0
    assert report.word_line_membership_errors == 0
    assert report.section_path_errors == 0
    assert report.tf_words == 2
    assert report.zero_span_words == 0

    api = corpus.load_tf(tmp_path)
    by_source = _nodes_by_source(api, "word")
    assert set(by_source) == {"QTEST.l0", "QTEST.l1"}
    assert _slots(api, by_source["QTEST.l0"]) == (1,)
    assert _slots(api, by_source["QTEST.l1"]) == (2,)
    assert api.F.synthetic.v(1) == 1
    assert api.F.utf8.v(1) is None
    assert api.F.utf8.v(2) == "𒀀"
    assert api.T.sectionFromNode(1) == (
        "test/unit:QTEST",
        "QTEST.face.1",
        "QTEST.1",
    )
    assert not (tmp_path / corpus.ZERO_SPAN_FILENAME).exists()


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

    api = corpus.load_tf(tmp_path)
    by_document = {
        api.F.document_key.v(node): api.F.gdl_json.v(node)
        for node in api.F.otype.s("word")
        if api.F.source_id.v(node).endswith(".l0")
    }

    assert by_document["test/unit:QABSENT"] is None
    assert by_document["test/unit:QEMPTY"] == "[]"
    assert by_document["test/unit:QNULL"] == "null"


def test_zero_sign_relation_chain_stays_inside_tf_losslessly(tmp_path):
    edition = _mixed_span_edition("test/unit", "QCHAIN")
    report = corpus.build_tf(
        tmp_path,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )

    assert report.signs == 1
    assert report.synthetic_slots == 1
    assert report.tf_slots == 2
    assert report.zero_span_counts == {}
    assert report.tf_node_counts["word"] == 2
    assert report.tf_node_counts["line"] == 2
    assert report.tf_node_counts["face"] == 1

    api = corpus.load_tf(tmp_path)
    words_by_source = _nodes_by_source(api, "word")
    lines_by_source = _nodes_by_source(api, "line")
    faces_by_source = _nodes_by_source(api, "face")
    word = words_by_source["QCHAIN.l0"]
    line = lines_by_source["QCHAIN.1"]
    face = faces_by_source["QCHAIN.face.1"]

    assert _slots(api, word) == (1,)
    assert _slots(api, line) == (1,)
    assert _slots(api, face) == (1, 2)
    assert tuple(api.E.word_line.f(word)) == (line,)
    assert tuple(api.E.line_face.f(line)) == (face,)
    assert not (tmp_path / corpus.ZERO_SPAN_FILENAME).exists()


def test_empty_slot_tf_is_byte_deterministic(tmp_path):
    edition = _edition("test/unit", "QTEST", signless=True)
    left = tmp_path / "left"
    right = tmp_path / "right"
    for target in (left, right):
        corpus.build_tf(
            target,
            editions=(edition,),
            metadata_index=metadata.MetadataIndex.empty(),
        )

    left_files = {path.name: path.read_bytes() for path in left.glob("*.tf")}
    right_files = {path.name: path.read_bytes() for path in right.glob("*.tf")}
    assert left_files
    assert left_files == right_files
    assert not (left / corpus.ZERO_SPAN_FILENAME).exists()
    assert not (right / corpus.ZERO_SPAN_FILENAME).exists()


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
    assert report.zero_span_counts == {}

    # Measurement gate for ADR-0001 migration.  The next commit pins the exact
    # corpus-wide synthetic/total slot counts from this diagnostic RED run.
    assert report.synthetic_slots == -1, report.report()

    api = corpus.load_tf(tmp_path)
    assert len(api.F.otype.s("document")) == report.documents
    assert len(api.F.otype.s("word")) == report.words
    assert len(api.F.otype.s("line")) == report.lines
    assert len(api.F.otype.s("lex")) == report.lexemes

    stored_gdl: dict[tuple[str, str], str | None] = {
        (api.F.document_key.v(node), api.F.source_id.v(node)): api.F.gdl_json.v(node)
        for node in api.F.otype.s("word")
    }
    assert len(stored_gdl) == report.words

    checked = 0
    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            expected = _canonical_source_gdl(dict(word.features))
            assert stored_gdl[(edition.key, word.source_id)] == expected
            checked += 1
    assert checked == report.words
