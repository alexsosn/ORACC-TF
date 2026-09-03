"""P-001 M2 - word layer.

Acceptance criteria from P-001 §5 M2:
- lemmatised words carry cf/gw/sense/norm/pos/epos;
- unlemmatised words survive with form and lemmaknown=0;
- word sign spans are contiguous and non-overlapping;
- whole-corpus word count matches the direct l-node count exactly.

The word layer consumes M1's semantic sign classifier; it never counts raw GDL
leaves independently.
"""

from __future__ import annotations

import pytest

from oracc_tf import loader, paths, words

LEMMATISED = "riao/ria1/Q005202.json"
UNLEMMATISED = "riao/ria1/Q005621.json"


def src(rel: str):
    sub, name = rel.rsplit("/", 1)
    return paths.DATA / sub / "corpusjson" / name


def source_word(doc: dict, word_id: str) -> dict:
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l" and node.get("id") == word_id:
            return node
        stack.extend(node.get("cdl") or [])
    raise AssertionError(f"word not found: {word_id}")


def test_lemmatised_word_preserves_analysis_and_uses_m1_sign_span():
    edition = loader.load_edition(src(LEMMATISED))
    node = source_word(edition.doc, "Q005202.l00510")

    word = words.from_source(node, start_slot=17)

    assert word.source_id == "Q005202.l00510"
    assert word.ref == "Q005202.1.1"
    assert word.form == "ma-an-iš-tu-su"
    assert word.frag == "ma-an-iš-tu-su"
    assert word.lang == "akk"
    assert word.cf == "Man-ištušu"
    assert word.gw == "king of Agade"
    assert word.sense == "king of Agade"
    assert word.norm == "Man-ištušu"
    assert word.pos == "RN"
    assert word.epos == "RN"
    assert word.sig.startswith("@riao/ria1%akk:")
    assert word.lemmaknown == 1

    assert word.slot_start == 17
    assert word.slot_end == 22
    assert word.sign_count == 5
    assert [sign.value.get("v") for sign in word.signs] == [
        "ma", "an", "iš", "tu", "su"
    ]
    assert all(sign.src_path.startswith("Q005202.l00510/gdl[") for sign in word.signs)


def test_unlemmatised_word_survives_with_form_and_zero_lemmaknown():
    edition = loader.load_edition(src(UNLEMMATISED))
    node = source_word(edition.doc, "Q005621.l005dd")

    word = words.from_source(node, start_slot=0)

    assert word.source_id == "Q005621.l005dd"
    assert word.form == "x"
    assert word.lang == "akk"
    assert word.pos == "u"
    assert word.lemmaknown == 0
    assert word.cf is None
    assert word.gw is None
    assert word.sense is None
    assert word.norm is None
    assert word.sig is None
    assert word.sign_count == 1
    assert word.signs[0].value.get("x") == "ellipsis"


def test_document_word_spans_are_contiguous_and_non_overlapping():
    edition = loader.load_edition(src(LEMMATISED))
    records = list(words.iter_words(edition.doc))

    assert records[:3][0].source_id == "Q005202.l00510"
    assert [(w.slot_start, w.slot_end) for w in records[:3]] == [
        (0, 5), (5, 6), (6, 7)
    ]
    assert all(left.slot_end == right.slot_start
               for left, right in zip(records, records[1:]))
    assert all(word.slot_end >= word.slot_start for word in records)


def test_from_source_rejects_non_word_nodes():
    with pytest.raises(words.InvalidWordSource, match="node='l'"):
        words.from_source({"node": "d", "type": "line-start"}, start_slot=0)


@pytest.mark.corpus
def test_whole_corpus_word_count_matches_direct_l_node_count_exactly():
    result = words.census(paths.DATA)
    direct = sum(
        edition.word_count
        for edition in loader.iter_editions(paths.DATA, skip_unreadable=True)
    )

    assert direct == 320975
    assert result.words == direct
    assert result.signs == 792651
    assert result.span_errors == 0
