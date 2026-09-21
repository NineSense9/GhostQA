"""Short-horizon branch / sequence exploration (v0.3.5 + v0.3.6 memory).

Natural navigation only: no global restore-from-start. Does not read
bug manifests. Replay still sees concrete Actions.

v0.3.5 modes (frozen): off | branch | followup | sequence
v0.3.6 modes (additive): structural | contextual | contextual-crossview
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .interaction import is_progress_action, DISTRACTOR_KEYWORDS
from .sequence_memory import (
    StructuralHubMemory, make_delta, CONTEXTUAL_NOVELTY_BONUS,
    W_CONTEXT_RETEST, MUTATION_REFRESH, MAX_SEQUENCE_ACTIONS,
    CROSS_VIEW_BONUS, PRODUCTIVE_WINDOW,
)
from ..state.models import Action
from ..state.similarity import NEW, SIMILAR

HUB_MIN_BRANCHES = 3
BRANCH_HORIZON = 3
W_BRANCH_NOVELTY = 0.55
W_FOLLOWUP = 0.75
RETURN_BONUS = 0.65
FOLLOWUP_HORIZON = 3
MUTATION_TTL = 10

SEQUENCE_LIKE = ("sequence", "structural", "contextual", "contextual-crossview")
FOLLOWUP_LIKE = ("followup",) + SEQUENCE_LIKE
CONTEXT_MODES = ("structural", "contextual", "contextual-crossview")

RETURN_WORDS = ("返回", "return", "back", "previous", "parent", "上一级")


def _blob(action, state) -> str:
    parts = [action.type, action.target_eid or ""]
    if state is not None:
        for el in state.elements:
            if el.eid == action.target_eid:
                parts.extend([el.text or "", el.role or "", el.eid or ""])
                break
    return " ".join(parts).lower()


def is_return_action(action, state) -> bool:
    if action is None:
        return False
    if action.type == "back":
        return True
    blob = _blob(action, state)
    return any(w in blob for w in RETURN_WORDS)


def is_branch_click(action, state) -> bool:
    if action is None or action.type != "click":
        return False
    if is_return_action(action, state):
        return False
    if is_progress_action(action, state):
        return False
    blob = _blob(action, state)
    if any(k.lower() in blob for k in DISTRACTOR_KEYWORDS):
        return False
    return True


def branch_key(cluster_id: str, action) -> str:
    eid = (action.target_eid or "") if action is not None else ""
    return f"{cluster_id or '?'}:click:{eid}"


def branch_clicks(state) -> list:
    out = []
    for el in state.elements:
        if not el.enabled or el.kind != "click":
            continue
        a = Action("click", el.eid)
        if is_branch_click(a, state):
            out.append(a)
    return out


def is_hub(state, graph=None, sig: str = "") -> bool:
    """A hub has several distinct non-input, non-commit, non-back clicks."""
    eids = {a.target_eid for a in branch_clicks(state) if a.target_eid}
    if len(eids) < HUB_MIN_BRANCHES:
        return False
    kinds = set()
    for el in state.elements:
        if el.eid in eids:
            kinds.add((el.role or "button", (el.text or "")[:8]))
    return len(kinds) >= 2 or len(eids) >= HUB_MIN_BRANCHES


@dataclass
class MutationContext:
    step: int
    source_sig: str
    action_key: str
    new_eids: tuple = ()
    changed_obs_keys: tuple = ()
    branch_id: str = ""
    visible_facts: dict = field(default_factory=dict)
    ttl: int = MUTATION_TTL


@dataclass
class BranchRec:
    hub_sig: str
    hub_cluster: str
    first_seen: int = 0
    discovered: set = field(default_factory=set)
    started: set = field(default_factory=set)
    completed: set = field(default_factory=set)
    returned: set = field(default_factory=set)


class BranchLedger:
    def __init__(self):
        self.hubs: dict = {}
        self.active_branch: str = ""
        self.parent_hub_sig: str = ""
        self.parent_hub_cluster: str = ""
        self.commitment_left: int = 0
        self.returning: bool = False
        self.branch_actions: int = 0
        self.branch_new_states: int = 0
        self.branch_findings: int = 0
        self.repeats: int = 0
        self.started_total: int = 0
        self.completed_total: int = 0
        self.return_attempts: int = 0
        self.return_success: int = 0
        self.mutations: int = 0
        self.followup_actions: int = 0
        self.sequences_started: int = 0
        self.sequences_completed: int = 0
        self.seq_lens: list = field(default_factory=list) if False else []
        self._seq_len: int = 0

    def hub(self, sig: str, cluster: str) -> BranchRec:
        rec = self.hubs.get(sig)
        if rec is None:
            rec = BranchRec(hub_sig=sig, hub_cluster=cluster)
            self.hubs[sig] = rec
        return rec

    def metrics(self) -> dict:
        """Deprecated exact-sig / mixed counters. Prefer canonical_metrics."""
        discovered = set()
        started = set()
        completed = set()
        for h in self.hubs.values():
            discovered |= h.discovered
            started |= h.started
            completed |= h.completed
        n_disc = len(discovered)
        mean_len = (sum(self.seq_lens) / len(self.seq_lens)) if self.seq_lens else None
        return {
            "hub_count": len(self.hubs),  # deprecated: hub_variant_count
            "hub_variant_count": len(self.hubs),
            "branches_discovered": n_disc,
            "branches_started": len(started),
            "branches_completed": len(completed),
            "branch_coverage": round(len(completed) / n_disc, 3) if n_disc else None,
            "unique_branch_targets": n_disc,
            "branch_repeats": self.repeats,
            "mean_actions_per_branch": (
                round(self.branch_actions / max(1, self.started_total), 3)
                if self.started_total else None),
            "mutation_count": self.mutations,
            "followup_actions": self.followup_actions,
            "sequences_started": self.sequences_started,
            "sequences_completed": self.sequences_completed,
            "return_attempts": self.return_attempts,
            "return_success": self.return_success,
            "mean_sequence_len": mean_len,
            "max_sequence_len": max(self.seq_lens) if self.seq_lens else 0,
        }


def _finding_fps(findings) -> list:
    """Observability only. Findings are already passed into after()."""
    out = []
    for f in findings or []:
        fn = getattr(f, "fingerprint", None)
        if callable(fn):
            try:
                fp = fn()
            except Exception:
                fp = None
        else:
            fp = fn
        if fp:
            out.append(str(fp))
    return out


def canonical_sequence_metrics(events: list) -> dict:
    """Cluster-level hub / branch / instance metrics from append-only events.

    Sequence length is the count of sequence_action events per instance.
    Horizon is a lifecycle event, not a terminal outcome.
    Policy never calls this.
    """
    hub_variants = set()
    hub_clusters = set()
    discovered = set()
    started_keys = set()
    returned_keys = set()
    finding_keys = set()
    start_events = 0
    return_attempt_events = 0
    horizon_n = 0
    instances = {}
    followup_n = 0
    mutation_n = 0
    fingerprints = set()

    def _inst(eid):
        if not eid:
            return None
        rec = instances.get(eid)
        if rec is None:
            rec = {"outcome": "open", "actions": 0, "branch": ""}
            instances[eid] = rec
        return rec

    for e in events:
        ev = e.get("event")
        cid = e.get("cluster_id") or ""
        sig = e.get("exact_sig") or ""
        bk = e.get("branch_key") or ""
        iid = e.get("sequence_instance_id")
        if ev == "hub_seen":
            if sig:
                hub_variants.add(sig)
            if cid:
                hub_clusters.add(cid)
        elif ev == "branch_discovered":
            if bk:
                discovered.add(bk)
        elif ev == "branch_start":
            start_events += 1
            if bk:
                started_keys.add(bk)
            rec = _inst(iid)
            if rec is not None and bk:
                rec["branch"] = bk
        elif ev == "sequence_action":
            rec = _inst(iid)
            if rec is not None:
                rec["actions"] += 1
                if bk:
                    rec["branch"] = rec["branch"] or bk
        elif ev == "mutation":
            mutation_n += 1
        elif ev == "followup":
            followup_n += 1
        elif ev == "return_attempt":
            return_attempt_events += 1
        elif ev in ("sequence_horizon_reached", "horizon"):
            horizon_n += 1
        elif ev == "sequence_terminal":
            rec = _inst(iid)
            outcome = e.get("outcome") or "unknown"
            if rec is not None and rec["outcome"] == "open":
                rec["outcome"] = outcome
                if bk:
                    rec["branch"] = rec["branch"] or bk
            for fp in e.get("fingerprints") or []:
                if fp:
                    fingerprints.add(fp)

    outcomes = {}
    lens = []
    for rec in instances.values():
        outcomes[rec["outcome"]] = outcomes.get(rec["outcome"], 0) + 1
        lens.append(rec["actions"])
        bk = rec.get("branch") or ""
        if rec["outcome"] == "returned" and bk:
            returned_keys.add(bk)
        elif rec["outcome"] == "finding" and bk:
            finding_keys.add(bk)

    n_hub_c = len(hub_clusters)
    n_hub_v = len(hub_variants)
    n_started_i = len(instances)
    n_returned = outcomes.get("returned", 0)
    n_finding = outcomes.get("finding", 0)
    n_disc = len(discovered)
    n_started_u = len(started_keys)
    n_returned_u = len(returned_keys)
    n_finding_u = len(finding_keys)
    n_terminal_u = len(returned_keys | finding_keys)
    requiring = n_started_i - n_finding - outcomes.get("crash", 0)
    return {
        "hub_variant_count": n_hub_v,
        "canonical_hub_count": n_hub_c,
        "hub_count": n_hub_v,  # deprecated alias of hub_variant_count
        "hub_variant_inflation": (
            round(n_hub_v / n_hub_c, 3) if n_hub_c else None),
        "unique_branches_discovered": n_disc,
        "unique_branches_started": n_started_u,
        "unique_branches_returned": n_returned_u,
        "unique_branches_with_finding": n_finding_u,
        "unique_branches_terminally_tested": n_terminal_u,
        "unique_branches_completed": n_returned_u,  # deprecated: returned
        "canonical_branch_coverage": (
            round(n_terminal_u / n_disc, 3) if n_disc else None),
        "branch_start_events": start_events,
        "branch_attempts_total": start_events,
        "branch_revisit_attempts": max(0, start_events - n_started_u),
        "branch_attempts_per_unique_branch": (
            round(start_events / n_started_u, 3) if n_started_u else None),
        "repeated_branch_attempt_rate": (
            round((start_events - n_started_u) / start_events, 3)
            if start_events else None),
        "sequence_instances_started": n_started_i,
        "sequence_instances_returned": n_returned,
        "sequence_returned": n_returned,
        "sequence_instances_ended_on_finding": n_finding,
        "sequence_ended_on_finding": n_finding,
        "sequence_found_finding": n_finding,  # deprecated alias
        "sequence_crashed": outcomes.get("crash", 0),
        "sequence_horizon_reached": horizon_n,
        "sequence_horizon_expired": horizon_n,  # lifecycle, not a terminal
        "sequence_budget_ended": outcomes.get("budget_end", 0),
        "sequence_lost_parent": outcomes.get("lost_parent", 0),
        "sequence_instances_open_at_budget_end": (
            outcomes.get("open", 0) + outcomes.get("budget_end", 0)),
        "sequence_instance_completion_rate": (
            round(n_returned / n_started_i, 3) if n_started_i else None),
        "return_attempt_events": return_attempt_events,
        "return_success_rate": (
            round(n_returned / requiring, 3) if requiring else None),
        "unique_candidate_fingerprints_during_sequence": len(fingerprints),
        "mutation_count": mutation_n,
        "followup_actions": followup_n,
        "mean_sequence_len": (
            round(sum(lens) / len(lens), 3) if lens else None),
        "max_sequence_len": max(lens) if lens else 0,
        "branches_discovered": n_disc,
        "branches_started": n_started_u,
        "branches_completed": n_returned_u,
        "branch_coverage": round(n_terminal_u / n_disc, 3) if n_disc else None,
    }


class SequenceController:
    """modes: off | branch | followup | sequence | structural | contextual | contextual-crossview"""

    def __init__(self, mode: str = "off"):
        self.mode = mode
        self.ledger = BranchLedger()
        self.mutations: list = []
        self.last_label = "normal"
        self.events: list = []
        self._instance_n = 0
        self._open_instance = None  # {"id", "branch", "len"}
        self.struct = StructuralHubMemory()
        self.ctx_stats = self._empty_ctx_stats()
        self._last_delta = None
        self._tried_action_ctx: set = set()
        self._pending_retest = None
        self._local_ctx_id = "e0:init"

    def _empty_ctx_stats(self) -> dict:
        return {
            "context_epochs_created": 0,
            "meaningful_mutations": 0,
            "contextual_branch_retests": 0,
            "contextual_branch_retests_productive": 0,
            "contextual_action_retests": 0,
            "contextual_action_retests_productive": 0,
            "mutation_refreshes": 0,
            "cross_view_checks": 0,
            "cross_view_checks_with_finding": 0,
            "contextual_retest_no_effect": 0,
        }

    def reset(self):
        self.ledger = BranchLedger()
        self.mutations = []
        self.last_label = "normal"
        self.events = []
        self._instance_n = 0
        self._open_instance = None
        self.struct = StructuralHubMemory()
        self.ctx_stats = self._empty_ctx_stats()
        self._last_delta = None
        self._tried_action_ctx = set()
        self._pending_retest = None
        self._local_ctx_id = "e0:init"

    def _emit(self, event: str, step: int, sig: str, cluster: str,
              bkey: str = "", extra: dict = None):
        rec = {
            "step": step,
            "event": event,
            "exact_sig": sig,
            "cluster_id": cluster,
            "branch_key": bkey,
            "sequence_instance_id": (
                self._open_instance["id"] if self._open_instance else None),
        }
        if extra:
            rec.update(extra)
        self.events.append(rec)

    def close_open(self, step: int = -1, sig: str = "", cluster: str = ""):
        """Measurement only: mark an open instance at budget end."""
        if self._open_instance is None:
            return
        self._emit("sequence_terminal", step, sig, cluster,
                   self._open_instance.get("branch", ""),
                   {"outcome": "budget_end",
                    "length": self._open_instance.get("len", 0)})
        self._open_instance = None

    def enabled(self) -> bool:
        return self.mode not in ("", "off", None)

    def metrics(self) -> dict:
        out = self.ledger.metrics()
        if self.events:
            out.update(canonical_sequence_metrics(self.events))
        out.update(self.ctx_stats)
        productive = self.ctx_stats["contextual_branch_retests_productive"]
        total_rt = self.ctx_stats["contextual_branch_retests"]
        out["productive_context_retest_rate"] = (
            round(productive / total_rt, 3) if total_rt else None)
        return out

    def score_bonus(self, action, state, graph, ctx) -> float:
        if not self.enabled() or action is None:
            return 0.0
        sig = ctx.get("sig", "")
        node = graph.nodes.get(sig) if graph else None
        cluster = (node.cluster_id if node else "") or sig.split(":")[0]
        bonus = 0.0
        if is_hub(state) and is_branch_click(action, state):
            key = branch_key(cluster, action)
            if self.mode in CONTEXT_MODES:
                hist = self.struct.hub(cluster).branches.get(key)
                if hist is None or hist.attempts == 0:
                    bonus += W_BRANCH_NOVELTY
                elif (self.mode != "structural"
                      and self.struct.retest_eligible(cluster, key, action, state)):
                    bonus += W_CONTEXT_RETEST
            else:
                rec = self.ledger.hub(sig, cluster)
                rec.discovered.add(key)
                if key not in rec.started and key not in rec.completed:
                    bonus += W_BRANCH_NOVELTY
        if self.mode in FOLLOWUP_LIKE and self._is_followup(action):
            bonus += W_FOLLOWUP
        if (self.mode in ("contextual", "contextual-crossview")
                and self._is_contextual_action(action, state)):
            bonus += CONTEXTUAL_NOVELTY_BONUS
        if self.ledger.returning and is_return_action(action, state):
            bonus += RETURN_BONUS
        if (self.mode in SEQUENCE_LIKE and self.ledger.commitment_left > 0
                and not is_return_action(action, state)):
            bonus += 0.25
        if self.mode == "contextual-crossview":
            bonus += self._cross_view_bonus(action, state, graph, sig)
        return bonus

    def pick_override(self, actions, state, graph, ctx):
        if not self.enabled() or not actions:
            return None
        sig = ctx.get("sig", "")
        if self.mode in SEQUENCE_LIKE and self.ledger.returning:
            for a in actions:
                if is_return_action(a, state):
                    self.last_label = "return_hub"
                    return a
        if self.mode in FOLLOWUP_LIKE and self.ledger.commitment_left > 0:
            for a in actions:
                if is_return_action(a, state):
                    continue
                if self._is_followup(a):
                    self.last_label = "sequence_followup"
                    return a
        if self.mode in SEQUENCE_LIKE and self.ledger.commitment_left > 0:
            return None  # additive score keeps us in-branch
        if is_hub(state):
            node = graph.nodes.get(sig) if graph else None
            cluster = (node.cluster_id if node else "") or sig.split(":")[0]
            rec = self.ledger.hub(sig, cluster)
            rec.first_seen = rec.first_seen or ctx.get("step_index", 0)
            untried = []
            retest = []
            for a in actions:
                if not is_branch_click(a, state):
                    continue
                key = branch_key(cluster, a)
                rec.discovered.add(key)
                if self.mode in CONTEXT_MODES:
                    hist = self.struct.hub(cluster).branches.get(key)
                    if hist is None or hist.attempts == 0:
                        untried.append(a)
                    elif (self.mode != "structural"
                          and self.struct.retest_eligible(cluster, key, a, state)):
                        retest.append(a)
                elif key not in rec.started and key not in rec.completed:
                    untried.append(a)
            if untried:
                self.last_label = "branch"
                return untried[0]
            if retest:
                self.last_label = "branch"
                return retest[0]
        return None

    def after(self, sig, action, state, new_state, relation, findings,
              new_sig, crashed, graph, step: int):
        if not self.enabled() or action is None:
            return
        node = graph.nodes.get(sig) if graph else None
        cluster = (node.cluster_id if node else "") or (sig.split(":")[0] if sig else "")
        was_hub = is_hub(state) if state is not None else False
        if was_hub:
            self._emit("hub_seen", step, sig, cluster)

        if was_hub and is_branch_click(action, state):
            rec = self.ledger.hub(sig, cluster)
            key = branch_key(cluster, action)
            rec.discovered.add(key)
            self._emit("branch_discovered", step, sig, cluster, key)
            if key in rec.started:
                self.ledger.repeats += 1
            else:
                rec.started.add(key)
                self.ledger.started_total += 1
                self.ledger.sequences_started += 1
            if self._open_instance is not None:
                self._emit("sequence_terminal", step, sig, cluster,
                           self._open_instance.get("branch", ""),
                           {"outcome": "lost_parent",
                            "length": self._open_instance.get("len", 0)})
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
            if self.mode in SEQUENCE_LIKE:
                self.ledger.commitment_left = BRANCH_HORIZON
            self.ledger.returning = False
            if self.mode in CONTEXT_MODES:
                self._on_struct_branch_start(cluster, sig, key, step)

        if self._open_instance is not None:
            self._emit(
                "sequence_action", step, sig, cluster,
                self._open_instance.get("branch", ""),
                {"action_key": action.key() if action is not None else "",
                 "decision_mode": self.last_label},
            )

        if self.ledger.active_branch:
            self.ledger.branch_actions += 1
            self.ledger._seq_len += 1
            if self.ledger.commitment_left > 0:
                self.ledger.commitment_left -= 1

        if findings:
            self.ledger.branch_findings += 1
        if relation in (NEW, SIMILAR):
            self.ledger.branch_new_states += 1

        if self.mode in FOLLOWUP_LIKE:
            self._record_mutation(sig, action, state, new_state, relation, step)

        if self.last_label == "sequence_followup":
            self.ledger.followup_actions += 1
            self._emit("followup", step, sig, cluster,
                       self.ledger.active_branch)

        if self.mode in CONTEXT_MODES:
            self._update_context_memory(
                sig, action, state, new_state, relation, findings,
                new_sig, graph, step, cluster)

        expire = False
        terminal_reason = None
        if crashed:
            expire = True
            terminal_reason = "crash"
        elif findings and self.mode in SEQUENCE_LIKE:
            expire = True
            terminal_reason = "finding"
        if self.mode in SEQUENCE_LIKE and self.ledger.commitment_left <= 0 and self.ledger.active_branch:
            expire = True
            if terminal_reason is None:
                terminal_reason = "horizon"
        if self.mode in SEQUENCE_LIKE and relation not in (NEW, SIMILAR) and not findings:
            if self.ledger.commitment_left <= 0:
                expire = True
                if terminal_reason is None:
                    terminal_reason = "horizon"

        if expire and self.ledger.active_branch and not self.ledger.returning:
            self.ledger.returning = True
            self.ledger.commitment_left = 0
            if terminal_reason in ("finding", "crash") and self._open_instance:
                self._emit("sequence_terminal", step, sig, cluster,
                           self._open_instance.get("branch", ""),
                           {"outcome": terminal_reason,
                            "fingerprints": _finding_fps(findings)})
                self._open_instance = None
            elif terminal_reason == "horizon":
                self._emit("sequence_horizon_reached", step, sig, cluster,
                           self.ledger.active_branch)

        if is_return_action(action, state) and self.ledger.returning:
            self._emit("return_attempt", step, sig, cluster,
                       self.ledger.active_branch)

        if self.ledger.returning and new_state is not None:
            self.ledger.return_attempts += 1
            dst_cluster = ""
            if graph and new_sig in graph.nodes:
                dst_cluster = graph.nodes[new_sig].cluster_id
            if (new_sig == self.ledger.parent_hub_sig
                    or (dst_cluster and dst_cluster == self.ledger.parent_hub_cluster)):
                self._complete_branch(step, sig, cluster)

        if self.last_label == "return_hub":
            self.ledger.return_attempts += 1

        self.mutations = [m for m in self.mutations if m.ttl > 0]
        for m in self.mutations:
            m.ttl -= 1

    def _complete_branch(self, step: int = -1, sig: str = "", cluster: str = ""):
        key = self.ledger.active_branch
        parent = self.ledger.parent_hub_sig
        if key and parent in self.ledger.hubs:
            self.ledger.hubs[parent].completed.add(key)
            self.ledger.hubs[parent].returned.add(key)
        if key:
            self.ledger.completed_total += 1
            self.ledger.sequences_completed += 1
            self.ledger.seq_lens.append(self.ledger._seq_len)
        if self._open_instance is not None:
            self._emit("sequence_terminal", step, sig, cluster, key,
                       {"outcome": "returned",
                        "length": self._open_instance.get("len", 0)})
            self._open_instance = None
        self.ledger.return_success += 1
        self.ledger.active_branch = ""
        self.ledger.returning = False
        self.ledger.commitment_left = 0
        self.ledger._seq_len = 0

    def _record_mutation(self, sig, action, state, new_state, relation, step):
        if new_state is None or state is None:
            return
        before = {e.eid for e in state.elements if e.enabled}
        after = {e.eid for e in new_state.elements if e.enabled}
        new_eids = tuple(sorted(after - before))
        changed = tuple(sorted(
            k for k in set(state.obs) | set(new_state.obs)
            if state.obs.get(k) != new_state.obs.get(k)))
        if relation not in (NEW, SIMILAR) and not new_eids and not changed:
            return
        self.ledger.mutations += 1
        facts = {k: new_state.obs.get(k) for k in changed[:6]}
        self._emit("mutation", step, sig, self.ledger.parent_hub_cluster,
                   self.ledger.active_branch)
        self.mutations.append(MutationContext(
            step=step, source_sig=sig, action_key=action.key(),
            new_eids=new_eids, changed_obs_keys=changed,
            branch_id=self.ledger.active_branch, visible_facts=facts,
            ttl=MUTATION_TTL))
        self.mutations = self.mutations[-3:]

    def _is_followup(self, action) -> bool:
        if action is None or not self.mutations:
            return False
        eid = action.target_eid or ""
        for m in self.mutations:
            if m.ttl <= 0:
                continue
            if eid and eid in m.new_eids:
                return True
        return False

    def _is_contextual_action(self, action, state=None) -> bool:
        if action is None or self._last_delta is None:
            return False
        if not self._last_delta.meaningful():
            return False
        if not self.ledger.active_branch:
            return False
        if state is not None and is_hub(state) and is_branch_click(action, state):
            return False
        eid = action.target_eid or ""
        if eid and eid in self._last_delta.new_eids:
            return False
        if (action.key(), self._local_ctx_id) in self._tried_action_ctx:
            return False
        return True

    def _on_struct_branch_start(self, cluster, sig, key, step):
        h = self.struct.hub(cluster)
        hist = self.struct.branch(cluster, key)
        if hist.attempts > 0 and self.mode != "structural":
            h.epoch_retests += 1
            self.ctx_stats["contextual_branch_retests"] += 1
            self._pending_retest = {
                "step": step, "kind": "branch", "left": PRODUCTIVE_WINDOW}
        hist.attempts += 1
        hist.last_test_step = step
        hist.last_test_epoch = h.context_epoch
        self.struct.note_variant(cluster, sig)

    def _update_context_memory(self, sig, action, state, new_state, relation,
                               findings, new_sig, graph, step, cluster):
        dst_cluster = ""
        if graph and new_sig in graph.nodes:
            dst_cluster = graph.nodes[new_sig].cluster_id
        elif new_sig:
            dst_cluster = new_sig.split(":")[0]
        parent_c = self.ledger.parent_hub_cluster or cluster
        delta = make_delta(step, action, state, new_state, parent_c, dst_cluster)
        business = bool(delta.changed_obs or (
            (delta.source_cluster == delta.dest_cluster)
            and (delta.new_eids or delta.removed_eids)))
        if (self.mode in ("contextual", "contextual-crossview")
                and self._is_contextual_action(action, state)):
            self.ctx_stats["contextual_action_retests"] += 1
            self._pending_retest = {
                "step": step, "kind": "action", "left": PRODUCTIVE_WINDOW}
        if business:
            self._last_delta = delta
            if self.struct.apply_delta(parent_c, delta):
                self.ctx_stats["context_epochs_created"] += 1
                self.ctx_stats["meaningful_mutations"] += 1
                self._local_ctx_id = delta.context_id(
                    self.struct.hub(parent_c).context_epoch)
            if (self.mode in ("contextual", "contextual-crossview")
                    and self.ledger.active_branch
                    and not self.ledger.returning
                    and self.ledger.branch_actions < MAX_SEQUENCE_ACTIONS
                    and self.ledger.commitment_left <= 0):
                self.ledger.commitment_left = MUTATION_REFRESH
                self.ctx_stats["mutation_refreshes"] += 1
                remain = MAX_SEQUENCE_ACTIONS - self.ledger.branch_actions
                if self.ledger.commitment_left > remain:
                    self.ledger.commitment_left = max(0, remain)
        self.struct.note_variant(cluster, sig)
        self.struct.note_facts(cluster, state)
        if new_state is not None:
            self.struct.note_facts(dst_cluster or cluster, new_state)
        if self._open_instance is not None and action is not None:
            self._tried_action_ctx.add((action.key(), self._local_ctx_id))
        if self.mode == "contextual-crossview" and self.struct.cross_view_relevant(
                dst_cluster, self._last_delta):
            self.ctx_stats["cross_view_checks"] += 1
            if findings:
                self.ctx_stats["cross_view_checks_with_finding"] += 1
        self._note_productive(relation, findings, business)
        self.struct.tick_facts()

    def _note_productive(self, relation, findings, business):
        pending = self._pending_retest
        if not pending:
            return
        pending["left"] -= 1
        if findings or business or relation in (NEW, SIMILAR):
            key = ("contextual_branch_retests_productive"
                   if pending.get("kind") == "branch"
                   else "contextual_action_retests_productive")
            self.ctx_stats[key] += 1
            self._pending_retest = None
            return
        if pending["left"] <= 0:
            self.ctx_stats["contextual_retest_no_effect"] += 1
            self._pending_retest = None

    def _cross_view_bonus(self, action, state, graph, sig) -> float:
        if action is None or graph is None:
            return 0.0
        edge = graph.edge(sig, action.key()) if hasattr(graph, "edge") else None
        dst = ""
        if edge is not None:
            node = graph.nodes.get(edge.dst)
            dst = node.cluster_id if node else ""
        if not dst and is_return_action(action, state):
            dst = self.ledger.parent_hub_cluster
        if not dst:
            return 0.0
        if self.struct.cross_view_relevant(dst, self._last_delta):
            return CROSS_VIEW_BONUS
        return 0.0

    def label_for(self, action, state) -> str:
        if self.last_label in ("branch", "sequence_followup", "return_hub"):
            return self.last_label
        if is_return_action(action, state) and self.ledger.returning:
            return "return_hub"
        if self._is_followup(action):
            return "sequence_followup"
        if is_branch_click(action, state):
            return "branch"
        return "normal"
