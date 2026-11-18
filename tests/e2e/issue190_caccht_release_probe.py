"""Issue #190: published v1.0.0 RIAO/RINAP compatibility, no source checkout.

Downloads ONLY the released ZIP/sha sidecar; uses installed CACCHT Explorer.
Records TEI translation_unit -> line edges and whether the stock Reader exposes
the attested text. No fabricated transliterations, translations or corpus.
"""
from __future__ import annotations

import json
from pathlib import Path
import resource
import time

from fastapi.testclient import TestClient
from cfabric_browser import __version__ as version, formats
from cfabric_browser.app import create_app
from cfabric_browser.corpora import CorpusService, resolve_corpus
from cfabric_browser.display.sections import section_ref_for
from cfabric_browser.workers import SearchPool

ROOT = Path("/tmp/issue190-release")
REPORT = ROOT / "released-v1-explorer.json"


def get(client: TestClient, route: str, params: dict | None = None) -> dict:
    try:
        response = client.get(route, params=params)
        data = response.json()
        if response.status_code != 200:
            return {"status": response.status_code, "detail": str(data)[:1500]}
        return {"status": 200, "data": data}
    except Exception as exc:
        return {"exception": f"{type(exc).__name__}: {exc}"[:1500]}


def api_summary(response: dict, fields: tuple[str, ...]) -> dict:
    if response.get("status") != 200:
        return response
    data = response["data"]
    return {"status": 200, **{field: data.get(field) for field in fields}}


