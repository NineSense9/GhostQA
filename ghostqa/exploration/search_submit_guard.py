"""Submit a search once after its long payload (v0.3.35).

Research-only. Not the product default. The v0.3.34 module is not edited.

A long search payload changes the page and the next decision leaves through
a hub link. This controller remembers that destination signature and, on the
next decision there, takes one untried button. Links are not taken.
"""
from __future__ import annotations

from .interaction import classify_field
from .payload import class_of_value
from .seen_button_guard import (
    SeenButtonGuardGhostPolicy,
    SeenButtonSequenceController,
)
from .sequence import is_return_action

_METRIC = "search_submit_selections"


class SearchSubmitSequenceController(SeenButtonSequenceController):
    """v0.3.34 seen-button rule, plus one button after a long search input."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._search_due = False
        self._search_sig = ""
        self._search_submits = 0

    def reset(self):
        super().reset()
        self._search_due = False
        self._search_sig = ""
        self._search_submits = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._search_button(actions, state, graph, ctx)
        if chosen is not None:
            return chosen
        return SeenButtonSequenceController.pick_override(
            self, actions, state, graph, ctx)

    def _search_button(self, actions, state, graph, ctx):
        if not self._search_due:
            return None
        sig = "" if not ctx else (ctx.get("sig") or "")
        if sig != self._search_sig:
            self._search_due = False
            self._search_sig = ""
            return None
        self._search_due = False
        self._search_sig = ""
        if not actions:
            return None
        node = None if graph is None else graph.nodes.get(sig)
        tried = set() if node is None else set(node.tried_actions)
        for action in actions:
            if getattr(action, "type", "") != "click":
                continue
            if is_return_action(action, state) or action.key() in tried:
                continue
            if self._element_role(action, state) != "button":
                continue
            self._search_submits += 1
            self.last_label = "search_submit"
            return action
        return None

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        arm = self._long_search(action, state)
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        if arm and new_sig:
            self._search_due = True
            self._search_sig = new_sig

    @staticmethod
    def _long_search(action, state) -> bool:
        if action is None or getattr(action, "type", "") != "input":
            return False
        if class_of_value(action.text or "") != "BOUNDARY_LONG":
            return False
        if state is None:
            return False
        for el in state.elements:
            if el.eid == action.target_eid:
                return classify_field(el) == "search"
        return False

    def label_for(self, action, state) -> str:
        if self.last_label == "search_submit":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._search_submits
        return out


class SearchSubmitGuardGhostPolicy(SeenButtonGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-search-submit-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = SearchSubmitSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "SearchSubmitGuardGhostPolicy",
    "SearchSubmitSequenceController",
]
