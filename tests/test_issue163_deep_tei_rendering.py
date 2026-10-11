"""RED-first TEI mixed-content regressions: deep nesting without text loss.

The 1,500-level tree is an in-memory stability edge case, not a statement
about the depth of pinned 2024 official RIAO TEI material.
"""
from __future__ import annotations

from xml.etree import ElementTree as ET

from oracc_tf import translations


TEI = "http://www.tei-c.org/ns/1.0"


def _tag(name: str) -> str:
    return f"{{{TEI}}}{name}"


def test_deep_markup_keeps_plain_text_and_canonical_raw_without_recursion() -> None:
    unit = ET.Element(_tag("div3"))
    unit.text = "Before "
    parent = unit
    for index in range(1500):
        attrs = {"type": "i", "rend": "special"} if index == 0 else {}
        parent = ET.SubElement(parent, _tag("hi"), attrs)
    parent.text = "deep <& text"
    parent.tail = " after deep"
    note = ET.SubElement(unit, _tag("note"))
    note.text = "Do not copy this editorial note"
    note.tail = " after note"

    text, raw = translations._translation_content(unit)
    assert text == "Before deep <& text after deep after note"
    assert "Do not copy this editorial note" not in text + raw
    assert raw.startswith('Before <hi rend="special" type="i"><hi>')
    assert raw.count("<hi") == raw.count("</hi>") == 1500
    assert "deep &lt;&amp; text" in raw
    assert raw.endswith(" after note")
    assert " after deep" in raw


def test_deep_note_tree_is_excluded_but_note_tail_survives() -> None:
    unit = ET.Element(_tag("div3"))
    unit.text = "start"
    note = ET.SubElement(unit, _tag("note"))
    parent = note
    for _ in range(1500):
        parent = ET.SubElement(parent, _tag("hi"))
    parent.text = "forbidden"
    note.tail = " visible after note"
    final = ET.SubElement(unit, _tag("p"))
    final.text = " ending"

    text, raw = translations._translation_content(unit)
    assert text == "start visible after note ending"
    assert raw == "start visible after note<p> ending</p>"
    assert "forbidden" not in text + raw


def test_mixed_notes_nested_tails_namespace_and_attribute_escaping() -> None:
    unit = ET.Element(_tag("div3"))
    unit.text = "A & B < "
    hi = ET.SubElement(unit, _tag("hi"))
    hi.set("type", "i")
    hi.set(_tag("rend"), 'quote & "<')
    hi.text = "word <& "
    note = ET.SubElement(hi, _tag("note"))
    note.text = "SECRET"
    note.tail = "after inner note & "
    hi.tail = "after hi "
    outer_note = ET.SubElement(unit, _tag("note"))
    outer_note.text = "HIDDEN"
    outer_note.tail = "after outer note"

    text, raw = translations._translation_content(unit)
    assert text == "A & B < word <& after inner note & after hi after outer note"
    assert raw == (
        'A &amp; B &lt; <hi rend="quote &amp; &quot;&lt;" type="i">'
        "word &lt;&amp; after inner note &amp; </hi>"
        "after hi after outer note"
    )
    assert "SECRET" not in raw and "HIDDEN" not in raw
