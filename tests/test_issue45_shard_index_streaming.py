"""Issue #45: bounded-memory and fail-closed shard_index contracts."""

from importlib.util import module_from_spec, spec_from_file_location
import hashlib
import json
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def write_index(path: Path, *, keys=None, mapping_marker="absent", metadata=None):
    doc = {
        "type": "index",
        "project": "fixture",
        **(metadata or {}),
        "keys": [] if keys is None else keys,
    }
    if mapping_marker != "absent":
        doc["map"] = mapping_marker
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def sample_keys():
    return [
        {"key": "alpha", "count": "1", "instances": ["P000001.1"]},
        {"key": "beta", "count": "2", "instances": ["P000002.1", "P000002.2"]},
        {"key": "éclair", "count": "1", "instances": ["P000003.1"]},
        {"key": "", "count": "0", "instances": []},
    ]


def _forbid_large_json_load(monkeypatch, forbidden_paths):
    """Allow json.load for the tiny manifest, but not corpus/shard payloads."""
    real_load = module.json.load
    forbidden = {str(Path(p).resolve()) for p in forbidden_paths}

    def guarded_load(fp, *args, **kwargs):
        name = getattr(fp, "name", None)
        if name is not None and str(Path(name).resolve()) in forbidden:
            raise AssertionError(f"whole-file json.load forbidden for {name}")
        return real_load(fp, *args, **kwargs)

    monkeypatch.setattr(module.json, "load", guarded_load)


def test_split_streams_source_instead_of_json_loading_whole_document(tmp_path, monkeypatch):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    write_index(
        src,
        keys=sample_keys(),
        mapping_marker={"𒀭": "DINGIR", "raw": "norm"},
        metadata={"nested": {"a": [1, 2, {"b": "c"}]}},
    )
    _forbid_large_json_load(monkeypatch, [src])

    module.split(src, outdir, max_mb=1)

    assert (outdir / module.MANIFEST).is_file()
    assert module.verify(outdir) == 0


def test_tiny_parser_chunks_preserve_escaped_unicode_and_nested_values(tmp_path, monkeypatch):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    joined = tmp_path / "joined.json"
    original = write_index(
        src,
        keys=[
            {
                "key": "ša𒀭",
                "count": "1",
                "instances": ['quoted " value \\ tail 😀'],
                "nested": {"list": [1, {"deep": "value"}]},
            }
        ],
        mapping_marker={"𒀭": 'DINGIR "quoted"'},
        metadata={"nested": {"unicode": "ṭuppu", "list": [1, 2, 3]}},
    )
    monkeypatch.setattr(module, "STREAM_CHUNK_CHARS", 7, raising=False)
    _forbid_large_json_load(monkeypatch, [src])

    module.split(src, outdir, max_mb=1)
    assert module.verify(outdir, against=src) == 0
    assert module.join(outdir, joined) == 0
    got = json.loads(joined.read_text(encoding="utf-8"))
    assert got == original


def test_verify_and_join_stream_shard_payloads(tmp_path, monkeypatch):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    joined = tmp_path / "joined.json"
    original = write_index(
        src,
        keys=sample_keys(),
        mapping_marker={"raw": "norm", "𒀭": "DINGIR"},
    )
    module.split(src, outdir, max_mb=1)

    payloads = [p for p in outdir.glob("*.json") if p.name != module.MANIFEST]
    _forbid_large_json_load(monkeypatch, [*payloads, src])

    assert module.verify(outdir, against=src) == 0
    assert module.join(outdir, joined) == 0
    got = json.loads(joined.read_text(encoding="utf-8"))
    assert got["keys"] == sorted(original["keys"], key=lambda e: module.bucket_of(e["key"]))
    assert got["map"] == original["map"]


