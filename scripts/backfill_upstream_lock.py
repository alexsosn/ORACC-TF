#!/usr/bin/env python3
"""Backfill the Phase-1 ORACC lock and compare current ZIPs with committed data.

This command never modifies data/. Each tracked archive is fetched twice,
serially, and must have stable bytes across both fetches before it contributes
to the generated lock. The output lock describes the fetched upstream bytes;
the report explicitly enumerates any drift from the committed extraction.
"""

from __future__ import annotations

import argparse
from datetime import timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from oracc_tf import releases, upstream


class BackfillError(RuntimeError):
    """A live provenance fact could not be established safely."""


def _iso_last_modified(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as exc:
        raise BackfillError(f"invalid Last-Modified header: {value!r}") from exc
    if parsed.tzinfo is None:
        raise BackfillError(f"Last-Modified has no timezone: {value!r}")
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(url: str, user_agent: str, timeout: int) -> tuple[bytes, str | None, str | None]:
    request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/zip"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured canonical URL
            body = response.read()
            etag = response.headers.get("ETag")
            last_modified = _iso_last_modified(response.headers.get("Last-Modified"))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise BackfillError(f"cannot fetch {url}: {exc}") from exc
    if not body.startswith(b"PK"):
        raise BackfillError(f"{url} did not return a ZIP body")
    return body, etag, last_modified


def _stable_fetch(url: str, user_agent: str, timeout: int) -> tuple[bytes, str | None, str | None]:
    first, _, _ = _fetch(url, user_agent, timeout)
    second, etag, last_modified = _fetch(url, user_agent, timeout)
    if upstream.sha256_bytes(first) != upstream.sha256_bytes(second) or len(first) != len(second):
        raise BackfillError(f"upstream bytes changed between consecutive fetches: {url}")
    return second, etag, last_modified


def run(repo_root: Path, output_dir: Path, timeout: int = 90) -> tuple[Path, Path]:
    config = upstream.load_config(repo_root / "upstream.toml")
    datasets = releases.load_datasets(repo_root / "datasets.toml")
    tracked = releases.tracked_archives(datasets)
    if len(tracked) != 11:
        raise BackfillError(f"Phase 1 requires exactly 11 active archives, found {len(tracked)}")

    records: list[upstream.ArchiveLock] = []
    archive_report: dict[str, object] = {}
    for name in sorted(tracked):
        url = config.index.rstrip("/") + f"/{name}.zip"
        expected = f"http://oracc.museum.upenn.edu/json/{name}.zip"
        if url != expected:
            raise BackfillError(f"non-canonical configured archive URL: {url}")
        body, etag, last_modified = _stable_fetch(url, config.user_agent, timeout)
        record = upstream.inspect_archive_bytes(
            name, body, etag=etag, last_modified=last_modified
        )
        diff = upstream.compare_archive_bytes_to_tree(body, repo_root / "data")
        records.append(record)
        archive_report[name] = {
            "sha256": record.sha256,
            "bytes": record.bytes,
            "oracc_utc_timestamp": record.oracc_utc_timestamp,
            "licence": record.licence,
            "extract_paths": list(record.extract_paths),
            "snapshot_exact": diff.exact,
            "added": list(diff.added),
            "removed": list(diff.removed),
            "modified": list(diff.modified),
        }
        print(
            f"{name}: sha256={record.sha256} bytes={record.bytes} "
            f"exact={diff.exact} +{len(diff.added)} -{len(diff.removed)} ~{len(diff.modified)}",
            flush=True,
        )

    lock_bytes = upstream.serialize_lock(records, allowed_archives=tracked)
    exact = sum(bool(value["snapshot_exact"]) for value in archive_report.values())  # type: ignore[index]
    report = {
        "tracked_archives": len(tracked),
        "snapshot_exact_archives": exact,
        "snapshot_drift_archives": len(tracked) - exact,
        "archives": archive_report,
    }
    report_bytes = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()

    output_dir.mkdir(parents=True, exist_ok=True)
    lock_path = output_dir / "upstream.lock.json"
    report_path = output_dir / "upstream-backfill-report.json"
    lock_path.write_bytes(lock_bytes)
    report_path.write_bytes(report_bytes)
    return lock_path, report_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--output-dir", type=Path, default=Path("backfill-output"))
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    run(args.repo_root.resolve(), args.output_dir.resolve(), args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
