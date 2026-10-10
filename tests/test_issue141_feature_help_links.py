"""RED-first regression for working Text-Fabric feature-help links (#141)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from oracc_tf import TF_VERSION, app_generation, corpus, loader, metadata

DATASET = "assyrian-royal-inscriptions"
ORG = "alexsosn"
COMMIT = "a" * 40
ROOT = Path(__file__).resolve().parents[1]


def _input(tmp_path: Path) -> tuple[Path, Path]:
    doc = {
        "type": "cdl",
        "textid": "Q141",
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": "Q141.U0",
                "cdl": [
                    {"node": "d", "type": "line-start", "ref": "Q141.1", "label": "1"},
                    {
                        "node": "l",
                        "id": "Q141.l1",
                        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                    },
                ],
            },
        ],
    }
    edition = loader.Edition(
        subproject="fixture/help",
        text_id="Q141",
        path=Path("/fixture/help/Q141.json"),
        doc=doc,
        word_count=1,
    )
    tf_root = tmp_path / "tf"
    corpus.build_tf(
        tf_root,
        editions=[edition],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    registry = tmp_path / "datasets.toml"
    registry.write_text(
        f"[{DATASET}]\narchives = ['fixture']\n", encoding="utf-8"
    )
    return tf_root, registry


def test_default_app_help_uses_existing_builder_docs_not_missing_distribution_repo(
    tmp_path: Path,
) -> None:
    tf_root, registry = _input(tmp_path)
    app = app_generation.generate_app(
        tf_root,
        tmp_path / "app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        repository_org=ORG,
        datasets_path=registry,
    )
    docs = yaml.safe_load((app / "config.yaml").read_text(encoding="utf-8"))["docs"]
    assert docs["docBase"] == "https://github.com/alexsosn/ORACC-TF/blob/main/docs"
    assert docs["featureBase"] == "{docBase}/reference/features.md#<feature>"
    reference = (ROOT / "docs/reference/features.md").read_text(encoding="utf-8")
    assert '<a id="word_lex"></a>' in reference
    assert '<a id="translation_line"></a>' in reference


def test_registered_build_can_pin_help_to_exact_git_commit(tmp_path: Path) -> None:
    tf_root, registry = _input(tmp_path)
    app = app_generation.generate_app(
        tf_root,
        tmp_path / "app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        repository_org=ORG,
        datasets_path=registry,
        docs_ref=COMMIT,
    )
    config = yaml.safe_load((app / "config.yaml").read_text(encoding="utf-8"))
    assert config["docs"]["docBase"] == f"https://github.com/{ORG}/ORACC-TF/blob/{COMMIT}/docs"
    assert config["docs"]["featurePage"] == "feature-reference"


@pytest.mark.parametrize(
    "ref",
    ["../main", "/main", "release/1.0", "main?x=1", "MAIN", "", "deadbeef", 123],
)
def test_feature_help_ref_does_not_admit_paths_or_url_injection(
    tmp_path: Path, ref: object
) -> None:
    tf_root, registry = _input(tmp_path)
    with pytest.raises(app_generation.AppGenerationError, match="docs_ref"):
        app_generation.generate_app(
            tf_root,
            tmp_path / "bad-app",
            dataset=DATASET,
            tf_version=TF_VERSION,
            repository_org=ORG,
            datasets_path=registry,
            docs_ref=ref,
        )


def test_real_release_workflow_uses_commit_pinned_docs_help() -> None:
    flow = (ROOT / ".github/workflows/issue83-install-research.yml").read_text(
        encoding="utf-8"
    )
    assert 'docs_ref=os.environ["GITHUB_SHA"]' in flow
    assert "docs/reference/features.md" in flow
