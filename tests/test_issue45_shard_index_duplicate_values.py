"""Issue #45 adversarial review: nested duplicate JSON keys must fail closed."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_duplicates", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "payload",
    [
        # Duplicate inside a keys[] entry would otherwise change the semantic
        # digest while silently discarding source information.
        '{"type":"index","keys":[{"key":"a","count":"1","count":"2","instances":[]}]}',
        # Metadata is retained in every shard, so duplicate nested metadata must
        # not be normalized silently either.
        '{"type":"index","metadata":{"label":"first","label":"second"},'
        '"keys":[{"key":"a","count":"1","instances":[]}]}',
        # The same rule applies recursively inside a key entry.
        '{"type":"index","keys":[{"key":"a","nested":{"x":1,"x":2},'
        '"count":"1","instances":[]}]}',
    ],
)
def test_duplicate_keys_inside_streamed_values_fail_closed(tmp_path, payload):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    src.write_text(payload, encoding="utf-8")

    with pytest.raises(Exception, match="(?i)duplicate"):
        module.split(src, outdir, max_mb=1)

    assert not outdir.exists()
