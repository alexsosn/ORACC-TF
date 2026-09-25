"""P-001 M9 — TEI translation layer contract.

These tests deliberately precede production implementation.  The source model is
line-range alignment: translation units retain xtr:sref/xtr:eref exactly and are
not token-aligned or reconstructed from prose.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import zipfile

from oracc_tf import TF_VERSION, translations


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
    assert "CC BY-SA 3.0" in record.license
    assert "project-specific terms may differ" in record.license
    assert "oracc" in record.license_url.lower()


def test_translation_nodes_and_features_advance_the_tf_schema():
    assert TF_VERSION == "0.4.0"


def test_official_archive_parser_pins_identity_and_preserves_explicit_gaps(tmp_path: Path, monkeypatch):
    archive_path = tmp_path / "tei.zip"
    xml = f'''<?xml version="1.0"?>
<teiCorpus xmlns="{TEI}" xmlns:xtr="{XTR}">
  <TEI><teiHeader><fileDesc><sourceDesc>
    <name type="file">riao/ria1/Q001801.xtf</name>
  </sourceDesc></fileDesc></teiHeader><text><body>
    <div3 type="tr" subtype="tr" xtr:sref="Q001801.1" xtr:eref="Q001801.2">A range.</div3>
    <div3 type="tr" subtype="dollar" xtr:ref="Q001801.3">A cited line.</div3>
    <div3 type="tr" subtype="dollar">An unaligned source unit.</div3>
  </body></text></TEI>
</teiCorpus>'''
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("source.xml", xml)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    monkeypatch.setattr(translations, "OFFICIAL_ARCHIVE_SHA256", digest)

    index = translations.parse_tei_archive(archive_path, expected_sha256=digest)

    record = index.get("riao/ria1:Q001801")
    assert record is not None
    assert len(record.units) == 3
    assert (record.units[0].sref, record.units[0].eref) == (
        "Q001801.1",
        "Q001801.2",
    )
    assert (record.units[1].sref, record.units[1].eref) == (
        "Q001801.3",
        "Q001801.3",
    )
    assert record.units[2].sref is None
    assert record.units[2].eref is None
    assert record.units[0].document_key == record.key
    assert record.units[0].source_name == translations.OFFICIAL_ARCHIVE_NAME
    assert record.units[0].source_sha256 == digest


def test_official_archive_parser_fails_closed_on_digest_mismatch(tmp_path: Path):
    path = tmp_path / "tei.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("source.xml", "<teiCorpus/>")

    try:
        translations.parse_tei_archive(path, expected_sha256="0" * 64)
    except translations.TranslationParseError as exc:
        assert "SHA-256 mismatch" in str(exc)
    else:
        raise AssertionError("archive digest mismatch must be rejected")


def test_translation_content_preserves_mixed_text_order_around_markup_and_notes(tmp_path: Path):
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}" xmlns:xtr="{XTR}" xml:id="Q_MIXED">
  <text><body>
    <div3 type="tr" xtr:sref="Q_MIXED.1" xtr:eref="Q_MIXED.1">Before <p>paragraph <hi type="i">italic</hi> tail</p> after paragraph <note>editorial note</note> after note.</div3>
  </body></text>
</TEI>'''
    path = tmp_path / "Q_MIXED.xml"
    path.write_text(xml, encoding="utf-8")

    record = translations.parse_tei_file(path, subproject="riao/ria1")
    unit = record.units[0]

    assert unit.text == "Before paragraph italic tail after paragraph after note."
    assert unit.text_raw.index("Before") < unit.text_raw.index("<p>")
    assert unit.text_raw.index("</p>") < unit.text_raw.index("after paragraph")
    assert unit.text_raw.index("after paragraph") < unit.text_raw.index("after note.")
    assert "<hi type=\"i\">italic</hi>" in unit.text_raw
    assert "editorial note" not in unit.text_raw
    assert "editorial note" not in unit.text
