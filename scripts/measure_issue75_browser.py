#!/usr/bin/env python3
"""Bounded real TF browser + source-semantic smoke without the ORACC-TF builder.

The distribution itself supplies tf/ and app/. Run this script from any
directory with Text-Fabric 13.1 available; it never imports oracc_tf.
"""

from __future__ import annotations

import argparse
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path

from tf.advanced.app import findApp
from tf.browser.kernel import makeTfKernel
from tf.browser.web import Web, factory


class BrowserSmokeError(ValueError):
    """Standalone browser failed a researcher-visible semantic check."""


def validate_browser_query(payload: object) -> int:
    """Require a successful, nonempty result from the actual browser endpoint."""
    if not isinstance(payload, dict) or payload.get("status") is not True:
        raise BrowserSmokeError("browser query response malformed or unsuccessful")
    count = payload.get("nResults")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise BrowserSmokeError("browser query returned no valid results")
    return count


class _FocusedSectionParser(HTMLParser):
    """Read selected TF passage identity without relying on an HTML snapshot."""

    def __init__(self, expected_section: str):
        super().__init__()
        self.expected_section = expected_section
        self.matched = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "details":
            return
        fields = dict(attrs)
        if (fields.get("seq") == self.expected_section
                and "focus" in (fields.get("class") or "").split()):
            self.matched = True


def validate_browser_passage(
    payload: object, expected_text: str, *, selected_section: str | None = None
) -> bool:
    """Check actual TF passage table text and optional focused section identity."""
    if not isinstance(payload, dict):
        raise BrowserSmokeError("browser passage response malformed")
    table = payload.get("table")
    if not isinstance(table, str) or not table or expected_text not in unescape(table):
        raise BrowserSmokeError("browser passage does not render source-selected text")
    if selected_section is not None:
        selector = _FocusedSectionParser(selected_section)
        selector.feed(table)
        if not selector.matched:
            raise BrowserSmokeError("browser passage failed to focus selected section")
    return True


