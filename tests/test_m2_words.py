"""P-001 M2 word-layer acceptance tests."""

from __future__ import annotations

import pytest

from oracc_tf import loader, paths, words


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


def record(rel: str, word_id: str, start_slot: int = 1):
    edition = loader.load_edition(src(rel))
    return words.from_source(source_word(edition.doc, word_id), start_slot=start_slot)


def test_lemmatised_word_preserves_source_analysis_and_m1_sign_span():
    word = record("riao/ria1/Q005202.json", "Q005202.l00510", 17)
    assert (word.cf, word.gw, word.sense, word.norm, word.pos, word.epos) == (
        "Man-ištušu", "king of Agade", "king of Agade", "Man-ištušu", "RN", "RN"
    )
    assert word.lang == "akk"
    assert word.form == "ma-an-iš-tu-su"
    assert word.sig.startswith("@riao/ria1%akk:")
    assert word.lemmaknown == 1
    assert (word.slot_start, word.slot_end, word.sign_count) == (17, 22, 5)
    assert [sign.value.get("v") for sign in word.signs] == ["ma", "an", "iš", "tu", "su"]


def test_unlemmatised_word_survives_with_form():
    word = record("riao/ria1/Q005621.json", "Q005621.l005dd")
    assert word.form == "x"
    assert word.pos == "u"
    assert word.lemmaknown == 0
    assert all(value is None for value in (word.cf, word.gw, word.sense, word.norm, word.sig))
    assert word.sign_count == 1


def test_lemmatised_source_can_lack_norm_without_fabrication():
    word = record("rinap/rinap2/Q006534.json", "Q006534.l047d9")
    assert word.cf == "Šarru-ukin"
    assert word.pos == word.epos == "RN"
    assert word.norm is None
    assert word.lemmaknown == 1


def test_norm_only_placeholder_is_not_a_known_lemma():
    word = record("rinap/rinap4/Q003344.json", "Q003344.l05b90")
    assert word.form == "*"
    assert word.norm == "Horned"
    assert word.cf is None
    assert word.lemmaknown == 0
    assert word.sign_count == 0


def test_signless_source_word_survives_with_empty_span():
    word = record("rinap/rinap1/Q003622.json", "Q003622.l00009", 42)
    assert word.lang == "arc"
    assert word.form == "mnn"
    assert word.lemmaknown == 0
    assert word.sign_count == 0
    assert (word.slot_start, word.slot_end) == (42, 42)
    assert list(word.slot_ids) == []


def test_document_word_spans_are_contiguous_and_non_overlapping():
    edition = loader.load_edition(src("riao/ria1/Q005202.json"))
    records = list(words.iter_words(edition.doc))
    assert [r.source_id for r in records[:3]] == ["Q005202.l00510", "Q005202.l00511", "Q005202.l00512"]
    assert [(r.slot_start, r.slot_end) for r in records[:3]] == [(1, 6), (6, 7), (7, 8)]
    assert all(a.slot_end == b.slot_start for a, b in zip(records, records[1:]))


def test_from_source_rejects_non_word_nodes():
    with pytest.raises(words.InvalidWordSource, match="node='l'"):
        words.from_source({"node": "d"}, start_slot=1)


def test_census_exposes_measured_source_classes():
    fields = words.WordCensus.__dataclass_fields__
    assert "lemmatised_without_norm" in fields
    assert "norm_only_unlemmatised" in fields
    assert "unlemmatised_without_form" in fields


@pytest.mark.corpus
def test_whole_corpus_word_count_and_source_classes_are_pinned():
    result = words.census(paths.DATA)
    direct = sum(e.word_count for e in loader.iter_editions(paths.DATA, skip_unreadable=True))
    assert direct == result.words == 320975
    assert result.signs == 792651
    assert result.span_errors == 0
    assert result.lemmatised == 289205
    assert result.unlemmatised == 31770
    assert result.zero_sign_words == 295
    assert result.lemmatised_without_norm == 878
    assert result.norm_only_unlemmatised == 230
    assert result.unlemmatised_without_form == 0
