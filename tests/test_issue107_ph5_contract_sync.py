"""Issue #107 RED contracts for post-#103 PH5 artifact synchronization."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "research" / "issue-95-ph5-gate-contracts.json"
EXPECTED_APPROVAL_KEY = [
    "gate_id",
    "subject.scope",
    "subject.id",
    "condition_sha256",
    "evidence_fingerprint",
]


def _contract() -> dict[str, object]:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_structured_contract_records_completed_normative_sync() -> None:
    contract = _contract()
    assert contract["status"] == "reviewed-design-normative-synced"
    assert "pending" not in str(contract["status"]).lower()


def test_gatefinding_requires_evidence_fingerprint() -> None:
    contract = _contract()
    finding = contract["finding_contract"]
    assert isinstance(finding, dict)
    required = finding["required_fields"]
    assert isinstance(required, list)
    assert "evidence_refs" in required
    assert "evidence_fingerprint" in required


def test_active_approval_identity_remains_evidence_bound() -> None:
    contract = _contract()
    approval = contract["approval_contract"]
    assert isinstance(approval, dict)
    assert approval["approval_key"] == EXPECTED_APPROVAL_KEY


def test_normative_follow_up_records_pr103_completion() -> None:
    contract = _contract()
    follow_up = contract["normative_follow_up"]
    assert isinstance(follow_up, str)
    assert follow_up.startswith("Completed by PR #103:")
    assert "R-002 and P-002 now adopt" in follow_up
    assert "PH5 evaluator TDD remains separately dependency-gated" in follow_up
    assert "before PH5 evaluator TDD begins" not in follow_up
