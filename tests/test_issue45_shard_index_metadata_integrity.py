"""Issue #45 adversarial review: shard metadata participates in integrity checks."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_metadata", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_verify_rejects_key_shard_metadata_drift(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    src.write_text(
        json.dumps(
            {
                "type": "index",
                "project": "fixture",
                "license": "CC0",
                "keys": [{"key": "alpha", "count": "1", "instances": []}],
            }
        ),
        encoding="utf-8",
    )
    module.split(src, outdir, max_mb=1)

    manifest = json.loads((outdir / module.MANIFEST).read_text(encoding="utf-8"))
    label = manifest["split"]["shards"][0]
    shard_path = outdir / f"{module.KEYS_PREFIX}{label}.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["project"] = "tampered-project"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    # Key payloads and their digest are unchanged, so a digest-only verifier
    # would incorrectly accept this corrupted standalone shard.
    assert module.verify(outdir, quiet=True) == 1
