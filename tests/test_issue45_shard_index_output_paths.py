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
