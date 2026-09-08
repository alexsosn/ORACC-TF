"""Issue #69 adversarial rendering-evidence regression.

The real-corpus measurement originally selected an empty structural line, so both
candidate formats returned ``""`` while the workflow still passed.  Research is
not complete until the probe separately demonstrates that a technical synthetic
slot is visually empty and that a semantic line renders actual source text.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from oracc_tf import corpus, loader, metadata


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_issue69_tf_app.py"


def _research_module():
    spec = importlib.util.spec_from_file_location("research_issue69_tf_app_evidence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _edition_with_empty_then_semantic_line() -> loader.Edition:
    text_id = "QEVIDENCE"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
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
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.2",
                        "label": "2",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="test/app",
        text_id=text_id,
        path=Path("/test/app/corpusjson/QEVIDENCE.json"),
        doc=doc,
        word_count=1,
    )


def test_issue69_probe_separates_blank_synthetic_anchor_from_semantic_text(tmp_path: Path) -> None:
    module = _research_module()
    source = tmp_path / "source"
    prototype = tmp_path / "prototype"
    corpus.build_tf(
        source,
        editions=(_edition_with_empty_then_semantic_line(),),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    module.inject_prototype_formats(source, prototype)

    result = module.probe_text_formats(prototype)

    assert result["synthetic_slot_count"] == 1
    assert result["synthetic_slot_utf8"] is None
    assert result["synthetic_slot_cuneiform"] == ""
    assert result["synthetic_slot_transliteration"] == ""
    assert result["semantic_line_cuneiform"] == "𒀀"
    assert result["semantic_line_transliteration"].strip() == "a"
