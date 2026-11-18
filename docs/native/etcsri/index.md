# ETCSRI — Sumerian royal inscriptions in Text-Fabric

**Corpus:** Electronic Text Corpus of Sumerian Royal Inscriptions (ETCSRI), edited by the project directed by Gábor Zólyomi at Eötvös Loránd University. **Primary input:** ORACC project `etcsri`, JSON snapshot timestamp `2024-08-14T14:47:14`.

The native ORACC-TF converter currently preserves **1,456 source JSON editions**, **29,573 source word occurrences** and **68,403 source GDL signs**. It retains independently queryable `base`, `morph` and `morph2` values on **28,180** words and source `para` annotations on **3,584** words. These figures describe the pinned checked-in ORACC source, not a promise about an updated upstream edition.

The conversion models documents, textual sections, sentences, phrases, physical lines, words, source signs and determinatives. Nontext spans and nonword markers receive explicit, non-visible technical anchors without fabricated words or cuneiform signs. Preserve document-qualified identities such as `etcsri:Q000935`; raw `Q` IDs alone are not sufficient to identify a TF document in mixed-corpus work.

**Distribution:** this guide covers the code-only converter and standalone archive format. Verify any actual public ETCSRI release on the [ORACC-TF Releases page](https://github.com/alexsosn/ORACC-TF/releases), together with its ZIP checksum and manifest. The converter wheel contains no corpus data. A workflow artifact or locally generated candidate is not evidence of public publication.

Start at [Quick start](quick-start.md), then see [Features and source semantics](features.md) and [Source rights and citation](rights.md). A readable running translation is **not included** in the current JSON-derived TF graph. The standard TF browser is an advanced research interface; ordinary first-user catalogue/text search is tracked separately.

