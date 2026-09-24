"""Experimental return-waypoint frontier escape (v0.3.21).

Research-only. Not the product default. The v0.3.19 controller is reused by
subclassing; its module is not modified.

After a handoff-resolved outer sequence resumes returning, a true return may
land on a previously visited intermediate hub that still has residual local or
structural frontier. The return obligation is abandoned there. The escape does
not choose the next action and does not count a successful return.
"""
from __future__ import annotations

from ..state.models import Action
from .finding_return_entry_guard import FindingReturnEntryDrainSequenceController
from .policy import GhostPolicy
from .sequence import branch_key, is_branch_click, is_return_action


class ReturnWaypointFrontierSequenceController(FindingReturnEntryDrainSequenceController):
    """v0.3.19 composite policy plus intermediate-waypoint return escape."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_waypoint()

    def _reset_waypoint(self) -> None:
        self._resumed = {}
        self._outbound = {}
        self._escape_keys = set()
        self._wp_checks = 0
        self._wp_known = 0
        self._wp_residual = 0
        self._wp_escapes = 0
        self._wp_local_count = 0
        self._wp_struct_count = 0
        self._wp_suppressed = 0
        self._wp_exact = 0
        self._wp_cluster = 0
        self._wp_false_success = 0
        self._wp_terminal_violations = 0
        self._wp_parent_violations = 0
        self._wp_stack_violations = 0
        self._wp_unknown_violations = 0
        self._wp_repeat_violations = 0
        self._residual_graph = None

    def reset(self):
        super().reset()
        self._reset_waypoint()

    def _bucket(self, instance_id: str) -> dict:
        return self._outbound.setdefault(instance_id, {"clusters": [], "sigs": set()})

    def _note_outbound(self, instance_id: str, sig: str, graph) -> None:
        if not instance_id or not sig or sig == "CRASHED":
            return
        cluster = self._cluster(sig, graph)
        if not cluster:
            return
        bucket = self._bucket(instance_id)
        if cluster not in bucket["clusters"]:
            bucket["clusters"].append(cluster)
        bucket["sigs"].add(sig)

    def _open_id(self):
        if self._open_instance is None:
            return None
        return self._open_instance.get("id")

    def _absorb_resumes(self, new_events: list) -> None:
        for event in new_events:
            if event.get("event") != "parent_frame_resume_to_return":
                continue
            instance_id = event.get("resumed_sequence_instance_id") or event.get("sequence_instance_id")
            if not instance_id:
                continue
            reason = event.get("reason") or "parent_frame_resume_to_return"
            for item in new_events:
                if item.get("event") != "sequence_horizon_reached":
                    continue
                if item.get("reason") != "horizon_handoff_resolved":
                    continue
                if item.get("step") == event.get("step"):
                    reason = "horizon_handoff_resolved"
                    break
            bucket = self._outbound.get(instance_id) or {"clusters": [], "sigs": set()}
            self._resumed[instance_id] = {
                "sequence_instance_id": instance_id,
                "branch": event.get("resumed_branch") or event.get("branch_key") or "",
                "parent_sig": event.get("original_parent_hub_sig") or "",
                "parent_cluster": event.get("original_parent_hub_cluster") or "",
                "stack_depth": event.get("stack_depth"),
                "resume_step": event.get("step"),
                "reason": reason,
                "visited_clusters": list(bucket.get("clusters") or []),
                "visited_sigs": set(bucket.get("sigs") or []),
            }

    def _note_outbound_after(self, pre_id, pre_returning, new_sig, crashed, new_state,
                             new_events, graph) -> None:
        usable = bool(new_state is not None and new_sig and new_sig != "CRASHED" and not crashed)
        for event in new_events:
            if event.get("event") != "branch_start":
                continue
            instance_id = event.get("sequence_instance_id") or ""
            self._note_outbound(instance_id, event.get("exact_sig") or "", graph)
            if usable:
                self._note_outbound(instance_id, new_sig, graph)
        if pre_returning or not usable or not pre_id:
            return
        if self._open_id() == pre_id:
            self._note_outbound(pre_id, new_sig, graph)

    def _residual_visible(self, state, sig: str, cluster: str) -> tuple:
        if state is None or not cluster:
            return [], []
        self._observe_branches(state, sig, self._residual_graph)
        local = [item[2] for item in self._eligible_buttons(state, cluster)]
        blocked_branch = self.ledger.active_branch or ""
        frontier = self._frontier_keys(cluster, exclude={blocked_branch})
        structural = []
        for element in getattr(state, "elements", ()) or ():
            if not getattr(element, "enabled", True):
                continue
            if (getattr(element, "kind", "click") or "click") != "click":
                continue
            action = Action("click", element.eid)
            if not is_branch_click(action, state) or is_return_action(action, state):
                continue
            key = branch_key(cluster, action)
            if key == blocked_branch or key not in frontier:
                continue
            structural.append(key)
        return local, structural

    def _parent_hit(self, new_sig: str, dest_cluster: str, ctx: dict) -> bool:
        parent_sig = ctx.get("parent_sig") or ""
        parent_cluster = ctx.get("parent_cluster") or ""
        if parent_sig and new_sig == parent_sig:
            return True
        return bool(dest_cluster and parent_cluster and dest_cluster == parent_cluster)

    def _maybe_escape(self, pre, action, new_state, new_sig, crashed, graph, step: int) -> None:
        if not pre["returning"] or pre["label"] != "return_hub" or not pre["action_is_return"]:
            return
        if crashed or new_state is None or not new_sig or new_sig == "CRASHED":
            return
        new_events = self.events[pre["n_events"]:]
        if any(event.get("event") == "return_cycle_escape" for event in new_events):
            return
        if any(
            event.get("event") == "sequence_terminal" and event.get("outcome") == "returned"
            for event in new_events
        ):
            return
        if int(self.ledger.return_success) != pre["success"]:
            return
        instance_id = self._open_id()
        if not instance_id or instance_id != pre["open_id"]:
            return
        if self._already_terminal(instance_id):
            return
        ctx = self._resumed.get(instance_id)
        if not ctx:
            return
        if not self.ledger.returning or not self.ledger.active_branch:
            return
        if (self.ledger.active_branch or "") != (ctx.get("branch") or ""):
            return
        if (ctx.get("branch") or "") != pre["branch"]:
            return
        if self.stack_depth != 0:
            return
        self._wp_checks += 1
        dest_cluster = self._cluster(new_sig, graph)
        if self._parent_hit(new_sig, dest_cluster, ctx):
            return
        visited = set(ctx.get("visited_clusters") or [])
        if not dest_cluster or dest_cluster not in visited:
            return
        self._wp_known += 1
        strength = "exact" if new_sig in set(ctx.get("visited_sigs") or []) else "cluster"
        self._residual_graph = graph
        local_keys, structural_keys = self._residual_visible(new_state, new_sig, dest_cluster)
        self._residual_graph = None
        if not local_keys and not structural_keys:
            return
        self._wp_residual += 1
        escape_key = (self.ledger.active_branch or "", dest_cluster)
        if escape_key in self._escape_keys:
            self._wp_suppressed += 1
            return
        self._abandon(pre, ctx, new_sig, dest_cluster, strength, local_keys, structural_keys, step)

    def _abandon(self, pre, ctx, new_sig, dest_cluster, strength, local_keys, structural_keys, step):
        instance_id = self._open_id()
        branch = self.ledger.active_branch or ""
        escape_key = (branch, dest_cluster)
        if self._parent_hit(new_sig, dest_cluster, ctx):
            self._wp_parent_violations += 1
            return
        if self.stack_depth != 0:
            self._wp_stack_violations += 1
            return
        if dest_cluster not in set(ctx.get("visited_clusters") or []):
            self._wp_unknown_violations += 1
            return
        if escape_key in self._escape_keys:
            self._wp_repeat_violations += 1
            return
        if instance_id and self._already_terminal(instance_id):
            self._wp_terminal_violations += 1
            return
        length = 0 if self._open_instance is None else self._open_instance.get("len", 0)
        returned_before = self._returned_count()
        payload = {
            "step": step,
            "sequence_instance_id": instance_id,
            "active_branch": branch,
            "original_final_parent_sig": ctx.get("parent_sig") or "",
            "original_final_parent_cluster": ctx.get("parent_cluster") or "",
            "waypoint_sig": new_sig,
            "waypoint_cluster": dest_cluster,
            "waypoint_match_strength": strength,
            "resume_step": ctx.get("resume_step"),
            "stack_depth": self.stack_depth,
            "local_residual_keys": list(local_keys),
            "local_residual_count": len(local_keys),
            "structural_residual_keys": list(structural_keys),
            "structural_residual_count": len(structural_keys),
            "return_attempts": int(self.ledger.return_attempts),
            "return_success_before": pre["success"],
            "escape_suppression_key": [branch, dest_cluster],
            "reason": "residual_frontier",
        }
        self._emit(
            "return_waypoint_frontier_escape", step, new_sig, dest_cluster, branch, payload)
        self._emit(
            "sequence_terminal", step, new_sig, dest_cluster, branch,
            {
                "outcome": "return_cycle_abandoned",
                "reason": "return_waypoint_escape",
                "length": length,
            })
        self._open_instance = None
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger.parent_hub_sig = ""
        self.ledger.parent_hub_cluster = ""
        self.ledger._seq_len = 0
        self._seen_failed_return_dests = set()
        self._return_entry = None
        self._pending_return_probe = None
        if self._lease is not None:
            self._lease["active"] = False
        self._pending_lease_action = None
        self._lease_chain = 0
        if instance_id:
            self._deferred_unemitted.discard(instance_id)
            self._horizon_emitted.add(instance_id)
        self._escape_keys.add(escape_key)
        self.last_label = "normal"
        self._wp_escapes += 1
        self._wp_local_count += len(local_keys)
        self._wp_struct_count += len(structural_keys)
        if strength == "exact":
            self._wp_exact += 1
        else:
            self._wp_cluster += 1
        parent = ctx.get("parent_sig") or ""
        record = self.ledger.hubs.get(parent)
        falsely_completed = bool(
            record is not None and (branch in record.completed or branch in record.returned))
        terminals = [
            event for event in self.events
            if event.get("event") == "sequence_terminal"
            and event.get("sequence_instance_id") == instance_id
        ]
        returned_now = [
            event for event in terminals if event.get("outcome") == "returned"
        ]
        if (
            int(self.ledger.return_success) != pre["success"]
            or self._returned_count() != returned_before
            or returned_now
        ):
            self._wp_false_success += 1
        if (
            len(terminals) != 1
            or terminals[0].get("outcome") != "return_cycle_abandoned"
            or int(self.ledger.sequences_started) != pre["started"]
            or int(self.ledger.sequences_completed) != pre["completed"]
            or self.ledger.returning
            or self.ledger.active_branch
            or self.ledger.commitment_left
            or falsely_completed
            or self.stack_depth < 0
        ):
            self._wp_terminal_violations += 1

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        pre = {
            "returning": bool(self.ledger.returning),
            "label": self.last_label,
            "action_is_return": is_return_action(action, state),
            "open_id": self._open_id(),
            "branch": self.ledger.active_branch or "",
            "success": int(self.ledger.return_success),
            "started": int(self.ledger.sequences_started),
            "completed": int(self.ledger.sequences_completed),
            "n_events": len(self.events),
        }
        if pre["open_id"] and not pre["returning"]:
            self._note_outbound(pre["open_id"], sig, graph)
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        new_events = self.events[pre["n_events"]:]
        self._note_outbound_after(
            pre["open_id"], pre["returning"], new_sig, bool(crashed), new_state,
            new_events, graph)
        self._absorb_resumes(new_events)
        self._maybe_escape(pre, action, new_state, new_sig, bool(crashed), graph, step)

    def metrics(self) -> dict:
        out = super().metrics()
        out["return_waypoint_checks"] = self._wp_checks
        out["return_waypoint_known_intermediate"] = self._wp_known
        out["return_waypoint_residual_present"] = self._wp_residual
        out["return_waypoint_frontier_escape_events"] = self._wp_escapes
        out["return_waypoint_escape_local_residual_count"] = self._wp_local_count
        out["return_waypoint_escape_structural_residual_count"] = self._wp_struct_count
        out["return_waypoint_escape_repeat_suppressed"] = self._wp_suppressed
        out["return_waypoint_escape_exact_matches"] = self._wp_exact
        out["return_waypoint_escape_cluster_matches"] = self._wp_cluster
        out["return_waypoint_false_success_violations"] = self._wp_false_success
        out["return_waypoint_terminal_accounting_violations"] = self._wp_terminal_violations
        out["return_waypoint_parent_precedence_violations"] = self._wp_parent_violations
        out["return_waypoint_stack_scope_violations"] = self._wp_stack_violations
        out["return_waypoint_unknown_hub_violations"] = self._wp_unknown_violations
        out["return_waypoint_repeat_escape_violations"] = self._wp_repeat_violations
        return out


class ReturnWaypointFrontierGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-return-waypoint-frontier-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ReturnWaypointFrontierSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "ReturnWaypointFrontierGuardGhostPolicy",
    "ReturnWaypointFrontierSequenceController",
]
