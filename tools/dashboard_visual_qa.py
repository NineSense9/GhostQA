"""Capture dashboard screenshots and structural checks.

    python tools/dashboard_visual_qa.py \
      --dashboard-url http://127.0.0.1:8787 \
      --output-dir ./tmp-visual-qa

Does not start servers. Google Fonts 404/failed requests are ignored.
Captures a light/dark theme matrix and checks theme persistence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def _drop_font(route) -> None:
    url = route.request.url
    if "css" in url:
        route.fulfill(status=200, content_type="text/css; charset=utf-8", body="")
    else:
        route.fulfill(status=200, content_type="font/woff2", body=b"")


def _block_fonts(context) -> None:
    context.route("**/*fonts.googleapis.com/**", _drop_font)
    context.route("**/*fonts.gstatic.com/**", _drop_font)

STATIC_SHOTS = [
    ("overview-{theme}-1440x900.png", 1440, 900, "overview"),
    ("overview-{theme}-1366x768.png", 1366, 768, "overview"),
    ("overview-{theme}-1920x1080.png", 1920, 1080, "overview"),
    ("overview-{theme}-1024x768.png", 1024, 768, "overview"),
    ("evidence-{theme}-1440x900.png", 1440, 900, "evidence"),
    ("live-{theme}-idle-1440x900.png", 1440, 900, "live"),
    ("overview-{theme}-390x844.png", 390, 844, "overview"),
    ("live-{theme}-390x844.png", 390, 844, "live"),
    ("evidence-{theme}-390x844.png", 390, 844, "evidence"),
    ("overview-{theme}-430x932.png", 430, 932, "overview"),
    ("overview-{theme}-375x812.png", 375, 812, "overview"),
]


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
    page.screenshot(path=path, full_page=full, timeout=8000, animations="disabled")


def _set_theme(page, theme: str) -> None:
    page.evaluate(
        """(t) => {
          if (window.GhostQA && window.GhostQA.setTheme) window.GhostQA.setTheme(t);
          else {
            document.documentElement.setAttribute('data-theme', t);
            try { localStorage.setItem('ghostqa-theme', t); } catch (e) {}
          }
        }""",
        theme,
    )
    page.wait_for_timeout(200)


def _theme_of(page) -> str:
    return page.evaluate(
        "() => document.documentElement.getAttribute('data-theme') || ''"
    )


def _attach_page_hooks(page, console_errors: list, failed_req: list) -> None:
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

    page.on("console", on_console)
    page.on("pageerror", on_pageerror)
    page.on("requestfailed", on_request_failed)
    page.on("response", on_response)


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

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context()
        # Fonts may hang on some networks; fallbacks are enough for layout QA.
        _block_fonts(context)
        page = context.new_page()
        _attach_page_hooks(page, console_errors, failed_req)

        try:
            page.goto(args.dashboard_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_function(
                "() => document.getElementById('rc-b-states')?.textContent === '6'",
                timeout=10000)
            page.wait_for_timeout(200)
        except Exception as e:
            print(f"FAILED: cannot open {args.dashboard_url}: {e}")
            browser.close()
            return 2

        if not page.locator("#theme-toggle").count():
            errors.append("theme toggle missing")

        for theme in ("light", "dark"):
            _set_theme(page, theme)
            if _theme_of(page) != theme:
                errors.append(f"setTheme({theme}) did not stick")
            for tmpl, w, h, view in STATIC_SHOTS:
                name = tmpl.format(theme=theme)
                page.set_viewport_size({"width": w, "height": h})
                page.evaluate(f"window.GhostQA && window.GhostQA.setView('{view}')")
                page.wait_for_timeout(350)
                ov = _overflow(page)
                path = os.path.join(out, name)
                _shot(page, path)
                overflow = ov["scrollWidth"] > ov["clientWidth"] + args.overflow_tol
                print(f"{theme} {w}x{h} {view} overflow={overflow} -> {path}")
                results.append({"file": name, "theme": theme, "overflow": overflow, **ov})
                if overflow:
                    errors.append(f"horizontal overflow {name} {ov}")

            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("window.GhostQA && window.GhostQA.setView('overview')")
            page.wait_for_timeout(250)
            _shot(page, os.path.join(out, f"overview-{theme}-full-1440.png"), full=True)

            bg = page.evaluate(
                "() => getComputedStyle(document.documentElement).backgroundColor"
            )
            print(f"theme {theme} html background {bg}")
            if theme == "light" and "242, 239, 232" not in bg:
                errors.append(f"light background unexpected: {bg}")
            if theme == "dark" and "28, 29, 31" not in bg:
                errors.append(f"dark background unexpected: {bg}")

        # Persistence + hard reload.
        _set_theme(page, "dark")
        page.reload(wait_until="commit", timeout=20000)
        page.wait_for_timeout(400)
        stored = page.evaluate("() => localStorage.getItem('ghostqa-theme')")
        if stored != "dark" or _theme_of(page) != "dark":
            errors.append(
                f"theme persistence failed after reload theme={_theme_of(page)} stored={stored}"
            )
        _shot(page, os.path.join(out, "overview-dark-reload-1440x900.png"))
        print("hard reload dark persisted", stored, _theme_of(page))

        _set_theme(page, "light")
        page.reload(wait_until="commit", timeout=20000)
        page.wait_for_timeout(400)
        stored = page.evaluate("() => localStorage.getItem('ghostqa-theme')")
        if stored != "light" or _theme_of(page) != "light":
            errors.append(
                f"theme persistence failed after light reload theme={_theme_of(page)} stored={stored}"
            )
        _shot(page, os.path.join(out, "overview-light-reload-1440x900.png"))
        print("hard reload light persisted", stored, _theme_of(page))

        # First visit: no saved key, follow prefers-color-scheme.
        for scheme, expect in (("light", "light"), ("dark", "dark")):
            ctx = browser.new_context(color_scheme=scheme)
            _block_fonts(ctx)
            ctx.add_init_script("try { localStorage.removeItem('ghostqa-theme'); } catch (e) {}")
            pg = ctx.new_page()
            try:
                pg.goto(args.dashboard_url, wait_until="commit", timeout=20000)
                pg.wait_for_timeout(250)
                got = pg.evaluate("() => document.documentElement.getAttribute('data-theme')")
                print(f"prefers-color-scheme {scheme} -> {got}")
                if got != expect:
                    errors.append(f"first-visit theme {scheme} became {got}")
                _shot(pg, os.path.join(out, f"overview-first-visit-{scheme}.png"))
            except Exception as e:
                errors.append(f"first-visit {scheme}: {e}")
            finally:
                ctx.close()

        rm = browser.new_context(reduced_motion="reduce")
        _block_fonts(rm)
        rp = rm.new_page()
        rp.goto(args.dashboard_url, wait_until="domcontentloaded", timeout=30000)
        rp.set_viewport_size({"width": 1440, "height": 900})
        rp.wait_for_timeout(400)
        opacity = rp.evaluate("() => getComputedStyle(document.body).opacity")
        if float(opacity) == 0:
            errors.append("reduced-motion body opacity 0")
        _shot(rp, os.path.join(out, "overview-reduced-motion-1440.png"))
        rm.close()

        if not args.skip_live:
            page.set_viewport_size({"width": 1440, "height": 900})
            page.evaluate("window.GhostQA && window.GhostQA.setView('live')")
            _set_theme(page, "light")
            page.wait_for_timeout(300)
            page.click("#btn-preset")
            page.wait_for_timeout(200)
            url_val = page.input_value("#f-url")
            if "127.0.0.1:3939" not in url_val:
                errors.append("preset URL not applied")
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
                page.wait_for_function(
                    "() => window.__cy && window.__cy.nodes().length > 0",
                    timeout=45000)
                page.wait_for_timeout(600)
                _shot(page, os.path.join(out, "live-light-running-1440x900.png"))
                print("live-light-running captured")

                _set_theme(page, "dark")
                page.wait_for_timeout(400)
                nodes = page.evaluate("() => window.__cy ? window.__cy.nodes().length : 0")
                if nodes < 1:
                    errors.append("graph lost nodes after theme switch")
                _shot(page, os.path.join(out, "live-dark-running-1440x900.png"))
                print("live-dark-running captured, nodes", nodes)

                page.wait_for_function(
                    "() => ['已完成','出错'].includes(document.getElementById('r-status')?.textContent)",
                    timeout=180000)
                page.wait_for_timeout(800)
                _shot(page, os.path.join(out, "live-dark-done-1440x900.png"))
                print("live-dark-done captured", page.inner_text("#r-status"))
                _set_theme(page, "light")
                page.wait_for_timeout(300)
                _shot(page, os.path.join(out, "live-light-done-1440x900.png"))
                print("live-light-done captured")
            except Exception as e:
                errors.append(f"live run: {e}")
                _shot(page, os.path.join(out, "live-run-failed.png"))

        unexpected_console = [
            c for c in console_errors
            if "cdn" not in c.lower()
            and "font" not in c.lower()
            and "err_failed" not in c.lower()
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
