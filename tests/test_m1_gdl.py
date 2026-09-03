"""P-001 M1 - semantic GDL classification.

These tests are deliberately content-based. The old leaf rule happened to
produce almost the right total while replacing real composite signs with
rendering/operator children. M1 therefore pins the identity and disposition
of the hazardous objects, not merely a sign count.
"""

from __future__ import annotations

from collections import Counter

import pytest

from oracc_tf import gdl, loader, paths

NUMERAL = "riao/ria1/Q005620.json"
QUALIFIED = "riao/ria1/Q005278.json"


def src(rel: str):
    sub, name = rel.rsplit("/", 1)
    return paths.DATA / sub / "corpusjson" / name


def word_by_id(doc: dict, word_id: str) -> dict:
    stack = [doc]
    while stack:
        node = stack.pop()
        if node.get("node") == "l" and node.get("id") == word_id:
            return node
        stack.extend(node.get("cdl") or [])
    raise AssertionError(f"word not found: {word_id}")


def test_composite_numeral_parent_is_the_slot_and_r_child_is_rendering():
    tree = [{
        "n": "n", "sexified": "1(diš)", "form": "1", "utf8": "𒁹",
        "id": "Q005620.44.1.0", "seq": [{"r": "1"}],
    }]
    classified = list(gdl.classify_tree(tree, word_id="Q005620.l00a19"))
    assert [item.disposition for item in classified] == [
        gdl.Disposition.SLOT, gdl.Disposition.RENDERING,
    ]
    slots = list(gdl.signs(tree, word_id="Q005620.l00a19"))
    assert len(slots) == 1
    assert slots[0].value["utf8"] == "𒁹"
    assert slots[0].value["sexified"] == "1(diš)"
    assert slots[0].value["form"] == "1"
    assert slots[0].value["id"] == "Q005620.44.1.0"
    assert slots[0].src_path == "Q005620.l00a19/gdl[0]"


def test_qualified_parent_with_utf8_is_one_slot_and_children_are_modifiers():
    tree = [{
        "q": "surₓ(SAG)", "utf8": "𒊕", "id": "Q005278.5.1.1",
        "qualified": [{"v": "surₓ"}, {"s": "SAG"}],
    }]
    classified = list(gdl.classify_tree(tree, word_id="Q005278.l009f8"))
    assert Counter(item.disposition for item in classified) == Counter({
        gdl.Disposition.SLOT: 1, gdl.Disposition.MODIFIER: 2,
    })
    assert [item.value.get("q") for item in gdl.signs(
        tree, word_id="Q005278.l009f8"
    )] == ["surₓ(SAG)"]


def test_compound_parent_is_slot_and_operator_is_never_a_slot():
    tree = [{
        "q": "ŠIGₓ(|URU×GU|)",
        "qualified": [
            {"v": "ŠIGₓ"},
            {"c": "|URU×GU|", "utf8": "𒍀", "seq": [
                {"s": "URU"}, {"o": "containing"}, {"s": "GU"},
            ]},
        ],
    }]
    classified = list(gdl.classify_tree(tree, word_id="Q005620.l00999"))
    assert Counter(item.disposition for item in classified) == Counter({
        gdl.Disposition.STRUCTURAL: 1,
        gdl.Disposition.SLOT: 2,
        gdl.Disposition.MODIFIER: 3,
    })
    slots = list(gdl.signs(tree, word_id="Q005620.l00999"))
    assert [slot.value.get("v") or slot.value.get("c") for slot in slots] == [
        "ŠIGₓ", "|URU×GU|"
    ]
    assert slots[1].value["utf8"] == "𒍀"
    assert all("o" not in slot.value for slot in slots)


def test_ellipsis_with_o_markup_metadata_remains_a_slot():
    # Real corpus shape: Q005621.l00736.  `o` here is bracket/original markup,
    # not a standalone compound operator node.
    source = {
        "x": "ellipsis",
        "id": "Q005621.68.7.0",
        "breakStart": "1",
        "break": "missing",
        "o": "[",
    }
    classified = list(gdl.classify_tree([source], word_id="Q005621.l00736"))
    assert len(classified) == 1
    assert classified[0].disposition == gdl.Disposition.SLOT
    assert classified[0].value == source


def test_standalone_operator_is_modifier_not_slot():
    classified = list(gdl.classify_tree(
        [{"o": "containing"}], word_id="Q.synthetic"
    ))
    assert len(classified) == 1
    assert classified[0].disposition == gdl.Disposition.MODIFIER
    assert list(gdl.signs([{"o": "containing"}], word_id="Q.synthetic")) == []


def test_unknown_leaf_shape_fails_loudly_with_source_path():
    with pytest.raises(gdl.UnknownGDLShape, match=r"Q\.l1/gdl\[0\]"):
        list(gdl.classify_tree([{"mystery": "shape"}], word_id="Q.l1"))


def test_q005620_numeral_keeps_parent_content_and_src_path_resolves():
    edition = loader.load_edition(src(NUMERAL))
    target = None
    stack = [edition.doc]
    while stack and target is None:
        node = stack.pop()
        if node.get("node") == "l":
            for item in gdl.signs((node.get("f") or {}).get("gdl") or [],
                                  word_id=node["id"]):
                if item.value.get("id") == "Q005620.44.1.0":
                    target = (node, item)
                    break
        stack.extend(node.get("cdl") or [])
    assert target is not None
    word, slot = target
    assert slot.value["utf8"] == "𒁹"
    assert slot.value["sexified"] == "1(diš)"
    assert slot.value["form"] == "1"
    assert gdl.resolve_src_path(
        (word.get("f") or {})["gdl"], slot.src_path, word_id=word["id"]
    ) == slot.value
    classified = list(gdl.classify_tree(
        (word.get("f") or {})["gdl"], word_id=word["id"]
    ))
    assert not any(
        item.disposition == gdl.Disposition.SLOT and item.value == {"r": "1"}
        for item in classified
    )


def test_q005278_qualified_sign_is_parent_borne_single_slot():
    edition = loader.load_edition(src(QUALIFIED))
    word = word_by_id(edition.doc, "Q005278.l009f8")
    slots = list(gdl.signs((word.get("f") or {})["gdl"], word_id=word["id"]))
    qualified = [slot for slot in slots if slot.value.get("q") == "surₓ(SAG)"]
    assert len(qualified) == 1
    assert qualified[0].value["utf8"] == "𒊕"
    assert qualified[0].value["id"] == "Q005278.5.1.1"
    assert gdl.resolve_src_path(
        (word.get("f") or {})["gdl"], qualified[0].src_path, word_id=word["id"]
    ) == qualified[0].value


@pytest.mark.corpus
def test_four_way_gdl_census_matches_measured_ground_truth():
    census = gdl.census(paths.DATA)
    assert census.slot == 792651
    assert census.structural == 178869
    assert census.modifier == 10
    assert census.rendering == 6584
    assert census.total == 978114
    assert census.unknown == 0
