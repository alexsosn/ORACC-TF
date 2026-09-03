"""P-001 M5 catalogue metadata join acceptance tests.

Bare Q-numbers are not document identities: rinap5 and rinap5p1 reuse 140 of
them, and some collisions are materially different editions.  Catalogue
metadata must therefore be indexed by ``subproject:Q`` while source-level
licence provenance remains attached even when a catalogue member is absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oracc_tf import loader, metadata, paths


RINAP5_Q003840 = paths.DATA / "rinap/rinap5/corpusjson/Q003840.json"
RINAP5P1_Q003840 = paths.DATA / "rinap/rinap5p1/corpusjson/Q003840.json"


def test_q003840_catalogue_join_is_subproject_qualified():
    index = metadata.load_index(
        paths.DATA,
        subprojects=("rinap/rinap5", "rinap/rinap5p1"),
    )
    rinap5 = metadata.join_edition(loader.load_edition(RINAP5_Q003840), index)
    rinap5p1 = metadata.join_edition(loader.load_edition(RINAP5P1_Q003840), index)

    assert rinap5.key == "rinap/rinap5:Q003840"
    assert rinap5p1.key == "rinap/rinap5p1:Q003840"
    assert rinap5.catalogue_present is True
    assert rinap5p1.catalogue_present is True

    # Same bare Q, genuinely different catalogue records.
    assert rinap5.catalogue["designation"] == "Ashurbanipal 2001"
    assert rinap5.catalogue["language"] == "Akkadian"
    assert rinap5.catalogue["object_type"] == "stele"
    assert rinap5.catalogue["provenience"] == "Qalat Sherqat (Assur)"

    assert rinap5p1.catalogue["designation"] == "Ashurbanipal 2003"
    assert rinap5p1.catalogue["language"] == "Sumerian"
    assert rinap5p1.catalogue["object_type"] == "door socket"
    assert rinap5p1.catalogue["provenience"] == "Tell Muqayyar (Ur)"
    assert rinap5.catalogue != rinap5p1.catalogue


def test_missing_catalogue_member_keeps_document_and_raw_licence_provenance():
    edition = loader.Edition(
        subproject="test/project",
        text_id="QTEST",
        path=Path("QTEST.json"),
        doc={
            "type": "cdl",
            "project": "test/project",
            "textid": "QTEST",
            "license": "Do not redistribute",
            "license-url": "https://example.test/license",
            "license-type": "restricted",
            "cdl": [],
        },
        word_count=0,
    )

    joined = metadata.join_edition(edition, metadata.MetadataIndex.empty())

    assert joined.key == "test/project:QTEST"
    assert joined.catalogue_present is False
    assert joined.catalogue == {}
    assert joined.license == "Do not redistribute"
    assert joined.license_url == "https://example.test/license"
    assert joined.license_type == "restricted"


def test_licence_type_accepts_underscore_source_spelling_without_rewriting_value():
    edition = loader.Edition(
        subproject="test/project",
        text_id="QTYPE",
        path=Path("QTYPE.json"),
        doc={
            "type": "cdl",
            "project": "test/project",
            "textid": "QTYPE",
            "license": "custom licence text",
            "license_type": "custom-source-token",
            "cdl": [],
        },
        word_count=0,
    )

    joined = metadata.join_edition(edition, metadata.MetadataIndex.empty())
    assert joined.license_type == "custom-source-token"


def test_catalogue_member_project_mismatch_fails_closed():
    source = {
        "type": "catalogue",
        "project": "rinap/rinap5",
        "members": {
            "QTEST": {
                "project": "rinap/rinap5p1",
                "designation": "wrong edition",
            }
        },
    }

    with pytest.raises(metadata.CatalogueProjectMismatch):
        metadata.index_catalogue("rinap/rinap5", source)


@pytest.mark.corpus
def test_whole_corpus_catalogue_join_meets_m5_exit_criteria():
    result = metadata.census(paths.DATA)

    assert result.populated_documents == 1845
    assert result.catalogue_entries == 2098
    assert result.multiply_attached_records == 0, result.report()
    assert result.populated_with_ruler / result.populated_documents >= 0.96, result.report()

    # Diagnostic hardening: force the measured report into CI once, then pin
    # the exact values in the next commit rather than retaining only a ratio.
    assert result.catalogue_attached_documents == 0, result.report()
