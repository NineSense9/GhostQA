"""Replace a repeated input with a different payload (v0.3.31).

Research-only. Not the product default. The v0.3.30 controller is subclassed
but its click-stealing rule is not used.

On a non-hub page, a followup that would repeat an input already used in the
current branch is replaced by another input for the same field. No other
click is taken.
"""
from __future__ import annotations

from .parent_hub_sibling_guard import ParentHubSiblingSequenceController
from .repeat_click_guard import RepeatClickGuardGhostPolicy
from .sequence import FOLLOWUP_LIKE, is_hub, is_return_action

_METRIC = "alternate_payload_selections"


class AlternatePayloadSequenceController(ParentHubSiblingSequenceController):
    """v0.3.27 parent-hub rule, plus one alternate input on a non-hub page."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._branch_inputs = {}
        self._alternate_payloads = 0

    def reset(self):
        super().reset()
        self._branch_inputs = {}
        self._alternate_payloads = 0

    def pick_override(self, actions, state, graph, ctx):
        chosen = self._alternate_input(actions, state, ctx)
        if chosen is not None:
            return chosen
        return ParentHubSiblingSequenceController.pick_override(
            self, actions, state, graph, ctx)

    def _alternate_input(self, actions, state, ctx):
        if self._sibling_blocked():
            return None
        if self.mode not in FOLLOWUP_LIKE or not self.ledger.commitment_left:
            return None
        if self.ledger.returning or not actions or is_hub(state):
            return None
        branch = self.ledger.active_branch or ""
        used = self._branch_inputs.get(branch) or set()
        if not used:
            return None
        followups = [
            action for action in actions
            if not is_return_action(action, state) and self._is_followup(action)
        ]
        if not followups or followups[0].key() not in used:
            return None
        if getattr(followups[0], "type", "") != "input":
            return None
        eid = followups[0].target_eid
        for action in actions:
            if getattr(action, "type", "") != "input" or action.target_eid != eid:
                continue
            if action.key() in used:
                continue
            self._alternate_payloads += 1
            self.last_label = "alternate_payload"
            return action
        return None

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        branch = self.ledger.active_branch or ""
        key = "" if action is None or getattr(action, "type", "") != "input" else action.key()
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        if key and branch:
            self._branch_inputs.setdefault(branch, set()).add(key)

    def label_for(self, action, state) -> str:
        if self.last_label == "alternate_payload":
            label = self.last_label
            self.last_label = ""
            return label
        return super().label_for(action, state)

    def metrics(self) -> dict:
        out = super().metrics()
        out[_METRIC] = self._alternate_payloads
        return out


class AlternatePayloadGuardGhostPolicy(RepeatClickGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-alternate-payload-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = AlternatePayloadSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False


__all__ = [
    "AlternatePayloadGuardGhostPolicy",
    "AlternatePayloadSequenceController",
]
