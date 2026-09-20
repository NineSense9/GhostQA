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
            "hub_count": len(self.hubs),
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


class SequenceController:
    """modes: off | branch | followup | sequence"""

    def __init__(self, mode: str = "off"):
        self.mode = mode
        self.ledger = BranchLedger()
        self.mutations: list = []
        self.last_label = "normal"

    def reset(self):
        self.ledger = BranchLedger()
        self.mutations = []
        self.last_label = "normal"

    def enabled(self) -> bool:
        return self.mode not in ("", "off", None)

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

        if was_hub and is_branch_click(action, state):
            rec = self.ledger.hub(sig, cluster)
            key = branch_key(cluster, action)
            rec.discovered.add(key)
            if key in rec.started:
                self.ledger.repeats += 1
            else:
                rec.started.add(key)
                self.ledger.started_total += 1
                self.ledger.sequences_started += 1
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

        expire = False
        if crashed or (findings and self.mode == "sequence"):
            expire = True
        if self.mode == "sequence" and self.ledger.commitment_left <= 0 and self.ledger.active_branch:
            expire = True
        if self.mode == "sequence" and relation not in (NEW, SIMILAR) and not findings:
            if self.ledger.commitment_left <= 0:
                expire = True

        if expire and self.ledger.active_branch and not self.ledger.returning:
            self.ledger.returning = True
            self.ledger.commitment_left = 0

        if self.ledger.returning and new_state is not None:
            self.ledger.return_attempts += 1
            dst_cluster = ""
            if graph and new_sig in graph.nodes:
                dst_cluster = graph.nodes[new_sig].cluster_id
            if (new_sig == self.ledger.parent_hub_sig
                    or (dst_cluster and dst_cluster == self.ledger.parent_hub_cluster)):
                self._complete_branch()

        if self.last_label == "return_hub":
            self.ledger.return_attempts += 1

        self.mutations = [m for m in self.mutations if m.ttl > 0]
        for m in self.mutations:
            m.ttl -= 1

    def _complete_branch(self):
        key = self.ledger.active_branch
        parent = self.ledger.parent_hub_sig
        if key and parent in self.ledger.hubs:
            self.ledger.hubs[parent].completed.add(key)
            self.ledger.hubs[parent].returned.add(key)
        if key:
            self.ledger.completed_total += 1
            self.ledger.sequences_completed += 1
            self.ledger.seq_lens.append(self.ledger._seq_len)
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
