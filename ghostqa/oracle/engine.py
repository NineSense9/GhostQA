"""Three-layer Oracle engine.

L1 hard anomalies (program, 100% automatic): crash / js_error / http_error / blank
L2 structural anomalies (rules): dead_action / nav_loop
L3 semantic anomalies (spec-driven assertions): semantic
"""
from __future__ import annotations

from typing import Optional

from ..state.models import GUIState, Action, Finding
from ..state.signature import state_signature
from .spec import eval_pred, when_matches, DEFAULT_REGISTRY


class OracleEngine:
    def __init__(self, spec: Optional[list] = None, registry=None):
        self.spec = spec or []
        self.registry = registry or DEFAULT_REGISTRY

    def inspect(self, prev: Optional[GUIState], action: Action, result,
                new_state: Optional[GUIState], ctx: dict) -> list:
        """ctx keys: step_index, history_sigs (list[str]), ground_truth (dict)."""
        findings = []
        step = ctx.get("step_index", 0)

        # ---- L1 ----
        if getattr(result, "crashed", False):
            findings.append(Finding(
                kind="crash", severity="high",
                description=f"应用崩溃：执行 {action.brief()} 后崩溃。{getattr(result, 'message', '')}",
                step_index=step,
                evidence={"action": action.brief(),
                          "page": prev.meta.get("page") if prev else None,
                          "page_url": prev.url if prev else None,
                          "url": prev.url if prev else None}))
            return findings  # crashed: nothing more to inspect

        for err in getattr(result, "js_errors", []):
            findings.append(Finding(
                kind="js_error", severity="medium",
                description=f"JS 错误：{err}（触发：{action.brief()}）",
                step_index=step,
                evidence={"action": action.brief(), "error": err,
                          "url": new_state.url if new_state else None}))

        for err in getattr(result, "http_errors", []):
            findings.append(Finding(
                kind="http_error", severity="high",
                description=f"HTTP 错误：{err}",
                step_index=step,
                evidence={"action": action.brief(), "error": err}))

        if new_state is not None and len(new_state.elements) == 0:
            findings.append(Finding(
                kind="blank", severity="high",
                description=f"白屏/无可交互元素：{new_state.url}",
                step_index=step,
                evidence={"url": new_state.url}))

        if prev is None or new_state is None:
            return findings

        # ---- L2: dead action ----
        if action.type == "click" and not getattr(result, "events", None):
            same_sig = state_signature(prev) == state_signature(new_state)
            same_obs = prev.obs == new_state.obs
            if same_sig and same_obs:
                findings.append(Finding(
                    kind="dead_action", severity="medium",
                    description=f"点击无响应：元素 {action.target_eid} 点击后界面无任何变化",
                    step_index=step,
                    evidence={"eid": action.target_eid, "url": prev.url,
                              "page": prev.meta.get("page")}))

        # ---- L2: navigation loop (A,B,A,B pattern) ----
        hist = ctx.get("history_sigs", [])
        if len(hist) >= 4:
            a, b, c, d = hist[-4:]
            if a == c and b == d and a != b:
                cycle_urls = sorted({ctx.get("sig_url_map", {}).get(a, ""),
                                     ctx.get("sig_url_map", {}).get(b, "")})
                findings.append(Finding(
                    kind="nav_loop", severity="medium",
                    description="检测到导航死循环（A→B→A→B），可能无法退出当前页面组",
                    step_index=step,
                    evidence={"cycle": [a, b], "cycle_urls": cycle_urls,
                              "url": new_state.url}))

        # ---- L3: semantic assertions ----
        gt = ctx.get("ground_truth", {})
        for assertion in self.spec:
            if not when_matches(assertion.get("when"), new_state.url, action.key()):
                continue
            try:
                ok = eval_pred(assertion["assert"], new_state.obs, gt, self.registry)
            except Exception:
                continue
            if ok is False:                     # None = not applicable on this page
                findings.append(Finding(
                    kind="semantic",
                    severity=assertion.get("severity", "medium"),
                    description=f"语义异常[{assertion['id']}]：{assertion.get('desc', assertion['id'])}",
                    step_index=step,
                    evidence={"assert_id": assertion["id"],
                              "url": new_state.url,
                              "obs": new_state.obs,
                              "action": action.brief()}))
        return findings
