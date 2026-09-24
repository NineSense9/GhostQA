"""Experimental residual-frontier debt escape (v0.3.23).

Research-only. Not the product default. The v0.3.21 controller is reused by
subclassing; its module is not modified.

A waypoint escape records a debt. Later, when no sequence lifecycle is active
and the current observed SCC is closed and interaction-exhausted, the oldest
usable debt is restored with the existing reset-plus-replay contract. Replay
does not choose the next action and does not consume debt tokens.
"""
from __future__ import annotations

from .planner import pending_opportunity_counts
from .return_waypoint_frontier_guard import (
    ReturnWaypointFrontierGuardGhostPolicy,
    ReturnWaypointFrontierSequenceController,
)

CLICK_KINDS = ("button", "click")
_METRIC_KEYS = (
    "residual_frontier_debts_created",
    "residual_frontier_debts_resolved",
    "residual_frontier_debts_unresolved",
    "residual_frontier_tokens_created",
    "residual_frontier_tokens_consumed",
    "residual_frontier_debt_relocations",
    "residual_frontier_relocation_failures",
    "residual_frontier_gate_checks",
    "residual_frontier_closed_scc_checks",
    "residual_frontier_exhausted_scc_checks",
    "residual_frontier_active_sequence_suppressed",
    "residual_frontier_open_scc_suppressed",
    "residual_frontier_pending_scc_suppressed",
    "residual_frontier_inside_scc_suppressed",
    "residual_frontier_no_path_suppressed",
    "residual_frontier_budget_suppressed",
    "residual_frontier_zero_normal_action_suppressed",
    "residual_frontier_false_success_violations",
    "residual_frontier_restore_sequence_violations",
    "residual_frontier_consumption_violations",
    "residual_frontier_target_identity_violations",
)


def normalize_residual_tokens(local_keys, structural_keys, waypoint_cluster: str = "") -> list:
    """Collapse button/click duplicates to cluster:role:eid."""
    seen = set()
    tokens = []
    for raw in list(local_keys or []) + list(structural_keys or []):
        parts = str(raw or "").split(":")
        if len(parts) < 3:
            continue
        cluster, kind, eid = parts[0], parts[1], ":".join(parts[2:])
        if not cluster or not kind or not eid:
            continue
        if waypoint_cluster and cluster != waypoint_cluster:
            continue
        role = "click" if kind in CLICK_KINDS else kind
        identity = (cluster, role, eid)
        if identity in seen:
            continue
        seen.add(identity)
        tokens.append(f"{cluster}:{role}:{eid}")
    return tokens


def _tarjan(nodes: list, adjacency: dict) -> list:
    index = {}
    low = {}
    stack = []
    on_stack = set()
    components = []
    counter = [0]

    def strong(node: str) -> None:
        index[node] = counter[0]
        low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        for nxt in adjacency.get(node, ()):
            if nxt not in index:
                strong(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], index[nxt])
        if low[node] == index[node]:
            component = []
            while True:
                item = stack.pop()
                on_stack.remove(item)
                component.append(item)
                if item == node:
                    break
            components.append(component)

    for node in nodes:
        if node not in index:
            strong(node)
    return components


def observed_scc(graph, current_sig: str):
    """SCC of the current signature on the runtime graph.

    Edges need a stored action. Edges into CRASHED are ignored. Returns None
    when the current signature is absent.
    """
    nodes_map = getattr(graph, "nodes", None) or {}
    if not current_sig or current_sig == "CRASHED" or current_sig not in nodes_map:
        return None
    node_ids = [sig for sig in nodes_map if sig and sig != "CRASHED"]
    adjacency = {sig: [] for sig in node_ids}
    usable = []
    for edge in getattr(graph, "edges", {}).values():
        if getattr(edge, "action", None) is None:
            continue
        src = getattr(edge, "src", "")
        dst = getattr(edge, "dst", "")
        if src == "CRASHED" or dst == "CRASHED":
            continue
        if src not in adjacency:
            continue
        usable.append(edge)
        if dst in adjacency and dst not in adjacency[src]:
            adjacency[src].append(dst)
    components = _tarjan(node_ids, adjacency)
    component = next((item for item in components if current_sig in item), None)
    if component is None:
        return None
    members = set(component)
    outgoing = 0
    for edge in usable:
        dst = edge.dst
        if edge.src in members and dst not in members and dst != "CRASHED":
            outgoing += 1
    return {
        "sigs": list(component),
        "members": members,
        "size": len(component),
        "closed": outgoing == 0,
        "outgoing": outgoing,
    }


