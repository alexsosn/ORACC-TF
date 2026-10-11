"""Isolated ETCSRI Text-Fabric conversion of source-verified corpusjson editions.

This is a real-data *vertical slice*, not a registered full ETCSRI dataset.
In particular, morph and morph2 are independent source annotations: their
internal segmentation is not parsed or falsely paired by this converter.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from tf.fabric import Fabric

from . import gdl, loader


class ETCSRISourceError(ValueError):
    """One source shape or identity cannot be represented without inference."""


@dataclass(frozen=True)
class ETCSRIBuildReport:
    documents: int
    words: int
    semantic_signs: int
    synthetic_slots: int
    lines: int
    sentences: int
    phrases: int
    determinatives: int
    tf_node_counts: dict[str, int]


@dataclass
class _Node:
    otype: str
    attrs: dict[str, str | int] = field(default_factory=dict)
    slots: set[int] = field(default_factory=set)
    parent: int | None = None


_TYPE_ORDER = (
    "document", "text", "discourse", "sentence", "phrase",
    "line", "word", "determinative",
)
_CHUNK_TYPES = frozenset({"text", "discourse", "sentence", "phrase"})


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _str_value(mapping: dict, name: str, *, where: str, required: bool = False) -> str | None:
    value = mapping.get(name)
    if value is None:
        if required:
            raise ETCSRISourceError(f"{where}: required field {name!r} is missing")
        return None
    if not isinstance(value, str) or (required and not value):
        raise ETCSRISourceError(f"{where}: field {name!r} must be a string")
    return value


def _add_text_features(attrs: dict[str, str | int], source: dict, fields: Iterable[str], *, where: str) -> None:
    for name in fields:
        value = _str_value(source, name, where=where)
        if value is not None:
            attrs[name] = value


def _load_source(path: Path) -> tuple[dict, bytes]:
    try:
        payload = path.read_bytes()
        edition = loader.load_edition(path)
    except (OSError, loader.SourceError) as exc:
        raise ETCSRISourceError(f"unusable ETCSRI source {path}: {exc}") from exc
    doc = edition.doc
    if doc.get("project") != "etcsri":
        raise ETCSRISourceError(f"{path}: expected project 'etcsri'")
    if doc.get("type") != "cdl":
        raise ETCSRISourceError(f"{path}: unknown document type")
    return doc, payload


def _save_tf(root: Path, nodes: list[_Node], slots: list[dict[str, str | int]],
             edges: dict[str, dict[int, set[int]]]) -> dict[str, int]:
    max_slot = len(slots)
    counts = Counter(node.otype for node in nodes)
    remap: dict[int, int] = {}
    next_node = max_slot + 1
    for otype in _TYPE_ORDER:
        for i, node in enumerate(nodes):
            if node.otype == otype:
                remap[i] = next_node
                next_node += 1
    if len(remap) != len(nodes):
        raise ETCSRISourceError("unsupported non-slot type in graph")

    node_features: dict[str, dict[int, str | int]] = defaultdict(dict)
    node_features["otype"].update({i: "sign" for i in range(1, max_slot + 1)})
    for slot, attrs in enumerate(slots, start=1):
        for feature, value in attrs.items():
            node_features[feature][slot] = value
    oslots: dict[int, set[int]] = {}
    for i, node in enumerate(nodes):
        if not node.slots:
            raise ETCSRISourceError(f"unanchored TF node {node.otype}: {node.attrs.get('source_id')}")
        tf_id = remap[i]
        node_features["otype"][tf_id] = node.otype
        oslots[tf_id] = set(node.slots)
        for feature, value in node.attrs.items():
            node_features[feature][tf_id] = value

    edge_features: dict[str, dict[int, set[int]]] = {"oslots": oslots}
    for edge_name, adjacency in edges.items():
        values: dict[int, set[int]] = {}
        for source, targets in adjacency.items():
            values[remap[source]] = {
                # det_sign points to sign slots; other edges point to non-slot nodes.
                t if edge_name == "det_sign" else remap[t] for t in targets
            }
        if values:
            edge_features[edge_name] = values

    # Advertised text formats should load in a sparse source subset.
    for name in ("utf8", "form", "morph", "morph2", "base", "line", "text_id"):
        node_features.setdefault(name, {})

    metadata: dict[str, dict[str, object]] = {
        "": {
            "name": "ETCSRI source-preserving TF vertical slice",
            "converter": "oracc-tf-etcsri",
            "version": "0.1.0",
        },
        "otext": {
            "sectionTypes": "document,line",
            "sectionFeatures": "text_id,line",
            "fmt:text-orig-full": "sign#{utf8}",
            "fmt:text-trans-full": "word#{form} ",
        },
        "otype": {"valueType": "str"},
        "oslots": {"valueType": "str"},
    }
    for feature in node_features:
        if feature not in metadata:
            metadata[feature] = {
                "valueType": "int" if feature == "synthetic" else "str",
                "description": f"ETCSRI preserved source feature: {feature}",
            }
    for feature in edge_features:
        if feature not in metadata:
            metadata[feature] = {
                "valueType": "str",
                "description": f"ETCSRI source relationship: {feature}",
            }

    root.mkdir(parents=True, exist_ok=True)
    tf = Fabric(locations=str(root), silent="deep")
    if not tf.save(
        nodeFeatures=dict(node_features),
        edgeFeatures=edge_features,
        metaData=metadata,
        silent="deep",
    ):
        raise ETCSRISourceError(f"Text-Fabric could not save ETCSRI graph at {root}")
    # Fabric inserts a wall-clock date in metadata headers; normalize for
    # byte-identical rebuilds of the same checked-in source and converter.
    for feature_file in sorted(root.glob("*.tf")):
        payload = feature_file.read_bytes()
        header, sep, body = payload.partition(b"\n\n")
        if not sep:
            raise ETCSRISourceError(f"TF feature missing header separator: {feature_file}")
        normalized = b"\n".join(
            line for line in header.split(b"\n")
            if not line.startswith(b"@dateWritten=")
        )
        if normalized != header:
            feature_file.write_bytes(normalized + sep + body)
    return dict(sorted({**counts, "sign": max_slot}.items()))


def build_tf(out_dir: Path | str, *, source_paths: Iterable[Path | str]) -> ETCSRIBuildReport:
    """Build source-grounded ETCSRI TF from explicitly named corpusjson files.

    Unknown source CDL/GDL shapes are errors. This function does not download,
    register or publish any corpus. Only validated source witnesses are accepted.
    """
    sources = sorted((Path(p) for p in source_paths), key=lambda p: p.as_posix())
    if not sources:
        raise ETCSRISourceError("ETCSRI vertical slice requires at least one source")
    target = Path(out_dir)
    if target.exists() and (not target.is_dir() or any(target.iterdir())):
        raise ETCSRISourceError(
            f"refusing non-empty ETCSRI TF output (would retain stale features): {target}"
        )
    nodes: list[_Node] = []
    slots: list[dict[str, str | int]] = []
    edges: dict[str, dict[int, set[int]]] = defaultdict(lambda: defaultdict(set))
    seen_docs: set[str] = set()
    counts: Counter[str] = Counter()
    semantic_signs = 0
    synthetic_slots = 0

    def node(otype: str, attrs: dict[str, str | int], parent: int | None = None) -> int:
        i = len(nodes)
        nodes.append(_Node(otype=otype, attrs=attrs, parent=parent))
        if parent is not None:
            edges["chunk_parent"][i].add(parent)
        return i

    for path in sources:
        doc, payload = _load_source(path)
        text_id = _str_value(doc, "textid", where=str(path), required=True)
        assert text_id is not None
        doc_key = f"etcsri:{text_id}"
        if doc_key in seen_docs:
            raise ETCSRISourceError(f"duplicate document key: {doc_key}")
        seen_docs.add(doc_key)
        # Preserve the source header separately from its CDL tree, including
        # the original project, source URL, licence URL and UTC source timestamp.
        # This is data provenance, not an assertion that a blanket reuse grant
        # resolves all edition-specific rights.
        source_meta = {key: value for key, value in doc.items() if key != "cdl"}
        doc_idx = node("document", {
            "document_key": doc_key, "text_id": text_id,
            "source_id": text_id, "source_sha256": sha256(payload).hexdigest(),
            "source_license": _str_value(doc, "license", where=text_id) or "",
            "source_url": _str_value(doc, "source", where=text_id) or "",
            "source_license_url": _str_value(doc, "license-url", where=text_id) or "",
            "source_timestamp": _str_value(doc, "UTC-timestamp", where=text_id) or "",
            "source_meta_json": _json(source_meta),
        })
        current_line: int | None = None
        chunks: list[int] = []
        word_ids: set[str] = set()
        chunk_ids: set[str] = set()
        sign_paths: set[str] = set()
        linkbase_seen = False

        def assign_slot(attrs: dict[str, str | int], word_idx: int | None = None) -> int:
            slot = len(slots) + 1
            slots.append({"document_key": doc_key, **attrs})
            nodes[doc_idx].slots.add(slot)
            for c in chunks:
                nodes[c].slots.add(slot)
            if current_line is not None:
                nodes[current_line].slots.add(slot)
            if word_idx is not None:
                nodes[word_idx].slots.add(slot)
            return slot

        def anchor_if_empty(index: int) -> None:
            nonlocal synthetic_slots
            if not nodes[index].slots:
                synthetic_slots += 1
                # Never ascribe visible script to a technical TF positional slot.
                nodes[index].slots.add(assign_slot({"synthetic": 1}))

        def visit(entry: object) -> None:
            nonlocal current_line, semantic_signs, synthetic_slots, linkbase_seen
            if not isinstance(entry, dict):
                raise ETCSRISourceError(f"{doc_key}: non-object CDL child")
            kind = entry.get("node")
            # ETCSRI includes separate top-level scholarly linksets in CDL.
            # Preserve source bytes as canonical JSON; they are not text/sign slots.
            if kind is None and "linkbase" in entry:
                if set(entry) != {"linkbase"} or chunks:
                    raise ETCSRISourceError(f"{doc_key}: unsupported linkbase location/shape")
                if linkbase_seen:
                    raise ETCSRISourceError(f"{doc_key}: duplicate linkbase record")
                linksets = entry["linkbase"]
                if not isinstance(linksets, list) or any(not isinstance(x, dict) for x in linksets):
                    raise ETCSRISourceError(f"{doc_key}: malformed linkbase list")
                nodes[doc_idx].attrs["linkbase_json"] = _json(linksets)
                linkbase_seen = True
                return
            if kind == "c":
                ctype = entry.get("type")
                if ctype not in _CHUNK_TYPES:
                    raise ETCSRISourceError(f"{doc_key}: unsupported chunk type {ctype!r}")
                source_id = _str_value(entry, "id", where=doc_key, required=True)
                assert source_id is not None
                if source_id in chunk_ids:
                    raise ETCSRISourceError(f"{doc_key}: duplicate chunk id {source_id}")
                chunk_ids.add(source_id)
                meta = {k: v for k, v in entry.items() if k != "cdl"}
                chunk_idx = node(ctype, {
                    "document_key": doc_key, "source_id": source_id,
                    "chunk_json": _json(meta),
                }, parent=chunks[-1] if chunks else doc_idx)
                chunks.append(chunk_idx)
                children = entry.get("cdl")
                if not isinstance(children, list):
                    raise ETCSRISourceError(f"{doc_key}:{source_id}: missing cdl list")
                for child in children:
                    visit(child)
                anchor_if_empty(chunk_idx)
                chunks.pop()
                return
            if kind == "d":
                if entry.get("type") != "line-start":
                    raise ETCSRISourceError(f"{doc_key}: unknown CDL marker {entry.get('type')!r}")
                if current_line is not None:
                    anchor_if_empty(current_line)
                line_ref = _str_value(entry, "ref", where=doc_key, required=True)
                assert line_ref is not None
                current_line = node("line", {
                    "document_key": doc_key, "source_id": line_ref,
                    "line": line_ref, "line_json": _json(entry),
                })
                # The line-start event has a source-chunk parent even when
                # no later word slots make that parentage inferable.
                if chunks:
                    edges["line_chunk"][current_line].add(chunks[-1])
                counts["line"] += 1
                return
            if kind != "l":
                raise ETCSRISourceError(f"{doc_key}: unknown CDL node {kind!r}")

            word_id = _str_value(entry, "id", where=doc_key, required=True)
            assert word_id is not None
            if word_id in word_ids:
                raise ETCSRISourceError(f"{doc_key}: duplicate word id {word_id}")
            word_ids.add(word_id)
            if current_line is None:
                raise ETCSRISourceError(f"{doc_key}: {word_id} precedes first line")
            f = entry.get("f")
            if not isinstance(f, dict):
                raise ETCSRISourceError(f"{doc_key}:{word_id}: missing f object")
            attrs: dict[str, str | int] = {
                "document_key": doc_key, "source_id": word_id,
                "f_json": _json(f), "word_json": _json(entry),
            }
            _add_text_features(
                attrs, f,
                ("base", "morph", "morph2", "form", "cf", "gw", "sense",
                 "norm", "pos", "epos", "lang"),
                where=word_id,
            )
            for name in ("para", "props"):
                if name in entry:
                    attrs[f"{name}_json"] = _json(entry[name])
            word_idx = node("word", attrs)
            edges["word_line"][word_idx].add(current_line)
            counts["word"] += 1
            entries = f.get("gdl")
            if not isinstance(entries, list):
                raise ETCSRISourceError(f"{doc_key}:{word_id}: expected GDL list")
            determinants: list[tuple[str, dict]] = []
            word_signs: dict[str, int] = {}
            try:
                classified = gdl.classify_tree(entries, word_id=word_id)
                for item in classified:
                    value = item.value
                    src_path = item.src_path
                    if item.disposition == gdl.Disposition.STRUCTURAL and "det" in value:
                        if value.get("det") != "semantic" or value.get("pos") not in {"pre", "post"}:
                            raise ETCSRISourceError(f"{doc_key}:{src_path}: unknown determinative metadata")
                        determinants.append((src_path, dict(value)))
                    if item.disposition != gdl.Disposition.SLOT:
                        continue
                    if src_path in sign_paths:
                        raise ETCSRISourceError(f"{doc_key}: duplicate GDL source path {src_path}")
                    sign_paths.add(src_path)
                    slot_attrs: dict[str, str | int] = {
                        "synthetic": 0,
                        "src_path": src_path,
                        "sign_json": _json(value),
                    }
                    for field in ("id", "utf8", "gdl_sign", "v", "s", "x"):
                        if field in value and value[field] is not None:
                            if not isinstance(value[field], str):
                                raise ETCSRISourceError(f"{doc_key}:{src_path}: invalid {field}")
                            slot_attrs["source_id" if field == "id" else field] = value[field]
                    word_signs[src_path] = assign_slot(slot_attrs, word_idx=word_idx)
                    semantic_signs += 1
            except gdl.UnknownGDLShape as exc:
                raise ETCSRISourceError(f"{doc_key}:{word_id}: unsupported GDL shape: {exc}") from exc
            for src_path, value in determinants:
                owned = {
                    slot for child_path, slot in word_signs.items()
                    if child_path.startswith(src_path + "/")
                }
                if not owned:
                    raise ETCSRISourceError(f"{doc_key}:{src_path}: empty determinative wrapper")
                det_idx = node("determinative", {
                    "document_key": doc_key, "src_path": src_path,
                    "det_kind": str(value["det"]), "det_pos": str(value["pos"]),
                    "det_json": _json(value),
                })
                nodes[det_idx].slots.update(owned)
                edges["det_sign"][det_idx].update(owned)
                edges["det_word"][det_idx].add(word_idx)
                counts["determinative"] += 1
            if not nodes[word_idx].slots:
                synthetic_slots += 1
                assign_slot({"synthetic": 1}, word_idx=word_idx)

        if not isinstance(doc.get("cdl"), list):
            raise ETCSRISourceError(f"{doc_key}: document lacks cdl list")
        for c in doc["cdl"]:
            visit(c)
        if current_line is not None:
            anchor_if_empty(current_line)
        if not nodes[doc_idx].slots:
            raise ETCSRISourceError(f"{doc_key}: source edition has no textual slots")
        counts["document"] += 1

    # Frozen TF type/slot identity; no RIAO/RINAP feature mapping is touched.
    emitted_types = _save_tf(Path(out_dir), nodes, slots, edges)
    return ETCSRIBuildReport(
        documents=counts["document"],
        words=counts["word"],
        semantic_signs=semantic_signs,
        synthetic_slots=synthetic_slots,
        lines=counts["line"],
        sentences=emitted_types.get("sentence", 0),
        phrases=emitted_types.get("phrase", 0),
        determinatives=counts["determinative"],
        tf_node_counts=emitted_types,
    )
