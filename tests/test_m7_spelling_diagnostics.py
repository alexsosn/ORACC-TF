"""Diagnostic RED for residual sign-only spelling mismatches in P-001 M7."""

from __future__ import annotations

import pytest

from oracc_tf import loader, paths, roundtrip, words


@pytest.mark.corpus
def test_residual_slot_spelling_examples_are_exposed_before_pinning():
    samples: list[dict[str, object]] = []
    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            result = roundtrip.evaluate_word(word)
            if result.reason != "slot_spelling":
                continue
            samples.append({
                "document": edition.key,
                "word": word.source_id,
                "form": word.form,
                "candidate": result.candidate,
                "signs": [dict(sign.value) for sign in word.signs],
            })
            if len(samples) == 20:
                break
        if len(samples) == 20:
            break

    assert not samples, samples
