"""Issue #69 contracts for the real Text-Fabric browser baseline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from oracc_tf import corpus, loader, metadata


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_issue69_tf_app.py"
WORKFLOW = ROOT / ".github" / "workflows" / "issue69-app-research.yml"


def _research_module():
    spec = importlib.util.spec_from_file_location("research_issue69_browser", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_fixture(root: Path) -> None:
    text_id = "QBROWSER"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [{
            "node": "c",
            "type": "text",
            "id": f"{text_id}.U0",
            "cdl": [
                {"node": "d", "type": "surface", "ref": "", "label": ""},
                {
                    "node": "d",
                    "type": "line-start",
                    "ref": f"{text_id}.1",
                    "label": "1",
                },
                {
                    "node": "l",
                    "id": f"{text_id}.l1",
                    "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                },
            ],
        }],
    }
    edition = loader.Edition(
        subproject="test/browser",
        text_id=text_id,
        path=Path("/test/browser/corpusjson/QBROWSER.json"),
        doc=doc,
        word_count=1,
    )
    corpus.build_tf(
        root,
        editions=(edition,),
        metadata_index=metadata.MetadataIndex.empty(),
    )


def test_issue69_captures_current_generic_tf_browser_routes(tmp_path: Path) -> None:
    """Pin current no-app behavior instead of pretending the generic browser is healthy."""
    module = _research_module()
    tf_root = tmp_path / "tf"
    _build_fixture(tf_root)

    result = module.probe_browser_routes(tf_root)

    assert result["schema_version"] == 1
    assert result["browser_setup"] is True
    # Text-Fabric 13.1's vanilla data AdvancedApp has no corpus header. Passage
    # and query work, while root/export currently fail in app.header(). The
    # production app acceptance ticket is responsible for making all four 200.
    assert result["routes"] == {
        "/": 500,
        "/passage": 200,
        "/query": 200,
        "/export": 500,
    }
    assert result["responses_nonempty"] == {
        "/": True,
        "/passage": True,
        "/query": True,
        "/export": True,
    }


def test_issue69_research_workflow_records_real_corpus_browser_baseline() -> None:
    """The reproducible artifact must include browser behavior, not only fixture evidence."""
    payload = WORKFLOW.read_text(encoding="utf-8")
    assert "browser.json" in payload
    assert " browser /tmp/oracc-tf" in payload
    assert 'browser = json.loads((root / "browser.json").read_text())' in payload
    assert '"browser": browser' in payload
