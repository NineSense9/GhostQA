"""Experimental return-cycle guard (v0.3.9).

Isolated from frozen SequenceController / GhostPolicy source files.

During an unresolved return phase, arriving at the same exact destination
signature (new_sig) a second time before matching the recorded parent hub
is treated as a deterministic return cycle. The branch is abandoned, not
returned/completed. No attempt threshold N. No cluster-only trigger.
"""
from __future__ import annotations

from .policy import GhostPolicy
from .sequence import SequenceController


class ReturnCycleGuardSequenceController(SequenceController):
    """Structural sequence plus exact-signature return-cycle escape."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._seen_failed_return_dests: set = set()
        self._escape_n = 0
        self._abandoned_n = 0

    def reset(self):
        super().reset()
        self._seen_failed_return_dests = set()
        self._escape_n = 0
        self._abandoned_n = 0

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        was_returning = self.ledger.returning
        super().after(sig, action, state, new_state, relation, findings,
                      new_sig, crashed, graph, step)
        if not self.ledger.returning:
            self._seen_failed_return_dests = set()
            return
        if not was_returning:
            self._seen_failed_return_dests = set()
        dest = new_sig or ""
        if not dest:
            return
        if dest in self._seen_failed_return_dests:
            self._escape_cycle(step, sig, dest, graph)
            return
        self._seen_failed_return_dests.add(dest)

    def _escape_cycle(self, step, sig, dest, graph):
        cluster = ""
        if graph is not None and sig in getattr(graph, "nodes", {}):
            cluster = graph.nodes[sig].cluster_id
        elif sig:
            cluster = sig.split(":")[0]
        extra = {
            "repeated_destination_sig": dest,
            "parent_hub_sig": self.ledger.parent_hub_sig,
            "parent_hub_cluster": self.ledger.parent_hub_cluster,
            "active_branch": self.ledger.active_branch,
            "return_phase_attempts": len(self._seen_failed_return_dests),
            "outcome": "return_cycle_abandoned",
        }
        self._emit("return_cycle_escape", step, sig, cluster,
                   self.ledger.active_branch, extra)
        if self._open_instance is not None:
            self._emit("sequence_terminal", step, sig, cluster,
                       self._open_instance.get("branch", ""),
                       {"outcome": "return_cycle_abandoned"})
            self._open_instance = None
        self._escape_n += 1
        self._abandoned_n += 1
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger.parent_hub_sig = ""
        self.ledger.parent_hub_cluster = ""
        self._seen_failed_return_dests = set()

    def metrics(self) -> dict:
        out = super().metrics()
        out["return_cycle_escape_events"] = self._escape_n
        out["return_cycle_abandoned_branches"] = self._abandoned_n
        n_term = sum(
            1 for e in self.events
            if e.get("event") == "sequence_terminal"
            and e.get("outcome") == "return_cycle_abandoned")
        out["sequence_return_cycle_abandoned"] = n_term
        return out


class ReturnCycleGuardGhostPolicy(GhostPolicy):
    """Benchmark-only experimental identity. Not the product default."""

    name = "ghost-structural-return-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ReturnCycleGuardSequenceController("structural")
        self.sequence_mode = "structural"
