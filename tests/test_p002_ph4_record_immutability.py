"""Adversarial REDs for immutable public PH4 provenance records."""

import pytest

from oracc_tf import source_diff as module


def _text(key="p/a:Q000001"):
    subproject, text_id = key.rsplit(":", 1)
    return module.TextState(
        key=key,
        subproject=subproject,
        text_id=text_id,
        content_sha256="a" * 64,
        word_count=1,
        lemma_count=1,
        gdl_shapes=(),
        chunk_shapes=(),
    )


def test_direct_archive_snapshot_copies_and_freezes_text_mapping():
    original = {"p/a:Q000001": _text()}
    snap = module.ArchiveSnapshot(
        dataset="fixture-dataset",
        archive="fixture-archive",
        source_state="sha256:" + "a" * 64,
        oracc_utc_timestamp="2026-08-07T12:00:00",
        licence="CC0",
        texts=original,
    )

    original["p/a:Q999999"] = _text("p/a:Q999999")
    assert "p/a:Q999999" not in snap.texts
    with pytest.raises(TypeError):
        snap.texts["p/a:Q999999"] = _text("p/a:Q999999")


def _direct_diff(word_deltas, subproject_deltas):
    return module.SourceDiff(
        dataset="fixture-dataset",
        archive="fixture-archive",
        before_source_state="sha256:" + "a" * 64,
        after_source_state="sha256:" + "b" * 64,
        added=(),
        removed=(),
        modified=("p/a:Q000001",),
        text_word_deltas=word_deltas,
        subproject_deltas=subproject_deltas,
        new_gdl_shapes=(),
        new_chunk_shapes=(),
        licence_before="CC0",
        licence_after="CC0",
        oracc_utc_timestamp_before="2026-08-07T12:00:00",
        oracc_utc_timestamp_after="2026-08-08T12:00:00",
    )


def test_direct_source_diff_copies_and_freezes_word_delta_mapping():
    original = {"p/a:Q000001": 0}
    diff = _direct_diff(original, {})

    original["p/a:Q999999"] = 999
    assert "p/a:Q999999" not in diff.text_word_deltas
    with pytest.raises(TypeError):
        diff.text_word_deltas["p/a:Q999999"] = 999


def test_direct_source_diff_copies_and_freezes_subproject_delta_mapping():
    delta = module.SubprojectDelta(1, 1, 0, 1, 1, 0)
    original = {"p/a": delta}
    diff = _direct_diff({}, original)

    original["p/evil"] = delta
    assert "p/evil" not in diff.subproject_deltas
    with pytest.raises(TypeError):
        diff.subproject_deltas["p/evil"] = delta
