"""Leave a distractor side path after four steps (v0.3.37).

Research-only. Not the product default. The v0.3.36 module is not edited.

Opening the distractor link kept the explorer on the help and settings pages
until the budget was gone, so the order page never closed and reopened.
This controller lets that side path run four steps, which is the length of
one A-B-A-B navigation, then takes a return action.
"""
from __future__ import annotations

from .hub_distractor_guard import (
    HubDistractorGuardGhostPolicy,
    HubDistractorSequenceController,
)
from .sequence import is_return_action

_METRIC = "loop_exit_selections"
_SIDE_LIMIT = 4


class LoopExitSequenceController(HubDistractorSequenceController):
    """v0.3.36 distractor entry, then a return after four side steps."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._side = False
        self._side_steps = 0
        self._loop_exits = 0

    def reset(self):
        super().reset()
        self._side = False
        self._side_steps = 0
        self._loop_exits = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._leave_side(actions, state)
        if chosen is not None:
            return chosen
        chosen = HubDistractorSequenceController.pick_override(
            self, actions, state, graph, ctx)
        if chosen is not None and self.last_label == "hub_distractor":
            self._side = True
            self._side_steps = 0
        return chosen

    def _leave_side(self, actions, state):
        if not self._side or self._side_steps < _SIDE_LIMIT:
            return None
        self._side = False
        self._side_steps = 0
        for action in actions or []:
            if is_return_action(action, state):
                self._loop_exits += 1
                self.last_label = "loop_exit"
                return action
        return None

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        if self._side:
            self._side_steps += 1

    def label_for(self, action, state) -> str:
        if self.last_label == "loop_exit":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._loop_exits
        return out


class LoopExitGuardGhostPolicy(HubDistractorGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-loop-exit-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = LoopExitSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "LoopExitGuardGhostPolicy",
    "LoopExitSequenceController",
]
