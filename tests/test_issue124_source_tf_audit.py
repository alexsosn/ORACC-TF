"""Issue #124 RED contracts for the final source-to-TF audit."""

from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from oracc_tf import corpus, loader, metadata, paths


SOURCE_REVISION = "85d2f131202882d40b05b65bfb4c83e8b1238426"
DATASET = "assyrian-royal-inscriptions"
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_source_to_tf.py"
WORKFLOW = ROOT / ".github" / "workflows" / "issue124-source-tf-audit.yml"


def _audit():
    return importlib.import_module("oracc_tf.audit")


def _doc(text_id: str, *, signless: bool = False) -> dict[str, object]:
    word = {
        "node": "l",
        "id": f"{text_id}.l1",
        "f": {
            "lang": "akk",
            "form": "*" if signless else "a",
            "gdl": [] if signless else [{"v": "a", "utf8": "𒀀", "id": f"{text_id}.1.1.0"}],
        },
    }
    return {
        "type": "cdl",
        "project": "riao/ria1",
        "textid": text_id,
        "license": "fixture",
        "license-url": "https://example.test/license",
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": "o"},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    word,
                ],
            }
        ],
    }


def _write_source(data: Path, text_id: str, *, signless: bool = False) -> Path:
    root = data / "riao" / "ria1" / "corpusjson"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{text_id}.json"
    path.write_text(json.dumps(_doc(text_id, signless=signless)), encoding="utf-8")
    return path


def _write_catalogue(data: Path, members: dict[str, object] | None = None) -> None:
    root = data / "riao" / "ria1"
    root.mkdir(parents=True, exist_ok=True)
    (root / "catalogue.json").write_text(
        json.dumps(
            {
                "type": "catalogue",
                "project": "riao/ria1",
                "members": {} if members is None else members,
            }
        ),
        encoding="utf-8",
    )


def test_audit_reconciles_source_tf_and_keeps_known_gaps_explicit(tmp_path: Path) -> None:
    audit = _audit()
    data = tmp_path / "data"
    _write_source(data, "Q000001", signless=True)
    empty = data / "riao" / "ria1" / "corpusjson" / "QEMPTY.json"
    empty.write_bytes(b"")
    _write_catalogue(data)

    tf_root = tmp_path / "tf"
    corpus.build_full_tf(tf_root, data=data)
    report = audit.build_report(
        data=data,
        tf_dir=tf_root,
        source_revision=SOURCE_REVISION,
        dataset=DATASET,
    )

    assert report["schema_version"] == 1
    assert report["source"]["repository_revision"] == SOURCE_REVISION
    assert report["source"]["subprojects"] == ["riao/ria1"]
    assert report["source"]["members"] == 2
    assert report["source"]["readable_documents"] == 1
    assert report["source"]["hazards"][0]["kind"] == "empty-file"
    assert report["source"]["hazards"][0]["relative_path"].endswith("QEMPTY.json")

    manifest = report["source"]["members_manifest"]
    assert [item["relative_path"] for item in manifest] == [
        "riao/ria1/corpusjson/Q000001.json",
        "riao/ria1/corpusjson/QEMPTY.json",
    ]
    assert manifest[0]["document_key"] == "riao/ria1:Q000001"
    assert manifest[0]["status"] == "readable"
    assert manifest[1]["kind"] == "empty-file"
    assert manifest[1]["status"] == "hazard"
    assert len(report["source"]["catalogue_manifest"]) == 1
    assert report["source"]["catalogue_manifest"][0]["relative_path"] == (
        "riao/ria1/catalogue.json"
    )
    assert len(report["source"]["source_state_sha256"]) == 64

    assert report["tf"]["documents"] == 1
    assert report["tf"]["words"] == 1
    assert report["tf"]["semantic_signs"] == 0
    assert report["tf"]["synthetic_slots"] == 1
    assert report["tf"]["total_slots"] == 1

    assert report["reconciliation"]["documents"]["missing_in_tf"] == []
    assert report["reconciliation"]["documents"]["unexpected_in_tf"] == []
    assert report["reconciliation"]["words"]["missing_in_tf"] == []
    assert report["reconciliation"]["words"]["unexpected_in_tf"] == []
    assert report["reconciliation"]["semantic_signs"] == {
        "source": 0,
        "tf": 0,
        "delta": 0,
    }
    assert report["synthetic"]["source_payload_violations"] == []
    assert report["catalogue"]["missing_document_keys"] == ["riao/ria1:Q000001"]
    assert report["roundtrip"]["words"] == 1
    assert report["roundtrip"]["exceptions"] == {"zero_sign": 1}
    assert report["unexplained"] == []
    assert report["status"] == "pass"


