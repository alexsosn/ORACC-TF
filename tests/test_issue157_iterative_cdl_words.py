"""RED-first behavioral regressions for a streaming ORACC CDL source walker.

Deep structural nesting is a possible *in-memory* event-tree edge case,
not a claim that the pinned ORACC source archive has this depth.
"""
from __future__ import annotations

import pytest

from oracc_tf import words


def _word(word_id: str) -> dict:
    # Empty GDL is a real source-compatible shape (zero-sign words exist).
    return {"node": "l", "id": word_id, "f": {"gdl": []}}


def test_source_word_traversal_handles_deep_cdl_without_python_recursion() -> None:
    doc: dict = {"node": "d", "cdl": [_word("deep.word")]}
    for _ in range(1500):
        doc = {"node": "d", "cdl": [doc]}

    assert [item["id"] for item in words.source_words(doc)] == ["deep.word"]
    # Normal conversion path should also preserve the zero-span word.
    rows = list(words.iter_words(doc, start_slot=17))
    assert [(row.source_id, row.slot_start, row.slot_end) for row in rows] == [
        ("deep.word", 17, 17)
    ]


def test_nested_cdl_order_and_iterator_laziness_are_unchanged() -> None:
    doc = {
        "node": "d",
        "cdl": [
            _word("first"),
            {"node": "d", "cdl": [_word("middle"), {"node": "d", "cdl": [_word("last")]}]},
            _word("after"),
        ],
    }
    assert [item["id"] for item in words.source_words(doc)] == [
        "first", "middle", "last", "after"
    ]
    assert [row.source_id for row in words.iter_words(doc)] == [
        "first", "middle", "last", "after"
    ]

    malformed = {"node": "d", "cdl": [_word("visible"), False]}
    source = words.source_words(malformed)
    assert next(source)["id"] == "visible"
    with pytest.raises(words.InvalidWordSource, match=r"document/cdl\[1\]: child is bool"):
        next(source)


def test_invalid_children_and_non_list_cdl_still_fail_closed() -> None:
    with pytest.raises(words.InvalidWordSource, match=r"document: 'cdl' is str"):
        list(words.source_words({"node": "d", "cdl": "unexpected"}))
    with pytest.raises(words.InvalidWordSource, match=r"document/cdl\[0\]/cdl\[1\]: child is int"):
        list(words.source_words({
            "node": "d",
            "cdl": [{"node": "d", "cdl": [_word("first"), 3]}],
        }))


def test_wide_cdl_stays_lazy_instead_of_prefetching_all_siblings() -> None:
    """A streaming walker must not touch late siblings until they are visited."""
    class GuardedSiblings(list):
        allow_tail = False

        def __getitem__(self, index: int) -> object:
            if index > 0 and not self.allow_tail:
                raise AssertionError("walker eagerly inspected a later sibling")
            return super().__getitem__(index)

        def __iter__(self):
            for index in range(len(self)):
                yield self[index]

    siblings = GuardedSiblings([_word("early"), *(_word(f"late-{i}") for i in range(100))])
    source = words.source_words({"node": "d", "cdl": siblings})
    assert next(source)["id"] == "early"
    siblings.allow_tail = True
    assert [node["id"] for node in source] == [f"late-{i}" for i in range(100)]
