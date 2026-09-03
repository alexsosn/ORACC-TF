"""P-001 M4 lexeme-layer acceptance tests.

ORACC distinguishes occurrence morphology (``inst`` / ``sig``) from lexical
identity. Compound orthographic forms may repeat occurrence slots, so raw
``inst`` arity and distinct word→lex degree are deliberately tested
separately.
"""

from __future__ import annotations

import pytest

from oracc_tf import lexemes, loader, paths


Q003333 = paths.DATA / "rinap/rinap4/corpusjson/Q003333.json"
Q009276 = paths.DATA / "riao/ria5/corpusjson/Q009276.json"


def source_word(doc: dict, word_id: str) -> dict:
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l" and node.get("id") == word_id:
            return node
        stack.extend(node.get("cdl") or [])
    raise AssertionError(f"word not found: {word_id}")


def test_signature_identity_includes_language_but_not_project():
    rinap = lexemes.parse_sig(
        "@rinap/rinap4%akk:X=šarru[king//king]N'N$šarru"
    )[0]
    riao = lexemes.parse_sig(
        "@riao/ria5%akk:Y=šarru[king//king]N'N$šarri"
    )[0]
    sumerian = lexemes.parse_sig(
        "@riao/ria5%sux:Y=šarru[king//king]N'N$šarru"
    )[0]

    assert rinap.project != riao.project
    assert rinap.key == riao.key == lexemes.LexemeKey("akk", "šarru", "king", "N")
    assert sumerian.key != rinap.key


def test_q003333_three_lexeme_compound_links_to_three_distinct_nodes():
    edition = loader.load_edition(Q003333)
    source = source_word(edition.doc, "Q003333.l04f6b")
    slots = lexemes.parse_inst(source["inst"])
    index = lexemes.index_document(edition.doc)

    assert len(slots) == 3
    assert [(slot.form, slot.gw, slot.pos) for slot in slots] == [
        ("šattu", "year", "N"),
        ("rēšu", "head", "N"),
        ("šarrūtu", "kingship", "N"),
    ]
    assert index.word_to_lex["Q003333.l04f6b"] == (
        lexemes.LexemeKey("akk", "šattu", "year", "N"),
        lexemes.LexemeKey("akk", "rēšu", "head", "N"),
        lexemes.LexemeKey("akk", "šarrūtu", "kingship", "N"),
    )
    assert index.word_sigs["Q003333.l04f6b"] == source["sig"]


def test_q009276_fourteen_inst_slots_collapse_to_two_distinct_lexemes():
    edition = loader.load_edition(Q009276)
    source = source_word(edition.doc, "Q009276.l00a19")
    slots = lexemes.parse_inst(source["inst"])
    index = lexemes.index_document(edition.doc)

    assert len(slots) == 14
    assert (slots[0].form, slots[0].gw, slots[0].pos) == ("šakin", "governor", "N")
    assert all((slot.form, slot.gw, slot.pos) == ("māti", "land", "N") for slot in slots[1:])
    assert index.word_to_lex["Q009276.l00a19"] == (
        lexemes.LexemeKey("akk", "šaknu", "appointee", "N"),
        lexemes.LexemeKey("akk", "mātu", "land", "N"),
    )
    assert index.word_sigs["Q009276.l00a19"] == source["sig"]


def test_inst_parser_preserves_optional_norm_sense_and_coform_marker():
    slots = lexemes.parse_inst(
        "pītu[opening]N$pīt&+bābu[gate//gate]N$bābi"
    )

    assert len(slots) == 2
    assert (slots[0].form, slots[0].gw, slots[0].sense, slots[0].pos, slots[0].norm, slots[0].coform) == (
        "pītu", "opening", None, "N", "pīt", False
    )
    assert (slots[1].form, slots[1].gw, slots[1].sense, slots[1].pos, slots[1].norm, slots[1].coform) == (
        "bābu", "gate", "gate", "N", "bābi", True
    )


def test_inst_parser_preserves_real_empty_gloss_instead_of_rejecting_it():
    slot = lexemes.parse_inst("Zarpanitu[]DN$Zer-banitum")[0]

    assert (slot.form, slot.gw, slot.sense, slot.pos, slot.norm) == (
        "Zarpanitu", "", None, "DN", "Zer-banitum"
    )
    assert slot.opaque is False


def test_inst_parser_preserves_real_bare_token_as_opaque_slot():
    slot = lexemes.parse_inst("n")[0]

    assert slot.raw == "n"
    assert slot.opaque is True
    assert (slot.form, slot.gw, slot.sense, slot.pos, slot.norm) == (
        None, None, None, None, None
    )


def test_inst_parser_preserves_partial_bracketed_analysis_without_pos():
    slot = lexemes.parse_inst("ūlid[produce]")[0]

    assert slot.raw == "ūlid[produce]"
    assert slot.opaque is False
    assert (slot.form, slot.gw, slot.sense, slot.pos, slot.norm) == (
        "ūlid", "produce", None, None, None
    )


def test_index_keeps_every_source_word_even_when_it_has_no_lexeme():
    doc = {
        "type": "cdl",
        "project": "test/project",
        "textid": "QTEST",
        "cdl": [{
            "node": "c", "type": "text", "id": "QTEST.U0", "cdl": [
                {"node": "l", "id": "QTEST.l1", "frag": "x", "f": {"lang": "akk", "form": "x", "gdl": []}},
            ]
        }],
    }

    index = lexemes.index_document(doc)
    assert index.word_count == 1
    assert index.word_to_lex["QTEST.l1"] == ()
    assert index.word_sigs["QTEST.l1"] is None


@pytest.mark.corpus
def test_whole_corpus_lexeme_identity_and_compound_arity_are_pinned():
    result = lexemes.census(paths.DATA)

    assert result.words == 320975
    assert result.lexemes == 8025
    assert result.cross_language_triples == 29
    assert result.max_inst_slots == 14
    assert result.max_word_lex_degree == 3
