"""P-001 M9 — TEI translation layer contract.

These tests deliberately precede production implementation.  The source model is
line-range alignment: translation units retain xtr:sref/xtr:eref exactly and are
not token-aligned or reconstructed from prose.
"""

from __future__ import annotations

from pathlib import Path

from oracc_tf import translations


XTR = "http://oracc.org/ns/xtr/1.0"
TEI = "http://www.tei-c.org/ns/1.0"


def _tei() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}" xmlns:xtr="{XTR}" xml:id="Q001801">
  <text><body>
    <div type="translation">
      <div3 type="tr" subtype="tr" xtr:sref="Q001801.1" xtr:eref="Q001801.15" xtr:rows="72">
        <p>Plain <hi type="i">italic</hi> and <seg type="r">(parenthetic)</seg> text.</p>
        <note>First note</note>
      </div3>
      <div3 type="tr" subtype="dollar" xtr:sref="Q001801.16" xtr:eref="Q001801.16" xtr:rows="1">
        <p>No translation warranted.</p>
      </div3>
    </div>
  </body></text>
</TEI>'''


def test_parse_tei_preserves_range_rows_subtype_markup_and_notes(tmp_path: Path):
    path = tmp_path / "Q001801.xml"
    path.write_text(_tei(), encoding="utf-8")

    record = translations.parse_tei_file(path, subproject="riao/ria1")

    assert record.key == "riao/ria1:Q001801"
    assert record.text_id == "Q001801"
    assert len(record.units) == 2

    first, second = record.units
    assert (first.sref, first.eref, first.rows, first.subtype) == (
        "Q001801.1",
        "Q001801.15",
        72,
        "tr",
    )
    assert first.text == "Plain italic and (parenthetic) text."
    assert '<hi type="i">italic</hi>' in first.text_raw
    assert '<seg type="r">(parenthetic)</seg>' in first.text_raw
    assert first.notes == ("First note",)

    assert (second.sref, second.eref, second.rows, second.subtype) == (
        "Q001801.16",
        "Q001801.16",
        1,
        "dollar",
    )
    assert second.text == "No translation warranted."


def test_translation_index_is_qualified_by_subproject_and_q(tmp_path: Path):
    path = tmp_path / "Q001801.xml"
    path.write_text(_tei(), encoding="utf-8")
    record = translations.parse_tei_file(path, subproject="riao/ria1")

    index = translations.TranslationIndex.from_records([record])

    assert index.get("riao/ria1:Q001801") is record
    assert index.get("rinap/rinap1:Q001801") is None


def test_translation_provenance_is_explicit_and_conservative(tmp_path: Path):
    path = tmp_path / "Q001801.xml"
    path.write_text(_tei(), encoding="utf-8")

    record = translations.parse_tei_file(
        path,
        subproject="riao/ria1",
        source_archive="riao-teiCorpus-20241202.zip",
    )

    assert record.source_archive == "riao-teiCorpus-20241202.zip"
    assert record.license == "CC BY-SA 3.0"
    assert "oracc" in record.license_url.lower()
