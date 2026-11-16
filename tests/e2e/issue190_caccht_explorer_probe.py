"""Research #190: installed CACCHT Explorer 0.1.2 against real ORACC-TF slices.

This is a compatibility measurement, not a claim that stock Explorer provides
a complete reader. Both sources are pinned, and no synthetic TF corpus is used.
The two modes measure stock config and a reversible, display-only word-base
override. All API exceptions are recorded, not silently treated as passes.
"""
from __future__ import annotations

import hashlib
import json
import resource
from pathlib import Path
import time

from fastapi.testclient import TestClient
import yaml

from cfabric_browser import __version__ as explorer_version, formats
from cfabric_browser.app import create_app
from cfabric_browser.corpora import CorpusService, resolve_corpus
from cfabric_browser.workers import SearchPool

ROOT = Path("/tmp/issue190-explorer")
REPORT = ROOT / "compatibility.json"
SOURCES = {
    "etcsri": ("Q000935", "a2eef2a0337d276191fbda85a4269948fb00f9c3", 7),
    "ninmed": ("P285136", "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b", 204),
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def verify_source(kind: str) -> None:
    (name, sha, _) = SOURCES[kind]
    path = ROOT / "sources" / kind / "corpusjson" / f"{name}.json"
    raw = path.read_bytes()
    assert git_blob(raw) == sha, (kind, git_blob(raw))
    assert json.loads(raw)["textid"] == name


def get(client: TestClient, path: str, params: dict | None = None) -> dict:
    try:
        response = client.get(path, params=params)
        payload = response.json()
        return {
            "status": response.status_code,
            "data": payload if response.status_code == 200 else str(payload)[:1000],
        }
    except Exception as exc:
        return {"exception": f"{type(exc).__name__}: {exc}"[:1200]}


def drill_down(client: TestClient, kind: str, result: dict) -> str | None:
    url = f"/api/corpora/{kind}/sections"
    top = get(client, url)
    result["sections"] = {"root": top.get("status"), "hops": []}
    for _ in range(5):
        children = top.get("data", {}).get("children", [])
        if not children:
            break
        item = children[0]
        ref = item["ref"]
        result["sections"]["hops"].append(
            {"type": item.get("type"), "ref": ref, "label": item.get("label")}
        )
        top = get(client, url, {"ref": ref})
        if top.get("status") != 200:
            result["sections"]["error"] = top
            break
    return (result["sections"]["hops"][-1]["ref"]
            if result["sections"]["hops"] else None)


def probe(kind: str, mode: str) -> dict:
    path = ROOT / kind / "tf" / "0.1.0"
    spec = resolve_corpus(f"{kind}={path}")
    service = CorpusService([spec], overrides=ROOT / "no-user-overrides")
    api = service.api(kind)
    config = service.config(kind)
    word_nodes = api.F.otype.s("word")
    first = int(word_nodes[0])
    (_, _, expected) = SOURCES[kind]
    assert len(word_nodes) == expected, (kind, len(word_nodes), expected)
    result = {
        "mode": mode,
        "kind": kind,
        "words": len(word_nodes),
        "slot_type": config.slot_type,
        "section_types": list(config.section_types),
        "format_all": list(config.text_formats),
        "format_offered": formats.shown(config),
        "format_effective_default": formats.default(config),
        "format_requested_default": config.default_format,
        "base_types": sorted(config.base_types),
        "first_word_id": first,
        "source_features": {
            name: api.Fs(name).v(first)
            for name in ("form", "cf", "gw", "pos", "lang", "base", "morph", "morph2")
            if name in api.Fall()
        },
    }
    pool = SearchPool(
        [(spec.name, str(spec.path))],
        sort_key=lambda c: service.api(c).N.sortKeyTuple,
        workers=1, timeout=25, max_results=2000,
    )
    pool.start(wait=True)
    try:
        app = create_app(service, pool, manage_pool=False, library=False, ui="reader")
        with TestClient(app) as client:
            result["health"] = get(client, "/api/health")
            card = get(client, f"/api/corpora/{kind}")
            if card.get("status") == 200:
                c = card["data"]
                result["card"] = {
                    name: c.get(name) for name in
                    ("slotType", "maxSlot", "sectionTypes", "textFormats",
                     "defaultFormat", "baseTypes", "title")
                }
            else:
                result["card"] = card
            ref = drill_down(client, kind, result)
            if ref:
                for name, path_suffix, params in (
                    ("passage", "passage", {"ref": ref, "mode": "plain"}),
                    ("interlinear", "interlinear", {"ref": ref, "features": "cf,gw,pos,lang,morph,morph2"}),
                ):
                    response = get(client, f"/api/corpora/{kind}/{path_suffix}", params)
                    if response.get("status") == 200:
                        data = response["data"]
                        result[name] = {
                            "status": 200,
                            "ref": data.get("ref"),
                            "count": data.get("total", len(data.get("verses", []))),
                            "tree_excerpt": str(data.get("trees", []))[:1200]
                            if name == "passage" else None,
                            "first_verse": str(data.get("verses", [])[:1])[:1300]
                            if name == "interlinear" else None,
                        }
                    else:
                        result[name] = response
            summary = get(client, f"/api/corpora/{kind}/nodes/{first}/summary")
            if summary.get("status") == 200:
                val = summary["data"]
                result["word_summary"] = {
                    name: val.get(name) for name in ("ref", "text", "summary", "type")
                }
            else:
                result["word_summary"] = summary
            info = get(client, f"/api/corpora/{kind}/nodes/{first}/info")
            if info.get("status") == 200:
                v = info["data"]
                result["word_info"] = {
                    "feature_subset": {k: v.get("features", {}).get(k) for k in
                        ("form", "cf", "gw", "pos", "lang", "base", "morph", "morph2")},
                    "edge_names": sorted(v.get("edges", {})),
                }
            else:
                result["word_info"] = info
            if mode == "baseline":
                try:
                    started = client.post(
                        f"/api/corpora/{kind}/search",
                        json={"template": "word"},
                    )
                    status = {"start_status": started.status_code}
                    if started.status_code == 202:
                        job_id = started.json()["id"]
                        deadline = time.monotonic() + 35
                        while time.monotonic() < deadline:
                            value = client.get(f"/api/searches/{job_id}").json()
                            if value["state"] in ("done", "failed", "timeout", "cancelled"):
                                status.update({k: value.get(k) for k in ("state", "count", "problems")})
                                break
                            time.sleep(0.1)
                    else:
                        status["response"] = started.text[:500]
                    result["tfql_search"] = status
                except Exception as exc:
                    result["tfql_search"] = {"exception": repr(exc)[:800]}
    finally:
        pool.shutdown()
    return result


def main() -> None:
    import cfabric
    ROOT.mkdir(parents=True, exist_ok=True)
    out = {
        "explorer_version": explorer_version,
        "cfabric_file": str(Path(cfabric.__file__)),
        "real_source_git_blobs": {kind: tup[1] for kind, tup in SOURCES.items()},
        "results": [],
    }
    try:
        for kind in SOURCES:
            verify_source(kind)
            conf_path = ROOT / kind / "app" / "config.yaml"
            original = conf_path.read_bytes()
            try:
                out["results"].append(probe(kind, "baseline"))
                settings = yaml.safe_load(original)
                settings["typeDisplay"]["word"]["base"] = True
                conf_path.write_text(yaml.safe_dump(settings, allow_unicode=True), encoding="utf-8")
                out["results"].append(probe(kind, "word-base-override"))
            finally:
                conf_path.write_bytes(original)
        # Assertions only for the proved baseline interoperability paths.
        # Broken/empty word summaries and format whitelisting remain research
        # observations, never passing criteria for a user-facing reader.
        assert len(out["results"]) == 4
        for case in out["results"]:
            assert case["health"]["status"] == 200, case
            assert case["sections"]["root"] == 200, case
            assert case["sections"]["hops"], case
            for name in ("passage", "interlinear", "word_summary", "word_info"):
                assert case[name]["status"] == 200, (name, case[name])
            original_cf = case["source_features"].get("cf")
            shown_cf = case["word_info"]["feature_subset"].get("cf")
            assert shown_cf == original_cf, (case["kind"], shown_cf, original_cf)
            assert case["format_requested_default"] == "text-trans-full"
            if case["mode"] == "baseline":
                assert case["tfql_search"]["state"] == "done", case["tfql_search"]
                assert case["tfql_search"]["count"] == SOURCES[case["kind"]][2]
        assert all(x["mode"] in {"baseline", "word-base-override"} for x in out["results"])
    finally:
        out["rss_kb_highwater"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        out["tf_bytes"] = sum(p.stat().st_size for p in ROOT.rglob("*.tf"))
        out["cached_cfm_bytes"] = sum(p.stat().st_size for p in ROOT.rglob("*.cfm"))
        REPORT.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("EXPLORER RESEARCH REPORT", REPORT)
        for case in out["results"]:
            print(json.dumps({
                "kind": case["kind"], "mode": case["mode"],
                "words": case["words"],
                "base_types": case["base_types"],
                "formats": case["format_offered"],
                "default": case["format_effective_default"],
                "summary": case.get("word_summary", {}).get("summary"),
                "passage": case.get("passage", {}).get("status"),
                "interlinear": case.get("interlinear", {}).get("status"),
                "search": case.get("tfql_search"),
            }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
