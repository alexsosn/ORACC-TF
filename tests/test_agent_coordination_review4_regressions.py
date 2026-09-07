"""Fourth independent-review RED regressions for P-004.PH0.

These cases pin ambiguous same-timestamp review ordering and fail-closed recovery
validation discovered while reviewing exact head c238b451. Production changes
must follow this RED.
"""

from datetime import datetime, timezone
import json

from oracc_tf.coordination import analyze, validate_completion

NOW = datetime(2026, 9, 5, 13, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40


def marker(kind, **payload):
    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def task(task_id="A", issue_number=101):
    return {
        "id": task_id,
        "title": task_id,
        "priority": "P0",
        "blocked_by": [],
        "status": "todo",
        "issue": issue_number,
    }


def registry():
    return {"schema_version": 2, "tasks": [task()]}


def claim(cid=10, session="impl", *, expires="2026-09-05T14:00:00Z"):
    return {
        "id": cid,
        "body": marker(
            "claim",
            task="A",
            session=session,
            base_sha=BASE,
            expires_at=expires,
        ),
    }


def issue(*comments):
    return {"number": 101, "state": "open", "comments": list(comments)}


def review(review_id, verdict, submitted_at):
    return {
        "id": review_id,
        "submitted_at": submitted_at,
        "body": marker(
            "review",
            task="A",
            review_session="reviewer",
            implementation_session="impl",
            head_sha=HEAD,
            verdict=verdict,
        ),
    }


def implementation_pr(reviews):
    return {
        "number": 201,
        "state": "open",
        "head_sha": HEAD,
        "body": marker("implementation", task="A", issue=101, session="impl"),
        "reviews": list(reviews),
    }


def snapshot(issue_a, *, prs=()):
    return {
        "main_sha": BASE,
        "issues": [issue_a],
        "pull_requests": list(prs),
    }


def test_same_timestamp_conflicting_graphql_reviews_fail_closed_as_ambiguous():
    same_time = "2026-09-05T14:00:00Z"
    # Opaque GraphQL ids have no chronological meaning. The lexicographically
    # larger id deliberately carries pass so the pre-fix implementation would
    # incorrectly approve instead of reporting ambiguity.
    reviews = [
        review("PRR_a", "request_changes", same_time),
        review("PRR_z", "pass", same_time),
    ]
    snap = snapshot(
        issue(claim()),
        prs=[implementation_pr(reviews)],
    )

    problems = validate_completion("A", registry(), snap, NOW)

    assert any("review order is ambiguous" in problem for problem in problems)


def test_invalid_recovery_markers_fail_closed_instead_of_disappearing():
    invalid_payloads = [
        {"task": "A", "claim_id": 10},
        {"task": "A", "session": "new", "claim_id": "10"},
        {"task": "A", "session": "new", "claim_id": 999},
    ]

    for offset, payload in enumerate(invalid_payloads, start=11):
        recovery = {"id": offset, "body": marker("recover", **payload)}
        state = analyze(registry(), snapshot(issue(recovery)), NOW)["A"]
        assert state.phase == "conflict", payload
        assert any("recover" in problem for problem in state.problems), payload
