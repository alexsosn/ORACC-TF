"""Integrated RIAO+RINAP Text-Fabric build and M6 invariant report.

M0--M5 deliberately keep source interpretation in small independently tested
modules.  M6 is the first place where those views are joined into an actual
Text-Fabric graph.  ``sign`` is the TF slot type.  Source words with no
semantic sign slots are preserved as ordinary (empty-oslots) ``word`` nodes;
they are never repaired by inventing a sign.  Explicit relation edges keep
such words connected to their source line/face/document path.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tf.fabric import Fabric

from . import TF_VERSION, gdl, lexemes, loader, metadata, paths, sections, words


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

    @property
    def unicode_coverage(self) -> float:
        return self.unicode_signs / self.signs if self.signs else 0.0

    def report(self) -> str:
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
        ))


class _Graph:
    """Provisional TF graph whose non-slot ids are shifted after slot count is known."""

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

    def materialise(self, max_slot: int) -> tuple[
        dict[str, dict[int, str | int]],
        dict[str, dict[int, set[int]]],
        dict[str, dict[str, object]],
    ]:
        shift = max_slot
        otype: dict[int, str] = {slot: "sign" for slot in range(1, max_slot + 1)}
        otype.update({shift + node: typ for node, typ in self.non_slot_otype.items()})

        node_features: dict[str, dict[int, str | int]] = {"otype": otype}
        all_names = set(self.slot_features) | set(self.node_features)
        for name in all_names:
            data: dict[int, str | int] = {}
            data.update(self.slot_features.get(name, {}))
            data.update({
                shift + node: value
                for node, value in self.node_features.get(name, {}).items()
            })
            node_features[name] = data

        edge_features: dict[str, dict[int, set[int]]] = {
            "oslots": {
                shift + node: set(slots)
                for node, slots in self.non_slot_oslots.items()
            }
        }
        for name, data in self.edges.items():
            edge_features[name] = {
                shift + source: {shift + target for target in targets}
                for source, targets in data.items()
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
        for name in all_names:
            meta_data[name] = {
                "valueType": "int" if name in int_features else "str"
            }
        for name in self.edges:
            meta_data[name] = {"valueType": "str"}

        return node_features, edge_features, meta_data


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _source_gdl(word: words.WordRecord) -> str:
    return _json(word.features.get("gdl") or [])


def _catalogue_feature_value(value: object) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (str, int)):
        return value
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


def build_tf(
    out_dir: Path | str,
    *,
    editions: Iterable[loader.Edition],
    metadata_index: metadata.MetadataIndex,
) -> CorpusBuildReport:
    """Build one joined Text-Fabric dataset from already selected editions.

    The function owns global slot numbering.  All source-derived non-slot nodes
    may have empty ``oslots``; in particular this is required for the 295 real
    signless words measured by M2 and for the 233 valid stub documents.
    """
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
                f"{edition.key}: loader says {edition.word_count} words but M2 yielded {len(source_words)}"
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
                raise CorpusBuildError(f"{edition.key}: duplicate column id {column.source_id!r}")
            node = graph.node("column")
            column_nodes[column.source_id] = node
            _add_section_features(graph, node, column, document_key=edition.key)
            graph.feature(node, column_id=column.source_id)
            if column.face_id is None or column.face_id not in face_nodes:
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
                section_path_errors += 1
            else:
                graph.add_oslots(face_nodes[line.face_id], slots)
                graph.edge("line_face", node, face_nodes[line.face_id])
            if line.column_id is not None:
                if line.column_id not in column_nodes:
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
        if set(section_words) != set(by_word):
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
            if line_id is None or line_id not in line_nodes:
                word_line_errors += 1
                section_path_errors += int(edition.populated)
            else:
                line_node = line_nodes[line_id]
                graph.edge("word_line", word_node, line_node)
                line_source = next(
                    (line for line in section_view.lines if line.source_id == line_id),
                    None,
                )
                if line_source is None or line_source.face_id not in face_nodes:
                    section_path_errors += int(edition.populated)

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
    membership_errors = sum(
        count != 1 for slot, count in sign_word_memberships.items()
    ) + (max_slot - len(sign_word_memberships))

    if collision_count:
        raise CorpusBuildError(
            f"qualified document keys are not unique: {collision_count} collisions"
        )

    node_features, edge_features, meta_data = graph.materialise(max_slot)
    tf = Fabric(locations=str(out_dir), silent="deep")
    if not tf.save(
        nodeFeatures=node_features,
        edgeFeatures=edge_features,
        metaData=meta_data,
        silent="deep",
    ):
        raise CorpusBuildError(f"Text-Fabric rejected generated graph in {out_dir}")

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
    api = tf.loadAll(silent="deep")
    if api is None:
        raise CorpusBuildError(f"Text-Fabric could not load generated graph in {out_dir}")
    return api
