"""P-001 M9 — translation provenance is separate and coverage is explicit."""

from __future__ import annotations

from pathlib import Path

from oracc_tf import corpus, loader, metadata, translations


SOURCE_SHA256 = "a" * 64


def _edition(text_id: str = "QTEST") -> loader.Edition:
    doc = {
        "type": "cdl",
        "textid": text_id,
        "license": "CC0",
        "license-url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {"node": "d", "type": "line-start", "ref": f"{text_id}.1", "label": "1"},
                {"node": "l", "id": f"{text_id}.l1", "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]}},
            ],
        }],
    }
    return loader.Edition(
        subproject="test/unit",
        text_id=text_id,
        path=Path(f"/test/unit/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=1,
    )


def _unit() -> translations.TranslationUnit:
    return translations.TranslationUnit(
        document_key="test/unit:QTEST",
        text_id="QTEST",
        source_id="QTEST_project-en.0",
        subtype="tr",
        sref="QTEST.1",
        eref="QTEST.1",
        rows=1,
        label="(1)",
        se_label=None,
        text="translation",
        text_raw="translation",
        source_name="riao-teiCorpus-20241202.zip",
        source_sha256=SOURCE_SHA256,
        source_url="https://oracc.example/riao-teiCorpus-20241202.zip",
        source_license="CC BY-SA 3.0",
        source_license_url="https://creativecommons.org/licenses/by-sa/3.0/",
    )


def test_translation_provenance_is_emitted_without_overwriting_corpusjson_licence(tmp_path):
    report = corpus.build_tf(
        tmp_path,
        editions=(_edition(),),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={"test/unit:QTEST": (_unit(),)},
    )
    api = corpus.load_tf(tmp_path)

    unit = api.F.otype.s("translation_unit")[0]
    assert api.F.translation_source.v(unit) == "riao-teiCorpus-20241202.zip"
    assert api.F.translation_source_sha256.v(unit) == SOURCE_SHA256
    assert api.F.translation_source_url.v(unit) == "https://oracc.example/riao-teiCorpus-20241202.zip"
    assert api.F.translation_license.v(unit) == "CC BY-SA 3.0"
    assert api.F.translation_license_url.v(unit) == "https://creativecommons.org/licenses/by-sa/3.0/"

    document = api.F.otype.s("document")[0]
    assert api.F.license.v(document) == "CC0"
    assert report.translation_source_supplied is True
    assert report.translation_units == 1
    assert report.translated_documents == 1
    assert report.translation_missing_documents == 0


def test_translation_gap_reporting_distinguishes_no_source_from_explicit_empty_source(tmp_path):
    no_source = corpus.build_tf(
        tmp_path / "none",
        editions=(_edition(),),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    assert no_source.translation_source_supplied is False
    assert no_source.translation_units == 0
    assert no_source.translated_documents == 0
    assert no_source.translation_missing_documents == 0

    explicit_empty = corpus.build_tf(
        tmp_path / "empty",
        editions=(_edition(),),
        metadata_index=metadata.MetadataIndex.empty(),
        translations_by_document={},
    )
    assert explicit_empty.translation_source_supplied is True
    assert explicit_empty.translation_units == 0
    assert explicit_empty.translated_documents == 0
    assert explicit_empty.translation_missing_documents == 1
