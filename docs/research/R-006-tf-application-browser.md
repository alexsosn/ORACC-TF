---
id: R-006
title: Text-Fabric application and browser architecture for ORACC-TF datasets
type: research
status: active
priority: P1
depends_on: [P-001, R-003, R-005]
updated: 2026-09-08
---

# Text-Fabric application and browser architecture for ORACC-TF datasets

## Question

What corpus-specific application layer should a published ORACC-TF semantic dataset ship so that Text-Fabric notebook and browser users get source-faithful cuneiform, transliteration, useful node presentation, documentation and source links without creating a second semantic model or a custom web server?

This research is the evidence gate for issue #69 and the normative input to plan issue #70 and implementation issues #71-#75. It does **not** add a production corpus app.

## Pinned executable baseline

The comparison was reproduced against the following current surfaces rather than copied from BHSA prose:

- ORACC-TF base `cc078176195071af1e9ef907decafa65066ed91a`, whose package constraint is `text-fabric>=13.1,<14`;
- Text-Fabric `v13.1.0` / API version 3, pinned during the audit to tag commit `dd227ce62b5536de53a0e20eac98c0459da8fd3d`;
- ETCBC/BHSA `master` `4db00e2157915495e1a4d3d57e41223df24775da` (2026-01-18).

Text-Fabric 13.1 supplies the browser/server and the advanced app runtime. A corpus app configures that runtime; it does not need its own Flask/server implementation. `config.yaml` and `app.py` are both optional. `data:/path/to/data` works with the advanced-app loader, while repository-style loading discovers a conventional app next to the TF data location. Text-Fabric also loads app CSS/static assets and supports optional Python specialization where declarative configuration is insufficient.

BHSA confirms the intended pattern. Its current app consists primarily of `app/config.yaml`, one static logo, and a very small `app.py` whose only corpus-specific method is `getLexId`. Its text/lexeme formats are declared in `tf/2021/otext.tf`; the app config mainly controls display, feature preloading, missing-value presentation, documentation, provenance/web links, and writing-system policy.

ORACC-TF currently has no production app source. Its generated `otext` declares the dynamic `document,face,line` section hierarchy but no named text formats. The corpus graph already contains the presentation inputs: sign-level `utf8`/`readingu`, word-level `form`, canonical lexeme fields, qualified document identity, generated feature descriptions, and `synthetic=1` technical slots. The missing layer is presentation/configuration, not new corpus semantics.

## Measured current behavior

### Advanced-app load and feature exclusion

The research harness `scripts/research_issue69_tf_app.py` loads the real built `assyrian-royal-inscriptions` corpus through Text-Fabric's actual advanced-app API, not through a mock. The pinned measurement artifact from research head `e0ad631e8ff683b63a842c3a920c1976981c4fdc` is GitHub Actions artifact `10033165907` (artifact digest `sha256:233c72bb51c445150799f3df1e30d03e20722770accb61d4292e1c1f0a34571c`). The workflow ran three cold-cache repetitions for baseline and exclusion profiles, alternating order and removing Text-Fabric's binary cache before each profile.

The three candidate audit-heavy features occupy:

| feature | source `.tf` bytes |
|---|---:|
| `catalogue_json` | 3,039,583 |
| `gdl_json` | 88,690,213 |
| `sign_json` | 80,687,720 |
| **total** | **172,417,516** |

On that GitHub-hosted Linux runner, median advanced-app cold load changed from **54.396 s** to **49.233 s** when those three features were excluded from automatic app loading, a 5.163 s / 9.49% reduction. Median process peak RSS changed from **2,690,840 KiB** to **2,000,900 KiB**, a 689,940 KiB / 25.64% reduction. All three features were loaded in every baseline run and absent from every excluded run. These are reproducible directional measurements for the pinned runner and corpus, not an SLA or a general hardware claim.

`excludedFeatures` changes advanced-app/browser preload only. The `.tf` feature files remain part of the dataset and remain explicitly loadable through the programmatic Text-Fabric API. The research therefore supports excluding `sign_json`, `gdl_json`, and `catalogue_json` from normal browser preload while preserving them as research/audit data.

### Missing/sentinel values

BHSA configures `noneValues` as `absent`, `n/a`, `none`, `unknown`, `null`, `NA`. The ORACC-TF whole-corpus census does **not** justify copying that policy:

