"""Issue #58 research gate: reproduce the exact OBABAT source census."""

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import warnings

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_obabat_snapshot.py"
spec = spec_from_file_location("research_obabat_snapshot", SCRIPT)
module = module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


@pytest.mark.corpus
def test_obabat_research_snapshot_gate():
    report = module.build_report()

    # Emit the first exact overlap/unmatched census into CI's warnings summary;
    # this warning is removed once the measured values are frozen in research.
    warnings.warn(
        "ISSUE58_RESEARCH_CENSUS="
        + json.dumps(report, sort_keys=True, ensure_ascii=False),
        stacklevel=1,
    )

    assert report["source"]["corpus_blob_sha"] == "f3dae9f3e713683ebc4c49075ff8475a44e3b1f8"
    assert report["source"]["document_source_metadata_mismatches"] == []
    assert report["source"]["textid_mismatches"] == []
    assert report["membership"] == {
        "corpus_members": 121,
        "corpusjson_files": 121,
        "overlap_ids": 86,
        "not_in_pinned_nino_ids": 35,
    }
    assert report["catalogue"]["missing_from_catalogue"] == []
    assert report["catalogue"]["catalogue_only"] == []
    assert report["catalogue"]["id_text_mismatches"] == []
    assert report["catalogue"]["project_mismatches"] == []
    assert report["all"]["counts"]["documents"] == 121
    assert report["all"]["counts"]["words"] == 9517
    assert report["all"]["dtypes"]["line-start"] == 3242
    assert report["all"]["counts"].get("utf8", 0) == 0
