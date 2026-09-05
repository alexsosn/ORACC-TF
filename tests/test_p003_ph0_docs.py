from pathlib import Path

from oracc_tf import corpus


def test_every_emitted_feature_has_nonempty_description():
    graph = corpus._Graph()
    graph.slot_feature(1, form="a")
    node = graph.node("document", {1})
    graph.feature(
        node,
        document="Q1",
        cf="x",
        gw="g",
        sense="s",
        norm="n",
        epos="N",
        sig="sig",
    )
    materialised = graph.materialise(1)
    for name, meta in materialised.meta_data.items():
        if name in {"", "otext", "otype", "oslots"}:
            continue
        assert meta.get("description", "").strip(), name


def test_phase0_reference_tree_and_generators_exist():
    expected = {
        "index.md", "model.md", "signs.md", "words-and-lexemes.md",
        "translations.md", "identity.md", "query-guide.md",
        "reproducibility.md", "features.md",
    }
    root = Path("docs/reference")
    assert root.is_dir()
    assert expected <= {p.name for p in root.glob("*.md")}
    assert Path("scripts/gen_docs.py").is_file()
    assert Path("scripts/check_docs.py").is_file()