- `NA`: 46 exact occurrences, in source-valued `form` and `frag` features;
- `unknown`: 56 exact occurrences, in `exemplars` and `provenience`;
- the other four BHSA candidates: zero exact occurrences.

Because those observed values can encode source uncertainty/content rather than a generic missing-value sentinel, the initial ORACC-TF app should not globally hide them. Start with no copied global `noneValues`; add a value only after a feature-specific/source-grounded audit proves that treating it as absent cannot erase meaningful source information.

### Text-format behavior

Text-Fabric 13.1 explicitly supports formats targeted at a non-slot node type using `nodeType#template`. Its own text API documentation discusses the case where signs are slots but words carry a higher-level feature. The source-faithful ORACC-TF prototype therefore uses:

```text
@fmt:text-orig-full={utf8}
@fmt:text-trans-full=word#{form} 
```

This keeps cuneiform authoritative on sign slots and transliteration authoritative on word nodes. It does **not** duplicate `word.form` onto signs.

The initial real-corpus probe exposed an important research-harness defect: choosing the first line that contained a synthetic slot could select an entirely empty structural line, yielding empty strings for both formats while the workflow still passed. The adversarial regression `tests/test_issue69_format_evidence.py` now separates the two claims:

1. render a technical synthetic slot directly and require both public candidate formats to return the empty string;
2. find a real non-synthetic Unicode sign, ascend to its containing line, and require non-empty cuneiform and word-level transliteration.

The real-corpus research workflow enforces the same separation and the known whole-corpus `synthetic_slot_count == 689`. Thus synthetic anchors remain positionally present in TF but are not fabricated into visible cuneiform or transliteration.

### Browser-stack baseline and a Text-Fabric 13.1 data-only discrepancy

The advanced-app call `tf.app.use("data:<tf-root>")` works on both the fixture and the real ORACC-TF corpus. The public browser setup path is different in pinned Text-Fabric 13.1: `tf.browser.command.argParam()` recognizes `data:<path>`, but `argApp()` returns no app specification when `appName` is absent, so `tf.browser.web.setup()` reports `No TF dataset specified` / `Could not set up TF` for the data-only browser form. Research must not describe that CLI/discovery route as working.

To characterize the browser stack without disguising that limitation, `probe_browser_routes()` starts from the successfully loaded real `AdvancedApp`, passes it through `makeTfKernel()`, and then uses Text-Fabric's browser Flask `factory`. The research workflow records this separately as `browser.json`. This is evidence about rendering/query/export route behavior **inside the Text-Fabric browser stack**, not proof that a clean published repository will be discovered correctly by the public browser command.

On the fixture, the vanilla data-only AdvancedApp has no corpus-specific header: `/passage` and `/query` return 200, while `/` and `/export` currently return 500 during header rendering. That is useful baseline behavior, not the desired product contract. Production repository-style app discovery and all-route browser acceptance remain mandatory in #71/#75.

## Capability matrix

| Capability | Current evidence | Decision |
|---|---|---|
| Generic browser/server | Text-Fabric 13.1 `tf.browser` supplies it | Reuse upstream TF; no ORACC-TF server |
| Vanilla advanced app | Real local corpus loads through `data:<tf-root>` | Use as baseline/failure comparison |
| Data-only public browser setup | Pinned TF 13.1 parser/setup behavior | Does not work; do not rely on it |
| Browser stack below discovery | `AdvancedApp -> makeTfKernel -> browser factory` fixture/real probe | Characterization only; not production discovery proof |
| Declarative app config | TF 13.1 + current BHSA | Default mechanism |
| Sign-level original text | Real `utf8` feature + TF format prototype | `text-orig-full={utf8}` |
| Word-level transliteration over sign slots | TF `nodeType#template` + fixture/real probe | `text-trans-full=word#{form}`; no sign duplication |
| Synthetic empty position | ADR-0001 corpus + rendering regression | Structurally present, visually empty |
| Browser preload exclusion | Real advanced-app measurements | Exclude the three large JSON audit payloads from preload |
| `noneValues` | Whole-corpus exact-value census | Do not copy BHSA list |
| `typeDisplay` | TF 13.1 configuration surface + BHSA precedent | Use declarative per-type policy |
| Static/CSS | TF app discovery/static support | Allowed for readability/branding, no semantics |
| Feature-help links | TF `docs.featureBase` is feature-name-centric | Generate a flat feature entry point over P-003 type-scoped pages |
| External document links | TF `webFeature`/`webUrl`; ORACC qualified identities | Generate collision-safe qualified link data or smallest resolver hook |
| Lexeme web links | No verified stable ORACC lexeme identity mapping | Do not emit guessed links |
| Release provenance | P-005/P-002 distribution inputs | Generate from the same release state as TF bytes |
| Custom Python hook | Not needed for formats/display/preload/docs | Omit by default; permit only for a proven non-declarative requirement |
| Browser/search/export E2E | Generic TF runtime is established; production app not yet present | Mandatory production acceptance in #75, not claimed complete by this research PR |

