from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest

from oracc_tf import corpus


def _load_script(name: str):
    spec = spec_from_file_location(name, Path("scripts") / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class _Feature:
    def __init__(self, description: str, data):
        self.meta = {"description": description, "valueType": "str"}
        self._data = data

    def items(self):
        yield from self._data


class _Otype:
    meta = {"description": "Text-Fabric node type.", "valueType": "str"}

    @staticmethod
    def v(node):
        return "sign" if node == 1 else "word"

    @staticmethod
    def items():
        yield (1, "sign")
        yield (2, "word")


class _Api:
    class F:
        otype = _Otype()

    def __init__(self):
        self._node = {"form": _Feature("Source sign form.", [(1, "a")])}
        self._edge = {
            "oslots": _Feature("Text-Fabric warp edge.", [(2, {1})]),
            "linked": _Feature("Source relation.", [(1, {2})]),
        }

    def Fall(self):
        return ["otype", *self._node]

    def Eall(self):
        return list(self._edge)

    def Fs(self, name):
        if name == "otype":
            return self.F.otype
        return self._node[name]

    def Es(self, name):
        return self._edge[name]


class _Fabric:
    def __init__(self, *args, **kwargs):
        self.api = _Api()

    def loadAll(self, **kwargs):
        return True


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
        if name in {"", "otext"}:
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


def test_generator_documents_node_edge_and_warp_features(tmp_path, monkeypatch):
    gen_docs = _load_script("gen_docs")
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    gen_docs.generate(tmp_path / "tf", tmp_path / "docs")

    node_page = tmp_path / "docs/features/sign/form.md"
    edge_page = tmp_path / "docs/features/edge/linked.md"
    otype_page = tmp_path / "docs/features/mixed/otype.md"
    oslots_page = tmp_path / "docs/features/edge/oslots.md"
    assert node_page.is_file()
    assert edge_page.is_file()
    assert otype_page.is_file()
    assert oslots_page.is_file()
    assert "populated values: `1`" in node_page.read_text(encoding="utf-8")
    assert "populated values: `1`" in edge_page.read_text(encoding="utf-8")
    index = (tmp_path / "docs/features.md").read_text(encoding="utf-8")
    assert "features/sign/form.md" in index
    assert "features/edge/linked.md" in index
    assert "features/mixed/otype.md" in index
    assert "features/edge/oslots.md" in index


def test_generator_is_idempotent_and_preserves_manual_regions(tmp_path, monkeypatch):
    gen_docs = _load_script("gen_docs")
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)
    page = docs / "features/sign/form.md"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "<!-- manual:begin interpretation -->\n<!-- manual:end -->",
            "<!-- manual:begin interpretation -->\nHuman caveat.\n<!-- manual:end -->",
        ),
        encoding="utf-8",
    )
    gen_docs.generate(tmp_path / "tf", docs)
    once = page.read_text(encoding="utf-8")
    gen_docs.generate(tmp_path / "tf", docs)
    twice = page.read_text(encoding="utf-8")
    assert once == twice
    assert "Human caveat." in twice


def test_generator_detects_deleted_manual_region(tmp_path, monkeypatch):
    gen_docs = _load_script("gen_docs")
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)
    page = docs / "features/sign/form.md"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "<!-- manual:begin interpretation -->\n<!-- manual:end -->\n",
            "",
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="manual region"):
        gen_docs.generate(tmp_path / "tf", docs)


def test_drift_check_preserves_manual_prose_and_rejects_stale_feature_pages(tmp_path, monkeypatch):
    gen_docs = _load_script("gen_docs")
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    docs = tmp_path / "docs"
    tf_dir = tmp_path / "tf"
    gen_docs.generate(tf_dir, docs)

    page = docs / "features/sign/form.md"
    page.write_text(
        page.read_text(encoding="utf-8").replace(
            "<!-- manual:begin interpretation -->\n<!-- manual:end -->",
            "<!-- manual:begin interpretation -->\nHuman caveat.\n<!-- manual:end -->",
        ),
        encoding="utf-8",
    )

    check_docs = _load_script("check_docs")
    monkeypatch.setattr(sys.modules["gen_docs"], "Fabric", _Fabric)
    check_docs.check(tf_dir, docs)

    stale = docs / "features/sign/stale.md"
    stale.write_text("# stale\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="feature set drift"):
        check_docs.check(tf_dir, docs)
