"""P-002 PH4 RED contracts for deterministic source-state diff reports."""

from __future__ import annotations

import importlib
import json

import pytest


def api():
    return importlib.import_module("oracc_tf.source_diff")


def word(word_id: str, *, cf: str | None = None, norm: str | None = None, sig: str | None = None, gdl=None):
    features: dict[str, object] = {"form": word_id}
    if cf is not None:
        features["cf"] = cf
    if norm is not None:
        features["norm"] = norm
    if gdl is not None:
        features["gdl"] = gdl
    out: dict[str, object] = {"node": "l", "id": word_id, "f": features}
    if sig is not None:
        out["sig"] = sig
    return out


def doc(text_id: str, *children: dict[str, object]):
    return {"type": "cdl", "textid": text_id, "cdl": list(children)}


def source(module, subproject: str, document: dict[str, object]):
    return module.SourceDocument(subproject=subproject, document=document)


def snapshot(module, *, documents, state="sha256:" + "a" * 64, licence="CC0", timestamp="2026-08-07T12:00:00"):
    return module.snapshot_archive(
        dataset="fixture-dataset",
        archive="fixture-archive",
        source_state=state,
        oracc_utc_timestamp=timestamp,
        licence=licence,
        documents=documents,
    )


def test_canonical_text_hash_ignores_mapping_key_order_but_preserves_list_order():
    module = api()
    first = {"textid": "Q000001", "type": "cdl", "cdl": [{"node": "d", "type": "line-start", "label": "1"}]}
    reordered = {"cdl": [{"label": "1", "type": "line-start", "node": "d"}], "type": "cdl", "textid": "Q000001"}
    reversed_list = {"textid": "Q000001", "type": "cdl", "cdl": [{"node": "d", "label": "2"}, {"node": "d", "label": "1"}]}

    assert module.canonical_document_sha256(first) == module.canonical_document_sha256(reordered)
    assert module.canonical_document_sha256(first) != module.canonical_document_sha256(reversed_list)


def test_qualified_document_identity_prevents_bare_q_collision():
    module = api()
    snap = snapshot(
        module,
        documents=[
            source(module, "rinap/rinap5", doc("Q003840", word("a", cf="a"))),
            source(module, "rinap/rinap5p1", doc("Q003840", word("b", cf="b"))),
        ],
    )

    assert tuple(snap.texts) == ("rinap/rinap5:Q003840", "rinap/rinap5p1:Q003840")
    assert snap.texts["rinap/rinap5:Q003840"].content_sha256 != snap.texts["rinap/rinap5p1:Q003840"].content_sha256


def test_added_removed_modified_texts_and_word_deltas_reconcile():
    module = api()
    before = snapshot(
        module,
        documents=[
            source(module, "p/a", doc("Q000001", word("a", cf="a"))),
            source(module, "p/a", doc("Q000002", word("b", cf="b"), word("c", norm="C"))),
        ],
    )
    after = snapshot(
        module,
        state="sha256:" + "b" * 64,
        documents=[
            source(module, "p/a", doc("Q000002", word("b", cf="b"), word("c", norm="C"), word("d", sig="x"))),
            source(module, "p/a", doc("Q000003", word("e", cf="e"), word("f", cf="f"))),
        ],
    )

    diff = module.diff_snapshots(before, after)

    assert diff.added == ("p/a:Q000003",)
    assert diff.removed == ("p/a:Q000001",)
    assert diff.modified == ("p/a:Q000002",)
    assert diff.text_word_deltas == {
        "p/a:Q000001": -1,
        "p/a:Q000002": 1,
        "p/a:Q000003": 2,
    }
    aggregate = diff.subproject_deltas["p/a"]
    assert aggregate.before_words == 3
    assert aggregate.after_words == 5
    assert aggregate.word_delta == 2
    # norm-only is deliberately not lemma evidence; cf and sig are.
    assert aggregate.before_lemmas == 2
    assert aggregate.after_lemmas == 4
    assert aggregate.lemma_delta == 2
    assert sum(diff.text_word_deltas.values()) == aggregate.word_delta


