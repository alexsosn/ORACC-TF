from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path("scripts/research_issue33_ninmed.py")
WORKFLOW = Path(".github/workflows/issue33-ninmed-research.yml")
REFERENCE_SHA = "9e413c41670117a96272ab2b2727ff9a1f9d3baf"


def load_harness():
    spec = spec_from_file_location("research_issue33_ninmed_cli", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_writes_canonical_report_from_explicit_pinned_inputs(tmp_path: Path) -> None:
    module = load_harness()
    oracc_dir = tmp_path / "oracc"
    reference_dir = tmp_path / "reference"
    tf_dir = tmp_path / "tf"
    output = tmp_path / "report.json"
    oracc_dir.mkdir()
    reference_dir.mkdir()
    tf_dir.mkdir()

    (oracc_dir / "P000001.json").write_text(
        '{"textid":"P000001","cdl":[{"node":"l","f":{"form":"a","cf":"A","pos":"N"}}]}',
        encoding="utf-8",
    )
    (reference_dir / "AO -- P000001.json").write_text(
        '{"cdliNumber":"P000001","text":{"allLines":[{"content":[{"type":"Word","cleanValue":"a","uniqueLemma":["A I"]}]}]}}',
        encoding="utf-8",
    )
    (tf_dir / "lemma.tf").write_text("@node\n", encoding="utf-8")

    result = module.main(
        [
            "--oracc-dir", str(oracc_dir),
            "--reference-dir", str(reference_dir),
            "--reference-tf-dir", str(tf_dir),
            "--oracc-revision", "oracc-pin",
            "--reference-revision", REFERENCE_SHA,
            "--oracc-licence", "CC0 verbatim",
            "--reference-repository-licence", "MIT verbatim",
            "--reference-source-provenance", "personal communication verbatim",
            "--output", str(output),
        ]
    )

    assert result == 0
    payload = output.read_bytes()
    report = json.loads(payload)
    assert report["pins"]["reference_revision"] == REFERENCE_SHA
    assert payload == module.canonical_report_bytes(report)


def test_workflow_is_read_only_exact_sha_and_uploads_report_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in text
    assert "repository: Nino-cunei/ninmed" in text
    assert f"ref: {REFERENCE_SHA}" in text
    assert "source/json/0.1" in text
    assert "tf/0.3" in text
    assert "docs/about.md" in text
    assert "LICENSE" in text
    assert "artifacts/issue33-ninmed-report.json" in text
    assert "actions/upload-artifact@v4" in text
    assert "complete.zip" not in text
    assert "tf-0.3.zip" not in text
