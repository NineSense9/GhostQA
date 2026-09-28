"""Back out of a distractor side path with browser history (v0.3.38).

Research-only. Not the product default. The v0.3.37 module is not edited.

The four-step return on the settings page points back at the help page, so
the explorer stays inside the pair. After four side steps this controller
takes the browser back action until the page is no longer one of the URLs
seen during those four steps.
"""
from __future__ import annotations

from .loop_exit_guard import (
    LoopExitGuardGhostPolicy,
    LoopExitSequenceController,
)

_METRIC = "side_back_selections"


class SideBackSequenceController(LoopExitSequenceController):
    """v0.3.37 side path, then browser back until the page leaves it."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._side_urls = set()
        self._side_backs = 0

    def reset(self):
        super().reset()
        self._side_urls = set()
        self._side_backs = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._browser_back(actions, state)
        if chosen is not None:
            return chosen
        return LoopExitSequenceController.pick_override(
            self, actions, state, graph, ctx)

    def _browser_back(self, actions, state):
        if not self._side or self._side_steps < 4:
            return None
        url = "" if state is None else (getattr(state, "url", "") or "")
        if self._side_urls and url not in self._side_urls:
            self._side = False
            self._side_steps = 0
            return None
        for action in actions or []:
            if getattr(action, "type", "") == "back":
                self._side_backs += 1
                self.last_label = "side_back"
                return action
        return None

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        leaving = self._side and self._side_steps >= 4
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        url = "" if new_state is None else (getattr(new_state, "url", "") or "")
        if self._side and not leaving and url:
            self._side_urls.add(url)
        if leaving and url and url not in self._side_urls:
            self._side = False
            self._side_steps = 0

    def label_for(self, action, state) -> str:
        if self.last_label == "side_back":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._side_backs
        return out


class SideBackGuardGhostPolicy(LoopExitGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-side-back-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = SideBackSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "SideBackGuardGhostPolicy",
    "SideBackSequenceController",
]
