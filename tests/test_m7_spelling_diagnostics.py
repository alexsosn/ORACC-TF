"""Diagnostic RED for residual sign-only spelling mismatches in P-001 M7."""

from __future__ import annotations

from collections import Counter
import unicodedata

import pytest

from oracc_tf import loader, paths, roundtrip, words


@pytest.mark.corpus
def test_residual_slot_spelling_shapes_are_exposed_before_pinning():
    relations: Counter[str] = Counter()
    continuation_profiles: Counter[tuple[str, ...]] = Counter()
    feature_flags: Counter[str] = Counter()

    continuation_keys = {"headform", "tailform", "contrefs", "cont", "continuation"}

    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            result = roundtrip.evaluate_word(word)
            if result.reason != "slot_spelling":
                continue

            form = word.form or ""
            candidate = result.candidate or ""
            continuation_profiles[tuple(sorted(continuation_keys & set(word.features)))] += 1
            for key in continuation_keys:
                if key in word.features:
                    feature_flags[key] += 1

            if candidate == form:
                relation = "equal"
            elif candidate.rstrip("-.:") == form:
                relation = "candidate_trailing_delimiter"
            elif form.rstrip("-.:") == candidate:
                relation = "form_trailing_delimiter"
            elif form.startswith(candidate):
                relation = "candidate_prefix_of_form"
            elif candidate.startswith(form):
                relation = "form_prefix_of_candidate"
            elif word.frag is not None and candidate == word.frag:
                relation = "candidate_equals_frag"
            elif word.frag is not None and form == word.frag:
                relation = "form_equals_frag"
            elif unicodedata.normalize("NFC", candidate) == unicodedata.normalize("NFC", form):
                relation = "unicode_normalization_only"
            else:
                relation = "other"
            relations[relation] += 1

    assert not relations, {
        "relations": dict(relations.most_common()),
        "continuation_profiles": {
            "+".join(profile) if profile else "none": count
            for profile, count in continuation_profiles.most_common()
        },
        "feature_flags": dict(feature_flags.most_common()),
    }
