"""#181 RED: a real native ORACC Text-Fabric corpus must load in a LOCAL browser.

These are checked-in ORACC primary-source witnesses; no fabricated word corpus
and no Nino source material. No dataset is registered or published.
"""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path

import pytest
import yaml
from tf.app import use
from tf.browser.web import setup

from oracc_tf import app_generation, etcsri, ninmed, paths


WITNESSES = {
    "etcsri": ("Q000935", "a2eef2a0337d276191fbda85a4269948fb00f9c3"),
    "ninmed": ("P285136", "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b"),
}


def _native_tf(tmp_path: Path, kind: str) -> Path:
    source_id, source_blob = WITNESSES[kind]
    src = (
        paths.DATA / "etcsri" / "corpusjson" / f"{source_id}.json"
        if kind == "etcsri"
        else paths.DATA / "asbp" / "ninmed" / "corpusjson" / f"{source_id}.json"
    )
    raw = src.read_bytes()
    assert sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest() == source_blob
    assert json.loads(raw)["textid"] == source_id
    tf_root = tmp_path / "tf"
    if kind == "etcsri":
        etcsri.build_tf(tf_root, source_paths=[src])
    else:
        ninmed.build_tf(tf_root, source_paths=[src])
    return tf_root


@pytest.mark.corpus
@pytest.mark.parametrize("kind", ["etcsri", "ninmed"])
def test_native_local_app_renders_real_source_tf_without_public_dataset_registration(
    tmp_path: Path,
    kind: str,
) -> None:
    tf_root = _native_tf(tmp_path, kind)
    app_root = app_generation.generate_local_app(
        tf_root, tmp_path / "app", corpus_kind=kind,
    )
    cfg = yaml.safe_load((app_root / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["apiVersion"] == 3
    assert cfg["provenanceSpec"]["corpus"] == f"{kind}-local-preview"
    assert cfg["dataDisplay"]["textFormat"] == "text-trans-full"
    assert cfg["provenanceSpec"]["version"] == "", "local flat TF output has no version subdirectory"
    assert set(cfg["typeDisplay"])  # actual TF schema, not guessed types
    assert "word" in cfg["typeDisplay"]

    # This exercises the official advanced app loader; it must not require
    # a released dataset registry entry or download a remote corpus.
    app = use(
        f"app:{app_root}", locations=[str(tf_root)], modules=[""],
        silent="deep",
    )
    assert app is not None and app.api is not None
    assert len(app.api.F.otype.s("document")) == 1
    if kind == "etcsri":
        assert len(app.api.F.otype.s("word")) == 7
        assert len([w for w in app.api.F.otype.s("word") if app.api.F.morph.v(w)]) == 7
        assert {"text", "discourse", "sentence", "determinative"} <= set(cfg["typeDisplay"])
        for otype in ("nontext_span", "nonword_marker", "determinative"):
            if otype in cfg["typeDisplay"]:
                assert cfg["typeDisplay"][otype]["hidden"] is True
    else:
        words = app.api.F.otype.s("word")
        assert len(words) == 204
        example = next(w for w in words if app.api.F.source_id.v(w) == "P285136.l003f2")
        assert app.api.F.cf.v(example) == "DÙ.DÙ.BI"
        assert app.api.E.word_lex.f(example)


@pytest.mark.corpus
def test_local_native_app_rejects_mislabelled_corpus(tmp_path: Path) -> None:
    tf_root = _native_tf(tmp_path, "etcsri")
    with pytest.raises(app_generation.AppGenerationError, match="NINMED|ninmed|identity"):
        app_generation.generate_local_app(
            tf_root, tmp_path / "app", corpus_kind="ninmed"
        )
    assert not (tmp_path / "app" / "config.yaml").exists()


@pytest.mark.corpus
@pytest.mark.parametrize("kind", ["etcsri", "ninmed"])
def test_native_real_text_fabric_browser_http_routes(tmp_path: Path, kind: str) -> None:
    """Actual TF browser Flask stack for both native corpora."""
    tf_root = _native_tf(tmp_path, kind)
    app_root = app_generation.generate_local_app(
        tf_root, tmp_path / "app", corpus_kind=kind,
    )
    webapp = setup(
        False, f"app:{app_root}", f"--locations={tf_root}", "--modules=",
    )
    assert webapp is not None
    client = webapp.test_client()
    # TF's front page is HTML, but its section/query endpoints deliberately
    # return JSON response payloads for the browser client, not entire pages.
    front = client.get("/")
    assert front.status_code == 200
    assert "<html" in front.get_data(as_text=True).lower()
    for route in ("/sections", "/query"):
        response = client.get(route)
        assert response.status_code == 200, (route, response.get_data(as_text=True)[-1000:])
        assert response.is_json, (route, response.content_type)
        payload = response.get_json()
        assert isinstance(payload, dict) and "messages" in payload
        assert "Traceback" not in response.get_data(as_text=True)


@pytest.mark.corpus
def test_native_app_prepare_cli_is_usable_outside_builder_working_dir(tmp_path: Path) -> None:
    import subprocess
    import sys
    tf_root = _native_tf(tmp_path, "ninmed")
    app_root = tmp_path / "app"
    run = subprocess.run(
        [
            sys.executable, "-m", "oracc_tf", "prepare-local-app",
            "--kind", "ninmed", "--tf-dir", str(tf_root),
            "--app-dir", str(app_root),
        ],
        cwd=tmp_path, text=True, capture_output=True, check=False,
    )
    assert run.returncode == 0, run.stderr
    assert (app_root / "config.yaml").is_file()
    assert "tf" in run.stdout.lower() and "app:" in run.stdout


@pytest.mark.corpus
def test_missing_lines_and_blank_ref_events_are_hidden_not_fake_text(
    tmp_path: Path,
) -> None:
    """Two actual ETCSRI CDL events must not appear as invented words."""
    sources = []
    for doc_id, expected_blob in (
        ("Q000377", "62bbca48a50205353ac5ed8225a3ce3e163c5f31"),
        ("Q001794", "286a599b1331f437ca1fa0bbb22e16053206056e"),
    ):
        path = paths.DATA / "etcsri" / "corpusjson" / f"{doc_id}.json"
        raw = path.read_bytes()
        assert sha1(b"blob " + str(len(raw)).encode("ascii") + bytes([0]) + raw).hexdigest() == expected_blob
        sources.append(path)
    tf_root = tmp_path / "tf"
    etcsri.build_tf(tf_root, source_paths=sources)
    app_root = app_generation.generate_local_app(tf_root, tmp_path / "app", corpus_kind="etcsri")
    cfg = yaml.safe_load((app_root / "config.yaml").read_text(encoding="utf-8"))
    for kind in ("nontext_span", "nonword_marker", "determinative"):
        assert cfg["typeDisplay"][kind]["hidden"] is True
    app = use(f"app:{app_root}", locations=[str(tf_root)], modules=[""], silent="deep")
    assert app is not None and app.api is not None
    assert app.api.F.otype.s("nontext_span")
    assert app.api.F.otype.s("nonword_marker")
    assert "word_json" in cfg["dataDisplay"]["excludedFeatures"]
    assert "marker_json" in cfg["dataDisplay"]["excludedFeatures"]
    # The official TF browser deliberately does not load excluded heavyweight
    # provenance. Assert native source fidelity via a separate *full* TF API.
    from tf.fabric import Fabric
    full_tf = Fabric(locations=str(tf_root), silent="deep")
    assert full_tf.loadAll(silent="deep")
    assert any(
        json.loads(full_tf.api.F.marker_json.v(n)).get("ref") == ""
        for n in full_tf.api.F.otype.s("nonword_marker")
    )


@pytest.mark.corpus
def test_local_browser_does_not_overwrite_researcher_owned_app_directory(
    tmp_path: Path,
) -> None:
    """Local preview must not replace an unrelated user directory with a config."""
    tf_root = _native_tf(tmp_path, "etcsri")
    target = tmp_path / "notes-and-app"
    target.mkdir()
    (target / "research-notes.md").write_text("do not erase", encoding="utf8")
    with pytest.raises(app_generation.AppGenerationError, match="nonempty|empty|overwrite|user"):
        app_generation.generate_local_app(tf_root, target, corpus_kind="etcsri")
    assert (target / "research-notes.md").read_text(encoding="utf8") == "do not erase"
    assert not (target / "config.yaml").exists()
