"""Full 1,456-edition preflight for GDL source-shape and semantic-sign drift.

This is deliberately cheaper than generating all TF features before learning
the next unrecognised source shape: iterate real ORACC source words and use
the same sign classifier as the converter. The legacy source leaf census is
an independently implemented cross-check, not a license to fabricate slots.
"""
from __future__ import annotations

import json

import pytest

from oracc_tf import gdl, paths, words


@pytest.mark.corpus
def test_all_real_etcsri_gdl_shapes_and_sign_population() -> None:
    root = paths.DATA / "etcsri" / "corpusjson"
    members = sorted(root.glob("*.json"))
    assert len(members) == 1456
    total_words = 0
    semantic_signs = 0
    with_unicode = 0
    for source in members:
        doc = json.loads(source.read_text(encoding="utf-8"))
        assert doc["textid"] == source.stem
        assert doc["project"] == "etcsri"
        for word in words.source_words(doc):
            total_words += 1
            try:
                signs = list(gdl.signs(word["f"]["gdl"], word_id=word["id"]))
            except (ValueError, TypeError, KeyError) as exc:
                raise AssertionError(
                    f"{source.name}:{word['id']}: unclassified real source GDL"
                ) from exc
            semantic_signs += len(signs)
            with_unicode += sum(bool(item.value.get("utf8")) for item in signs)
    assert total_words == 29573
    assert semantic_signs == 68403, (
        "GDL semantic slot total differs from independent R-007 sign census"
    )
    assert with_unicode == 67624