def test_audit_reports_qualified_missing_document_and_word(tmp_path: Path) -> None:
    audit = _audit()
    data = tmp_path / "data"
    first = _write_source(data, "Q000001")
    _write_source(data, "Q000002")
    _write_catalogue(data)

    # Deliberately incomplete candidate: only one of two readable source editions.
    tf_root = tmp_path / "tf"
    corpus.build_tf(
        tf_root,
        editions=(loader.load_edition(first),),
        metadata_index=metadata.MetadataIndex.empty(),
    )
    report = audit.build_report(
        data=data,
        tf_dir=tf_root,
        source_revision=SOURCE_REVISION,
        dataset=DATASET,
    )

    assert report["reconciliation"]["documents"]["missing_in_tf"] == [
        "riao/ria1:Q000002"
    ]
    assert report["reconciliation"]["words"]["missing_in_tf"] == [
        "riao/ria1:Q000002|Q000002.l1"
    ]
    assert report["status"] == "fail"
    assert {item["kind"] for item in report["unexplained"]} >= {
        "missing-document",
        "missing-word",
        "semantic-sign-count",
        "line-count",
    }



def test_audit_detects_same_cardinality_semantic_drift(tmp_path: Path) -> None:
    audit = _audit()
    data = tmp_path / "data"
    source_path = _write_source(data, "Q000001")
    source_doc = json.loads(source_path.read_text(encoding="utf-8"))
    source_word = source_doc["cdl"][0]["cdl"][-1]
    source_word["f"].update(
        {"cf": "abu", "gw": "father", "pos": "N"}
    )
    source_path.write_text(json.dumps(source_doc), encoding="utf-8")
    _write_catalogue(
        data,
        {"Q000001": {"project": "riao/ria1", "designation": "Fixture 1"}},
    )

    candidate_doc = copy.deepcopy(source_doc)
    candidate_word = candidate_doc["cdl"][0]["cdl"][-1]
    candidate_word["f"].update(
        {
            "form": "ba",
            "cf": "alu",
            "gw": "city",
            "gdl": [
                {
                    "v": "ba",
                    "utf8": "𒁀",
                    "id": "Q000001.1.1.0",
                }
            ],
        }
    )
    candidate = loader.Edition(
        subproject="riao/ria1",
        text_id="Q000001",
        path=source_path,
        doc=candidate_doc,
        word_count=1,
    )

    tf_root = tmp_path / "tf"
    corpus.build_tf(
        tf_root,
        editions=(candidate,),
        metadata_index=metadata.load_index(data),
    )
    report = audit.build_report(
        data=data,
        tf_dir=tf_root,
        source_revision=SOURCE_REVISION,
        dataset=DATASET,
    )

    # Counts and qualified document/word identities are deliberately unchanged.
    assert report["reconciliation"]["documents"]["missing_in_tf"] == []
    assert report["reconciliation"]["words"]["missing_in_tf"] == []
    assert report["reconciliation"]["semantic_signs"]["delta"] == 0
    assert report["reconciliation"]["lines"]["delta"] == 0
    assert report["reconciliation"]["lexemes"]["delta"] == 0

    kinds = {item["kind"] for item in report["unexplained"]}
    assert {
        "word-feature-mismatch",
        "semantic-sign-payload-mismatch",
        "lexeme-identity",
        "word-lex-relation",
    } <= kinds
    assert report["status"] == "fail"


