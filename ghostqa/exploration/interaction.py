"""Interaction-level action abstraction (v0.3.1).

A text field with 6 payloads is ONE interaction opportunity, not six
frontier slots. Payloads are an internal budget of that opportunity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..state.models import GUIState, Action, UIElement
from ..executor.base import DEFAULT_INPUT_VOCAB


PROGRESS_KEYWORDS = (
    "下一步", "继续", "登录", "提交", "创建", "确认", "完成", "保存",
    "进入", "演示登录", "新建", "打开项目", "结算", "支付", "注册",
    "next", "continue", "login", "submit", "create", "confirm", "finish",
    "save", "enter", "sign in", "signup", "register", "checkout", "pay",
)

DISTRACTOR_KEYWORDS = (
    "帮助", "关于", "文档", "设置", "历史", "报表", "日志", "返回",
    "help", "about", "docs", "settings", "history", "report", "back",
)


@dataclass(frozen=True)
class InteractionOpportunity:
    kind: str                    # click | input | back
    eid: Optional[str]
    label: str
    field_type: str = "unknown"
    progress: bool = False

    def key(self) -> str:
        if self.kind == "back":
            return "back"
        return f"{self.kind}:{self.eid or ''}"


def interaction_key(action: Action) -> str:
    if action.type == "back":
        return "back"
    if action.type == "input":
        return f"input:{action.target_eid or ''}"
    return f"{action.type}:{action.target_eid or ''}"


def interaction_key_from_str(action_key: str) -> str:
    parts = (action_key or "").split(":")
    typ = parts[0] if parts else ""
    eid = parts[1] if len(parts) > 1 else ""
    if typ == "back":
        return "back"
    if typ == "input":
        return f"input:{eid}"
    return f"{typ}:{eid}"


def classify_field(el: UIElement) -> str:
    """Programmatic field type from visible attributes only. No LLM."""
    blob = " ".join([
        getattr(el, "input_type", "") or "",
        getattr(el, "placeholder", "") or "",
        getattr(el, "name", "") or "",
        getattr(el, "aria_label", "") or "",
        el.eid or "",
        el.text or "",
        el.role or "",
    ]).lower()
    itype = (getattr(el, "input_type", "") or "").lower()
    if itype in ("password",) or "password" in blob or "密码" in blob:
        return "password"
    if itype in ("email",) or "email" in blob or "邮箱" in blob:
        return "email"
    if itype in ("number", "range") or any(k in blob for k in ("qty", "数量", "stock", "库存", "price", "价格")):
        return "number"
    if itype in ("search",) or "search" in blob or "搜索" in blob:
        return "search"
    if any(k in blob for k in ("user", "username", "用户", "帐号", "账号")):
        return "username"
    if itype in ("text", "tel", "url", ""):
        return "text"
    return "unknown"


def is_progress_element(el: UIElement) -> bool:
    blob = f"{el.text} {el.eid} {el.role}".lower()
    if any(k.lower() in blob for k in DISTRACTOR_KEYWORDS):
        # 返回/帮助 are not workflow progress even if they contain 入
        if any(k.lower() in blob for k in ("帮助", "关于", "文档", "设置", "help", "about", "docs", "settings")):
            return False
    return any(k.lower() in blob for k in PROGRESS_KEYWORDS)


def is_progress_action(action: Action, state: GUIState) -> bool:
    if action.type != "click":
        return False
    for el in state.elements:
        if el.eid == action.target_eid:
            return is_progress_element(el)
    blob = (action.target_eid or "").lower()
    return any(k.lower() in blob for k in PROGRESS_KEYWORDS)


def opportunities(state: GUIState, can_back: bool = True) -> list:
    out = []
    for el in state.elements:
        if not el.enabled:
            continue
        if el.kind == "click":
            out.append(InteractionOpportunity(
                kind="click", eid=el.eid, label=el.text,
                progress=is_progress_element(el)))
        elif el.kind == "input":
            out.append(InteractionOpportunity(
                kind="input", eid=el.eid, label=el.text,
                field_type=classify_field(el)))
    if can_back:
        out.append(InteractionOpportunity(kind="back", eid=None, label="back"))
    return out


def diagnose_action_space(state: GUIState, can_back: bool = True,
                          vocab=None) -> dict:
    vocab = vocab if vocab is not None else DEFAULT_INPUT_VOCAB
    n_click = n_input_el = 0
    for el in state.elements:
        if not el.enabled:
            continue
        if el.kind == "click":
            n_click += 1
        elif el.kind == "input":
            n_input_el += 1
    n_back = 1 if can_back else 0
    raw_input = n_input_el * len(vocab)
    opps = opportunities(state, can_back)
    return {
        "click_actions": n_click,
        "input_elements": n_input_el,
        "raw_input_actions": raw_input,
        "back_actions": n_back,
        "total_actions": n_click + raw_input + n_back,
        "unique_interaction_targets": len(opps),
        "progress_opportunities": sum(1 for o in opps if o.progress),
    }


def form_progress(state: GUIState, tried_fields: set) -> dict:
    inputs = [e for e in state.elements if e.kind == "input" and e.enabled]
    submits = [e for e in state.elements
               if e.kind == "click" and e.enabled and is_progress_element(e)]
    tested = sum(1 for e in inputs if e.eid in tried_fields)
    filled_obs = 0
    for e in inputs:
        key = f"input_{e.eid}"
        if state.obs.get(key):
            filled_obs += 1
    return {
        "visible_inputs": len(inputs),
        "tested_input_fields": tested,
        "filled_inputs": max(tested, filled_obs),
        "submit_candidates": [e.eid for e in submits],
        "ready": (not inputs) or tested >= len(inputs) or filled_obs >= len(inputs),
    }


def workflow_stage(url: str) -> int:
    """Visible-URL heuristic. Never reads bug manifests."""
    u = (url or "").lower()
    stage = 0
    if any(k in u for k in ("login", "register", "注册", "登录")):
        stage = max(stage, 1)
    if any(k in u for k in ("dashboard", "工作台")):
        stage = max(stage, 2)
    if "wizard" in u:
        stage = max(stage, 3)
    if any(k in u for k in ("project", "members", "tasks", "billing",
                            "项目", "成员", "任务", "账单")):
        stage = max(stage, 4)
    return stage
