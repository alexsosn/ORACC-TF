from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "docs" / "research" / "issue-115-ph4-ph6-count-reconciliation.json"
PLAN = ROOT / "docs" / "plans" / "P-002-upstream-automation.md"


def test_reviewed_count_contract_is_machine_readable() -> None:
    assert ARTIFACT.exists(), "reviewed #115 contract must be serialized"
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["issue"] == 115
    assert payload["status"] == "reviewed"

    census = payload["source_census"]
    assert census["document_domain"] == "buildable-qualified-editions-including-stubs"
    assert census["semantic_sign_counter"] == "oracc_tf.gdl.classify_tree"
    assert census["duplicate_qualified_documents"] == "error-before-aggregation"
    assert census["lifecycle"] == "validation-side-evidence"

    equations = payload["equations"]
    assert equations["documents"] == "build.documents == source_census.documents"
    assert equations["words"] == "build.words == source_census.words"
    assert equations["semantic_signs"] == "build.semantic_signs == source_census.semantic_signs"
    assert equations["tf_slots"] == "build.tf_slots == build.semantic_signs + build.synthetic_slots"

    technical = payload["technical_slots"]
    assert technical["source_fact"] is False
    assert technical["same_source_and_schema_requires_exact_reproduction"] is True

    translation = payload["translation"]
    assert translation["evidence_source"] == "authenticated-M9-TEI"
    assert translation["json_ph4_source"] is False
    assert translation["required_state_authority"] == "release-dataset-policy"
    assert translation["missing_required_evidence"] == "error"

    assert payload["ph5_ownership"]["word_count_unexplained"] == "PH5-postbuild-only"


def test_phase6_normative_wording_separates_source_and_converter_facts() -> None:
    text = PLAN.read_text(encoding="utf-8")

    assert "source documents / words / semantic signs" in text
    assert "authenticated M9/TEI translation evidence" in text
    assert "synthetic slots and total TF slots" in text
    assert "buildable qualified source-document domain, including stubs" in text
    assert "duplicate qualified document identities across contributors" in text

    old = "slot / word / document counts, with deltas explained by the Phase 4 diff"
    assert old not in text
