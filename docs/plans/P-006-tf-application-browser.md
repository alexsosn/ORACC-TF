---
id: P-006
title: Text-Fabric application and browser layer for ORACC-TF semantic datasets
type: plan
status: draft
priority: P1
depends_on: [R-006, P-005]
informs: [P-003]
updated: 2026-09-09
---

# Text-Fabric application and browser layer for ORACC-TF semantic datasets

## Purpose

Turn the accepted R-006 research into a release-ready implementation sequence for a source-faithful Text-Fabric application/browser layer. This plan owns the design contract for issues #71, #72, #73, #74, and #75. It coordinates with the standalone documentation work in #78 and the distribution-support-path gate in #79; it does not replace either ticket.

The normal app is **generated-by-default**. A newly registered semantic dataset must receive the ordinary app surface from authoritative registry/schema/release inputs without a maintainer copying another corpus app and editing release facts by hand.

## Normative inputs

The plan is pinned to the independently reviewed R-006 audit and to the merged P-005 distribution contract.

- Text-Fabric 13.1 / API v3 supplies the advanced-app runtime and browser/server. **No custom ORACC-TF web server** is part of this plan.
- BHSA is a reference implementation for the product pattern, not a template whose corpus-specific Hebrew/Biblical content is copied into ORACC-TF.
- P-005 fixes one generated lightweight repository per registered semantic dataset as the semantic distribution topology.
- P-005 also fixes a fail-closed manifest ownership boundary. App/docs paths may be added only by extending that ownership model; production work must not bypass or weaken it.
- R-006 establishes that Text-Fabric's advanced-app `data:<path>` form works, while the pinned Text-Fabric 13.1 public **data-only browser CLI** path does not constitute working repository discovery. #71 and #75 must therefore test the real supported published-repository discovery path rather than treating the research harness as product acceptance.

## Invariants

### 1. Source-faithful text presentation

The public original-text format is sign-slot based and uses source Unicode where present. The public transliteration format targets words using Text-Fabric's higher-level-node format support, e.g. `word#{form}`. Production code must never add a display-only semantic duplicate of `word.form` to sign slots.

A `synthetic=1` slot is a positional technical anchor. It remains part of TF topology but renders no fabricated cuneiform or transliteration. Tests must separately prove blank synthetic rendering and non-empty rendering on a semantic witness.

Lexeme presentation uses the established ORACC-TF lexeme identity and occurrence relation; it must not reinterpret `sig` as lexeme identity or invent external lexeme identifiers.

### 2. Browser feature policy is measured, not cargo-culted

R-006 measured `sign_json`, `gdl_json`, and `catalogue_json` as expensive automatic browser payloads while preserving them as programmatically loadable TF data. #73 may exclude those features from normal browser preload, but must not delete them from the corpus or make research/audit access impossible.

BHSA's global `noneValues` list is not copied. ORACC-TF has source-bearing exact `NA` and `unknown` values, so missing-value display policy requires feature-specific evidence.

### 3. Generated release state is authoritative

The app generator consumes authoritative inputs:

```text
dataset registry
+ emitted TF schema / node and feature inventory
+ reviewed shared presentation policy
+ upstream/release provenance
+ generated documentation destinations
+ optional narrow validated override
    -> deterministic app/config/static inputs
```

Release version, licence, source state/hash, emitted feature inventory, documentation destinations, and standard text formats are generated facts. A **narrow validated override** may contain only genuinely non-derivable presentation needs such as reviewed branding/CSS or a proven non-declarative resolver. A normal dataset must not require a hand-maintained full per-dataset application source tree.

### 4. Qualified source identity is mandatory

Any official ORACC document/passage link is derived from qualified `subproject:Q` identity. Bare Q-number joins are forbidden because collisions are a measured corpus fact. #74 may generate a collision-safe URL suffix feature or, only if declarative Text-Fabric configuration cannot express the verified official URL contract, the smallest independently reviewed resolver hook.

Do not guess lexeme/glossary URLs from `cf`, `gw`, `pos`, or `lang` without a verified stable upstream identity mapping.

### 5. Documentation remains semantically scoped

Text-Fabric's feature-help URL is feature-name-centric, whereas P-003 canonical feature pages are node-type scoped. #73 must generate a stable feature-name entry point that links to all applicable canonical pages rather than collapsing mixed-scope features into a falsely typed page.

#78 owns the standalone documentation product: quick start, corpus scope/provenance, model, public formats, generated feature reference, browser/query guidance, hazards, citation/bibliography/licensing, release history/known issues, and app/help cross-links. P-006 owns integration points, not duplicate documentation content.

## Distribution interface and #79 gate

P-005 has accepted the semantic topology but not yet the final support-path extension. The desired dedicated-distribution shape is:

```text
repository root is the semantic distribution root
./app
./tf/<version>
./docs
```

This shape is a planning interface subject to #79's independent review. #79 must extend manifest ownership/integrity so generated app and documentation trees are first-class owned release artifacts. #71 must not copy app files into an already staged repository as foreign/untracked content, and no implementation may weaken P-005's fail-closed boundary to make app packaging convenient.

Explicit dependency edge: `#79 -> #71` for production packaging/discovery acceptance. Research/prototyping allowed by the issue bodies may occur earlier, but #71 cannot be finalized until #79 has accepted the canonical support-path/ownership contract.

## Phase graph

The implementation sequence is deliberately small and independently reviewable:

