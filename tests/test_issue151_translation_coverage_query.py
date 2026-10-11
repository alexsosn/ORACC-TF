"""Behavioral RED tests for the shipped researcher translation coverage query.

Execute the exact documented Python rather than testing a duplicate recipe.
The known note is an exact source expression, not a general translation detector.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SECTION = "## Audit explicit untranslated units"


def documented_query() -> str:
    guide = (ROOT / "docs/reference/query-guide.md").read_text(encoding="utf-8")
    section = guide.split(SECTION, 1)[1].split("\n## ", 1)[0]
    fence = chr(96) * 3
    return section.split(f"{fence}python\n", 1)[1].split(f"\n{fence}", 1)[0]


def execute_coverage_query(api: object) -> dict[str, int]:
    context = {"api": api}
    with redirect_stdout(io.StringIO()):
        exec(compile(documented_query(), "docs/reference/query-guide.md", "exec"), context)
    result = context.get("coverage")
    assert isinstance(result, dict)
    return result


def test_translation_coverage_query_counts_explicit_source_notice_only() -> None:
    """Do not conflate aligned unit count, editorial notices and true translation."""
    texts = {
        12: "(Not yet translated.)",
        13: "(Not\n yet   translated.)",
        14: "This was (Not yet translated.) in another edition.",
        15: "King of Assyria",
        16: "",
        17: None,
        18: "Not yet translated.",
    }
    otype = SimpleNamespace(s=lambda kind: tuple(texts) if kind == "translation_unit" else ())
    features = SimpleNamespace(otype=otype, translation_text=SimpleNamespace(v=texts.get))
    api = SimpleNamespace(F=features)
    result = execute_coverage_query(api)
    assert result == {
        "aligned_units": 7,
        "explicit_not_yet_translated": 2,
        "empty_text_units": 2,
        "other_unclassified_units": 3,
    }


def test_translation_coverage_query_empty_corpus() -> None:
    otype = SimpleNamespace(s=lambda kind: ())
    features = SimpleNamespace(otype=otype, translation_text=SimpleNamespace(v=lambda n: None))
    result = execute_coverage_query(SimpleNamespace(F=features))
    assert result == {
        "aligned_units": 0,
        "explicit_not_yet_translated": 0,
        "empty_text_units": 0,
        "other_unclassified_units": 0,
    }


def test_translation_coverage_query_docs_disclaim_nonexhaustive_classification() -> None:
    guide = (ROOT / "docs/reference/query-guide.md").read_text(encoding="utf-8")
    section = guide.split(SECTION, 1)[1].split("\n## ", 1)[0]
    assert "other_unclassified_units" in section
    assert "not verified translations" in section
    assert "not a percentage of translated lines" in section
    assert "riao/ria2:Q009244" in section
