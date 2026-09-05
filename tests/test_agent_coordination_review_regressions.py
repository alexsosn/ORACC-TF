"""Review-discovered RED regressions for P-004.PH0.

These tests are committed before the review fixes. They pin the repository-facing
selector and ensure a winning claimant cannot bypass unrelated fail-closed
coordination conflicts.
"""

from datetime import datetime, timezone
from pathlib import Path
import json

from oracc_tf.coordination import analyze, claim_result, ready_tasks

NOW = datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40


def marker(kind, **payload):
    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def test_repository_loop_documentation_no_longer_prescribes_global_lowest_task():
    text = Path("docs/README.md").read_text(encoding="utf-8")

    assert "Take the lowest-numbered task" not in text
    assert "all dependency-ready" in text
    assert "reconcile" in text.lower()
    assert "claim" in text.lower()


def test_winning_claim_cannot_bypass_an_unrelated_fail_closed_conflict():
    registry = {
        "schema_version": 2,
        "tasks": [
            {
                "id": "A",
                "title": "A",
                "priority": "P0",
                "blocked_by": [],
                "status": "todo",
                "issue": 101,
            }
        ],
    }
    good_claim = {
        "id": 10,
        "body": marker(
            "claim",
            task="A",
            session="winner",
            base_sha=BASE,
            expires_at="2026-09-05T14:00:00Z",
        ),
    }
    malformed = {"id": 11, "body": '<!-- oracc-tf:claim {"task":"A",oops} -->'}
    snapshot = {
        "main_sha": BASE,
        "issues": [{"number": 101, "state": "open", "comments": [good_claim, malformed]}],
        "pull_requests": [],
    }

    state = analyze(registry, snapshot, NOW)["A"]

    assert state.phase == "conflict"
    assert state.owner_session == "winner"
    assert claim_result(state, "winner") == "conflict"


def test_migrated_live_work_is_not_readvertised_as_ready():
    registry = {
        "schema_version": 2,
        "tasks": [
            {"id": "P-001.M9", "title": "M9", "priority": "P1", "blocked_by": [], "status": "todo", "issue": 16},
            {"id": "P-002.PH1", "title": "PH1", "priority": "P0", "blocked_by": [], "status": "todo", "issue": 17},
            {"id": "P-003.PH0", "title": "PH0", "priority": "P1", "blocked_by": [], "status": "todo", "issue": 26},
        ],
    }

    def claim(cid, task, session):
        return {
            "id": cid,
            "body": marker(
                "claim",
                task=task,
                session=session,
                base_sha=BASE,
                expires_at="2026-09-05T14:00:00Z",
            ),
        }

    def pr(number, task, issue, session):
        return {
            "number": number,
            "state": "open",
            "head_sha": HEAD,
            "body": marker("implementation", task=task, issue=issue, session=session),
            "reviews": [],
        }

    snapshot = {
        "main_sha": BASE,
        "issues": [
            {"number": 16, "state": "open", "comments": [claim(1016, "P-001.M9", "migration-pr13")]},
            {"number": 17, "state": "open", "comments": [claim(1017, "P-002.PH1", "migration-pr10")]},
            {"number": 26, "state": "open", "comments": [claim(1026, "P-003.PH0", "migration-pr15")]},
        ],
        "pull_requests": [
            pr(13, "P-001.M9", 16, "migration-pr13"),
            pr(10, "P-002.PH1", 17, "migration-pr10"),
            pr(15, "P-003.PH0", 26, "migration-pr15"),
        ],
    }

    states = analyze(registry, snapshot, NOW)

    assert ready_tasks(registry, snapshot, NOW) == []
    assert states["P-001.M9"].active_pr == 13
    assert states["P-002.PH1"].active_pr == 10
    assert states["P-003.PH0"].active_pr == 15
