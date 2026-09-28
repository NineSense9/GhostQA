"""Open one distractor link after a hub's branches are started (v0.3.36).

Research-only. Not the product default. The v0.3.35 module is not edited.

A help link is not a branch click, so the hub explorer never starts it.
Once every branch click on that hub has been started, this controller takes
one untried distractor link. Return links are not taken. Each hub cluster
gets one such click.
"""
from __future__ import annotations

from .interaction import DISTRACTOR_KEYWORDS
from .search_submit_guard import (
    SearchSubmitGuardGhostPolicy,
    SearchSubmitSequenceController,
)
from .sequence import (
    branch_key,
    is_branch_click,
    is_hub,
    is_progress_action,
    is_return_action,
)

_METRIC = "hub_distractor_selections"


class HubDistractorSequenceController(SearchSubmitSequenceController):
    """v0.3.35 search-submit rule, plus one distractor link per hub."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._distractor_done = set()
        self._distractor_picks = 0

    def reset(self):
        super().reset()
        self._distractor_done = set()
        self._distractor_picks = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._hub_distractor(actions, state, graph, ctx)
        if chosen is not None:
            return chosen
        return SearchSubmitSequenceController.pick_override(
            self, actions, state, graph, ctx)

    def _hub_distractor(self, actions, state, graph, ctx):
        if self._sibling_blocked() or self.ledger.returning or not is_hub(state):
            return None
        sig = "" if not ctx else (ctx.get("sig") or "")
        cluster = self._cluster(sig, graph)
        if not cluster or cluster in self._distractor_done:
            return None
        rec = self.ledger.hub(sig, cluster)
        for action in actions or []:
            if not is_branch_click(action, state):
                continue
            if branch_key(cluster, action) not in rec.started:
                return None
        node = None if graph is None else graph.nodes.get(sig)
        tried = set() if node is None else set(node.tried_actions)
        for action in actions or []:
            if getattr(action, "type", "") != "click":
                continue
            if is_return_action(action, state) or is_progress_action(action, state):
                continue
            if is_branch_click(action, state) or action.key() in tried:
                continue
            blob = self._blob(action, state)
            if not any(word.lower() in blob for word in DISTRACTOR_KEYWORDS):
                continue
            self._distractor_done.add(cluster)
            self._distractor_picks += 1
            self.last_label = "hub_distractor"
            return action
        return None

    @staticmethod
    def _blob(action, state) -> str:
        parts = [action.target_eid or ""]
        if state is not None:
            for el in state.elements:
                if el.eid == action.target_eid:
                    parts.extend([el.text or "", el.role or ""])
                    break
        return " ".join(parts).lower()

    def label_for(self, action, state) -> str:
        if self.last_label == "hub_distractor":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._distractor_picks
        return out


class HubDistractorGuardGhostPolicy(SearchSubmitGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-hub-distractor-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = HubDistractorSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "HubDistractorGuardGhostPolicy",
    "HubDistractorSequenceController",
]
