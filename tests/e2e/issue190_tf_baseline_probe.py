"""Issue #190: comparable raw Text-Fabric full corpus load on exact release.

Runs as a separate process and venv from Context-Fabric. Both load all the
original TF features; the report compares process high-water marks but does
not claim equivalent browser functions or whole-machine memory footprints.
"""
from __future__ import annotations

import json
from pathlib import Path
import resource
from time import monotonic

from tf.fabric import Fabric

ROOT = Path("/tmp/issue190-release")
out = ROOT / "raw-tf-baseline.json"
paths = [
    p.parent for p in (ROOT / "unpacked").rglob("otext.tf")
    if (p.parent / "otype.tf").is_file()
]
assert len(paths) == 1, paths
root = paths[0]

start = monotonic()
fabric = Fabric(locations=str(root), silent="deep")
fabric_init_seconds = monotonic() - start
before_load_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
api = fabric.loadAll(silent="deep")
assert api, "Text-Fabric could not load release"
load_seconds = monotonic() - start
after_load_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
words = api.F.otype.s("word")
docs = api.F.otype.s("document")
translations = api.F.otype.s("translation_unit")
assert len(words) == 320975 and len(docs) == 2078 and len(translations) == 6792
data = {
    "tool": "text-fabric==13.1.2",
    "source": "public v1.0.0 SHA256-verified corpus",
    "tf_root": str(root),
    "fabric_init_seconds": round(fabric_init_seconds, 3),
    "load_all_seconds": round(load_seconds, 3),
    "rss_before_load_kb": before_load_kb,
    "rss_after_load_kb": after_load_kb,
    "word_nodes": len(words),
    "document_nodes": len(docs),
    "translation_unit_nodes": len(translations),
    "slot_type": api.F.otype.slotType,
}
out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print("RAW TF FULL CORPUS BASELINE", json.dumps(data, sort_keys=True), flush=True)
