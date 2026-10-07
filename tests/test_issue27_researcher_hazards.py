"""Issue #27 RED contracts for researcher-facing hazard documentation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "docs" / "reference"


def _text(name: str) -> str:
    return (REF / name).read_text(encoding="utf-8")


def _audit() -> dict[str, object]:
    return json.loads(
        (ROOT / "docs" / "task-state" / "ISSUE-124.json").read_text(encoding="utf-8")
    )["audit"]


def test_hazard_pages_are_active_and_discoverable() -> None:
    index = _text("index.md")
    for page in (
        "signs.md",
        "words-and-lexemes.md",
        "identity.md",
        "model.md",
        "translations.md",
    ):
        assert f"]({page})" in index
        assert "status: active" in _text(page).split("---", 2)[1]


def test_sign_page_separates_source_signs_from_synthetic_slots() -> None:
    text = _text("signs.md")
    audit = _audit()
    assert f"{audit['source']['semantic_signs']:,}" in text
    assert f"{audit['tf']['synthetic_slots']:,}" in text
    assert "synthetic=1" in text
    assert "1(diš)" in text
    assert "𒁹" in text
    assert "Q005620" in text
    assert "classification" in text.lower()


def test_words_and_lexemes_page_documents_absence_and_multilexeme_hazards() -> None:
    text = _text("words-and-lexemes.md")
    for feature in ("`cf`", "`gw`", "`sense`", "`norm`", "`pos`", "`epos`", "`sig`"):
        assert feature in text
    for value in ("31,770", "878", "230", "295"):
        assert value in text
    assert "Q003333.l04f6b" in text
    assert "Q009276.l00a19" in text
    assert "three" in text.lower() and "lexeme" in text.lower()
    assert "14" in text and "two" in text.lower()
    assert "word_lex" in text
    assert "naive" in text.lower()


def test_identity_page_demonstrates_bare_q_collision_failure() -> None:
    text = _text("identity.md")
    assert "140" in text
    assert "48" in text
    assert "rinap/rinap5:Q003840" in text
    assert "rinap/rinap5p1:Q003840" in text
    assert "`document_key`" in text
    assert "bare" in text.lower() and "Q003840" in text


def test_translation_page_starts_with_real_range_edge_lookup() -> None:
    text = _text("translations.md")
    first_python = text.split("```python", 1)[1].split("```", 1)[0]
    assert "translation_line" in first_python
    assert "translation_sref" in first_python
    assert "translation_eref" in first_python
    assert "line.translation" not in first_python
    assert "no `line.translation` feature" in text


def test_model_page_has_researcher_graph_overview_and_svg() -> None:
    text = _text("model.md")
    assert "model.svg" in text
    assert (REF / "model.svg").is_file()
    for term in ("document", "face", "line", "word", "lex", "translation_unit", "sign"):
        assert f"`{term}`" in text
    assert "word_lex" in text
    assert "translation_line" in text
    assert "synthetic=1" in text
