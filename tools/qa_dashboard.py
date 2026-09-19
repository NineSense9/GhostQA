"""Render the dashboard and capture screenshots for visual QA."""
import sys
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "qa"
URL = "http://127.0.0.1:8787"

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000},
                            device_scale_factor=1)
    errors = []
    page.on("console", lambda m: errors.append(f"{m.type}: {m.text}")
            if m.type in ("error",) else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    page.goto(URL, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.screenshot(path=f"{OUT}-idle.png", full_page=False)

    # Start a run through the real UI form.
    page.fill("#f-budget", "26")
    page.check("#f-mock")
    page.click("#btn-run")
    page.wait_for_timeout(9000)
    page.screenshot(path=f"{OUT}-running.png", full_page=False)

    # Wait for completion, then capture the finished state.
    for _ in range(60):
        txt = page.inner_text("#r-status")
        if txt in ("已完成", "出错"):
            break
        page.wait_for_timeout(1000)
    page.wait_for_timeout(2500)
    page.screenshot(path=f"{OUT}-done.png", full_page=False)

    # Expand the first bug card if present.
    heads = page.query_selector_all(".bug-head")
    if heads:
        heads[0].click()
        page.wait_for_timeout(700)
        page.screenshot(path=f"{OUT}-bug.png", full_page=False)

    # Scroll the right rail so benchmark evidence is captured too.
    page.eval_on_selector(".col-right", "el => el.scrollTop = el.scrollHeight")
    page.wait_for_timeout(800)
    page.screenshot(path=f"{OUT}-rail.png", full_page=False)
    page.eval_on_selector(".col-right", "el => el.scrollTop = 0")

    # Mobile check.
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_timeout(900)
    page.screenshot(path=f"{OUT}-mobile.png", full_page=True)

    print("status:", page.inner_text("#r-status"))
    print("steps:", page.inner_text("#r-steps"))
    print("nodes:", page.inner_text("#r-states"))
    print("bugs:", page.inner_text("#r-bugs"))
    print("log rows:", len(page.query_selector_all(".log-row")))
    print("bug cards:", len(page.query_selector_all(".bug")))
    print("console errors:", len(errors))
    for e in errors[:10]:
        print("  ", e[:180])
    browser.close()
