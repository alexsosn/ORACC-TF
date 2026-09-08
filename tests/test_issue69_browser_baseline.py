"""Issue #69 RED contract for the real Text-Fabric browser baseline."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from oracc_tf import corpus, loader, metadata


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_issue69_tf_app.py"


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


def test_issue69_probes_supported_tf_browser_routes(tmp_path: Path) -> None:
    module = _research_module()
    tf_root = tmp_path / "tf"
    _build_fixture(tf_root)

    result = module.probe_browser_routes(tf_root)

    assert result["schema_version"] == 1
    assert result["browser_setup"] is True
    assert result["routes"] == {
        "/": 200,
        "/passage": 200,
        "/query": 200,
        "/export": 200,
    }
    assert result["responses_nonempty"] == {
        "/": True,
        "/passage": True,
        "/query": True,
        "/export": True,
    }
