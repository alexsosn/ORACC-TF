"""P-002 Phase 1 — upstream policy and deterministic lock contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import upstream


SHA_A = "a" * 64
SHA_B = "b" * 64


def _record(name: str, sha: str, text_sha: str) -> upstream.ArchiveLock:
    return upstream.ArchiveLock(
        name=name,
        url=f"http://oracc.museum.upenn.edu/json/{name}.zip",
        sha256=sha,
        bytes=123,
        etag='"abc"',
        last_modified="2026-08-07T12:00:00Z",
        oracc_utc_timestamp="2026-08-07T11:59:00",
        licence="CC0",
        extract_paths=("riao/ria1/",),
        text_ids_sha256=text_sha,
    )


def test_upstream_policy_matches_phase_one_contract():
    config = upstream.load_config(Path("upstream.toml"))
    assert config.index == "http://oracc.museum.upenn.edu/json/"
    assert config.projects == "http://oracc.museum.upenn.edu/projects.json"
    assert config.user_agent == "ORACC-TF/1.0 (+https://github.com/alexsosn/ORACC-TF)"
    assert config.poll_cron == "daily"
    assert config.inventory_cron == "weekly"
    assert config.auto_publish is True
    assert config.max_parallel_fetch == 1


def test_text_ids_digest_is_order_independent_and_content_sensitive():
    first = upstream.text_ids_digest({"Q1": SHA_A, "Q2": SHA_B})
    reordered = upstream.text_ids_digest({"Q2": SHA_B, "Q1": SHA_A})
    changed = upstream.text_ids_digest({"Q1": SHA_B, "Q2": SHA_B})
    assert first == reordered
    assert first != changed


def test_lock_serialization_is_byte_stable_under_record_ordering():
    q1 = upstream.text_ids_digest({"Q1": SHA_A})
    q2 = upstream.text_ids_digest({"Q2": SHA_B})
    a = _record("riao-ria1", SHA_A, q1)
    b = _record("rinap-rinap1", SHA_B, q2)
    first = upstream.serialize_lock([a, b], allowed_archives={a.name, b.name})
    second = upstream.serialize_lock([b, a], allowed_archives={a.name, b.name})
    assert first == second
    assert first.endswith(b"\n")
    decoded = json.loads(first)
    assert list(decoded) == ["riao-ria1", "rinap-rinap1"]
    assert decoded["riao-ria1"]["sha256"] == SHA_A
    assert decoded["riao-ria1"]["text_ids_sha256"] == q1
    assert "fetched_at" not in decoded["riao-ria1"]


def test_lock_rejects_duplicate_and_out_of_scope_archives():
    digest = upstream.text_ids_digest({"Q1": SHA_A})
    record = _record("riao-ria1", SHA_A, digest)
    with pytest.raises(upstream.UpstreamModelError, match="duplicate archive"):
        upstream.serialize_lock([record, record], allowed_archives={record.name})
    with pytest.raises(upstream.UpstreamModelError, match="not tracked"):
        upstream.serialize_lock([record], allowed_archives={"rinap-rinap1"})


def test_archive_lock_rejects_malformed_identity_and_duplicate_paths():
    digest = upstream.text_ids_digest({"Q1": SHA_A})
    with pytest.raises(upstream.UpstreamModelError, match="SHA-256"):
        _record("riao-ria1", "bad", digest)
    with pytest.raises(upstream.UpstreamModelError, match="duplicate extract path"):
        upstream.ArchiveLock(
            name="riao-ria1",
            url="http://oracc.museum.upenn.edu/json/riao-ria1.zip",
            sha256=SHA_A,
            bytes=123,
            etag=None,
            last_modified=None,
            oracc_utc_timestamp="2026-08-07T11:59:00",
            licence="CC0",
            extract_paths=("riao/ria1/", "riao/ria1/"),
            text_ids_sha256=digest,
        )
