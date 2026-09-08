from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_checker():
    spec = spec_from_file_location(
        "check_docs_registry_issue47", Path("scripts/check_docs_registry.py")
    )
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_research_and_plan_require_snapshot_evidence_policy():
    checker = _load_checker()
    for doc_type in ("research", "plan"):
        problems = checker.fact_policy_problems(
            Path(f"docs/{doc_type}/X.md"),
            {"type": doc_type},
            "Measured 1,234 records on 2026-09-07.\n",
        )
        assert any("fact_policy" in problem for problem in problems)


def test_snapshot_policy_requires_dated_reproducible_evidence():
    checker = _load_checker()
    base = {"type": "research", "fact_policy": "snapshot-evidence"}
    problems = checker.fact_policy_problems(Path("docs/research/R-X.md"), base, "")
    assert any("evidence_date" in problem for problem in problems)
    assert any("evidence_basis" in problem for problem in problems)

    bad_date = {
        **base,
        "evidence_date": "2026-02-30",
        "evidence_basis": "python scripts/measure.py --json report.json",
    }
    problems = checker.fact_policy_problems(Path("docs/research/R-X.md"), bad_date, "")
    assert any("evidence_date" in problem for problem in problems)


def test_valid_snapshot_and_operational_documents_pass_without_digit_scanning():
    checker = _load_checker()
    snapshot = {
        "type": "research",
        "fact_policy": "snapshot-evidence",
        "evidence_date": "2026-09-07",
        "evidence_basis": "python scripts/measure.py --json report.json",
    }
    assert checker.fact_policy_problems(
        Path("docs/research/R-X.md"), snapshot, "Measured 1,234 records.\n"
    ) == []

    operational = {"type": "guide", "fact_policy": "operational"}
    body = "Use Python 3.12; inspect Q003840; schema version 1.2.0.\n"
    assert checker.fact_policy_problems(
        Path("docs/guides/G-X.md"), operational, body
    ) == []


def test_guide_and_index_reject_snapshot_policy():
    checker = _load_checker()
    for doc_type in ("guide", "index"):
        problems = checker.fact_policy_problems(
            Path(f"docs/{doc_type}/X.md"),
            {
                "type": doc_type,
                "fact_policy": "snapshot-evidence",
                "evidence_date": "2026-09-07",
                "evidence_basis": "report.json",
            },
            "",
        )
        assert any("operational" in problem for problem in problems)


def test_policy_table_must_match_registry_document_ids_exactly():
    checker = _load_checker()
    registry_docs = {
        "R-X": {"id": "R-X", "type": "research", "path": "docs/research/R-X.md"},
        "G-X": {"id": "G-X", "type": "guide", "path": "docs/guides/G-X.md"},
    }
    complete = {
        "R-X": {
            "fact_policy": "snapshot-evidence",
            "evidence_date": "2026-09-07",
            "evidence_basis": "measured report",
        },
        "G-X": {"fact_policy": "operational"},
    }

    assert checker.fact_policy_table_problems(registry_docs, complete) == []

    missing = dict(complete)
    del missing["G-X"]
    problems = checker.fact_policy_table_problems(registry_docs, missing)
    assert any("missing" in problem and "G-X" in problem for problem in problems)

    extra = dict(complete)
    extra["ORPHAN"] = {"fact_policy": "operational"}
    problems = checker.fact_policy_table_problems(registry_docs, extra)
    assert any("orphan" in problem.lower() and "ORPHAN" in problem for problem in problems)
