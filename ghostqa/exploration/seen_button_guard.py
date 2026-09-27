"""Do not click the same button twice in one branch (v0.3.34).

Research-only. Not the product default. The v0.3.33 module is not edited.

v0.3.33 asked the current signature whether a button was already tried.
A click that changes the signature looks untried again, so one button can
be repeated until the budget ends. This controller remembers the button
ids taken on the current branch and drops the chain when the next choice
repeats one of them.
"""
from __future__ import annotations

from .page_buttons_guard import (
    PageButtonsGuardGhostPolicy,
    PageButtonsSequenceController,
)
from .payload_button_guard import PayloadButtonSequenceController
from .sequence import is_return_action

_METRIC = "seen_button_stops"


class SeenButtonSequenceController(PageButtonsSequenceController):
    """v0.3.33 button chain, stopped when a branch repeats a button id."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._seen_eids = {}
        self._seen_stops = 0

    def reset(self):
        super().reset()
        self._seen_eids = {}
        self._seen_stops = 0

    def _payload_button(self, actions, state, graph, ctx):
        chosen = PayloadButtonSequenceController._payload_button(
            self, actions, state, graph, ctx)
        if chosen is None:
            return None
        branch = self.ledger.active_branch or ""
        seen = self._seen_eids.setdefault(branch, set())
        eid = chosen.target_eid or ""
        if eid not in seen:
            seen.add(eid)
            return chosen
        self._payload_buttons = max(0, self._payload_buttons - 1)
        self.last_label = ""
        sig = "" if not ctx else (ctx.get("sig") or "")
        node = None if graph is None else graph.nodes.get(sig)
        tried = set() if node is None else set(node.tried_actions)
        for action in actions or []:
            if getattr(action, "type", "") != "click":
                continue
            if is_return_action(action, state) or action.key() in tried:
                continue
            if self._element_role(action, state) != "button":
                continue
            nxt = action.target_eid or ""
            if nxt in seen:
                continue
            seen.add(nxt)
            self._payload_buttons += 1
            self.last_label = "payload_button"
            return action
        self._button_due = False
        self._button_due_branch = ""
        self._seen_stops += 1
        return None

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._seen_stops
        return out


class SeenButtonGuardGhostPolicy(PageButtonsGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-seen-button-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = SeenButtonSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "SeenButtonGuardGhostPolicy",
    "SeenButtonSequenceController",
]
