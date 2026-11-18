# Product goals — ORACC-TF

## Users and purpose

Assyriologists, Sumerologists and other ancient Near Eastern researchers should be able to acquire, browse, search, inspect and cite source-faithful ORACC-derived inscriptions and scholarly annotations without needing to understand the converter. The native Text-Fabric API remains available for advanced research.

## Representative research journeys

1. Find a RIAO/RINAP royal inscription by its source-qualified identifier or attested catalogue metadata, then read its lines in order.
2. Search an attested transliterated form, inspect its word, sign, lemma and morphology evidence, and return to its original document and line.
3. Explore the ETCSRI corpus and compare source-attested morphological annotations without silently normalizing uncertainty.
4. Query NINMED's lexical and medical vocabulary while preserving ORACC edition identity, source gaps and differences from independent Nino-cunei data.
5. Display and cite a translation only when an actually available, appropriately licensed source alignment supports it. Clearly identify absent translations.

## Milestones and evidence

- **Dataset delivery:** independently downloadable, versioned ETCSRI and NINMED native TF archives with source identity, corpus-specific instructions, fresh-install TF query and browser smoke, and verified public assets. Candidate ZIPs or CI artifacts alone do not count as published.
- **Researcher-facing reader:** an untrained first-time user can browse a catalogue, open a text, read lines, search ordinary forms, inspect a hit and cite a source without typing TFQL. This is a distinct UX milestone, not an excuse to postpone otherwise sound dataset publication indefinitely.
- **Sustained correctness:** published RIAO/RINAP, ETCSRI and NINMED behavior remains covered by representative real-source and first-user regression checks.

## Boundaries

Keep corpus semantics in the existing native TF data and the converter. Reuse the existing TF/Context-Fabric reading infrastructure wherever its demonstrated behavior suffices. Do not invent a second corpus store, generalized release-certification framework or translations absent from the source. Keep data/software licences and third-party imagery separate.

## Immediate product focus

Complete the actual ETCSRI/NINMED public-asset download-and-load milestone (issue #194), and the ordinary browse/read/search journey (issue #189). Distinguish them in release claims.

## Autonomous-development decision rules

- Select work by the researcher journeys above, not issue count or the ease of adding tests. Prefer finishing active PRs and releases over opening new tickets.
- Before introducing a new adapter, workflow, registry, protocol, or validation layer, demonstrate that an existing mechanism cannot meet a concrete acceptance need.
- Preserve source fidelity, access controls, security, and applicable upstream rights. Do not invent inferred text or silently weaken correctness gates.
- Batch repetitive data changes and reuse parameterized tests. Keep independent adversarial review proportional to risk, and validate the actual researcher path.
- If two successive cycles do not advance a journey or remove an observed blocker, reconsider the approach. Stop when the scoped deliverable works instead of generating optional infrastructure work.
