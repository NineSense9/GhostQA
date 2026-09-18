"""Model gateway: pluggable LLM access with a deterministic Mock for tests/experiments.

Real providers (DeepSeek/Qwen/OpenAI-compatible) plug in later via the same
interface; every call is counted so token cost is a first-class experiment metric.
"""
from __future__ import annotations


class ModelGateway:
    """Interface used by policies/oracles. All methods must be deterministic
    in Mock implementations (seeded experiments require reproducibility)."""

    def score_actions(self, state_brief: str, action_briefs: list,
                      spec_brief: str = "") -> dict:
        """Return {index: 0..1 semantic value score} for candidate actions."""
        raise NotImplementedError

    def choose_action(self, state_brief: str, action_briefs: list) -> int:
        """Naive LLM-only policy hook: pick one action index."""
        raise NotImplementedError


HIGH_VALUE_KEYWORDS = ["购物车", "结算", "支付", "删除", "提交", "清空", "注册", "购买",
                       "cart", "checkout", "pay", "delete", "submit", "clear", "buy"]
LOW_VALUE_KEYWORDS = ["帮助", "关于", "help", "about"]


class MockLLM(ModelGateway):
    """Deterministic keyword-based stand-in. Counts calls & pseudo-tokens."""

    def __init__(self):
        self.calls = 0
        self.pseudo_tokens = 0

    def _score_one(self, brief: str) -> float:
        b = brief.lower()
        if any(k in b for k in HIGH_VALUE_KEYWORDS):
            return 0.9
        if any(k in b for k in LOW_VALUE_KEYWORDS):
            return 0.1
        return 0.45

    def score_actions(self, state_brief: str, action_briefs: list,
                      spec_brief: str = "") -> dict:
        self.calls += 1
        self.pseudo_tokens += (len(state_brief) + sum(len(a) for a in action_briefs)
                               + len(spec_brief)) // 4
        return {i: self._score_one(a) for i, a in enumerate(action_briefs)}

    def choose_action(self, state_brief: str, action_briefs: list) -> int:
        scores = self.score_actions(state_brief, action_briefs)
        return max(scores, key=scores.get)


class NullLLM(ModelGateway):
    """LLM disabled (ablation / offline fallback)."""
    calls = 0
    pseudo_tokens = 0

    def score_actions(self, state_brief, action_briefs, spec_brief=""):
        return {i: 0.5 for i in range(len(action_briefs))}

    def choose_action(self, state_brief, action_briefs):
        return 0
