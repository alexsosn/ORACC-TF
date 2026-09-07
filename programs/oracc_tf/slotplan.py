"""Source-ordered Text-Fabric slot planning for ORACC-TF.

M2 deliberately numbers semantic ORACC signs independently of Text-Fabric.
This module turns that semantic stream plus M3 source-order spans into the
actual TF ``sign`` slot stream.  It inserts the minimum synthetic empty anchors
required by ADR-0001 while preserving source order.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Mapping, Sequence

from . import gdl, sections, words


class SlotPlanError(ValueError):
    """A document cannot be assigned a source-faithful TF slot stream."""


@dataclass(frozen=True)
class SlotEvent:
    """One final Text-Fabric slot and the source fact that caused it."""

    slot: int
    source_order: int
    semantic_slot: int | None
    owner_otype: str
    source_id: str
    word_id: str | None
    sign: gdl.ClassifiedGDL | None

    @property
    def synthetic(self) -> bool:
        return self.semantic_slot is None


@dataclass(frozen=True)
class SlotPlan:
    """Complete TF slot mapping for one edition."""

    events: tuple[SlotEvent, ...]
    word_slots: Mapping[str, tuple[int, ...]]
    section_slots: Mapping[sections.SectionNode, tuple[int, ...]]
    document_slots: tuple[int, ...]
    semantic_to_tf: Mapping[int, int]
    synthetic_slots: int
    next_tf_slot: int


@dataclass(frozen=True)
class _PendingEvent:
    source_order: int
    tie: int
    semantic_slot: int | None
    owner_otype: str
    source_id: str
    word_id: str | None
    sign: gdl.ClassifiedGDL | None


_STRUCTURAL_PRIORITY = {
    "line": 0,
    "phrase": 1,
    "chunk": 2,
    "column": 3,
    "face": 4,
}


def _contains_order(sorted_orders: list[int], start: int, end: int) -> bool:
    index = bisect_left(sorted_orders, start)
    return index < len(sorted_orders) and sorted_orders[index] <= end


def build_slot_plan(
    *,
    text_id: str,
    source_words: Sequence[words.WordRecord],
    section_view: sections.SectionWalk,
    start_tf_slot: int,
) -> SlotPlan:
    """Plan all real and synthetic TF slots for one source edition.

    Semantic M2 ordinals are never rewritten.  ``semantic_to_tf`` records how
    those source-sign ordinals map into the final TF stream after empty anchors
    have been inserted.
    """
    if not isinstance(start_tf_slot, int) or isinstance(start_tf_slot, bool) or start_tf_slot < 1:
        raise SlotPlanError("start_tf_slot must be a positive 1-based integer")

    pending: list[_PendingEvent] = []
    occupied_orders: list[int] = []

    for word in source_words:
        try:
            source_order = section_view.word_order[word.source_id]
        except KeyError as exc:
            raise SlotPlanError(
                f"word {word.source_id!r} has no M3 source-order position"
            ) from exc
        if source_order < 1:
            raise SlotPlanError(
                f"word {word.source_id!r} has invalid source-order position {source_order}"
            )

        if word.signs:
            for index, (semantic_slot, sign) in enumerate(
                zip(word.slot_ids, word.signs, strict=True)
            ):
                pending.append(_PendingEvent(
                    source_order=source_order,
                    tie=index,
                    semantic_slot=semantic_slot,
                    owner_otype="word",
                    source_id=word.source_id,
                    word_id=word.source_id,
                    sign=sign,
                ))
        else:
            pending.append(_PendingEvent(
                source_order=source_order,
                tie=0,
                semantic_slot=None,
                owner_otype="word",
                source_id=word.source_id,
                word_id=word.source_id,
                sign=None,
            ))
        occupied_orders.append(source_order)

    occupied_orders.sort()

    candidates = list(section_view.nodes)
    for node in candidates:
        if node.source_start < 1 or node.source_end < node.source_start:
            raise SlotPlanError(
                f"{node.otype} {node.source_id!r} has invalid source interval "
                f"[{node.source_start}, {node.source_end}]"
            )

    # Inner/smaller intervals get first chance to create a technical anchor.
    # Ancestors then see that event and reuse it.  This is what prevents one
    # empty line inside one empty chunk/face/document from multiplying anchors.
    candidates.sort(key=lambda node: (
        node.source_end - node.source_start,
        node.source_start,
        _STRUCTURAL_PRIORITY.get(node.otype, 99),
        node.source_id,
    ))
    structural_tie = 1_000_000
    for node in candidates:
        if _contains_order(occupied_orders, node.source_start, node.source_end):
            continue
        pending.append(_PendingEvent(
            source_order=node.source_start,
            tie=structural_tie,
            semantic_slot=None,
            owner_otype=node.otype,
            source_id=node.source_id,
            word_id=None,
            sign=None,
        ))
        structural_tie += 1
        insert_at = bisect_right(occupied_orders, node.source_start)
        occupied_orders.insert(insert_at, node.source_start)

    # A metadata-only document can have no M3 section node at all.  It still
    # needs one technical position so the document remains a normal TF node.
    if not pending:
        pending.append(_PendingEvent(
            source_order=1,
            tie=structural_tie,
            semantic_slot=None,
            owner_otype="document",
            source_id=text_id,
            word_id=None,
            sign=None,
        ))

    pending.sort(key=lambda event: (
        event.source_order,
        event.tie,
        event.owner_otype,
        event.source_id,
    ))

    events: list[SlotEvent] = []
    semantic_to_tf: dict[int, int] = {}
    word_slots_mut: dict[str, list[int]] = {
        word.source_id: [] for word in source_words
    }
    for offset, item in enumerate(pending):
        slot = start_tf_slot + offset
        event = SlotEvent(
            slot=slot,
            source_order=item.source_order,
            semantic_slot=item.semantic_slot,
            owner_otype=item.owner_otype,
            source_id=item.source_id,
            word_id=item.word_id,
            sign=item.sign,
        )
        events.append(event)
        if item.semantic_slot is not None:
            if item.semantic_slot in semantic_to_tf:
                raise SlotPlanError(
                    f"semantic sign slot {item.semantic_slot} was planned twice"
                )
            semantic_to_tf[item.semantic_slot] = slot
        if item.word_id is not None:
            word_slots_mut[item.word_id].append(slot)

    final_orders = [event.source_order for event in events]
    final_slots = [event.slot for event in events]
    section_slots: dict[sections.SectionNode, tuple[int, ...]] = {}
    for node in section_view.nodes:
        left = bisect_left(final_orders, node.source_start)
        right = bisect_right(final_orders, node.source_end)
        slots = tuple(final_slots[left:right])
        if not slots:
            raise SlotPlanError(
                f"{node.otype} {node.source_id!r} remained without a TF slot"
            )
        section_slots[node] = slots

    word_slots = {
        source_id: tuple(slots)
        for source_id, slots in word_slots_mut.items()
    }
    for word in source_words:
        slots = word_slots[word.source_id]
        expected = word.sign_count if word.sign_count else 1
        if len(slots) != expected:
            raise SlotPlanError(
                f"word {word.source_id!r} planned {len(slots)} slots, expected {expected}"
            )

    document_slots = tuple(event.slot for event in events)
    synthetic_slots = sum(event.synthetic for event in events)
    return SlotPlan(
        events=tuple(events),
        word_slots=word_slots,
        section_slots=section_slots,
        document_slots=document_slots,
        semantic_to_tf=semantic_to_tf,
        synthetic_slots=synthetic_slots,
        next_tf_slot=start_tf_slot + len(events),
    )
