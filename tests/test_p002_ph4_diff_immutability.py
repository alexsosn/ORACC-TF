"""Adversarial immutability contracts for P-002 PH4 provenance records."""

from __future__ import annotations

import importlib

import pytest


def _module():
    return importlib.import_module("oracc_tf.source_diff")


def _snapshot(module, *, state: str, form: str):
    document = {
        "type": "cdl",
        "textid": "Q000001",
        "cdl": [
            {
                "node": "l",
                "id": "w1",
                "f": {"form": form, "cf": form},
            }
        ],
    }
    return module.snapshot_archive(
        dataset="fixture-dataset",
        archive="fixture-archive",
        source_state=state,
        oracc_utc_timestamp="2026-08-07T12:00:00",
        licence="CC0",
        documents=[module.SourceDocument(subproject="p/a", document=document)],
    )


def _changed_diff(module):
    before = _snapshot(module, state="sha256:" + "a" * 64, form="a")
    after = _snapshot(module, state="sha256:" + "b" * 64, form="b")
    return module.diff_snapshots(before, after)


def test_source_diff_text_word_delta_mapping_is_immutable():
    module = _module()
    diff = _changed_diff(module)
    original = dict(diff.text_word_deltas)

    with pytest.raises(TypeError):
        diff.text_word_deltas["p/a:Q000001"] = 999

    assert dict(diff.text_word_deltas) == original


def test_source_diff_subproject_delta_mapping_is_immutable():
    module = _module()
    diff = _changed_diff(module)
    original = dict(diff.subproject_deltas)

    with pytest.raises(TypeError):
        diff.subproject_deltas["p/a"] = diff.subproject_deltas["p/a"]

    assert dict(diff.subproject_deltas) == original
