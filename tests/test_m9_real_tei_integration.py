"""Real-source P-001 M9 acceptance against the published RIAO TEI export.

The ordinary test suite stays network-independent.  The dedicated M9 workflow
fetches the exact archive and supplies ``ORACC_TRANSLATION_TEI_ZIP``.  This gate
validates source shape/coverage, source-word reconciliation, and the resulting
whole-corpus Text-Fabric graph before M9 may be finalized.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pytest

from oracc_tf import corpus, loader, metadata, paths, translations, words


EXCLUDED_SOURCE_GAPS = {"rinap/rinap5p1"}
EXPECTED_TRANSLATED_DOCUMENTS = 1646
EXPECTED_PARSEABLE_DOCUMENTS = 2078


@lru_cache(maxsize=1)
def _editions() -> tuple[loader.Edition, ...]:
    return tuple(loader.iter_editions(paths.DATA, skip_unreadable=True))


@lru_cache(maxsize=1)
def _archive() -> translations.TranslationArchive:
    location = os.environ.get("ORACC_TRANSLATION_TEI_ZIP")
    if not location:
        pytest.skip("real RIAO TEI archive is supplied by the dedicated M9 CI gate")

    archive_path = Path(location)
    assert archive_path.is_file()
    document_keys = translations.qualified_key_map(
        _editions(),
        excluded_subprojects=EXCLUDED_SOURCE_GAPS,
    )
    return translations.load_tei_zip(
        archive_path,
        document_keys=document_keys,
        source_url="https://oracc.museum.upenn.edu/riao/downloads/riao-teiCorpus-20241202.zip",
        source_license="CC BY-SA 3.0",
        source_license_url="https://creativecommons.org/licenses/by-sa/3.0/",
    )


def test_real_tei_archive_matches_pinned_m9_source_characterisation():
    archive = _archive()

    assert len(archive.units_by_document) == EXPECTED_TRANSLATED_DOCUMENTS
    assert not any(key.startswith("rinap/rinap5p1:") for key in archive.units_by_document)

    q001801 = archive.units_by_document["riao/ria1:Q001801"]
    assert q001801
    assert q001801[0].sref == "Q001801.1"
    assert q001801[0].eref == "Q001801.15"

    all_units = tuple(unit for units in archive.units_by_document.values() for unit in units)
    assert any(unit.rows == 1 for unit in all_units)
    assert any(unit.rows == 72 for unit in all_units)
    assert any(unit.subtype == "dollar" for unit in all_units)
    assert any('type="i"' in unit.text_raw for unit in all_units)
    assert any('type="r"' in unit.text_raw for unit in all_units)

    assert all(unit.source_sha256 == archive.source_sha256 for unit in all_units)
    assert all(unit.source_license == "CC BY-SA 3.0" for unit in all_units)


def test_real_tei_word_ids_reconcile_one_to_one_with_all_corpusjson_words():
    archive = _archive()
    editions = {edition.key: edition for edition in _editions()}

    assert set(archive.word_ids_by_document) == set(archive.units_by_document)
    for document_key, tei_word_ids in archive.word_ids_by_document.items():
        edition = editions[document_key]
        source_word_ids = tuple(word.source_id for word in words.iter_words(edition.doc))
        # ``iter_words`` includes zero-sign words, so this is a source-domain
        # reconciliation rather than a comparison limited to TF warp nodes.
        assert tei_word_ids == source_word_ids, document_key
        assert len(tei_word_ids) == len(set(tei_word_ids))


def test_real_translation_archive_builds_complete_nonempty_tf_layer(tmp_path):
    archive = _archive()
    editions = _editions()
    report = corpus.build_tf(
        tmp_path,
        editions=editions,
        metadata_index=metadata.load_index(paths.DATA),
        translations_by_document=archive.units_by_document,
    )

    assert report.documents == EXPECTED_PARSEABLE_DOCUMENTS
    assert report.translation_source_supplied
    assert report.translated_documents == EXPECTED_TRANSLATED_DOCUMENTS
    assert report.translation_missing_documents == (
        EXPECTED_PARSEABLE_DOCUMENTS - EXPECTED_TRANSLATED_DOCUMENTS
    )
    assert report.translation_units > 0

    api = corpus.load_tf(tmp_path)
    translation_nodes = api.F.otype.s("translation_unit")
    assert len(translation_nodes) == report.translation_units
    assert all(api.E.oslots.s(node) for node in translation_nodes)

    q001801_nodes = [
        node
        for node in translation_nodes
        if api.F.document_key.v(node) == "riao/ria1:Q001801"
        and api.F.translation_sref.v(node) == "Q001801.1"
        and api.F.translation_eref.v(node) == "Q001801.15"
    ]
    assert len(q001801_nodes) == 1
