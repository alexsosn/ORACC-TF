#!/usr/bin/env python3
"""Measure clean local Python use of an extracted ISSUE-83 standalone candidate."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import resource
import sys
import time

from tf.app import use


HEAVY_FEATURES = {"catalogue_json", "gdl_json", "sign_json"}


def _peak_rss_kib() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if value > 10_000_000:
        value //= 1024
    return value


def _tree_stats(root: Path) -> dict[str, int]:
    logical = 0
    allocated = 0
    files = 0
    if not root.exists():
        return {"logical_bytes": 0, "allocated_bytes": 0, "files": 0}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        logical += stat.st_size
        blocks = getattr(stat, "st_blocks", 0)
        allocated += blocks * 512 if blocks else stat.st_size
        files += 1
    return {"logical_bytes": logical, "allocated_bytes": allocated, "files": files}


def profile(stage: Path, *, version: str, archive: Path) -> dict[str, object]:
    stage = stage.resolve()
    tf_root = stage / "tf" / version
    app_root = stage / "app"
    docs_root = stage / "docs"
    before = _tree_stats(stage)
    tf_before = _tree_stats(tf_root)
    heavy_payload = {
        feature: _tree_stats(tf_root / f"{feature}.tf")
        for feature in sorted(HEAVY_FEATURES)
    }

    started = time.perf_counter()
    with redirect_stdout(sys.stderr):
        app = use(f"app:{app_root}", silent="deep")
    startup = time.perf_counter() - started
    if app is None or app.api is None:
        raise RuntimeError("standalone app failed to load")

    loaded = set(app.api.Fall())
    if loaded & HEAVY_FEATURES:
        raise RuntimeError(
            "normal standalone load unexpectedly preloaded heavy features: "
            + ", ".join(sorted(loaded & HEAVY_FEATURES))
        )

    documents = app.api.F.otype.s("document")
    lines = app.api.F.otype.s("line")
    if not documents or not lines:
        raise RuntimeError("standalone corpus has no document/line navigation surface")
    section = app.api.T.sectionFromNode(lines[0])

    query_started = time.perf_counter()
    query_result = next(iter(app.api.S.search("word", limit=1, silent="deep")), None)
    query_seconds = time.perf_counter() - query_started
    if query_result is None:
        raise RuntimeError("representative Text-Fabric query returned no result")

    after = _tree_stats(stage)
    cache = _tree_stats(tf_root / ".tf")
    return {
        "schema_version": 1,
        "stage": str(stage),
        "archive_bytes": archive.stat().st_size,
        "archive_name": archive.name,
        "before_first_load": before,
        "after_first_load": after,
        "tf_payload_before_load": tf_before,
        "tf_payload_after_load": _tree_stats(tf_root),
        "heavy_feature_payload": heavy_payload,
        "app_payload": _tree_stats(app_root),
        "docs_payload": _tree_stats(docs_root),
        "tf_cache": cache,
        "startup_seconds": startup,
        "peak_rss_kib": _peak_rss_kib(),
        "query_seconds": query_seconds,
        "query_result": list(query_result),
        "first_line_section": list(section) if section is not None else None,
        "max_slot": app.api.F.otype.maxSlot,
        "loaded_node_features": sorted(loaded),
        "excluded_heavy_features": sorted(HEAVY_FEATURES),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", type=Path)
    parser.add_argument("--version", required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = profile(args.stage, version=args.version, archive=args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
