"""Simulated web-app executor.

Deterministic, zero-dependency executor for unit tests and algorithm experiments.
A SimApp is declared as plain Python dicts; `render_obs(internal, page_id)` maps
internal ground truth to observable values on each page.

Page element schema:
    {"eid": str, "role": str, "text": str, "kind": "click"|"input",
     "effect": {...}}          # for click elements
Effect ops:
    {"op": "goto", "to": page_id}
    {"op": "crash"}
    {"op": "js_error", "message": str}
    {"op": "mutate", "mutations": [[op_name, value], ...], "then": effect|None}
    {"op": "noop"}
    optional "guard": {"if_not": internal_key, "goto": page_id}
Mutation op names (built-in): cart_add, cart_remove, purchase, login, set_field, submit_form
Input rules per page: "input_rules": {eid: {"max_len": int, "on_violate": effect}}
"""
from __future__ import annotations

import copy
from typing import Callable, Optional

from ..state.models import GUIState, Action, UIElement
from .base import Executor, ExecResult


class SimApp:
    def __init__(self, app_id: str, start: str, pages: dict,
                 initial_internal: dict,
                 render_obs: Callable[[dict, str], dict]):
        self.app_id = app_id
        self.start = start
        self.pages = pages
        self.initial_internal = initial_internal
        self.render_obs = render_obs


class SimExecutor(Executor):
    def __init__(self, app: SimApp):
        self.app = app
        self._crashed = False
        self.reset()

    # ---- lifecycle ----
    def reset(self) -> GUIState:
        self.internal = copy.deepcopy(self.app.initial_internal)
        self.page = self.app.start
        self.nav_stack: list[str] = []
        self._crashed = False
        return self.observe()

    def ground_truth(self) -> dict:
        return self.internal

    # ---- observation ----
    def observe(self) -> GUIState:
        if self._crashed:
            raise RuntimeError("app is crashed; call reset()")
        pdef = self.app.pages[self.page]
        elements = tuple(
            UIElement(eid=e["eid"], role=e.get("role", "button"),
                      text=e.get("text", ""), kind=e.get("kind", "click"),
                      enabled=e.get("enabled", True),
                      input_type=e.get("input_type", ""),
                      placeholder=e.get("placeholder", ""),
                      name=e.get("name", ""),
                      aria_label=e.get("aria_label", ""))
            for e in pdef.get("elements", [])
        )
        return GUIState(
            app=self.app.app_id,
            url=f"sim://{self.app.app_id}{pdef['url']}",
            title=pdef.get("title", ""),
            elements=elements,
            obs=self.app.render_obs(self.internal, self.page),
            meta={"page": self.page},
        )

    # ---- mutations ----
    def _apply_mutation(self, name: str, value):
        it = self.internal
        if name == "cart_add":
            it["cart"].append(value)
            # NOTE: total display updated on add (bug: not updated on remove)
            it["cart_total_display"] = sum(i["price"] * i["qty"] for i in it["cart"])
        elif name == "cart_remove":
            if it["cart"]:
                it["cart"].pop(0)
            # BUG seed: cart_total_display intentionally NOT updated here.
        elif name == "cart_remove_todo":
            if it.get("todos"):
                it["todos"].pop(0)
            # BUG seed: count_display intentionally NOT updated here.
        elif name == "purchase":
            it["stock"] = it.get("stock", 0) - 1
        elif name == "login":
            it["logged_in"] = True
        elif name == "set_field":
            key, val = value
            it.setdefault("fields", {})[key] = val
        elif name == "set_msg":
            it["form_msg"] = value
        elif name == "submit_form":
            it["form_submitted"] = True
        else:
            raise ValueError(f"unknown mutation {name}")

    def _apply_effect(self, effect: Optional[dict], result: ExecResult) -> Optional[str]:
        """Returns goto target page id or None. Mutates result for crash/js_error."""
        if not effect:
            return None
        guard = effect.get("guard")
        if guard and not self.internal.get(guard["if_not"]):
            return guard["goto"]
        when = effect.get("when")
        if when and "empty" in when and self.internal.get(when["empty"]):
            return self._apply_effect(effect.get("else"), result)
        op = effect.get("op")
        if op == "crash":
            result.crashed = True
            result.ok = True
            self._crashed = True
            return None
        if op == "js_error":
            result.js_errors.append(effect.get("message", "js error"))
            return None
        if op == "mutate":
            for name, value in effect.get("mutations", []):
                self._apply_mutation(name, value)
            result.events.append("mutated")
            return self._apply_effect(effect.get("then"), result)
        if op == "goto":
            return effect["to"]
        if op == "noop":
            return None
        return None

    # ---- execution ----
    def execute(self, action: Action) -> ExecResult:
        if self._crashed:
            return ExecResult(ok=False, crashed=True, message="app already crashed")
        pdef = self.app.pages[self.page]

        if action.type == "back":
            if not self.nav_stack:
                return ExecResult(ok=True, state=self.observe(),
                                  message="back at root (no-op)")
            self.page = self.nav_stack.pop()
            return ExecResult(ok=True, state=self.observe(), events=["navigated"])

        if action.type == "wait":
            return ExecResult(ok=True, state=self.observe())

        elem = None
        for e in pdef.get("elements", []):
            if e["eid"] == action.target_eid and e.get("enabled", True):
                elem = e
                break
        if elem is None:
            return ExecResult(ok=False, state=self.observe(),
                              message=f"element {action.target_eid} not found")

        kind = elem.get("kind", "click")
        if action.type == "input" and kind == "input":
            text = action.text or ""
            self.internal.setdefault("fields", {})[elem["eid"]] = text
            result = ExecResult(ok=True)
            rule = pdef.get("input_rules", {}).get(elem["eid"])
            if rule and len(text) > rule.get("max_len", 1 << 30):
                self._apply_effect(rule["on_violate"], result)
            result.state = self.observe() if not result.crashed else None
            return result

        if action.type == "click" and kind == "click":
            result = ExecResult(ok=True)
            target = self._apply_effect(elem.get("effect"), result)
            if result.crashed:
                return result
            if target:
                self.nav_stack.append(self.page)
                self.page = target
                result.events.append("navigated")
            result.state = self.observe()
            return result

        return ExecResult(ok=False, state=self.observe(),
                          message=f"action {action.type} not supported by {kind} element")
