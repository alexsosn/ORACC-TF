"""#183: real Chromium click-through for installed native Text-Fabric previews.

Runs only in the dedicated GitHub Actions job with pinned primary ORACC JSON.
No synthetic TF fixture, ad-hoc Flask app, or source-checkout imports.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright
from tf.browser.command import argApp, getPort


CASES = (
    ("etcsri", "Q000935", "a2eef2a0337d276191fbda85a4269948fb00f9c3", 7),
    ("ninmed", "P285136", "a26ee7550a1f6d62187ef84b7d84ab1bfd877b2b", 204),
)
HOME = Path("/tmp/issue183-native-user")
ARTIFACTS = Path("/tmp/issue183-artifacts")


def verify_primary_source(kind: str, text_id: str, expected_sha: str) -> None:
    path = Path(f"/tmp/issue183-native-source/{kind}/corpusjson/{text_id}.json")
    raw = path.read_bytes()
    blob_sha = hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()
    assert blob_sha == expected_sha, (kind, blob_sha)
    assert json.loads(raw)["textid"] == text_id


def wait_for_server(url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"TF browser exited before readiness: {process.returncode}")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, OSError, TimeoutError):
            pass
        time.sleep(1)
    raise AssertionError(f"TF browser did not become HTTP-ready: {url}")


def collect_process_info(kind: str, process: subprocess.Popen[str], root: Path) -> None:
    status = Path(f"/proc/{process.pid}/status")
    high_water = "unavailable"
    if status.is_file():
        match = re.search(r"^VmHWM:\s*(.+)$", status.read_text(), flags=re.MULTILINE)
        if match:
            high_water = match.group(1)
    disk_bytes = sum(f.stat().st_size for f in root.glob("*.tf"))
    record = {"kind": kind, "server_pid": process.pid, "server_peak_rss": high_water,
              "tf_disk_bytes": disk_bytes}
    (ARTIFACTS / f"{kind}-measurements.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf8"
    )
    print(f"CHROMIUM MEASUREMENT {record}", flush=True)


def visit_kind(browser, kind: str, count: int) -> None:
    root, app = HOME / f"{kind}-tf", HOME / f"{kind}-app"
    args = [f"app:{app}", f"--locations={root}", "--modules=", "-noweb"]
    port = getPort(argApp(args, True))
    url = f"http://127.0.0.1:{port}"
    log_path = ARTIFACTS / f"{kind}-server.log"
    errors: list[str] = []
    page = None
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    with log_path.open("w", encoding="utf8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "tf.browser.start", *args],
            cwd=HOME, env=env, stdout=log, stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_server(url, process)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            try:
                page = context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                page.locator("textarea#query").wait_for(state="visible", timeout=60000)
                page.locator("button#queryGo").wait_for(state="visible")
                page.screenshot(path=str(ARTIFACTS / f"{kind}-landing.png"))
                page.locator("textarea#query").fill("word")
                # The browser's *own JS* must serialize the real form and
                # produce visible DOM output. A test-client POST is insufficient.
                with page.expect_response(
                    lambda r: r.request.method == "POST"
                    and r.url.split("?")[0].rstrip("/").endswith("/query"),
                    timeout=60000,
                ) as ajax:
                    page.locator("button#queryGo").click()
                result = ajax.value
                assert result.status == 200, (kind, result.status)
                payload = result.json()
                assert payload["status"] is True, (kind, payload.get("messages"))
                assert payload["nResults"] == count, (kind, payload["nResults"])
                page.wait_for_function(
                    """expected => {
                      const table = document.querySelector('#queryTable');
                      if (!table || !table.getClientRects().length
                          || !table.innerText.trim()) return false;
                      return [...document.querySelectorAll('.nresults')].some(el =>
                        el.getClientRects().length &&
                        new RegExp('\\\\b' + expected + '\\\\b').test(el.textContent));
                    }""",
                    arg=count, timeout=60000,
                )
                table_text = page.locator("#queryTable").inner_text()
                assert len(table_text.strip()) > 8, (kind, table_text[:200])
                # #185 (test first): an actual researcher must be able to
                # expand a real result and inspect source-grounded morphology.
                # The native TF browser lazily fetches /query/<sequence> only
                # after a <details> disclosure is clicked in the real page.
                if kind == "etcsri":
                    first = page.locator("#queryTable details.pretty[seq='1']")
                    first.locator("summary").wait_for(state="visible")
                    with page.expect_response(
                        lambda r: r.request.method == "POST"
                        and r.url.split("?")[0].rstrip("/").endswith("/query/1"),
                        timeout=60000,
                    ) as detail_ajax:
                        first.locator("summary").click()
                    assert detail_ajax.value.status == 200, (kind, detail_ajax.value.status)
                    expanded = first.locator(":scope > div.pretty")
                    expanded.wait_for(state="visible", timeout=60000)
                    page.wait_for_function(
                        """() => document.querySelector(
                          '#queryTable details.pretty[seq="1"] > div.pretty'
                        )?.textContent.includes('N1=Urnammak')""",
                        timeout=60000,
                    )
                    assert "N1=Urnammak" in expanded.inner_text(), (
                        kind, expanded.inner_text()[:1000]
                    )
                    page.screenshot(path=str(ARTIFACTS / "etcsri-expanded-morphology.png"))
                    print("CHROMIUM MORPH PASS etcsri: Q000935.1.1 N1=Urnammak", flush=True)
                assert not errors, (kind, errors)
                page.screenshot(path=str(ARTIFACTS / f"{kind}-search.png"))
                collect_process_info(kind, process, root)
                print(f"CHROMIUM CLICK PASS {kind}: {count} visible word results", flush=True)
            finally:
                if page is not None:
                    page.screenshot(path=str(ARTIFACTS / f"{kind}-final.png"))
                context.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    server_text = log_path.read_text(encoding="utf8")
    assert "Traceback (most recent call last)" not in server_text, (
        kind, server_text[-2500:]
    )


def main() -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for kind, text_id, expected_sha, _ in CASES:
        verify_primary_source(kind, text_id, expected_sha)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for kind, _text_id, _sha, count in CASES:
                visit_kind(browser, kind, count)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
