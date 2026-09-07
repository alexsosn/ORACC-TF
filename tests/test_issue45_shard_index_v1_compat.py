"""Issue #45: existing v1 shard directories must remain readable unchanged."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "shard_index.py"
spec = spec_from_file_location("shard_index_issue45_v1", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_legacy_v1_pretty_shards_verify_and_join(tmp_path):
    indir = tmp_path / "legacy"
    indir.mkdir()
    joined = tmp_path / "legacy.json"
    entries = [
        {"key": "alpha", "count": "1", "instances": ["P000001.1"]},
        {"key": "beta", "count": "1", "instances": ["P000002.1"]},
        {"key": "éclair", "count": "1", "instances": ["P000003.1"]},
        {"key": "", "count": "0", "instances": []},
    ]
    mapping = {"raw": "norm", "𒀭": "DINGIR"}
    metadata = {"type": "index", "project": "fixture"}

    groups = {}
    for entry in entries:
        groups.setdefault(module.bucket_of(entry["key"]), []).append(entry)

    for label, group in groups.items():
        payload = {
            **metadata,
            "section": "keys",
            "shard": label,
            "keys": group,
        }
        (indir / f"{module.KEYS_PREFIX}{label}.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    (indir / module.MAP_FILE).write_text(
        json.dumps(
            {**metadata, "section": "map", "map": mapping},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        **metadata,
        "split": {
            "tool": "scripts/shard_index.py",
            "scheme": "legacy-v1-fixture",
            "source_file": "index.json",
            "shards": sorted(groups),
            "has_map": True,
            "note": "legacy fixture",
            "verify": {
                "keys_count": len(entries),
                "keys_digest": module.digest_keys(entries),
                "map_count": len(mapping),
                "map_digest": module.digest_map(mapping),
            },
        },
    }
    (indir / module.MANIFEST).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    assert module.verify(indir) == 0
    assert module.join(indir, joined) == 0
    got = json.loads(joined.read_text(encoding="utf-8"))
    assert module.digest_keys(got["keys"]) == module.digest_keys(entries)
    assert got["map"] == mapping
