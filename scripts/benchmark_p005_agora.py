#!/usr/bin/env python3
"""Measure Agora GitStore acquisition for one pinned TF repository root.

The P-005 CI gate serves local bare repositories over loopback so Linux
``/proc/net/dev`` provides protocol-byte accounting without mutable public-
network noise. Cold acquisition and warm/no-change checks are reported
separately.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from agora_context_fabric.gitstore import GitStore
from oracc_tf import corpus


def directory_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file() and not p.is_symlink())


def interface_bytes(interface: str = "lo", proc_net_dev: Path = Path("/proc/net/dev")) -> int:
    for line in proc_net_dev.read_text(encoding="utf-8").splitlines():
        name, sep, payload = line.partition(":")
        if sep and name.strip() == interface:
            fields = payload.split()
            if len(fields) < 16:
                raise RuntimeError(f"unexpected /proc/net/dev row for {interface!r}")
            return int(fields[0]) + int(fields[8])
    raise RuntimeError(f"network interface {interface!r} not found in {proc_net_dev}")


def elapsed_and_network(fn, *, interface: str) -> tuple[object, float, int]:
    before_bytes = interface_bytes(interface)
    started = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - started
    after_bytes = interface_bytes(interface)
    return result, elapsed, max(0, after_bytes - before_bytes)


def benchmark(
    *,
    repository: str,
    ref: str,
    tf_path: str,
    cache_dir: Path,
    cache_key: str,
    label: str,
    interface: str = "lo",
) -> dict[str, object]:
    store = GitStore(cache_dir, snapshot_soft_limit_bytes=0, min_free_bytes=0)

    repo_obj, metadata_seconds, metadata_network_bytes = elapsed_and_network(
        lambda: store.ensure_metadata(repository, cache_key=cache_key, ref=ref),
        interface=interface,
    )
    repo = Path(repo_obj)

    started = time.perf_counter()
    roots = store.dataset_roots(repo)
    tree_seconds = time.perf_counter() - started
    if tf_path not in roots:
        raise RuntimeError(f"requested TF path {tf_path!r} not discovered; roots={roots!r}")

    snapshot_obj, materialize_seconds, materialize_network_bytes = elapsed_and_network(
        lambda: store.materialize(repo, tf_path, ref),
        interface=interface,
    )
    snapshot = Path(snapshot_obj)

    started = time.perf_counter()
    api = corpus.load_tf(snapshot)
    load_seconds = time.perf_counter() - started
    if api.F.otype.maxSlot < 1:
        raise RuntimeError("materialized Text-Fabric dataset has no slots")

    _, warm_metadata_seconds, warm_metadata_network_bytes = elapsed_and_network(
        lambda: store.ensure_metadata(repository, cache_key=cache_key, ref=ref),
        interface=interface,
    )
    _, warm_materialize_seconds, warm_materialize_network_bytes = elapsed_and_network(
        lambda: store.materialize(repo, tf_path, ref),
        interface=interface,
    )

    return {
        "schema_version": 1,
        "label": label,
        "repository": repository,
        "requested_ref": ref,
        "resolved_revision": store.selected_revision(repo),
        "tf_path": tf_path,
        "discovered_roots": len(roots),
        "metadata_network_bytes": metadata_network_bytes,
        "materialize_network_bytes": materialize_network_bytes,
        "total_network_bytes": metadata_network_bytes + materialize_network_bytes,
        "warm_metadata_network_bytes": warm_metadata_network_bytes,
        "warm_materialize_network_bytes": warm_materialize_network_bytes,
        "warm_total_network_bytes": warm_metadata_network_bytes + warm_materialize_network_bytes,
        "metadata_seconds": round(metadata_seconds, 6),
        "tree_seconds": round(tree_seconds, 6),
        "materialize_seconds": round(materialize_seconds, 6),
        "load_seconds": round(load_seconds, 6),
        "warm_metadata_seconds": round(warm_metadata_seconds, 6),
        "warm_materialize_seconds": round(warm_materialize_seconds, 6),
        "metadata_cache_bytes": directory_size(repo),
        "snapshot_bytes": directory_size(snapshot),
        "total_cache_bytes": directory_size(cache_dir),
        "max_slot": api.F.otype.maxSlot,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--tf-path", required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--cache-key", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--interface", default="lo")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = benchmark(
        repository=args.repository,
        ref=args.ref,
        tf_path=args.tf_path,
        cache_dir=args.cache_dir,
        cache_key=args.cache_key,
        label=args.label,
        interface=args.interface,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
