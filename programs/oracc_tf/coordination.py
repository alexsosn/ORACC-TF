"""Parallel-safe task coordination for ORACC-TF's GitHub agent loop.

The reconciliation functions are deliberately pure: callers provide the git
registry and a normalized GitHub snapshot, and receive computed task states and
validation errors. Network writes remain the responsibility of the agent so
claims, recovery, supersession, and review stay visible in GitHub history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import re
from typing import Any, Iterable

SCHEMA_VERSION = 2
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
TASK_STATUSES = {"todo", "blocked", "done"}
KINDS = {"claim", "recover", "release", "implementation", "supersede", "review"}
MARKER_RE = re.compile(
    r"<!--\s*oracc-tf:(claim|recover|release|implementation|supersede|review)\s+(.+?)\s*-->",
    re.DOTALL,
)
# #43 was bootstrapped before the colon marker syntax was frozen. Read that one
# legacy spelling so its own lease remains auditable during the v1 -> v2 cutover.
LEGACY_CLAIM_RE = re.compile(r"<!--\s*oracc-tf-claim\s+(.+?)\s*-->", re.DOTALL)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TASK_HINT_RE = re.compile(r'"task"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')


@dataclass
class CoordinationState:
    """Computed runtime state for one registry task."""

    task_id: str
    phase: str
    owner_session: str | None = None
    winning_claim_id: int | None = None
    active_pr: int | None = None
    problems: list[str] = field(default_factory=list)


def _iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _marker_kind_name(prefix: str) -> str:
    if prefix == "oracc-tf-claim":
        return "claim"
    return prefix.rsplit(":", 1)[-1]


def _parse_markers(
    text: str | None,
) -> tuple[
    list[tuple[str, dict[str, Any]]],
    list[str],
    list[tuple[str, str, str]],
]:
    """Parse markers and retain malformed-attempt text for task-local scoping."""

    text = text or ""
    found: list[tuple[str, dict[str, Any]]] = []
    problems: list[str] = []
    malformed: list[tuple[str, str, str]] = []
    consumed: list[tuple[int, int, str]] = []

    def parse_match(kind: str, raw: str, span: tuple[int, int], attempt: str) -> None:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            message = f"malformed {kind} marker: {exc.msg}"
            problems.append(message)
            malformed.append((kind, attempt, message))
            consumed.append((*span, kind))
            return
        if not isinstance(payload, dict):
            message = f"malformed {kind} marker: payload must be an object"
            problems.append(message)
            malformed.append((kind, attempt, message))
            consumed.append((*span, kind))
            return
        found.append((kind, payload))
        consumed.append((*span, kind))

    for match in MARKER_RE.finditer(text):
        parse_match(match.group(1), match.group(2), match.span(), match.group(0))
    for match in LEGACY_CLAIM_RE.finditer(text):
        parse_match("claim", match.group(1), match.span(), match.group(0))

    # Detect an HTML-comment marker opener that did not form a complete marker.
    # Bare prose such as ``oracc-tf:recover`` is documentation, not a marker.
    for prefix in [*(f"oracc-tf:{kind}" for kind in KINDS), "oracc-tf-claim"]:
        kind = _marker_kind_name(prefix)
        opener = re.compile(rf"<!--\s*{re.escape(prefix)}\b")
        for match in opener.finditer(text):
            start = match.start()
            if any(a <= start < b and parsed_kind == kind for a, b, parsed_kind in consumed):
                continue
            end = text.find("-->", start)
            attempt = text[start : end + 3 if end >= 0 else len(text)]
            message = f"malformed {kind} marker"
            problems.append(message)
            malformed.append((kind, attempt, message))
    return found, problems, malformed


def _markers(text: str | None) -> tuple[list[tuple[str, dict[str, Any]]], list[str]]:
    """Parse machine markers; malformed HTML-comment marker attempts fail closed."""

    found, problems, _ = _parse_markers(text)
    return found, problems


def _task_hints(text: str) -> set[str]:
    hints: set[str] = set()
    for match in TASK_HINT_RE.finditer(text):
        raw = f'"{match.group(1)}"'
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, str):
            hints.add(value)
    return hints


def _issue_map(snapshot: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        item["number"]: item
        for item in snapshot.get("issues", [])
        if isinstance(item, dict) and isinstance(item.get("number"), int)
    }


def _task_map(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        task["id"]: task
        for task in registry.get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("id"), str)
    }


def validate_registry(registry: dict[str, Any]) -> list[str]:
    """Validate schema-v2 coordination metadata without contacting GitHub."""

    problems: list[str] = []
    if registry.get("schema_version") != SCHEMA_VERSION:
        problems.append(
            f"registry schema_version must be {SCHEMA_VERSION}, got {registry.get('schema_version')!r}"
        )
    tasks_list = registry.get("tasks", [])
    if not isinstance(tasks_list, list):
        return problems + ["registry tasks must be a list"]

    ids: set[str] = set()
    tasks: dict[str, dict[str, Any]] = {}
    issue_owner: dict[int, str] = {}
    evidence_owner: dict[str, str] = {}
    for index, task in enumerate(tasks_list):
        if not isinstance(task, dict):
            problems.append(f"task at index {index}: must be an object")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            problems.append(f"task at index {index}: missing id")
            continue
        if task_id in ids:
            problems.append(f"task {task_id}: duplicate id")
            continue
        ids.add(task_id)
        tasks[task_id] = task

        status = task.get("status")
        if status not in TASK_STATUSES:
            problems.append(f"task {task_id}: bad status {status!r}")
        if task.get("priority") not in PRIORITY_RANK:
            problems.append(f"task {task_id}: bad priority {task.get('priority')!r}")

        issue_number = task.get("issue")
        if status != "done" and (not isinstance(issue_number, int) or issue_number <= 0):
            problems.append(f"task {task_id}: unfinished task requires a GitHub issue")
        if issue_number is not None:
            if not isinstance(issue_number, int) or issue_number <= 0:
                problems.append(f"task {task_id}: issue must be a positive integer")
            elif issue_number in issue_owner:
                problems.append(
                    f"task {task_id}: issue {issue_number} also mapped by {issue_owner[issue_number]}"
                )
            else:
                issue_owner[issue_number] = task_id

        evidence_file = task.get("evidence_file")
        if evidence_file is not None:
            if not isinstance(evidence_file, str) or not evidence_file:
                problems.append(f"task {task_id}: evidence_file must be a non-empty string")
            elif evidence_file in evidence_owner:
                problems.append(
                    f"task {task_id}: evidence_file {evidence_file!r} also used by "
                    f"{evidence_owner[evidence_file]}"
                )
            else:
                evidence_owner[evidence_file] = task_id

    for task_id, task in tasks.items():
        dependencies = task.get("blocked_by") or []
        if not isinstance(dependencies, list):
            problems.append(f"task {task_id}: blocked_by must be a list")
            continue
        for dependency in dependencies:
            if dependency not in tasks:
                problems.append(f"task {task_id}: blocked_by unknown task {dependency}")
        if task.get("status") == "done":
            for dependency in dependencies:
                if tasks.get(dependency, {}).get("status") != "done":
                    problems.append(
                        f"task {task_id}: done but depends on unfinished {dependency}"
                    )
    return problems


def _comment_events(
    issue: dict[str, Any] | None, task_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    problems: list[str] = []
    if issue is None:
        return events, problems
    for comment in issue.get("comments", []) or []:
        if not isinstance(comment, dict):
            continue
        comment_id = comment.get("id")
        parsed, parse_problems = _markers(comment.get("body"))
        problems.extend(parse_problems)
        for kind, payload in parsed:
            if payload.get("task") == task_id:
                events.append({"id": comment_id, "kind": kind, "payload": payload})
    events.sort(key=lambda event: event["id"] if isinstance(event.get("id"), int) else 2**63)
    return events, problems


def _claim_state(
    events: list[dict[str, Any]], now: datetime
) -> tuple[str | None, int | None, bool, bool, list[str]]:
    """Resolve leases to owner/id plus conflict/stale flags."""

    problems: list[str] = []
    claims = [event for event in events if event["kind"] == "claim"]
    recoveries = [event for event in events if event["kind"] == "recover"]
    releases = [event for event in events if event["kind"] == "release"]
    stale_unrecovered: list[dict[str, Any]] = []
    live: list[dict[str, Any]] = []

    claim_ids = {
        event.get("id")
        for event in claims
        if isinstance(event.get("id"), int)
    }
    valid_recoveries: list[dict[str, Any]] = []
    for recovery in recoveries:
        recovery_id = recovery.get("id")
        recovery_payload = recovery["payload"]
        recovery_session = recovery_payload.get("session")
        recovery_claim_id = recovery_payload.get("claim_id")
        if not isinstance(recovery_id, int):
            problems.append("recover marker is attached to a comment without an integer id")
            continue
        if not isinstance(recovery_session, str) or not recovery_session:
            problems.append(f"recover {recovery_id}: missing session")
            continue
        if not isinstance(recovery_claim_id, int):
            problems.append(f"recover {recovery_id}: invalid claim_id")
            continue
        if recovery_claim_id not in claim_ids:
            problems.append(
                f"recover {recovery_id}: references unknown claim {recovery_claim_id}"
            )
            continue
        valid_recoveries.append(recovery)

    valid_releases: list[dict[str, Any]] = []
    for release in releases:
        release_id = release.get("id")
        release_payload = release["payload"]
        release_session = release_payload.get("session")
        if not isinstance(release_id, int):
            problems.append("release marker is attached to a comment without an integer id")
            continue
        if not isinstance(release_session, str) or not release_session:
            problems.append(f"release {release_id}: missing session")
            continue
        claim_id = release_payload.get("claim_id")
        if claim_id is not None and not isinstance(claim_id, int):
            problems.append(f"release {release_id}: invalid claim_id")
            continue
        valid_releases.append(release)

    for event in claims:
        payload = event["payload"]
        claim_id = event.get("id")
        session = payload.get("session")
        expiry = _iso_datetime(payload.get("expires_at"))
        base_sha = payload.get("base_sha")
        if not isinstance(claim_id, int):
            problems.append("claim marker is attached to a comment without an integer id")
            continue
        if not isinstance(session, str) or not session:
            problems.append(f"claim {claim_id}: missing session")
            continue
        if expiry is None:
            problems.append(f"claim {claim_id}: invalid expires_at")
            continue
        if not isinstance(base_sha, str) or not SHA_RE.fullmatch(base_sha):
            problems.append(f"claim {claim_id}: invalid base_sha")
            continue

        released = False
        for release in valid_releases:
            if release["id"] <= claim_id:
                continue
            release_payload = release["payload"]
            release_session = release_payload["session"]
            targets_claim = release_payload.get("claim_id") == claim_id
            targets_session = (
                release_payload.get("claim_id") is None and release_session == session
            )
            if not (targets_claim or targets_session):
                continue
            if release_session != session:
                problems.append(
                    f"release {release['id']}: session does not own claim {claim_id}"
                )
                continue
            released = True
            break
        if released:
            continue

        recovered = any(
            recovery["id"] > claim_id
            and recovery["payload"]["claim_id"] == claim_id
            for recovery in valid_recoveries
        )
        if expiry <= now:
            if not recovered:
                stale_unrecovered.append(event)
            continue
        if recovered:
            problems.append(f"claim {claim_id}: live claim cannot be recovered")
            continue
        live.append(event)

    live.sort(key=lambda event: event["id"])
    if stale_unrecovered and live:
        problems.append(
            "new claim exists while an earlier stale claim has not been explicitly recovered"
        )
    if not live:
        return None, None, False, bool(stale_unrecovered), problems

    winner = live[0]
    owner = winner["payload"]["session"]
    sessions = {event["payload"].get("session") for event in live}
    return owner, winner["id"], len(sessions) > 1, bool(stale_unrecovered), problems


def _pr_info(
    snapshot: dict[str, Any], task_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    prs: list[dict[str, Any]] = []
    problems: list[str] = []
    for pr in snapshot.get("pull_requests", []) or []:
        if not isinstance(pr, dict) or pr.get("state") != "open":
            continue
        body = pr.get("body") or ""
        parsed, _, malformed = _parse_markers(body)
        valid_task_markers = [
            (kind, payload)
            for kind, payload in parsed
            if payload.get("task") == task_id
        ]
        implementation_tasks = {
            payload.get("task")
            for kind, payload in parsed
            if kind == "implementation" and isinstance(payload.get("task"), str)
        }

        scoped_problems: list[str] = []
        for _, attempt, message in malformed:
            hints = _task_hints(attempt)
            if task_id in hints:
                scoped_problems.append(message)
            elif not hints and implementation_tasks == {task_id}:
                # An unscoped malformed marker on a PR with one unambiguous
                # implementation owner belongs to that PR's task.
                scoped_problems.append(message)

        if not valid_task_markers and not scoped_problems:
            continue
        problems.extend(scoped_problems)

        implementations = [
            payload
            for kind, payload in valid_task_markers
            if kind == "implementation"
        ]
        if not implementations:
            continue
        bindings = {
            (payload.get("issue"), payload.get("session"))
            for payload in implementations
        }
        if len(bindings) > 1:
            problems.append(
                f"task {task_id}: conflicting implementation markers in PR {pr.get('number')}"
            )
        implementation = implementations[0]
        supersedes = {
            payload.get("old_pr")
            for kind, payload in valid_task_markers
            if kind == "supersede"
            and payload.get("session") == implementation.get("session")
            and isinstance(payload.get("old_pr"), int)
        }
        enriched = dict(pr)
        enriched["_implementation"] = implementation
        enriched["_supersedes"] = supersedes
        prs.append(enriched)
    return prs, problems


def _select_active_pr(
    prs: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    if not prs:
        return None, []
    if len(prs) == 1:
        return prs[0], []
    numbers = {pr.get("number") for pr in prs}
    candidates = [
        pr
        for pr in prs
        if (numbers - {pr.get("number")}) <= set(pr.get("_supersedes") or set())
    ]
    if len(candidates) == 1:
        return candidates[0], []
    return None, [
        "multiple active implementation PRs without one explicit supersession winner"
    ]


def analyze(
    registry: dict[str, Any], snapshot: dict[str, Any], now: datetime
) -> dict[str, CoordinationState]:
    """Reconcile git task state with a normalized GitHub snapshot."""

    tasks = _task_map(registry)
    issues = _issue_map(snapshot)
    result: dict[str, CoordinationState] = {}
    now = now.astimezone(timezone.utc) if now.tzinfo else now.replace(tzinfo=timezone.utc)

    for task_id, task in tasks.items():
        problems: list[str] = []
        status = task.get("status")
        issue_number = task.get("issue")
        issue = issues.get(issue_number) if isinstance(issue_number, int) else None

        if status != "done" and issue is None:
            problems.append(f"task {task_id}: unfinished task has no matching GitHub issue")
        if issue is not None:
            issue_state = issue.get("state")
            if status == "done" and issue_state == "open":
                problems.append(f"task {task_id}: registry is done but issue is open")
            if status != "done" and issue_state == "closed":
                problems.append(
                    f"task {task_id}: issue is closed while registry status is {status}"
                )

        dependencies_done = all(
            tasks.get(dependency, {}).get("status") == "done"
            for dependency in task.get("blocked_by") or []
        )
        events, event_problems = _comment_events(issue, task_id)
        problems.extend(event_problems)
        owner, winning_id, claim_conflict, stale, claim_problems = _claim_state(events, now)
        problems.extend(claim_problems)

        prs, pr_parse_problems = _pr_info(snapshot, task_id)
        problems.extend(pr_parse_problems)
        active_pr, pr_select_problems = _select_active_pr(prs)
        problems.extend(pr_select_problems)

        if active_pr is not None:
            implementation = active_pr["_implementation"]
            if implementation.get("issue") != issue_number:
                problems.append(
                    f"task {task_id}: implementation PR issue "
                    f"{implementation.get('issue')!r} does not match registry issue "
                    f"{issue_number!r}"
                )
            implementation_session = implementation.get("session")
            if not isinstance(implementation_session, str) or not implementation_session:
                problems.append(f"task {task_id}: implementation PR is missing session")
            elif owner is None:
                problems.append(f"task {task_id}: implementation PR has no winning claim")
            elif implementation_session != owner:
                problems.append(
                    f"task {task_id}: implementation session {implementation_session!r} "
                    f"does not match winning claim session {owner!r}"
                )
        if claim_conflict:
            problems.append(f"task {task_id}: multiple live claim sessions")

        if problems:
            phase = "conflict"
        elif status == "done":
            phase = "done"
        elif status == "blocked" or not dependencies_done:
            phase = "blocked"
        elif stale:
            phase = "stale"
        elif active_pr is not None:
            phase = "review"
        elif owner is not None:
            phase = "claimed"
        else:
            phase = "ready"

        result[task_id] = CoordinationState(
            task_id=task_id,
            phase=phase,
            owner_session=owner,
            winning_claim_id=winning_id,
            active_pr=active_pr.get("number") if active_pr is not None else None,
            problems=problems,
        )
    return result


def claim_result(state: CoordinationState, session: str) -> str:
    """Return this session's claim disposition after re-reading GitHub."""

    if state.phase == "conflict":
        race_only = bool(state.problems) and all(
            problem.endswith("multiple live claim sessions")
            for problem in state.problems
        )
        if race_only and state.owner_session == session:
            return "owned"
        return "conflict"
    if state.owner_session == session:
        return "owned"
    if state.owner_session is not None:
        return "conflict"
    if state.phase == "ready":
        return "available"
    return state.phase


