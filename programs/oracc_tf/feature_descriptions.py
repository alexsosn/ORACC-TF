"""Authoritative Text-Fabric feature descriptions for ORACC-TF.

Descriptions are part of the emitted TF schema. Keep them concise, source-facing,
and explicit enough that generated reference documentation can rely on them
without re-interpreting ORACC semantics in Markdown.
"""

from __future__ import annotations


DESCRIPTIONS: dict[str, str] = {
    # Text-Fabric warp features
    "otype": "Text-Fabric node type.",
    "oslots": "Text-Fabric warp edge from a non-slot node to its sign slots.",
    # Stable/source identity and references
    "document": "Qualified ORACC document key used as the Text-Fabric document section value.",
    "document_key": "Qualified ORACC subproject/document key used by ORACC-TF for cross-node identity.",
    "source_id": "Source ORACC node identifier preserved from the input data.",
    "text_id": "ORACC text identifier without the subproject qualifier.",
    "subproject": "ORACC subproject that supplied the document.",
    "word_id": "Source ORACC word identifier containing this sign.",
    "ref": "Source reference string preserved from ORACC.",
    "la…636 tokens truncated…oordinate value preserved as text.",
    "cdli_id": "ORACC catalogue CDLI identifier value preserved as text.",
    "collection": "ORACC catalogue collection value preserved as text.",
    # Structural / technical provenance layer
    "synthetic": "Integer flag marking ORACC-TF-synthesized section nodes or technical empty sign slots; synthetic slots carry no fabricated cuneiform content.",
    "implicit": "Source section implicit marker preserved from ORACC.",
    "chunk_type": "ORACC chunk type preserved from the source structure.",
    "chunk_subtype": "ORACC chunk subtype preserved from the source structure.",
    "face": "Source face identifier used as the Text-Fabric face section value.",
    "column_id": "Source ORACC column identifier.",
    "line": "Source ORACC line identifier used as the Text-Fabric line section value.",
    "lnno": "Source ATF/ORACC line label; compatibility alias used by cross-corpus tooling.",
    # Word and lexical analysis
    "frag": "ORACC source fragment value for the word occurrence.",
    "form": "Surface transliteration form of the ORACC word occurrence.",
    "lang": "ORACC language code attached to the word or lexeme.",
    "cf": "ORACC citation form (lemma) attached to the word or lexeme.",
    "gw": "ORACC guide word used to disambiguate the lexical entry.",
    "sense": "ORACC contextual lexical sense attached to the word occurrence.",
    "norm": "ORACC normalized Akkadian form attached to the word occurrence, when available.",
    "pos": "ORACC lexical part-of-speech value.",
    "epos": "ORACC effective/contextual part-of-speech value for the word occurrence.",
    "inst": "ORACC source instance-analysis value preserved on the word occurrence.",
    "sig": "ORACC occurrence analysis signature preserved verbatim; not a stable ORACC-TF lexeme identifier.",
    "lemmaknown": "Integer ORACC lexical-analysis flag indicating whether the word has a known lemma analysis.",
    "lexeme": "Canonical JSON tuple [lang, cf, gw, pos] used by ORACC-TF as the lexeme key.",
    # Semantic/structural edges
    "face_document": "Edge from a face node to its containing document node.",
    "column_face": "Edge from a column node to its containing face node.",
    "line_face": "Edge from a line node to its containing face node.",
    "line_column": "Edge from a line node to its containing column node.",
    "word_line": "Edge from a word node to its containing line node.",
    "word_lex": "Edge from a word occurrence to its ORACC-TF lexeme node.",
    # TEI translation layer
    "translation_id": "Qualified ORACC-TF translation identity composed from the source document key and TEI unit identifier.",
    "translation_source_id": "Identifier of this translation unit in the pinned official TEI source.",
    "translation_sref": "Inclusive source line-range start declared by TEI xtr:sref.",
    "translation_eref": "Inclusive source line-range end declared by TEI xtr:eref.",
    "translation_rows": "Row count declared by the TEI translation source, when present.",
    "translation_subtype": "Translation subtype declared by the TEI source, such as tr or dollar.",
    "translation_label": "Translation label declared by the TEI source.",
    "translation_se_label": "Source edition label declared by the TEI translation source.",
    "translation_text": "Plain running translation text extracted from source TEI markup.",
    "translation_text_raw": "Canonical source TEI markup for the running translation, excluding note elements.",
    "translation_source_name": "Name of the pinned official TEI archive supplying this translation.",
    "translation_source_sha256": "SHA-256 digest of the pinned official TEI archive supplying this translation.",
    "translation_source_url": "Official source URL for the pinned TEI archive.",
    "translation_source_license": "Conservative translation licence statement, kept separate from corpusjson document licence metadata.",
    "translation_source_license_url": "ORACC licensing guidance for the translation source; project-specific terms may differ.",
    "translation_note_id": "Stable source-derived identifier for a translation note.",
    "translation_note_text": "Plain text of an editorial note supplied inside a TEI translation unit.",
    "translation_document": "Edge from a TEI translation unit to its qualified ORACC document.",
    "translation_line": "Edge from a TEI translation unit to each explicitly referenced source line in its inclusive range.",
    "translation_note_unit": "Edge from a TEI note to the translation unit that explicitly contains it.",
}


def require(name: str) -> str:
    """Return the authoritative description or fail on undocumented schema."""
    try:
        return DESCRIPTIONS[name]
    except KeyError as exc:
        raise KeyError(f"no Text-Fabric feature description registered for {name!r}") from exc
