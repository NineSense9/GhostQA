"""Input payload budgeting (v0.3.1).

Payloads are classes, not first-class frontier actions. First encounter of
an input spends a small first-wave; remaining classes are deferred fuzz.
"""
from __future__ import annotations

from .interaction import classify_field

# Semantic classes → concrete strings (Executor still sees Action.text).
PAYLOAD_VALUES = {
    "NORMAL": "测试输入",
    "EMPTY": "",
    "BOUNDARY_LONG": "x" * 25,
    "SCRIPT_SPECIAL": "<script>alert(1)</script>",
    "LARGE_NUMERIC": "999999",
    "NEGATIVE": "-1",
}

ALL_CLASSES = tuple(PAYLOAD_VALUES.keys())

_VALUE_TO_CLASS = {v: k for k, v in PAYLOAD_VALUES.items()}


def class_of_value(text: str) -> str:
    return _VALUE_TO_CLASS.get(text if text is not None else "", "NORMAL")


def first_wave(field_type: str) -> list:
    """First visit: normal + one contextually useful boundary."""
    if field_type == "number":
        return ["NORMAL", "NEGATIVE"]
    if field_type == "search":
        return ["NORMAL", "BOUNDARY_LONG"]
    if field_type == "username":
        return ["NORMAL", "EMPTY"]
    if field_type == "password":
        return ["NORMAL", "EMPTY"]
    if field_type == "email":
        return ["NORMAL", "EMPTY"]
    return ["NORMAL", "EMPTY"]


def deferred_wave(field_type: str) -> list:
    first = set(first_wave(field_type))
    return [c for c in ALL_CLASSES if c not in first]


class PayloadPolicy:
    """Tracks which payload classes have been tried per (state, field)."""

    def __init__(self):
        self.tried: dict = {}          # (sig, eid) -> set[class]
        self.workflow_progressed = False
        self.progress_pages: set = set()

    def mark(self, sig: str, eid: str, text: str):
        self.tried.setdefault((sig, eid), set()).add(class_of_value(text or ""))

    def mark_progress(self, sig: str):
        self.workflow_progressed = True
        self.progress_pages.add(sig)

    def tried_fields(self, sig: str) -> set:
        return {eid for (s, eid) in self.tried if s == sig}

    def allowed_classes(self, el, sig: str, ctx: dict) -> list:
        field = classify_field(el)
        done = self.tried.get((sig, el.eid), set())
        first = [c for c in first_wave(field) if c not in done]
        if first:
            return first
        if self._may_defer(ctx):
            return [c for c in deferred_wave(field) if c not in done]
        return []

    def remaining_deferred(self, el, sig: str) -> list:
        field = classify_field(el)
        done = self.tried.get((sig, el.eid), set())
        return [c for c in deferred_wave(field) if c not in done]

    def remaining_deferred_eid(self, sig: str, eid: str, field_type: str = "unknown") -> list:
        done = self.tried.get((sig, eid), set())
        return [c for c in deferred_wave(field_type) if c not in done]

    def _may_defer(self, ctx: dict) -> bool:
        """Deferred fuzz only after workflow has moved, or no better work."""
        if ctx.get("force_deferred"):
            return True
        if ctx.get("high_risk_page"):
            return True
        if ctx.get("spec_relevant"):
            return True
        remaining = ctx.get("budget", 10**9) - ctx.get("step_index", 0)
        if remaining < 8:
            return False
        # Prefer breadth: only fuzz if this page already progressed or
        # the caller says there is no higher-value frontier.
        if self.workflow_progressed and ctx.get("page_progressed"):
            return True
        if ctx.get("no_better_frontier"):
            return True
        return False

    def actions_for(self, state, sig: str, can_back: bool, ctx: dict) -> list:
        from ..state.models import Action
        acts = []
        for el in state.elements:
            if not el.enabled:
                continue
            if el.kind == "click":
                acts.append(Action("click", el.eid))
            elif el.kind == "input":
                for cls in self.allowed_classes(el, sig, ctx):
                    acts.append(Action("input", el.eid, PAYLOAD_VALUES[cls]))
        if can_back:
            acts.append(Action("back"))
        return acts
