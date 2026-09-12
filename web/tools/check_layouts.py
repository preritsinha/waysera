#!/usr/bin/env python3
"""
Check the Waysera pages for horizontal overflow at real device widths.

The brand lockup, journey code and group rows are the things most likely to
push a phone layout sideways, and horizontal scroll is the kind of defect that
is obvious on a device and invisible in a desktop browser.

    backend/.venv/bin/python tools/check_layouts.py
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import os
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websockets

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Defaults to the web client. Set WAYSERA_WEB_ROOT to point the same checks at
# android_app/www, which no harness would otherwise ever load.
WEB_ROOT = Path(os.environ["WAYSERA_WEB_ROOT"]).resolve() if os.environ.get("WAYSERA_WEB_ROOT") else PROJECT_ROOT / "frontend"
PORT = 8770
DEBUG_PORT = 9335
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

WIDTHS = [320, 375, 390, 430, 768, 1024]
PAGES = ["index.html", "replay.html"]
SCHEMES = ["light", "dark"]


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


async def measure(socket, page_url, width, scheme):
    counter = {"id": 0}

    async def call(method, params=None):
        counter["id"] += 1
        message_id = counter["id"]
        await socket.send(
            json.dumps({"id": message_id, "method": method, "params": params or {}})
        )
        while True:
            event = json.loads(await asyncio.wait_for(socket.recv(), timeout=30))
            if event.get("id") == message_id:
                return event.get("result", {})

    await call(
        "Emulation.setDeviceMetricsOverride",
        {"width": width, "height": 800, "deviceScaleFactor": 2, "mobile": width < 768},
    )
    await call(
        "Emulation.setEmulatedMedia",
        {"features": [{"name": "prefers-color-scheme", "value": scheme}]},
    )
    await call("Page.navigate", {"url": page_url})

    # Settle, then measure.
    for _ in range(60):
        result = await call(
            "Runtime.evaluate",
            {"expression": "document.readyState === 'complete'", "returnByValue": True},
        )
        if result.get("result", {}).get("value"):
            break
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.4)

    result = await call(
        "Runtime.evaluate",
        {
            "expression": """
                JSON.stringify({
                    scrollWidth: document.documentElement.scrollWidth,
                    clientWidth: document.documentElement.clientWidth,
                    widest: (() => {
                        let worst = null;
                        for (const el of document.querySelectorAll('body *')) {
                            const r = el.getBoundingClientRect();
                            if (r.width === 0) continue;
                            const overhang = r.right - document.documentElement.clientWidth;
                            if (overhang > 1 && (!worst || overhang > worst.overhang)) {
                                worst = {
                                    overhang: Math.round(overhang),
                                    tag: el.tagName.toLowerCase(),
                                    cls: el.className && el.className.toString().slice(0, 40)
                                };
                            }
                        }
                        return worst;
                    })()
                })
            """,
            "returnByValue": True,
        },
    )
    # call() already unwraps the outer envelope, so this is one level, not two.
    return json.loads(result["result"]["value"])


async def run():
    failures = []

    for _ in range(100):
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=1
            ) as response:
                targets = json.load(response)
            page = next(
                (t for t in targets if t.get("type") == "page" and t.get("webSocketDebuggerUrl")),
                None,
            )
            if page:
                break
        except Exception:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("Chrome DevTools endpoint never became available")

    async with websockets.connect(page["webSocketDebuggerUrl"], max_size=20 * 1024 * 1024) as socket:
        for name in PAGES:
            for scheme in SCHEMES:
                for width in WIDTHS:
                    url = f"http://localhost:{PORT}/{name}"
                    metrics = await measure(socket, url, width, scheme)
                    # 1px of slack absorbs subpixel rounding.
                    if metrics["scrollWidth"] > metrics["clientWidth"] + 1:
                        widest = metrics.get("widest")
                        detail = (
                            f". Widest offender: <{widest['tag']} class=\"{widest['cls']}\"> "
                            f"overhangs by {widest['overhang']}px"
                            if widest
                            else ""
                        )
                        failures.append(
                            f"{name} @ {width}px {scheme}: scrolls horizontally "
                            f"({metrics['scrollWidth']} > {metrics['clientWidth']}){detail}"
                        )
    return failures


def main() -> int:
    server = ThreadingHTTPServer(
        ("127.0.0.1", PORT), partial(Handler, directory=str(WEB_ROOT))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()

    profile = tempfile.mkdtemp(prefix="waysera-layout-")
    chrome = subprocess.Popen(
        [
            CHROME, "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-default-browser-check",
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        failures = asyncio.run(run())
    finally:
        chrome.terminate()
        try:
            chrome.wait(timeout=10)
        except subprocess.TimeoutExpired:
            chrome.kill()
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)

    if failures:
        for failure in failures:
            print(f"FAIL  {failure}")
        print(f"\n{len(failures)} layout problem(s)")
        return 1

    checked = len(PAGES) * len(SCHEMES) * len(WIDTHS)
    print(f"no horizontal overflow across {checked} page/width/scheme combinations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