def test_audit_json_is_deterministic_and_checkout_path_independent(tmp_path: Path) -> None:
    audit = _audit()
    payloads = []
    for name in ("left", "right"):
        root = tmp_path / name
        data = root / "data"
        _write_source(data, "Q000001")
        _write_catalogue(
            data,
            {"Q000001": {"project": "riao/ria1", "designation": "Fixture 1"}},
        )
        tf_root = root / "tf"
        corpus.build_full_tf(tf_root, data=data)
        report = audit.build_report(
            data=data,
            tf_dir=tf_root,
            source_revision=SOURCE_REVISION,
            dataset=DATASET,
        )
        payloads.append(audit.canonical_bytes(report))

    assert payloads[0] == payloads[1]
    left_report = json.loads(payloads[0])
    right_report = json.loads(payloads[1])
    assert left_report["source"]["source_state_sha256"] == (
        right_report["source"]["source_state_sha256"]
    )
    assert str(tmp_path).encode() not in payloads[0]
    assert payloads[0].endswith(b"\n")



def test_release_workflow_verifies_pinned_source_tree_before_audit() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert 'git diff --exit-code "$SOURCE_REVISION" -- data/riao data/rinap datasets.toml' in workflow


def test_audit_cli_emits_machine_readable_json(tmp_path: Path) -> None:
    assert SCRIPT.is_file()
    data = tmp_path / "data"
    _write_source(data, "Q000001")
    _write_catalogue(data)
    tf_root = tmp_path / "tf"
    corpus.build_full_tf(tf_root, data=data)

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data",
            str(data),
            "--tf-dir",
            str(tf_root),
            "--source-revision",
            SOURCE_REVISION,
            "--dataset",
            DATASET,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(completed.stdout)
    assert report["status"] == "pass"
    assert report["source"]["repository_revision"] == SOURCE_REVISION


@pytest.mark.corpus
def test_real_candidate_has_no_unexplained_source_to_tf_loss(tmp_path: Path) -> None:
    audit = _audit()
    tf_root = tmp_path / "tf"
    corpus.build_full_tf(tf_root, data=paths.DATA)

    report = audit.build_report(
        data=paths.DATA,
        tf_dir=tf_root,
        source_revision=SOURCE_REVISION,
        dataset=DATASET,
    )

    assert report["source"]["members"] == 2081
    assert report["source"]["readable_documents"] == 2078
    assert report["source"]["populated_documents"] == 1845
    assert report["source"]["stubs"] == 233
    assert len(report["source"]["hazards"]) == 3
    assert {item["kind"] for item in report["source"]["hazards"]} == {"empty-file"}

    assert report["tf"]["documents"] == 2078
    assert report["tf"]["words"] == 320975
    assert report["tf"]["semantic_signs"] == 792651
    assert report["tf"]["synthetic_slots"] == 689
    assert report["tf"]["total_slots"] == 793340
    assert report["tf"]["lines"] == 56226
    assert report["tf"]["lexemes"] == 8025

    assert report["reconciliation"]["documents"]["missing_in_tf"] == []
    assert report["reconciliation"]["documents"]["unexpected_in_tf"] == []
    assert report["reconciliation"]["words"]["missing_in_tf"] == []
    assert report["reconciliation"]["words"]["unexpected_in_tf"] == []
    assert report["reconciliation"]["semantic_signs"]["delta"] == 0
    assert report["reconciliation"]["lines"]["delta"] == 0
    assert report["reconciliation"]["lexemes"]["delta"] == 0
    assert report["reconciliation"]["gdl_unknown"] == 0
    assert report["synthetic"]["source_payload_violations"] == []
    assert report["roundtrip"]["words"] == 320975
    assert report["roundtrip"]["exact"] + sum(
        report["roundtrip"]["exceptions"].values()
    ) == 320975
    assert report["unexplained"] == []
    assert report["status"] == "pass"
