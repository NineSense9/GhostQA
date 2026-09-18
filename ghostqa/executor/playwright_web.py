"""PlaywrightWebExecutor: drives a real Chromium browser against a web app.

Design rules:
- NO access to app internals. Observation is purely page-presented
  (DOM, a11y-ish attributes, console/network events). `ground_truth()`
  always returns {} on real web - oracle assertions must use obs only.
- Stable element identity via ElementDescriptor resolution order:
  data-testid -> role+text -> visible text -> CSS path.
  If a target cannot be resolved during replay, the step is INVALID
  (we never silently click a different element).
- Compact Page Representation: capped element list + data-obs values
  + input values, a few KB at most; full DOM is never fed to models.
"""
from __future__ import annotations

import hashlib
import io
import os
import time
from typing import Optional

from ..state.models import GUIState, Action, UIElement
from .base import Executor, ExecResult

MAX_ELEMENTS = 80
SETTLE_MS = 450

_EXTRACT_JS = """
() => {
  const vis = (e) => {
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden'
           && s.display !== 'none' && r.bottom > 0 && r.right > 0;
  };
  const cssPath = (e) => {
    const parts = [];
    while (e && e.nodeType === 1 && parts.length < 6) {
      let p = e.tagName.toLowerCase();
      if (e.id) { p += '#' + e.id; parts.unshift(p); break; }
      const i = Array.prototype.indexOf.call(e.parentNode.children, e) + 1;
      parts.unshift(p + ':nth-child(' + i + ')');
      e = e.parentNode;
    }
    return parts.join('>');
  };
  const ROLE = {A: 'link', BUTTON: 'button', INPUT: 'input',
                SELECT: 'select', TEXTAREA: 'input'};
  const out = [];
  const seen = new Set();
  const nodes = document.querySelectorAll(
    'a[href], button, input, select, textarea, [role=button], [data-testid]');
  nodes.forEach((e, idx) => {
    if (!vis(e) || e.disabled) return;
    const tag = e.tagName;
    const role = e.getAttribute('role') || ROLE[tag] || 'button';
    const type = (e.getAttribute('type') || '').toLowerCase();
    const kind = (tag === 'INPUT' && !['button','submit','checkbox','radio'].includes(type))
                 || tag === 'TEXTAREA' || tag === 'SELECT' ? 'input' : 'click';
    let text = (e.innerText || e.value || e.getAttribute('aria-label')
                || e.getAttribute('placeholder') || e.getAttribute('title') || '');
    text = text.trim().slice(0, 64);
    const testid = e.getAttribute('data-testid') || '';
    const key = role + '|' + text + '|' + testid;
    if (seen.has(key)) return;
    seen.add(key);
    out.push({role, text, kind, testid, css: cssPath(e),
              value: kind === 'input' ? (e.value || '') : undefined,
              index: idx});
  });
  const obs = {};
  document.querySelectorAll('[data-obs]').forEach((e) => {
    const k = e.getAttribute('data-obs');
    const v = (e.innerText || '').trim();
    if (obs[k] === undefined) obs[k] = v;
    else if (Array.isArray(obs[k])) obs[k].push(v);
    else obs[k] = [obs[k], v];
  });
  const inputs = {};
  document.querySelectorAll('input, textarea, select').forEach((e) => {
    const id = e.getAttribute('data-testid') || e.id;
    if (id) inputs['input_' + id] = e.value || '';
  });
  return {
    title: document.title,
    elements: out,
    obs,
    inputs,
    body_text_len: (document.body ? document.body.innerText.trim().length : 0),
    dom_size: document.documentElement.outerHTML.length,
  };
}
"""

_MUTATION_JS = """
() => {
  if (window.__gqMutCount === undefined) {
    window.__gqMutCount = 0;
    new MutationObserver((ms) => { window.__gqMutCount += ms.length; })
      .observe(document.body, {childList: true, subtree: true,
                               attributes: true, characterData: true});
  }
  return true;
}
"""


