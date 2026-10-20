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
    "line", "nontext_span", "nonword_marker", "word", "determinative",
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


def _nonx_attrs(entry: dict, *, where: str) -> dict[str, str]:
    """Source-native ETCSRI nonx attributes; no invented missing text.

    Source census 38166385264 and real shape survey 38235200315 attest
    694 events: positive integers, estimated integer ranges, or n/rest/end extent, optional scope, two strict
    flags and six distinct states. Preserve their original lexical strings.
    """
    allowed = {"node", "type", "ref", "scope", "state", "extent", "strict"}
    required = {"node", "type", "ref", "state", "extent", "strict"}
    if not required <= set(entry) or set(entry) - allowed:
        raise ETCSRISourceError(f"{where}: malformed nonx marker fields")
    if entry.get("node") != "d" or entry.get("type") != "nonx":
        raise ETCSRISourceError(f"{where}: expected nonx CDL marker")
    ref = _str_value(entry, "ref", where=where, required=True)
    scope = _str_value(entry, "scope", where=where)
    state = _str_value(entry, "state", where=where, required=True)
    extent = _str_value(entry, "extent", where=where, required=True)
    strict = _str_value(entry, "strict", where=where, required=True)
    if scope not in (None, "line", "column", "case"):
        raise ETCSRISourceError(f"{where}: unsupported nonx scope {scope!r}")
    if state not in ("missing", "blank", "ruling", "traces", "illegible", "erased"):
        raise ETCSRISourceError(f"{where}: unsupported nonx state {state!r}")
    if strict not in ("0", "1"):
        raise ETCSRISourceError(f"{where}: unsupported nonx strict flag {strict!r}")
    # Q001123 has e.g. extent="5-6" and "9-10". Preserve the *string*
    # as an uncertainty interval; never invent positional words or lines.
    bounds = extent.split("-")
    numeric = extent.isascii() and extent.isdecimal() and int(extent) > 0
    estimated_range = (
        len(bounds) == 2
        and all(part.isascii() and part.isdecimal() and int(part) > 0 for part in bounds)
        and int(bounds[0]) < int(bounds[1])
    )
    if not (extent in ("rest", "n", "end") or numeric or estimated_range):
        raise ETCSRISourceError(f"{where}: invalid nonx extent {extent!r}")
    assert ref is not None and state is not None and extent is not None and strict is not None
    attrs = {
        "source_id": ref, "marker_type": "nonx", "marker_json": _json(entry),
        "gap_state": state, "gap_extent": extent, "gap_strict": strict,
    }
    if scope is not None:
        attrs["gap_scope"] = scope
    return attrs


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
        line_ids: set[str] = set()
        missing_refs: set[str] = set()
        nonword_marker_count = 0
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
            if nodes[index].slots:
                return
            synthetic_slots += 1
            # Anchors for empty source spans must belong to their *source*
            # hierarchy. The mutable traversal stack/current_line might
            # already refer to the next sentence/line when this one closes.
            slot = len(slots) + 1
            slots.append({"document_key": doc_key, "synthetic": 1})
            nodes[doc_idx].slots.add(slot)
            nodes[index].slots.add(slot)
            if nodes[index].otype == "line":
                parents = edges["line_chunk"].get(index, set())
            elif nodes[index].otype in _CHUNK_TYPES or nodes[index].otype in {"nontext_span", "nonword_marker"}:
                parents = {nodes[index].parent} if nodes[index].parent is not None else set()
            else:
                raise ETCSRISourceError("unexpected empty-anchor owner")
            for parent in parents:
                while parent is not None:
                    nodes[parent].slots.add(slot)
                    parent = nodes[parent].parent

        def visit(entry: object) -> None:
            nonlocal current_line, semantic_signs, synthetic_slots, linkbase_seen, nonword_marker_count
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
                if entry.get("type") == "nonw":
                    # Real Q001794 and Q001870 records are CDL events, not
                    # source words, signs or missing-line extent markers.
                    if set(entry) - {"node", "type", "ref", "lang"} or "ref" not in entry:
                        raise ETCSRISourceError(
                            f"{doc_key}: unsupported nonw marker fields"
                        )
                    ref = entry["ref"]
                    if not isinstance(ref, str):
                        raise ETCSRISourceError(
                            f"{doc_key}: nonw ref must be a string (empty is attested)"
                        )
                    lang = entry.get("lang")
                    if lang is not None and (not isinstance(lang, str) or not lang):
                        raise ETCSRISourceError(f"{doc_key}: invalid nonw lang")
                    nonword_marker_count += 1
                    attrs: dict[str, str | int] = {
                        "document_key": doc_key,
                        "marker_type": "nonw",
                        "marker_json": _json(entry),
                        "source_ref_json": _json(ref),
                        "marker_ordinal": nonword_marker_count,
                    }
                    if ref:
                        attrs["source_id"] = ref
                    if lang is not None:
                        attrs["marker_lang"] = lang
                    idx = node(
                        "nonword_marker", attrs,
                        parent=chunks[-1] if chunks else doc_idx,
                    )
                    anchor_if_empty(idx)
                    counts["nonword_marker"] += 1
                    return
                if entry.get("type") == "nonx":
                    native = _nonx_attrs(entry, where=doc_key)
                    marker_ref = native["source_id"]
                    if marker_ref in missing_refs:
                        raise ETCSRISourceError(
                            f"{doc_key}: duplicate nonx source reference {marker_ref!r}"
                        )
                    missing_refs.add(marker_ref)
                    gap_idx = node(
                        "nontext_span", {"document_key": doc_key, **native},
                        parent=chunks[-1] if chunks else doc_idx,
                    )
                    # One nontextual anchor under its source chunk, never
                    # fabricated rows/signs for the source extent notation.
                    anchor_if_empty(gap_idx)
                    counts["nontext_span"] += 1
                    return
                if entry.get("type") != "line-start":
                    raise ETCSRISourceError(f"{doc_key}: unknown CDL marker {entry.get('type')!r}")
                if current_line is not None:
                    anchor_if_empty(current_line)
                line_ref = _str_value(entry, "ref", where=doc_key, required=True)
                assert line_ref is not None
                if line_ref in line_ids:
                    raise ETCSRISourceError(f"{doc_key}: duplicate line reference {line_ref}")
                line_ids.add(line_ref)
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
