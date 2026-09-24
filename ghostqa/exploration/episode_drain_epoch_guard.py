"""Experimental episode scope for same-hub drain dedupe (v0.3.24).

Research-only. Not the product default. The v0.3.23 controller is reused by
subclassing; its module is not modified.

Same-hub local and return-entry drain keys are browser-episode memory.
A real residual-debt relocation reset invalidates only those keys. Promoted
and other cross-hub drain keys, and every structural ledger, stay run-scoped.
No new drain trigger is added.
"""
from __future__ import annotations

from .residual_frontier_debt_guard import (
    ResidualFrontierDebtGuardGhostPolicy,
    ResidualFrontierDebtSequenceController,
)

_METRIC_KEYS = (
    "local_drain_episode_advances",
    "local_drain_same_hub_keys_recorded",
    "local_drain_same_hub_keys_invalidated",
    "local_drain_cross_hub_keys_preserved",
    "local_drain_revalidated_probe_count",
    "local_drain_episode_without_relocation_violations",
    "local_drain_cross_hub_invalidation_violations",
    "local_drain_restore_probe_violations",
    "local_drain_episode_false_success_violations",
    "local_drain_duplicate_same_episode_violations",
)


class EpisodeDrainEpochSequenceController(ResidualFrontierDebtSequenceController):
    """v0.3.23 debt escape, with same-hub drain keys scoped to the reset episode."""

    def __init__(self, mode: str = "structural"):
        super().__init__(mode)
        self._reset_episode()

    def _reset_episode(self) -> None:
        self.interaction_episode = 0
        self._episode_same_hub_keys = set()
        self._episode_completed = set()
        self._same_hub_origin = {}
        self._invalidated = {}
        self._cross_hub_keys = set()
        self._revalidated_seen = set()
        self._revalidated_clusters = set()
        self._episode_counts = {key: 0 for key in _METRIC_KEYS}

    def reset(self):
        super().reset()
        self._reset_episode()

    def _bump(self, key: str, amount: int = 1) -> None:
        counts = getattr(self, "_episode_counts", None)
        if counts is not None and key in counts:
            counts[key] = int(counts.get(key) or 0) + amount
            return
        super()._bump(key, amount)

    def _structural_view(self) -> tuple:
        debts = tuple(
            (
                debt.get("debt_id"),
                debt.get("status"),
                tuple(debt.get("remaining_tokens") or []),
                tuple(debt.get("consumed_tokens") or []),
                int(debt.get("relocation_count") or 0),
            )
            for debt in self._debts
        )
        return (
            int(self.ledger.return_success),
            int(self.ledger.sequences_started),
            int(self.ledger.sequences_completed),
            bool(self.ledger.returning),
            self.ledger.active_branch or "",
            int(self.stack_depth),
            debts,
        )

    def _drained_total(self) -> int:
        return sum(len(keys) for keys in self._drained_by_cluster.values())

    def _note_same_hub(self, cluster: str, key: str, step: int, trigger: str) -> None:
        identity = (cluster or "", key)
        if not key or identity in self._episode_completed:
            self._bump("local_drain_duplicate_same_episode_violations")
            return
        self._episode_completed.add(identity)
        self._episode_same_hub_keys.add(identity)
        self._same_hub_origin[identity] = int(self.interaction_episode)
        self._bump("local_drain_same_hub_keys_recorded")
        self._emit(
            "local_drain_same_hub_key_recorded",
            step,
            "",
            cluster or "",
            key,
            {
                "cluster": cluster or "",
                "key": key,
                "episode": int(self.interaction_episode),
                "trigger": trigger,
                "sequence_instance_id": None,
            },
        )

    def _note_cross_hub(self, cluster: str, key: str, step: int, reason: str) -> None:
        identity = (cluster or "", key)
        if not key:
            return
        if identity in self._cross_hub_keys:
            return
        self._cross_hub_keys.add(identity)
        self._bump("local_drain_cross_hub_keys_preserved")
        self._emit(
            "local_drain_cross_hub_key_preserved",
            step,
            "",
            cluster or "",
            key,
            {
                "cluster": cluster or "",
                "key": key,
                "episode": int(self.interaction_episode),
                "reason": reason,
                "sequence_instance_id": None,
            },
        )

    def _note_revalidation(self, ctx, probe: dict, trigger: str) -> None:
        if not probe:
            return
        cluster = probe.get("hub_cluster") or ""
        key = probe.get("key") or ""
        record = self._invalidated.get((cluster, key))
        if not record or not key:
            return
        original = int(record.get("original_episode") or 0)
        if int(self.interaction_episode) <= original:
            return
        seen = (int(self.interaction_episode), cluster, key)
        if seen in self._revalidated_seen:
            self._bump("local_drain_duplicate_same_episode_violations")
            return
        self._revalidated_seen.add(seen)
        self._revalidated_clusters.add(cluster)
        self._bump("local_drain_revalidated_probe_count")
        step = -1 if not ctx else ctx.get("step_index", -1)
        self._emit(
            "local_drain_key_revalidated",
            step,
            "",
            cluster,
            key,
            {
                "original_episode": original,
                "current_episode": int(self.interaction_episode),
                "cluster": cluster,
                "key": key,
                "trigger": trigger,
                "sequence_instance_id": None,
            },
        )

    def _restore_context(self, ctx) -> bool:
        if not (ctx and ctx.get("restore_step")):
            return False
        self._bump("local_drain_restore_probe_violations")
        return True

    def _complete_same_hub(self, probe, sig, action, state, new_state, relation,
                           findings, new_sig, graph, step, source_cluster,
                           dst_cluster) -> None:
        drain = self._drain or {}
        cluster = probe.get("hub_cluster") or drain.get("hub_cluster") or ""
        key = probe.get("key") or ""
        already = key in self._drained_by_cluster.get(cluster or "", ())
        super()._complete_same_hub(
            probe, sig, action, state, new_state, relation, findings,
            new_sig, graph, step, source_cluster, dst_cluster)
        if key and key in self._drained_by_cluster.get(cluster or "", ()) and not already:
            self._note_same_hub(cluster, key, step, "local_action")
        elif already and key:
            self._bump("local_drain_duplicate_same_episode_violations")

    def _complete_return_same_hub(self, probe, sig, findings, new_state, new_sig,
                                  graph, step, dst_cluster, before: tuple) -> None:
        entry = self._return_entry or {}
        cluster = probe.get("hub_cluster") or entry.get("hub_cluster") or ""
        key = probe.get("key") or ""
        already = key in self._drained_by_cluster.get(cluster or "", ())
        super()._complete_return_same_hub(
            probe, sig, findings, new_state, new_sig, graph, step, dst_cluster, before)
        if key and key in self._drained_by_cluster.get(cluster or "", ()) and not already:
            self._note_same_hub(cluster, key, step, "return_entry")
        elif already and key:
            self._bump("local_drain_duplicate_same_episode_violations")

    def _leave_hub(self, probe, sig, new_sig, graph, step, dst_cluster, before) -> None:
        entry = self._return_entry or {}
        cluster = probe.get("hub_cluster") or entry.get("hub_cluster") or ""
        key = probe.get("key") or ""
        super()._leave_hub(probe, sig, new_sig, graph, step, dst_cluster, before)
        self._note_cross_hub(cluster, key, step, "return_entry_left_hub")

    def _resume_drain(self, step, sig, new_sig, new_state, graph, strength) -> None:
        drain = self._drain or {}
        cluster = drain.get("hub_cluster") or ""
        key = drain.get("promoted_button_key") or ""
        super()._resume_drain(step, sig, new_sig, new_state, graph, strength)
        self._note_cross_hub(cluster, key, step, "promoted_child")

    def _select_local(self, actions, state, graph, ctx, sig):
        if self._restore_context(ctx):
            return None
        chosen = super()._select_local(actions, state, graph, ctx, sig)
        self._note_revalidation(ctx, self._pending_probe or {}, "local_action_drain")
        return chosen

    def _select_return_entry(self, actions, state, graph, ctx, sig):
        if self._restore_context(ctx):
            return None
        chosen = super()._select_return_entry(actions, state, graph, ctx, sig)
        self._note_revalidation(
            ctx, self._pending_return_probe or {}, "return_entry_drain")
        return chosen

    def _advance_episode(self, ctx, target: str) -> None:
        if not target:
            self._bump("local_drain_episode_without_relocation_violations")
            return
        before = self._structural_view()
        old = int(self.interaction_episode)
        invalidated = []
        for cluster, key in sorted(self._episode_same_hub_keys):
            if (cluster, key) in self._cross_hub_keys:
                self._bump("local_drain_cross_hub_invalidation_violations")
                continue
            bucket = self._drained_by_cluster.get(cluster)
            if not bucket or key not in bucket:
                continue
            bucket.remove(key)
            if not bucket:
                self._drained_by_cluster.pop(cluster, None)
            origin = int(self._same_hub_origin.get((cluster, key), old))
            self._invalidated[(cluster, key)] = {"original_episode": origin}
            invalidated.append({
                "cluster": cluster,
                "key": key,
                "original_episode": origin,
            })
            self._bump("local_drain_same_hub_keys_invalidated")
        preserved = self._drained_total()
        self._episode_same_hub_keys.clear()
        self._episode_completed.clear()
        self.interaction_episode = old + 1
        self._bump("local_drain_episode_advances")
        if self._structural_view() != before:
            self._bump("local_drain_episode_false_success_violations")
        event = None
        for item in reversed(self.events):
            if item.get("event") == "residual_frontier_debt_relocate":
                event = item
                break
        self._emit(
            "local_drain_episode_advanced",
            None if not ctx else ctx.get("step_index"),
            target,
            "" if event is None else event.get("target_waypoint_cluster") or "",
            "",
            {
                "old_episode": old,
                "new_episode": int(self.interaction_episode),
                "debt_id": "" if event is None else event.get("debt_id") or "",
                "target_sig": target,
                "target_cluster": "" if event is None else event.get("target_waypoint_cluster") or "",
                "invalidated_same_hub_key_count": len(invalidated),
                "invalidated_keys": invalidated,
                "preserved_drained_key_count": preserved,
                "reason": "residual_frontier_debt_relocation",
                "sequence_instance_id": None,
            },
        )

    def maybe_debt_relocate(self, graph, state, actions, ctx, payload_policy=None):
        target = super().maybe_debt_relocate(
            graph, state, actions, ctx, payload_policy=payload_policy)
        if target:
            self._advance_episode(ctx, target)
        return target

    def metrics(self) -> dict:
        out = super().metrics()
        out.update(self._episode_counts)
        out["local_drain_interaction_episode"] = int(self.interaction_episode)
        out["local_drain_revalidated_cluster_count"] = len(self._revalidated_clusters)
        return out


class EpisodeDrainEpochGuardGhostPolicy(ResidualFrontierDebtGuardGhostPolicy):
    """Benchmark-only identity. Does not replace the product default."""

    name = "ghost-structural-episode-drain-epoch-guard"

    def __init__(self, llm=None, **kwargs):
        kwargs["use_frontier"] = False
        kwargs["sequence_mode"] = "structural"
        super().__init__(llm=llm, **kwargs)
        self.sequence = EpisodeDrainEpochSequenceController("structural")
        self.sequence_mode = "structural"
        self.use_frontier = False

    def maybe_relocate(self, graph, state, actions, ctx):
        seq = self.sequence
        if not isinstance(seq, EpisodeDrainEpochSequenceController) or not seq.enabled():
            return None
        return seq.maybe_debt_relocate(
            graph, state, actions, ctx, payload_policy=self.payload_policy)


__all__ = [
    "EpisodeDrainEpochGuardGhostPolicy",
    "EpisodeDrainEpochSequenceController",
]
