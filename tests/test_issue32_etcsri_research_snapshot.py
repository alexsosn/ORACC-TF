"""Issue #32 research gate — reproducible ETCSRI snapshot census.

The research tool must distinguish derived-cache evidence from raw ORACC
source evidence. These tests exercise only deterministic local ZIP handling;
live Zenodo acquisition belongs to a dedicated integration workflow.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import subprocess
import sys
import zipfile


def _write_csv(zf: zipfile.ZipFile, name: str, rows: list[dict[str, str]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    zf.writestr(name, buffer.getvalue())


def test_local_derived_zip_census_is_deterministic_and_labels_evidence(tmp_path: Path):
    archive = tmp_path / "etcsri.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        _write_csv(
            zf,
            "etcsri/P000001.csv",
            [
                {
                    "id": "P000001.1.1",
                    "form": "lugal",
                    "base": "lugal",
                    "morph": "lugal=ak",
                    "morph2": "king=GEN",
                    "cf": "lugal",
                    "gw": "king",
                    "pos": "N",
                    "lang": "sux",
                },
                {
                    "id": "P000001.1.2",
                    "form": "e2",
                    "base": "e2",
                    "morph": "e2",
                    "morph2": "house",
                    "cf": "e",
                    "gw": "house",
                    "pos": "N",
                    "lang": "sux",
                },
            ],
        )
        _write_csv(
            zf,
            "etcsri/P000002.csv",
            [
                {
                    "id": "P000002.1.1",
                    "form": "mu",
                    "base": "mu",
                    "morph": "mu",
                    "morph2": "name",
                    "cf": "mu",
                    "gw": "name",
                    "pos": "N",
                    "lang": "sux",
                }
            ],
        )

    report = tmp_path / "report.json"
    command = [
        sys.executable,
        "scripts/research_etcsri_snapshot.py",
        "--derived-zip",
        str(archive),
        "--output",
        str(report),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr

    first = report.read_bytes()
    data = json.loads(first)
    assert data["schema"] == "oracc-tf-etcsri-research-v1"
    assert data["evidence_kind"] == "derived-cache"
    assert data["raw_source_claims_supported"] is False
    assert data["files"] == 2
    assert data["rows"] == 3
    assert data["columns"]["morph"]["populated"] == 3
    assert data["columns"]["morph2"]["populated"] == 3
    assert data["columns"]["base"]["populated"] == 3
    assert data["columns"]["lang"]["distinct"] == 1
    assert len(data["sha256"]) == 64

    subprocess.run(command, check=True, capture_output=True, text=True)
    assert report.read_bytes() == first


def test_census_fails_closed_when_morphology_columns_are_absent(tmp_path: Path):
    archive = tmp_path / "etcsri.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        _write_csv(zf, "etcsri/P000001.csv", [{"id": "x", "form": "lugal"}])

    report = tmp_path / "report.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/research_etcsri_snapshot.py",
            "--derived-zip",
            str(archive),
            "--output",
            str(report),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode != 0
    assert "morph" in completed.stderr.lower()
    assert not report.exists()
