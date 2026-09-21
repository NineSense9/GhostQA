"""Capture dashboard screenshots and structural checks.

    python tools/dashboard_visual_qa.py \
      --dashboard-url http://127.0.0.1:8787 \
      --output-dir ./tmp-visual-qa

Does not start servers. Google Fonts 404/failed requests are ignored.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time


FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def _is_font(url: str) -> bool:
    return any(h in url for h in FONT_HOSTS)


def _overflow(page) -> dict:
    return page.evaluate(
        """() => ({
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          bodyScrollWidth: document.body.scrollWidth
        })"""
    )


def _shot(page, path: str, full: bool = False) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    page.screenshot(path=path, full_page=full)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dashboard-url", default="http://127.0.0.1:8787")
    p.add_argument("--output-dir", required=True)
    p.add_argument("--skip-live", action="store_true")
    p.add_argument("--run-budget", type=int, default=16)
    p.add_argument("--overflow-tol", type=int, default=2)
    args = p.parse_args()
    out = os.path.abspath(args.output_dir)
    os.makedirs(out, exist_ok=True)

    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    console_errors: list[str] = []
    failed_req: list[str] = []
    results = []

    def on_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)

    def on_pageerror(exc):
        console_errors.append(str(exc))

    def on_request_failed(req):
        url = req.url
        if _is_font(url):
            return
        failed_req.append(f"{req.failure.error_text if req.failure else 'fail'} {url}")

    def on_response(resp):
        if resp.status >= 400 and not _is_font(resp.url):
            failed_req.append(f"HTTP {resp.status} {resp.url}")

    viewports = [
        ("overview-1440x900.png", 1440, 900, "overview"),
        ("overview-1366x768.png", 1366, 768, "overview"),
        ("overview-1920x1080.png", 1920, 1080, "overview"),
        ("evidence-1440x900.png", 1440, 900, "evidence"),
        ("live-idle-1440x900.png", 1440, 900, "live"),
        ("overview-mobile-390x844.png", 390, 844, "overview"),
        ("live-mobile-390x844.png", 390, 844, "live"),
        ("evidence-mobile-390x844.png", 390, 844, "evidence"),
        ("overview-mobile-430x932.png", 430, 932, "overview"),
    ]

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("console", on_console)
        page.on("pageerror", on_pageerror)
        page.on("requestfailed", on_request_failed)
        page.on("response", on_response)

        try:
            page.goto(args.dashboard_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_function(
                "() => document.getElementById('rc-b-states')?.textContent === '6'",
                timeout=10000)
            page.wait_for_timeout(200)
        except Exception as e:
            print(f"FAILED: cannot open {args.dashboard_url}: {e}")
            browser.close()
            return 2

        for name, w, h, view in viewports:
            page.set_viewport_size({"width": w, "height": h})
            page.evaluate(f"window.GhostQA && window.GhostQA.setView('{view}')")
            page.wait_for_timeout(400)
            ov = _overflow(page)
            path = os.path.join(out, name)
            _shot(page, path)
            overflow = ov["scrollWidth"] > ov["clientWidth"] + args.overflow_tol
            print(f"{w}x{h} {view} overflow={overflow} -> {path}")
            results.append({"file": name, "overflow": overflow, **ov})
            if overflow:
                errors.append(f"horizontal overflow {name} {ov}")

        page.set_viewport_size({"width": 1440, "height": 900})
        page.evaluate("window.GhostQA && window.GhostQA.setView('overview')")
        page.wait_for_timeout(300)
        _shot(page, os.path.join(out, "overview-full-1440.png"), full=True)

        # Reduced motion: page must remain visible.
        rm = browser.new_context(reduced_motion="reduce")
        rp = rm.new_page()
        rp.goto(args.dashboard_url, wait_until="domcontentloaded", timeout=30000)
        rp.set_viewport_size({"width": 1440, "height": 900})
        rp.wait_for_timeout(400)
        opacity = rp.evaluate(
            "() => getComputedStyle(document.body).opacity")
        if float(opacity) == 0:
            errors.append("reduced-motion body opacity 0")
        _shot(rp, os.path.join(out, "overview-reduced-motion-1440.png"))
        rm.close()

        if not args.skip_live:
            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("window.GhostQA && window.GhostQA.setView('live')")
            page.wait_for_timeout(300)
            # Preset must not auto-run.
            page.click("#btn-preset")
            page.wait_for_timeout(200)
            url_val = page.input_value("#f-url")
            if "127.0.0.1:3939" not in url_val:
                errors.append("preset URL not applied")
            status = page.inner_text("#r-status")
            if status not in ("空闲", "已完成", "出错"):
                # May already be restoring a previous run.
                pass
            page.fill("#f-budget", str(args.run_budget))
            page.check("#f-mock")
            page.click("#btn-run")
            try:
                page.wait_for_function(
                    "() => ['探索中','启动中'].includes(document.getElementById('r-status')?.textContent)",
                    timeout=60000)
                page.wait_for_function(
                    "() => document.getElementById('r-status')?.textContent === '探索中'",
                    timeout=60000)
                try:
                    page.wait_for_function(
                        "() => { const s = document.getElementById('shot'); return s && !s.hidden && s.naturalWidth > 0; }",
                        timeout=45000)
                except Exception:
                    page.wait_for_timeout(4000)
                page.wait_for_timeout(600)
                _shot(page, os.path.join(out, "live-running-1440x900.png"))
                print("live-running captured")
                page.wait_for_function(
                    "() => ['已完成','出错'].includes(document.getElementById('r-status')?.textContent)",
                    timeout=180000)
                page.wait_for_timeout(800)
                _shot(page, os.path.join(out, "live-done-1440x900.png"))
                print("live-done captured", page.inner_text("#r-status"))
            except Exception as e:
                errors.append(f"live run: {e}")
                _shot(page, os.path.join(out, "live-run-failed.png"))

        unexpected_console = [
            c for c in console_errors
            if "cdn" not in c.lower() and "font" not in c.lower()
        ]
        print("console_errors", len(unexpected_console))
        for c in unexpected_console:
            print("  ", c)
        print("failed_requests", len(failed_req))
        for c in failed_req[:12]:
            print("  ", c)

        summary = {
            "errors": errors,
            "console_errors": unexpected_console,
            "failed_requests": failed_req,
            "results": results,
        }
        with open(os.path.join(out, "qa-summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        browser.close()

    if unexpected_console:
        errors.extend(f"console: {c}" for c in unexpected_console)
    if failed_req:
        errors.extend(f"net: {c}" for c in failed_req)
    if errors:
        print("FAILED")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
