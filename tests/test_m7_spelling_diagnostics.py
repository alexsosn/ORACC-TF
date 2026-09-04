"""Diagnostic RED for residual sign-only spelling mismatches in P-001 M7."""

from __future__ import annotations

from collections import Counter

import pytest

from oracc_tf import loader, paths, roundtrip, words


@pytest.mark.corpus
def test_residual_slot_spelling_shapes_are_exposed_before_pinning():
    key_profiles: Counter[tuple[str, ...]] = Counter()
    continuation_profiles: Counter[tuple[str, ...]] = Counter()
    samples: list[dict[str, object]] = []

    continuation_keys = {"headform", "tailform", "contrefs", "cont", "continuation"}

    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            result = roundtrip.evaluate_word(word)
            if result.reason != "slot_spelling":
                continue

            keys = tuple(sorted(word.features))
            key_profiles[keys] += 1
            continuation_profiles[tuple(sorted(continuation_keys & set(word.features)))] += 1

            if len(samples) < 12:
                samples.append({
                    "document": edition.key,
                    "word": word.source_id,
                    "form": word.form,
                    "candidate": result.candidate,
                    "features": dict(word.features),
                    "signs": [dict(sign.value) for sign in word.signs],
                })

    assert not key_profiles, {
        "key_profiles": dict(key_profiles.most_common()),
        "continuation_profiles": dict(continuation_profiles.most_common()),
        "samples": samples,
    }
