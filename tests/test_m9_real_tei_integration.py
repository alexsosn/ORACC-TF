"""Real-source P-001 M9 acceptance against the published RIAO TEI export.

The ordinary test suite stays network-independent.  The dedicated M9 workflow
fetches the exact archive and supplies ``ORACC_TRANSLATION_TEI_ZIP``.  This gate
first validates source shape/coverage before the archive is allowed to drive a
whole-corpus graph build.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from oracc_tf import loader, paths, translations


EXCLUDED_SOURCE_GAPS = {"rinap/rinap5p1"}
EXPECTED_TRANSLATED_DOCUMENTS = 1646


def _archive() -> translations.TranslationArchive:
    location = os.environ.get("ORACC_TRANSLATION_TEI_ZIP")
    if not location:
        pytest.skip("real RIAO TEI archive is supplied by the dedicated M9 CI gate")

    archive_path = Path(location)
    assert archive_path.is_file()
    editions = tuple(loader.iter_editions(paths.DATA, skip_unreadable=True))
    document_keys = translations.qualified_key_map(
        editions,
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
