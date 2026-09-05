#!/usr/bin/env python3
"""Validate the maintainer documentation registry against documents on disk.

``docs/registry.json`` drives the automated development loop, so it owns the
maintainer-facing document graph: the docs index plus research, plans, guides,
and reports that declare stable document ids. ``docs/reference/**`` is a
separate user-facing/generated surface owned by ``scripts/check_docs.py``; it
is deliberately excluded here so generated per-feature pages never need manual
registry entries.

Verifies:
  * every registry-owned Markdown document has required front matter
  * every front-matter id is unique and matches its filename prefix
  * every depends_on / blocks target exists
  * registry documents match the files on disk, field for field
  * every task's plan exists and its spec section is findable in that plan
  * the task graph is acyclic and every blocked_by id exists
  * no task is 'done' while something it depends on is not

Usage: scripts/check_docs_registry.py [--docs docs]
Exit code 1 on any problem.
"""

import argparse
import glob
import json
import os
import re
import sys

REQUIRED = ("id", "title", "type", "status", "priority")
STATUSES = {"draft", "active", "done", "blocked", "superseded"}
PRIORITIES = {"P0", "P1", "P2"}
TASK_STATUSES = {"todo", "in_progress", "blocked", "done"}
REFERENCE_DIR = "reference"


def front_matter(path):
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---\n"):
        return None, text
    _, fm, body = text.split("---\n", 2)
    out = {}
    for line in fm.splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("["):
            val = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
        out[key] = val
    return out, body


def _registry_owned(path, docs_root):
    rel = os.path.relpath(path, docs_root)
    return rel.split(os.sep, 1)[0] != REFERENCE_DIR


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="docs")
    a = ap.parse_args()
    problems = []

    docs = {}
    bodies = {}
    all_markdown = sorted(glob.glob(os.path.join(a.docs, "**", "*.md"), recursive=True))
    for path in (path for path in all_markdown if _registry_owned(path, a.docs)):
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
                        f"document says {docs[did].get(field)!r}"
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
        for dep in t.get("blocked_by") or []:
            if dep not in tasks:
                problems.append(f"task {tid}: blocked_by unknown task {dep}")

    colour = {}

    def visit(n, trail):
        if colour.get(n) == 1:
            problems.append("task cycle: " + " -> ".join(trail + [n]))
            return
        if colour.get(n) == 2:
            return
        colour[n] = 1
        for dep in tasks.get(n, {}).get("blocked_by") or []:
            if dep in tasks:
                visit(dep, trail + [n])
        colour[n] = 2

    for tid in tasks:
        visit(tid, [])

    for tid, t in tasks.items():
        if t.get("status") == "done":
            for dep in t.get("blocked_by") or []:
                if tasks.get(dep, {}).get("status") != "done":
                    problems.append(f"task {tid}: done but depends on unfinished {dep}")

    ready = [
        tid
        for tid, t in sorted(tasks.items())
        if t.get("status") == "todo"
        and all(tasks.get(d, {}).get("status") == "done" for d in t.get("blocked_by") or [])
    ]
    if not problems:
        print(f"documents: {len(docs)}   tasks: {len(tasks)}")
        print(f"ready now ({len(ready)}): {', '.join(ready[:8])}")
    return report(problems)


def report(problems):
    for p in problems:
        print("  " + p)
    print("FAILED" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