def ready_tasks(
    registry: dict[str, Any], snapshot: dict[str, Any], now: datetime
) -> list[str]:
    """Return every currently claimable task, priority then id ordered."""

    states = analyze(registry, snapshot, now)
    tasks = _task_map(registry)
    ready = [
        task_id
        for task_id, state in states.items()
        if state.phase == "ready" and tasks[task_id].get("status") == "todo"
    ]
    return sorted(
        ready,
        key=lambda task_id: (
            PRIORITY_RANK.get(tasks[task_id].get("priority"), 99),
            task_id,
        ),
    )


def _find_active_pr(
    snapshot: dict[str, Any], number: int | None
) -> dict[str, Any] | None:
    if number is None:
        return None
    return next(
        (
            pr
            for pr in snapshot.get("pull_requests", []) or []
            if isinstance(pr, dict) and pr.get("number") == number
        ),
        None,
    )


def validate_completion(
    task_id: str,
    registry: dict[str, Any],
    snapshot: dict[str, Any],
    now: datetime,
) -> list[str]:
    """Check dependency, ownership, PR, and independent exact-head review gates."""

    tasks = _task_map(registry)
    task = tasks.get(task_id)
    if task is None:
        return [f"unknown task {task_id}"]
    problems: list[str] = []
    for dependency in task.get("blocked_by") or []:
        status = tasks.get(dependency, {}).get("status")
        if status != "done":
            problems.append(f"task {task_id}: dependency {dependency} is {status}")

    state = analyze(registry, snapshot, now)[task_id]
    problems.extend(state.problems)
    if state.phase == "blocked":
        problems.append(f"task {task_id}: blocked task cannot pass completion gate")
    pr = _find_active_pr(snapshot, state.active_pr)
    if pr is None:
        problems.append(f"task {task_id}: no active implementation PR")
        return _dedupe(problems)

    parsed, parse_problems = _markers(pr.get("body"))
    problems.extend(parse_problems)
    implementations = [
        payload
        for kind, payload in parsed
        if kind == "implementation" and payload.get("task") == task_id
    ]
    if not implementations:
        problems.append(f"task {task_id}: active PR lacks implementation marker")
        return _dedupe(problems)
    implementation = implementations[0]
    implementation_session = implementation.get("session")
    head_sha = pr.get("head_sha")
    if not isinstance(head_sha, str) or not SHA_RE.fullmatch(head_sha):
        problems.append(f"task {task_id}: active PR has invalid head_sha")
        return _dedupe(problems)

    saw_self_review = False
    saw_stale_pass = False
    saw_any_review = False
    exact_reviews: list[dict[str, Any]] = []
    for index, review in enumerate(pr.get("reviews", []) or []):
        if not isinstance(review, dict):
            continue
        review_markers, review_problems = _markers(review.get("body"))
        problems.extend(review_problems)
        for kind, payload in review_markers:
            if kind != "review" or payload.get("task") != task_id:
                continue
            saw_any_review = True
            if payload.get("implementation_session") != implementation_session:
                problems.append(
                    f"task {task_id}: review names a different implementation session"
                )
                continue
            review_session = payload.get("review_session")
            if not isinstance(review_session, str) or not review_session:
                problems.append(f"task {task_id}: review is missing review_session")
                continue
            if review_session == implementation_session:
                if payload.get("verdict") == "pass":
                    saw_self_review = True
                continue
            if payload.get("head_sha") != head_sha:
                if payload.get("verdict") == "pass":
                    saw_stale_pass = True
                continue
            exact_reviews.append(
                {
                    "verdict": str(payload.get("verdict")),
                    "submitted_at": _iso_datetime(review.get("submitted_at")),
                    "id": review.get("id"),
                    "index": index,
                }
            )

    if exact_reviews:
        submitted = [entry["submitted_at"] for entry in exact_reviews]
        int_ids = [entry["id"] for entry in exact_reviews]
        latest_verdict: str | None = None
        if all(value is not None for value in submitted):
            latest_time = max(submitted)
            latest_entries = [
                entry for entry in exact_reviews if entry["submitted_at"] == latest_time
            ]
            latest_verdicts = {entry["verdict"] for entry in latest_entries}
            if len(latest_verdicts) == 1:
                latest_verdict = next(iter(latest_verdicts))
            elif all(isinstance(entry["id"], int) for entry in latest_entries):
                latest = max(
                    latest_entries,
                    key=lambda entry: (entry["id"], entry["index"]),
                )
                latest_verdict = latest["verdict"]
            else:
                problems.append(f"task {task_id}: exact-head review order is ambiguous")
        elif all(isinstance(value, int) for value in int_ids):
            latest = max(exact_reviews, key=lambda entry: (entry["id"], entry["index"]))
            latest_verdict = latest["verdict"]
        elif len(exact_reviews) == 1:
            latest_verdict = exact_reviews[0]["verdict"]
        else:
            problems.append(f"task {task_id}: exact-head review order is ambiguous")

        if latest_verdict is not None and latest_verdict != "pass":
            problems.append(
                f"task {task_id}: latest exact-head review is {latest_verdict!r}, not pass"
            )
    else:
        if saw_self_review:
            problems.append(
                f"task {task_id}: self-review cannot satisfy independent review"
            )
        if saw_stale_pass:
            problems.append(
                f"task {task_id}: independent review is not for the exact head {head_sha}"
            )
        if not saw_any_review:
            problems.append(f"task {task_id}: independent review is missing")
        elif not saw_self_review and not saw_stale_pass:
            problems.append(
                f"task {task_id}: no passing independent review for exact head"
            )
    return _dedupe(problems)


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
