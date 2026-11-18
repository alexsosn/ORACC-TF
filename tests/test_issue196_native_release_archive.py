"""RED release-format TF ZIP acceptance on pinned native ORACC primary JSON.

A local code-only wheel and the old royal corpus ZIP do not count as an
ETCSRI/NINMED deliverable. This creates actual release-shaped bytes.
"""
from __future__ import annotations

from hashlib import sha1, sha256
import json
from pathlib import Path
import shutil
from zipfile import ZipFile

import pytest
import yaml
from tf.app import use
from tf.fabric import Fabric

from oracc_tf import app_generation, distribution, etcsri, manual, ninmed, paths, release_archive


SOURCES = (
    ("etcsri", "Q000935", "etcsri/corpusjson/Q000935.json",
     "a2eef2a0337d276191fbda85a4269948fb00f9c3", 7),
    ("ninmed", "P285136", "asbp/ninmed/corpusjson/P285136.json",
     "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b", 204),
)


def _real_source(kind: str) -> tuple[Path, str, int]:
    _, text_id, path, blob, count = next(row for row in SOURCES if row[0] == kind)
    source = paths.DATA / path
    raw = source.read_bytes()
    actual = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
    assert actual == blob, f"{text_id}: primary-source blob changed; stop and re-review"
    assert json.loads(raw)["textid"] == text_id
    return source, text_id, count


def _source_state(path: Path) -> str:
    # Test-only source-state identity, not a fabricated upstream remote revision.
    raw = path.read_bytes()
    return "sha256:" + sha256(path.name.encode() + b"\0" + sha256(raw).digest()).hexdigest()


def _manual_repository(tmp_path: Path, kind: str) -> Path:
    """Minimal portable docs fixture, retaining source licence distinctions."""
    repo = tmp_path / "manual-repo"
    src = repo / "docs" / "native" / kind
    src.mkdir(parents=True)
    (src / "index.md").write_text(
        f"# {kind} native reader\n\n[Quick start](quick-start.md)\n"
        "[Features](features.md)\n[Rights](rights.md)\n",
        encoding="utf-8",
    )
    for name in ("quick-start.md", "features.md", "rights.md"):
        (src / name).write_text(
            f"# {kind} {name}\n\nORACC JSON source is CC0, not MIT corpus data.\n",
            encoding="utf-8",
        )
    (repo / "CITATION.cff").write_text(
        "cff-version: 1.2.0\nmessage: cite source and converter separately\n",
        encoding="utf-8",
    )
    (repo / "LICENSE_SCOPE.md").write_text(
        "Software MIT. ORACC JSON CC0. Website materials and images retain their licenses.\n",
        encoding="utf-8",
    )
    return repo


def test_native_registry_tracks_two_distinct_semantic_datasets_without_royal_mutation() -> None:
    datasets = __import__("oracc_tf.releases", fromlist=["load_datasets"]).load_datasets(
        paths.ROOT / "datasets.toml"
    )
    assert datasets["etcsri"].archives == ("etcsri",)
    assert datasets["ninmed"].archives == ("asbp-ninmed",)
    assert len(datasets["assyrian-royal-inscriptions"].archives) == 11


@pytest.mark.corpus
@pytest.mark.parametrize("kind", ("etcsri", "ninmed"))
def test_real_native_primary_source_to_versioned_app_stage_and_verified_zip(
    tmp_path: Path, kind: str,
) -> None:
    source, text_id, expected_words = _real_source(kind)
    tf_root = tmp_path / "source-tf"
    if kind == "etcsri":
        report = etcsri.build_tf(tf_root, source_paths=[source])
    else:
        report = ninmed.build_tf(tf_root, source_paths=[source])
    assert report.documents == 1 and report.words == expected_words

    app_root = app_generation.generate_app(
        tf_root, tmp_path / "generated-app",
        dataset=kind, tf_version="0.1.0", repository_org="alexsosn",
        native_kind=kind,
    )
    config = yaml.safe_load((app_root / "config.yaml").read_text(encoding="utf-8"))
    assert config["docs"]["featureBase"] == (
        "{docBase}/native/" + kind + "/features.md#<feature>"
    ), "native release app must not route a feature to the royal handbook"
    docs_root = manual.assemble_native_manual(
        _manual_repository(tmp_path, kind), tmp_path / "generated-docs",
        dataset=kind,
    )
    stage = tmp_path / "stage"
    manifest = distribution.stage_distribution(
        tf_root, stage, dataset=kind, release_id="0.1.0-rc1",
        tf_version="0.1.0",
        builder_commit="a" * 40,
        source_state=_source_state(source),
        support_roots={"app": app_root, "docs": docs_root},
    )
    assert manifest["dataset"] == kind
    assert manifest["tf_root"] == "tf/0.1.0"
    assert manifest["support_roots"]["app"]["path"] == "app"
    assert manifest["support_roots"]["docs"]["path"] == "docs"

    archive, sidecar = release_archive.package_release(stage, tmp_path / "assets")
    assert archive.name == f"{kind}-0.1.0-rc1.zip"
    expected_checksum = sidecar.read_text(encoding="utf-8").split()[0]
    assert sha256(archive.read_bytes()).hexdigest() == expected_checksum
    with ZipFile(archive) as zf:
        names = set(zf.namelist())
        assert {"manifest.json", "README.md", "app/config.yaml", "tf/0.1.0/otype.tf",
                "docs/index.md", "docs/reference/index.md",
                "docs/reference/quick-start.md", "docs/reference/features.md",
                "docs/reference/rights.md", "docs/reference/installation.md"} <= names
        assert not any(name.startswith(("data/", "programs/", "docs/native/",
                                        "docs/reference/words-and-lexemes.md"))
                       for name in names)
        zf.extractall(tmp_path / "user")
    assert json.loads((tmp_path / "user" / "manifest.json").read_text()) == manifest
    # This is the actual extracted end-user layout, not builder-side discovery.
    app = use(f"app:{tmp_path / 'user' / 'app'}", modules=[""], silent="deep")
    assert app is not None and app.api is not None
    api = app.api
    assert len(api.F.otype.s("document")) == 1
    assert len(api.F.otype.s("word")) == expected_words
    expected_key = f"{'etcsri' if kind == 'etcsri' else 'asbp/ninmed'}:{text_id}"
    assert expected_key in {
        api.F.document_key.v(n) for n in api.F.otype.s("document")
    }
    if kind == "etcsri":
        assert any(api.F.morph2.v(n) == "N1=NAME" for n in api.F.otype.s("word"))
    else:
        words = api.F.otype.s("word")
        assert any(api.F.cf.v(n) == "DÙ.DÙ.BI" for n in words)
        assert any(api.E.word_lex.f(n) for n in words)


@pytest.mark.parametrize("kind", ("etcsri", "ninmed"))
def test_native_manual_assembly_is_isolated_and_refuses_wrong_corpus(tmp_path: Path, kind: str) -> None:
    repo = _manual_repository(tmp_path, kind)
    other = "ninmed" if kind == "etcsri" else "etcsri"
    with pytest.raises(manual.ManualAssemblyError, match="native|missing|corpus"):
        manual.assemble_native_manual(repo, tmp_path / "bad", dataset=other)
    assert not (tmp_path / "bad").exists()
    docs = manual.assemble_native_manual(repo, tmp_path / "good", dataset=kind)
    assert (docs / "reference" / "installation.md").is_file()
    assert kind in (docs / "reference" / "index.md").read_text(encoding="utf-8")
    assert not (docs / "reference" / "words-and-lexemes.md").exists()
