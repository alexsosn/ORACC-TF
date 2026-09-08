from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "plans" / "P-006-tf-application-browser.md"
REGISTRY = ROOT / "docs" / "registry.json"
FACT_POLICY = ROOT / "docs" / "fact-policy.json"


def _plan_text() -> str:
    assert PLAN.is_file(), "#70 must materialize the next free P-series plan as P-006"
    return PLAN.read_text(encoding="utf-8")


def test_issue70_materializes_registered_reviewable_p006_plan() -> None:
    text = _plan_text()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    policies = json.loads(FACT_POLICY.read_text(encoding="utf-8"))["documents"]

    docs = {item["id"]: item for item in registry["documents"]}
    assert docs["P-006"]["path"] == "docs/plans/P-006-tf-application-browser.md"
    assert docs["P-006"]["depends_on"] == ["R-006", "P-005"]
    assert policies["P-006"]["fact_policy"] == "snapshot-evidence"
    assert policies["P-006"]["evidence_date"] == "2026-09-09"
    assert policies["P-006"]["evidence_basis"].strip()

    for marker in (
        "id: P-006",
        "type: plan",
        "depends_on: [R-006, P-005]",
        "#71",
        "#72",
        "#73",
        "#74",
        "#75",
        "#78",
        "#79",
    ):
        assert marker in text


def test_issue70_plan_freezes_generated_app_and_dependency_boundaries() -> None:
    text = _plan_text()

    required_contracts = (
        "generated-by-default",
        "one generated lightweight repository per registered semantic dataset",
        "repository root is the semantic distribution root",
        "./app",
        "./tf/<version>",
        "./docs",
        "word#{form}",
        "synthetic=1",
        "No custom ORACC-TF web server",
        "Text-Fabric 13.1",
        "data-only browser CLI",
        "qualified `subproject:Q`",
        "manifest-owned",
        "narrow validated override",
        "independent review",
        "RED",
        "GREEN",
    )
    for contract in required_contracts:
        assert contract in text

    # Phase A is the production foundation; B/C may proceed only after A.
    assert "#71 -> (#72 || #73)" in text
    # Distribution support paths are an interface gate, not an excuse to weaken P-005.
    assert "#79 -> #71" in text
    # Browser E2E closes only after the standalone docs/distribution surface is real.
    assert "#78 -> #75" in text
    assert "#79 -> #75" in text

    forbidden = (
        "copy word form onto sign",
        "hand-maintained full per-dataset app tree",
        "disable TLS verification",
    )
    for phrase in forbidden:
        assert phrase not in text
