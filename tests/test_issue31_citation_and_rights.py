"""Issue #31 RED contracts: separate software citation from source rights and limitations."""

from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "reference"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_software_citation_is_valid_and_does_not_relicense_data() -> None:
    cff = yaml.safe_load(_read("CITATION.cff"))
    assert cff["cff-version"] == "1.2.0"
    assert cff["type"] == "software"
    assert cff["license"] == "MIT"
    assert cff["title"] and cff["authors"]
    assert "ORACC-TF" in cff["title"]
    assert "github.com/alexsosn/ORACC-TF" in cff["repository-code"]
    assert "1.0" not in str(cff.get("version", ""))  # software CFF must not assert a dataset 1.0 release version
    assert "ORACC" in cff["abstract"]
    assert "not" in cff["abstract"].lower() and "data" in cff["abstract"].lower()


def test_researcher_citation_documents_versioned_dataset_and_rights_boundaries() -> None:
    text = _read("docs/reference/citation.md")
    assert "status: active" in text
    for marker in (
        "RIAO", "RINAP", "ORACC", "document_key", "manifest.json",
        "release_id", "source_state", "builder_commit", "tf_version",
        "MIT", "CC0", "CC BY-SA 3.0", "editor", "translation",
    ):
        assert marker in text
    assert "CITATION.cff" in text
    assert "not automatically" in text.lower()
    assert "actual versioned GitHub Release URL" in text
    assert "matching checksum" in text
    assert "No DOI" in text


def test_known_issues_are_real_source_and_tei_hazards_not_software_hype() -> None:
    text = _read("docs/reference/known-issues.md")
    assert "status: active" in text
    for marker in (
        "ISSUE-124", "unreadable", "stub", "catalogue",
        "synthetic=1", "word", "lexeme", "translation-gaps.json",
        "rinap5p1", "CC BY-SA",
    ):
        assert marker.lower() in text.lower()
    assert "data-audit.md" in text
    assert "translations.md" in text


def test_actual_source_has_conflicting_machine_and_editorial_license_statements() -> None:
    corpus_path = ROOT / "data/riao/ria1/corpusjson/Q001801.json"
    catalogue_path = ROOT / "data/riao/ria1/catalogue.json"
    if not corpus_path.is_file() or not catalogue_path.is_file():
        import pytest
        pytest.skip("checked-in ORACC source snapshot unavailable")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    assert "CC0" in corpus["license"]
    assert "Attribution Share-Alike" in catalogue["members"]["Q001801"]["credits"]
    text = _read("docs/reference/citation.md")
    assert "Q001801" in text
    assert "conflict" in text.lower() or "tension" in text.lower()


def test_reference_landing_exposes_citation_and_limitations() -> None:
    index = _read("docs/reference/index.md")
    assert "](citation.md)" in index
    assert "](known-issues.md)" in index
