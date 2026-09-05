"""Second independent-review RED regressions for P-004.PH0.

These cases pin task-local failure isolation and completion semantics discovered
while reviewing exact head fa8ff8f5. Production changes must follow this RED.
"""

from datetime import datetime, timezone
import json

from oracc_tf.coordination import analyze, validate_completion

NOW = datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40


def marker(kind, **payload):
    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def task(task_id, issue_number, *, status="todo"):
    return {
        "id": task_id,
        "title": task_id,
        "priority": "P0",
        "blocked_by": [],
        "status": status,
        "issue": issue_number,
    }


def registry(*tasks):
    return {"schema_version": 2, "tasks": list(tasks)}


def issue(number, *, comments=(), state="open"):
    return {"number": number, "state": state, "comments": list(comments)}


def claim(cid, task_id, session="impl"):
    return {
        "id": cid,
        "body": marker(
            "claim",
            task=task_id,
            session=session,
            base_sha=BASE,
            expires_at="2026-09-05T14:00:00Z",
        ),
    }


def review(rid, task_id, verdict, *, reviewer="reviewer", implementer="impl"):
    return {
        "id": rid,
        "body": marker(
            "review",
            task=task_id,
            review_session=reviewer,
            implementation_session=implementer,
            head_sha=HEAD,
            verdict=verdict,
        ),
    }


def implementation_pr(number, task_id, issue_number, *, reviews=(), extra=""):
    body = marker(
        "implementation",
        task=task_id,
        issue=issue_number,
        session="impl",
    )
    if extra:
        body += "\n" + extra
    return {
        "number": number,
        "state": "open",
        "head_sha": HEAD,
        "body": body,
        "reviews": list(reviews),
    }


def snapshot(*issues, prs=()):
    return {
        "main_sha": BASE,
        "issues": list(issues),
        "pull_requests": list(prs),
    }


def test_marker_names_in_ordinary_prose_are_not_machine_events():
    reg = registry(task("A", 101))
    prose = {
        "id": 10,
        "body": "Document `oracc-tf:recover` and `oracc-tf:release` for operators; these are not markers.",
    }

    state = analyze(reg, snapshot(issue(101, comments=[prose])), NOW)["A"]

    assert state.phase == "ready"
    assert state.problems == []


def test_malformed_marker_in_unrelated_pr_does_not_stall_ready_task():
    reg = registry(task("A", 101), task("B", 102))
    malformed_b_review = '<!-- oracc-tf:review {"task":"B",oops} -->'
    snap = snapshot(
        issue(101),
        issue(102, comments=[claim(20, "B")]),
        prs=[implementation_pr(202, "B", 102, extra=malformed_b_review)],
    )

    states = analyze(reg, snap, NOW)

    assert states["A"].phase == "ready"
    assert states["A"].problems == []
    assert states["B"].phase == "conflict"
    assert any("malformed review marker" in problem for problem in states["B"].problems)


def test_blocked_task_cannot_pass_completion_gate_even_with_valid_pr_and_review():
    reg = registry(task("A", 101, status="blocked"))
    snap = snapshot(
        issue(101, comments=[claim(10, "A")]),
        prs=[
            implementation_pr(
                201,
                "A",
                101,
                reviews=[review(1, "A", "pass")],
            )
        ],
    )

    problems = validate_completion("A", reg, snap, NOW)

    assert any("blocked" in problem for problem in problems)


def test_latest_exact_head_independent_review_controls_completion():
    reg = registry(task("A", 101))
    issue_a = issue(101, comments=[claim(10, "A")])

    later_blocker = snapshot(
        issue_a,
        prs=[
            implementation_pr(
                201,
                "A",
                101,
                reviews=[
                    review(1, "A", "pass"),
                    review(2, "A", "request_changes"),
                ],
            )
        ],
    )
    problems = validate_completion("A", reg, later_blocker, NOW)
    assert any("latest exact-head review" in problem for problem in problems)

    later_pass = snapshot(
        issue_a,
        prs=[
            implementation_pr(
                201,
                "A",
                101,
                reviews=[
                    review(1, "A", "request_changes"),
                    review(2, "A", "pass"),
                ],
            )
        ],
    )
    assert validate_completion("A", reg, later_pass, NOW) == []
