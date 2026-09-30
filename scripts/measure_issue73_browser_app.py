#!/usr/bin/env python3
"""Measure the generated ISSUE-73 browser app on an existing TF corpus."""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import resource
import sys
import time

from tf.advanced.app import findApp
from tf.browser.kernel import makeTfKernel
from tf.browser.web import Web, factory


def _peak_rss_kib() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if value > 10_000_000:
        value //= 1024
    return value


def profile(tf_root: Path, app_root: Path, *, version: str) -> dict[str, object]:
    tf_root = tf_root.resolve()
    app_root = app_root.resolve()
    app_name = f"app:{app_root}"

    started = time.perf_counter()
    with redirect_stdout(sys.stderr):
        app = findApp(
            app_name,
            "",
            None,
            "github",
            True,
            locations=[str(tf_root)],
            modules=[""],
            version=version,
            silent="deep",
        )
    elapsed = time.perf_counter() - started
    if app is None or app.api is None:
        return {
            "schema_version": 1,
            "app_loaded": False,
            "elapsed_seconds": elapsed,
            "peak_rss_kib": _peak_rss_kib(),
            "routes": {},
            "responses_nonempty": {},
            "loaded_node_features": [],
            "excluded_features": [],
        }

    kernel = makeTfKernel(app, app_name)
    if not kernel:
        raise RuntimeError("generated app loaded but browser kernel setup failed")
    webapp = factory(Web(kernel))
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
        "loaded_node_features": sorted(app.api.Fall()),
        "excluded_features": sorted(app.context.excludedFeatures),
        "node_types": list(app.api.F.otype.all),
        "max_slot": app.api.F.otype.maxSlot,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tf_root", type=Path)
    parser.add_argument("app_root", type=Path)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    result = profile(args.tf_root, args.app_root, version=args.version)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["app_loaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