def test_explicit_empty_map_round_trips_and_verifies(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    joined = tmp_path / "joined.json"
    write_index(src, keys=sample_keys(), mapping_marker={})

    module.split(src, outdir, max_mb=1)

    assert module.verify(outdir) == 0
    assert module.join(outdir, joined) == 0
    got = json.loads(joined.read_text(encoding="utf-8"))
    assert "map" in got
    assert got["map"] == {}


def test_absent_map_stays_absent_and_empty_keys_are_supported(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    joined = tmp_path / "joined.json"
    write_index(src, keys=[], mapping_marker="absent")

    module.split(src, outdir, max_mb=1)
    assert module.verify(outdir) == 0
    assert module.join(outdir, joined) == 0
    got = json.loads(joined.read_text(encoding="utf-8"))
    assert got["keys"] == []
    assert "map" not in got


def test_single_entry_larger_than_limit_fails_without_publishing_partial_output(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    huge = {"key": "aa", "count": "1", "instances": ["x" * 20_000]}
    write_index(src, keys=[huge])

    with pytest.raises(Exception, match="(?i)(limit|large|size|shard)"):
        module.split(src, outdir, max_mb=0.001)

    assert not outdir.exists()
    assert src.exists()


def test_duplicate_map_keys_fail_closed(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    src.write_text(
        '{"type":"index","keys":[{"key":"a","count":"1","instances":[]}],'
        '"map":{"dup":"first","dup":"second"}}',
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="(?i)duplicate.*map"):
        module.split(src, outdir, max_mb=1)

    assert not outdir.exists()


def test_duplicate_top_level_fields_fail_closed(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    src.write_text(
        '{"type":"index","type":"second",'
        '"keys":[{"key":"a","count":"1","instances":[]}]}',
        encoding="utf-8",
    )

    with pytest.raises(Exception, match="(?i)duplicate.*(top|field|type)"):
        module.split(src, outdir, max_mb=1)

    assert not outdir.exists()


def test_truncated_json_fails_without_partial_output(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    src.write_text(
        '{"type":"index","keys":[{"key":"a","instances":["unterminated',
        encoding="utf-8",
    )

    with pytest.raises(Exception):
        module.split(src, outdir, max_mb=1)

    assert not outdir.exists()


def test_failed_join_does_not_clobber_existing_destination(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    joined = tmp_path / "joined.json"
    write_index(src, keys=sample_keys(), mapping_marker={"raw": "norm"})
    module.split(src, outdir, max_mb=1)

    manifest_path = outdir / module.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["split"]["verify"]["keys_digest"] = "0" * 40
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    joined.write_text("sentinel", encoding="utf-8")

    assert module.join(outdir, joined) == 1
    assert joined.read_text(encoding="utf-8") == "sentinel"


def test_split_output_is_byte_deterministic(tmp_path):
    src = tmp_path / "index.json"
    left = tmp_path / "left"
    right = tmp_path / "right"
    write_index(
        src,
        keys=sample_keys(),
        mapping_marker={"z": "last", "a": "first"},
        metadata={"nested": {"unicode": "ša"}},
    )

    module.split(src, left, max_mb=1)
    module.split(src, right, max_mb=1)

    left_files = sorted(p.name for p in left.iterdir())
    right_files = sorted(p.name for p in right.iterdir())
    assert left_files == right_files
    for name in left_files:
        assert (left / name).read_bytes() == (right / name).read_bytes()


def test_v1_digest_semantics_are_preserved_exactly():
    entries = sample_keys()
    mapping = {"z": "last", "a": "first", "𒀭": "DINGIR"}

    legacy_entry_hashes = sorted(
        hashlib.sha1(
            json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        for entry in entries
    )
    legacy_keys_digest = hashlib.sha1("".join(legacy_entry_hashes).encode()).hexdigest()
    legacy_map_digest = hashlib.sha1(
        json.dumps(mapping, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()

    assert module.digest_keys(entries) == legacy_keys_digest
    assert module.digest_map(mapping) == legacy_map_digest


def test_replace_never_deletes_source_when_split_cannot_meet_size_limit(tmp_path, monkeypatch):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    huge = {"key": "aa", "count": "1", "instances": ["x" * 20_000]}
    write_index(src, keys=[huge])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "shard_index.py",
            "split",
            str(src),
            "-o",
            str(outdir),
            "--max-mb",
            "0.001",
            "--replace",
        ],
    )

    with pytest.raises((Exception, SystemExit)):
        module.main()

    assert src.exists()
