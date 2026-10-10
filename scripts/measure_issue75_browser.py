#!/usr/bin/env python3
"""Bounded real TF browser + source-semantic smoke without the ORACC-TF builder.

The distribution itself supplies tf/ and app/. Run this script from any
directory with Text-Fabric 13.1 available; it never imports oracc_tf.
"""

from __future__ import annotations

import argparse
from html import unescape
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


def validate_browser_passage(payload: object, expected_text: str) -> bool:
    """Require selected text inside TF's rendered passage table, not navigation."""
    if not isinstance(payload, dict):
        raise BrowserSmokeError("browser passage response malformed")
    table = payload.get("table")
    if not isinstance(table, str) or not table or expected_text not in unescape(table):
        raise BrowserSmokeError(
            "browser passage does not render source-selected text"
        )
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
            validate_browser_passage(selected.get_json(silent=True), expected)
            browser_passage_formats[text_format] = expected

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
        "search_has_result": True,
        "browser_query_results": browser_results,
        "browser_passage_sections": sections,
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = smoke_browser(
        args.root / "tf" / args.version, args.root / "app",
        version=args.version,
        document_key=args.document_key,
        line_ref=args.line_ref,
        expected_glyph=args.expected_glyph,
        expected_form=args.expected_form,
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
