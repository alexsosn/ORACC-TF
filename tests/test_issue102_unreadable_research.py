from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path


SCRIPT = Path("scripts/research_issue102_unreadable.py")
WORKFLOW = Path(".github/workflows/issue102-unreadable-research.yml")
PINNED_REVISION = "dd6a657d15999288948a266c9eb17666f9790497"


def load_harness():
    assert SCRIPT.is_file(), "ISSUE-102 research census harness is not implemented yet"
    spec = spec_from_file_location("research_issue102_unreadable", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classifies_bad_bytes_without_filename_identity() -> None:
    module = load_harness()

    cases = [
        (b"", "empty-file"),
        (b"\xff", "invalid-utf8"),
        (b"{not-json", "invalid-json"),
        (b"[]", "non-object-json"),
        (b'{"type":"cdl","cdl":[]}', "missing-source-id"),
    ]
    for payload, kind in cases:
        result = module.classify_source_bytes(payload, relative_path="P999999.json")
        assert result["status"] == "hazard"
        assert result["kind"] == kind
        assert result["relative_path"] == "P999999.json"
        assert result["bytes"] == len(payload)
        assert len(result["sha256"]) == 64
        assert "source_id" not in result


def test_readable_identity_comes_from_json_not_filename() -> None:
    module = load_harness()
    payload = b'{"type":"cdl","textid":"Q000123","cdl":[]}'
    result = module.classify_source_bytes(
        payload,
        relative_path="misleading-Q999999.json",
    )

    assert result == {
        "status": "readable",
        "relative_path": "misleading-Q999999.json",
        "bytes": len(payload),
        "sha256": result["sha256"],
        "source_id": "Q000123",
    }
    assert len(result["sha256"]) == 64


def test_research_census_preserves_nonblank_embedded_identity_verbatim() -> None:
    module = load_harness()
    payload = b'{"type":"cdl","textid":" Q000123 ","cdl":[]}'

    result = module.classify_source_bytes(payload, relative_path="Q000123.json")

    assert result["status"] == "readable"
    assert result["source_id"] == " Q000123 "


def test_scan_repository_covers_every_corpusjson_tree_and_reconciles_totals(tmp_path: Path) -> None:
    module = load_harness()
    data = tmp_path / "data"
    first = data / "asbp" / "ninmed" / "corpusjson"
    second = data / "rinap" / "rinap1" / "corpusjson"
    ignored = data / "asbp" / "ninmed" / "catalogue.json"
    first.mkdir(parents=True)
    second.mkdir(parents=True)
    ignored.write_text("{}", encoding="utf-8")

    (first / "P1.json").write_text(
        json.dumps({"type": "cdl", "textid": "P000001", "cdl": []}), encoding="utf-8"
    )
    (first / "P2.json").write_bytes(b"")
    (second / "Q1.json").write_text(
        json.dumps({"type": "cdl", "textid": "Q000001", "cdl": []}), encoding="utf-8"
    )
    (second / "Q2.json").write_text("{broken", encoding="utf-8")

    report = module.scan_repository(data)

    assert report["schema_version"] == 1
    assert report["totals"] == {"source_members": 4, "readable": 2, "hazards": 2}
    assert tuple(tree["tree"] for tree in report["trees"]) == (
        "asbp/ninmed/corpusjson",
        "rinap/rinap1/corpusjson",
    )
    assert report["trees"][0]["counts"] == {
        "source_members": 2,
        "readable": 1,
        "hazards": 1,
    }
    assert report["trees"][0]["hazards"][0]["kind"] == "empty-file"
    assert report["trees"][1]["hazards"][0]["kind"] == "invalid-json"


def test_duplicate_embedded_identity_is_reported_per_tree_not_collapsed(tmp_path: Path) -> None:
    module = load_harness()
    tree = tmp_path / "data" / "fixture" / "corpusjson"
    tree.mkdir(parents=True)
    for name in ("a.json", "b.json"):
        (tree / name).write_text(
            json.dumps({"type": "cdl", "textid": "P000001", "cdl": []}), encoding="utf-8"
        )

    report = module.scan_repository(tmp_path / "data")

    assert report["trees"][0]["duplicate_source_ids"] == (
        {"source_id": "P000001", "relative_paths": ("a.json", "b.json")},
    )
    assert report["totals"]["duplicate_identity_groups"] == 1


def test_canonical_report_bytes_are_deterministic() -> None:
    module = load_harness()
    left = {"z": [2, 1], "a": {"y": 2, "x": 1}}
    right = {"a": {"x": 1, "y": 2}, "z": [2, 1]}

    assert module.canonical_report_bytes(left) == module.canonical_report_bytes(right)
    assert module.canonical_report_bytes(left).endswith(b"\n")


def test_pinned_report_binds_repository_revision(tmp_path: Path) -> None:
    module = load_harness()
    tree = tmp_path / "data" / "fixture" / "corpusjson"
    tree.mkdir(parents=True)
    (tree / "x.json").write_text(
        json.dumps({"type": "cdl", "textid": "X000001", "cdl": []}),
        encoding="utf-8",
    )

    report = module.build_pinned_report(
        tmp_path / "data", repository_revision=PINNED_REVISION
    )

    assert report["repository_revision"] == PINNED_REVISION
    assert report["totals"]["source_members"] == 1
    assert module.canonical_report_bytes(report) == module.canonical_report_bytes(
        module.build_pinned_report(tmp_path / "data", repository_revision=PINNED_REVISION)
    )


def test_cli_writes_exact_pinned_canonical_report(tmp_path: Path) -> None:
    module = load_harness()
    tree = tmp_path / "data" / "fixture" / "corpusjson"
    tree.mkdir(parents=True)
    (tree / "x.json").write_text(
        json.dumps({"type": "cdl", "textid": "X000001", "cdl": []}),
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    assert module.main(
        [
            "--data-root",
            str(tmp_path / "data"),
            "--repository-revision",
            PINNED_REVISION,
            "--output",
            str(output),
        ]
    ) == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["repository_revision"] == PINNED_REVISION
    assert output.read_bytes() == module.canonical_report_bytes(report)


def test_research_workflow_scans_exact_source_revision_read_only() -> None:
    assert WORKFLOW.is_file(), "ISSUE-102 exact-SHA research workflow is not implemented yet"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: read" in text
    assert f"ref: {PINNED_REVISION}" in text
    assert "path: .external/source" in text
    assert "sparse-checkout: |\n            data" in text
    assert "--data-root .external/source/data" in text
    assert f"--repository-revision {PINNED_REVISION}" in text
    assert "actions/upload-artifact@v4" in text
    assert "artifacts/issue102-unreadable-report.json" in text
