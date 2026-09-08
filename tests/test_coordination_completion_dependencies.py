"""Regression tests for start-ready tasks with later completion dependencies."""

from datetime import datetime, timezone

from oracc_tf.coordination import ready_tasks, validate_completion, validate_registry

NOW = datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc)
BASE = "a" * 40
HEAD = "b" * 40


def marker(kind, **payload):
    import json

    return f"<!-- oracc-tf:{kind} {json.dumps(payload, sort_keys=True)} -->"


def task(task_id, issue, *, status="todo", blocked_by=(), completion_blocked_by=()):
    return {
        "id": task_id,
        "title": task_id,
        "priority": "P0",
        "blocked_by": list(blocked_by),
        "completion_blocked_by": list(completion_blocked_by),
        "status": status,
        "issue": issue,
    }


def registry(*tasks):
    return {"schema_version": 2, "tasks": list(tasks)}


def issue(number, *, state="open", comments=()):
    return {"number": number, "state": state, "comments": list(comments)}


def snapshot(*issues, prs=()):
    return {
        "main_sha": BASE,
        "issues": list(issues),
        "pull_requests": list(prs),
    }


def claim(task_id, session="impl"):
    return {
        "id": 10,
        "body": marker(
            "claim",
            task=task_id,
            session=session,
            base_sha=BASE,
            expires_at="2026-09-07T21:00:00Z",
        ),
    }


def implementation_pr(task_id, issue_number, session="impl"):
    return {
        "number": 201,
        "state": "open",
        "head_sha": HEAD,
        "body": marker(
            "implementation",
            task=task_id,
            issue=issue_number,
            session=session,
        ),
        "reviews": [
            {
                "id": 1,
                "body": marker(
                    "review",
                    task=task_id,
                    review_session="reviewer",
                    implementation_session=session,
                    head_sha=HEAD,
                    verdict="pass",
                ),
            }
        ],
    }


def test_completion_dependency_does_not_block_claim_but_blocks_finalization():
    reg = registry(
        task("UPSTREAM", 100),
        task("RESEARCH", 101, completion_blocked_by=("UPSTREAM",)),
    )
    open_snapshot = snapshot(issue(100), issue(101))

    assert "RESEARCH" in ready_tasks(reg, open_snapshot, NOW)

    completion_snapshot = snapshot(
        issue(100),
        issue(101, comments=[claim("RESEARCH")]),
        prs=[implementation_pr("RESEARCH", 101)],
    )
    problems = validate_completion("RESEARCH", reg, completion_snapshot, NOW)

    assert any("completion dependency UPSTREAM is todo" in problem for problem in problems)


def test_registry_rejects_unknown_completion_dependency():
    reg = registry(task("A", 101, completion_blocked_by=("MISSING",)))

    assert any(
        "completion_blocked_by unknown task MISSING" in problem
        for problem in validate_registry(reg)
    )


def test_done_task_requires_completion_dependencies_to_be_done():
    reg = registry(
        task("A", 101, status="todo"),
        task("B", 102, status="done", completion_blocked_by=("A",)),
    )

    assert any(
        "done but depends on unfinished A" in problem
        for problem in validate_registry(reg)
    )
