#!/usr/bin/env python3
"""Reproducible Text-Fabric app measurements for issue #69.

This module is deliberately research tooling, not a corpus application.  It
loads an existing TF root through Text-Fabric's real advanced-app API and can
create an isolated copy with candidate display formats for behavior probes.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path
import resource
import shutil
import sys
import time

from tf.app import use
import tf.browser.command as browser_command
from tf.browser.kernel import makeTfKernel
from tf.browser.web import Web, factory as browser_factory

from oracc_tf import corpus


SCHEMA_VERSION = 1
CUNEIFORM_FORMAT = "@fmt:text-orig-full={utf8}"
TRANSLITERATION_FORMAT = "@fmt:text-trans-full=word#{form} "
BHSA_NONE_VALUES = ("absent", "n/a", "none", "unknown", "null", "NA")
DEFAULT_HEAVY_FEATURES = ("sign_json", "gdl_json", "catalogue_json")


def _peak_rss_kib() -> int:
    """Return process peak resident memory in KiB on the Linux CI baseline."""
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # macOS reports bytes while Linux reports KiB.  Keep the public result in KiB.
    if value > 10_000_000:
        value //= 1024
    return value


def profile_advanced_app(
    tf_root: Path | str,
    *,
    excluded_features: tuple[str, ...] | list[str] = (),
) -> dict[str, object]:
    """Load a local TF root through the real advanced app and record the result."""
    root = Path(tf_root).resolve()
    excluded = tuple(excluded_features)
    started = time.perf_counter()
    app = use(
        f"data:{root}",
        dataDisplay={"excludedFeatures": list(excluded)},
        silent="deep",
    )
    elapsed = time.perf_counter() - started
    if app is None or app.api is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "app_loaded": False,
            "excluded_features": list(excluded),
            "elapsed_seconds": elapsed,
            "peak_rss_kib": _peak_rss_kib(),
            "max_slot": 0,
            "loaded_node_features": [],
            "loaded_edge_features": [],
        }

    api = app.api
    return {
        "schema_version": SCHEMA_VERSION,
        "app_loaded": True,
        "excluded_features": list(excluded),
        "elapsed_seconds": elapsed,
        "peak_rss_kib": _peak_rss_kib(),
        "max_slot": api.F.otype.maxSlot,
        "loaded_node_features": sorted(api.Fall()),
        "loaded_edge_features": sorted(api.Eall()),
    }


def probe_browser_routes(tf_root: Path | str) -> dict[str, object]:
    """Exercise Text-Fabric's browser kernel/routes without opening a server.

    Text-Fabric 13.1 accepts ``data:/path`` in ``tf.app.use()``.  Browser CLI
    support is measured through the installed parser instead of being frozen in
    the harness: pinned 13.1.0 currently rejects the data-only source, while a
    future compatible parser may accept it.  The route probe still starts from a
    real AdvancedApp and feeds it into the same browser kernel and Flask factory.
    """
    root = Path(tf_root).resolve()
    data_spec = f"data:{root}"
    cli_supported = browser_command.argApp((data_spec,), False) is not None

    advanced_app = use(data_spec, silent="deep")
    if advanced_app is None or advanced_app.api is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "browser_setup": False,
            "probe_path": "advanced-app->kernel->factory",
            "data_only_browser_cli_supported": cli_supported,
            "routes": {},
            "responses_nonempty": {},
        }

    kernel_api = makeTfKernel(advanced_app, data_spec)
    if not kernel_api:
        return {
            "schema_version": SCHEMA_VERSION,
            "browser_setup": False,
            "probe_path": "advanced-app->kernel->factory",
            "data_only_browser_cli_supported": cli_supported,
            "routes": {},
            "responses_nonempty": {},
        }
    webapp = browser_factory(Web(kernel_api))

    route_names = ("/", "/passage", "/query", "/export")
    routes: dict[str, int] = {}
    responses_nonempty: dict[str, bool] = {}
    with webapp.test_client() as client:
        for route in route_names:
            response = client.get(route)
            routes[route] = response.status_code
            responses_nonempty[route] = bool(response.data)

    return {
        "schema_version": SCHEMA_VERSION,
        "browser_setup": True,
        "probe_path": "advanced-app->kernel->factory",
        "data_only_browser_cli_supported": cli_supported,
        "routes": routes,
        "responses_nonempty": responses_nonempty,
    }


def measure_feature_bytes(
    tf_root: Path | str,
    *,
    features: tuple[str, ...] | list[str] = DEFAULT_HEAVY_FEATURES,
) -> dict[str, object]:
    """Measure source `.tf` bytes for candidate browser-heavy node features.

    Missing files are an error: a typo or schema drift must not silently turn an
    exclusion candidate into a zero-byte result.
    """
    root = Path(tf_root).resolve()
    feature_bytes: dict[str, int] = {}
    for feature in features:
        path = root / f"{feature}.tf"
        if not path.is_file():
            raise FileNotFoundError(f"TF feature file not found: {path}")
        feature_bytes[feature] = path.stat().st_size
    return {
        "schema_version": SCHEMA_VERSION,
        "feature_bytes": feature_bytes,
        "total_bytes": sum(feature_bytes.values()),
    }


def census_exact_values(
    tf_root: Path | str,
    *,
    candidates: tuple[str, ...] | list[str] = BHSA_NONE_VALUES,
) -> dict[str, object]:
    """Count exact node-feature values that could be configured as `noneValues`.

    The default candidates are the values used by the pinned BHSA app.  They are
    measurement inputs only: a value is recommended for ORACC-TF only if it is
    actually observed and its source semantics justify treating it as absent.
    """
    candidate_values = tuple(candidates)
    candidate_set = set(candidate_values)
    counts = {value: 0 for value in candidate_values}
    features_seen: dict[str, set[str]] = {value: set() for value in candidate_values}

    api = corpus.load_tf(Path(tf_root))
    for feature in sorted(api.Fall()):
        feature_api = api.Fs(feature)
        if feature_api is None:
            continue
        for _node, value in feature_api.items():
            if not isinstance(value, str) or value not in candidate_set:
                continue
            counts[value] += 1
            features_seen[value].add(feature)

    return {
        "schema_version": SCHEMA_VERSION,
        "candidates": list(candidate_values),
        "counts": counts,
        "features": {
            value: sorted(feature_names)
            for value, feature_names in features_seen.items()
        },
    }


def _insert_otext_formats(payload: str) -> str:
    header, separator, body = payload.partition("\n\n")
    if not separator:
        raise ValueError("otext.tf lacks a metadata/body separator")
    lines = header.splitlines()
    keys = {line.split("=", 1)[0] for line in lines if line.startswith("@fmt:")}
    additions = []
    if "@fmt:text-orig-full" not in keys:
        additions.append(CUNEIFORM_FORMAT)
    if "@fmt:text-trans-full" not in keys:
        additions.append(TRANSLITERATION_FORMAT)
    return "\n".join([*lines, *additions]) + separator + body


def inject_prototype_formats(source: Path | str, target: Path | str) -> None:
    """Copy a TF root and add candidate formats without mutating source bytes."""
    source_path = Path(source)
    target_path = Path(target)
    if target_path.exists() or target_path.is_symlink():
        if target_path.is_dir() and not target_path.is_symlink():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
    shutil.copytree(source_path, target_path)

    # A copied Text-Fabric binary cache may describe the pre-prototype otext file.
    shutil.rmtree(target_path / ".tf", ignore_errors=True)
    otext = target_path / "otext.tf"
    if not otext.is_file():
        raise ValueError(f"TF prototype has no otext.tf: {target_path}")
    otext.write_text(
        _insert_otext_formats(otext.read_text(encoding="utf-8")),
        encoding="utf-8",
    )


def probe_text_formats(tf_root: Path | str) -> dict[str, object]:
    """Exercise candidate formats on synthetic and semantic TF positions separately."""
    api = corpus.load_tf(Path(tf_root))
    synthetic_slots = [
        slot
        for slot in range(1, api.F.otype.maxSlot + 1)
        if api.F.synthetic.v(slot) == 1
    ]

    first_synthetic = synthetic_slots[0] if synthetic_slots else None
    synthetic_utf8 = (
        api.F.utf8.v(first_synthetic) if first_synthetic is not None else None
    )
    synthetic_cuneiform = (
        api.T.text(first_synthetic, fmt="text-orig-full")
        if first_synthetic is not None
        else None
    )
    synthetic_transliteration = (
        api.T.text(first_synthetic, fmt="text-trans-full")
        if first_synthetic is not None
        else None
    )

    semantic_slot = next(
        (
            slot
            for slot in range(1, api.F.otype.maxSlot + 1)
            if api.F.synthetic.v(slot) != 1
            and isinstance(api.F.utf8.v(slot), str)
            and api.F.utf8.v(slot)
        ),
        None,
    )
    if semantic_slot is None:
        raise ValueError("TF prototype has no semantic slot with source Unicode")

    semantic_lines = tuple(api.L.u(semantic_slot, otype="line"))
    if not semantic_lines:
        raise ValueError(f"semantic slot {semantic_slot} has no containing line")
    semantic_line = semantic_lines[0]
    semantic_cuneiform = api.T.text(semantic_line, fmt="text-orig-full")
    semantic_transliteration = api.T.text(semantic_line, fmt="text-trans-full")
    if not semantic_cuneiform:
        raise ValueError(f"semantic line {semantic_line} rendered empty cuneiform")
    if not semantic_transliteration.strip():
        raise ValueError(f"semantic line {semantic_line} rendered empty transliteration")

    return {
        "schema_version": SCHEMA_VERSION,
        "line_node": semantic_line,
        "semantic_slot": semantic_slot,
        "synthetic_slot": first_synthetic,
        "synthetic_slot_count": len(synthetic_slots),
        "synthetic_slot_utf8": synthetic_utf8,
        "synthetic_slot_cuneiform": synthetic_cuneiform,
        "synthetic_slot_transliteration": synthetic_transliteration,
        "semantic_line_cuneiform": semantic_cuneiform,
        "semantic_line_transliteration": semantic_transliteration,
        # Backwards-compatible aliases used by the original issue-69 fixture probe.
        "cuneiform": semantic_cuneiform,
        "transliteration": semantic_transliteration,
    }


def _csv_values(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split(",") if item)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    profile = sub.add_parser("profile")
    profile.add_argument("tf_root", type=Path)
    profile.add_argument("--exclude", default="")

    feature_bytes = sub.add_parser("feature-bytes")
    feature_bytes.add_argument("tf_root", type=Path)
    feature_bytes.add_argument(
        "--features",
        default=",".join(DEFAULT_HEAVY_FEATURES),
    )

    census = sub.add_parser("census")
    census.add_argument("tf_root", type=Path)
    census.add_argument("--candidates", default=",".join(BHSA_NONE_VALUES))

    prototype = sub.add_parser("prototype")
    prototype.add_argument("source", type=Path)
    prototype.add_argument("target", type=Path)

    probe = sub.add_parser("probe")
    probe.add_argument("tf_root", type=Path)

    browser = sub.add_parser("browser")
    browser.add_argument("tf_root", type=Path)

    args = parser.parse_args()
    if args.command == "profile":
        result = profile_advanced_app(
            args.tf_root,
            excluded_features=_csv_values(args.exclude),
        )
        print(json.dumps(result, sort_keys=True))
    elif args.command == "feature-bytes":
        print(
            json.dumps(
                measure_feature_bytes(
                    args.tf_root,
                    features=_csv_values(args.features),
                ),
                sort_keys=True,
            )
        )
    elif args.command == "census":
        print(
            json.dumps(
                census_exact_values(
                    args.tf_root,
                    candidates=_csv_values(args.candidates),
                ),
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    elif args.command == "prototype":
        inject_prototype_formats(args.source, args.target)
    elif args.command == "browser":
        # Text-Fabric writes informational and browser diagnostics to stdout.
        # Keep the research artifact channel machine-readable by forwarding only
        # those diagnostics to stderr and reserving stdout for one JSON document.
        with redirect_stdout(sys.stderr):
            result = probe_browser_routes(args.tf_root)
        print(json.dumps(result, sort_keys=True))
    else:
        print(json.dumps(probe_text_formats(args.tf_root), sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