def main() -> None:
    roots = sorted(
        p.parent for p in (ROOT / "unpacked").rglob("otext.tf")
        if (p.parent / "otype.tf").is_file() and (p.parent / "oslots.tf").is_file()
    )
    assert len(roots) == 1, ("unexpected release TF roots", [str(x) for x in roots])
    path = roots[0]
    spec = resolve_corpus(f"riao={path}")
    service = CorpusService([spec], overrides=ROOT / "no-user-overrides")
    api = service.api(spec.name)
    config = service.config(spec.name)
    words = api.F.otype.s("word")
    documents = api.F.otype.s("document")
    assert words and documents, "released corpus must contain documents and words"
    report = {
        "source": "published v1.0.0 GitHub release SHA256 sidecar verified by CI",
        "explorer_version": version,
        "tf_root": str(path),
        "app_config_found": str(config.source) if config.source else None,
        "words": len(words), "documents": len(documents),
        "slot_type": config.slot_type,
        "section_types": list(config.section_types),
        "format_offered": formats.shown(config),
        "format_requested_default": config.default_format,
        "format_effective_default": formats.default(config),
        "base_types": sorted(config.base_types),
    }
    first_word = int(words[0])
    translation_nodes = (
        api.F.otype.s("translation_unit")
        if "translation_unit" in api.F.otype.all else ()
    )
    report["translation_unit_count"] = len(translation_nodes)
    report["translation_edges_present"] = "translation_line" in api.Eall()
    report["translation_source_witness"] = None
    units_to_check = list(translation_nodes)
    for n in units_to_check:
        text = (
            api.F.translation_text.v(n)
            if "translation_text" in api.Fall() else None
        )
        if not isinstance(text, str) or len(text.strip()) < 10:
            continue
        lines = (
            [int(x) if not isinstance(x, tuple) else int(x[0])
             for x in (api.Es("translation_line").f(n) or ())]
            if "translation_line" in api.Eall() else []
        )
        if not lines:
            continue
        report["translation_source_witness"] = {
            "node": int(n),
            "text": text[:400],
            "line_nodes": lines[:15],
            "line_source_refs": [
                str(api.Fs("line").v(line)) if "line" in api.Fall() else ""
                for line in lines[:15]
            ],
            "id": (
                api.F.translation_id.v(n)
                if "translation_id" in api.Fall() else None
            ),
        }
        break

    # Choose a real line on a text-bearing path, preferably one linked to TEI.
    lines = (
        report["translation_source_witness"]["line_nodes"]
        if report["translation_source_witness"] else []
    )
    if not lines:
        lines = [int(n) for n in api.F.otype.s("line")[:1]]
    assert lines, "no real line to navigate"
    line = lines[0]
    ref = section_ref_for(api, config, line)
    report["tested_ref"] = ref
    pool = SearchPool(
        [(spec.name, str(spec.path))],
        sort_key=lambda c: service.api(c).N.sortKeyTuple,
        workers=1, timeout=30, max_results=500,
    )
    app = create_app(service, pool, manage_pool=False, library=False, ui="reader")
    with TestClient(app) as client:
        health = get(client, "/api/health")
        report["health"] = api_summary(health, ("ok", "version", "ui"))
        card = get(client, "/api/corpora/riao")
        report["card"] = api_summary(
            card, ("slotType", "maxSlot", "sectionTypes", "textFormats", "defaultFormat")
        )
        catalog = get(client, "/api/corpora/riao/sections")
        report["catalog"] = (
            {"status": 200, "count": len(catalog["data"].get("children", [])),
             "first": catalog["data"].get("children", [])[:2]}
            if catalog.get("status") == 200 else catalog
        )
        for name, route, params in (
            ("passage", "/api/corpora/riao/passage", {"ref": ref, "mode": "plain"}),
            ("interlinear", "/api/corpora/riao/interlinear", {"ref": ref, "features": "cf,gw,pos,lang"}),
            ("summary", f"/api/corpora/riao/nodes/{first_word}/summary", None),
        ):
            response = get(client, route, params)
            if response.get("status") != 200:
                report[name] = response
                continue
            payload = response["data"]
            if name == "summary":
                report[name] = {"status": 200, "ref": payload.get("ref"),
                                "summary": payload.get("summary"),
                                "text": payload.get("text", "")[:120]}
            else:
                serial = json.dumps(payload, ensure_ascii=False)
                wanted = (report["translation_source_witness"] or {}).get("text") or ""
                report[name] = {
                    "status": 200,
                    "ref": payload.get("ref"),
                    "text_preview": serial[:1000],
                    # A source-backed test, not a claim that an arbitrary
                    # snippet occurs in the whole rendered surface.
                    "includes_full_selected_translation": bool(wanted) and wanted in serial,
                    "selected_translation_snippet": wanted[:70],
                }
    # Passing the research job must require concrete API interoperability,
    # not silently pass with all probes recording exceptions. Translation
    # visibility is independently recorded as a known negative, not hidden.
    assert report["translation_source_witness"] is not None, (
        "public release must retain its source-linked TEI translation",
        report["translation_unit_count"],
    )
    assert report["catalog"]["status"] == 200, report["catalog"]
    assert report["catalog"]["count"] == len(documents), (
        report["catalog"]["count"], len(documents)
    )
    for name in ("health", "card", "passage", "interlinear", "summary"):
        assert report[name]["status"] == 200, (name, report[name])
    assert report["translation_edges_present"]
    report["peak_rss_kb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["tf_bytes"] = sum(p.stat().st_size for p in path.glob("*.tf"))
    report["cache_bytes"] = sum(p.stat().st_size for p in path.rglob("*.cfm"))
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("EXPLORER RELEASE RESEARCH", REPORT, flush=True)
    print(json.dumps({
        k: report.get(k) for k in (
            "words", "documents", "slot_type", "section_types",
            "format_offered", "format_effective_default",
            "translation_unit_count", "translation_edges_present",
            "tested_ref", "peak_rss_kb", "tf_bytes", "cache_bytes"
        )
    }, ensure_ascii=False), flush=True)
    print("TRANSLATION WITNESS", json.dumps(report["translation_source_witness"],
                                            ensure_ascii=False)[:1200], flush=True)
    print("API STATUS", {k: report.get(k, {}).get("status")
                         for k in ("health", "card", "catalog", "passage", "interlinear", "summary")}, flush=True)
    print("TRANSLATION VISIBLE", {k: report.get(k, {}).get("includes_full_selected_translation")
                                  for k in ("passage", "interlinear")}, flush=True)


if __name__ == "__main__":
    main()
