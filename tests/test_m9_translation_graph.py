"""P-001 M9 — translation units must align to source line ranges exactly."""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, translations


def _edition() -> loader.Edition:
    text_id = "QTEST"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {"node": "d", "type": "line-start", "ref": f"{text_id}.1", "label": "1"},
                {"node": "l", "id": f"{text_id}.l1", "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]}},
                {"node": "d", "type": "line-start", "ref": f"{text_id}.2", "label": "2"},
                {"node": "l", "id": f"{text_id}.l2", "f": {"form": "na", "gdl": [{"v": "na", "utf8": "𒈾"}]}},
            ],
        }],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path("/test/unit/corpusjson/QTEST.json"),
        doc=doc,
        word_count=2,
    )


def _metadata() -> metadata.MetadataIndex:
    return metadata.MetadataIndex(records={
        "test/unit:QTEST": {
            "license": "CC0",
            "license-url": "https://creativecommons.org/publicdomain/zero/1.0/",
        }
    })


def _unit(*, sref: str = "QTEST.1", eref: str = "QTEST.2") -> translations.TranslationUnit:
    return translations.TranslationUnit(
        document_key="test/unit:QTEST",
        text_id="QTEST",
        source_id="QTEST_project-en.0",
        subtype="tr",
        sref=sref,
        eref=eref,
        rows=2,
        label="(1)",
        se_label="source label",
        text="translated text",
        text_raw="translated <hi type=\"i\">text</hi>",
        source_name="tei.zip",
    )


def test_translation_unit_oslots_are_union_of_inclusive_source_line_range(tmp_path):
    corpus.build_tf(
        tmp_path,
        editions=(_edition(),),
        metadata_index=_metadata(),
        translations_by_document={"test/unit:QTEST": (_unit(),)},
    )
    api = corpus.load_tf(tmp_path)

    unit = api.F.otype.s("translation_unit")[0]
    lines = api.F.otype.s("line")
    expected = tuple(sorted({slot for line in lines for slot in api.E.oslots.s(line)}))

    assert tuple(api.E.oslots.s(unit)) == expected
    assert api.F.translation_subtype.v(unit) == "tr"
    assert api.F.translation_sref.v(unit) == "QTEST.1"
    assert api.F.translation_eref.v(unit) == "QTEST.2"
    assert api.F.translation_text.v(unit) == "translated text"
    assert api.F.translation_text_raw.v(unit) == 'translated <hi type="i">text</hi>'
    assert api.F.translation_source.v(unit) == "tei.zip"

    document = api.F.otype.s("document")[0]
    assert api.F.license.v(document) == "CC0"


def test_translation_alignment_rejects_missing_endpoint_instead_of_shrinking_range(tmp_path):
    with pytest.raises(corpus.CorpusBuildError, match="translation.*eref"):
        corpus.build_tf(
            tmp_path,
            editions=(_edition(),),
            metadata_index=_metadata(),
            translations_by_document={
                "test/unit:QTEST": (_unit(eref="QTEST.999"),)
            },
        )
