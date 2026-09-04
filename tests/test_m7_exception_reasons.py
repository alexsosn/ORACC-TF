"""P-001 M7 regression tests for explicit sign-roundtrip exception reasons."""

from __future__ import annotations

from oracc_tf import roundtrip, words


def test_unreadable_x_slot_is_explicit_source_exception():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.x",
        "f": {
            "form": "x",
            "gdl": [{"x": "ellipsis", "break": "missing"}],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate is None
    assert not result.exact
    assert result.reason == "unreadable_sign"


def test_bracket_break_markup_is_not_called_plain_spelling_difference():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.break",
        "f": {
            "form": "[a]",
            "gdl": [{
                "v": "a",
                "utf8": "𒀀",
                "breakStart": "1",
                "breakEnd": "1",
                "break": "damaged",
            }],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate == "a"
    assert not result.exact
    assert result.reason == "slot_markup"


def test_source_h_normalization_of_gdl_h_with_breve_is_explicit():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.h",
        "f": {
            "form": "hab-ta",
            "gdl": [
                {"v": "ḫab", "utf8": "𒄩", "delim": "-"},
                {"v": "ta", "utf8": "𒋫"},
            ],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate == "ḫab-ta"
    assert not result.exact
    assert result.reason == "source_orthography"


def test_source_orthography_does_not_hide_unrelated_spelling_change():
    word = words.from_source({
        "node": "l",
        "id": "QTEST.other",
        "f": {
            "form": "hab-du",
            "gdl": [
                {"v": "ḫab", "utf8": "𒄩", "delim": "-"},
                {"v": "ta", "utf8": "𒋫"},
            ],
        },
    }, start_slot=1)

    result = roundtrip.evaluate_word(word)

    assert result.candidate == "ḫab-ta"
    assert not result.exact
    assert result.reason == "slot_spelling"
