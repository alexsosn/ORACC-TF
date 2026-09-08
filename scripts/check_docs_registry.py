#!/usr/bin/env python3
"""Validate the agentic documentation registry against its source documents.

docs/registry.json drives the automated development loop. This static check
validates git-side metadata only; a task is not claimable until GitHub issue,
claim, and PR state have also been reconciled by ``oracc_tf.coordination``.
User-facing generated/reference documentation under ``docs/reference`` is
intentionally outside this registry contract.

Verifies:
  * every registered-source docs/**/*.md outside docs/reference has required front-matter
  * every front-matter id is unique and matches its filename prefix
  * every depends_on / blocks target exists
  * registry documents match the files on disk, field for field
  * every registered document has exactly one structurally valid fact-policy entry
  * research/plan snapshot evidence has a real ISO date and non-empty evidence basis
  * every task's plan exists and its spec section is findable in that plan
  * the task graph is acyclic and every dependency id exists
  * no task is 'done' while a start or completion dependency is not
  * schema-v2 unfinished tasks have unique GitHub issue mappings
  * task-specific evidence_file paths are unique
  * completed/blocked task evidence files, when declared, exist

Usage: scripts/check_docs_registry.py [--docs docs]
Exit code 1 on any problem.
"""

import argparse
from collections.abc import Mapping
from datetime import date
import glob
import json
import os
from pathlib import Path
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "programs"))

from oracc_tf.coordination import validate_registry

REQUIRED = ("id", "title", "type", "status", "priority")
STATUSES = {"draft", "active", "done", "blocked", "superseded"}
PRIORITIES = {"P0", "P1", "P2"}
TASK_STATUSES = {"todo", "blocked", "done"}
FACT_POLICY_SCHEMA = 1
SNAPSHOT_TYPES = {"research", "plan"}
OPERATIONAL_TYPES = {"guide", "index"}


def front_matter(path):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        return None, text
    _, fm, body = text.split("---\n", 2)
    out = {}
    pending_list = None
    for line in fm.splitlines():
        if pending_list and re.match(r"^\s+-\s+", line):
            out[pending_list].append(re.sub(r"^\s+-\s+", "", line).strip())
            continue
        pending_list = None
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("["):
            val = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
        elif val == "":
            val = []
            pending_list = key
        out[key] = val
    return out, body


def fact_policy_problems(path: Path, meta: Mapping[str, object], body: str) -> list[str]:
    """Validate fact provenance structurally without guessing from numeric tokens."""
    del body  # Numeric literals are intentionally not scanned; policy is semantic metadata.
    problems: list[str] = []
    doc_type = meta.get("type")
    policy = meta.get("fact_policy")

    if doc_type in SNAPSHOT_TYPES:
        if policy != "snapshot-evidence":
            problems.append(
                f"{path}: {doc_type} document requires fact_policy 'snapshot-evidence'"
            )
        raw_date = meta.get("evidence_date")
        valid_date = isinstance(raw_date, str) and bool(raw_date) and raw_date == raw_date.strip()
        if valid_date:
            try:
                date.fromisoformat(raw_date)
            except ValueError:
                valid_date = False
        if not valid_date:
            problems.append(f"{path}: snapshot evidence requires a valid evidence_date (YYYY-MM-DD)")

        basis = meta.get("evidence_basis")
        if not isinstance(basis, str) or not basis.strip():
            problems.append(f"{path}: snapshot evidence requires non-empty evidence_basis")
        elif any(ord(char) < 0x20 for char in basis):
            problems.append(f"{path}: evidence_basis contains control characters")
    elif doc_type in OPERATIONAL_TYPES:
        if policy != "operational":
            problems.append(f"{path}: {doc_type} document requires fact_policy 'operational'")
    else:
        problems.append(f"{path}: unsupported fact-policy document type {doc_type!r}")

    return problems


def fact_policy_table_problems(
    registry_docs: Mapping[str, Mapping[str, object]],
    policies: Mapping[str, object],
) -> list[str]:
    """Require one fact-policy record for every and only registered document id."""
    problems: list[str] = []
    registry_ids = set(registry_docs)
    policy_ids = set(policies)

    for did in sorted(registry_ids - policy_ids):
        problems.append(f"fact policy: missing registered document {did}")
    for did in sorted(policy_ids - registry_ids):
        problems.append(f"fact policy: orphan document {did} is not registered")

    for did in sorted(registry_ids & policy_ids):
        reg_doc = registry_docs[did]
        policy = policies[did]
        if not isinstance(policy, Mapping):
            problems.append(f"fact policy: {did} entry must be an object")
            continue

        doc_type = reg_doc.get("type")
        expected_fields = (
            {"fact_policy", "evidence_date", "evidence_basis"}
            if doc_type in SNAPSHOT_TYPES
            else {"fact_policy"}
            if doc_type in OPERATIONAL_TYPES
            else set()
        )
        if expected_fields and set(policy) != expected_fields:
            problems.append(
                f"fact policy: {did} fields must be exactly {sorted(expected_fields)!r}"
            )

        path = Path(str(reg_doc.get("path") or did))
        merged = {"type": doc_type, **dict(policy)}
        problems.extend(fact_policy_problems(path, merged, ""))

    return problems


