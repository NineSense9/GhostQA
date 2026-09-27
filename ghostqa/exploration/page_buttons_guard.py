"""Take the remaining untried buttons before returning (v0.3.33).

Research-only. Not the product default. The v0.3.32 module is not edited.

The v0.3.32 one-shot takes a single button and then returns. This controller
re-arms that one-shot after each button, so the same non-hub branch keeps
taking the next untried button until none remain. Links are not taken. A hub
or a changed branch drops the chain.
"""
from __future__ import annotations

from .payload_button_guard import (
    PayloadButtonGuardGhostPolicy,
    PayloadButtonSequenceController,
)

_METRIC = "page_button_selections"


class PageButtonsSequenceController(PayloadButtonSequenceController):
    """v0.3.32 button, repeated until the non-hub page has no untried button."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._page_buttons = 0

    def reset(self):
        super().reset()
        self._page_buttons = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = PayloadButtonSequenceController.pick_override(
            self, actions, state, graph, ctx)
        if chosen is not None and self.last_label == "payload_button":
            self._page_buttons += 1
            self._button_due = True
            self._button_due_branch = self.ledger.active_branch or ""
        return chosen

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._page_buttons
        return out


class PageButtonsGuardGhostPolicy(PayloadButtonGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-page-buttons-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = PageButtonsSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "PageButtonsGuardGhostPolicy",
    "PageButtonsSequenceController",
]
