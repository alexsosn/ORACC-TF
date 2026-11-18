"""Release reader-manual RED contract for source-distinct ETCSRI and NINMED.

Short public manuals must be grounded in primary ORACC JSON; the generic
royal inscriptions handbook must not be silently recycled for native corpora.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from oracc_tf import paths


MANUALS = Path(__file__).resolve().parents[1] / "docs" / "native"
REQUIRED = ("index.md", "quick-start.md", "features.md", "rights.md")

SOURCE = {
    "etcsri": paths.DATA / "etcsri" / "metadata.json",
    "ninmed": paths.DATA / "asbp" / "ninmed" / "metadata.json",
}


@pytest.mark.parametrize("kind", ("etcsri", "ninmed"))
def test_each_native_corpus_has_its_own_complete_reader_manual(kind: str) -> None:
    root = MANUALS / kind
    for name in REQUIRED:
        page = root / name
        assert page.is_file(), (kind, name)
        assert len(page.read_text(encoding="utf-8").strip()) > 120, (kind, name)
    index = (root / "index.md").read_text(encoding="utf-8")
    for name in REQUIRED[1:]:
        assert f"({name})" in index, (kind, "missing local navigation to", name)


@pytest.mark.parametrize("kind", ("etcsri", "ninmed"))
def test_native_manual_identifies_primary_upstream_and_cc0_json_not_mit_data(kind: str) -> None:
    source_meta = json.loads(SOURCE[kind].read_text(encoding="utf-8"))
    assert source_meta["license-url"] == "https://creativecommons.org/publicdomain/zero/1.0/"
    page = (MANUALS / kind / "rights.md").read_text(encoding="utf-8")
    assert source_meta["project"] in page
    assert source_meta["UTC-timestamp"] in page
    assert "CC0" in page and "CC BY-SA" in page
    assert "MIT" in page and "JSON" in page
    assert "British Museum" in page if kind == "ninmed" else True
    assert "translations" in page.lower() or "translation" in page.lower()


def test_etcsri_manual_explains_observed_unparsed_morphology_and_technical_markers() -> None:
    root = MANUALS / "etcsri"
    features = (root / "features.md").read_text(encoding="utf-8")
    quickstart = (root / "quick-start.md").read_text(encoding="utf-8")
    assert "morph2" in features and "morph" in features and "base" in features
    assert "para_json" in features and "nontext_span" in features and "nonword_marker" in features
    assert "N1=NAME" in features and "N1=Urnammak" in features
    assert "Q000935" in quickstart and "text-trans-full" in quickstart

    doc = json.loads((paths.DATA / "etcsri/corpusjson/Q000935.json").read_text(encoding="utf-8"))
    stack = [doc]
    found = []
    while stack:
        node = stack.pop()
        if node.get("node") == "l":
            found.append(node["f"])
        stack.extend(node.get("cdl") or [])
    assert any(f.get("morph") == "N1=Urnammak" and f.get("morph2") == "N1=NAME" for f in found)


def test_ninmed_manual_explains_native_lexicon_and_known_zero_byte_member() -> None:
    root = MANUALS / "ninmed"
    features = (root / "features.md").read_text(encoding="utf-8")
    quickstart = (root / "quick-start.md").read_text(encoding="utf-8")
    assert all(key in features for key in ("cf", "gw", "pos", "word_lex", "source_markers_json"))
    assert "DÙ.DÙ.BI" in features and "ritual (instructions)" in features
    assert "P285136" in quickstart and "P395407" in quickstart
    assert "65,089" in (root / "index.md").read_text(encoding="utf-8")
    assert (paths.DATA / "asbp/ninmed/corpusjson/P395407.json").read_bytes() == b""

    doc = json.loads((paths.DATA / "asbp/ninmed/corpusjson/P285136.json").read_text(encoding="utf-8"))
    stack = [doc]
    found = []
    while stack:
        node = stack.pop()
        if node.get("node") == "l":
            found.append(node["f"])
        stack.extend(node.get("cdl") or [])
    assert any(f.get("cf") == "DÙ.DÙ.BI" and f.get("gw") == "ritual (instructions)" for f in found)


@pytest.mark.corpus
@pytest.mark.parametrize("kind,text_id", (("etcsri", "Q000935"), ("ninmed", "P285136")))
def test_copy_paste_python_quickstart_executes_on_actual_oracc_tf(
    tmp_path: Path, kind: str, text_id: str
) -> None:
    """User-facing Python examples must run, not merely mention correct words."""
    import re
    import subprocess
    import sys

    from oracc_tf import etcsri, ninmed

    source = (
        paths.DATA / "etcsri" / "corpusjson" / f"{text_id}.json"
        if kind == "etcsri"
        else paths.DATA / "asbp" / "ninmed" / "corpusjson" / f"{text_id}.json"
    )
    if kind == "etcsri":
        etcsri.build_tf(tmp_path / "etcsri-tf", source_paths=[source])
    else:
        ninmed.build_tf(tmp_path / "ninmed-tf", source_paths=[source])

    markdown = (MANUALS / kind / "quick-start.md").read_text(encoding="utf-8")
    snippets = re.findall(r"```python\n(.*?)\n```", markdown, flags=re.S)
    assert len(snippets) == 1, "one complete Python sample per native manual"
    run = subprocess.run(
        [sys.executable, "-c", snippets[0]],
        cwd=tmp_path, text=True, capture_output=True, timeout=60, check=False,
    )
    assert run.returncode == 0, (kind, run.stdout, run.stderr)
    if kind == "etcsri":
        assert "N1=Urnammak" in run.stdout
    else:
        assert "DÙ.DÙ.BI" in run.stdout
        assert "ritual (instructions)" in run.stdout
