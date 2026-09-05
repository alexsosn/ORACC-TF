"""Issue #45 adversarial review: metadata participates in integrity checks."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_metadata", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def _write_source(path: Path, *, project="fixture", mapping=None):
    doc = {
        "type": "index",
        "project": project,
        "license": "CC0",
        "keys": [{"key": "alpha", "count": "1", "instances": []}],
    }
    if mapping is not None:
        doc["map"] = mapping
    path.write_text(json.dumps(doc), encoding="utf-8")


def test_verify_rejects_key_shard_metadata_drift(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    _write_source(src)
    module.split(src, outdir, max_mb=1)

    manifest = json.loads((outdir / module.MANIFEST).read_text(encoding="utf-8"))
    label = manifest["split"]["shards"][0]
    shard_path = outdir / f"{module.KEYS_PREFIX}{label}.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["project"] = "tampered-project"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    assert module.verify(outdir, quiet=True) == 1


def test_verify_rejects_map_shard_metadata_drift(tmp_path):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    _write_source(src, mapping={"raw": "norm"})
    module.split(src, outdir, max_mb=1)

    map_path = outdir / module.MAP_FILE
    shard = json.loads(map_path.read_text(encoding="utf-8"))
    shard["license"] = "tampered-license"
    map_path.write_text(json.dumps(shard), encoding="utf-8")

    assert module.verify(outdir, quiet=True) == 1


def test_verify_against_rejects_source_metadata_drift(tmp_path):
    src = tmp_path / "index.json"
    changed = tmp_path / "changed.json"
    outdir = tmp_path / "shards"
    _write_source(src, project="fixture", mapping={"raw": "norm"})
    module.split(src, outdir, max_mb=1)

    _write_source(changed, project="different-project", mapping={"raw": "norm"})

    # Payload digests are identical; provenance/metadata is not.
    assert module.verify(outdir, against=changed, quiet=True) == 1
