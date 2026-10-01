# Feature reference

<a id="feature-reference"></a>

Generated from TF metadata; do not hand-edit generated fields.

<a id="catalogue_json"></a>
- [`catalogue_json`](features/document/catalogue_json.md) — Canonical JSON serialization of the joined ORACC catalogue record.
<a id="catalogue_present"></a>
- [`catalogue_present`](features/document/catalogue_present.md) — Integer flag: 1 when catalogue metadata was joined for the document, otherwise 0.
<a id="cdli_id"></a>
- [`cdli_id`](features/document/cdli_id.md) — ORACC catalogue CDLI identifier value preserved as text.
<a id="cf"></a>
- [`cf`](features/mixed/cf.md) — ORACC citation form (lemma) attached to the word or lexeme.
<a id="chunk_subtype"></a>
- [`chunk_subtype`](features/chunk/chunk_subtype.md) — ORACC chunk subtype preserved from the source structure.
<a id="chunk_type"></a>
- [`chunk_type`](features/chunk/chunk_type.md) — ORACC chunk type preserved from the source structure.
<a id="collection"></a>
- [`collection`](features/document/collection.md) — ORACC catalogue collection value preserved as text.
<a id="column_id"></a>
- [`column_id`](features/column/column_id.md) — Source ORACC column identifier.
<a id="cuneiform_trailer"></a>
- [`cuneiform_trailer`](features/sign/cuneiform_trailer.md) — ORACC-TF presentation-only ASCII word separator attached to the final semantic/source sign of a word; absent on synthetic slots.
<a id="designation"></a>
- [`designation`](features/document/designation.md) — ORACC catalogue designation value preserved as text.
<a id="document"></a>
- [`document`](features/document/document.md) — Qualified ORACC document key used as the Text-Fabric document section value.
<a id="document_key"></a>
- [`document_key`](features/mixed/document_key.md) — Qualified ORACC subproject/document key used by ORACC-TF for cross-node identity.
<a id="epos"></a>
- [`epos`](features/word/epos.md) — ORACC effective/contextual part-of-speech value for the word occurrence.
<a id="exemplars"></a>
- [`exemplars`](features/document/exemplars.md) — ORACC catalogue exemplars value preserved as text.
<a id="face"></a>
- [`face`](features/face/face.md) — Source face identifier used as the Text-Fabric face section value.
<a id="form"></a>
- [`form`](features/word/form.md) — Surface transliteration form of the ORACC word occurrence.
<a id="frag"></a>
- [`frag`](features/word/frag.md) — ORACC source fragment value for the word occurrence.
<a id="gdl_form"></a>
- [`gdl_form`](features/sign/gdl_form.md) — ORACC GDL form value attached to this sign, when present.
<a id="gdl_id"></a>
- [`gdl_id`](features/sign/gdl_id.md) — ORACC GDL identifier attached to this sign, when present.
<a id="gdl_json"></a>
- [`gdl_json`](features/word/gdl_json.md) — Canonical JSON serialization of the source ORACC word-level GDL payload.
<a id="gdl_sexified"></a>
- [`gdl_sexified`](features/sign/gdl_sexified.md) — ORACC GDL sexified value attached to this sign, when present.
<a id="genre"></a>
- [`genre`](features/document/genre.md) — ORACC catalogue genre value preserved as text.
<a id="gw"></a>
- [`gw`](features/mixed/gw.md) — ORACC guide word used to disambiguate the lexical entry.
<a id="implicit"></a>
- [`implicit`](features/chunk/implicit.md) — Source section implicit marker preserved from ORACC.
<a id="inst"></a>
- [`inst`](features/word/inst.md) — ORACC source instance-analysis value preserved on the word occurrence.
<a id="label"></a>
- [`label`](features/mixed/label.md) — Source section label preserved from ORACC.
<a id="lang"></a>
- [`lang`](features/mixed/lang.md) — ORACC language code attached to the word or lexeme.
<a id="language"></a>
- [`language`](features/document/language.md) — ORACC catalogue language value preserved as text.
<a id="lemmaknown"></a>
- [`lemmaknown`](features/word/lemmaknown.md) — Integer ORACC lexical-analysis flag indicating whether the word has a known lemma analysis.
<a id="lexeme"></a>
- [`lexeme`](features/lex/lexeme.md) — Canonical JSON tuple [lang, cf, gw, pos] used by ORACC-TF as the lexeme key.
<a id="license"></a>
- [`license`](features/document/license.md) — Licence label supplied by ORACC for the source document metadata.
<a id="license_url"></a>
- [`license_url`](features/document/license_url.md) — Licence URL supplied by ORACC for the source document metadata.
<a id="line"></a>
- [`line`](features/line/line.md) — Source ORACC line identifier used as the Text-Fabric line section value.
<a id="lnno"></a>
- [`lnno`](features/line/lnno.md) — Source ATF/ORACC line label; compatibility alias used by cross-corpus tooling.
<a id="material"></a>
- [`material`](features/document/material.md) — ORACC catalogue material value preserved as text.
<a id="norm"></a>
- [`norm`](features/word/norm.md) — ORACC normalized Akkadian form attached to the word occurrence, when available.
<a id="object_type"></a>
- [`object_type`](features/document/object_type.md) — ORACC catalogue object-type value preserved as text.
<a id="otype"></a>
- [`otype`](features/mixed/otype.md) — Text-Fabric node type.
<a id="period"></a>
- [`period`](features/document/period.md) — ORACC catalogue period value preserved as text.
<a id="pleiades_coord"></a>
- [`pleiades_coord`](features/document/pleiades_coord.md) — ORACC catalogue Pleiades coordinate value preserved as text.
<a id="pleiades_id"></a>
- [`pleiades_id`](features/document/pleiades_id.md) — ORACC catalogue Pleiades identifier value preserved as text.
<a id="populated"></a>
- [`populated`](features/document/populated.md) — Integer flag: 1 when the ORACC edition contains parsed words, otherwise 0.
<a id="pos"></a>
- [`pos`](features/mixed/pos.md) — ORACC lexical part-of-speech value.
<a id="primary_publication"></a>
- [`primary_publication`](features/document/primary_publication.md) — ORACC catalogue primary-publication value preserved as text.
<a id="provenience"></a>
- [`provenience`](features/document/provenience.md) — ORACC catalogue provenience value preserved as text.
<a id="readingu"></a>
- [`readingu`](features/sign/readingu.md) — Compatibility alias for the ORACC Unicode cuneiform sign string in utf8.
<a id="ref"></a>
- [`ref`](features/mixed/ref.md) — Source reference string preserved from ORACC.
<a id="ruler"></a>
- [`ruler`](features/document/ruler.md) — ORACC catalogue ruler value preserved as text.
<a id="script"></a>
- [`script`](features/document/script.md) — ORACC catalogue script value preserved as text.
<a id="sense"></a>
- [`sense`](features/word/sense.md) — ORACC contextual lexical sense attached to the word occurrence.
<a id="sig"></a>
- [`sig`](features/word/sig.md) — ORACC occurrence analysis signature preserved verbatim; not a stable ORACC-TF lexeme identifier.
<a id="sign_json"></a>
- [`sign_json`](features/sign/sign_json.md) — Canonical JSON serialization of the source ORACC sign/GDL object.
<a id="source_id"></a>
- [`source_id`](features/mixed/source_id.md) — Source ORACC node identifier preserved from the input data.
<a id="src_path"></a>
- [`src_path`](features/sign/src_path.md) — Source GDL path of this sign within the ORACC word structure.
<a id="subgenre"></a>
- [`subgenre`](features/document/subgenre.md) — ORACC catalogue subgenre value preserved as text.
<a id="subproject"></a>
- [`subproject`](features/document/subproject.md) — ORACC subproject that supplied the document.
<a id="supergenre"></a>
- [`supergenre`](features/document/supergenre.md) — ORACC catalogue supergenre value preserved as text.
<a id="synthetic"></a>
- [`synthetic`](features/mixed/synthetic.md) — Integer flag marking ORACC-TF-synthesized section nodes or technical empty sign slots; synthetic slots carry no fabricated cuneiform content.
<a id="text_id"></a>
- [`text_id`](features/document/text_id.md) — ORACC text identifier without the subproject qualifier.
<a id="translation_eref"></a>
- [`translation_eref`](features/translation_unit/translation_eref.md) — Inclusive source line-range end declared by TEI xtr:eref.
<a id="translation_id"></a>
- [`translation_id`](features/translation_unit/translation_id.md) — Qualified ORACC-TF translation identity composed from the source document key and TEI unit identifier.
<a id="translation_label"></a>
- [`translation_label`](features/translation_unit/translation_label.md) — Translation label declared by the TEI source.
<a id="translation_rows"></a>
- [`translation_rows`](features/translation_unit/translation_rows.md) — Row count declared by the TEI translation source, when present.
<a id="translation_se_label"></a>
- [`translation_se_label`](features/translation_unit/translation_se_label.md) — Source edition label declared by the TEI translation source.
<a id="translation_source_id"></a>
- [`translation_source_id`](features/translation_unit/translation_source_id.md) — TEI xml:id declared on this translation unit, when supplied by the pinned official source.
<a id="translation_source_license"></a>
- [`translation_source_license`](features/translation_unit/translation_source_license.md) — Conservative translation licence statement, kept separate from corpusjson document licence metadata.
<a id="translation_source_license_url"></a>
- [`translation_source_license_url`](features/translation_unit/translation_source_license_url.md) — ORACC licensing guidance for the translation source; project-specific terms may differ.
<a id="translation_source_name"></a>
- [`translation_source_name`](features/translation_unit/translation_source_name.md) — Name of the pinned official TEI archive supplying this translation.
<a id="translation_source_sha256"></a>
- [`translation_source_sha256`](features/translation_unit/translation_source_sha256.md) — SHA-256 digest of the pinned official TEI archive supplying this translation.
<a id="translation_source_url"></a>
- [`translation_source_url`](features/translation_unit/translation_source_url.md) — Official source URL for the pinned TEI archive.
<a id="translation_sref"></a>
- [`translation_sref`](features/translation_unit/translation_sref.md) — Inclusive source line-range start declared by TEI xtr:sref.
<a id="translation_subtype"></a>
- [`translation_subtype`](features/translation_unit/translation_subtype.md) — Translation subtype declared by the TEI source, such as tr or dollar.
<a id="translation_text"></a>
- [`translation_text`](features/translation_unit/translation_text.md) — Plain running translation text extracted from source TEI markup.
<a id="translation_text_raw"></a>
- [`translation_text_raw`](features/translation_unit/translation_text_raw.md) — Canonical source TEI markup for the running translation, excluding note elements.
<a id="utf8"></a>
- [`utf8`](features/sign/utf8.md) — Unicode cuneiform string supplied by ORACC for this sign, when available.
<a id="word_id"></a>
- [`word_id`](features/sign/word_id.md) — Source ORACC word identifier containing this sign.
<a id="column_face"></a>
- [`column_face`](features/edge/column_face.md) — Edge from a column node to its containing face node.
<a id="face_document"></a>
- [`face_document`](features/edge/face_document.md) — Edge from a face node to its containing document node.
<a id="line_column"></a>
- [`line_column`](features/edge/line_column.md) — Edge from a line node to its containing column node.
<a id="line_face"></a>
- [`line_face`](features/edge/line_face.md) — Edge from a line node to its containing face node.
<a id="oslots"></a>
- [`oslots`](features/edge/oslots.md) — Text-Fabric warp edge from a non-slot node to its sign slots.
<a id="translation_document"></a>
- [`translation_document`](features/edge/translation_document.md) — Edge from a TEI translation unit to its qualified ORACC document.
<a id="translation_line"></a>
- [`translation_line`](features/edge/translation_line.md) — Edge from a TEI translation unit to each explicitly referenced source line in its inclusive range.
<a id="word_lex"></a>
- [`word_lex`](features/edge/word_lex.md) — Edge from a word occurrence to its ORACC-TF lexeme node.
<a id="word_line"></a>
- [`word_line`](features/edge/word_line.md) — Edge from a word node to its containing line node.
