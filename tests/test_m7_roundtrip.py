"""P-001 M7 — sign-derived form round-trip and source GDL preservation."""

from __future__ import annotations

import pytest

from oracc_tf import paths, roundtrip, words


def test_simple_sign_sequence_reconstructs_form_exactly():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.l1",
        "f": {
            "form": "a-šur",
            "gdl": [
                {"v": "a", "utf8": "𒀀", "delim": "-"},
                {"v": "šur", "utf8": "𒋙"},
            ],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate == "a-šur"
    assert result.exact
    assert result.reason is None


def test_structural_context_failure_is_explicit_not_silently_accepted():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.l2",
        "f": {
            "form": "{d}a",
            "gdl": [
                {
                    "det": "semantic",
                    "pos": "pre",
                    "seq": [{"v": "d", "utf8": "𒀭"}],
                },
                {"v": "a", "utf8": "𒀀"},
            ],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate == "da"
    assert not result.exact
    assert result.reason == "structural_context"


def test_canonical_gdl_storage_distinguishes_absent_empty_and_null():
    assert roundtrip.source_gdl_json({}) is None
    assert roundtrip.source_gdl_json({"gdl": []}) == "[]"
    assert roundtrip.source_gdl_json({"gdl": None}) == "null"


@pytest.mark.corpus
def test_whole_corpus_sign_roundtrip_is_fully_accounted_for():
    census = roundtrip.census(paths.DATA)

    assert census.words == 320975
    assert census.zero_sign_words == 295
    assert census.exact + sum(census.exceptions.values()) == census.words
    # Diagnostic RED: replace this only with the exact measured exception
    # profile. A broad >= / non-empty assertion would hide future drift.
    assert census.exceptions == {}, census.report()
