#!/usr/bin/env python3
"""Measure the documented local Text-Fabric browser path for ISSUE-83."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import resource
import sys
import time

from tf.browser.web import setup


def _peak_rss_kib() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if value > 10_000_000:
        value //= 1024
    return value


def profile(app_root: Path) -> dict[str, object]:
    app_spec = f"app:{app_root.resolve()}"
    started = time.perf_counter()
    with redirect_stdout(sys.stderr):
        webapp = setup(False, app_spec)
    elapsed = time.perf_counter() - started
    if webapp is None:
        return {
            "schema_version": 1,
            "app_loaded": False,
            "elapsed_seconds": elapsed,
            "peak_rss_kib": _peak_rss_kib(),
            "routes": {},
            "responses_nonempty": {},
        }

    routes: dict[str, int] = {}
    responses_nonempty: dict[str, bool] = {}
    with webapp.test_client() as client:
        for route in ("/", "/passage", "/query", "/export"):
            response = client.get(route)
            routes[route] = response.status_code
            responses_nonempty[route] = bool(response.data)

    return {
        "schema_version": 1,
        "app_loaded": True,
        "elapsed_seconds": elapsed,
        "peak_rss_kib": _peak_rss_kib(),
        "routes": routes,
        "responses_nonempty": responses_nonempty,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = profile(args.app_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if result["app_loaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
