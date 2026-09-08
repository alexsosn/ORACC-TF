"""Adversarial regression contracts for PH2 discovery state semantics."""

from __future__ import annotations

import importlib

import pytest


INDEX = "https://oracc.museum.upenn.edu/json/"


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


def test_matching_weak_etag_never_authorizes_unchanged() -> None:
    module = api()
    locked = module.ArchiveFingerprint(
        name="riao-ria1",
        sha256="a" * 64,
        bytes=123,
        etag='W/"same"',
        last_modified=None,
    )
    current = module.head_from_response(
        200,
        {"ETag": 'W/"same"', "Content-Length": "123"},
    )

    decision = module.decide_probe(locked, current)

    assert decision.action == "download-required"
    assert decision.requires_download is True


@pytest.mark.parametrize(
    "href",
    [
        "https://evil.invalid/riao-ria1.zip",
        "//evil.invalid/riao-ria1.zip",
        "../riao-ria1.zip",
    ],
)
def test_archive_inventory_rejects_zip_links_outside_listing_boundary(href: str) -> None:
    module = api()

    with pytest.raises(module.UpstreamInventoryError):
        module.parse_archive_inventory(f'<a href="{href}">archive</a>', INDEX)


def test_archive_inventory_accepts_same_directory_absolute_link() -> None:
    module = api()

    entries = module.parse_archive_inventory(
        '<a href="https://oracc.museum.upenn.edu/json/riao-ria1.zip">archive</a>',
        INDEX,
    )

    assert len(entries) == 1
    assert entries[0].url == "https://oracc.museum.upenn.edu/json/riao-ria1.zip"
