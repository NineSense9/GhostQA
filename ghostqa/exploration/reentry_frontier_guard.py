"""Experimental early parent re-entry and local frontier lease (v0.3.16).

Research-only. Not the product default. Does not replace historical
identities. The v0.3.14 controller is reused by subclassing; its module is
not modified.

Invariant A: a non-returning active sequence completes when the destination
matches its recorded parent signature or cluster, even if commitment remains.

Invariant B: after a valid child-parent witness, one previously discovered
and still untried local branch key at that hub receives a single structural
slot before the outer sequence is forced to return.
"""
from __future__ import annotations

from ..state.models import Action
from .horizon_handoff_guard import HorizonHandoffSequenceController
from .policy import GhostPolicy
from .return_cycle_guard import ReturnCycleGuardSequenceController
from .sequence import branch_key, is_branch_click, is_return_action


def _json_list(values) -> list:
    return sorted(str(item) for item in values)


class ReentryFrontierSequenceController(HorizonHandoffSequenceController):
    """Horizon handoff plus parent re-entry and a one-slot frontier lease."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_reentry_state()

    def _reset_reentry_state(self) -> None:
        self._reentry_arm = None
        self._skip_early = False
        self._last_destination_state = None
        self._lease = None
        self._lease_generation = 0
        self._lease_chain = 0
        self._max_lease_chain = 0
        self._leased_keys: set = set()
        self._known_keys: dict = {}
        self._frontier_new_keys_from_variant = 0
        self._repeated_key_violations = 0
        self._mono_violations = 0
        self._mono = None
        self._pending_lease_action = None
        self._reentry_double = 0
        self._deferred_unemitted: set = set()
        self._horizon_emitted: set = set()
        self._deferred_by_return = 0
        self._deferred_by_reentry = 0
        self._lease_cross_hub = 0
        self._lease_active_at_end = False
        self._lease_remaining_at_end = 0
        self._budget_end_seen = False

    def reset(self):
        super().reset()
        self._reset_reentry_state()

    def _match_parent(self, sig: str, graph) -> str:
        parent_sig = self.ledger.parent_hub_sig or ""
        parent_cluster = self.ledger.parent_hub_cluster or ""
        if not sig:
            return ""
        if parent_sig and sig == parent_sig:
            return "exact"
        cluster = self._cluster(sig, graph)
        if cluster and parent_cluster and cluster == parent_cluster:
            return "cluster"
        return ""

    def _observe_branches(self, state, sig: str, graph) -> None:
        if state is None or not sig:
            return
        cluster = self._cluster(sig, graph)
        rec = self.ledger.hub(sig, cluster)
        seen = set()
        for element in getattr(state, "elements", ()) or ():
            if not getattr(element, "enabled", True):
                continue
            if (getattr(element, "kind", "click") or "click") != "click":
                continue
            action = Action("click", element.eid)
            if not is_branch_click(action, state):
                continue
            key = branch_key(cluster, action)
            rec.discovered.add(key)
            seen.add(key)
        self._note_variant_keys(cluster, seen)

    def _note_variant_keys(self, cluster: str, keys) -> None:
        if not cluster or not keys:
            return
        known = self._known_keys.setdefault(cluster, set())
        fresh = set(keys) - known
        if known and fresh:
            self._frontier_new_keys_from_variant += len(fresh)
        known |= set(keys)

    def _frontier_keys(self, cluster: str, exclude=()) -> set:
        discovered: set = set()
        started: set = set()
        completed: set = set()
        for rec in self.ledger.hubs.values():
            if (rec.hub_cluster or "") != (cluster or ""):
                continue
            discovered |= set(rec.discovered)
            started |= set(rec.started)
            completed |= set(rec.completed)
        attempted: set = set()
        hub = self.struct.hubs.get(cluster or "?")
        if hub is not None:
            for key, hist in hub.branches.items():
                if getattr(hist, "attempts", 0) > 0:
                    attempted.add(key)
        blocked = started | completed | attempted | set(exclude or ()) | set(self._leased_keys)
        return {key for key in discovered if key not in blocked}

    def _snapshot(self) -> dict:
        instance = self._open_instance or {}
        return {
            "sequence_instance_id": instance.get("id"),
            "active_branch": self.ledger.active_branch or "",
            "parent_hub_sig": self.ledger.parent_hub_sig or "",
            "parent_hub_cluster": self.ledger.parent_hub_cluster or "",
            "commitment_left": self.ledger.commitment_left,
            "returning": bool(self.ledger.returning),
        }

    def _suppress_deferred(self, instance_id: str, by_reentry: bool) -> None:
        if not instance_id or instance_id not in self._deferred_unemitted:
            return
        self._deferred_unemitted.discard(instance_id)
        self._horizon_emitted.add(instance_id)
        if by_reentry:
            self._deferred_by_reentry += 1

    def _clear_obligation(self) -> None:
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger._seq_len = 0
        self._open_instance = None

    def _complete_returned_once(self, step, sig, cluster, by_reentry: bool) -> bool:
        instance_id = None if self._open_instance is None else self._open_instance.get("id")
        if instance_id and self._already_terminal(instance_id):
            self._reentry_double += 1
            self._suppress_deferred(instance_id, by_reentry=False)
            self._clear_obligation()
            return False
        self._suppress_deferred(instance_id or "", by_reentry=by_reentry)
        self._complete_branch(step, sig, cluster)
        return True

    def _early_from(self, was_returning, new_state, new_sig, step, sig, graph) -> None:
        if was_returning or new_state is None:
            return
        if not self.ledger.active_branch:
            return
        strength = self._match_parent(new_sig, graph)
        if not strength:
            return
        snap = self._snapshot()
        dest_cluster = self._cluster(new_sig, graph)
        self._emit(
            "early_parent_reentry", step, new_sig or sig, dest_cluster,
            snap["active_branch"],
            {
                "reentry_strength": strength,
                "parent_hub_sig": snap["parent_hub_sig"],
                "parent_hub_cluster": snap["parent_hub_cluster"],
                "destination_sig": new_sig or "",
                "destination_cluster": dest_cluster,
                "source_sig": sig or "",
                "commitment_left": snap["commitment_left"],
                "returning": False,
                "sequence_instance_id": snap["sequence_instance_id"],
                "frontier_count": 0,
            },
        )
        self._complete_returned_once(step, sig, self._cluster(sig, graph), by_reentry=True)

    def _maybe_source_repair(self, action, state, sig, new_sig, graph, step) -> bool:
        del action, state
        if not self.ledger.active_branch or self.ledger.returning:
            return False
        strength = self._match_parent(sig, graph)
        if not strength:
            return False
        snap = self._snapshot()
        cluster = self._cluster(sig, graph)
        self._emit(
            "source_parent_reentry_repair", step, sig, cluster, snap["active_branch"],
            {
                "reentry_strength": strength,
                "parent_hub_sig": snap["parent_hub_sig"],
                "parent_hub_cluster": snap["parent_hub_cluster"],
                "current_hub_sig": sig or "",
                "current_hub_cluster": cluster,
                "commitment_left": snap["commitment_left"],
                "returning": False,
                "sequence_instance_id": snap["sequence_instance_id"],
                "frontier_count": len(self._frontier_keys(cluster)),
            },
        )
        before = self._markers()
        self._complete_returned_once(step, sig, cluster, by_reentry=True)
        self._skip_early = True
        self._reentry_arm = None
        self._last_destination_state = None
        self._resolve_stack(before, sig, new_sig, graph, step)
        return True

    def _emit_lease_action_if_pending(self, action, sig, graph, step) -> None:
        pending = self._pending_lease_action
        if not pending or action is None:
            return
        cluster = self._cluster(sig, graph)
        key = branch_key(cluster, action)
        self._pending_lease_action = None
        if key != pending.get("key"):
            return
        if key in self._leased_keys:
            self._repeated_key_violations += 1
            return
        self._leased_keys.add(key)
        self._mono = {
            "key": key,
            "cluster": cluster,
            "before_keys": set(pending.get("before_keys") or ()),
        }
        lease = self._lease or {}
        self._emit(
            "local_frontier_lease_action", step, sig, cluster, key,
            {
                "hub_sig": pending.get("hub_sig") or sig,
                "hub_cluster": pending.get("cluster") or cluster,
                "chosen_branch_key": key,
                "frontier_count_before": pending.get("frontier_before"),
                "frontier_keys": _json_list(pending.get("before_keys") or ()),
                "outer_sequence_instance_id": lease.get("outer_id"),
                "outer_parent_sig": lease.get("outer_parent_sig") or "",
                "outer_parent_cluster": lease.get("outer_parent_cluster") or "",
                "lease_generation": pending.get("generation"),
                "commitment_left": self.ledger.commitment_left,
                "returning": bool(self.ledger.returning),
                "sequence_instance_id": None if self._open_instance is None else self._open_instance.get("id"),
            },
        )

    def _check_monotonic(self) -> None:
        pending = self._mono
        self._mono = None
        if not pending:
            return
        cluster = pending["cluster"]
        key = pending["key"]
        started = key in self._leased_keys
        hub = self.struct.hubs.get(cluster or "?")
        if hub is not None:
            hist = hub.branches.get(key)
            if hist is not None and hist.attempts > 0:
                started = True
        for rec in self.ledger.hubs.values():
            if (rec.hub_cluster or "") == (cluster or "") and key in rec.started:
                started = True
        if not started:
            return
        after = self._frontier_keys(cluster)
        before = set(pending["before_keys"])
        revealed = after - before
        if len(after) > len(before) - 1 + len(revealed):
            self._mono_violations += 1

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        self._observe_branches(state, sig, graph)
        self._emit_lease_action_if_pending(action, sig, graph, step)
        self._reentry_arm = {
            "was_returning": bool(self.ledger.returning),
            "new_state": new_state,
            "new_sig": new_sig,
        }
        if self._maybe_source_repair(action, state, sig, new_sig, graph, step):
            self._reentry_arm = {
                "was_returning": bool(self.ledger.returning),
                "new_state": new_state,
                "new_sig": new_sig,
            }
            before = self._markers()
            ReturnCycleGuardSequenceController.after(
                self, sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            self._resolve_stack(before, sig, new_sig, graph, step)
            self._check_monotonic()
            return
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._check_monotonic()

    def _resolve_stack(self, before, sig, new_sig, graph, step: int) -> None:
        arm = self._reentry_arm or {}
        self._last_destination_state = arm.get("new_state")
        skip = self._skip_early
        self._skip_early = False
        self._reentry_arm = None
        if not skip:
            self._early_from(
                bool(arm.get("was_returning", True)),
                arm.get("new_state"),
                arm.get("new_sig", new_sig),
                step, sig, graph)
        super()._resolve_stack(before, sig, new_sig, graph, step)

    def _handoff(self, sig, action, state, new_state, relation, findings,
                 new_sig, crashed, graph, step: int) -> None:
        outer_id = None if self._open_instance is None else self._open_instance.get("id")
        if outer_id:
            self._deferred_unemitted.add(outer_id)
        if self._lease and self._lease.get("active"):
            self._lease["active"] = False
        super()._handoff(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)

    def _emit_deferred_once(self, instance_id, step, sig, cluster, branch) -> None:
        if not instance_id or instance_id in self._horizon_emitted:
            return
        if instance_id not in self._deferred_unemitted:
            return
        if self._already_terminal(instance_id):
            self._suppress_deferred(instance_id, by_reentry=False)
            return
        self._deferred_unemitted.discard(instance_id)
        self._horizon_emitted.add(instance_id)
        self._deferred_by_return += 1
        self._emit(
            "sequence_horizon_reached", step, sig, cluster, branch or "",
            {
                "reason": "horizon_handoff_resolved",
                "sequence_instance_id": instance_id,
            },
        )

    def _grant_lease(self, frame, frontier: set, step, sig, graph, dst_cluster) -> None:
        self._lease_generation += 1
        self._lease_chain += 1
        self._max_lease_chain = max(self._max_lease_chain, self._lease_chain)
        outer = frame.open_instance or {}
        keys = _json_list(frontier)
        self._lease = {
            "active": True,
            "hub_cluster": frame.child_parent_cluster or dst_cluster or "",
            "hub_sig": frame.child_parent_sig or sig or "",
            "keys": keys,
            "generation": self._lease_generation,
            "outer_id": outer.get("id"),
            "outer_branch": frame.active_branch or "",
            "outer_parent_sig": frame.parent_hub_sig or "",
            "outer_parent_cluster": frame.parent_hub_cluster or "",
        }
        self.ledger.commitment_left = 1
        self.ledger.returning = False
        cluster = self._lease["hub_cluster"]
        self._emit(
            "local_frontier_lease_granted", step, self._lease["hub_sig"], cluster,
            frame.child_branch or "",
            {
                "hub_sig": self._lease["hub_sig"],
                "hub_cluster": cluster,
                "frontier_keys": keys,
                "frontier_count": len(keys),
                "outer_sequence_instance_id": outer.get("id"),
                "outer_parent_sig": frame.parent_hub_sig or "",
                "outer_parent_cluster": frame.parent_hub_cluster or "",
                "lease_generation": self._lease_generation,
                "commitment_left": 1,
                "returning": False,
                "sequence_instance_id": outer.get("id"),
                "active_branch": frame.active_branch or "",
            },
        )

    def _end_lease(self, event_name: str, step, sig, graph, extra=None) -> None:
        lease = self._lease or {}
        if not lease.get("active"):
            return
        lease["active"] = False
        self._lease_chain = 0
        snap = self._snapshot()
        self.ledger.commitment_left = 0
        self.ledger.returning = True
        cluster = self._cluster(sig, graph)
        payload = {
            "hub_sig": lease.get("hub_sig") or "",
            "hub_cluster": lease.get("hub_cluster") or "",
            "current_hub_sig": sig or "",
            "current_hub_cluster": cluster,
            "frontier_keys": list(lease.get("keys") or []),
            "frontier_count": len(lease.get("keys") or []),
            "outer_sequence_instance_id": lease.get("outer_id"),
            "commitment_left": 0,
            "returning": True,
            "sequence_instance_id": snap["sequence_instance_id"],
            "active_branch": snap["active_branch"],
            "lease_generation": lease.get("generation"),
        }
        if extra:
            payload.update(extra)
        self._emit(event_name, step, sig, cluster, snap["active_branch"], payload)
        self._emit_deferred_once(
            snap["sequence_instance_id"], step, sig, cluster, snap["active_branch"])
        resumed = snap["sequence_instance_id"]
        self._emit(
            "parent_frame_resume_to_return", step, sig, cluster, snap["active_branch"],
            {
                "resumed_sequence_instance_id": resumed,
                "resumed_branch": snap["active_branch"],
                "original_parent_hub_sig": snap["parent_hub_sig"],
                "original_parent_hub_cluster": snap["parent_hub_cluster"],
                "returning": True,
                "commitment_left": 0,
                "stack_depth": len(self._stack),
                "sequence_instance_id": resumed,
                "reason": event_name,
            },
        )

    def _witness_and_resume(self, frame, step, sig, new_sig, graph, strength,
                            context, delta, dst_cluster) -> None:
        if frame.horizon_resolved:
            self._witness_violations += 1
            return
        depth_before = len(self._stack)
        self._stack.pop()
        source_cluster = self._cluster(sig, graph)
        self._emit(
            "child_parent_witness", step, sig, source_cluster, frame.child_branch,
            {
                "child_sequence_instance_id": frame.child_instance_id,
                "child_branch": frame.child_branch,
                "expected_parent_sig": frame.child_parent_sig,
                "expected_parent_cluster": frame.child_parent_cluster,
                "observed_destination_sig": new_sig or "",
                "observed_destination_cluster": dst_cluster,
                "witness_strength": strength,
                "terminal_context": context,
                "return_success_delta": delta,
                "stack_depth_before_pop": depth_before,
                "sequence_instance_id": frame.child_instance_id,
            },
        )
        self._restore_frame(frame)
        frame.horizon_resolved = True
        dest_state = self._last_destination_state
        dest_sig = new_sig or frame.child_parent_sig or ""
        if dest_state is not None and dest_sig:
            self._observe_branches(dest_state, dest_sig, graph)
        hub_cluster = frame.child_parent_cluster or dst_cluster or ""
        frontier = self._frontier_keys(hub_cluster, exclude={frame.child_branch or ""})
        if frontier:
            self._grant_lease(frame, frontier, step, dest_sig or sig, graph, dst_cluster)
            return
        self._lease_chain = 0
        self.ledger.commitment_left = 0
        self.ledger.returning = True
        resumed = None if self._open_instance is None else self._open_instance.get("id")
        self._emit(
            "parent_frame_resume_to_return", step, sig, source_cluster,
            frame.active_branch,
            {
                "resumed_sequence_instance_id": resumed,
                "resumed_branch": frame.active_branch,
                "original_parent_hub_sig": frame.parent_hub_sig,
                "original_parent_hub_cluster": frame.parent_hub_cluster,
                "returning": True,
                "commitment_left": 0,
                "stack_depth": len(self._stack),
                "sequence_instance_id": resumed,
            },
        )
        if frame.deferred_horizon:
            self._emit_deferred_once(
                resumed, step, sig, source_cluster, frame.active_branch)

    def _select_lease(self, actions, state, graph, ctx, sig):
        lease = self._lease or {}
        if not lease.get("active"):
            return None
        cluster = self._cluster(sig, graph)
        step = -1 if not ctx else ctx.get("step_index", -1)
        if cluster != (lease.get("hub_cluster") or ""):
            self._end_lease("local_frontier_lease_location_lost", step, sig, graph)
            return None
        allowed = set(lease.get("keys") or [])
        visible = []
        for action in actions or []:
            if not is_branch_click(action, state):
                continue
            key = branch_key(cluster, action)
            if key not in allowed:
                continue
            if key in self._leased_keys or key not in self._frontier_keys(cluster):
                if key in self._leased_keys:
                    self._repeated_key_violations += 1
                continue
            visible.append((action, key))
        untried = [key for key in allowed if key in self._frontier_keys(cluster)]
        if visible:
            action, key = visible[0]
            before_keys = self._frontier_keys(cluster)
            self.last_label = "local_frontier_lease"
            self._pending_lease_action = {
                "key": key,
                "generation": lease.get("generation"),
                "frontier_before": len(before_keys),
                "before_keys": set(before_keys),
                "cluster": cluster,
                "hub_sig": sig,
            }
            return action
        if untried:
            self._end_lease(
                "local_frontier_lease_exhausted_or_hidden", step, sig, graph)
        else:
            self._end_lease("local_frontier_lease_exhausted", step, sig, graph)
        return None

    def _return_action(self, actions, state):
        for action in actions or []:
            if is_return_action(action, state):
                self.last_label = "return_hub"
                return action
        return None

    def pick_override(self, actions, state, graph, ctx):
        sig = "" if not ctx else (ctx.get("sig") or "")
        self._observe_branches(state, sig, graph)
        if self._lease and self._lease.get("active"):
            chosen = self._select_lease(actions, state, graph, ctx, sig)
            if chosen is not None:
                return chosen
            if self.ledger.returning:
                back = self._return_action(actions, state)
                if back is not None:
                    return back
        return super().pick_override(actions, state, graph, ctx)

    def label_for(self, action, state) -> str:
        if self.last_label == "local_frontier_lease":
            return self.last_label
        return super().label_for(action, state)

    def _unwind(self, step: int, sig, graph, reason: str) -> None:
        if self._lease is not None:
            self._lease["active"] = False
        self._lease_chain = 0
        self._pending_lease_action = None
        self._mono = None
        ids = []
        if self._open_instance is not None and self._open_instance.get("id"):
            ids.append(self._open_instance.get("id"))
        for frame in self._stack:
            inst = frame.open_instance or {}
            if inst.get("id"):
                ids.append(inst.get("id"))
        super()._unwind(step, sig, graph, reason)
        for instance_id in ids:
            self._deferred_unemitted.discard(instance_id)
            self._horizon_emitted.add(instance_id)

    def close_open(self, step: int = -1, sig: str = "", cluster: str = ""):
        if self._budget_end_seen:
            return
        lease = self._lease or {}
        self._lease_active_at_end = bool(lease.get("active"))
        self._lease_remaining_at_end = (
            len(self._frontier_keys(lease.get("hub_cluster") or ""))
            if self._lease_active_at_end else 0
        )
        self._budget_end_seen = True
        super().close_open(step, sig, cluster)

    def metrics(self) -> dict:
        out = super().metrics()
        events = self.events

        def named(event_name: str) -> list:
            return [event for event in events if event.get("event") == event_name]

        early = named("early_parent_reentry")
        actions = named("local_frontier_lease_action")
        out["early_parent_reentry_events"] = len(early)
        out["early_parent_reentry_exact"] = sum(
            1 for event in early if event.get("reentry_strength") == "exact")
        out["early_parent_reentry_cluster"] = sum(
            1 for event in early if event.get("reentry_strength") == "cluster")
        out["source_parent_reentry_repair_events"] = len(
            named("source_parent_reentry_repair"))
        out["reentry_double_completion_violations"] = self._reentry_double
        out["local_frontier_lease_granted_events"] = len(
            named("local_frontier_lease_granted"))
        out["local_frontier_lease_action_events"] = len(actions)
        out["local_frontier_lease_exhausted_events"] = len(
            named("local_frontier_lease_exhausted"))
        out["local_frontier_lease_hidden_events"] = len(
            named("local_frontier_lease_exhausted_or_hidden"))
        out["local_frontier_lease_location_lost_events"] = len(
            named("local_frontier_lease_location_lost"))
        out["unique_frontier_branch_keys_leased"] = len({
            event.get("chosen_branch_key") for event in actions
            if event.get("chosen_branch_key")
        })
        out["frontier_repeated_key_violations"] = self._repeated_key_violations
        out["max_frontier_lease_chain"] = self._max_lease_chain
        out["frontier_new_keys_from_variant"] = self._frontier_new_keys_from_variant
        out["frontier_monotonicity_violations"] = self._mono_violations
        out["deferred_horizon_resolved_by_return"] = self._deferred_by_return
        out["deferred_horizon_resolved_by_reentry"] = self._deferred_by_reentry
        out["lease_cross_hub_uncancelled"] = self._lease_cross_hub
        out["frontier_lease_active_at_budget_end"] = bool(self._lease_active_at_end)
        out["frontier_lease_remaining_keys_at_budget_end"] = int(
            self._lease_remaining_at_end)
        return out


class ReentryFrontierGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-reentry-frontier-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ReentryFrontierSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "ReentryFrontierGuardGhostPolicy",
    "ReentryFrontierSequenceController",
]
