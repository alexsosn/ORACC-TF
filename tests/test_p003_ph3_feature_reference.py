from array import array
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


def _load_gen_docs():
    spec = spec_from_file_location("gen_docs_ph3", Path("scripts/gen_docs.py"))
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules["gen_docs_ph3"] = module
    spec.loader.exec_module(module)
    return module


class _Feature:
    def __init__(self, description, data):
        self.meta = {"description": description, "valueType": "str"}
        self._data = list(data)

    def items(self):
        yield from self._data


class _Otype:
    meta = {"description": "Text-Fabric node type.", "valueType": "str"}

    def __init__(self, types):
        self._types = dict(types)

    def v(self, node):
        return self._types[node]

    def items(self):
        yield from sorted(self._types.items())


class _Api:
    def __init__(self):
        types = {
            1: "sign", 2: "sign", 3: "sign",
            10: "word", 11: "word",
            20: "lex", 21: "lex", 22: "lex",
        }
        self.F = type("F", (), {})()
        self.F.otype = _Otype(types)
        self._node = {
            "form": _Feature("Surface form.", [(1, "a"), (2, "b"), (3, "a")]),
        }
        self._edge = {
            "linked": _Feature("Word to lexeme.", [(10, {20, 21}), (11, {22})]),
        }

    def Fall(self):
        return ["form"]

    def Eall(self):
        return ["linked"]

    def Fs(self, name):
        return self._node[name]

    def Es(self, name):
        return self._edge[name]


class _Fabric:
    def __init__(self, *args, **kwargs):
        self.api = _Api()

    def loadAll(self, **kwargs):
        return True


def test_node_feature_page_has_derived_value_domain_and_frequency(tmp_path, monkeypatch):
    gen_docs = _load_gen_docs()
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)

    text = (docs / "features/sign/form.md").read_text(encoding="utf-8")
    assert "- distinct values: `2`" in text
    assert "## Value frequencies" in text
    assert "| `a` | 2 |" in text
    assert "| `b` | 1 |" in text
    assert text.index("| `a` | 2 |") < text.index("| `b` | 1 |")


def test_high_cardinality_node_domain_is_bounded_and_deterministic(tmp_path, monkeypatch):
    gen_docs = _load_gen_docs()

    class ManyApi(_Api):
        def __init__(self):
            super().__init__()
            self.F.otype = _Otype({node: "word" for node in range(1, 23)})
            self._node = {
                "sig": _Feature("Occurrence signature.", [(i, f"v{i:02d}") for i in range(1, 23)])
            }

        def Fall(self):
            return ["sig"]

    class ManyFabric(_Fabric):
        def __init__(self, *args, **kwargs):
            self.api = ManyApi()

    monkeypatch.setattr(gen_docs, "Fabric", ManyFabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)
    text = (docs / "features/word/sig.md").read_text(encoding="utf-8")

    assert "- distinct values: `22`" in text
    assert "Showing the 20 most frequent values" in text
    assert text.count("| `v") == 20
    assert "| `v21`" not in text
    assert "| `v22`" not in text


def test_long_frequency_values_are_bounded_with_stable_digest(tmp_path, monkeypatch):
    gen_docs = _load_gen_docs()
    long_value = "x" * 500

    class LongApi(_Api):
        def __init__(self):
            super().__init__()
            self.F.otype = _Otype({1: "document"})
            self._node = {"catalogue_json": _Feature("Catalogue JSON.", [(1, long_value)])}

        def Fall(self):
            return ["catalogue_json"]

        def Eall(self):
            return []

    class LongFabric(_Fabric):
        def __init__(self, *args, **kwargs):
            self.api = LongApi()

    monkeypatch.setattr(gen_docs, "Fabric", LongFabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)
    text = (docs / "features/document/catalogue_json.md").read_text(encoding="utf-8")
    value_row = next(line for line in text.splitlines() if line.startswith("| `x"))
    assert len(value_row) < 220
    assert "sha256:" in value_row
    assert long_value not in value_row


def test_edge_feature_page_has_source_target_types_links_and_degree_frequency(tmp_path, monkeypatch):
    gen_docs = _load_gen_docs()
    monkeypatch.setattr(gen_docs, "Fabric", _Fabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)

    text = (docs / "features/edge/linked.md").read_text(encoding="utf-8")
    assert "- source node types: `word`" in text
    assert "- target node types: `lex`" in text
    assert "- populated sources: `2`" in text
    assert "- links: `3`" in text
    assert "## Out-degree frequencies" in text
    assert "| 1 | 1 |" in text
    assert "| 2 | 1 |" in text


def test_edge_targets_accept_text_fabric_array_storage(tmp_path, monkeypatch):
    gen_docs = _load_gen_docs()

    class ArrayApi(_Api):
        def __init__(self):
            super().__init__()
            self._edge = {
                "linked": _Feature("Word to lexeme.", [(10, array("I", [20, 21]))]),
            }

    class ArrayFabric(_Fabric):
        def __init__(self, *args, **kwargs):
            self.api = ArrayApi()

    monkeypatch.setattr(gen_docs, "Fabric", ArrayFabric)
    docs = tmp_path / "docs"
    gen_docs.generate(tmp_path / "tf", docs)
    text = (docs / "features/edge/linked.md").read_text(encoding="utf-8")
    assert "- links: `2`" in text
    assert "- target node types: `lex`" in text
    assert "| 2 | 1 |" in text
