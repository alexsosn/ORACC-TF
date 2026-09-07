"""Third independent-review RED regressions for P-004.PH0.

These cases pin lease actor identity, live GitHub review ordering, task-local
failure isolation, and unambiguous PR ownership discovered while reviewing
exact head 1688f727. Production changes must follow this RED.
"""

from datetime import datetime, timezone
import json

from oracc_tf.coordination import analyze, validate_completion

NOW = datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40


def marker(kind, **payload):
    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def task(task_id, issue_number):
    return {
        "id": task_id,
        "title": task_id,
        "priority": "P0",
        "blocked_by": [],
        "status": "todo",
        "issue": issue_number,
    }


def registry(*tasks):
    return {"schema_version": 2, "tasks": list(tasks)}


def issue(number, *, comments=()):
    return {"number": number, "state": "open", "comments": list(comments)}


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


def implementation_pr(number, body, *, reviews=()):
    return {
        "number": number,
        "state": "open",
        "head_sha": HEAD,
        "body": body,
        "reviews": list(reviews),
    }


def review(review_id, task_id, verdict, submitted_at):
    return {
        "id": review_id,
        "submitted_at": submitted_at,
        "body": marker(
            "review",
            task=task_id,
            review_session="reviewer",
            implementation_session="impl",
            head_sha=HEAD,
            verdict=verdict,
        ),
    }


def snapshot(*issues, prs=()):
    return {
        "main_sha": BASE,
        "issues": list(issues),
        "pull_requests": list(prs),
    }


def test_release_without_owner_session_fails_closed_and_keeps_claim_owned():
    reg = registry(task("A", 101))
    release_without_actor = {
        "id": 11,
        "body": marker("release", task="A", claim_id=10),
    }
    snap = snapshot(
        issue(
            101,
            comments=[claim(10, "A", session="owner"), release_without_actor],
        )
    )

    state = analyze(reg, snap, NOW)["A"]

    assert state.phase == "conflict"
    assert state.owner_session == "owner"
    assert any("release" in problem and "session" in problem for problem in state.problems)


def test_latest_review_uses_submitted_at_for_graphql_string_ids_not_list_order():
    reg = registry(task("A", 101))
    body = marker("implementation", task="A", issue=101, session="impl")
    # The normalized connector returns GraphQL string ids. Deliberately provide
    # reverse list order: the blocker is chronologically newer than the pass.
    reviews = [
        review("PRR_later", "A", "request_changes", "2026-09-05T14:00:00Z"),
        review("PRR_earlier", "A", "pass", "2026-09-05T13:00:00Z"),
    ]
    snap = snapshot(
        issue(101, comments=[claim(10, "A")]),
        prs=[implementation_pr(201, body, reviews=reviews)],
    )

    problems = validate_completion("A", reg, snap, NOW)

    assert any("latest exact-head review" in problem for problem in problems)


def test_json_task_example_in_unrelated_pr_prose_does_not_scope_malformed_marker_to_task():
    reg = registry(task("A", 101), task("B", 102))
    body = "\n".join(
        [
            marker("implementation", task="B", issue=102, session="impl"),
            'Documentation example only: {"task": "A"}',
            '<!-- oracc-tf:review {"task":"B",oops} -->',
        ]
    )
    snap = snapshot(
        issue(101),
        issue(102, comments=[claim(20, "B")]),
        prs=[implementation_pr(202, body)],
    )

    states = analyze(reg, snap, NOW)

    assert states["A"].phase == "ready"
    assert states["A"].problems == []
    assert states["B"].phase == "conflict"


def test_conflicting_duplicate_implementation_markers_fail_closed():
    reg = registry(task("A", 101))
    body = "\n".join(
        [
            marker("implementation", task="A", issue=101, session="impl"),
            marker("implementation", task="A", issue=999, session="other"),
        ]
    )
    snap = snapshot(
        issue(101, comments=[claim(10, "A")]),
        prs=[implementation_pr(201, body)],
    )

    state = analyze(reg, snap, NOW)["A"]

    assert state.phase == "conflict"
    assert any("implementation" in problem and "conflict" in problem for problem in state.problems)
