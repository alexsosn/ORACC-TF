"""Round-trip measurements and source-preservation helpers for P-001 M7.

A flat sign sequence is intentionally treated as weaker than the original GDL
tree. The evaluator reconstructs a form only from semantic sign-slot payload
and reports why that candidate cannot reproduce the source form. Separately,
``source_gdl_json`` defines the canonical JSON contract used to preserve the
original GDL representation without conflating an absent field with ``[]`` or
``null``.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import gdl, loader, paths, words


# These are sign-local editorial/orthographic annotations that alter the
# printed/transliterated surface without changing which semantic sign slot is
# present. Structural wrappers (determinatives, logograms, qualifiers, etc.)
# are classified separately and take precedence below.
_SLOT_MARKUP_KEYS = frozenset({"break", "breakStart", "breakEnd", "o"})


@dataclass(frozen=True)
class WordRoundTrip:
    """Result of reconstructing one source word from semantic sign payload."""

    candidate: str | None
    exact: bool
    reason: str | None


@dataclass(frozen=True)
class RoundTripCensus:
    """Whole-corpus sign-derived form accounting."""

    words: int
    exact: int
    zero_sign_words: int
    exceptions: dict[str, int]

    @property
    def exception_words(self) -> int:
        return sum(self.exceptions.values())

    def report(self) -> str:
        lines = [
            f"words              : {self.words:>8,}",
            f"exact              : {self.exact:>8,}",
            f"exceptions         : {self.exception_words:>8,}",
            f"zero-sign words    : {self.zero_sign_words:>8,}",
        ]
        for reason, count in sorted(self.exceptions.items()):
            lines.append(f"  {reason:<20}: {count:>8,}")
        return "\n".join(lines)


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def source_gdl_json(features: Mapping[str, object]) -> str | None:
    """Return canonical JSON for the source ``gdl`` field, preserving absence.

    An absent field returns ``None``; a present empty list returns ``"[]"``;
    a present JSON null returns ``"null"``. This distinction is required for
    an auditable source-preservation contract.
    """
    if "gdl" not in features:
        return None
    return _json(features["gdl"])


def _sign_piece(value: Mapping[str, object]) -> str | None:
    """Return the transliteration contribution carried by one semantic slot."""
    piece: object | None = None
    for key in ("v", "s", "q", "c"):
        if key in value:
            piece = value[key]
            break
    if piece is None and "n" in value:
        piece = value.get("form")
    if not isinstance(piece, str):
        return None

    delim = value.get("delim")
    if delim is None:
        return piece
    if not isinstance(delim, str):
        return None
    return piece + delim


def _source_entries(word: words.WordRecord) -> Sequence[Mapping[str, object]]:
    raw = word.features.get("gdl")
    if raw is None:
        return ()
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
        return raw
    # M2 already rejects this shape; keep the M7 helper fail-closed as well.
    raise words.InvalidWordSource(
        f"{word.source_id}: 'gdl' is {type(raw).__name__}, expected list"
    )


def _has_slot_markup(word: words.WordRecord) -> bool:
    return any(
        any(key in sign.value for key in _SLOT_MARKUP_KEYS)
        for sign in word.signs
    )


def _has_continuation_context(word: words.WordRecord) -> bool:
    """Whether ORACC explicitly says this local word fragment continues elsewhere."""
    contrefs = word.features.get("contrefs")
    if not isinstance(contrefs, str) or not contrefs.strip():
        return False
    return any(
        isinstance(word.features.get(name), str)
        for name in ("headform", "tailform")
    )


def evaluate_word(word: words.WordRecord) -> WordRoundTrip:
    """Attempt a form round-trip using only M1 semantic sign-slot payload."""
    if word.form is None:
        return WordRoundTrip(candidate=None, exact=False, reason="missing_form")
    if not word.signs:
        return WordRoundTrip(candidate=None, exact=False, reason="zero_sign")

    pieces: list[str] = []
    for sign in word.signs:
        # ``x`` is itself a semantic textual position but intentionally lacks a
        # recoverable sign reading. Do not bury this known source state under a
        # generic unsupported-payload bucket.
        if "x" in sign.value:
            return WordRoundTrip(candidate=None, exact=False, reason="unreadable_sign")
        piece = _sign_piece(sign.value)
        if piece is None:
            return WordRoundTrip(
                candidate=None,
                exact=False,
                reason="unsupported_slot_payload",
            )
        pieces.append(piece)

    candidate = "".join(pieces)
    if candidate == word.form:
        return WordRoundTrip(candidate=candidate, exact=True, reason=None)

    # A continued ORACC word stores the complete lexical ``form`` on a local
    # fragment whose GDL/signs encode only the head or tail.  The mismatch is
    # therefore source-declared, not a failure of sign spelling reconstruction.
    if _has_continuation_context(word):
        return WordRoundTrip(
            candidate=candidate,
            exact=False,
            reason="continuation_context",
        )

    # A terminal delimiter belongs to the source grapheme stream but may be
    # excluded from the lemmatiser's ``form``. Keep that source distinction
    # explicit instead of treating it as a spelling failure.
    if candidate.rstrip("-.:") == word.form:
        return WordRoundTrip(
            candidate=candidate,
            exact=False,
            reason="trailing_delimiter",
        )

    # ``frag`` is ORACC's source-facing transliteration fragment. When the flat
    # sign stream reproduces it exactly but the lemmatised ``form`` differs,
    # the source itself explains the non-round-trip.
    if word.frag is not None and candidate == word.frag:
        return WordRoundTrip(
            candidate=candidate,
            exact=False,
            reason="fragment_context",
        )

    # RIAO/RINAP contain a small, closed source-internal orthography class in
    # which GDL uses ḫ while the lemmatiser's written ``form`` uses h.  The
    # corpus census establishes that this exact replacement explains every
    # otherwise-residual mismatch; no unrelated edit is accepted here.
    if "ḫ" in candidate and candidate.replace("ḫ", "h") == word.form:
        return WordRoundTrip(
            candidate=candidate,
            exact=False,
            reason="source_orthography",
        )

    dispositions = {
        item.disposition
        for item in gdl.classify_tree(_source_entries(word), word_id=word.source_id)
    }
    if gdl.Disposition.STRUCTURAL in dispositions:
        reason = "structural_context"
    elif _has_slot_markup(word):
        reason = "slot_markup"
    elif gdl.Disposition.MODIFIER in dispositions:
        reason = "modifier_context"
    elif gdl.Disposition.RENDERING in dispositions:
        reason = "rendering_context"
    else:
        reason = "slot_spelling"
    return WordRoundTrip(candidate=candidate, exact=False, reason=reason)


def census(data: Path = paths.DATA) -> RoundTripCensus:
    """Measure sign-derived form round-trip over all parseable RIAO+RINAP words."""
    total = 0
    exact = 0
    zero_sign = 0
    exceptions: Counter[str] = Counter()

    for edition in loader.iter_editions(Path(data), skip_unreadable=True):
        for word in words.iter_words(edition.doc):
            total += 1
            result = evaluate_word(word)
            if result.exact:
                exact += 1
                continue
            if result.reason is None:
                raise RuntimeError(f"{word.source_id}: failed round-trip without reason")
            exceptions[result.reason] += 1
            if result.reason == "zero_sign":
                zero_sign += 1

    return RoundTripCensus(
        words=total,
        exact=exact,
        zero_sign_words=zero_sign,
        exceptions=dict(sorted(exceptions.items())),
    )