def _ahash64_from_png(data: bytes) -> Optional[int]:
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert("L").resize((8, 8))
        px = list(img.getdata())
        avg = sum(px) / 64.0
        h = 0
        for p in px:
            h = (h << 1) | (1 if p >= avg else 0)
        return h
    except Exception:
        return None


class PlaywrightWebExecutor(Executor):
    def __init__(self, base_url: str, headless: bool = True,
                 screenshots_dir: str = None, slow_mo_ms: int = 0,
                 shared: dict = None):
        """`shared` = {"pw": ..., "browser": ...} reuses an existing browser
        process (sync Playwright allows only one instance per thread)."""
        self.base_url = base_url.rstrip("/")
        self.screenshots_dir = screenshots_dir
        if screenshots_dir:
            os.makedirs(screenshots_dir, exist_ok=True)
        if shared is not None:
            self._pw, self.browser = shared["pw"], shared["browser"]
            self._owns_browser = False
        else:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self.browser = self._pw.chromium.launch(headless=headless,
                                                    slow_mo=slow_mo_ms)
            self._owns_browser = True
        self.context = self.browser.new_context(ignore_https_errors=True)
        self.page = self.context.new_page()
        self._console_errors: list = []
        self._page_errors: list = []
        self._http_errors: list = []
        self._network_count = 0
        self._nav_stack: list = []
        self.page.on("console", self._on_console)
        self.page.on("pageerror", self._on_pageerror)
        self.page.on("response", self._on_response)
        self._goto(self.base_url + "/index.html")
        self.page.evaluate(_MUTATION_JS)

    # ---- event listeners ----
    def _on_console(self, msg):
        if msg.type == "error":
            self._console_errors.append(msg.text[:300])

    def _on_pageerror(self, err):
        self._page_errors.append(str(err).splitlines()[0][:300])

    def _on_response(self, resp):
        self._network_count += 1
        if resp.status >= 500:
            self._http_errors.append(f"{resp.request.method} {resp.url} -> {resp.status}")

    def _drain_errors(self):
        js = self._page_errors + self._console_errors
        http = self._http_errors
        self._page_errors, self._console_errors, self._http_errors = [], [], []
        return js, http

    # ---- helpers ----
    def _goto(self, url: str):
        self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
        self.page.wait_for_timeout(SETTLE_MS)

    def _resolve(self, action: Action):
        """Locate the element for an action. Returns a Locator or None."""
        p = self.page
        eid = action.target_eid or ""
        # 1. data-testid (eid may be the testid itself)
        loc = p.locator(f"[data-testid='{eid}']")
        if loc.count() > 0:
            return loc.first
        # 2. stored descriptor (role/text/css captured at observe time)
        desc = getattr(self, "_descriptors", {}).get(eid)
        if desc:
            if desc.get("testid"):
                loc = p.locator(f"[data-testid='{desc['testid']}']")
                if loc.count() > 0:
                    return loc.first
            if desc.get("text"):
                role = desc.get("role", "button")
                pw_role = {"link": "link", "button": "button"}.get(role)
                if pw_role:
                    loc = p.get_by_role(pw_role, name=desc["text"], exact=False)
                    if loc.count() > 0:
                        return loc.first
                loc = p.get_by_text(desc["text"], exact=False)
                if loc.count() > 0:
                    return loc.first
            if desc.get("css"):
                loc = p.locator(desc["css"])
                if loc.count() > 0:
                    return loc.first
        return None

    # ---- Executor interface ----
    def observe(self) -> GUIState:
        data = self.page.evaluate(_EXTRACT_JS)
        elements = []
        self._descriptors = {}
        for e in data["elements"][:MAX_ELEMENTS]:
            testid = e.get("testid") or ""
            if testid:
                eid = testid
            else:
                eid = hashlib.sha1(
                    f"{e['role']}|{e['text']}|{e['index']}".encode()).hexdigest()[:10]
            elements.append(UIElement(eid=eid, role=e["role"], text=e["text"],
                                      kind=e["kind"], enabled=True))
            self._descriptors[eid] = {"testid": testid, "role": e["role"],
                                      "text": e["text"], "css": e["css"]}
        obs = dict(data["obs"])
        obs.update(data["inputs"])
        shot = None
        if self.screenshots_dir:
            raw = self.page.screenshot(type="png")
            shot = _ahash64_from_png(raw)
        return GUIState(
            app="web:" + self.base_url.split("//", 1)[-1],
            url=self.page.url, title=data["title"],
            elements=tuple(elements), obs=obs,
            screenshot_ahash=shot,
            meta={"body_text_len": data["body_text_len"],
                  "dom_size": data["dom_size"], "page": self.page.url},
        )

    def execute(self, action: Action) -> ExecResult:
        t0 = time.time()
        js_errors, http_errors = self._drain_errors()       # discard stale
        net_before = self._network_count
        mut_before = self.page.evaluate("window.__gqMutCount || 0")
        url_before = self.page.url

        try:
            if action.type == "back":
                if not self._nav_stack:
                    return ExecResult(ok=True, state=self.observe(),
                                      message="back at root (no-op)")
                self._goto(self._nav_stack.pop())
                return self._finish(action, t0, net_before, mut_before, url_before,
                                    navigated=True)
            if action.type == "wait":
                self.page.wait_for_timeout(int(action.text or 500))
                return self._finish(action, t0, net_before, mut_before, url_before)
            if action.type == "scroll":
                self.page.mouse.wheel(0, 600)
                self.page.wait_for_timeout(SETTLE_MS)
                return self._finish(action, t0, net_before, mut_before, url_before)

            loc = self._resolve(action)
            if loc is None:
                return ExecResult(ok=False, state=self.observe(),
                                  message=f"element {action.target_eid} not found")
            if action.type == "click":
                self._nav_stack.append(url_before)
                loc.scroll_into_view_if_needed(timeout=3000)
                loc.click(timeout=5000)
            elif action.type == "input":
                loc.scroll_into_view_if_needed(timeout=3000)
                loc.fill("")
                loc.fill(action.text or "")
            else:
                return ExecResult(ok=False, state=self.observe(),
                                  message=f"unsupported action {action.type}")
            self.page.wait_for_timeout(SETTLE_MS)
            try:
                self.page.wait_for_load_state("networkidle", timeout=1200)
            except Exception:
                pass
            return self._finish(action, t0, net_before, mut_before, url_before)
        except Exception as e:                                # noqa: BLE001
            msg = str(e)
            if "crash" in msg.lower() or "target closed" in msg.lower():
                return ExecResult(ok=True, crashed=True, message=msg[:300])
            return ExecResult(ok=False, state=self.observe(),
                              message=msg[:300])

    def _finish(self, action, t0, net_before, mut_before, url_before,
                navigated=False) -> ExecResult:
        js_errors, http_errors = self._drain_errors()
        mut_after = self.page.evaluate("window.__gqMutCount || 0")
        events = []
        if navigated or self.page.url != url_before:
            events.append("navigated")
        if self._network_count > net_before:
            events.append("network")
        if mut_after > mut_before:
            events.append("mutated")
        state = self.observe()
        if self.screenshots_dir:
            path = os.path.join(self.screenshots_dir,
                                f"shot-{int(t0*1000)}.png")
            self.page.screenshot(path=path)
            state.meta["screenshot"] = path
        state.meta["elapsed_ms"] = int((time.time() - t0) * 1000)
        return ExecResult(ok=True, state=state, js_errors=js_errors,
                          http_errors=http_errors, events=events)

    def reset(self) -> GUIState:
        self._nav_stack = []
        self._drain_errors()
        self._goto(self.base_url + "/index.html")
        self.page.evaluate("() => localStorage.clear()")
        self._goto(self.base_url + "/index.html")
        self.page.evaluate(_MUTATION_JS)
        return self.observe()

    def ground_truth(self) -> dict:
        # Real web: no internal access by design (benchmark judge is separate).
        return {}

    def share_handle(self) -> dict:
        """Handle for creating sibling executors on the same browser process."""
        return {"pw": self._pw, "browser": self.browser}

    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        if getattr(self, "_owns_browser", True):
            try:
                self.browser.close()
                self._pw.stop()
            except Exception:
                pass
