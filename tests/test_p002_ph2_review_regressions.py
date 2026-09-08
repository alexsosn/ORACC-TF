"""Adversarial regression contracts for PH2 discovery state semantics."""

from __future__ import annotations

import importlib


def api():
    return importlib.import_module("oracc_tf.upstream_discovery")


def test_sha256_text_case_does_not_trigger_false_rebuild() -> None:
    module = api()
    locked = module.ArchiveFingerprint(
        name="riao-ria1",
        sha256="A" * 64,
        bytes=123,
        etag='"old"',
        last_modified=None,
    )
    downloaded = module.DownloadedArchive(
        name="riao-ria1",
        sha256="a" * 64,
        bytes=123,
        etag='"new"',
        last_modified=None,
    )

    change = module.reconcile_download(locked, downloaded)

    assert change.kind == "metadata-only"
    assert change.requires_rebuild is False
    assert change.sha256 == "a" * 64


def test_archive_shared_by_active_datasets_is_polled_once() -> None:
    module = api()
    manifest = """
[first]
archives = ["shared-source", "first-only"]

[second]
archives = ["shared-source", "second-only"]
"""

    assert module.tracked_archives_from_datasets(manifest) == (
        "shared-source",
        "first-only",
        "second-only",
    )
