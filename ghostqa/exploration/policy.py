"""Exploration policies: baselines (Random/DFS/BFS/LLM-naive) + GhostPolicy v1.2.

GhostPolicy scoring (local):
    Score(s,a) = w1*Novelty + w2*UCB + w3*Semantics(LLM, slow-path) + w4*Risk
                 - w5*Repetition - w6*Cost
Global (v1.2): FrontierPlanner may request reset+replay to a non-current node.

Program terms run every step; LLM only on gated slow-path.
Cache key is the exact state_id (cluster+variant), never the structural
signature alone.
"""
from __future__ import annotations

import math
import random

from ..state.models import Action
from ..agent.gateway import NullLLM
from .planner import FrontierPlanner

RISK_KEYWORDS = ["支付", "删除", "提交", "结算", "清空", "注册", "购买",
                 "pay", "delete", "submit", "clear", "checkout", "buy"]


class Policy:
    name = "base"

    def select(self, graph, state, actions: list, ctx: dict) -> Action:
        raise NotImplementedError

    def reset(self):
        pass


class RandomPolicy(Policy):
    name = "monkey"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def select(self, graph, state, actions, ctx):
        return self.rng.choice(actions)


class DFSPolicy(Policy):
    """Depth-first: prefer last-inserted untried action; backtrack when exhausted."""
    name = "dfs"

    def select(self, graph, state, actions, ctx):
        keys = [a.key() for a in actions]
        untried = set(graph.untried_actions(ctx["sig"], keys))
        for a in reversed(actions):            # stack-like: newest first
            if a.key() in untried and a.type != "back":
                return a
        for a in actions:
            if a.type == "back":
                return a
        return actions[-1]


class BFSPolicy(Policy):
    """Breadth-first: prefer first-inserted untried action; backtrack when exhausted."""
    name = "bfs"

    def select(self, graph, state, actions, ctx):
        keys = [a.key() for a in actions]
        untried = set(graph.untried_actions(ctx["sig"], keys))
        for a in actions:                      # queue-like: oldest first
            if a.key() in untried and a.type != "back":
                return a
        for a in actions:
            if a.type == "back":
                return a
        return actions[0]


class LLMNaivePolicy(Policy):
    """LLM-only baseline: asks the model every step, no state graph reasoning."""
    name = "llm_naive"

    def __init__(self, llm):
        self.llm = llm

    def select(self, graph, state, actions, ctx):
        briefs = [a.brief() for a in actions]
        idx = self.llm.choose_action(ctx.get("state_brief", ""), briefs)
        return actions[max(0, min(idx, len(actions) - 1))]


DEFAULT_WEIGHTS = {
    "w1_novelty": 1.0,
    "w2_ucb": 0.8,
    "w3_semantic": 0.8,        # v1.1: lowered - LLM re-ranks, not dominates
    "w4_risk": 0.6,
    "w5_repetition": 1.0,
    "w6_cost": 0.5,
    "slow_path_interval": 15,  # v1.1: long backstop only; gates do the real work
    "slow_path_topk": 5,
    "slow_path_epsilon": 0.1,
}

ACTION_COST = {"click": 0.05, "input": 0.10, "back": 0.02, "wait": 0.01, "navigate": 0.02}


