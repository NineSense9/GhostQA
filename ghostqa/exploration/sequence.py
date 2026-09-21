"""Short-horizon branch / sequence exploration (v0.3.5).

Natural navigation only: no global restore-from-start. Does not read
bug manifests. Replay still sees concrete Actions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .interaction import is_progress_action, DISTRACTOR_KEYWORDS
from ..state.models import Action
from ..state.similarity import NEW, SIMILAR

HUB_MIN_BRANCHES = 3
BRANCH_HORIZON = 3
W_BRANCH_NOVELTY = 0.55
W_FOLLOWUP = 0.75
RETURN_BONUS = 0.65
FOLLOWUP_HORIZON = 3
MUTATION_TTL = 10

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
    """modes: off | branch | followup | sequence"""

    def __init__(self, mode: str = "off"):
        self.mode = mode
        self.ledger = BranchLedger()
        self.mutations: list = []
        self.last_label = "normal"
        self.events: list = []
        self._instance_n = 0
        self._open_instance = None  # {"id", "branch", "len"}

    def reset(self):
        self.ledger = BranchLedger()
        self.mutations = []
        self.last_label = "normal"
        self.events = []
        self._instance_n = 0
        self._open_instance = None

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
        return out

    def score_bonus(self, action, state, graph, ctx) -> float:
        if not self.enabled() or action is None:
            return 0.0
        sig = ctx.get("sig", "")
        node = graph.nodes.get(sig) if graph else None
        cluster = (node.cluster_id if node else "") or sig.split(":")[0]
        bonus = 0.0
        if is_hub(state) and is_branch_click(action, state):
            rec = self.ledger.hub(sig, cluster)
            rec.discovered.add(branch_key(cluster, action))
            key = branch_key(cluster, action)
            if key not in rec.started and key not in rec.completed:
                bonus += W_BRANCH_NOVELTY
        if self.mode in ("followup", "sequence") and self._is_followup(action):
            bonus += W_FOLLOWUP
        if self.ledger.returning and is_return_action(action, state):
            bonus += RETURN_BONUS
        if (self.mode == "sequence" and self.ledger.commitment_left > 0
                and not is_return_action(action, state)):
            bonus += 0.25
        return bonus

    def pick_override(self, actions, state, graph, ctx):
        if not self.enabled() or not actions:
            return None
        sig = ctx.get("sig", "")
        if self.mode == "sequence" and self.ledger.returning:
            for a in actions:
                if is_return_action(a, state):
                    self.last_label = "return_hub"
                    return a
        if self.mode in ("followup", "sequence") and self.ledger.commitment_left > 0:
            for a in actions:
                if self._is_followup(a) and not is_return_action(a, state):
                    self.last_label = "sequence_followup"
                    return a
        if self.mode == "sequence" and self.ledger.commitment_left > 0:
            return None  # additive score keeps us in-branch
        if is_hub(state):
            node = graph.nodes.get(sig) if graph else None
            cluster = (node.cluster_id if node else "") or sig.split(":")[0]
            rec = self.ledger.hub(sig, cluster)
            rec.first_seen = rec.first_seen or ctx.get("step_index", 0)
            untried = []
            for a in actions:
                if not is_branch_click(a, state):
                    continue
                key = branch_key(cluster, a)
                rec.discovered.add(key)
                if key not in rec.started and key not in rec.completed:
                    untried.append(a)
            if untried:
                self.last_label = "branch"
                return untried[0]
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
            if self.mode == "sequence":
                self.ledger.commitment_left = BRANCH_HORIZON
            self.ledger.returning = False

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

        if self.mode in ("followup", "sequence"):
            self._record_mutation(sig, action, state, new_state, relation, step)

        if self.last_label == "sequence_followup":
            self.ledger.followup_actions += 1
            self._emit("followup", step, sig, cluster,
                       self.ledger.active_branch)

        expire = False
        terminal_reason = None
        if crashed:
            expire = True
            terminal_reason = "crash"
        elif findings and self.mode == "sequence":
            expire = True
            terminal_reason = "finding"
        if self.mode == "sequence" and self.ledger.commitment_left <= 0 and self.ledger.active_branch:
            expire = True
            if terminal_reason is None:
                terminal_reason = "horizon"
        if self.mode == "sequence" and relation not in (NEW, SIMILAR) and not findings:
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
