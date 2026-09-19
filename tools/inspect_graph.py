"""Inspect the live cytoscape graph state in a real browser."""
import sys, json
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    p = b.new_page(viewport={"width": 1600, "height": 1000})
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto("http://127.0.0.1:8787", wait_until="networkidle")
    p.wait_for_timeout(1200)

    # Kick off a short mock run and let the graph populate.
    p.fill("#f-budget", "18")
    p.check("#f-mock")
    p.click("#btn-run")
    for _ in range(40):
        if p.inner_text("#r-status") in ("已完成", "出错"):
            break
        p.wait_for_timeout(1000)
    p.wait_for_timeout(3000)

    info = p.evaluate("""() => {
      const cy = window.__cy;
      if (!cy) return {error: 'cy not exposed'};
      return {
        nodes: cy.nodes().length,
        zoom: cy.zoom(),
        extent: cy.extent(),
        labels: cy.nodes().map(n => ({
          id: n.id().slice(0, 18),
          label: n.data('label'),
          w: n.width(), h: n.height(),
          x: Math.round(n.position('x')), y: Math.round(n.position('y')),
          labelW: n.numericStyle ? undefined : undefined,
        })),
      };
    }""")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:2500])
    print("pageerrors:", errs[:5])
    b.close()