class GhostPolicy(Policy):
    """GhostQA Exploration Policy v1.2: local scoring + global frontier."""
    name = "ghost"

    def __init__(self, llm=None, weights: dict = None,
                 use_frontier: bool = True, use_semantic_state: bool = True):
        self.llm = llm or NullLLM()
        self.w = dict(DEFAULT_WEIGHTS)
        if weights:
            self.w.update(weights)
        self._semantic_cache: dict = {}      # exact state_id -> {action_key: score}
        self.use_llm = llm is not None
        self.use_frontier = use_frontier
        self.use_semantic_state = use_semantic_state
        self.planner = FrontierPlanner() if use_frontier else None
        self._last_relocate_step = -999

    def reset(self):
        self._semantic_cache = {}
        self._last_relocate_step = -999

    # ---- program-computed terms ----
    def _novelty(self, graph, sig: str, action: Action) -> float:
        edge = graph.edge(sig, action.key())
        if edge is None:
            return 0.8                        # never tried: optimistic
        return 0.05 if graph.nodes.get(edge.dst) else 0.8

    def _ucb(self, graph, sig: str, action: Action) -> float:
        return 1.0 / math.sqrt(1 + graph.edge_count(sig, action.key()))

    def _risk(self, graph, state, action: Action) -> float:
        score = 0.0
        text = ""
        for el in state.elements:
            if el.eid == action.target_eid:
                text = el.text.lower()
                break
        if any(k in text for k in RISK_KEYWORDS):
            score += 0.4
        if action.type == "input":
            score += 0.2
        node = graph.nodes.get(state.meta.get("sig", ""))
        if node and "had_l2_finding" in node.flags:
            score += 0.3
        return min(score, 1.0)

    def _repetition(self, action: Action, ctx: dict) -> float:
        recent = ctx.get("recent_action_keys", [])
        return recent.count(action.key()) * 0.2

    def _program_score(self, graph, state, action, ctx) -> float:
        sig = ctx["sig"]
        score = (self.w["w1_novelty"] * self._novelty(graph, sig, action)
                 + self.w["w2_ucb"] * self._ucb(graph, sig, action)
                 + self.w["w4_risk"] * self._risk(graph, state, action)
                 - self.w["w5_repetition"] * self._repetition(action, ctx)
                 - self.w["w6_cost"] * ACTION_COST.get(action.type, 0.05))
        # Backtracking is for exhausted nodes; untried on-page actions win.
        if action.type == "back":
            keys = [a.key() for a in ctx.get("candidate_actions", [])] or None
            if keys is None:
                score -= 0.35
            else:
                untried = graph.untried_actions(sig, keys)
                if any(not k.startswith("back:") for k in untried):
                    score -= 0.35
        return score

    # ---- v1.1 gates: LLM is consulted only when it adds information ----
    def _gate_reasons(self, program_scores, ranked, ctx) -> list:
        reasons = []
        if len(ranked) >= 2 and abs(
                program_scores[ranked[0].key()] - program_scores[ranked[1].key()]
        ) < self.w["slow_path_epsilon"]:
            reasons.append("uncertainty")          # UncertaintyGate
        if ctx.get("entered_new_state", False) or ctx.get("entered_new_variant", False):
            reasons.append("novel_state")          # NovelStateGate (cluster or variant)
        if ctx.get("cycle_detected", False):
            reasons.append("stuck")                # StuckGate
        spec_brief = ctx.get("spec_brief", "")
        if spec_brief:
            text = (ctx.get("state_brief", "") + " "
                    + " ".join(a.brief() for a in ranked[:3])).lower()
            if any(kw in text for kw in
                   ("cart", "total", "stock", "register", "login", "购物车",
                    "总价", "库存", "注册", "登录", "结算", "支付",
                    "归档", "权限", "成员", "项目", "任务", "优惠", "账单",
                    "archive", "permission", "member", "project", "task")):
                reasons.append("spec_relevance")   # SpecRelevanceGate
        if ctx.get("step_index", 0) % int(self.w["slow_path_interval"]) == 0:
            reasons.append("interval")             # long backstop
        return reasons

    def maybe_relocate(self, graph, state, actions, ctx):
        """Return a frontier sig to restore, or None to stay here.

        Relocate when the current page is locally exhausted, or a distant
        frontier scores clearly higher than the best local program score.
        """
        if not self.use_frontier or self.planner is None:
            return None
        step = ctx.get("step_index", 0)
        if step < 8:
            return None
        if step - self._last_relocate_step < 8:
            return None
        sig = ctx["sig"]
        keys = [a.key() for a in actions]
        local_untried = [k for k in graph.untried_actions(sig, keys)
                         if not k.startswith("back:")]
        # Stay on a page that still has untried work. Relocate is a jump
        # out of an exhausted node, not a pre-emption of local exploration.
        if local_untried:
            return None
        remaining = ctx.get("budget", 10**9) - step
        target = self.planner.select(graph, sig, remaining_budget=remaining)
        if target is None or target.sig == sig:
            return None
        path = graph.shortest_path(graph.start_sig, target.sig)
        if path is None:
            return None
        if len(path) >= remaining:
            return None
        self._last_relocate_step = step
        ctx["last_relocate"] = {
            "from": sig, "to": target.sig, "score": round(target.score, 3),
            "path_len": target.path_len, "reasons": target.reasons,
        }
        return target.sig

    def _semantic_scores(self, graph, state, topk_actions, ctx) -> dict:
        """Score ONLY the top-k candidates; other actions are unaffected."""
        sig = ctx["sig"]          # exact state_id (cluster:variant)
        if sig in self._semantic_cache:
            return self._semantic_cache[sig]
        briefs = [a.brief() for a in topk_actions]
        raw = self.llm.score_actions(ctx.get("state_brief", ""), briefs,
                                     ctx.get("spec_brief", ""))
        scores = {a.key(): raw.get(i, 0.5) for i, a in enumerate(topk_actions)}
        self._semantic_cache[sig] = scores
        return scores

    def select(self, graph, state, actions, ctx) -> Action:
        ctx = dict(ctx)
        ctx["candidate_actions"] = actions
        program_scores = {a.key(): self._program_score(graph, state, a, ctx)
                          for a in actions}
        ranked = sorted(actions, key=lambda a: -program_scores[a.key()])

        reasons = self._gate_reasons(program_scores, ranked, ctx) \
            if self.use_llm else []
        if not reasons:
            return ranked[0]

        topk = ranked[: int(self.w["slow_path_topk"])]
        sem = self._semantic_scores(graph, state, topk, ctx)
        best = max(topk, key=lambda a: program_scores[a.key()]
                   + self.w["w3_semantic"] * sem.get(a.key(), 0.5))
        ctx["last_decision"] = {
            "trigger": reasons,
            "candidates": {a.brief(): round(program_scores[a.key()]
                           + self.w["w3_semantic"] * sem.get(a.key(), 0.5), 3)
                           for a in topk},
            "chosen": best.brief(),
            "program_top": ranked[0].brief(),
        }
        return best
