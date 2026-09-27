"""After an alternate payload, take one untried button before returning (v0.3.32).

Research-only. Not the product default. The v0.3.31 module is not edited.

Choosing an alternate payload arms a one-shot for that branch. On the next
returning decision, a non-hub page yields the first untried button click.
Links and return actions are not taken. A hub, or a changed branch, drops
the one-shot.
"""
from __future__ import annotations

from .alternate_payload_guard import (
    AlternatePayloadGuardGhostPolicy,
    AlternatePayloadSequenceController,
)
from .sequence import is_hub, is_return_action

_METRIC = "payload_button_selections"


class PayloadButtonSequenceController(AlternatePayloadSequenceController):
    """v0.3.31 alternate payload, plus one button before the following return."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._button_due = False
        self._button_due_branch = ""
        self._payload_buttons = 0

    def reset(self):
        super().reset()
        self._button_due = False
        self._button_due_branch = ""
        self._payload_buttons = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._payload_button(actions, state, graph, ctx)
        if chosen is not None:
            return chosen
        chosen = AlternatePayloadSequenceController.pick_override(
            self, actions, state, graph, ctx)
        if chosen is not None and self.last_label == "alternate_payload":
            self._button_due = True
            self._button_due_branch = self.ledger.active_branch or ""
        return chosen

    def _payload_button(self, actions, state, graph, ctx):
        if not self._button_due:
            return None
        if self._sibling_blocked():
            return None
        branch = self.ledger.active_branch or ""
        if branch != self._button_due_branch:
            self._button_due = False
            self._button_due_branch = ""
            return None
        if not self.ledger.returning:
            return None
        self._button_due = False
        self._button_due_branch = ""
        if is_hub(state) or not actions:
            return None
        sig = "" if not ctx else (ctx.get("sig") or "")
        node = None if graph is None else graph.nodes.get(sig)
        tried = set() if node is None else set(node.tried_actions)
        for action in actions:
            if getattr(action, "type", "") != "click":
                continue
            if is_return_action(action, state) or action.key() in tried:
                continue
            if self._element_role(action, state) != "button":
                continue
            self._payload_buttons += 1
            self.last_label = "payload_button"
            return action
        return None

    @staticmethod
    def _element_role(action, state) -> str:
        if state is None:
            return ""
        for el in state.elements:
            if el.eid == action.target_eid:
                return el.role or ""
        return ""

    def label_for(self, action, state) -> str:
        if self.last_label == "payload_button":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._payload_buttons
        return out


class PayloadButtonGuardGhostPolicy(AlternatePayloadGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-payload-button-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = PayloadButtonSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "PayloadButtonGuardGhostPolicy",
    "PayloadButtonSequenceController",
]
