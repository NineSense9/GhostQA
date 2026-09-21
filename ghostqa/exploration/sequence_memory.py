"""Contextual workflow memory for sequence exploration (v0.3.6).

Structural hub identity is cluster_id. Semantic context is a visible
obs/element delta, never variant_key and never a full state snapshot.
Does not read manifests, hidden browser storage, or backend ground truth.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..state.signature import variant_facts

CONTEXT_RETEST_BUDGET = 1
CONTEXTUAL_NOVELTY_BONUS = 0.45
W_CONTEXT_RETEST = 0.40
MUTATION_REFRESH = 1
MAX_SEQUENCE_ACTIONS = 6
CROSS_VIEW_BONUS = 0.40
FACT_TTL = 10
PRODUCTIVE_WINDOW = 3

# Generic risk tokens (unicode-safe). Not DeepBench-specific labels.
RISK_TOKENS = {
    "delete", "remove", "destroy", "archive", "unarchive", "pay", "purchase",
    "submit", "clear", "register", "login", "drop", "disable", "enable",
    "restore", "purge",
    "删除", "归档", "取消归档", "支付", "提交", "清空", "注册", "购买", "登录",
    "停用", "恢复", "销毁",
}

_TOKEN_RE = re.compile(r"[0-9a-zA-Z\u0080-\uffff]+", re.UNICODE)


def tokenize(text: str) -> set:
    if not text:
        return set()
    out = set()
    for part in _TOKEN_RE.findall(str(text).lower()):
        out.add(part)
        for piece in re.split(r"[_\-]+", part):
            if len(piece) >= 2:
                out.add(piece)
    return out


def token_overlap(a: set, b: set) -> int:
    if not a or not b:
        return 0
    return len(a & b)


def action_tokens(action, state=None) -> set:
    parts = set()
    if action is None:
        return parts
    parts |= tokenize(getattr(action, "type", "") or "")
    parts |= tokenize(getattr(action, "target_eid", "") or "")
    if state is not None:
        eid = getattr(action, "target_eid", None)
        for el in state.elements:
            if el.eid == eid:
                parts |= tokenize(el.text or "")
                parts |= tokenize(el.role or "")
                parts |= tokenize(el.eid or "")
                break
    return parts


def is_risk_action(action, state=None) -> bool:
    toks = action_tokens(action, state)
    blob = " ".join(sorted(toks))
    return any(r in blob or r in toks for r in RISK_TOKENS)


def facts_map(state) -> dict:
    if state is None:
        return {}
    return {k: v for k, v in variant_facts(state)}


def enabled_eids(state) -> set:
    if state is None:
        return set()
    return {e.eid for e in state.elements if e.enabled}


@dataclass
class ContextDelta:
    step: int = 0
    action_key: str = ""
    action_text: str = ""
    changed_obs: tuple = ()  # ((key, before, after), ...)
    new_eids: tuple = ()
    removed_eids: tuple = ()
    source_cluster: str = ""
    dest_cluster: str = ""

    def tokens(self) -> set:
        out = tokenize(self.action_key) | tokenize(self.action_text)
        for k, before, after in self.changed_obs:
            out |= tokenize(k) | tokenize(before) | tokenize(after)
        for eid in self.new_eids + self.removed_eids:
            out |= tokenize(eid)
        return out

    def context_id(self, epoch: int) -> str:
        keys = ",".join(k for k, _, _ in self.changed_obs[:8])
        return f"e{epoch}:{keys}:{self.action_key}"

    def meaningful(self) -> bool:
        return bool(self.changed_obs or self.new_eids or self.removed_eids)


def make_delta(step, action, state, new_state, source_cluster="", dest_cluster="") -> ContextDelta:
    before = facts_map(state)
    after = facts_map(new_state)
    changed = []
    for k in sorted(set(before) | set(after)):
        if before.get(k) != after.get(k):
            changed.append((k, before.get(k, ""), after.get(k, "")))
    old_e = enabled_eids(state)
    new_e = enabled_eids(new_state)
    text = ""
    if action is not None and state is not None:
        for el in state.elements:
            if el.eid == action.target_eid:
                text = el.text or ""
                break
    return ContextDelta(
        step=step,
        action_key=action.key() if action is not None else "",
        action_text=text,
        changed_obs=tuple(changed),
        new_eids=tuple(sorted(new_e - old_e)),
        removed_eids=tuple(sorted(old_e - new_e)),
        source_cluster=source_cluster or "",
        dest_cluster=dest_cluster or "",
    )


@dataclass
class BranchHistory:
    branch_key: str
    attempts: int = 0
    last_test_step: int = 0
    last_test_epoch: int = 0
    tested_context_ids: set = field(default_factory=set)
    findings: int = 0
    returned: bool = False
    last_outcome: str = ""


@dataclass
class RecentVisibleFact:
    key: str
    before: str = ""
    after: str = ""
    source_cluster: str = ""
    action_key: str = ""
    step: int = 0
    ttl: int = FACT_TTL


@dataclass
class HubMem:
    cluster_id: str
    variants_seen: set = field(default_factory=set)
    branches: dict = field(default_factory=dict)  # branch_key -> BranchHistory
    context_epoch: int = 0
    recent_deltas: list = field(default_factory=list)
    epoch_retests: int = 0
    last_delta: ContextDelta | None = None
    observed_fact_keys: set = field(default_factory=set)


class StructuralHubMemory:
    def __init__(self):
        self.hubs: dict = {}
        self.facts: list = []
        self.cluster_fact_keys: dict = {}  # cluster -> set of obs keys

    def hub(self, cluster_id: str) -> HubMem:
        cid = cluster_id or "?"
        rec = self.hubs.get(cid)
        if rec is None:
            rec = HubMem(cluster_id=cid)
            self.hubs[cid] = rec
        return rec

    def branch(self, cluster_id: str, bkey: str) -> BranchHistory:
        h = self.hub(cluster_id)
        rec = h.branches.get(bkey)
        if rec is None:
            rec = BranchHistory(branch_key=bkey)
            h.branches[bkey] = rec
        return rec

    def note_variant(self, cluster_id: str, sig: str):
        if cluster_id:
            self.hub(cluster_id).variants_seen.add(sig)

    def note_facts(self, cluster_id: str, state):
        if not cluster_id or state is None:
            return
        keys = set(facts_map(state))
        self.hub(cluster_id).observed_fact_keys |= keys
        self.cluster_fact_keys.setdefault(cluster_id, set()).update(keys)

    def apply_delta(self, cluster_id: str, delta: ContextDelta) -> bool:
        """Advance epoch only on meaningful business-state mutation."""
        if not cluster_id or delta is None or not delta.meaningful():
            return False
        h = self.hub(cluster_id)
        h.context_epoch += 1
        h.epoch_retests = 0
        h.last_delta = delta
        h.recent_deltas = (h.recent_deltas + [delta])[-5:]
        for k, before, after in delta.changed_obs:
            self.facts.append(RecentVisibleFact(
                key=k, before=str(before), after=str(after),
                source_cluster=delta.source_cluster or cluster_id,
                action_key=delta.action_key, step=delta.step, ttl=FACT_TTL))
        self.facts = self.facts[-24:]
        return True

    def tick_facts(self):
        self.facts = [f for f in self.facts if f.ttl > 0]
        for f in self.facts:
            f.ttl -= 1

    def retest_eligible(self, cluster_id: str, bkey: str, action, state) -> bool:
        h = self.hub(cluster_id)
        hist = h.branches.get(bkey)
        if hist is None or hist.attempts == 0:
            return False
        if h.context_epoch <= hist.last_test_epoch:
            return False
        if h.epoch_retests >= CONTEXT_RETEST_BUDGET:
            return False
        delta = h.last_delta
        if hist.last_outcome in ("lost_parent", "") and hist.attempts > 0:
            incomplete = hist.last_outcome in ("lost_parent", "")
        else:
            incomplete = hist.last_outcome not in ("returned", "finding")
        relevant = False
        if delta is not None:
            relevant = token_overlap(action_tokens(action, state), delta.tokens()) > 0
        risk = is_risk_action(action, state)
        newly = False
        if state is not None and action is not None:
            eid = action.target_eid
            newly = bool(eid and eid in (delta.new_eids if delta else ()))
        return bool(relevant or risk or incomplete or newly)

    def cross_view_relevant(self, dest_cluster: str, delta: ContextDelta | None) -> bool:
        if not dest_cluster or delta is None:
            return False
        seen = self.cluster_fact_keys.get(dest_cluster) or set()
        if not seen:
            return False
        changed = {k for k, _, _ in delta.changed_obs}
        if changed & seen:
            return True
        dt = delta.tokens()
        sk = set()
        for k in seen:
            sk |= tokenize(k)
        return token_overlap(dt, sk) > 0
