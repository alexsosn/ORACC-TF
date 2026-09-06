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
    "label": "Source section label preserved from ORACC.",
    "src_path": "Source GDL path of this sign within the ORACC word structure.",
    # Sign/GDL layer
    "utf8": "Unicode cuneiform string supplied by ORACC for this sign, when available.",
    "readingu": "Compatibility alias for the ORACC Unicode cuneiform sign string in utf8.",
    "sign_json": "Canonical JSON serialization of the source ORACC sign/GDL object.",
    "gdl_id": "ORACC GDL identifier attached to this sign, when present.",
    "gdl_form": "ORACC GDL form value attached to this sign, when present.",
    "gdl_sexified": "ORACC GDL sexified value attached to this sign, when present.",
    "gdl_json": "Canonical JSON serialization of the source ORACC word-level GDL payload.",
    # Document/catalogue metadata
    "populated": "Integer flag: 1 when the ORACC edition contains parsed words, otherwise 0.",
    "catalogue_present": "Integer flag: 1 when catalogue metadata was joined for the document, otherwise 0.",
    "catalogue_json": "Canonical JSON serialization of the joined ORACC catalogue record.",
    "license": "Licence label supplied by ORACC for the source document metadata.",
    "license_url": "Licence URL supplied by ORACC for the source document metadata.",
    "license_type": "Licence type supplied by ORACC for the source document metadata.",
    "designation": "ORACC catalogue designation value preserved as text.",
    "genre": "ORACC catalogue genre value preserved as text.",
    "subgenre": "ORACC catalogue subgenre value preserved as text.",
    "period": "ORACC catalogue period value preserved as text.",
    "provenience": "ORACC catalogue provenience value preserved as text.",
    "language": "ORACC catalogue language value preserved as text.",
    "supergenre": "ORACC catalogue supergenre value preserved as text.",
    "ruler": "ORACC catalogue ruler value preserved as text.",
    "object_type": "ORACC catalogue object-type value preserved as text.",
    "material": "ORACC catalogue material value preserved as text.",
    "script": "ORACC catalogue script value preserved as text.",
    "exemplars": "ORACC catalogue exemplars value preserved as text.",
    "primary_publication": "ORACC catalogue primary-publication value preserved as text.",
    "pleiades_id": "ORACC catalogue Pleiades identifier value preserved as text.",
    "pleiades_coord": "ORACC catalogue Pleiades coordinate value preserved as text.",
    "cdli_id": "ORACC catalogue CDLI identifier value preserved as text.",
    "collection": "ORACC catalogue collection value preserved as text.",
    "nino_overlap_status": "OBABAT comparison status against the exact pinned Nino Old Babylonian corpus; unmatched does not mean independently clean.",
    # Structural layer
    "synthetic": "Integer flag marking a section node synthesized by ORACC-TF to preserve source hierarchy.",
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
    "props_json": "Canonical JSON serialization of the source ORACC word-level props payload.",
    "discourse": "ORACC discourse property value supplied on the word occurrence.",
    "base": "ORACC morphological base value supplied on the word occurrence, when present.",
    "morph": "ORACC morphological segmentation value supplied on the word occurrence, when present.",
    "morph2": "ORACC secondary/glossed morphological segmentation value supplied on the word occurrence, when present.",
    # Semantic/structural edges
    "face_document": "Edge from a face node to its containing document node.",
    "column_face": "Edge from a column node to its containing face node.",
    "line_face": "Edge from a line node to its containing face node.",
    "line_column": "Edge from a line node to its containing column node.",
    "word_line": "Edge from a word node to its containing line node.",
    "word_lex": "Edge from a word occurrence to its ORACC-TF lexeme node.",
}


def require(name: str) -> str:
    """Return the authoritative description or fail on undocumented schema."""
    try:
        return DESCRIPTIONS[name]
    except KeyError as exc:
        raise KeyError(f"no Text-Fabric feature description registered for {name!r}") from exc
