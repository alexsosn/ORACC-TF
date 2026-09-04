"""P-002 Phase 1 — upstream policy and deterministic lock contract."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

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


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        for path, body in files.items():
            archive.writestr(path, body)
    return out.getvalue()


def _fixture_archive() -> tuple[bytes, bytes]:
    text = b'{"textid":"Q000001","cdl":[]}'
    metadata = json.dumps(
        {
            "type": "metadata",
            "project": "riao/ria1",
            "license": "This data is released under the CC0 license",
            "UTC-timestamp": "2026-08-07T11:59:00",
        },
        separators=(",", ":"),
    ).encode()
    return (
        _zip_bytes(
            {
                "riao/ria1/metadata.json": metadata,
                "riao/ria1/catalogue.json": b"{}",
                "riao/ria1/corpusjson/Q000001.json": text,
            }
        ),
        text,
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


def test_archive_inspection_derives_lock_from_archive_bytes():
    body, text = _fixture_archive()
    record = upstream.inspect_archive_bytes(
        "riao-ria1",
        body,
        etag='"abc"',
        last_modified="2026-08-07T12:00:00Z",
    )
    assert record.name == "riao-ria1"
    assert record.sha256 == upstream.sha256_bytes(body)
    assert record.bytes == len(body)
    assert record.oracc_utc_timestamp == "2026-08-07T11:59:00"
    assert record.licence == "This data is released under the CC0 license"
    assert record.extract_paths == ("riao/ria1/",)
    assert record.text_ids_sha256 == upstream.text_ids_digest(
        {"Q000001": upstream.sha256_bytes(text)}
    )


def test_archive_inspection_rejects_non_zip_and_mismatched_project():
    with pytest.raises(upstream.UpstreamModelError, match="valid ZIP"):
        upstream.inspect_archive_bytes("riao-ria1", b"404", etag=None, last_modified=None)

    body, _ = _fixture_archive()
    wrong = body.replace(b"riao/ria1", b"rinap/r1 ")
    with pytest.raises(upstream.UpstreamModelError):
        upstream.inspect_archive_bytes("riao-ria1", wrong, etag=None, last_modified=None)


def test_snapshot_diff_is_non_destructive_and_enumerates_every_file(tmp_path: Path):
    body, _ = _fixture_archive()
    root = tmp_path / "data"
    (root / "riao/ria1/corpusjson").mkdir(parents=True)
    (root / "riao/ria1/metadata.json").write_bytes(
        json.dumps(
            {
                "type": "metadata",
                "project": "riao/ria1",
                "license": "This data is released under the CC0 license",
                "UTC-timestamp": "2026-08-07T11:59:00",
            },
            separators=(",", ":"),
        ).encode()
    )
    (root / "riao/ria1/catalogue.json").write_bytes(b'{"old":true}')
    (root / "riao/ria1/corpusjson/Q000002.json").write_bytes(b"old")

    diff = upstream.compare_archive_bytes_to_tree(body, root)
    assert diff.added == ("riao/ria1/corpusjson/Q000001.json",)
    assert diff.removed == ("riao/ria1/corpusjson/Q000002.json",)
    assert diff.modified == ("riao/ria1/catalogue.json",)
    assert (root / "riao/ria1/catalogue.json").read_bytes() == b'{"old":true}'