## Browser display policy by current node type

The app should reinforce the adopted ORACC-TF model rather than give every source node equal visual weight.

| node type | recommended browser policy |
|---|---|
| `document` | Visible top section. Primary identity is the qualified dataset document key (`subproject:Q`), with compact source-supported catalogue fields such as designation/ruler/period where useful. |
| `face` | Visible section boundary using source label/ref. |
| `column` | Structural detail, not promoted to the rigid Text-Fabric section hierarchy. Give it a compact source label when expanded. |
| `line` | Lowest primary browsable/verse-like section using the source line label/`lnno`. |
| `chunk` | Hidden/collapsed by default. ORACC `chunk_type=sentence` is source machinery and must not be presented as a linguistic sentence without independent evidence. |
| `phrase` | Structural detail available when expanded; show only source-supported labels/subtypes. |
| `word` | `form` is the primary transliterated representation; expose compact language/POS/lexical evidence. Do not present `sig` as lexeme identity. |
| `lex` | Canonical citation identity is based on the established lexeme key (`lang,cf,gw,pos`); display `cf` prominently with `gw`/POS/language detail and use `lexOcc: word`. |
| `sign` | Show source Unicode/content where present. A `synthetic=1` sign is a technical positional anchor and has no visible source sign text. |

Exact typography, hidden defaults beyond `chunk`, and compact feature lists belong to #73 and must be tested against representative real browser output rather than frozen here as CSS trivia.

## Documentation breadth

The BHSA reference is useful here as a **documentation product pattern**, not as corpus content to copy. Its repository/browser documentation surface goes beyond feature help: it has a user-facing landing orientation, corpus/topic reference material, bibliography/references, historical and colophon-style provenance, news/change-oriented material, static documentation assets, and app-to-doc cross-linking. Those categories explain how a mature Text-Fabric corpus helps a user move from discovery to interpretation and provenance.

ORACC-TF should adopt the transferable categories through P-003 and #78: a concise per-corpus landing page; corpus scope and topic/reference pages generated or curated from authoritative metadata; bibliography/references tied to source and release provenance; history/version and colophon/provenance material derived from release state; a changelog or news-style release surface where it adds user value; documentation assets owned by the generated distribution; and explicit app-to-doc links for feature help, corpus guidance, source/provenance, and release information. These are product-level documentation responsibilities, distinct from the narrower `docs.featureBase` browser integration described below.

BHSA-specific theological/Biblical corpus explanations, Hebrew-specific reference material, SHEBANQ-oriented guidance, BHSA bibliography selections, project history narratives, branding assets, screenshots, and news content are **not transferable** facts and must not be cargo-culted into ORACC-TF. #78 should reproduce the useful information architecture with ORACC-specific evidence and generated provenance rather than cloning BHSA pages. The app work should expose stable links into that documentation product; it should not become the owner of the documentation content itself.

## Documentation integration

Text-Fabric's app documentation contract is feature-name-centric (`docs.featureBase` substitutes `<feature>`), while P-003 deliberately generates richer canonical pages by node type, e.g. `docs/reference/features/<node-type>/<feature>.md`. ORACC-TF should not flatten the semantic scope of mixed features merely to satisfy one browser URL.

The production docs layer should generate a stable flat feature-name entry point or redirect/index that links to every applicable canonical type-specific page. Mixed features such as `cf`, `lang`, or `pos` must remain visibly multi-scope. #73 owns browser configuration; #78 owns the complete per-corpus documentation product.

## Provenance and source links

Hand-maintained app source should contain semantic presentation policy only. Release facts must flow from authoritative build inputs:

```text
dataset registry + release/distribution manifest + upstream lock
    -> TF data + generated app provenance + generated docs/source links
```

Do not maintain a second manually synchronized corpus version, source hash, licence, DOI, or release state in `config.yaml`.

