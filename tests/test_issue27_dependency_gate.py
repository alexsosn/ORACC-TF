"""Issue #27 blocker synchronization after the empty-slot architecture change."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _task(task_id: str) -> dict[str, object]:
    registry = json.loads((ROOT / "docs/registry.json").read_text(encoding="utf-8"))
    return next(task for task in registry["tasks"] if task["id"] == task_id)


def test_p003_ph1_waits_for_translation_layer() -> None:
    task = _task("P-003.PH1")
    assert "P-001.M9" in task["blocked_by"]


def test_p003_phase1_model_contract_tracks_empty_slot_architecture() -> None:
    plan = (ROOT / "docs/plans/P-003-documentation.md").read_text(encoding="utf-8")
    phase1 = plan.split("# Phase 1 —", 1)[1].split("# Phase 2 —", 1)[0].lower()
    assert "synthetic empty" in phase1
    assert "semantic sign" in phase1
