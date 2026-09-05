"""P-001 M9 — deterministic TEI archive ingestion without Q-number guesses."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import pytest

from oracc_tf import loader, translations


XTR = "http://oracc.org/ns/xtr/1.0"


def _tei(text_id: str) -> str:
    return f"""\
<TEI xmlns:xtr="{XTR}" xml:id="{text_id}_project-en">
  <text><body>
    <div3 type="tr" subtype="tr" xml:id="{text_id}_project-en.0"
          xtr:sref="{text_id}.1" xtr:eref="{text_id}.1" xtr:rows="1">
      Translation for {text_id}.
    </div3>
  </body></text>
</TEI>
"""


def _archive(path: Path) -> str:
    corpus = "<teiCorpus>" + _tei("Q001801") + _tei("Q003840") + "</teiCorpus>"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("riao-teiCorpus.xml", corpus)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _edition(subproject: str, text_id: str) -> loader.Edition:
    return loader.Edition(
        subproject=subproject,
        text_id=text_id,
        path=Path(f"/{subproject}/corpusjson/{text_id}.json"),
        doc={"type": "cdl", "textid": text_id, "cdl": []},
        word_count=0,
    )


def test_qualified_key_map_fails_ambiguous_q_and_allows_explicit_source_gap_exclusion():
    editions = (
        _edition("riao/ria1", "Q001801"),
        _edition("rinap/rinap5", "Q003840"),
        _edition("rinap/rinap5p1", "Q003840"),
    )

    with pytest.raises(translations.TranslationSourceError, match="ambiguous.*Q003840"):
        translations.qualified_key_map(editions)

    mapping = translations.qualified_key_map(
        editions,
        excluded_subprojects={"rinap/rinap5p1"},
    )
    assert mapping == {
        "Q001801": "riao/ria1:Q001801",
        "Q003840": "rinap/rinap5:Q003840",
    }


def test_load_tei_zip_computes_archive_identity_and_propagates_explicit_provenance(tmp_path):
    archive_path = tmp_path / "riao-teiCorpus-20241202.zip"
    expected_sha = _archive(archive_path)
    key_map = {
        "Q001801": "riao/ria1:Q001801",
        "Q003840": "rinap/rinap5:Q003840",
    }

    archive = translations.load_tei_zip(
        archive_path,
        document_keys=key_map,
        source_url="https://oracc.example/riao/downloads/riao-teiCorpus-20241202.zip",
        source_license="CC BY-SA 3.0",
        source_license_url="https://creativecommons.org/licenses/by-sa/3.0/",
    )

    assert archive.source_name == archive_path.name
    assert archive.source_sha256 == expected_sha
    assert set(archive.units_by_document) == set(key_map.values())
    assert archive.translation_units == 2
    first = archive.units_by_document["riao/ria1:Q001801"][0]
    assert first.source_sha256 == expected_sha
    assert first.source_license == "CC BY-SA 3.0"


def test_load_tei_zip_rejects_translation_for_unmapped_text(tmp_path):
    archive_path = tmp_path / "tei.zip"
    _archive(archive_path)
    with pytest.raises(translations.TranslationSourceError, match="unmapped.*Q003840"):
        translations.load_tei_zip(
            archive_path,
            document_keys={"Q001801": "riao/ria1:Q001801"},
        )
