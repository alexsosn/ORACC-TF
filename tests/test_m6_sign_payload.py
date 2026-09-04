"""P-001 M6 regression: the joined TF must preserve M1 sign semantics."""

from __future__ import annotations

import json

from oracc_tf import corpus, loader, metadata, paths


def _load(rel: str) -> loader.Edition:
    subproject, name = rel.rsplit("/", 1)
    return loader.load_edition(paths.DATA / subproject / "corpusjson" / name)


def _slot_by_identity(api, *, word_id: str, utf8: str) -> int:
    matches = [
        slot
        for slot in range(1, api.F.otype.maxSlot + 1)
        if api.F.word_id.v(slot) == word_id and api.F.utf8.v(slot) == utf8
    ]
    assert len(matches) == 1, (word_id, utf8, matches)
    return matches[0]


def test_joined_tf_preserves_composite_sign_parent_payload(tmp_path):
    """M6 must not turn M1's content-based guarantee back into a count-only one."""
    editions = (
        _load("riao/ria1/Q005620.json"),
        _load("riao/ria1/Q005278.json"),
    )
    corpus.build_tf(
        tmp_path,
        editions=editions,
        metadata_index=metadata.MetadataIndex.empty(),
    )
    api = corpus.load_tf(tmp_path)

    numeral = _slot_by_identity(api, word_id="Q005620.l009d1", utf8="𒁹")
    assert api.F.gdl_id.v(numeral) == "Q005620.44.1.0"
    assert api.F.gdl_form.v(numeral) == "1"
    assert api.F.gdl_sexified.v(numeral) == "1(diš)"
    assert json.loads(api.F.sign_json.v(numeral)) == {
        "n": "n",
        "sexified": "1(diš)",
        "form": "1",
        "utf8": "𒁹",
        "id": "Q005620.44.1.0",
        "seq": [{"r": "1"}],
    }

    qualified = _slot_by_identity(api, word_id="Q005278.l009f8", utf8="𒊕")
    assert api.F.gdl_id.v(qualified) == "Q005278.5.1.1"
    assert json.loads(api.F.sign_json.v(qualified)) == {
        "q": "surₓ(SAG)",
        "utf8": "𒊕",
        "id": "Q005278.5.1.1",
        "qualified": [{"v": "surₓ"}, {"s": "SAG"}],
    }
