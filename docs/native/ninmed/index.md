# NINMED — Nineveh Medical Encyclopaedia in Text-Fabric

**Corpus:** the ORACC `asbp/ninmed` edition of the *Nineveh Medical Encyclopaedia*, a project directed by Jon Taylor in collaboration with Mark Geller, funded by the Wellcome Trust. **Primary JSON snapshot timestamp:** `2024-07-05T13:32:14`.

The native ORACC-TF graph converts **159 readable source JSON bodies** into **65,089 actual source words**, preserving source line, word and GDL sign data, `cf` (citation form), `gw` (gloss) and `pos` (part of speech) with lexical `word_lex` relations where attested. A 160th source member, `P395407.json`, is zero bytes. It is quarantined as an explicit source exception, **not** represented as an empty medical text. The broader ORACC catalogue contains records without readable JSON bodies; those are not silently promoted to text editions.

This graph is an ORACC-based conversion and **does not reproduce** `Nino-cunei/ninmed`, which is a distinct ATF-derived edition. Among 34 matched source IDs, a pinned independent study found 33 differing complete word-form sequences. No alignment by word position or imported `uniqueLemma` is valid.

**Published distribution:** [Download NINMED Text-Fabric 0.1.0](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip) and its [SHA-256 checksum](https://github.com/alexsosn/ORACC-TF/releases/download/native-v0.1.0/ninmed-0.1.0.zip.sha256) from the public [native-v0.1.0 GitHub release](https://github.com/alexsosn/ORACC-TF/releases/tag/native-v0.1.0). Verify the checksum, unpack the archive and install `text-fabric==13.1.0`. Start the included versioned browser using `python -m tf.browser.start "app:$PWD/app" "--modules=" -noweb` from the extracted root. No converter, repository checkout or original JSON is needed for this download. Native TFQL search remains an expert interface, with ordinary first-user search tracked in [#189](https://github.com/alexsosn/ORACC-TF/issues/189).

Start with [Quick start](quick-start.md), [Source-specific features](features.md), and [Rights, acknowledgement and scope](rights.md). No official running translations are available in the converted JSON-derived graph.