class _ExpandedWordParser(HTMLParser):
    """Collect named TF feature spans inside one expanded focused passage."""

    def __init__(self, section: str, names: set[str]):
        super().__init__(convert_charrefs=True)
        self.section = section
        self.names = names
        self.details_depth = 0
        self.focus_depth = 0
        self.pretty_depth = 0
        self.feature_depth = 0
        self.active_feature: str | None = None
        self.feature_chunks: list[str] = []
        self.values: dict[str, list[str]] = {name: [] for name in names}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        fields = dict(attrs)
        if tag == "details":
            self.details_depth += 1
            if (
                self.focus_depth == 0
                and fields.get("seq") == self.section
                and "focus" in (fields.get("class") or "").split()
                and "open" in fields
            ):
                self.focus_depth = self.details_depth
        elif tag == "div" and self.focus_depth:
            if self.pretty_depth:
                self.pretty_depth += 1
            elif "pretty" in (fields.get("class") or "").split():
                self.pretty_depth = 1
        elif tag == "span" and self.focus_depth and self.pretty_depth:
            if self.feature_depth:
                self.feature_depth += 1
            else:
                classes = set((fields.get("class") or "").split())
                feature = next((name for name in self.names if name in classes), None)
                if feature is not None:
                    self.active_feature = feature
                    self.feature_depth = 1
                    self.feature_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self.feature_depth:
            self.feature_depth -= 1
            if self.feature_depth == 0 and self.active_feature:
                self.values[self.active_feature].append("".join(self.feature_chunks))
                self.active_feature = None
                self.feature_chunks = []
        elif tag == "div" and self.focus_depth and self.pretty_depth:
            self.pretty_depth -= 1
        elif tag == "details":
            if self.focus_depth == self.details_depth:
                self.focus_depth = 0
                self.pretty_depth = 0
            self.details_depth = max(0, self.details_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.focus_depth and self.pretty_depth and self.active_feature:
            self.feature_chunks.append(data)


def validate_expanded_word_features(
    payload: object, section: str, features: dict[str, str]
) -> bool:
    """Match source values against rendered named TF features in selected line."""
    if not isinstance(payload, dict) or not isinstance(payload.get("table"), str):
        raise BrowserSmokeError("expanded browser passage response malformed")
    parser = _ExpandedWordParser(section, set(features))
    parser.feed(payload["table"])
    for feature, value in features.items():
        rendered = parser.values.get(feature, ())
        if not value or not any(value in item for item in rendered):
            raise BrowserSmokeError(
                f"expanded browser passage did not display source {feature}={value!r}"
            )
    return True


class _TranslationTextParser(HTMLParser):
    """Read actual translation_text feature spans from TF's pretty output."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts: list[str] = []
        self.values: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "span":
            return
        if self.depth:
            self.depth += 1
        elif "translation_text" in (dict(attrs).get("class") or "").split():
            self.depth = 1
            self.parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "span" or not self.depth:
            return
        self.depth -= 1
        if not self.depth:
            self.values.append("".join(self.parts))
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)


def validate_browser_translation(payload: object, expected_text: str) -> bool:
    """Do not confuse source text in navigation/messages with rendered translation."""
    if not isinstance(payload, dict) or not isinstance(payload.get("table"), str):
        raise BrowserSmokeError("browser translation response malformed")
    parser = _TranslationTextParser()
    parser.feed(payload["table"])
    expected = " ".join(expected_text.split())
    if not expected or not any(" ".join(v.split()) == expected for v in parser.values):
        raise BrowserSmokeError("browser translation not rendered in named TF feature")
    return True


def smoke_browser(
    tf_root: Path | str,
    app_root: Path | str,
    *,
    version: str,
    document_key: str,
    line_ref: str,
    expected_glyph: str,
    expected_form: str,
    require_translation: bool = False,
) -> dict[str, object]:
    tf_root = Path(tf_root).resolve()
    app_root = Path(app_root).resolve()
    name = f"app:{app_root}"
    app = findApp(
        name, "", None, "github", True,
        locations=[str(tf_root)], modules=[""],
        version=version, silent="deep",
    )
    if app is None or app.api is None:
        raise BrowserSmokeError("standalone Text-Fabric app failed to load")
    api = app.api
    docs = [
        n for n in api.F.otype.s("document")
        if api.F.document_key.v(n) == document_key
    ]
    if len(docs) != 1:
        raise BrowserSmokeError(
            f"document_key lookup must find exactly one document: {document_key}"
        )
    lines = [
        n for n in api.L.d(docs[0], otype="line")
        if api.F.line.v(n) == line_ref
    ]
    if len(lines) != 1:
        raise BrowserSmokeError(f"passage lookup failed: {document_key}:{line_ref}")
    line = lines[0]
    sections = tuple(str(value) for value in api.T.sectionFromNode(line, fillup=True))
    if len(sections) != 3 or sections[0] != document_key or sections[2] != line_ref:
        raise BrowserSmokeError("selected browser passage section identity mismatches source")
    cuneiform = api.T.text(line, fmt="text-orig-full")
    transliteration = api.T.text(line, fmt="text-trans-full")
    if expected_glyph not in cuneiform:
        raise BrowserSmokeError("cuneiform output missing source glyph")
    if expected_form not in transliteration:
        raise BrowserSmokeError("transliteration output missing source form")

    # A selected document need not have an empty-sign source word. Check
    # the actual corpus-wide technical anchors (689 in the pinned edition).
    synthetic = [
        n for n in api.F.otype.s("sign")
        if api.F.synthetic.v(n) == 1
    ]
    if any(api.T.text(n, fmt="text-orig-full").strip() for n in synthetic):
        raise BrowserSmokeError("technical synthetic sign rendered visible text")

    lexical = sum(
        bool(api.E.word_lex.f(n))
        for n in api.L.d(docs[0], otype="word")
    )
    if lexical == 0:
        raise BrowserSmokeError("canonical word_lex link missing")
    # Source-backed expanded lexical inspection may use another line in the
    # same qualified document when its first line lacks a glossed word.
    lexical_word = next(
        (
            word for word in api.L.d(docs[0], otype="word")
            if api.E.word_lex.f(word)
            and isinstance(api.F.cf.v(word), str) and api.F.cf.v(word).strip()
            and isinstance(api.F.gw.v(word), str) and api.F.gw.v(word).strip()
            and api.L.u(word, otype="line")
        ),
        None,
    )
    if lexical_word is None:
        raise BrowserSmokeError("no source-backed glossed lexical word for browser")
    lexical_line = api.L.u(lexical_word, otype="line")[0]
    lexical_sections = tuple(
        str(value) for value in api.T.sectionFromNode(lexical_line, fillup=True)
    )
    browser_word_features = {
        "cf": api.F.cf.v(lexical_word),
        "gw": api.F.gw.v(lexical_word),
    }
    if not next(iter(api.S.search("word", limit=1, silent="deep")), None):
        raise BrowserSmokeError("representative TF search yielded nothing")

    kernel = makeTfKernel(app, name)
    if not kernel:
        raise BrowserSmokeError("browser kernel failed to start")
    webapp = factory(Web(kernel))
    routes: dict[str, int] = {}
    browser_passage_formats = {}
    with webapp.test_client() as client:
        for route in ("/", "/passage", "/query", "/export"):
            response = client.get(route)
            routes[route] = response.status_code
            if response.status_code != 200 or not response.data:
                raise BrowserSmokeError(f"browser route unusable: {route}")
        for text_format, expected in (
            ("text-orig-full", expected_glyph),
            ("text-trans-full", expected_form),
        ):
            selected = client.post(
                "/passage",
                data={
                    "jobName": "oracc-source-passage",
                    "sec0": sections[0],
                    "sec1": sections[1],
                    "sec2": sections[2],
                    "textFormat": text_format,
                    "features": "cf pos",
                    "edgeFeatures": "word_lex",
                },
            )
            if selected.status_code != 200:
                raise BrowserSmokeError("selected browser passage returned an HTTP error")
            validate_browser_passage(
                selected.get_json(silent=True), expected, selected_section=sections[2]
            )
            browser_passage_formats[text_format] = expected

        # The prior collapsed passage proves text/navigation but does not
        # render the inspection panel. Expand a real source-glossed line.
        expanded = client.post(
            "/passage",
            data={
                "jobName": "oracc-lexical-inspect",
                "sec0": lexical_sections[0],
                "sec1": lexical_sections[1],
                "sec2": lexical_sections[2],
                "passageOpened": lexical_sections[2],
                "textFormat": "text-trans-full",
                "features": "cf gw pos",
                "queryFeatures": "1",  # TF form omits unchecked interface options.
                "edgeFeatures": "word_lex",
            },
        )
        if expanded.status_code != 200:
            raise BrowserSmokeError("expanded browser passage returned an HTTP error")
        validate_expanded_word_features(
            expanded.get_json(silent=True), lexical_sections[2], browser_word_features
        )

        browser_translation_results = 0
        browser_translation_text = ""
        if require_translation:
            found = next(
                iter(api.S.search("translation_unit", limit=1, silent="deep")),
                None,
            )
            if not found:
                raise BrowserSmokeError("no aligned translation_unit to inspect")
            translation_node = found[0]
            expected_translation = api.F.translation_text.v(translation_node)
            if not isinstance(expected_translation, str) or not expected_translation.strip():
                raise BrowserSmokeError("first translation unit has no source text")
            translation_query = {
                "jobName": "oracc-translation-inspect",
                "query": "translation_unit",
                "batch": "5",
                "queryFeatures": "1",
                # TF's typeDisplay.featuresBare is suppressed unless standard
                # features are enabled or explicitly named by the query.
                "standardFeatures": "1",
                "features": "translation_text",
                "condenseType": "translation_unit",
            }
            results = client.post("/query", data=translation_query)
            if results.status_code != 200:
                raise BrowserSmokeError("browser translation query HTTP error")
            browser_translation_results = validate_browser_query(
                results.get_json(silent=True)
            )
            expanded_translation = client.post("/query/1", data=translation_query)
            if expanded_translation.status_code != 200:
                raise BrowserSmokeError("browser translation expansion HTTP error")
            validate_browser_translation(
                expanded_translation.get_json(silent=True), expected_translation
            )
            browser_translation_text = expected_translation

        response = client.post(
            "/query", data={
                "jobName": "oracc-smoke",
                "query": "word",
                "batch": "5",
                "condenseType": "line",  # TF 13.1 display requires valid rank.
            }
        )
        if response.status_code != 200:
            raise BrowserSmokeError("browser query returned an HTTP error")
        browser_results = validate_browser_query(response.get_json(silent=True))

    return {
        "document_key": document_key,
        "line_ref": line_ref,
        "cuneiform_verified": True,
        "transliteration_verified": True,
        "synthetic_sign_count": len(synthetic),
        "synthetic_signs_visible": False,
        "word_lex_edges": lexical,
        "browser_lexical_section": lexical_sections[2],
        "browser_word_features": browser_word_features,
        "search_has_result": True,
        "browser_query_results": browser_results,
        "browser_translation_results": browser_translation_results,
        "browser_translation_text": browser_translation_text,
        "browser_passage_sections": sections,
        "browser_selected_section": sections[2],
        "browser_passage_formats": browser_passage_formats,
        "browser_routes": routes,
        "browser_help_link": app.context.featureBase.replace("<feature>", "word_lex").format(version=version),
        "help_url_verified": False,  # Requires actual public help publication.
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Extracted standalone corpus root")
    parser.add_argument("--version", default="0.4.0")
    parser.add_argument("--document-key", default="riao/ria1:Q001801")
    parser.add_argument("--line-ref", default="Q001801.1")
    parser.add_argument("--expected-glyph", default="𒂍")
    parser.add_argument("--expected-form", default="E₂")
    parser.add_argument("--require-translation", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = smoke_browser(
        args.root / "tf" / args.version, args.root / "app",
        version=args.version,
        document_key=args.document_key,
        line_ref=args.line_ref,
        expected_glyph=args.expected_glyph,
        expected_form=args.expected_form,
        require_translation=args.require_translation,
    )
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
