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


# ---------------------------------------------------------------------------
# Real provider: OpenAI-compatible (DeepSeek / Qwen / OpenAI / proxies)
# ---------------------------------------------------------------------------
import json
import os
import time
import urllib.request
import urllib.error


class OpenAICompatibleGateway(ModelGateway):
    """Production LLM gateway.

    Env vars:
        GHOSTQA_MODEL_BASE_URL   e.g. https://api.deepseek.com/v1
        GHOSTQA_MODEL_API_KEY
        GHOSTQA_MODEL_NAME       e.g. deepseek-chat / qwen-plus

    Properties: timeout, retry, response JSON validation, token & latency
    accounting, prompt cache, and **failure fallback**: after repeated
    failures the gateway degrades (self.degraded=True) and returns neutral
    scores so the policy silently behaves as its no-LLM variant instead of
    aborting the whole test run.

    Only decision summaries (scores) are ever requested/kept - the model is
    asked for bare JSON, never for chain-of-thought.
    """

    def __init__(self, base_url: str = None, api_key: str = None,
                 model: str = None, timeout: float = 20.0, max_retries: int = 2):
        self.base_url = (base_url or os.environ.get("GHOSTQA_MODEL_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("GHOSTQA_MODEL_API_KEY", "")
        self.model = model or os.environ.get("GHOSTQA_MODEL_NAME", "")
        self.timeout = timeout
        self.max_retries = max_retries
        self.calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_latency_ms = 0.0
        self.degraded = False
        self._cache: dict = {}
        self._fail_streak = 0

    @property
    def pseudo_tokens(self):
        return self.prompt_tokens + self.completion_tokens

    @property
    def available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model) and not self.degraded

    # ---- HTTP ----
    def _chat(self, prompt: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 400,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.api_key})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            self.total_latency_ms += (time.time() - t0) * 1000
            data = json.loads(resp.read().decode("utf-8"))
        usage = data.get("usage", {})
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        return data["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_scores(text: str, n: int):
        """Extract a JSON {"scores": [...]} with exactly n numbers in [0,1]."""
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            obj = json.loads(text[start:end + 1])
            scores = obj["scores"]
            if not isinstance(scores, list) or len(scores) != n:
                return None
            return [max(0.0, min(1.0, float(s))) for s in scores]
        except (ValueError, TypeError, KeyError):
            return None

    def _scored(self, state_brief: str, action_briefs: list, spec_brief: str):
        key = (state_brief, tuple(action_briefs), spec_brief)
        if key in self._cache:
            return self._cache[key]
        prompt = (
            "你是软件测试专家。给定当前页面摘要、候选测试动作和需求规格摘要，"
            "为每个候选动作估计其发现缺陷的价值（0~1）。"
            "只输出 JSON：{\"scores\": [..]}，不要输出任何解释。\n"
            f"页面：{state_brief}\n"
            f"需求规格：{spec_brief or '（无）'}\n"
            "候选动作：\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(action_briefs)))
        result = None
        for _ in range(1 + self.max_retries):
            try:
                self.calls += 1
                result = self._parse_scores(self._chat(prompt), len(action_briefs))
                if result is not None:
                    break
            except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
                continue
        if result is None:
            self._fail_streak += 1
            if self._fail_streak >= 3:
                self.degraded = True        # fallback: behave as no-LLM policy
            result = [0.5] * len(action_briefs)
        else:
            self._fail_streak = 0
        self._cache[key] = result
        return result

    # ---- ModelGateway interface ----
    def score_actions(self, state_brief, action_briefs, spec_brief=""):
        if not self.available:
            return {i: 0.5 for i in range(len(action_briefs))}
        scores = self._scored(state_brief, action_briefs, spec_brief)
        return {i: scores[i] for i in range(len(action_briefs))}

    def choose_action(self, state_brief, action_briefs):
        scores = self.score_actions(state_brief, action_briefs)
        return max(scores, key=scores.get)
