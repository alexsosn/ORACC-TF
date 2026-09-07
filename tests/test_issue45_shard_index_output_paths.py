"""Issue #45 adversarial review: output paths must not destroy files."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_paths", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _write_source(path: Path) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "index",
                "project": "fixture",
                "keys": [{"key": "a", "count": "1", "instances": []}],
            }
        ),
        encoding="utf-8",
    )
    return path.read_bytes()


def test_split_rejects_source_file_as_output_directory_without_mutation(tmp_path):
    src = tmp_path / "index.json"
    original = _write_source(src)

    with pytest.raises(Exception, match="(?i)(output|directory|source|path)"):
        module.split(src, src, max_mb=1)

    assert src.is_file()
    assert src.read_bytes() == original


def test_split_rejects_existing_regular_file_output_without_mutation(tmp_path):
    src = tmp_path / "index.json"
    out = tmp_path / "existing.txt"
    _write_source(src)
    out.write_bytes(b"sentinel")

    with pytest.raises(Exception, match="(?i)(output|directory|path)"):
        module.split(src, out, max_mb=1)

    assert out.is_file()
    assert out.read_bytes() == b"sentinel"


def test_split_rejects_output_directory_that_contains_source(tmp_path):
    outdir = tmp_path / "data"
    src = outdir / "index.json"
    original = _write_source(src)

    with pytest.raises(Exception, match="(?i)(output|directory|source|contain|path)"):
        module.split(src, outdir, max_mb=1)

    assert src.is_file()
    assert src.read_bytes() == original


def test_successful_split_preserves_unrelated_existing_files_and_drops_stale_shards(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    _write_source(src)
    outdir.mkdir()
    (outdir / "notes.txt").write_text("keep me", encoding="utf-8")
    (outdir / "keys-z.json").write_text("stale", encoding="utf-8")

    module.split(src, outdir, max_mb=1)

    assert (outdir / "notes.txt").read_text(encoding="utf-8") == "keep me"
    assert not (outdir / "keys-z.json").exists()
    manifest = json.loads((outdir / module.MANIFEST).read_text(encoding="utf-8"))
    assert manifest["split"]["shards"] == ["a"]
    assert module.verify(outdir) == 0


def test_dry_run_does_not_create_missing_output_parent(tmp_path, capsys):
    src = tmp_path / "index.json"
    _write_source(src)
    outdir = tmp_path / "missing-parent" / "shards"
    assert not outdir.parent.exists()

    module.split(src, outdir, max_mb=1, dry_run=True)

    assert "dry run, nothing written" in capsys.readouterr().out
    assert not outdir.parent.exists()


def test_join_rejects_managed_shard_as_destination_without_mutation(tmp_path):
    """Joining must never be able to overwrite a file it is reading."""
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    _write_source(src)
    module.split(src, outdir, max_mb=1)

    manifest = json.loads((outdir / module.MANIFEST).read_text(encoding="utf-8"))
    label = manifest["split"]["shards"][0]
    managed = outdir / f"{module.KEYS_PREFIX}{label}.json"
    original = managed.read_bytes()

    with pytest.raises(Exception, match="(?i)(output|destination|shard|input|path)"):
        module.join(outdir, managed)

    assert managed.read_bytes() == original
    assert module.verify(outdir, quiet=True) == 0
