"""Issue #108 RED contracts for ADR-0001 zero-span documentation sync."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
P001 = ROOT / "docs" / "plans" / "P-001-riao-rinap-tf.md"
P002 = ROOT / "docs" / "plans" / "P-002-upstream-automation.md"
G002 = ROOT / "docs" / "guides" / "G-002-development.md"
PH5 = ROOT / "docs" / "research" / "issue-95-ph5-gate-contracts.json"


def test_p001_current_model_no_longer_requires_sidecar_domain() -> None:
    text = P001.read_text(encoding="utf-8")

    # Historical revision notes may still discuss the superseded sidecar model,
    # but current normative decisions/milestones must not encode it as v1 truth.
    assert "the distributable v1 corpus is two coordinated layers" not in text
    assert "TF warp itself contains 320,680 word nodes" not in text
    assert "Its features and relation edges must survive in deterministic `zero-span.json`" not in text
    assert "preserve it in deterministic `zero-span.json`" not in text

    assert "synthetic=1" in text
    assert "synthetic" in text.lower() and "anchor" in text.lower()
    assert "semantic/source sign" in text.lower()
    assert "total TF slot" in text.lower()


def test_g002_describes_tf_root_without_required_zero_span_sidecar() -> None:
    text = G002.read_text(encoding="utf-8")

    assert "coordinated\nsidecars such as `zero-span.json`" not in text
    assert "does not require `zero-span.json`" in text


def test_p002_postbuild_reconciles_complete_tf_word_domain() -> None:
    text = P002.read_text(encoding="utf-8")

    assert "TF warp plus zero-span sidecar domain" not in text
    assert "source words" in text.lower()
    assert "synthetic" in text.lower()
    assert "anchor" in text.lower()


def test_ph5_structured_contract_reconciles_complete_tf_word_domain() -> None:
    contract = json.loads(PH5.read_text(encoding="utf-8"))
    semantics = contract["gate_semantics"]["word-count-unexplained"]

    assert isinstance(semantics, str)
    assert "zero-span sidecar domain" not in semantics
    assert "source-word" in semantics or "source word" in semantics
    assert "synthetic" in semantics.lower()
    assert "anchor" in semantics.lower()
