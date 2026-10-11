"""RED-first regressions for deep *in-memory* source GDL classification.

These synthetic depths do not assert that pinned ORACC JSON files are 1500
levels deep. Semantic slot suppression and source path fidelity matter more
than merely avoiding RecursionError.
"""
from __future__ import annotations

import pytest

from oracc_tf import gdl


def test_deep_structural_wrappers_reach_one_sign_with_resolvable_path() -> None:
    leaf: dict = {"v": "SIG"}
    for _ in range(1500):
        leaf = {"group": [leaf]}
    source = [leaf]
    classified = list(gdl.classify_tree(source, word_id="QDEEP.l1"))
    assert len(classified) == 1501
    assert all(x.disposition == gdl.Disposition.STRUCTURAL for x in classified[:-1])
    assert classified[-1].disposition == gdl.Disposition.SLOT
    assert classified[-1].src_path == (
        "QDEEP.l1/gdl[0]" + "/group[0]" * 1500
    )
    assert gdl.resolve_src_path(
        source, classified[-1].src_path, word_id="QDEEP.l1"
    ) is classified[-1].value
    slots = list(gdl.signs(source, word_id="QDEEP.l1"))
    assert len(slots) == 1
    assert slots[0].value == {"v": "SIG"}


def test_deep_sign_parent_suppresses_all_descendants() -> None:
    leaf: dict = {"v": "internal"}
    for _ in range(1500):
        leaf = {"qualified": [leaf]}
    source = [{"utf8": "𒁹", "seq": [leaf]}]
    classified = list(gdl.classify_tree(source, word_id="QSIGN.l1"))
    assert len(classified) == 1502
    assert classified[0].disposition == gdl.Disposition.SLOT
    assert all(item.disposition == gdl.Disposition.MODIFIER for item in classified[1:])
    assert len(list(gdl.signs(source, word_id="QSIGN.l1"))) == 1


def test_gdl_child_key_priority_sibling_order_and_modifier_rendering() -> None:
    source = [{
        "group": [{"v": "G1"}, {"v": "G2"}],
        "seq": [{"o": "containing"}, {"r": "drawing"}],
        "qualified": [{"s": "QA"}],
        "mods": [{"x": "MB"}],
    }]
    classified = list(gdl.classify_tree(source, word_id="QORDER.l1"))
    assert [x.src_path.rsplit("/", 1)[-1] for x in classified] == [
        "gdl[0]", "group[0]", "group[1]",
        "seq[0]", "seq[1]", "qualified[0]", "mods[0]",
    ]
    assert [x.disposition for x in classified] == [
        gdl.Disposition.STRUCTURAL,
        gdl.Disposition.SLOT, gdl.Disposition.SLOT,
        gdl.Disposition.MODIFIER, gdl.Disposition.RENDERING,
        gdl.Disposition.SLOT, gdl.Disposition.SLOT,
    ]


def test_source_validation_timing_and_error_paths_preserved() -> None:
    # Original slot parent is yielded before descendants are validated.
    source = gdl.classify_tree(
        [{"utf8": "𒁹", "seq": [7]}], word_id="QERR.l1"
    )
    assert next(source).disposition == gdl.Disposition.SLOT
    with pytest.raises(gdl.UnknownGDLShape, match=r"QERR.l1/gdl\[0\]/seq\[0\]: GDL child is int"):
        next(source)

    # Structural wrapper validates immediate child shape *before* yielding.
    with pytest.raises(gdl.UnknownGDLShape, match=r"QERR.l2/gdl\[0\]/group\[0\]: GDL child is int"):
        next(gdl.classify_tree([{"group": [7]}], word_id="QERR.l2"))

    # Suppression does not hide unknown nested editorial shapes.
    bad = {"utf8": "𒁹", "seq": [{"mystery": "unknown"}]}
    with pytest.raises(gdl.UnknownGDLShape, match="unknown nested GDL shape"):
        list(gdl.classify_tree([bad], word_id="QERR.l3"))

    # First source entry can be consumed before a malformed later entry.
    stream = gdl.classify_tree([{"v": "A"}, False], word_id="QERR.l4")
    assert next(stream).disposition == gdl.Disposition.SLOT
    with pytest.raises(gdl.UnknownGDLShape, match=r"QERR.l4/gdl\[1\]: GDL item is bool"):
        next(stream)