```text
R-006 / #69 accepted
       |
       v
P-006 / #70 reviewed
       |
       +-----------------> #79 distribution support-path ownership
       |                         |
       |                         v
       +-----------------------> #71 app packaging/discovery
                                  |
                        #71 -> (#72 || #73)
                                  |
                        +---------+---------+
                        |                   |
                       #72                 #73
                        |                   |
                        +---------+---------+
                                  v
                                 #74
                                  |
                       +----------+----------+
                       |                     |
                      #78                   #79
                       |                     |
                       +----------+----------+
                                  v
                                 #75
```

Completion edges are explicit: `#78 -> #75` and `#79 -> #75`. #75 is not a release-closing browser acceptance gate until both the standalone documentation surface and manifest-owned support paths are present in a clean generated distribution.

### Phase A — #71: generated app packaging and discovery

Deliver the generator/distribution foundation, not final display polish.

Acceptance includes:

- ordinary per-dataset app artifacts are generated from authoritative inputs;
- any override schema is narrow, deterministic, validated, and unable to replace derivable release/schema facts;
- #79-approved canonical app path is manifest-owned and integrity-bound;
- a clean generated distribution is discovered through the supported Text-Fabric 13.1 repository/app mechanism;
- the known data-only browser CLI limitation is not disguised as working discovery;
- no custom server and no unnecessary `app.py` hook.

### Phase B — #72: source-faithful text and lexeme formats

Implement and test cuneiform, word transliteration, and lexeme formats against fixture and real-corpus witnesses.

Required witnesses include semantic non-empty lines, zero-sign words/technical anchors, multilingual/source-uncertain forms, and representative lexeme occurrences. Synthetic anchors remain blank. Text formatting must not mutate corpus semantics merely to satisfy browser templates.

### Phase C — #73: node presentation, preload policy, and docs integration

Implement reviewed `typeDisplay` and browser policy for every current node type: `document`, `face`, `column`, `line`, `chunk`, `phrase`, `word`, `lex`, and `sign`.

`chunk` is hidden/collapsed by default as source machinery rather than asserted linguistic sentence structure. Browser-heavy JSON audit features may be excluded from preload based on R-006 measurements while remaining in TF. Feature help resolves through generated stable feature-name entry points into P-003 canonical scoped pages.

#72 and #73 may proceed in parallel only after #71's foundation is accepted.

### Phase D — #74: generated provenance and source links

Generate app provenance from the same release state that produced the TF bytes and distribution manifest. No manually synchronized version/source/licence facts are allowed.

Official ORACC links must be collision-safe and based on qualified document identity. Prefer declarative generated link data. Introduce a Python hook only for a demonstrated non-declarative requirement and cover it with direct tests plus independent review.

### Phase E — #75: real browser/server acceptance

Exercise a clean, standalone generated distribution with the real Text-Fabric browser/server surface and representative user operations. This gate must cover repository-style app discovery, passage rendering, search/query, export where supported, feature/help links, source/provenance links, static assets, and failure behavior.

The lower-level browser factory used by R-006 is characterization evidence only; it cannot substitute for this public discovery/E2E gate.

## Documentation/release coordination

- #78 provides the complete standalone documentation product consumed by the app and release.
- #79 defines and implements canonical manifest-owned support paths.
- #81/#82/#84 may implement or validate pieces of #78; their ownership remains with the documentation workstream.
- #83 consumer-route matrix and P-005 follow-on publication tickets consume the generated distribution contract; they do not redefine P-006 app semantics.
- Translation-specific browser presentation is deferred until P-001.M9/#16 has a stable reviewed contract. The initial app must remain useful without translations.

## TDD and independent-review gates

Every production child ticket follows the project loop:

1. **Research** the exact current Text-Fabric/upstream/release surface needed by that ticket and record pinned evidence.
2. **Plan/design** the smallest implementation and explicit stop conditions before code changes.
3. Commit tests-only **RED** evidence that fails for the missing behavior and does not fail unrelated contracts.
4. Implement the smallest change that turns the intended contract **GREEN**.
5. Run focused, whole-corpus, generated-reference, cross-validation, distribution, and browser gates that are relevant to the changed surface.
6. Perform a logically **independent review** on the exact final head. Any blocker creates a new RED-first sub-loop; a review from an earlier head is stale.
7. After a passing exact-head review, make no further code/docs commits before merge.

The plan itself follows the same rule in #70: its tests must be RED before P-006 exists, GREEN after registration, and the final planning head receives a logically independent adversarial review before #71 is design-ready.

## Stop conditions

Stop and reopen research/design rather than weakening invariants if any of the following occurs:

- supported Text-Fabric app/browser discovery differs materially from pinned Text-Fabric 13.1 behavior;
- transliteration cannot be rendered from word-level source features without semantic duplication or loss;
- synthetic technical slots leak fabricated visible content into rendering/search/export;
- canonical app/docs paths cannot be incorporated into P-005 manifest ownership without weakening fail-closed integrity;
- qualified ORACC source URLs cannot be generated deterministically from authoritative identity;
- generated app provenance cannot be bound to the same immutable release state as TF bytes;
- browser preload exclusions make research-critical features unavailable through the programmatic API;
- acceptance requires a custom ORACC-TF server rather than Text-Fabric's server/runtime;
- an implementation ticket cannot produce an observable RED or exact-head independent review.

## Completion criteria for #70

P-006 is complete when:

- this document and registry/fact-policy metadata pass deterministic docs validation;
- accepted R-006 facts are distinguished from #79/#78 open implementation decisions;
- #71–#75 responsibilities and dependency edges are explicit and non-overlapping;
- generated-by-default, source-faithful, qualified-identity, release-provenance, and no-custom-server invariants are frozen;
- the planning PR is exact-head GREEN;
- a logically independent adversarial reviewer finds no unresolved blocker on the exact final SHA.
