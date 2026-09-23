"""Experimental local action drain before the structural frontier (v0.3.17).

Research-only. Not the product default. The v0.3.16 controller is reused by
subclassing; its module is not modified.

After a valid child-parent witness, visible eligible button clicks at that
hub are probed once before the suspended outer is restored. A probe that
stays on the hub is not a sequence action. A probe that leaves the hub is
promoted into a real child. Structural frontier lease runs only after the
local button frontier is empty.
"""
from __future__ import annotations

from ..state.models import Action
from ..state.similarity import NEW, SIMILAR
from .horizon_handoff_guard import terminal_violations
from .interaction import DISTRACTOR_KEYWORDS
from .policy import GhostPolicy
from .reentry_frontier_guard import ReentryFrontierSequenceController
from .sequence import (
    BRANCH_HORIZON, CONTEXT_MODES, SEQUENCE_LIKE, _blob, _finding_fps,
    branch_key, is_return_action,
)


def _json_list(values) -> list:
    return sorted(str(item) for item in values)


class LocalActionDrainSequenceController(ReentryFrontierSequenceController):
    """v0.3.16 re-entry and lease, with a local button drain in front."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_drain_state()

    def _reset_drain_state(self) -> None:
        self._drain = None
        self._pending_probe = None
        self._drained_by_cluster = {}
        self._revealed_keys = set()
        self._variant_revisits = 0
        self._repeat_violations = 0
        self._cross_hub_violations = 0
        self._accounting_violations = 0
        self._max_actions_per_drain = 0
        self._drain_epochs = 0

    def reset(self):
        super().reset()
        self._reset_drain_state()

    def _local_key(self, cluster: str, eid: str) -> str:
        return f"{cluster or '?'}:button:{eid or ''}"

    def _promoted_key(self, cluster: str, eid: str) -> str:
        return f"{cluster or '?'}:local-button:{eid or ''}"

    def _is_distractor(self, action, state) -> bool:
        blob = _blob(action, state)
        return any(keyword.lower() in blob for keyword in DISTRACTOR_KEYWORDS)

    def _eligible_buttons(self, state, cluster: str) -> list:
        if state is None:
            return []
        drained = self._drained_by_cluster.get(cluster or "", set())
        found = []
        for element in getattr(state, "elements", ()) or ():
            if not getattr(element, "enabled", True):
                continue
            if (getattr(element, "kind", "click") or "click") != "click":
                continue
            if (getattr(element, "role", "") or "").strip().lower() != "button":
                continue
            action = Action("click", element.eid)
            if is_return_action(action, state):
                continue
            if self._is_distractor(action, state):
                continue
            key = self._local_key(cluster, element.eid)
            if key in drained:
                continue
            found.append((element, action, key))
        return found

    def _drained_click_keys(self, cluster: str) -> set:
        blocked = set()
        for key in self._drained_by_cluster.get(cluster or "", ()):
            prefix = f"{cluster or '?'}:button:"
            if not str(key).startswith(prefix):
                continue
            eid = str(key)[len(prefix):]
            blocked.add(branch_key(cluster, Action("click", eid)))
        return blocked

    def _frontier_keys(self, cluster: str, exclude=()) -> set:
        keys = super()._frontier_keys(cluster, exclude)
        blocked = self._drained_click_keys(cluster)
        if not blocked:
            return keys
        return {key for key in keys if key not in blocked}

    def _mark_drained(self, cluster: str, key: str) -> None:
        bucket = self._drained_by_cluster.setdefault(cluster or "", set())
        if key in bucket:
            self._repeat_violations += 1
            return
        bucket.add(key)

    def _holding(self) -> bool:
        drain = self._drain or {}
        return bool(drain.get("active")) and not drain.get("paused")

    def _note_epoch(self, count: int) -> None:
        if count > self._max_actions_per_drain:
            self._max_actions_per_drain = count

    def _accounting(self) -> tuple:
        starts = sum(1 for event in self.events if event.get("event") == "branch_start")
        terminals = sum(
            1 for event in self.events if event.get("event") == "sequence_terminal")
        return (
            self.ledger.sequences_started,
            self.ledger.sequences_completed,
            self.ledger.return_success,
            self.ledger.active_branch,
            self.ledger.commitment_left,
            starts,
            terminals,
        )

    def _check_accounting(self, before: tuple) -> None:
        if self._accounting() != before:
            self._accounting_violations += 1

    def _note_revealed(self, state, cluster: str) -> list:
        drain = self._drain or {}
        current = [item[2] for item in self._eligible_buttons(state, cluster)]
        known = set(drain.get("seen_keys") or ())
        fresh = [key for key in current if key not in known]
        for key in fresh:
            self._revealed_keys.add(key)
            eid = key.split(":button:", 1)[-1]
            self._emit(
                "local_action_new_key_revealed", drain.get("step", -1),
                drain.get("current_sig") or "", cluster, key,
                {
                    "key": key,
                    "eid": eid,
                    "hub_cluster": cluster,
                    "sequence_instance_id": None,
                },
            )
        drain["visible_keys"] = list(current)
        drain["seen_keys"] = list(known | set(current))
        return fresh

    def _witness_and_resume(self, frame, step, sig, new_sig, graph, strength,
                            context, delta, dst_cluster) -> None:
        if frame.horizon_resolved:
            self._witness_violations += 1
            return
        if self._drain and self._drain.get("active"):
            super()._witness_and_resume(
                frame, step, sig, new_sig, graph, strength,
                context, delta, dst_cluster)
            return
        hub_cluster = frame.child_parent_cluster or dst_cluster or ""
        buttons = self._eligible_buttons(self._last_destination_state, hub_cluster)
        if not buttons:
            super()._witness_and_resume(
                frame, step, sig, new_sig, graph, strength,
                context, delta, dst_cluster)
            return
        self._hold_for_drain(
            frame, step, sig, new_sig, graph, strength, context, delta, dst_cluster)

    def _hold_for_drain(self, frame, step, sig, new_sig, graph, strength,
                        context, delta, dst_cluster) -> None:
        depth_before = len(self._stack)
        if self._stack and self._stack[-1] is frame:
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
        frame.horizon_resolved = True
        dest_state = self._last_destination_state
        dest_sig = new_sig or frame.child_parent_sig or ""
        hub_cluster = frame.child_parent_cluster or dst_cluster or ""
        if dest_state is not None and dest_sig:
            self._observe_branches(dest_state, dest_sig, graph)
        buttons = self._eligible_buttons(dest_state, hub_cluster)
        keys = [item[2] for item in buttons]
        outer = frame.open_instance or {}
        self._drain_epochs += 1
        self._drain = {
            "active": True,
            "paused": False,
            "frame": frame,
            "hub_cluster": hub_cluster,
            "hub_sig": frame.child_parent_sig or dest_sig,
            "current_sig": dest_sig,
            "current_state": dest_state,
            "epoch_keys": [],
            "visible_keys": list(keys),
            "seen_keys": list(keys),
            "step": step,
            "promoted_child_id": "",
            "promoted_branch": "",
            "promoted_button_key": "",
            "child_parent_sig": frame.child_parent_sig or "",
            "child_parent_cluster": hub_cluster,
            "promoted_since": 0,
        }
        self._emit(
            "local_action_drain_started", step, self._drain["hub_sig"], hub_cluster, "",
            {
                "hub_sig": self._drain["hub_sig"],
                "hub_cluster": hub_cluster,
                "suspended_outer_id": outer.get("id"),
                "suspended_branch": frame.active_branch or "",
                "visible_eligible_keys": list(keys),
                "stack_depth": len(self._stack),
                "sequence_instance_id": None,
            },
        )

    def _select_local(self, actions, state, graph, ctx, sig):
        drain = self._drain or {}
        step = -1 if not ctx else ctx.get("step_index", -1)
        observed = self._cluster(sig, graph) if sig else ""
        hub_cluster = drain.get("hub_cluster") or ""
        if observed and observed != hub_cluster:
            self._cross_hub_violations += 1
            self._abort(step, sig, graph, "cross_hub")
            return None
        buttons = self._eligible_buttons(state, hub_cluster)
        if not buttons:
            self._enter_structural(step, sig, graph)
            return None
        element, action, key = buttons[0]
        if key in self._drained_by_cluster.get(hub_cluster, set()):
            self._repeat_violations += 1
            return None
        outer = (drain.get("frame").open_instance or {}) if drain.get("frame") else {}
        self.last_label = "local_action_drain"
        self._pending_probe = {
            "key": key,
            "eid": element.eid,
            "role": element.role,
            "hub_cluster": hub_cluster,
            "frontier_before": len(buttons),
        }
        self._emit(
            "local_action_probe_selected", step, sig or drain.get("hub_sig") or "",
            hub_cluster, key,
            {
                "key": key,
                "eid": element.eid,
                "role": element.role,
                "hub_cluster": hub_cluster,
                "frontier_count": len(buttons),
                "outer_suspended_id": outer.get("id"),
                "stack_depth": len(self._stack),
                "sequence_instance_id": None,
            },
        )
        for candidate in actions or []:
            if getattr(candidate, "type", "") == "click" and candidate.target_eid == element.eid:
                return candidate
        return action

    def pick_override(self, actions, state, graph, ctx):
        sig = "" if not ctx else (ctx.get("sig") or "")
        self._observe_branches(state, sig, graph)
        if self._holding():
            chosen = self._select_local(actions, state, graph, ctx, sig)
            if chosen is not None:
                return chosen
        return super().pick_override(actions, state, graph, ctx)

    def label_for(self, action, state) -> str:
        if self.last_label == "local_action_drain":
            return self.last_label
        return super().label_for(action, state)

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if self._pending_probe is not None:
            probe = self._pending_probe
            self._pending_probe = None
            self._finish_probe(
                probe, sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
            return
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._maybe_resume(sig, new_state, new_sig, graph, step, bool(crashed))

    def _finish_probe(self, probe, sig, action, state, new_state, relation,
                      findings, new_sig, crashed, graph, step) -> None:
        drain = self._drain or {}
        hub_cluster = probe.get("hub_cluster") or drain.get("hub_cluster") or ""
        if crashed or new_state is None and crashed:
            self._emit(
                "local_action_probe_crash", step, sig, hub_cluster, probe.get("key") or "",
                {
                    "key": probe.get("key"),
                    "eid": probe.get("eid"),
                    "hub_cluster": hub_cluster,
                    "sequence_instance_id": None,
                },
            )
            self._abort(step, sig, graph, "crash")
            return
        source_cluster = self._cluster(sig, graph)
        if source_cluster and hub_cluster and source_cluster != hub_cluster:
            self._cross_hub_violations += 1
            self._abort(step, sig, graph, "cross_hub")
            return
        dst_cluster = ""
        if new_state is not None and new_sig:
            dst_cluster = self._cluster(new_sig, graph)
        if new_state is not None and dst_cluster == hub_cluster and hub_cluster:
            self._complete_same_hub(
                probe, sig, action, state, new_state, relation, findings,
                new_sig, graph, step, source_cluster, dst_cluster)
            return
        self._promote(
            probe, sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)

    def _complete_same_hub(self, probe, sig, action, state, new_state, relation,
                           findings, new_sig, graph, step, source_cluster,
                           dst_cluster) -> None:
        del relation
        drain = self._drain
        if not drain:
            return
        before = self._accounting()
        key = probe.get("key") or ""
        self._mark_drained(drain["hub_cluster"], key)
        drain["epoch_keys"].append(key)
        self._note_epoch(len(drain["epoch_keys"]))
        if new_sig and drain.get("hub_sig") and new_sig != drain.get("hub_sig"):
            self._variant_revisits += 1
        drain["step"] = step
        drain["current_sig"] = new_sig or drain.get("current_sig")
        drain["current_state"] = new_state
        self._observe_branches(new_state, new_sig, graph)
        try:
            self._record_mutation(sig, action, state, new_state, NEW, step)
        except Exception:
            pass
        revealed = self._note_revealed(new_state, drain["hub_cluster"])
        fingerprints, asserts = _public_findings(findings)
        self._emit(
            "local_action_probe_completed", step, sig, source_cluster, key,
            {
                "source_sig": sig,
                "source_cluster": source_cluster,
                "destination_sig": new_sig or "",
                "destination_cluster": dst_cluster,
                "key": key,
                "finding_count": len(findings or []),
                "newly_revealed_keys": list(revealed),
                "sequence_instance_id": None,
            },
        )
        if findings:
            payload = {
                "key": key,
                "finding_count": len(findings or []),
                "hub_cluster": drain["hub_cluster"],
                "sequence_instance_id": None,
            }
            if fingerprints:
                payload["fingerprints"] = fingerprints
            if asserts:
                payload["assert_ids"] = asserts
            self._emit(
                "local_action_probe_finding", step, sig, source_cluster, key, payload)
        self._check_accounting(before)
        if not self._eligible_buttons(new_state, drain["hub_cluster"]):
            self._enter_structural(step, new_sig or sig, graph)

    def _promote(self, probe, sig, action, state, new_state, relation, findings,
                 new_sig, crashed, graph, step) -> None:
        drain = self._drain
        if not drain:
            return
        before_events = len(self.events)
        self.last_label = "branch"
        ReentryFrontierSequenceController.after(
            self, sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        if not any(
            event.get("event") == "branch_start"
            for event in self.events[before_events:]
        ):
            self._force_branch_start(
                sig, action, state, new_state, relation, findings,
                new_sig, crashed, graph, step)
        child_id = ""
        child_branch = self.ledger.active_branch or ""
        for event in self.events[before_events:]:
            if event.get("event") != "branch_start":
                continue
            child_id = event.get("sequence_instance_id") or child_id
            child_branch = event.get("branch_key") or child_branch
        if not child_id and self._open_instance is not None:
            child_id = self._open_instance.get("id") or ""
        hub_cluster = drain["hub_cluster"]
        promoted = self._promoted_key(hub_cluster, probe.get("eid") or "")
        outer = (drain["frame"].open_instance or {}) if drain.get("frame") else {}
        dst_cluster = self._cluster(new_sig, graph) if new_sig else ""
        self._emit(
            "local_action_promoted_to_child", step, sig, hub_cluster, promoted,
            {
                "source_hub_sig": sig or drain.get("hub_sig") or "",
                "source_hub_cluster": hub_cluster,
                "destination_hub_sig": new_sig or "",
                "destination_hub_cluster": dst_cluster,
                "button_key": probe.get("key") or "",
                "promoted_child_id": child_id,
                "promoted_child_branch": promoted,
                "historical_branch": child_branch,
                "child_parent_sig": self.ledger.parent_hub_sig or drain.get("hub_sig") or "",
                "child_parent_cluster": self.ledger.parent_hub_cluster or hub_cluster,
                "child_commitment_after_first_action": self.ledger.commitment_left,
                "outer_suspended_id": outer.get("id"),
                "sequence_instance_id": child_id or None,
            },
        )
        drain["paused"] = True
        drain["promoted_child_id"] = child_id
        drain["promoted_branch"] = child_branch
        drain["promoted_button_key"] = probe.get("key") or ""
        drain["child_parent_sig"] = self.ledger.parent_hub_sig or drain.get("hub_sig") or ""
        drain["child_parent_cluster"] = self.ledger.parent_hub_cluster or hub_cluster
        drain["promoted_since"] = before_events
        self._maybe_resume(sig, new_state, new_sig, graph, step, bool(crashed))

    def _force_branch_start(self, sig, action, state, new_state, relation,
                            findings, new_sig, crashed, graph, step) -> None:
        del state, new_sig
        cluster = self._cluster(sig, graph)
        key = branch_key(cluster, action)
        if self._open_instance is not None:
            self._emit(
                "sequence_terminal", step, sig, cluster,
                self._open_instance.get("branch", ""),
                {"outcome": "lost_parent", "length": self._open_instance.get("len", 0)})
        rec = self.ledger.hub(sig, cluster)
        rec.discovered.add(key)
        self._emit("branch_discovered", step, sig, cluster, key)
        if key in rec.started:
            self.ledger.repeats += 1
        else:
            rec.started.add(key)
            self.ledger.started_total += 1
            self.ledger.sequences_started += 1
        self._instance_n += 1
        self._open_instance = {
            "id": f"seq-{self._instance_n:04d}",
            "branch": key,
            "len": 1,
        }
        self._emit("branch_start", step, sig, cluster, key)
        self.ledger.active_branch = key
        self.ledger.parent_hub_sig = sig
        self.ledger.parent_hub_cluster = cluster
        self.ledger.branch_actions = 0
        self.ledger.branch_new_states = 0
        self.ledger.branch_findings = 0
        self.ledger._seq_len = 1
        self.ledger.commitment_left = BRANCH_HORIZON if self.mode in SEQUENCE_LIKE else 0
        self.ledger.returning = False
        if self.mode in CONTEXT_MODES:
            self._on_struct_branch_start(cluster, sig, key, step)
        self._emit(
            "sequence_action", step, sig, cluster, key,
            {"action_key": action.key() if action is not None else "",
             "decision_mode": self.last_label},
        )
        self.ledger.branch_actions += 1
        self.ledger._seq_len += 1
        if self.ledger.commitment_left > 0:
            self.ledger.commitment_left -= 1
        if relation in (NEW, SIMILAR):
            self.ledger.branch_new_states += 1
        if findings:
            self.ledger.branch_findings += 1
        if crashed or (findings and self.mode in SEQUENCE_LIKE):
            self.ledger.returning = True
            self.ledger.commitment_left = 0
            outcome = "crash" if crashed else "finding"
            self._emit(
                "sequence_terminal", step, sig, cluster, key,
                {"outcome": outcome, "fingerprints": _finding_fps(findings)})
            self._open_instance = None

    def _child_terminal(self, child_id: str) -> dict | None:
        if not child_id:
            return None
        found = None
        for event in self.events:
            if event.get("event") != "sequence_terminal":
                continue
            if event.get("sequence_instance_id") == child_id:
                found = event
        return found

    def _promoted_escaped(self, child_id: str, since: int) -> bool:
        for event in self.events[since:]:
            if event.get("event") == "return_cycle_escape":
                return True
            if (event.get("event") == "sequence_terminal"
                    and event.get("outcome") == "return_cycle_abandoned"
                    and event.get("sequence_instance_id") == child_id):
                return True
        return False

    def _maybe_resume(self, sig, new_state, new_sig, graph, step, crashed) -> None:
        drain = self._drain
        if not drain or not drain.get("paused"):
            return
        child_id = drain.get("promoted_child_id") or ""
        since = int(drain.get("promoted_since") or 0)
        if self._promoted_escaped(child_id, since):
            self._unwind(step, sig, graph, "promoted_child_return_cycle_escape")
            return
        if crashed:
            self._abort(step, sig, graph, "crash")
            return
        if self._stack:
            return
        child_still_open = (
            self._open_instance is not None and self._open_instance.get("id") == child_id
        ) or (
            self.ledger.active_branch and self.ledger.active_branch == drain.get("promoted_branch")
        )
        if self._lease and self._lease.get("active") and child_still_open:
            return
        if child_still_open:
            return
        if self._lease and self._lease.get("active") and not child_still_open:
            self._lease["active"] = False
            self._lease_chain = 0
        if self.ledger.active_branch and self.ledger.active_branch == drain.get("promoted_branch"):
            return
        if self._child_terminal(child_id) is None and self.ledger.active_branch:
            return
        if self._child_terminal(child_id) is None and self.ledger.return_success <= 0:
            return
        if self.ledger.active_branch:
            return
        parent_sig = drain.get("child_parent_sig") or ""
        parent_cluster = drain.get("child_parent_cluster") or ""
        dst_cluster = self._cluster(new_sig, graph) if new_state is not None and new_sig else ""
        exact = bool(parent_sig) and new_sig == parent_sig
        clustered = bool(dst_cluster) and dst_cluster == parent_cluster
        if not exact and not clustered:
            return
        if self._child_terminal(child_id) is None:
            return
        self._resume_drain(
            step, sig, new_sig, new_state, graph, "exact" if exact else "cluster")

    def _resume_drain(self, step, sig, new_sig, new_state, graph, strength) -> None:
        drain = self._drain
        if not drain:
            return
        key = drain.get("promoted_button_key") or ""
        cluster = drain.get("hub_cluster") or ""
        self._mark_drained(cluster, key)
        if key:
            drain["epoch_keys"].append(key)
            self._note_epoch(len(drain["epoch_keys"]))
        if strength == "cluster":
            self._variant_revisits += 1
        self._emit(
            "local_action_promoted_child_witness", step, new_sig or sig, cluster, key,
            {
                "button_key": key,
                "promoted_child_id": drain.get("promoted_child_id") or "",
                "witness_strength": strength,
                "destination_sig": new_sig or "",
                "destination_cluster": self._cluster(new_sig, graph) if new_sig else "",
                "hub_cluster": cluster,
                "hub_sig": drain.get("hub_sig") or "",
                "sequence_instance_id": drain.get("promoted_child_id") or None,
            },
        )
        drain["paused"] = False
        drain["promoted_child_id"] = ""
        drain["promoted_branch"] = ""
        drain["current_sig"] = new_sig or drain.get("current_sig")
        drain["current_state"] = new_state
        drain["step"] = step
        if new_state is not None:
            self._observe_branches(new_state, new_sig or "", graph)
            self._note_revealed(new_state, cluster)
        if not self._eligible_buttons(new_state, cluster):
            self._enter_structural(step, new_sig or sig, graph)

    def _enter_structural(self, step, sig, graph) -> None:
        drain = self._drain
        if not drain or not drain.get("active") or drain.get("paused"):
            return
        frame = drain["frame"]
        hub_cluster = drain.get("hub_cluster") or ""
        dest_sig = drain.get("current_sig") or sig or frame.child_parent_sig or ""
        dest_state = drain.get("current_state")
        if dest_state is not None and dest_sig:
            self._observe_branches(dest_state, dest_sig, graph)
        frontier = self._frontier_keys(hub_cluster, exclude={frame.child_branch or ""})
        phase = "structural_lease" if frontier else "outer_return"
        drained = list(drain.get("epoch_keys") or [])
        self._note_epoch(len(drained))
        self._emit(
            "local_action_drain_exhausted", step, dest_sig, hub_cluster, "",
            {
                "drained_keys": drained,
                "remaining_structural_frontier_count": len(frontier),
                "next_phase": phase,
                "sequence_instance_id": None,
            },
        )
        self._drain = None
        self._pending_probe = None
        self._restore_frame(frame)
        if frontier:
            self._grant_lease(frame, frontier, step, dest_sig or sig, graph, hub_cluster)
            return
        self._lease_chain = 0
        self.ledger.commitment_left = 0
        self.ledger.returning = True
        resumed = None if self._open_instance is None else self._open_instance.get("id")
        source_cluster = self._cluster(sig, graph) if sig else hub_cluster
        self._emit(
            "parent_frame_resume_to_return", step, sig or dest_sig, source_cluster,
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
                resumed, step, sig or dest_sig, source_cluster, frame.active_branch)

    def _abort(self, step, sig, graph, reason: str) -> None:
        cluster = self._cluster(sig, graph) if sig else ""
        self._emit(
            "local_action_drain_abort", step, sig, cluster, "",
            {"reason": reason, "sequence_instance_id": None},
        )
        self._unwind(step, sig, graph, reason)

    def _stack_has(self, frame) -> bool:
        return any(item is frame for item in self._stack)

    def _unwind(self, step: int, sig, graph, reason: str) -> None:
        drain = self._drain
        self._pending_probe = None
        if drain and drain.get("frame") is not None and not self._stack_has(drain["frame"]):
            self._stack.append(drain["frame"])
        promoted = bool(drain and drain.get("paused") and drain.get("promoted_child_id"))
        self._drain = None
        super()._unwind(step, sig, graph, reason)
        if not drain:
            return
        cluster = self._cluster(sig, graph) if sig else ""
        if promoted or "escape" in (reason or ""):
            self._emit(
                "local_action_promoted_child_unwind", step, sig, cluster, "",
                {
                    "reason": reason,
                    "promoted_child_id": drain.get("promoted_child_id") or "",
                    "button_key": drain.get("promoted_button_key") or "",
                    "stack_depth": len(self._stack),
                    "sequence_instance_id": drain.get("promoted_child_id") or None,
                },
            )

    def close_open(self, step: int = -1, sig: str = "", cluster: str = ""):
        drain = self._drain
        if drain and drain.get("frame") is not None and not self._stack_has(drain["frame"]):
            outer = drain["frame"].open_instance or {}
            if not outer.get("id") or not self._already_terminal(outer.get("id")):
                self._stack.append(drain["frame"])
        self._drain = None
        self._pending_probe = None
        super().close_open(step, sig, cluster)

    def metrics(self) -> dict:
        out = super().metrics()
        events = self.events

        def named(event_name: str) -> list:
            return [event for event in events if event.get("event") == event_name]

        drained = {
            key
            for keys in self._drained_by_cluster.values()
            for key in keys
        }
        out["local_action_drain_started_events"] = len(named("local_action_drain_started"))
        out["local_action_drain_exhausted_events"] = len(named("local_action_drain_exhausted"))
        out["local_action_drain_abort_events"] = len(named("local_action_drain_abort"))
        out["local_action_drain_epochs"] = self._drain_epochs
        out["max_local_actions_per_drain"] = self._max_actions_per_drain
        out["local_action_keys_drained"] = len(drained)
        out["local_action_probe_selected_events"] = len(named("local_action_probe_selected"))
        out["local_action_probe_completed_events"] = len(named("local_action_probe_completed"))
        out["local_action_probe_finding_events"] = len(named("local_action_probe_finding"))
        out["local_action_probe_crash_events"] = len(named("local_action_probe_crash"))
        out["same_hub_local_action_events"] = len(named("local_action_probe_completed"))
        out["local_action_new_key_revealed_events"] = len(
            named("local_action_new_key_revealed"))
        out["newly_revealed_local_action_keys"] = len(self._revealed_keys)
        out["local_action_variant_revisits"] = self._variant_revisits
        out["local_action_promoted_to_child_events"] = len(
            named("local_action_promoted_to_child"))
        out["local_action_promoted_child_witness_events"] = len(
            named("local_action_promoted_child_witness"))
        out["local_action_promoted_child_unwind_events"] = len(
            named("local_action_promoted_child_unwind"))
        out["repeated_local_action_key_violations"] = self._repeat_violations
        out["cross_hub_drain_violations"] = self._cross_hub_violations
        out["local_action_sequence_accounting_violations"] = self._accounting_violations
        out["terminal_accounting_violations"] = len(terminal_violations(events))
        return out


def _public_findings(findings) -> tuple:
    fingerprints = _finding_fps(findings)
    asserts = []
    for finding in findings or []:
        evidence = getattr(finding, "evidence", None)
        if isinstance(evidence, dict) and evidence.get("assert_id"):
            asserts.append(str(evidence["assert_id"]))
        elif isinstance(finding, dict):
            if finding.get("assert_id"):
                asserts.append(str(finding["assert_id"]))
            nested = finding.get("evidence") or {}
            if isinstance(nested, dict) and nested.get("assert_id"):
                asserts.append(str(nested["assert_id"]))
    return fingerprints, asserts


class LocalActionDrainGuardGhostPolicy(GhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-local-action-drain-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = LocalActionDrainSequenceController("structural")
        self.sequence_mode = "structural"


__all__ = [
    "LocalActionDrainGuardGhostPolicy",
    "LocalActionDrainSequenceController",
]
