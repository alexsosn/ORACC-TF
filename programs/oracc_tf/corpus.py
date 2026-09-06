"""Integrated RIAO+RINAP Text-Fabric build and M6 invariant report.

M0--M5 deliberately keep source interpretation in small independently tested
modules. M6 is the first place where those views are joined into an actual
Text-Fabric graph. ``sign`` is the TF slot type.

Text-Fabric requires every non-slot warp node to map to at least one slot.
ORACC legitimately contains textual entities with no semantic sign extent.
Following the accepted project-family architecture, those textual positions
remain inside TF through explicit synthetic empty ``sign`` slots. Synthetic
slots are technical positional anchors, never fabricated cuneiform signs.
Semantic/source sign cardinality is therefore tracked separately from total TF
slot cardinality.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tf.fabric import Fabric

from . import (
    TF_VERSION,
    feature_descriptions,
    lexemes,
    loader,
    metadata,
    paths,
    sections,
    slotplan,
    words,
)


# Legacy reader contract. Current builds do not emit a zero-span sidecar;
# these names remain public so older artifacts can still be inspected.
ZERO_SPAN_SCHEMA = "oracc-tf-zero-span-v1"
ZERO_SPAN_FILENAME = "zero-span.json"
ZERO_SPAN_REASON = (
    "Legacy ORACC-TF zero-span sidecar retained for reading older artifacts; "
    "current textual zero-span entities use explicit synthetic TF slots."
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
    synthetic_slots: int
    tf_slots: int
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
    def semantic_signs(self) -> int:
        """Explicit name for the backwards-compatible ``signs`` measurement."""
        return self.signs

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
            f"semantic/source signs      : {self.signs:>8,}",
            f"synthetic empty slots      : {self.synthetic_slots:>8,}",
            f"total TF slots             : {self.tf_slots:>8,}",
            f"unicode signs              : {self.unicode_signs:>8,} ({self.unicode_coverage:.4%})",
            f"slotless source words      : {self.slotless_words:>8,}",
            f"lines                      : {self.lines:>8,}",
            f"lexemes                    : {self.lexemes:>8,}",
            f"sign→word errors           : {self.sign_word_membership_errors:>8,}",
            f"word→line errors           : {self.word_line_membership_errors:>8,}",
            f"section path errors        : {self.section_path_errors:>8,}",
            f"TF node counts             : {tf_counts}",
            f"unanchored node counts     : {zero_counts}",
        ))


@dataclass(frozen=True)
class _MaterialisedGraph:
    node_features: dict[str, dict[int, str | int]]
    edge_features: dict[str, dict[int, set[int]]]
    meta_data: dict[str, dict[str, object]]
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
        omitted = {node for node in all_nodes if not self.non_slot_oslots.get(node)}
        zero_counts = Counter(self.non_slot_otype[node] for node in omitted)
        if omitted:
            detail = ", ".join(
                f"{otype}={count}" for otype, count in sorted(zero_counts.items())
            )
            raise CorpusBuildError(
                "empty-slot planning left unanchored TF nodes; classify them "
                f"explicitly instead of falling back to a sidecar: {detail}"
            )

        included = all_nodes
        remap = self._node_remap(max_slot, included)
        tf_counts = Counter(self.non_slot_otype[node] for node in included)
        tf_counts["sign"] = max_slot

        otype: dict[int, str] = {slot: "sign" for slot in range(1, max_slot + 1)}
        otype.update({remap[node]: self.non_slot_otype[node] for node in included})

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
        for name, data in self.edges.items():
            tf_data: dict[int, set[int]] = {}
            for source, targets in data.items():
                if source not in included:
                    raise CorpusBuildError(
                        f"edge feature {name!r} has unanchored source node {source}"
                    )
                missing = set(targets) - included
                if missing:
                    raise CorpusBuildError(
                        f"edge feature {name!r} targets unanchored nodes {sorted(missing)[:5]!r}"
                    )
                if targets:
                    tf_data[remap[source]] = {remap[target] for target in targets}
            if tf_data:
                edge_features[name] = tf_data

        # Text-Fabric eagerly resolves declared section features at load time.
        # Sparse standalone subsets (notably a metadata-only document) may not
        # contain face/line nodes, so only declare levels that actually exist.
        section_levels = [
            otype for otype in ("document", "face", "line")
            if tf_counts.get(otype, 0)
        ]
        section_spec = ",".join(section_levels)

        meta_data: dict[str, dict[str, object]] = {
            "": {
                "name": "ORACC-TF RIAO + RINAP",
                "converter": "oracc-tf",
                "version": TF_VERSION,
            },
            "otext": {
                "sectionTypes": section_spec,
                "sectionFeatures": section_spec,
            },
            "otype": {
                "valueType": "str",
                "description": feature_descriptions.require("otype"),
            },
            "oslots": {
                "valueType": "str",
                "description": feature_descriptions.require("oslots"),
            },
        }
        int_features = {"catalogue_present", "lemmaknown", "populated", "synthetic"}
        for name in set(node_features) - {"otype"}:
            meta_data[name] = {
                "valueType": "int" if name in int_features else "str",
                "description": feature_descriptions.require(name),
            }
        for name in set(edge_features) - {"oslots"}:
            meta_data[name] = {
                "valueType": "str",
                "description": feature_descriptions.require(name),
            }

        return _MaterialisedGraph(
            node_features=node_features,
            edge_features=edge_features,
            meta_data=meta_data,
            tf_node_counts=dict(sorted(tf_counts.items())),
            zero_span_counts={},
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


def load_zero_span(out_dir: Path | str) -> dict[str, object]:
    """Load and minimally validate a legacy deterministic zero-span sidecar."""
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
    """Build one joined TF dataset with explicit empty positional anchors."""
    graph = _Graph()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    next_semantic_slot = 1
    next_tf_slot = 1
    synthetic_slots = 0
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
        source_words = list(
            words.iter_words(edition.doc, start_slot=next_semantic_slot)
        )
        if len(source_words) != edition.word_count:
            raise CorpusBuildError(
                f"{edition.key}: loader says {edition.word_count} words "
                f"but M2 yielded {len(source_words)}"
            )

        by_word = {word.source_id: word for word in source_words}
        if len(by_word) != len(source_words):
            raise CorpusBuildError(f"{edition.key}: duplicate source word ids")

        for word in source_words:
            if not word.signs:
                slotless_words += 1
            for semantic_slot, sign in zip(word.slot_ids, word.signs, strict=True):
                sign_word_memberships[semantic_slot] += 1
                utf8 = sign.value.get("utf8")
                if isinstance(utf8, str) and utf8:
                    unicode_signs += 1
            next_semantic_slot = word.slot_end

        try:
            slot_plan = slotplan.build_slot_plan(
                text_id=edition.text_id,
                source_words=source_words,
                section_view=section_view,
                start_tf_slot=next_tf_slot,
            )
        except slotplan.SlotPlanError as exc:
            raise CorpusBuildError(f"{edition.key}: {exc}") from exc
        synthetic_slots += slot_plan.synthetic_slots
        next_tf_slot = slot_plan.next_tf_slot

        for event in slot_plan.events:
            if event.synthetic:
                graph.slot_feature(
                    event.slot,
                    document_key=edition.key,
                    source_id=event.source_id,
                    word_id=event.word_id,
                    synthetic=1,
                )
                continue
            sign = event.sign
            if sign is None or event.word_id is None:
                raise CorpusBuildError(
                    f"{edition.key}: semantic TF slot {event.slot} lacks source sign ownership"
                )
            utf8 = sign.value.get("utf8")
            graph.slot_feature(
                event.slot,
                document_key=edition.key,
                word_id=event.word_id,
                src_path=sign.src_path,
                utf8=utf8 if isinstance(utf8, str) else None,
                readingu=utf8 if isinstance(utf8, str) else None,
                sign_json=_json(sign.value),
                gdl_id=sign.value.get("id"),
                gdl_form=sign.value.get("form"),
                gdl_sexified=sign.value.get("sexified"),
            )

        joined = metadata.join_edition(edition, metadata_index)
        document_node = graph.node("document", slot_plan.document_slots)
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
            node = graph.node("face", slot_plan.section_slots[face])
            face_nodes[face.source_id] = node
            _add_section_features(graph, node, face, document_key=edition.key)
            graph.feature(node, face=face.source_id)
            graph.edge("face_document", node, document_node)

        for column in section_view.columns:
            if column.source_id in column_nodes:
                raise CorpusBuildError(
                    f"{edition.key}: duplicate column id {column.source_id!r}"
                )
            node = graph.node("column", slot_plan.section_slots[column])
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
            node = graph.node("line", slot_plan.section_slots[line])
            line_nodes[line.source_id] = node
            _add_section_features(graph, node, line, document_key=edition.key)
            graph.feature(node, line=line.source_id, lnno=line.label)

            if line.face_id is None or line.face_id not in face_nodes:
                if edition.populated:
                    section_path_errors += 1
            else:
                graph.edge("line_face", node, face_nodes[line.face_id])
            if line.column_id is not None:
                if line.column_id not in column_nodes:
                    if edition.populated:
                        section_path_errors += 1
                else:
                    graph.edge("line_column", node, column_nodes[line.column_id])

        for chunk in section_view.chunks:
            node = graph.node("chunk", slot_plan.section_slots[chunk])
            _add_section_features(graph, node, chunk, document_key=edition.key)

        for phrase in section_view.phrases:
            node = graph.node("phrase", slot_plan.section_slots[phrase])
            _add_section_features(graph, node, phrase, document_key=edition.key)

        section_words = section_view.word_to_line
        word_line_errors += len(set(section_words) ^ set(by_word))

        for word in source_words:
            word_count += 1
            slots = set(slot_plan.word_slots[word.source_id])
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

    semantic_signs = next_semantic_slot - 1
    max_tf_slot = next_tf_slot - 1
    collision_count = sum(count - 1 for count in key_counts.values() if count > 1)
    membership_errors = (
        sum(count != 1 for count in sign_word_memberships.values())
        + semantic_signs
        - len(sign_word_memberships)
    )

    if collision_count:
        raise CorpusBuildError(
            f"qualified document keys are not unique: {collision_count} collisions"
        )
    if document_count == 0 or max_tf_slot == 0:
        raise CorpusBuildError("cannot emit a Text-Fabric corpus with no documents")

    materialised = graph.materialise(max_tf_slot)
    tf = Fabric(locations=str(out_dir), silent="deep")
    if not tf.save(
        nodeFeatures=materialised.node_features,
        edgeFeatures=materialised.edge_features,
        metaData=materialised.meta_data,
        silent="deep",
    ):
        raise CorpusBuildError(f"Text-Fabric rejected generated graph in {out_dir}")

    # A successful current-format build is self-contained in TF. Remove a
    # stale sidecar only after the replacement TF graph has saved successfully.
    (out_dir / ZERO_SPAN_FILENAME).unlink(missing_ok=True)

    return CorpusBuildReport(
        documents=document_count,
        populated_documents=populated_count,
        stub_documents=stub_count,
        unique_document_keys=len(key_counts),
        document_key_collisions=collision_count,
        words=word_count,
        signs=semantic_signs,
        synthetic_slots=synthetic_slots,
        tf_slots=max_tf_slot,
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
