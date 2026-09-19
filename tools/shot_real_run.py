"""Capture the dashboard while a real-LLM run is in flight, then after."""
import sys
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else "real"
URL = "http://127.0.0.1:8787"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_page(viewport={"width": 1680, "height": 1050})
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)

    p.goto(URL, wait_until="networkidle")
    p.wait_for_timeout(1200)

    # Real LLM: leave the mock checkbox off.
    p.fill("#f-budget", "40")
    p.click("#btn-run")

    # Grab a mid-flight frame — this is the "watching it work" moment.
    caught = False
    for _ in range(40):
        p.wait_for_timeout(1000)
        if int(p.inner_text("#r-steps") or 0) >= 8:
            p.screenshot(path=f"{TAG}-live.png")
            caught = True
            break
    print("mid-flight captured:", caught, "steps:", p.inner_text("#r-steps"))

    for _ in range(90):
        if p.inner_text("#r-status") in ("已完成", "出错"):
            break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(2500)
    p.screenshot(path=f"{TAG}-final.png")

    # Expand every bug card for the evidence shot.
    for h in p.query_selector_all(".bug-head"):
        h.click()
        p.wait_for_timeout(150)
    p.wait_for_timeout(600)
    p.screenshot(path=f"{TAG}-bugs.png")

    print("status:", p.inner_text("#r-status"))
    print("steps/nodes/bugs:", p.inner_text("#r-steps"), "/",
          p.inner_text("#r-states"), "/", p.inner_text("#r-bugs"))
    print("llm calls:", p.inner_text("#r-llm"))
    print("errors:", errs[:5])
    b.close()
