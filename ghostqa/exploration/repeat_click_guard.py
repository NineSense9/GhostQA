"""Replace a repeated followup with an untried click (v0.3.30).

Research-only. Not the product default. The v0.3.27 controller is reused
by subclassing; its module is not modified.

When a sequence still has commitment and the first followup would repeat an
action key already tried on this signature, an untried non-return click on
the page is taken instead.
"""
from __future__ import annotations

from .parent_hub_sibling_guard import (
    ParentHubSiblingGuardGhostPolicy,
    ParentHubSiblingSequenceController,
)
from .sequence import FOLLOWUP_LIKE, is_return_action

_METRIC = "untried_click_before_repeat_selections"


class RepeatClickSequenceController(ParentHubSiblingSequenceController):
    """v0.3.27 parent-hub rule, plus one yield away from a repeated followup."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._repeat_clicks = 0

    def reset(self):
        super().reset()
        self._repeat_clicks = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._untried_click(actions, state, graph, ctx)
        if chosen is not None:
            return chosen
        return super().pick_override(actions, state, graph, ctx)

    def _untried_click(self, actions, state, graph, ctx):
        if self._sibling_blocked():
            return None
        if self.mode not in FOLLOWUP_LIKE or not self.ledger.commitment_left:
            return None
        if self.ledger.returning or not actions:
            return None
        sig = "" if not ctx else (ctx.get("sig") or "")
        node = None if graph is None else graph.nodes.get(sig)
        tried = set() if node is None else set(node.tried_actions)
        followups = [
            action for action in actions
            if not is_return_action(action, state) and self._is_followup(action)
        ]
        if not followups or followups[0].key() not in tried:
            return None
        for action in actions:
            if getattr(action, "type", "") != "click":
                continue
            if is_return_action(action, state) or action.key() in tried:
                continue
            self._repeat_clicks += 1
            self.last_label = "untried_click_before_repeat"
            return action
        return None

    def label_for(self, action, state) -> str:
        if self.last_label == "untried_click_before_repeat":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._repeat_clicks
        return out


class RepeatClickGuardGhostPolicy(ParentHubSiblingGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-repeat-click-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = RepeatClickSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "RepeatClickGuardGhostPolicy",
    "RepeatClickSequenceController",
]
