"""#32: Real ETCSRI Q000377 source GDL modifiers in a composite sign.

The source word Q000377.l02b7a includes b=AŠ and m=t under AŠ@t.
Those modifier objects do not contribute independent sign slots.
"""
from __future__ import annotations
import json
import pytest
from oracc_tf import gdl, paths

SOURCE = paths.DATA / "etcsri" / "corpusjson" / "Q000377.json"


def _real_source_word() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    assert source["textid"] == "Q000377" and source["project"] == "etcsri"
    stack = [source]
    while stack:
        entry = stack.pop()
        if entry.get("node") == "l" and entry.get("id") == "Q000377.l02b7a":
            return entry
        stack.extend(entry.get("cdl") or [])
    raise AssertionError("pinned actual Q000377 word is missing")


@pytest.mark.corpus
def test_q000377_modifier_objects_do_not_invent_extra_signs() -> None:
    word = _real_source_word()
    tree = word["f"]["gdl"]
    assert tree[0]["c"] == "|E₂×AŠ@t|"
    mods = tree[0]["seq"][2]["mods"]
    assert mods == [{"b": "AŠ"}, {"m": "t"}]
    found = list(gdl.classify_tree(tree, word_id=word["id"]))
    by_path = {item.src_path: item for item in found}
    for i, shape in enumerate(mods):
        path = f"{word['id']}/gdl[0]/seq[2]/mods[{i}]"
        item = by_path[path]
        assert item.disposition == gdl.Disposition.MODIFIER
        assert item.value == shape
    assert len(list(gdl.signs(tree, word_id=word["id"]))) == 2
    assert gdl.resolve_src_path(
        tree, f"{word['id']}/gdl[0]/seq[2]/mods[0]", word_id=word["id"]
    ) == {"b": "AŠ"}


@pytest.mark.parametrize("entry", [{"b": "AŠ"}, {"m": "t"}])
def test_source_modifier_shape_only_valid_inside_mods(entry: dict) -> None:
    with pytest.raises(gdl.UnknownGDLShape, match="unknown GDL shape"):
        list(gdl.classify_tree([entry], word_id="Q.negative"))
    with pytest.raises(gdl.UnknownGDLShape, match="unknown GDL shape"):
        list(gdl.classify_tree([{"seq": [entry]}], word_id="Q.negative"))


@pytest.mark.parametrize("entry", [
    {"b": 3}, {"m": ""}, {"b": "AŠ", "extra": "hidden"},
])
def test_malformed_modifier_source_does_not_silently_pass(entry: dict) -> None:
    with pytest.raises(gdl.UnknownGDLShape, match="modifier|shape"):
        list(gdl.classify_tree([{"seq": [{"mods": [entry]}]}], word_id="Q.bad"))
