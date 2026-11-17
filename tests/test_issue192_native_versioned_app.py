"""ISSUE-192 release-app RED gate: source-attested native TF in versioned layout.

This checks the actual Q000935 and P285136 ORACC JSON, not synthetic
'ETCSRI' / 'NINMED' node labels. No dataset publication or rights claim.
"""
from __future__ import annotations

from hashlib import sha1
from pathlib import Path

import pytest
import yaml

from oracc_tf import app_generation, etcsri, ninmed, paths


WITNESSES = (
    ("etcsri", "etcsri/corpusjson/Q000935.json", "a2eef2a0337d276191fbda85a4269948fb00f9c3"),
    ("ninmed", "asbp/ninmed/corpusjson/P285136.json", "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b"),
)


def _source(kind: str) -> Path:
    selected = next(item for item in WITNESSES if item[0] == kind)
    source = paths.DATA / selected[1]
    payload = source.read_bytes()
    actual = sha1(f"blob {len(payload)}\\0".encode("ascii") + payload).hexdigest()
    assert actual == selected[2], f"{kind} source changed: review edition before release"
    return source


def _registry(tmp_path: Path, *datasets: str) -> Path:
    registry = tmp_path / "datasets.toml"
    registry.write_text(
        "".join(f'[{kind}]\\narchives = ["{kind}"]\\n' for kind in datasets),
        encoding="utf-8",
    )
    return registry


def _native_tf(tmp_path: Path, kind: str) -> Path:
    root = tmp_path / f"{kind}-source-tf"
    source = _source(kind)
    if kind == "etcsri":
        result = etcsri.build_tf(root, source_paths=[source])
        assert result.words == 7
    else:
        result = ninmed.build_tf(root, source_paths=[source])
        assert result.words == 204
    return root


@pytest.mark.corpus
@pytest.mark.parametrize("kind", ("etcsri", "ninmed"))
def test_registered_versioned_app_preserves_native_identity_and_display(
    tmp_path: Path, kind: str
) -> None:
    source_tf = _native_tf(tmp_path, kind)
    app = tmp_path / "app"
    registry = _registry(tmp_path, kind)

    app_generation.generate_app(
        source_tf, app, dataset=kind, tf_version="0.1.0",
        repository_org="alexsosn", datasets_path=registry,
        native_kind=kind,
    )
    config = yaml.safe_load((app / "config.yaml").read_text(encoding="utf-8"))
    assert config["provenanceSpec"] == {
        "corpus": kind, "relative": "/tf", "version": "0.1.0",
    }
    assert "preview" not in (app / "config.yaml").read_text(encoding="utf-8")
    assert config["dataDisplay"]["textFormat"] == "text-trans-full"
    assert config["interfaceDefaults"]["standardFeatures"] is True
    assert config["typeDisplay"]["word"]["label"] == "{form}"
    assert "word_json" in config["dataDisplay"]["excludedFeatures"]
    if kind == "etcsri":
        assert set(("base", "morph", "morph2")) <= set(
            config["typeDisplay"]["word"]["featuresBare"].split()
        )
        assert config["typeDisplay"]["nontext_span"]["hidden"] is True
        assert config["typeDisplay"]["nonword_marker"]["hidden"] is True
    else:
        assert set(("cf", "gw", "pos")) <= set(
            config["typeDisplay"]["word"]["featuresBare"].split()
        )


@pytest.mark.parametrize("dataset,native_kind", (
    ("etcsri", None),
    ("ninmed", None),
    ("etcsri", "ninmed"),
    ("ninmed", "etcsri"),
    ("etcsri", "unknown"),
    ("assyrian-royal-inscriptions", "etcsri"),
))
def test_registered_native_app_cannot_silently_use_royal_or_foreign_policy(
    tmp_path: Path, dataset: str, native_kind: str | None
) -> None:
    registry = _registry(tmp_path, dataset)
    with pytest.raises(app_generation.AppGenerationError, match="native|kind|dataset"):
        app_generation.generate_app(
            tmp_path / "missing-tf", tmp_path / "app", dataset=dataset,
            tf_version="0.1.0", repository_org="alexsosn",
            datasets_path=registry, native_kind=native_kind,
        )
    assert not (tmp_path / "app").exists()


@pytest.mark.corpus
def test_versioned_app_rejects_cross_corpus_primary_source_identity(tmp_path: Path) -> None:
    # Dataset registry/key alone is not evidence that its TF graph is that corpus.
    native_ninmed_tf = _native_tf(tmp_path, "ninmed")
    registry = _registry(tmp_path, "etcsri")
    with pytest.raises(app_generation.AppGenerationError, match="identity mismatch"):
        app_generation.generate_app(
            native_ninmed_tf, tmp_path / "app", dataset="etcsri",
            tf_version="0.1.0", repository_org="alexsosn",
            datasets_path=registry, native_kind="etcsri",
        )
    assert not (tmp_path / "app").exists()
