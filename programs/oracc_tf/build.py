"""Integrated RIAO+RINAP graph and Text-Fabric warp for P-001 M6.

M0-M5 validate individual source layers. This module is the first place where
those layers are required to agree as one graph. It deliberately keeps three
identities separate:

* source ids are preserved verbatim as features;
* graph node keys are qualified by ``subproject:Q`` so the 140 bare-Q
  collisions cannot merge words or section nodes from different editions;
* Text-Fabric slot ids are a projection layer: semantic source signs occupy
  normal slots, while source objects with no signs receive explicit synthetic
  anchor slots because TF removes unlinked non-slot nodes.

Synthetic anchors are infrastructure, not source signs. They are counted
separately, marked ``synthetic=1`` / ``slot_kind=anchor``, and never enter the
pinned M1 semantic-sign census.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from . import gdl, lexemes, loader, metadata, paths, sections, words


class BuildError(ValueError):
    """The independently validated source layers cannot form one graph."""


class DuplicateGraphNode(BuildError):
    """Two source objects resolve to the same qualified graph identity."""


@dataclass(frozen=True)
class DocumentNode:
    key: str
    source_id: str
    subproject: str
    populated: int
    metadata: metadata.DocumentMetadata | None = None


@dataclass(frozen=True)
class CorpusGraph:
    """In-memory integrated graph before integer TF non-slot numbering."""

    slot_type: str
    max_slot: int
    document_nodes: Mapping[str, DocumentNode]
    words: Mapping[str, words.WordRecord]
    signs: Mapping[int, gdl.ClassifiedGDL]
    sign_owner: Mapping[int, str]
    anchor_owner: Mapping[int, str]
    anchor_reason: Mapping[int, str]
    word_to_line: Mapping[str, str]
    word_to_lex: Mapping[str, tuple[str, ...]]
    node_slots: Mapping[str, tuple[int, ...]]
    node_types: Mapping[str, str]
    source_ids: Mapping[str, str]
    node_documents: Mapping[str, str]
    section_nodes: Mapping[str, sections.SectionNode]
    lexeme_nodes: Mapping[str, lexemes.LexemeKey]
    document_words: Mapping[str, tuple[str, ...]]
    line_faces: Mapping[str, str]

    @property
    def source_sign_count(self) -> int:
        """Number of semantic source signs, excluding synthetic TF anchors."""
        return len(self.signs)


@dataclass(frozen=True)
class CorpusInvariantCensus:
    documents: int
    populated_documents: int
    stub_documents: int
    duplicate_document_keys: int
    source_signs: int
    tf_slots: int
    synthetic_anchor_slots: int
    unicode_signs: int
    non_unicode_source_signs: int
    non_unicode_non_x_signs: int
    words: int
    lines: int
    lexemes: int
    sign_owner_errors: int
    anchor_owner_errors: int
    word_line_errors: int
    populated_section_path_errors: int

    @property
    def signs(self) -> int:
        """Backward-compatible alias for the semantic source-sign census."""
        return self.source_signs

    @property
    def non_unicode_signs(self) -> int:
        """Backward-compatible alias scoped to semantic source signs."""
        return self.non_unicode_source_signs

    def report(self) -> str:
        unicode_pct = (
            100.0 * self.unicode_signs / self.source_signs
            if self.source_signs
            else 0.0
        )
        return "\n".join((
            f"documents                     : {self.documents:>9,}",
            f"populated                     : {self.populated_documents:>9,}",
            f"stubs                         : {self.stub_documents:>9,}",
            f"duplicate document keys       : {self.duplicate_document_keys:>9,}",
            f"source signs                  : {self.source_signs:>9,}",
            f"synthetic anchor slots        : {self.synthetic_anchor_slots:>9,}",
            f"TF slots total                : {self.tf_slots:>9,}",
            f"unicode source signs          : {self.unicode_signs:>9,} ({unicode_pct:.3f}%)",
            f"non-unicode source signs      : {self.non_unicode_source_signs:>9,}",
            f"non-unicode non-x signs       : {self.non_unicode_non_x_signs:>9,}",
            f"words                         : {self.words:>9,}",
            f"lines                         : {self.lines:>9,}",
            f"lexemes                       : {self.lexemes:>9,}",
            f"sign owner errors             : {self.sign_owner_errors:>9,}",
            f"anchor owner errors           : {self.anchor_owner_errors:>9,}",
            f"word→line errors              : {self.word_line_errors:>9,}",
            f"populated section-path errors : {self.populated_section_path_errors:>9,}",
        ))


@dataclass(frozen=True)
class ExportResult:
    graph: CorpusGraph
    census: CorpusInvariantCensus
    output_dir: Path
    good: bool


def _node_key(document_key: str, otype: str, source_id: str) -> str:
    return f"{document_key}\x1f{otype}\x1f{source_id}"


def _lex_key(key: lexemes.LexemeKey) -> str:
    # Lexemes are intentionally project-independent (M4), so their graph key
    # must not contain a document/project component.
    return "lex\x1f" + "\x1f".join((key.lang, key.cf, key.gw, key.pos))


def _slots_for_words(
    raw_word_ids: Iterable[str],
    qualified_words: Mapping[str, str],
    node_slots: Mapping[str, tuple[int, ...]],
    *,
    where: str,
) -> tuple[int, ...]:
    out: list[int] = []
    for raw_id in raw_word_ids:
        word_key = qualified_words.get(raw_id)
        if word_key is None:
            raise BuildError(f"{where}: section references unknown word {raw_id!r}")
        out.extend(node_slots[word_key])
    return tuple(out)


def build_editions(
    editions: Sequence[loader.Edition] | Iterable[loader.Edition],
    *,
    metadata_index: metadata.MetadataIndex | None = None,
) -> CorpusGraph:
    """Integrate already parsed editions into one qualified graph.

    Semantic source-sign ordinals and Text-Fabric slot ordinals are deliberately
    decoupled. M2's :class:`WordRecord` retains a source-only empty span for a
    zero-sign word; the TF projection gives that word one explicitly synthetic
    anchor slot so it survives TF validation.
    """
    document_nodes: dict[str, DocumentNode] = {}
    word_nodes: dict[str, words.WordRecord] = {}
    sign_nodes: dict[int, gdl.ClassifiedGDL] = {}
    sign_owner: dict[int, str] = {}
    anchor_owner: dict[int, str] = {}
    anchor_reason: dict[int, str] = {}
    word_to_line: dict[str, str] = {}
    word_to_lex: dict[str, tuple[str, ...]] = {}
    node_slots: dict[str, tuple[int, ...]] = {}
    node_types: dict[str, str] = {}
    source_ids: dict[str, str] = {}
    node_documents: dict[str, str] = {}
    section_nodes: dict[str, sections.SectionNode] = {}
    lexeme_nodes: dict[str, lexemes.LexemeKey] = {}
    document_words: dict[str, tuple[str, ...]] = {}
    line_faces: dict[str, str] = {}
    lexeme_slots: dict[str, set[int]] = {}

    source_next_slot = 1
    tf_next_slot = 1

    def allocate_anchor(owner: str, reason: str, document_key: str) -> int:
        nonlocal tf_next_slot
        slot = tf_next_slot
        tf_next_slot += 1
        if slot in sign_nodes or slot in anchor_owner:
            raise BuildError(f"TF slot {slot} allocated twice")
        anchor_owner[slot] = owner
        anchor_reason[slot] = reason
        node_documents[f"@slot:{slot}"] = document_key
        return slot

    def add_non_slot(
        key: str,
        otype: str,
        slots: tuple[int, ...],
        *,
        source_id: str,
        document_key: str | None,
    ) -> None:
        if key in node_types:
            raise DuplicateGraphNode(key)
        if not slots:
            raise BuildError(f"{key}: TF non-slot node has no slot projection")
        node_types[key] = otype
        node_slots[key] = slots
        source_ids[key] = source_id
        if document_key is not None:
            node_documents[key] = document_key

    for edition in editions:
        doc_key = edition.key
        if doc_key in document_nodes:
            raise DuplicateGraphNode(f"duplicate document key {doc_key}")

        joined = (
            None
            if metadata_index is None
            else metadata.join_edition(edition, metadata_index)
        )
        document_nodes[doc_key] = DocumentNode(
            key=doc_key,
            source_id=edition.text_id,
            subproject=edition.subproject,
            populated=int(edition.populated),
            metadata=joined,
        )

        qualified_words: dict[str, str] = {}
        doc_word_keys: list[str] = []
        doc_slots: list[int] = []

        for source_word in words.source_words(edition.doc):
            word = words.from_source(source_word, start_slot=source_next_slot)
            source_next_slot = word.slot_end

            word_key = _node_key(doc_key, "word", word.source_id)
            if word_key in word_nodes:
                raise DuplicateGraphNode(word_key)
            qualified_words[word.source_id] = word_key
            word_nodes[word_key] = word
            doc_word_keys.append(word_key)

            word_slots: list[int] = []
            for sign in word.signs:
                slot = tf_next_slot
                tf_next_slot += 1
                if slot in sign_owner or slot in anchor_owner:
                    raise BuildError(f"TF slot {slot} allocated twice")
                sign_owner[slot] = word_key
                sign_nodes[slot] = sign
                node_documents[f"@slot:{slot}"] = doc_key
                word_slots.append(slot)

            if not word_slots:
                word_slots.append(
                    allocate_anchor(word_key, "zero_sign_word", doc_key)
                )

            word_slot_tuple = tuple(word_slots)
            doc_slots.extend(word_slot_tuple)
            add_non_slot(
                word_key,
                "word",
                word_slot_tuple,
                source_id=word.source_id,
                document_key=doc_key,
            )

            lexical_keys = lexemes.keys_for_word(word)
            links = tuple(_lex_key(key) for key in lexical_keys)
            word_to_lex[word_key] = links
            for lex_key, lexical in zip(links, lexical_keys):
                lexeme_nodes.setdefault(lex_key, lexical)
                lexeme_slots.setdefault(lex_key, set()).update(word_slot_tuple)

        document_words[doc_key] = tuple(doc_word_keys)

        # TF removes unlinked non-slot nodes. Old Nino-cunei converters solved
        # this by inserting a slot for empty documents; we keep that mechanism
        # explicit and auditable instead of pretending it is source text.
        stub_anchor: int | None = None
        if not doc_slots:
            stub_anchor = allocate_anchor(doc_key, "stub_document", doc_key)
            doc_slots.append(stub_anchor)

        def projected_slots(
            key: str, otype: str, slots: tuple[int, ...]
        ) -> tuple[int, ...]:
            if slots:
                return slots
            if stub_anchor is not None:
                return (stub_anchor,)
            anchor = allocate_anchor(key, f"empty_{otype}", doc_key)
            doc_slots.append(anchor)
            return (anchor,)

        walk = sections.walk_document(edition.doc)
        if walk.source_words != len(doc_word_keys):
            raise BuildError(
                f"{doc_key}: word layer has {len(doc_word_keys)} words "
                f"but section walk has {walk.source_words}"
            )

        # Lines carry direct word membership; qualify their raw ids first.
        raw_line_to_key: dict[str, str] = {}
        face_slot_acc: dict[str, list[int]] = {}
        column_slot_acc: dict[str, list[int]] = {}
        for line in walk.lines:
            line_key = _node_key(doc_key, "line", line.source_id)
            raw_line_to_key[line.source_id] = line_key
            line_slots = projected_slots(
                line_key,
                "line",
                _slots_for_words(
                    line.word_ids, qualified_words, node_slots, where=line_key
                ),
            )
            add_non_slot(
                line_key,
                "line",
                line_slots,
                source_id=line.source_id,
                document_key=doc_key,
            )
            section_nodes[line_key] = line
            if line.face_id is None:
                raise BuildError(f"{line_key}: line has no face id")
            face_key = _node_key(doc_key, "face", line.face_id)
            line_faces[line_key] = face_key
            face_slot_acc.setdefault(line.face_id, []).extend(line_slots)
            if line.column_id is not None:
                column_slot_acc.setdefault(line.column_id, []).extend(line_slots)

        for raw_word_id, raw_line_id in walk.word_to_line.items():
            word_key = qualified_words.get(raw_word_id)
            line_key = raw_line_to_key.get(raw_line_id)
            if word_key is None or line_key is None:
                raise BuildError(
                    f"{doc_key}: cannot qualify word→line "
                    f"{raw_word_id!r} → {raw_line_id!r}"
                )
            word_to_line[word_key] = line_key

        for face in walk.faces:
            face_key = _node_key(doc_key, "face", face.source_id)
            face_slots = projected_slots(
                face_key,
                "face",
                tuple(face_slot_acc.get(face.source_id, ())),
            )
            add_non_slot(
                face_key,
                "face",
                face_slots,
                source_id=face.source_id,
                document_key=doc_key,
            )
            section_nodes[face_key] = face

        for column in walk.columns:
            column_key = _node_key(doc_key, "column", column.source_id)
            column_slots = projected_slots(
                column_key,
                "column",
                tuple(column_slot_acc.get(column.source_id, ())),
            )
            add_non_slot(
                column_key,
                "column",
                column_slots,
                source_id=column.source_id,
                document_key=doc_key,
            )
            section_nodes[column_key] = column

        for chunk in walk.chunks:
            chunk_key = _node_key(doc_key, "chunk", chunk.source_id)
            chunk_slots = projected_slots(
                chunk_key,
                "chunk",
                _slots_for_words(
                    chunk.word_ids, qualified_words, node_slots, where=chunk_key
                ),
            )
            add_non_slot(
                chunk_key,
                "chunk",
                chunk_slots,
                source_id=chunk.source_id,
                document_key=doc_key,
            )
            section_nodes[chunk_key] = chunk

        for phrase in walk.phrases:
            phrase_key = _node_key(doc_key, "phrase", phrase.source_id)
            phrase_slots = projected_slots(
                phrase_key,
                "phrase",
                _slots_for_words(
                    phrase.word_ids, qualified_words, node_slots, where=phrase_key
                ),
            )
            add_non_slot(
                phrase_key,
                "phrase",
                phrase_slots,
                source_id=phrase.source_id,
                document_key=doc_key,
            )
            section_nodes[phrase_key] = phrase

        # Delay the document projection until all possible section anchors have
        # been allocated so the document covers every TF slot created for it.
        unique_doc_slots = tuple(dict.fromkeys(doc_slots))
        add_non_slot(
            doc_key,
            "document",
            unique_doc_slots,
            source_id=edition.text_id,
            document_key=doc_key,
        )

    for lex_key, lexical in sorted(lexeme_nodes.items()):
        slots = tuple(sorted(lexeme_slots.get(lex_key, ())))
        if not slots:
            raise BuildError(f"{lex_key}: lexeme has no occurrence slots")
        add_non_slot(
            lex_key,
            "lex",
            slots,
            source_id="|".join((lexical.lang, lexical.cf, lexical.gw, lexical.pos)),
            document_key=None,
        )

    if source_next_slot - 1 != len(sign_nodes):
        raise BuildError(
            "source semantic sign numbering diverged from integrated sign count: "
            f"{source_next_slot - 1} != {len(sign_nodes)}"
        )
    if tf_next_slot - 1 != len(sign_nodes) + len(anchor_owner):
        raise BuildError(
            "TF slot accounting diverged from source signs + anchors: "
            f"{tf_next_slot - 1} != {len(sign_nodes)} + {len(anchor_owner)}"
        )

    return CorpusGraph(
        slot_type="sign",
        max_slot=tf_next_slot - 1,
        document_nodes=document_nodes,
        words=word_nodes,
        signs=sign_nodes,
        sign_owner=sign_owner,
        anchor_owner=anchor_owner,
        anchor_reason=anchor_reason,
        word_to_line=word_to_line,
        word_to_lex=word_to_lex,
        node_slots=node_slots,
        node_types=node_types,
        source_ids=source_ids,
        node_documents=node_documents,
        section_nodes=section_nodes,
        lexeme_nodes=lexeme_nodes,
        document_words=document_words,
        line_faces=line_faces,
    )


def _census_graph(graph: CorpusGraph) -> CorpusInvariantCensus:
    source_slots = set(graph.signs)
    owned_sign_slots = set(graph.sign_owner)
    sign_owner_errors = len(source_slots ^ owned_sign_slots)
    sign_owner_errors += sum(
        owner not in graph.words for owner in graph.sign_owner.values()
    )

    all_slots = set(range(1, graph.max_slot + 1))
    anchor_slots = set(graph.anchor_owner)
    expected_anchors = all_slots - source_slots
    anchor_owner_errors = len(expected_anchors ^ anchor_slots)
    anchor_owner_errors += len(source_slots & anchor_slots)
    anchor_owner_errors += sum(
        owner not in graph.node_types for owner in graph.anchor_owner.values()
    )
    anchor_owner_errors += len(anchor_slots ^ set(graph.anchor_reason))

    word_line_errors = 0
    for word_key in graph.words:
        line_key = graph.word_to_line.get(word_key)
        if line_key is None or graph.node_types.get(line_key) != "line":
            word_line_errors += 1

    section_path_errors = 0
    for doc_key, document in graph.document_nodes.items():
        if not document.populated:
            continue
        bad = False
        for word_key in graph.document_words.get(doc_key, ()):
            line_key = graph.word_to_line.get(word_key)
            face_key = None if line_key is None else graph.line_faces.get(line_key)
            if (
                line_key is None
                or graph.node_documents.get(line_key) != doc_key
                or face_key is None
                or graph.node_types.get(face_key) != "face"
                or graph.node_documents.get(face_key) != doc_key
            ):
                bad = True
                break
        if bad or not graph.document_words.get(doc_key):
            section_path_errors += 1

    unicode_signs = 0
    non_unicode_non_x = 0
    for sign in graph.signs.values():
        if sign.value.get("utf8"):
            unicode_signs += 1
        elif "x" not in sign.value:
            non_unicode_non_x += 1

    source_signs = len(graph.signs)
    anchors = len(graph.anchor_owner)
    return CorpusInvariantCensus(
        documents=len(graph.document_nodes),
        populated_documents=sum(d.populated for d in graph.document_nodes.values()),
        stub_documents=sum(not d.populated for d in graph.document_nodes.values()),
        duplicate_document_keys=0,
        source_signs=source_signs,
        tf_slots=graph.max_slot,
        synthetic_anchor_slots=anchors,
        unicode_signs=unicode_signs,
        non_unicode_source_signs=source_signs - unicode_signs,
        non_unicode_non_x_signs=non_unicode_non_x,
        words=len(graph.words),
        lines=sum(otype == "line" for otype in graph.node_types.values()),
        lexemes=len(graph.lexeme_nodes),
        sign_owner_errors=sign_owner_errors,
        anchor_owner_errors=anchor_owner_errors,
        word_line_errors=word_line_errors,
        populated_section_path_errors=section_path_errors,
    )


def census(data: Path = paths.DATA) -> CorpusInvariantCensus:
    graph = build_editions(loader.iter_editions(data, skip_unreadable=True))
    return _census_graph(graph)


def _set_feature(
    dest: dict[str, dict[int, str | int]],
    name: str,
    node: int,
    value: object,
) -> None:
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (str, int)):
        dest.setdefault(name, {})[node] = value


def _tf_payload(graph: CorpusGraph):
    """Translate qualified graph identities to contiguous integer TF nodes."""
    node_ids: dict[str, int] = {}
    next_node = graph.max_slot + 1
    order = {
        otype: i
        for i, otype in enumerate(
            ("document", "face", "column", "line", "chunk", "phrase", "word", "lex")
        )
    }
    for key in sorted(
        graph.node_types,
        key=lambda k: (order.get(graph.node_types[k], 99), k),
    ):
        node_ids[key] = next_node
        next_node += 1

    node_features: dict[str, dict[int, str | int]] = {
        "otype": {slot: "sign" for slot in range(1, graph.max_slot + 1)},
    }
    for key, node in node_ids.items():
        node_features["otype"][node] = graph.node_types[key]

    # Source sign provenance. src_path is guaranteed by M1; source_id uses
    # ORACC's GDL id where available and otherwise the auditable path.
    for slot, sign in graph.signs.items():
        raw_id = sign.value.get("id")
        _set_feature(
            node_features,
            "source_id",
            slot,
            raw_id if isinstance(raw_id, str) else sign.src_path,
        )
        _set_feature(node_features, "src_path", slot, sign.src_path)
        _set_feature(node_features, "utf8", slot, sign.value.get("utf8"))
        _set_feature(
            node_features,
            "document_key",
            slot,
            graph.node_documents.get(f"@slot:{slot}"),
        )

    # Synthetic TF anchors are explicitly distinguishable from source signs.
    for slot, owner in graph.anchor_owner.items():
        _set_feature(node_features, "synthetic", slot, 1)
        _set_feature(node_features, "slot_kind", slot, "anchor")
        _set_feature(
            node_features, "anchor_reason", slot, graph.anchor_reason.get(slot)
        )
        _set_feature(node_features, "anchor_owner", slot, owner)
        _set_feature(
            node_features,
            "source_id",
            slot,
            graph.source_ids.get(owner, owner),
        )
        _set_feature(
            node_features,
            "document_key",
            slot,
            graph.node_documents.get(f"@slot:{slot}"),
        )

    for key, node in node_ids.items():
        _set_feature(node_features, "source_id", node, graph.source_ids.get(key))
        _set_feature(
            node_features, "document_key", node, graph.node_documents.get(key)
        )

    for doc_key, document in graph.document_nodes.items():
        node = node_ids[doc_key]
        _set_feature(node_features, "populated", node, document.populated)
        joined = document.metadata
        if joined is not None:
            _set_feature(node_features, "license", node, joined.license)
            _set_feature(node_features, "license_url", node, joined.license_url)
            _set_feature(node_features, "license_type", node, joined.license_type)
            for name in (
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
            ):
                _set_feature(
                    node_features, name, node, joined.catalogue.get(name)
                )

    for key, word in graph.words.items():
        node = node_ids[key]
        for name in (
            "ref",
            "frag",
            "form",
            "lang",
            "cf",
            "gw",
            "sense",
            "norm",
            "pos",
            "epos",
            "inst",
            "sig",
        ):
            _set_feature(node_features, name, node, getattr(word, name))
        _set_feature(node_features, "lemmaknown", node, word.lemmaknown)

    for key, section in graph.section_nodes.items():
        node = node_ids[key]
        _set_feature(node_features, "label", node, section.label)
        _set_feature(node_features, "ref", node, section.ref)
        _set_feature(node_features, "synthetic", node, section.synthetic)
        _set_feature(node_features, "chunk_type", node, section.chunk_type)
        _set_feature(node_features, "chunk_subtype", node, section.chunk_subtype)
        _set_feature(node_features, "implicit", node, section.implicit)

    for key, lexical in graph.lexeme_nodes.items():
        node = node_ids[key]
        _set_feature(node_features, "lang", node, lexical.lang)
        _set_feature(node_features, "cf", node, lexical.cf)
        _set_feature(node_features, "gw", node, lexical.gw)
        _set_feature(node_features, "pos", node, lexical.pos)

    oslots: dict[int, set[int]] = {
        node_ids[key]: set(graph.node_slots[key]) for key in node_ids
    }
    if any(not slots for slots in oslots.values()):
        raise BuildError("TF payload contains an unlinked non-slot node")
    edge_features: dict[str, dict[int, set[int]]] = {"oslots": oslots}

    word_lex: dict[int, set[int]] = {}
    for word_key, lex_keys in graph.word_to_lex.items():
        if lex_keys:
            word_lex[node_ids[word_key]] = {node_ids[key] for key in lex_keys}
    edge_features["word_lex"] = word_lex

    int_features = {"populated", "lemmaknown", "synthetic"}
    meta_data: dict[str, dict[str, str]] = {
        "": {
            "dataset": "assyrian-royal-inscriptions",
            "sourceFormat": "ORACC corpusjson",
            "compiler": "ORACC-TF",
        }
    }
    for feature in node_features:
        meta_data[feature] = {
            "valueType": "int" if feature in int_features else "str"
        }
    for feature in edge_features:
        meta_data[feature] = {"valueType": "str"}
    meta_data["word_lex"]["description"] = "word to canonical lexeme"
    meta_data["synthetic"]["description"] = (
        "1 for source-recovery section nodes or synthetic TF anchor slots"
    )
    meta_data["slot_kind"] = {
        "valueType": "str",
        "description": "present as 'anchor' only on synthetic TF anchor slots",
    }
    meta_data["anchor_reason"] = {
        "valueType": "str",
        "description": "why a synthetic TF anchor slot was required",
    }
    meta_data["anchor_owner"] = {
        "valueType": "str",
        "description": "qualified graph node retained by a synthetic anchor slot",
    }
    return node_features, edge_features, meta_data


def export_tf_editions(
    editions: Sequence[loader.Edition] | Iterable[loader.Edition],
    output_dir: Path,
    *,
    metadata_index: metadata.MetadataIndex | None = None,
) -> ExportResult:
    """Build and write a TF dataset, then return the graph and its census."""
    from tf.fabric import Fabric

    graph = build_editions(editions, metadata_index=metadata_index)
    result = _census_graph(graph)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    node_features, edge_features, meta_data = _tf_payload(graph)
    TF = Fabric(locations=str(output_dir), modules=[""], silent="deep")
    good = bool(TF.save(
        nodeFeatures=node_features,
        edgeFeatures=edge_features,
        metaData=meta_data,
        location=str(output_dir),
        module="",
        silent="deep",
    ))
    return ExportResult(
        graph=graph,
        census=result,
        output_dir=output_dir,
        good=good,
    )


def export_tf(data: Path, output_dir: Path) -> ExportResult:
    """Build the complete in-scope RIAO+RINAP TF graph and write it to disk."""
    index = metadata.load_index(data)
    return export_tf_editions(
        loader.iter_editions(data, skip_unreadable=True),
        output_dir,
        metadata_index=index,
    )
