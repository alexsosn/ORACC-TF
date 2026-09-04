"""Integrated RIAO+RINAP Text-Fabric build and M6 invariant report.

M0--M5 deliberately keep source interpretation in small independently tested
modules. M6 is the first place where those views are joined into an actual
Text-Fabric graph. ``sign`` is the TF slot type.

Text-Fabric 13.1 has a hard warp invariant: every non-slot node in ``oslots``
must map to at least one slot. ORACC legitimately contains source entities with
zero sign extent (notably 295 words and 233 metadata-only documents in this
snapshot). Inventing or borrowing a sign would corrupt the source model, so
zero-span entities are omitted from the TF warp and written losslessly to a
deterministic sidecar together with any relation edges crossing that boundary.
Source cardinalities in :class:`CorpusBuildReport` always include both layers.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tf.fabric import Fabric

from . import TF_VERSION, lexemes, loader, metadata, paths, sections, words


ZERO_SPAN_SCHEMA = "oracc-tf-zero-span-v1"
ZERO_SPAN_FILENAME = "zero-span.json"
ZERO_SPAN_REASON = (
    "Text-Fabric warp requires every non-slot node to map to at least one sign slot; "
    "zero-span ORACC source entities are preserved here rather than assigned "
    "fabricated or borrowed slots."
)


class CorpusBuildError(RuntimeError):
    """The joined TF graph cannot be built without violating source invariants."""


@dataclass(frozen=True)
class CorpusBuildReport:
    """Measurements made while producing one joined TF dataset."""

    documents: int
    populated_documents: int
    stub_documents: int
    unique_document_keys: int
    document_key_collisions: int
    words: int
    signs: int
    unicode_signs: int
    slotless_words: int
    lines: int
    lexemes: int
    sign_word_membership_errors: int
    word_line_membership_errors: int
    section_path_errors: int
    tf_node_counts: dict[str, int]
    zero_span_counts: dict[str, int]

    @property
    def unicode_coverage(self) -> float:
        return self.unicode_signs / self.signs if self.signs else 0.0

    @property
    def tf_documents(self) -> int:
        return self.tf_node_counts.get("document", 0)

    @property
    def tf_words(self) -> int:
        return self.tf_node_counts.get("word", 0)

    @property
    def tf_lines(self) -> int:
        return self.tf_node_counts.get("line", 0)

    @property
    def tf_lexemes(self) -> int:
        return self.tf_node_counts.get("lex", 0)

    @property
    def zero_span_nodes(self) -> int:
        return sum(self.zero_span_counts.values())

    @property
    def zero_span_documents(self) -> int:
        return self.zero_span_counts.get("document", 0)

    @property
    def zero_span_words(self) -> int:
        return self.zero_span_counts.get("word", 0)

    def report(self) -> str:
        tf_counts = ", ".join(
            f"{otype}={count}" for otype, count in sorted(self.tf_node_counts.items())
        )
        zero_counts = ", ".join(
            f"{otype}={count}" for otype, count in sorted(self.zero_span_counts.items())
        ) or "none"
        return "\n".join((
            f"documents                  : {self.documents:>8,}",
            f"populated documents        : {self.populated_documents:>8,}",
            f"stub documents             : {self.stub_documents:>8,}",
            f"unique document keys       : {self.unique_document_keys:>8,}",
            f"document key collisions    : {self.document_key_collisions:>8,}",
            f"words                      : {self.words:>8,}",
            f"signs                      : {self.signs:>8,}",
            f"unicode signs              : {self.unicode_signs:>8,} ({self.unicode_coverage:.4%})",
            f"slotless words             : {self.slotless_words:>8,}",
            f"lines                      : {self.lines:>8,}",
            f"lexemes                    : {self.lexemes:>8,}",
            f"sign→word errors           : {self.sign_word_membership_errors:>8,}",
            f"word→line errors           : {self.word_line_membership_errors:>8,}",
            f"section path errors        : {self.section_path_errors:>8,}",
            f"TF node counts             : {tf_counts}",
            f"zero-span sidecar counts   : {zero_counts}",
        ))


@dataclass(frozen=True)
class _MaterialisedGraph:
    node_features: dict[str, dict[int, str | int]]
    edge_features: dict[str, dict[int, set[int]]]
    meta_data: dict[str, dict[str, object]]
    sidecar: dict[str, object]
    tf_node_counts: dict[str, int]
    zero_span_counts: dict[str, int]


class _Graph:
    """Provisional graph remapped to Text-Fabric node intervals at save time."""

    TYPE_ORDER = (
        "document",
        "face",
        "column",
        "line",
        "chunk",
        "phrase",
        "word",
        "lex",
    )

    def __init__(self) -> None:
        self.next_non_slot = 1
        self.non_slot_otype: dict[int, str] = {}
        self.non_slot_oslots: dict[int, set[int]] = {}
        self.slot_features: dict[str, dict[int, str | int]] = defaultdict(dict)
        self.node_features: dict[str, dict[int, str | int]] = defaultdict(dict)
        self.edges: dict[str, dict[int, set[int]]] = defaultdict(dict)

    def node(self, otype: str, oslots: Iterable[int] = ()) -> int:
        node = self.next_non_slot
        self.next_non_slot += 1
        self.non_slot_otype[node] = otype
        self.non_slot_oslots[node] = set(oslots)
        return node

    def feature(self, node: int, **features: object) -> None:
        for name, value in features.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = int(value)
            if not isinstance(value, (str, int)):
                value = _json(value)
            self.node_features[name][node] = value

    def slot_feature(self, slot: int, **features: object) -> None:
        for name, value in features.items():
            if value is None:
                continue
            if isinstance(value, bool):
                value = int(value)
            if not isinstance(value, (str, int)):
                value = _json(value)
            self.slot_features[name][slot] = value

    def edge(self, name: str, source: int, target: int) -> None:
        self.edges[name].setdefault(source, set()).add(target)

    def add_oslots(self, node: int, slots: Iterable[int]) -> None:
        self.non_slot_oslots[node].update(slots)

    def _node_features(self, node: int) -> dict[str, str | int]:
        return {
            name: data[node]
            for name, data in self.node_features.items()
            if node in data
        }

    def _stable_key(self, node: int) -> str:
        """Return a deterministic source-facing identity for sidecar relations."""
        otype = self.non_slot_otype[node]
        features = self._node_features(node)
        if otype == "document":
            identity = features.get("document") or features.get("document_key")
            if not identity:
                raise CorpusBuildError("zero-span document lacks a stable document key")
            return f"document:{identity}"
        if otype == "lex":
            identity = features.get("lexeme")
            if not identity:
                raise CorpusBuildError("zero-span lexeme lacks a stable lexeme key")
            return f"lex:{identity}"

        source_id = features.get("source_id")
        document_key = features.get("document_key")
        if not source_id or not document_key:
            raise CorpusBuildError(
                f"zero-span {otype} node lacks source_id/document_key for stable identity"
            )
        return f"{otype}:{document_key}:{source_id}"

    def _node_remap(self, max_slot: int, included: set[int]) -> dict[int, int]:
        """Put every included non-slot otype in one contiguous TF interval."""
        groups: dict[str, list[int]] = defaultdict(list)
        for node, otype in self.non_slot_otype.items():
            if node in included:
                groups[otype].append(node)

        ordered_types = [otype for otype in self.TYPE_ORDER if otype in groups]
        ordered_types.extend(sorted(set(groups) - set(ordered_types)))

        remap: dict[int, int] = {}
        actual = max_slot + 1
        for otype in ordered_types:
            for provisional in groups[otype]:
                remap[provisional] = actual
                actual += 1
        return remap

    def materialise(self, max_slot: int) -> _MaterialisedGraph:
        all_nodes = set(self.non_slot_otype)
        included = {
            node for node in all_nodes
            if self.non_slot_oslots.get(node)
        }
        omitted = all_nodes - included
        remap = self._node_remap(max_slot, included)

        tf_counts = Counter(self.non_slot_otype[node] for node in included)
        tf_counts["sign"] = max_slot
        zero_counts = Counter(self.non_slot_otype[node] for node in omitted)

        stable_keys = {node: self._stable_key(node) for node in all_nodes}
        if len(set(stable_keys.values())) != len(stable_keys):
            duplicates = Counter(stable_keys.values())
            repeated = sorted(key for key, count in duplicates.items() if count > 1)
            raise CorpusBuildError(
                f"non-unique stable node keys: {repeated[:5]!r}"
            )

        otype: dict[int, str] = {slot: "sign" for slot in range(1, max_slot + 1)}
        otype.update({
            remap[node]: self.non_slot_otype[node]
            for node in included
        })

        node_features: dict[str, dict[int, str | int]] = {"otype": otype}
        all_names = set(self.slot_features) | set(self.node_features)
        for name in all_names:
            data: dict[int, str | int] = {}
            data.update(self.slot_features.get(name, {}))
            data.update({
                remap[node]: value
                for node, value in self.node_features.get(name, {}).items()
                if node in included
            })
            if data:
                node_features[name] = data

        edge_features: dict[str, dict[int, set[int]]] = {
            "oslots": {
                remap[node]: set(self.non_slot_oslots[node])
                for node in included
            }
        }
        side_edges: list[dict[str, object]] = []
        for name, data in self.edges.items():
            tf_data: dict[int, set[int]] = {}
            for source, targets in data.items():
                included_targets = {target for target in targets if target in included}
                if source in included and included_targets:
                    tf_data[remap[source]] = {
                        remap[target] for target in included_targets
                    }

                boundary_targets = (
                    set(targets)
                    if source in omitted
                    else {target for target in targets if target in omitted}
                )
                if boundary_targets:
                    side_edges.append({
                        "feature": name,
                        "source": stable_keys[source],
                        "targets": sorted(stable_keys[target] for target in boundary_targets),
                    })
            if tf_data:
                edge_features[name] = tf_data

        side_nodes = [
            {
                "key": stable_keys[node],
                "otype": self.non_slot_otype[node],
                "features": dict(sorted(self._node_features(node).items())),
            }
            for node in sorted(omitted, key=lambda item: stable_keys[item])
        ]
        side_edges.sort(
            key=lambda edge: (
                str(edge["feature"]),
                str(edge["source"]),
                tuple(edge["targets"]),
            )
        )
        sidecar: dict[str, object] = {
            "schema": ZERO_SPAN_SCHEMA,
            "reason": ZERO_SPAN_REASON,
            "nodes": side_nodes,
            "edges": side_edges,
        }

        meta_data: dict[str, dict[str, object]] = {
            "": {
                "name": "ORACC-TF RIAO + RINAP",
                "converter": "oracc-tf",
                "version": TF_VERSION,
            },
            "otext": {
                "sectionTypes": "document,face,line",
                "sectionFeatures": "document,face,line",
            },
            "otype": {"valueType": "str"},
            "oslots": {"valueType": "str"},
        }
        int_features = {"catalogue_present", "lemmaknown", "populated", "synthetic"}
        for name in set(node_features) - {"otype"}:
            meta_data[name] = {
                "valueType": "int" if name in int_features else "str"
            }
        for name in set(edge_features) - {"oslots"}:
            meta_data[name] = {"valueType": "str"}

        return _MaterialisedGraph(
            node_features=node_features,
            edge_features=edge_features,
            meta_data=meta_data,
            sidecar=sidecar,
            tf_node_counts=dict(sorted(tf_counts.items())),
            zero_span_counts=dict(sorted(zero_counts.items())),
        )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _source_gdl(word: words.WordRecord) -> str | None:
    if "gdl" not in word.features:
        return None
    return _json(word.features["gdl"])


def _catalogue_feature_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return _json(value)


_CATALOGUE_FEATURES = (
    "designation",
    "genre",
    "subgenre",
    "period",
    "provenience",
    "language",
    "supergenre",
    "ruler",
    "object_type",
    "material",
    "script",
    "exemplars",
    "primary_publication",
    "pleiades_id",
    "pleiades_coord",
    "cdli_id",
    "collection",
)


def _add_section_features(
    graph: _Graph,
    node: int,
    source: sections.SectionNode,
    *,
    document_key: str,
) -> None:
    graph.feature(
        node,
        source_id=source.source_id,
        document_key=document_key,
        label=source.label,
        ref=source.ref,
        synthetic=source.synthetic,
        chunk_type=source.chunk_type,
        chunk_subtype=source.chunk_subtype,
        implicit=source.implicit,
    )


def _write_zero_span(out_dir: Path, sidecar: dict[str, object]) -> None:
    path = out_dir / ZERO_SPAN_FILENAME
    path.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_zero_span(out_dir: Path | str) -> dict[str, object]:
    """Load and minimally validate the deterministic zero-span sidecar."""
    path = Path(out_dir) / ZERO_SPAN_FILENAME
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorpusBuildError(f"cannot read zero-span sidecar {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != ZERO_SPAN_SCHEMA:
        raise CorpusBuildError(f"unsupported zero-span sidecar schema in {path}")
    if not isinstance(data.get("nodes"), list) or not isinstance(data.get("edges"), list):
        raise CorpusBuildError(f"invalid zero-span sidecar structure in {path}")
    return data


def build_tf(
    out_dir: Path | str,
    *,
    editions: Iterable[loader.Edition],
    metadata_index: metadata.MetadataIndex,
) -> CorpusBuildReport:
    """Build one joined TF dataset plus the lossless zero-span sidecar."""
    graph = _Graph()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    next_slot = 1
    document_count = 0
    populated_count = 0
    stub_count = 0
    word_count = 0
    slotless_words = 0
    unicode_signs = 0
    line_count = 0
    word_line_errors = 0
    section_path_errors = 0
    key_counts: Counter[str] = Counter()
    sign_word_memberships: Counter[int] = Counter()
    lex_nodes: dict[lexemes.LexemeKey, int] = {}

    for edition in editions:
        document_count += 1
        key_counts[edition.key] += 1
        if edition.populated:
            populated_count += 1
        else:
            stub_count += 1

        section_view = sections.walk_document(edition.doc)
        source_words = list(words.iter_words(edition.doc, start_slot=next_slot))
        if len(source_words) != edition.word_count:
            raise CorpusBuildError(
                f"{edition.key}: loader says {edition.word_count} words "
                f"but M2 yielded {len(source_words)}"
            )

        by_word = {word.source_id: word for word in source_words}
        if len(by_word) != len(source_words):
            raise CorpusBuildError(f"{edition.key}: duplicate source word ids")

        document_slots: set[int] = set()
        for word in source_words:
            slots = set(word.slot_ids)
            document_slots.update(slots)
            if not slots:
                slotless_words += 1
            for slot, sign in zip(word.slot_ids, word.signs, strict=True):
                sign_word_memberships[slot] += 1
                utf8 = sign.value.get("utf8")
                if isinstance(utf8, str) and utf8:
                    unicode_signs += 1
                graph.slot_feature(
                    slot,
                    document_key=edition.key,
                    word_id=word.source_id,
                    src_path=sign.src_path,
                    utf8=utf8 if isinstance(utf8, str) else None,
                    sign_json=_json(sign.value),
                    gdl_id=sign.value.get("id"),
                    gdl_form=sign.value.get("form"),
                    gdl_sexified=sign.value.get("sexified"),
                )
            next_slot = word.slot_end

        joined = metadata.join_edition(edition, metadata_index)
        document_node = graph.node("document", document_slots)
        graph.feature(
            document_node,
            document=edition.key,
            document_key=edition.key,
            source_id=edition.text_id,
            text_id=edition.text_id,
            subproject=edition.subproject,
            populated=int(edition.populated),
            catalogue_present=int(joined.catalogue_present),
            catalogue_json=_json(joined.catalogue),
            license=joined.license,
            license_url=joined.license_url,
            license_type=joined.license_type,
        )
        for name in _CATALOGUE_FEATURES:
            graph.feature(
                document_node,
                **{name: _catalogue_feature_value(joined.catalogue.get(name))},
            )

        face_nodes: dict[str, int] = {}
        column_nodes: dict[str, int] = {}
        line_nodes: dict[str, int] = {}
        line_sources = {line.source_id: line for line in section_view.lines}

        for face in section_view.faces:
            if face.source_id in face_nodes:
                raise CorpusBuildError(f"{edition.key}: duplicate face id {face.source_id!r}")
            node = graph.node("face")
            face_nodes[face.source_id] = node
            _add_section_features(graph, node, face, document_key=edition.key)
            graph.feature(node, face=face.source_id)
            graph.edge("face_document", node, document_node)

        for column in section_view.columns:
            if column.source_id in column_nodes:
                raise CorpusBuildError(
                    f"{edition.key}: duplicate column id {column.source_id!r}"
                )
            node = graph.node("column")
            column_nodes[column.source_id] = node
            _add_section_features(graph, node, column, document_key=edition.key)
            graph.feature(node, column_id=column.source_id)
            if column.face_id is None or column.face_id not in face_nodes:
                if edition.populated:
                    section_path_errors += 1
            else:
                graph.edge("column_face", node, face_nodes[column.face_id])

        for line in section_view.lines:
            line_count += 1
            if line.source_id in line_nodes:
                raise CorpusBuildError(f"{edition.key}: duplicate line id {line.source_id!r}")
            slots = {
                slot
                for word_id in line.word_ids
                for slot in by_word[word_id].slot_ids
            }
            node = graph.node("line", slots)
            line_nodes[line.source_id] = node
            _add_section_features(graph, node, line, document_key=edition.key)
            graph.feature(node, line=line.source_id)

            if line.face_id is None or line.face_id not in face_nodes:
                if edition.populated:
                    section_path_errors += 1
            else:
                graph.add_oslots(face_nodes[line.face_id], slots)
                graph.edge("line_face", node, face_nodes[line.face_id])
            if line.column_id is not None:
                if line.column_id not in column_nodes:
                    if edition.populated:
                        section_path_errors += 1
                else:
                    graph.add_oslots(column_nodes[line.column_id], slots)
                    graph.edge("line_column", node, column_nodes[line.column_id])

        for chunk in section_view.chunks:
            slots = {
                slot
                for word_id in chunk.word_ids
                for slot in by_word[word_id].slot_ids
            }
            node = graph.node("chunk", slots)
            _add_section_features(graph, node, chunk, document_key=edition.key)

        for phrase in section_view.phrases:
            slots = {
                slot
                for word_id in phrase.word_ids
                for slot in by_word[word_id].slot_ids
            }
            node = graph.node("phrase", slots)
            _add_section_features(graph, node, phrase, document_key=edition.key)

        section_words = section_view.word_to_line
        word_line_errors += len(set(section_words) ^ set(by_word))

        for word in source_words:
            word_count += 1
            slots = set(word.slot_ids)
            word_node = graph.node("word", slots)
            graph.feature(
                word_node,
                source_id=word.source_id,
                document_key=edition.key,
                ref=word.ref,
                frag=word.frag,
                form=word.form,
                lang=word.lang,
                cf=word.cf,
                gw=word.gw,
                sense=word.sense,
                norm=word.norm,
                pos=word.pos,
                epos=word.epos,
                inst=word.inst,
                sig=word.sig,
                lemmaknown=word.lemmaknown,
                gdl_json=_source_gdl(word),
            )

            line_id = section_words.get(word.source_id)
            if line_id is not None and line_id in line_nodes:
                graph.edge("word_line", word_node, line_nodes[line_id])
                line_source = line_sources[line_id]
                if line_source.face_id not in face_nodes and edition.populated:
                    section_path_errors += 1
            elif edition.populated:
                section_path_errors += 1

            for key in lexemes.keys_for_word(word):
                lex_node = lex_nodes.get(key)
                if lex_node is None:
                    lex_node = graph.node("lex")
                    lex_nodes[key] = lex_node
                    graph.feature(
                        lex_node,
                        lexeme=_json([key.lang, key.cf, key.gw, key.pos]),
                        lang=key.lang,
                        cf=key.cf,
                        gw=key.gw,
                        pos=key.pos,
                    )
                graph.add_oslots(lex_node, slots)
                graph.edge("word_lex", word_node, lex_node)

    max_slot = next_slot - 1
    collision_count = sum(count - 1 for count in key_counts.values() if count > 1)
    membership_errors = (
        sum(count != 1 for count in sign_word_memberships.values())
        + max_slot
        - len(sign_word_memberships)
    )

    if collision_count:
        raise CorpusBuildError(
            f"qualified document keys are not unique: {collision_count} collisions"
        )
    if max_slot == 0:
        raise CorpusBuildError(
            "Text-Fabric warp cannot be emitted without at least one sign slot"
        )

    materialised = graph.materialise(max_slot)
    tf = Fabric(locations=str(out_dir), silent="deep")
    if not tf.save(
        nodeFeatures=materialised.node_features,
        edgeFeatures=materialised.edge_features,
        metaData=materialised.meta_data,
        silent="deep",
    ):
        raise CorpusBuildError(f"Text-Fabric rejected generated graph in {out_dir}")
    _write_zero_span(out_dir, materialised.sidecar)

    return CorpusBuildReport(
        documents=document_count,
        populated_documents=populated_count,
        stub_documents=stub_count,
        unique_document_keys=len(key_counts),
        document_key_collisions=collision_count,
        words=word_count,
        signs=max_slot,
        unicode_signs=unicode_signs,
        slotless_words=slotless_words,
        lines=line_count,
        lexemes=len(lex_nodes),
        sign_word_membership_errors=membership_errors,
        word_line_membership_errors=word_line_errors,
        section_path_errors=section_path_errors,
        tf_node_counts=materialised.tf_node_counts,
        zero_span_counts=materialised.zero_span_counts,
    )


def build_full_tf(
    out_dir: Path | str,
    *,
    data: Path = paths.DATA,
) -> CorpusBuildReport:
    """Build the complete parseable RIAO+RINAP joined corpus."""
    data = Path(data)
    metadata_index = metadata.load_index(data)
    editions = loader.iter_editions(data, skip_unreadable=True)
    return build_tf(out_dir, editions=editions, metadata_index=metadata_index)


def load_tf(out_dir: Path | str):
    """Load a generated dataset with the real Text-Fabric API."""
    tf = Fabric(locations=str(Path(out_dir)), silent="deep")
    good = tf.loadAll(silent="deep")
    if not good or tf.api is None:
        raise CorpusBuildError(f"Text-Fabric could not load generated graph in {out_dir}")
    return tf.api