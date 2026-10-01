"""Issue #73 RED contracts for browser usability and preload policy."""

from __future__ import annotations

from pathlib import Path

import yaml
from tf.advanced.app import findApp
from tf.browser.kernel import makeTfKernel
from tf.browser.web import Web, factory

from oracc_tf import TF_VERSION, corpus, loader, metadata


DATASET = "assyrian-royal-inscriptions"
ORG = "example-org"
ROOT = Path(__file__).resolve().parents[1]


def _edition() -> loader.Edition:
    text_id = "Q000073"
    doc = {
        "type": "cdl",
        "project": "fixture/project",
        "textid": text_id,
        "license": "fixture",
        "license-url": "https://example.test/license",
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "obv", "label": "obv"},
                    {"node": "d", "type": "column", "ref": "1", "label": "i"},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "c",
                        "type": "phrase",
                        "id": f"{text_id}.U1",
                        "subtype": "NP",
                        "cdl": [
                            {
                                "node": "l",
                                "id": f"{text_id}.l1",
                                "ref": f"{text_id}.1.1",
                                "frag": "a",
                                "f": {
                                    "lang": "akk",
                                    "form": "a",
                                    "cf": "abu",
                                    "gw": "father",
                                    "pos": "N",
                                    "epos": "N",
                                    "gdl": [
                                        {
                                            "v": "a",
                                            "utf8": "𒀀",
                                            "id": f"{text_id}.1.1.0",
                                        }
                                    ],
                                },
                            },
                            {
                                "node": "l",
                                "id": f"{text_id}.l2",
                                "ref": f"{text_id}.1.2",
                                "frag": "mnn",
                                "f": {"lang": "arc", "form": "mnn", "gdl": []},
                            },
                        ],
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="fixture/project",
        text_id=text_id,
        path=Path(f"/fixture/corpusjson/{text_id}.json"),
        doc=doc,
        word_count=2,
    )


def _tf_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo" / "tf" / TF_VERSION
    corpus.build_tf(
        root,
        editions=[_edition()],
        metadata_index=metadata.MetadataIndex.empty(),
    )
    return root


def _datasets(tmp_path: Path) -> Path:
    path = tmp_path / "datasets.toml"
    path.write_text(
        f"[{DATASET}]\narchives = [\"fixture\"]\n",
        encoding="utf-8",
    )
    return path


def _generate(tmp_path: Path):
    from oracc_tf import app_generation

    tf_root = _tf_root(tmp_path)
    app_root = app_generation.generate_app(
        tf_root,
        tmp_path / "repo" / "app",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=_datasets(tmp_path),
        repository_org=ORG,
    )
    return tf_root, app_root


def test_generated_config_has_measured_preload_policy_and_docs_contract(tmp_path: Path) -> None:
    _tf, app_root = _generate(tmp_path)
    config = yaml.safe_load((app_root / "config.yaml").read_text(encoding="utf-8"))

    assert config["dataDisplay"]["excludedFeatures"] == [
        "catalogue_json",
        "gdl_json",
        "sign_json",
    ]
    assert config["dataDisplay"]["textFormat"] == "text-trans-full"
    assert "noneValues" not in config["dataDisplay"]

    provenance = config["provenanceSpec"]
    assert provenance == {
        "corpus": DATASET,
        "relative": "/tf",
        "version": TF_VERSION,
    }

    assert config["docs"] == {
        "docBase": (
            f"https://github.com/{ORG}/ORACC-TF-{DATASET}/blob/main/docs"
        ),
        "featureBase": "{docBase}/reference/features.md#<feature>",
        "featurePage": "feature-reference",
    }


def test_type_display_covers_emitted_types_with_source_faithful_policy(tmp_path: Path) -> None:
    tf_root, app_root = _generate(tmp_path)
    config = yaml.safe_load((app_root / "config.yaml").read_text(encoding="utf-8"))

    from tf.fabric import Fabric

    tf = Fabric(locations=str(tf_root), silent="deep")
    assert tf.loadAll(silent="deep")
    emitted = set(tf.api.F.otype.all)
    display = config["typeDisplay"]

    assert set(display) == emitted
    assert display["document"]["label"] == "{document}"
    assert display["line"]["label"] == "{lnno}"
    assert display["line"]["verselike"] is True
    assert display["chunk"]["hidden"] is True
    assert display["word"]["style"] == "trans"
    assert display["lex"]["lexOcc"] == "word"
    assert display["lex"]["label"] == "{cf} [{gw}]"
    assert display["sign"]["style"] == "orig"
    assert display["sign"]["exclude"] == {"synthetic": 1}
    assert "sentence" not in display


def test_excluded_features_remain_explicitly_loadable(tmp_path: Path) -> None:
    tf_root, app_root = _generate(tmp_path)
    app = findApp(
        f"app:{app_root}",
        "",
        None,
        "github",
        False,
        locations=[str(tf_root)],
        modules=[""],
        version=TF_VERSION,
        silent="deep",
    )
    assert app is not None and app.api is not None

    for feature in ("catalogue_json", "gdl_json", "sign_json"):
        assert feature not in set(app.api.Fall())
        assert app.load(feature, silent="deep")
        assert feature in set(app.api.Fall())


def test_generated_app_browser_mode_serves_core_routes_without_header_failure(
    tmp_path: Path,
) -> None:
    tf_root, app_root = _generate(tmp_path)
    app_name = f"app:{app_root}"
    app = findApp(
        app_name,
        "",
        None,
        "github",
        True,
        locations=[str(tf_root)],
        modules=[""],
        version=TF_VERSION,
        silent="deep",
    )
    assert app is not None and app.api is not None
    assert app.context.excludedFeatures == {
        "catalogue_json",
        "gdl_json",
        "sign_json",
    }

    webapp = factory(Web(makeTfKernel(app, app_name)))
    client = webapp.test_client()
    for route in ("/", "/passage", "/query", "/export"):
        response = client.get(route)
        assert response.status_code == 200, (route, response.status_code)
        assert response.data


def test_feature_reference_has_stable_feature_name_anchors() -> None:
    feature_index = (ROOT / "docs" / "reference" / "features.md").read_text(
        encoding="utf-8"
    )
    for feature in ("catalogue_json", "cf", "form", "sign_json", "word_lex"):
        assert f'<a id="{feature}"></a>' in feature_index


def test_generated_app_remains_declarative_and_deterministic(tmp_path: Path) -> None:
    from oracc_tf import app_generation

    tf_root = _tf_root(tmp_path)
    datasets = _datasets(tmp_path)
    first = app_generation.generate_app(
        tf_root,
        tmp_path / "app-a",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
        repository_org=ORG,
    )
    second = app_generation.generate_app(
        tf_root,
        tmp_path / "app-b",
        dataset=DATASET,
        tf_version=TF_VERSION,
        datasets_path=datasets,
        repository_org=ORG,
    )
    assert (first / "config.yaml").read_bytes() == (second / "config.yaml").read_bytes()
    assert not (first / "app.py").exists()
    assert not (second / "app.py").exists()
