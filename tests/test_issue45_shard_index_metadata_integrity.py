"""Issue #45 adversarial review: metadata participates in integrity checks."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


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


def _split_fixture(tmp_path, *, mapping=None):
    src = tmp_path / "index.json"
    outdir = tmp_path / "shards"
    _write_source(src, mapping=mapping)
    module.split(src, outdir, max_mb=1)
    return src, outdir


def test_verify_rejects_key_shard_metadata_drift(tmp_path):
    _src, outdir = _split_fixture(tmp_path)
    manifest = json.loads((outdir / module.MANIFEST).read_text(encoding="utf-8"))
    label = manifest["split"]["shards"][0]
    shard_path = outdir / f"{module.KEYS_PREFIX}{label}.json"
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    shard["project"] = "tampered-project"
    shard_path.write_text(json.dumps(shard), encoding="utf-8")

    with pytest.raises(module.IndexFormatError, match="metadata.*manifest"):
        module.verify(outdir, quiet=True)


def test_verify_rejects_map_shard_metadata_drift(tmp_path):
    _src, outdir = _split_fixture(tmp_path, mapping={"raw": "norm"})
    map_path = outdir / module.MAP_FILE
    shard = json.loads(map_path.read_text(encoding="utf-8"))
    shard["license"] = "tampered-license"
    map_path.write_text(json.dumps(shard), encoding="utf-8")

    with pytest.raises(module.IndexFormatError, match="metadata.*manifest"):
        module.verify(outdir, quiet=True)


def test_verify_against_rejects_source_metadata_drift(tmp_path):
    src, outdir = _split_fixture(tmp_path, mapping={"raw": "norm"})
    changed = tmp_path / "changed.json"
    _write_source(changed, project="different-project", mapping={"raw": "norm"})

    # Payload digests are identical; provenance/metadata is not.
    assert module.verify(outdir, against=changed, quiet=True) == 1


def test_duplicate_manifest_fields_fail_closed(tmp_path):
    _src, outdir = _split_fixture(tmp_path)
    manifest_path = outdir / module.MANIFEST
    text = manifest_path.read_text(encoding="utf-8")
    manifest_path.write_text(
        text.replace("{", '{"project":"tampered",', 1), encoding="utf-8"
    )

    with pytest.raises(Exception, match="(?i)duplicate"):
        module.verify(outdir, quiet=True)


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda split: split.update(shards=["a/../../../outside"]), "shard"),
        (lambda split: split.update(shards=["a", "a"]), "duplicate|shard"),
        (lambda split: split.update(shards="a"), "shard|list"),
        (lambda split: split.update(has_map="false"), "has_map|boolean"),
    ],
)
def test_malformed_manifest_split_schema_fails_before_path_use(tmp_path, mutate, message):
    _src, outdir = _split_fixture(tmp_path)
    manifest_path = outdir / module.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutate(manifest["split"])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(module.IndexFormatError, match=f"(?i)({message})"):
        module.verify(outdir, quiet=True)