def test_new_gdl_and_chunk_shapes_are_enumerated_without_semantic_classification():
    module = api()
    before = snapshot(
        module,
        documents=[
            source(
                module,
                "p/a",
                doc(
                    "Q000001",
                    {"node": "c", "type": "phrase", "subtype": "NP", "cdl": [word("a", cf="a", gdl=[{"v": "a"}])]},
                ),
            )
        ],
    )
    after = snapshot(
        module,
        state="sha256:" + "b" * 64,
        documents=[
            source(
                module,
                "p/a",
                doc(
                    "Q000001",
                    {"node": "c", "type": "new-kind", "subtype": "X", "cdl": [word("a", cf="a", gdl=[{"v": "a", "future": 1, "group": [{"x": "x"}]}])]},
                ),
            )
        ],
    )

    diff = module.diff_snapshots(before, after)

    assert ("future", "group", "v") in diff.new_gdl_shapes
    assert ("x",) in diff.new_gdl_shapes
    assert ("new-kind", "X") in diff.new_chunk_shapes
    assert ("phrase", "NP") not in diff.new_chunk_shapes


def test_licence_and_timestamp_changes_are_verbatim_independent_facts():
    module = api()
    documents = [source(module, "p/a", doc("Q000001", word("a", cf="a")))]
    before = snapshot(module, documents=documents, licence="CC0", timestamp="2025-01-02T03:04:05")
    after = snapshot(
        module,
        documents=documents,
        state="sha256:" + "b" * 64,
        licence="CC BY-SA 3.0; citation requested",
        timestamp="2026-08-07T17:50:00",
    )

    diff = module.diff_snapshots(before, after)

    assert diff.licence_before == "CC0"
    assert diff.licence_after == "CC BY-SA 3.0; citation requested"
    assert diff.oracc_utc_timestamp_before == "2025-01-02T03:04:05"
    assert diff.oracc_utc_timestamp_after == "2026-08-07T17:50:00"
    assert diff.added == diff.removed == diff.modified == ()


def test_identical_snapshot_has_empty_semantic_diff_and_stable_serialization():
    module = api()
    snap = snapshot(module, documents=[source(module, "p/a", doc("Q000001", word("a", cf="a")))])

    diff = module.diff_snapshots(snap, snap)
    first = module.render_diff(diff)
    second = module.render_diff(module.diff_snapshots(snap, snap))

    assert diff.empty is True
    assert diff.added == diff.removed == diff.modified == ()
    assert diff.new_gdl_shapes == ()
    assert diff.new_chunk_shapes == ()
    assert first == second
    assert first.endswith(b"\n")
    decoded = json.loads(first)
    assert decoded["before"]["source_state"] == "sha256:" + "a" * 64
    assert decoded["after"]["source_state"] == "sha256:" + "a" * 64


def test_cross_archive_diff_and_duplicate_or_mismatched_identity_fail_closed():
    module = api()
    good = source(module, "p/a", doc("Q000001", word("a")))
    with pytest.raises(module.SourceDiffError):
        snapshot(module, documents=[good, good])

    with pytest.raises(module.SourceDiffError):
        snapshot(module, documents=[source(module, "p/a", {"textid": "", "cdl": []})])

    left = snapshot(module, documents=[good])
    right = module.snapshot_archive(
        dataset="other-dataset",
        archive="fixture-archive",
        source_state="sha256:" + "b" * 64,
        oracc_utc_timestamp="2026-08-07T12:00:00",
        licence="CC0",
        documents=[good],
    )
    with pytest.raises(module.SourceDiffError):
        module.diff_snapshots(left, right)


def test_timestamp_validation_rejects_calendar_and_clock_impossibilities():
    module = api()
    documents = [source(module, "p/a", doc("Q000001", word("a")))]

    for impossible in ("2026-02-30T12:00:00", "2026-08-07T24:00:00", "2026-13-01T00:00:00"):
        with pytest.raises(module.SourceDiffError):
            snapshot(module, documents=documents, timestamp=impossible)


def test_unknown_nested_gdl_objects_are_enumerated_recursively():
    module = api()
    before = snapshot(
        module,
        documents=[source(module, "p/a", doc("Q000001", word("a", gdl=[{"v": "a"}])))],
    )
    after = snapshot(
        module,
        state="sha256:" + "b" * 64,
        documents=[
            source(
                module,
                "p/a",
                doc(
                    "Q000001",
                    word(
                        "a",
                        gdl=[
                            {
                                "v": "a",
                                "future_children": [
                                    {"novel_leaf": {"deep": "value"}}
                                ],
                            }
                        ],
                    ),
                ),
            )
        ],
    )

    diff = module.diff_snapshots(before, after)

    assert ("future_children", "v") in diff.new_gdl_shapes
    assert ("novel_leaf",) in diff.new_gdl_shapes
    assert ("deep",) in diff.new_gdl_shapes
