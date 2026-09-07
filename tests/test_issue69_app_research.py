"""Issue #69 research harness contracts.

These tests intentionally exercise Text-Fabric's real advanced-app and text-format
APIs.  The issue is research-only: the harness characterises current behavior and
must not add a production corpus app.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from oracc_tf import corpus, loader, metadata


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "research_issue69_tf_app.py"


def _research_module():
    assert SCRIPT.is_file(), "issue #69 app research harness has not been implemented"
    spec = importlib.util.spec_from_file_location("research_issue69_tf_app", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _edition() -> loader.Edition:
    text_id = "QAPP"
    doc = {
        "type": "cdl",
        "textid": text_id,
        "cdl": [
            {
                "node": "c",
                "type": "text",
                "id": f"{text_id}.U0",
                "cdl": [
                    {"node": "d", "type": "surface", "ref": "", "label": ""},
                    {
                        "node": "d",
                        "type": "line-start",
                        "ref": f"{text_id}.1",
                        "label": "1",
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l0",
                        "f": {"form": "*", "gdl": []},
                    },
                    {
                        "node": "l",
                        "id": f"{text_id}.l1",
                        "f": {"form": "a", "gdl": [{"v": "a", "utf8": "𒀀"}]},
                    },
                ],
            }
        ],
    }
    return loader.Edition(
        subproject="test/app",
        text_id=text_id,
        path=Path("/test/app/corpusjson/QAPP.json"),
        doc=doc,
        word_count=2,
    )


def _build_fixture(root: Path) -> None:
    corpus.build_tf(
        root,
        editions=(_edition(),),
        metadata_index=metadata.MetadataIndex.empty(),
    )


def test_issue69_profiles_real_advanced_app_and_excluded_features(tmp_path: Path) -> None:
    module = _research_module()
    tf_root = tmp_path / "tf"
    _build_fixture(tf_root)

    excluded = ("sign_json", "gdl_json", "catalogue_json")
    result = module.profile_advanced_app(tf_root, excluded_features=excluded)

    assert result["schema_version"] == 1
    assert result["app_loaded"] is True
    assert result["excluded_features"] == list(excluded)
    assert result["max_slot"] == 2
    assert result["elapsed_seconds"] >= 0
    assert result["peak_rss_kib"] > 0
    loaded = set(result["loaded_node_features"])
    assert loaded.isdisjoint(excluded)
    assert {"otype", "document", "face", "line"} <= loaded


def test_issue69_prototype_formats_do_not_leak_synthetic_slots(tmp_path: Path) -> None:
    module = _research_module()
    source = tmp_path / "source"
    prototype = tmp_path / "prototype"
    _build_fixture(source)

    module.inject_prototype_formats(source, prototype)
    result = module.probe_text_formats(prototype)

    assert result["schema_version"] == 1
    assert result["synthetic_slot_count"] == 1
    assert result["synthetic_slot_utf8"] is None
    assert result["cuneiform"] == "𒀀"
    assert result["transliteration"].strip().split() == ["*", "a"]
    assert "synthetic" not in result["cuneiform"].lower()
    assert "synthetic" not in result["transliteration"].lower()


def test_issue69_measures_candidate_feature_file_bytes(tmp_path: Path) -> None:
    module = _research_module()
    tf_root = tmp_path / "tf"
    _build_fixture(tf_root)

    features = ("sign_json", "gdl_json", "catalogue_json")
    result = module.measure_feature_bytes(tf_root, features=features)

    assert result["schema_version"] == 1
    assert result["feature_bytes"] == {
        feature: (tf_root / f"{feature}.tf").stat().st_size
        for feature in features
    }
    assert result["total_bytes"] == sum(result["feature_bytes"].values())


def test_issue69_censuses_none_values_without_copying_bhsa_policy(tmp_path: Path) -> None:
    module = _research_module()
    tf_root = tmp_path / "tf"
    _build_fixture(tf_root)

    assert module.BHSA_NONE_VALUES == (
        "absent",
        "n/a",
        "none",
        "unknown",
        "null",
        "NA",
    )
    default_result = module.census_exact_values(tf_root)
    assert default_result["schema_version"] == 1
    assert default_result["candidates"] == list(module.BHSA_NONE_VALUES)
    assert default_result["counts"] == {value: 0 for value in module.BHSA_NONE_VALUES}
    assert default_result["features"] == {value: [] for value in module.BHSA_NONE_VALUES}

    positive = module.census_exact_values(tf_root, candidates=("a", "missing"))
    assert positive["counts"]["a"] > 0
    assert "form" in positive["features"]["a"]
    assert positive["counts"]["missing"] == 0
    assert positive["features"]["missing"] == []