Text-Fabric 13.1 can form web links from a `provenanceSpec.webFeature` or from section-heading substitutions in `webUrl`. ORACC-TF's level-1 section heading is intentionally the qualified identity `subproject:Q`. A plain template cannot safely transform that identity into an official ORACC subproject path, and bare Q-numbers are known to collide (for example across `rinap5` and `rinap5p1`).

The safe production choices for #74 are therefore:

1. generate a small collision-safe URL suffix/path feature from authoritative qualified document identity and keep the app declarative; or
2. if that cannot express the verified official URL contract, add the smallest reviewed resolver hook.

Never route by bare Q-number, and do not infer lexeme/glossary URLs from `cf/gw/pos/lang` without a verified stable official identity mapping.

## Distribution boundary

P-005 has accepted the **semantic boundary**: each published distribution represents one semantic dataset. It has **not** yet accepted the final internal app/docs path layout. That canonical-path and manifest-ownership decision remains #79's review gate.

The central builder should keep per-dataset hand-maintained app policy isolated under a dataset-keyed source path such as:

```text
apps/<dataset>/...
```

For the generated one-dataset repository, R-006 recommends that #79 explicitly test the simple repository-root hypothesis:

```text
README.md
manifest.json
app/
tf/<tf-version>/
docs/
```

That layout is a **research recommendation/hypothesis**, not an already accepted #79 decision. #79 must verify Text-Fabric discovery, Agora/GitStore loading, manifest ownership and backwards compatibility before it becomes normative. Central local staging may still use `<output-base>/<dataset>/...`; local staging shape does not by itself determine the published repository paths.

P-005.PH0 deliberately rejects unowned staged content. Therefore #71/#79 must make the generated app tree (and later docs/support files) explicit manifest-owned, integrity-checked release artifacts. They must **not** weaken the existing unowned-path, transactional replacement, replay, symlink, or path-overlap protections merely to make copying `app/` convenient.

## Rejected alternatives

- **Custom ORACC-TF web server:** no evidence requires one; Text-Fabric already supplies the server/browser runtime.
- **Copy word transliteration onto sign slots:** creates a second, false sign-level semantic representation; TF already supports word-target formats.
- **Visible placeholder text for synthetic slots:** contradicts ADR-0001; the anchor is positional, not a source sign claim.
- **Copy BHSA `noneValues`:** whole-corpus census shows the values are not transferable policy.
- **One global app for every future ORACC dataset:** couples unrelated corpus presentation and encourages dataset-condition spaghetti.
- **Manually synchronized app provenance:** can drift from immutable release bytes and source locks.
- **Bare-Q ORACC links:** collision-unsafe under the existing data model.
- **Guessed lexeme URLs:** no stable mapping was established.
- **Allow arbitrary `app/`/`docs/` outside the P-005 manifest:** would regress the reviewed fail-closed distribution boundary.

## Implementation decomposition

The research result maps to already separated work:

- #70: synthesize this research into the next P-series application plan;
- #79: extend P-005 path/manifest ownership for canonical app/docs/release support paths;
- #71 / Phase A: per-dataset app source/materialization/discovery, coordinated with #79;
- #72 / Phase B: production cuneiform, word-level transliteration and lexeme formats;
- #73 / Phase C: `typeDisplay`, measured preload policy, docs links and CSS/static presentation;
- #74 / Phase D: generated release provenance and collision-safe official ORACC links;
- #75 / Phase E: real clean-distribution Text-Fabric browser/server acceptance including navigation, search, export, docs/source links and shutdown behavior;
- #78: assemble the comprehensive per-corpus documentation bundle from P-003 outputs and app/release metadata.

Production tickets must repeat their own current-API/source research gate, RED-first TDD, exact-head validation and logically-independent adversarial review. This R-006 decision is a design input, not permission to cargo-cult BHSA implementation details.

## Stop conditions

Return to research/plan review rather than implementing if:

- Text-Fabric changes the app/format/discovery contract materially;
- source-faithful word-level transliteration cannot be rendered without duplicating or strengthening sign semantics;
- synthetic technical positions become visible as fabricated source text in any public format/search/export path;
- a proposed `noneValues` rule suppresses meaningful source uncertainty/content;
- official ORACC linking cannot preserve qualified `subproject:Q` identity deterministically;
- app/docs publication would require weakening P-005 manifest ownership/integrity;
- release/app provenance cannot be generated from the same authoritative immutable release state;
- a custom server or broad Python app layer is proposed without new evidence that declarative Text-Fabric support is insufficient.
