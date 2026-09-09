"""P-001 M9 — translation TEI parsing and alignment contract.

These are intentionally small, network-independent fixtures.  The real TEI
export is validated by a separate integration gate; unit tests pin the source
semantics we are willing to materialise into Text-Fabric.
"""

from __future__ import annotations

import pytest

from oracc_tf import translations


XTR = "http://oracc.org/ns/xtr/1.0"


TEI = f"""\
<TEI xmlns:xtr="{XTR}" xml:id="Q001801_project-en">
  <text>
    <body>
      <div3 type="tr" subtype="tr" xml:id="Q001801_project-en.0"
            n="(1)" xtr:sref="Q001801.1" xtr:eref="Q001801.15"
            xtr:lab-start-lnum="1" xtr:lab-end-lnum="16"
            xtr:rows="15" xtr:label="(1)" xtr:se_label="Zarriqum 2001, 1">
        The <hi type="i">king</hi> ( <hi type="r">lord</hi> ) spoke.
      </div3>
      <div3 type="tr" subtype="dollar" xml:id="Q001801_project-en.1"
            xtr:sref="Q001801.16" xtr:eref="Q001801.16" xtr:rows="1">
        $ single-line editorial note
      </div3>
    </body>
  </text>
</TEI>
"""


def test_parse_translation_units_preserves_range_subtype_and_markup():
    units = translations.parse_tei_text(
        TEI,
        document_key="riao/ria1:Q001801",
        source_name="riao-teiCorpus-20241202.zip",
    )

    assert len(units) == 2
    first, dollar = units

    assert first.document_key == "riao/ria1:Q001801"
    assert first.text_id == "Q001801"
    assert first.source_id == "Q001801_project-en.0"
    assert first.subtype == "tr"
    assert first.sref == "Q001801.1"
    assert first.eref == "Q001801.15"
    assert first.rows == 15
    assert first.label == "(1)"
    assert first.se_label == "Zarriqum 2001, 1"
    assert "king" in first.text
    assert "lord" in first.text
    assert '<hi type="i">king</hi>' in first.text_raw
    assert '<hi type="r">lord</hi>' in first.text_raw
    assert first.source_name == "riao-teiCorpus-20241202.zip"

    assert dollar.subtype == "dollar"
    assert dollar.sref == dollar.eref == "Q001801.16"
    assert dollar.rows == 1


def test_translation_parser_rejects_missing_or_cross_document_ranges():
    missing = TEI.replace(' xtr:eref="Q001801.15"', "", 1)
    with pytest.raises(translations.TranslationSourceError, match="eref"):
        translations.parse_tei_text(missing, document_key="riao/ria1:Q001801")

    crossed = TEI.replace('xtr:eref="Q001801.15"', 'xtr:eref="Q999999.15"', 1)
    with pytest.raises(translations.TranslationSourceError, match="same text"):
        translations.parse_tei_text(crossed, document_key="riao/ria1:Q001801")


def test_translation_parser_requires_qualified_document_identity():
    with pytest.raises(translations.TranslationSourceError, match="qualified"):
        translations.parse_tei_text(TEI, document_key="Q001801")