def task_dependencies(task):
    """Return all start and completion dependencies for validation/cycle checks."""

    return [
        *(task.get("blocked_by") or []),
        *(task.get("completion_blocked_by") or []),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    a = ap.parse_args()
    problems = []

    docs = {}
    bodies = {}
    reference_root = os.path.abspath(os.path.join(a.docs, "reference"))
    for path in sorted(glob.glob(os.path.join(a.docs, "**", "*.md"), recursive=True)):
        if os.path.abspath(path).startswith(reference_root + os.sep):
            continue
        fm, body = front_matter(path)
        if fm is None:
            problems.append(f"{path}: no YAML front-matter")
            continue
        for field in REQUIRED:
            if field not in fm:
                problems.append(f"{path}: front-matter missing '{field}'")
        did = fm.get("id")
        if did in docs:
            problems.append(f"{path}: duplicate id {did} (also {docs[did]['path']})")
        if fm.get("status") not in STATUSES | {None}:
            problems.append(f"{path}: bad status {fm.get('status')!r}")
        if fm.get("priority") not in PRIORITIES | {None}:
            problems.append(f"{path}: bad priority {fm.get('priority')!r}")
        base = os.path.basename(path)
        if did and did != "INDEX" and not base.startswith(did):
            problems.append(f"{path}: filename does not start with id {did}")
        if did:
            fm["path"] = path
            docs[did] = fm
            bodies[did] = body

    for did, fm in docs.items():
        for rel in ("depends_on", "blocks", "informs", "blocked_by"):
            for target in fm.get(rel) or []:
                if target not in docs:
                    problems.append(f"{did}: {rel} -> unknown document {target}")

    reg_path = os.path.join(a.docs, "registry.json")
    if not os.path.isfile(reg_path):
        problems.append(f"{reg_path}: missing")
        return report(problems)
    reg = json.load(open(reg_path, encoding="utf-8"))
    problems.extend(validate_registry(reg))

    reg_docs = {d["id"]: d for d in reg.get("documents", [])}
    for did in set(docs) | set(reg_docs):
        if did not in reg_docs:
            problems.append(f"registry: document {did} on disk but not registered")
        elif did not in docs:
            problems.append(f"registry: document {did} registered but not on disk")
        else:
            for field in ("status", "priority", "path", "title"):
                if str(reg_docs[did].get(field)) != str(docs[did].get(field)):
                    problems.append(
                        f"registry: {did}.{field} is {reg_docs[did].get(field)!r}, "
                        f"document says {docs[did].get(field)!r}")

    fact_policy_path = os.path.join(a.docs, "fact-policy.json")
    if not os.path.isfile(fact_policy_path):
        problems.append(f"{fact_policy_path}: missing")
    else:
        try:
            fact_policy = json.load(open(fact_policy_path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{fact_policy_path}: unreadable: {exc}")
        else:
            if not isinstance(fact_policy, Mapping):
                problems.append(f"{fact_policy_path}: root must be an object")
            elif fact_policy.get("schema_version") != FACT_POLICY_SCHEMA:
                problems.append(
                    f"{fact_policy_path}: unsupported schema {fact_policy.get('schema_version')!r}"
                )
            elif set(fact_policy) != {"schema_version", "documents"}:
                problems.append(
                    f"{fact_policy_path}: fields must be exactly ['documents', 'schema_version']"
                )
            elif not isinstance(fact_policy.get("documents"), Mapping):
                problems.append(f"{fact_policy_path}: documents must be an object")
            else:
                problems.extend(
                    fact_policy_table_problems(reg_docs, fact_policy["documents"])
                )

    tasks = {t["id"]: t for t in reg.get("tasks", [])}
    for tid, t in tasks.items():
        if t.get("status") not in TASK_STATUSES:
            problems.append(f"task {tid}: bad status {t.get('status')!r}")
        if t.get("priority") not in PRIORITIES:
            problems.append(f"task {tid}: bad priority {t.get('priority')!r}")
        plan = t.get("plan")
        if plan not in docs:
            problems.append(f"task {tid}: unknown plan {plan}")
        else:
            spec = (t.get("spec") or "").lstrip("§").strip()
            key = spec.split()[-1] if spec else ""
            if key and key not in bodies[plan]:
                problems.append(f"task {tid}: spec {t.get('spec')!r} not found in {plan}")
        for field in ("blocked_by", "completion_blocked_by"):
            for dep in t.get(field) or []:
                if dep not in tasks:
                    problems.append(f"task {tid}: {field} unknown task {dep}")
        evidence_file = t.get("evidence_file")
        if evidence_file and t.get("status") in {"done", "blocked"}:
            if not os.path.isfile(evidence_file):
                problems.append(f"task {tid}: evidence_file does not exist: {evidence_file}")

    # cycle detection across both start and completion dependencies
    colour = {}

    def visit(n, trail):
        if colour.get(n) == 1:
            problems.append("task cycle: " + " -> ".join(trail + [n]))
            return
        if colour.get(n) == 2:
            return
        colour[n] = 1
        for dep in task_dependencies(tasks.get(n, {})):
            if dep in tasks:
                visit(dep, trail + [n])
        colour[n] = 2

    for tid in tasks:
        visit(tid, [])

    for tid, t in tasks.items():
        if t.get("status") == "done":
            for dep in task_dependencies(t):
                if tasks.get(dep, {}).get("status") != "done":
                    problems.append(f"task {tid}: done but depends on unfinished {dep}")

    # Claim/start readiness deliberately considers only blocked_by. A task may
    # have completion_blocked_by dependencies when its issue permits research or
    # design to proceed before later production integration is allowed.
    dependency_ready = [
        tid
        for tid, t in sorted(tasks.items())
        if t.get("status") == "todo"
        and all(tasks.get(d, {}).get("status") == "done" for d in t.get("blocked_by") or [])
    ]
    if not problems:
        print(f"documents: {len(docs)}   tasks: {len(tasks)}")
        print(
            "dependency-ready; reconcile GitHub before claiming "
            f"({len(dependency_ready)}): {', '.join(dependency_ready[:8])}"
        )
    return report(problems)


def report(problems):
    for p in problems:
        print("  " + p)
    print("FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