def component_pending(graph, sigs, payload_policy=None) -> int:
    total = 0
    for sig in sigs:
        counts = pending_opportunity_counts(graph, sig, payload_policy)
        total += (
            int(counts.get("progress") or 0)
            + int(counts.get("clicks") or 0)
            + int(counts.get("inputs") or 0)
            + int(counts.get("deferred") or 0)
        )
    return total


def _token_matches(token: str, cluster: str, role: str, eid: str) -> bool:
    parts = str(token or "").split(":")
    if len(parts) < 3:
        return False
    return parts[0] == cluster and parts[1] == role and ":".join(parts[2:]) == eid


class ResidualFrontierDebtSequenceController(ReturnWaypointFrontierSequenceController):
    """v0.3.21 waypoint escape plus residual-frontier debt."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_debt()

    def _reset_debt(self) -> None:
        self._debts = []
        self._debt_seq = 0
        self._hold = None
        self._debt_counts = {key: 0 for key in _METRIC_KEYS}

    def reset(self):
        super().reset()
        self._reset_debt()

    def _bump(self, key: str, amount: int = 1) -> None:
        self._debt_counts[key] = int(self._debt_counts.get(key) or 0) + amount

    def _unresolved(self) -> list:
        return [debt for debt in self._debts if debt.get("status") == "unresolved"]

    def _debt_before(self) -> dict:
        return {
            "success": int(self.ledger.return_success),
            "started": int(self.ledger.sequences_started),
            "completed": int(self.ledger.sequences_completed),
            "wp_false": int(self._wp_false_success),
            "wp_terminal": int(self._wp_terminal_violations),
        }

    def _note_false_success(self, before_success: int) -> None:
        if int(self.ledger.return_success) != before_success:
            self._bump("residual_frontier_false_success_violations")

    def _lifecycle_blocked(self) -> bool:
        if self._open_instance is not None:
            return True
        if self.ledger.active_branch:
            return True
        if self.ledger.returning:
            return True
        if int(self.stack_depth) != 0:
            return True
        if self._return_holding():
            return True
        if self._pending_return_probe is not None:
            return True
        if self._pending_probe is not None:
            return True
        drain = self._drain or {}
        if drain.get("active") or drain.get("paused") or drain.get("promoted_child_id"):
            return True
        lease = self._lease or {}
        if lease.get("active"):
            return True
        if self._pending_lease_action is not None:
            return True
        return False

    def _accounting_ok(self, event: dict, new_events: list, before: dict) -> bool:
        instance = event.get("sequence_instance_id") or ""
        waypoint_sig = event.get("waypoint_sig") or ""
        waypoint_cluster = event.get("waypoint_cluster") or ""
        if not instance or not waypoint_sig or not waypoint_cluster:
            return False
        terminals = [
            item for item in new_events
            if item.get("event") == "sequence_terminal"
            and item.get("sequence_instance_id") == instance
            and item.get("outcome") == "return_cycle_abandoned"
            and item.get("reason") == "return_waypoint_escape"
        ]
        if len(terminals) != 1:
            return False
        if int(self.ledger.return_success) != before["success"]:
            self._bump("residual_frontier_false_success_violations")
            return False
        if int(self._wp_false_success) != before["wp_false"]:
            self._bump("residual_frontier_false_success_violations")
            return False
        if int(self._wp_terminal_violations) != before["wp_terminal"]:
            return False
        if self.ledger.returning or self.ledger.active_branch or self._open_instance is not None:
            return False
        if int(self.ledger.sequences_started) != before["started"]:
            return False
        if int(self.ledger.sequences_completed) != before["completed"]:
            return False
        return True

    def _consider_debt(self, event: dict, new_events: list, before: dict) -> None:
        if not self._accounting_ok(event, new_events, before):
            return
        cluster = event.get("waypoint_cluster") or ""
        tokens = normalize_residual_tokens(
            event.get("local_residual_keys"),
            event.get("structural_residual_keys"),
            cluster,
        )
        if not tokens:
            return
        self._debt_seq += 1
        debt_id = f"debt-{self._debt_seq:04d}"
        debt = {
            "debt_id": debt_id,
            "created_step": event.get("step"),
            "source_sequence_instance_id": event.get("sequence_instance_id") or "",
            "source_branch": event.get("active_branch") or event.get("branch_key") or "",
            "waypoint_sig": event.get("waypoint_sig") or "",
            "waypoint_cluster": cluster,
            "residual_tokens": list(tokens),
            "remaining_tokens": list(tokens),
            "consumed_tokens": [],
            "raw_local_keys": list(event.get("local_residual_keys") or []),
            "raw_structural_keys": list(event.get("structural_residual_keys") or []),
            "relocation_count": 0,
            "last_relocation_step": None,
            "status": "unresolved",
            "skips": [],
        }
        self._debts.append(debt)
        self._bump("residual_frontier_debts_created")
        self._bump("residual_frontier_tokens_created", len(tokens))
        self._emit(
            "residual_frontier_debt_created",
            event.get("step"),
            debt["waypoint_sig"],
            cluster,
            debt["source_branch"],
            {
                "debt_id": debt_id,
                "waypoint_sig": debt["waypoint_sig"],
                "waypoint_cluster": cluster,
                "normalized_residual_tokens": list(tokens),
                "raw_residual_keys": {
                    "local": list(debt["raw_local_keys"]),
                    "structural": list(debt["raw_structural_keys"]),
                },
                "source_sequence_instance_id": debt["source_sequence_instance_id"],
                "source_branch": debt["source_branch"],
                "remaining_count": len(tokens),
            },
        )

    def _absorb_debts(self, new_events: list, before: dict) -> None:
        for event in new_events:
            if event.get("event") == "return_waypoint_frontier_escape":
                self._consider_debt(event, new_events, before)

    def _action_role(self, action) -> tuple:
        if action is None:
            return "", ""
        kind = getattr(action, "type", "") or ""
        role = "click" if kind in CLICK_KINDS else kind
        return role, getattr(action, "target_eid", "") or ""

    def _consume(self, sig: str, action, graph, step: int) -> None:
        role, eid = self._action_role(action)
        if not role or not eid or role == "back":
            return
        cluster = self._cluster(sig, graph)
        if not cluster:
            return
        success_before = int(self.ledger.return_success)
        for debt in list(self._debts):
            if debt.get("status") != "unresolved":
                continue
            if debt.get("waypoint_cluster") != cluster:
                continue
            matched = [
                token for token in list(debt["remaining_tokens"])
                if _token_matches(token, cluster, role, eid)
            ]
            if not matched:
                continue
            for token in matched:
                if token not in debt["remaining_tokens"]:
                    self._bump("residual_frontier_consumption_violations")
                    continue
                debt["remaining_tokens"].remove(token)
                debt["consumed_tokens"].append(token)
                self._bump("residual_frontier_tokens_consumed")
            self._emit(
                "residual_frontier_debt_consumed",
                step,
                sig,
                cluster,
                "",
                {
                    "debt_id": debt["debt_id"],
                    "consumed_tokens": list(matched),
                    "remaining_count": len(debt["remaining_tokens"]),
                    "action_role": role,
                    "action_eid": eid,
                },
            )
            if not debt["remaining_tokens"]:
                debt["status"] = "resolved"
                self._bump("residual_frontier_debts_resolved")
                self._emit(
                    "residual_frontier_debt_resolved",
                    step,
                    sig,
                    cluster,
                    "",
                    {
                        "debt_id": debt["debt_id"],
                        "remaining_count": 0,
                        "consumed_tokens": list(debt["consumed_tokens"]),
                    },
                )
            elif debt.get("status") == "resolved":
                self._bump("residual_frontier_consumption_violations")
        self._note_false_success(success_before)

    def observe_restore_action(self, sig: str, action, graph, step: int) -> None:
        """Replay must not consume debt or append sequence lifecycle events."""
        before_events = len(self.events)
        before_tokens = int(self._debt_counts["residual_frontier_tokens_consumed"])
        before_success = int(self.ledger.return_success)
        before_started = int(self.ledger.sequences_started)
        before_completed = int(self.ledger.sequences_completed)
        if (
            len(self.events) != before_events
            or int(self._debt_counts["residual_frontier_tokens_consumed"]) != before_tokens
            or int(self.ledger.return_success) != before_success
            or int(self.ledger.sequences_started) != before_started
            or int(self.ledger.sequences_completed) != before_completed
        ):
            self._bump("residual_frontier_restore_sequence_violations")
        del sig, action, graph, step

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        before = self._debt_before()
        n_events = len(self.events)
        super().after(
            sig, action, state, new_state, relation, findings,
            new_sig, crashed, graph, step)
        self._absorb_debts(self.events[n_events:], before)
        self._consume(sig, action, graph, step)
        if self._hold is not None:
            self._hold = None

    def _observe_hold(self, ctx: dict) -> None:
        hold = self._hold
        if not hold or hold.get("failure_emitted") or hold.get("arrival_noted"):
            return
        sig = ctx.get("sig") or ""
        if sig and sig == hold.get("target_sig"):
            hold["arrival_noted"] = True
            return
        hold["failure_emitted"] = True
        self._bump("residual_frontier_relocation_failures")
        debt = self._debt_by_id(hold.get("debt_id") or "")
        if debt is not None and debt.get("status") == "resolved":
            self._bump("residual_frontier_false_success_violations")
        self._emit(
            "residual_frontier_debt_relocation_failure",
            ctx.get("step_index"),
            sig,
            "",
            "",
            {
                "debt_id": hold.get("debt_id") or "",
                "target_waypoint_sig": hold.get("target_sig") or "",
                "from_sig": sig,
                "reason": "restore_failed",
                "remaining_count": 0 if debt is None else len(debt.get("remaining_tokens") or []),
            },
        )

    def _debt_by_id(self, debt_id: str):
        for debt in self._debts:
            if debt.get("debt_id") == debt_id:
                return debt
        return None

    def _skip(self, debt: dict, reason: str, step) -> None:
        debt.setdefault("skips", []).append({"step": step, "reason": reason})
        if reason == "inside_scc":
            self._bump("residual_frontier_inside_scc_suppressed")
        elif reason == "no_path":
            self._bump("residual_frontier_no_path_suppressed")
        elif reason == "budget":
            self._bump("residual_frontier_budget_suppressed")
        elif reason == "empty":
            self._bump("residual_frontier_consumption_violations")

    def _unusable(self, debt: dict, members: set, graph, ctx: dict) -> str:
        if not debt.get("remaining_tokens"):
            return "empty"
        target = debt.get("waypoint_sig") or ""
        if not target or target not in graph.nodes:
            return "no_path"
        if target in members:
            return "inside_scc"
        path = graph.shortest_path(graph.start_sig, target)
        if path is None:
            return "no_path"
        remaining = int(ctx.get("budget", 10**9)) - int(ctx.get("step_index") or 0)
        if remaining <= len(path):
            return "budget"
        return ""

    def _select_debt(self, members: set, graph, ctx: dict):
        chosen = None
        step = ctx.get("step_index")
        for debt in self._debts:
            if debt.get("status") != "unresolved":
                continue
            reason = self._unusable(debt, members, graph, ctx)
            if reason:
                self._skip(debt, reason, step)
                continue
            chosen = debt
            break
        return chosen

    def maybe_debt_relocate(self, graph, state, actions, ctx, payload_policy=None):
        del state, actions
        self._bump("residual_frontier_gate_checks")
        if graph is None or ctx is None:
            return None
        self._observe_hold(ctx)
        if self._hold is not None:
            self._bump("residual_frontier_zero_normal_action_suppressed")
            return None
        if not self._unresolved():
            return None
        if self._lifecycle_blocked():
            self._bump("residual_frontier_active_sequence_suppressed")
            return None
        current = ctx.get("sig") or ""
        component = observed_scc(graph, current)
        if component is None:
            return None
        self._bump("residual_frontier_closed_scc_checks")
        if not component["closed"]:
            self._bump("residual_frontier_open_scc_suppressed")
            return None
        pending = component_pending(graph, component["sigs"], payload_policy)
        self._bump("residual_frontier_exhausted_scc_checks")
        if pending != 0:
            self._bump("residual_frontier_pending_scc_suppressed")
            return None
        debt = self._select_debt(component["members"], graph, ctx)
        if debt is None:
            return None
        target = debt["waypoint_sig"]
        if target in component["members"] or target != debt["waypoint_sig"]:
            self._bump("residual_frontier_target_identity_violations")
            return None
        path = graph.shortest_path(graph.start_sig, target)
        if path is None:
            self._bump("residual_frontier_no_path_suppressed")
            return None
        success_before = int(self.ledger.return_success)
        debt["relocation_count"] = int(debt.get("relocation_count") or 0) + 1
        debt["last_relocation_step"] = ctx.get("step_index")
        self._bump("residual_frontier_debt_relocations")
        from_cluster = self._cluster(current, graph)
        self._emit(
            "residual_frontier_debt_relocate",
            ctx.get("step_index"),
            current,
            from_cluster,
            "",
            {
                "debt_id": debt["debt_id"],
                "from_sig": current,
                "from_cluster": from_cluster,
                "current_scc_node_count": component["size"],
                "scc_closed": True,
                "scc_pending_count": pending,
                "target_waypoint_sig": target,
                "target_waypoint_cluster": debt["waypoint_cluster"],
                "replay_path_length": len(path),
                "remaining_debt_tokens": list(debt["remaining_tokens"]),
                "remaining_count": len(debt["remaining_tokens"]),
                "active_sequence": False,
                "reason": "closed_exhausted_scc",
            },
        )
        self._hold = {
            "debt_id": debt["debt_id"],
            "target_sig": target,
            "failure_emitted": False,
            "arrival_noted": False,
        }
        self._note_false_success(success_before)
        if debt.get("status") != "unresolved":
            self._bump("residual_frontier_false_success_violations")
        return target

    def metrics(self) -> dict:
        out = super().metrics()
        out.update(self._debt_counts)
        out["residual_frontier_debts_unresolved"] = len(self._unresolved())
        out["residual_frontier_debts_created"] = len(self._debts)
        out["residual_frontier_debts_resolved"] = sum(
            1 for debt in self._debts if debt.get("status") == "resolved")
        out["residual_frontier_tokens_created"] = sum(
            len(debt.get("residual_tokens") or []) for debt in self._debts)
        out["residual_frontier_tokens_consumed"] = sum(
            len(debt.get("consumed_tokens") or []) for debt in self._debts)
        return out


class ResidualFrontierDebtGuardGhostPolicy(ReturnWaypointFrontierGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-residual-frontier-debt-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = ResidualFrontierDebtSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False

    def maybe_relocate(self, graph, state, actions, ctx):
        seq = self.sequence
        if not isinstance(seq, ResidualFrontierDebtSequenceController) or not seq.enabled():
            return None
        return seq.maybe_debt_relocate(
            graph, state, actions, ctx, payload_policy=self.payload_policy)


__all__ = [
    "ResidualFrontierDebtGuardGhostPolicy",
    "ResidualFrontierDebtSequenceController",
    "component_pending",
    "normalize_residual_tokens",
    "observed_scc",
]
