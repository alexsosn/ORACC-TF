"""Issue #58 research gate: reproduce the exact OBABAT source census."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_obabat_snapshot.py"
FROZEN = ROOT / "docs" / "research" / "issue-58-obabat-snapshot.json"
spec = spec_from_file_location("research_obabat_snapshot", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


@pytest.mark.corpus
def test_obabat_research_snapshot_gate():
    report = module.build_report()
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))

    assert report == frozen
    assert report["source"]["corpus_blob_sha"] == "f3dae9f3e713683ebc4c49075ff8475a44e3b1f8"
    assert report["membership"] == {
        "corpus_members": 121,
        "corpusjson_files": 121,
        "overlap_ids": 86,
        "not_in_pinned_nino_ids": 35,
    }
    assert report["catalogue"]["designation_collision_count"] == 0
    assert report["all"]["counts"]["words"] == 9517
    assert report["all"]["dtypes"]["line-start"] == 3242
    assert report["all"]["counts"].get("utf8", 0) == 0
