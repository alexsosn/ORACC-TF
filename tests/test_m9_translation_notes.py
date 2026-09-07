"""P-001 M9 — preserve serialized XTR note links without adjacency guesses."""

from __future__ import annotations

from oracc_tf import translations


XTR = "http://oracc.org/ns/xtr/1.0"
XML = f"""\
<TEI xmlns:xtr="{XTR}" xml:id="Q001801_project-en">
  <text><body>
    <div3 type="tr" subtype="tr" xml:id="Q001801_project-en.0"
          xtr:sref="Q001801.1" xtr:eref="Q001801.2" xtr:rows="2">
      The king<span class="notelink" xtr:noteref="Q001801_project-en.n1">1</span> spoke.
    </div3>
    <div class="note" xml:id="Q001801_project-en.n1">
      <p><span class="notemark">1</span> Variant reading.</p>
      <p>Second paragraph.</p>
    </div>
  </body></text>
</TEI>
"""


def test_serialized_note_link_becomes_recoverable_note_on_translation_unit():
    (unit,) = translations.parse_tei_text(
        XML,
        document_key="riao/ria1:Q001801",
        source_name="tei.zip",
    )

    assert len(unit.notes) == 1
    note = unit.notes[0]
    assert note.source_id == "Q001801_project-en.n1"
    assert note.text == "1 Variant reading. Second paragraph."
    assert "Variant reading." in note.text_raw
    assert note.source_name == "tei.zip"


def test_unreferenced_note_is_not_attached_by_position_guess():
    unlinked = XML.replace(
        '<span class="notelink" xtr:noteref="Q001801_project-en.n1">1</span>',
        "1",
    )
    (unit,) = translations.parse_tei_text(
        unlinked,
        document_key="riao/ria1:Q001801",
    )
    assert unit.notes == ()
