"""Issue #32 research gate — raw ETCSRI evidence from the Zenodo JSON cache."""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def _raw_cache(path: Path) -> None:
    inner = BytesIO()
    with zipfile.ZipFile(inner, "w") as project:
        project.writestr(
            "etcsri/corpusjson/P000001.json",
            json.dumps(
                {
                    "type": "cdl",
                    "textid": "P000001",
                    "cdl": [
                        {
                            "node": "c",
                            "type": "text",
                            "cdl": [
                                {"node": "d", "type": "surface", "label": "obverse"},
                                {"node": "d", "type": "line-start", "label": "1"},
                                {
                                    "node": "c",
                                    "type": "sentence",
                                    "cdl": [
                                        {
                                            "node": "l",
                                            "id": "P000001.1.1",
                                            "f": {
                                                "form": "lugal",
                                                "base": "lugal",
                                                "morph": "lugal=ak",
                                                "morph2": "king=GEN",
                                                "para": "1",
                                                "cf": "lugal",
                                                "gw": "king",
                                                "pos": "N",
                                                "lang": "sux",
                                                "gdl": [
                                                    {"v": "LUGAL", "utf8": "𒈗"}
                                                ],
                                            },
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
        )
    with zipfile.ZipFile(path, "w") as outer:
        outer.writestr("jsonzip/etcsri.zip", inner.getvalue())
        outer.writestr("jsonzip/other.zip", b"not inspected")


def test_raw_cache_census_targets_only_etcsri_and_supports_raw_claims(tmp_path: Path):
    archive = tmp_path / "oracc_jsonzip_all.zip"
    _raw_cache(archive)
    report = tmp_path / "raw.json"
    command = [
        sys.executable,
        "scripts/research_etcsri_snapshot.py",
        "--raw-cache",
        str(archive),
        "--output",
        str(report),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    first = report.read_bytes()
    data = json.loads(first)
    assert data["schema"] == "oracc-tf-etcsri-research-v1"
    assert data["evidence_kind"] == "raw-oracc-json-cache"
    assert data["raw_source_claims_supported"] is True
    assert len(data["cache_sha256"]) == 64
    assert len(data["project_zip_sha256"]) == 64
    assert data["corpusjson_files"] == 1
    assert data["parseable_documents"] == 1
    assert data["words"] == 1
    assert data["word_features"]["base"]["populated"] == 1
    assert data["word_features"]["morph"]["populated"] == 1
    assert data["word_features"]["morph2"]["populated"] == 1
    assert data["word_features"]["para"]["populated"] == 1
    assert data["chunk_types"] == {"sentence": 1, "text": 1}
    assert data["marker_types"] == {"line-start": 1, "surface": 1}
    assert data["gdl_object_keys"] == {"utf8,v": 1}

    subprocess.run(command, check=True, capture_output=True, text=True)
    assert report.read_bytes() == first


def test_raw_cache_fails_closed_without_nested_etcsri_bundle(tmp_path: Path):
    archive = tmp_path / "oracc_jsonzip_all.zip"
    with zipfile.ZipFile(archive, "w") as outer:
        outer.writestr("jsonzip/other.zip", b"irrelevant")

    report = tmp_path / "raw.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/research_etcsri_snapshot.py",
            "--raw-cache",
            str(archive),
            "--output",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "etcsri" in completed.stderr.lower()
    assert not report.exists()
