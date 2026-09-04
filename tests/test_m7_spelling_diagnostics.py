"""Diagnostic RED for residual sign-only spelling mismatches in P-001 M7."""

from __future__ import annotations

from collections import Counter, defaultdict
import unicodedata

import pytest

from oracc_tf import loader, paths, roundtrip, words


@pytest.mark.corpus
def test_residual_slot_spelling_shapes_are_exposed_before_pinning():
    relations: Counter[str] = Counter()
    other_feature_profiles: Counter[tuple[str, ...]] = Counter()
    other_sign_key_profiles: Counter[tuple[str, ...]] = Counter()
    samples: dict[str, list[dict[str, object]]] = defaultdict(list)

    for edition in loader.iter_editions(paths.DATA, skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            result = roundtrip.evaluate_word(word)
            if result.reason != "slot_spelling":
                continue

            form = word.form or ""
            candidate = result.candidate or ""
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

            if relation == "other":
                other_feature_profiles[tuple(sorted(word.features))] += 1
                for sign in word.signs:
                    other_sign_key_profiles[tuple(sorted(sign.value))] += 1

            if len(samples[relation]) < 8:
                samples[relation].append({
                    "document": edition.key,
                    "word": word.source_id,
                    "form": word.form,
                    "frag": word.frag,
                    "candidate": result.candidate,
                    "feature_keys": sorted(word.features),
                    "signs": [dict(sign.value) for sign in word.signs],
                })

    assert not relations, {
        "relations": dict(relations.most_common()),
        "other_feature_profiles": dict(other_feature_profiles.most_common(8)),
        "other_sign_key_profiles": dict(other_sign_key_profiles.most_common(12)),
        "samples": dict(samples),
    }
