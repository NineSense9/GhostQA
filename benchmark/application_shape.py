"""Application-shape descriptors and static topology (v0.3.8).

Read-only analysis. Does not change GhostPolicy / SequenceController.
Does not feed descriptors into scoring.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict, deque

from ghostqa.exploration.interaction import (
    DISTRACTOR_KEYWORDS, PROGRESS_KEYWORDS,
)
from ghostqa.exploration.sequence import (
    HUB_MIN_BRANCHES, RETURN_WORDS, branch_clicks, is_branch_click, is_hub,
    is_return_action,
)
from ghostqa.state.models import Action, GUIState, UIElement


def label_text(text: str) -> str:
    blob = (text or "").lower()
    if any(w in blob for w in RETURN_WORDS):
        return "return"
    if any(k.lower() in blob for k in DISTRACTOR_KEYWORDS):
        return "distractor"
    if any(k.lower() in blob for k in PROGRESS_KEYWORDS):
        return "progress"
    return "branch"


def el(eid, text, role="link"):
    return UIElement(eid, role, text, kind="click")


def shop_detail_state() -> GUIState:
    return GUIState(
        app="buggy-shop", url="/detail.html", title="商品详情·苹果",
        elements=(
            el("btn_add", "加入购物车", "button"),
            el("btn_fav", "收藏", "button"),
            el("btn_buy", "立即购买", "button"),
            el("back_list", "返回列表"),
        ), obs={"stock_num": "2"})


def shop_home_state() -> GUIState:
    return GUIState(
        app="buggy-shop", url="/index.html", title="幽灵商城·首页",
        elements=(
            el("products", "商品列表"),
            el("cart", "购物车"),
            el("register", "注册"),
            el("login", "登录"),
            el("profile", "个人中心"),
            el("promo", "活动专区"),
            UIElement("search_box", "input", "", kind="input"),
            el("search_btn", "搜索", "button"),
        ), obs={})


def flow_home_state() -> GUIState:
    return GUIState(
        app="buggy-flow", url="/index.html", title="BuggyFlow 项目工作台",
        elements=(
            el("nav_login", "登录"),
            el("nav_register", "注册"),
            el("nav_help", "帮助中心"),
            el("nav_about", "关于"),
            el("nav_settings", "系统设置"),
        ), obs={})


def flow_settings_state() -> GUIState:
    return GUIState(
        app="buggy-flow", url="/settings.html", title="系统设置",
        elements=(
            el("nav_home", "首页"),
            el("nav_reports", "报表"),
            el("nav_history", "操作历史"),
            el("nav_changelog", "更新日志"),
            el("btn_toggle_notify", "切换通知", "button"),
            el("btn_save_settings", "保存设置", "button"),
        ), obs={})


def flow_changelog_state() -> GUIState:
    return GUIState(
        app="buggy-flow", url="/changelog.html", title="更新日志",
        elements=(
            el("nav_settings", "系统设置"),
            el("btn_changelog_detail", "查看详情", "button"),
        ), obs={})


def flow_billing_state(qty="1") -> GUIState:
    return GUIState(
        app="buggy-flow", url="/billing.html", title="账单",
        elements=(
            el("nav_project", "返回项目"),
            el("btn_qty_up", "增加数量", "button"),
            el("btn_qty_down", "减少数量", "button"),
            el("btn_coupon", "应用优惠", "button"),
            el("btn_export", "导出账单", "button"),
        ), obs={"bill_qty": qty, "bill_price": "100", "bill_price_expected": "100"})


# Declared from apps/buggy-shop/static/app.js (href / go("*.html") literals).
# Not a runtime-measured graph. Tests check these strings exist in app.js.
SOURCE_MODELED_SHOP_PAGES = {
    "index.html": ["products.html", "cart.html", "register.html",
                   "login.html", "profile.html", "promo.html"],
    "products.html": ["detail.html", "help.html", "index.html"],
    "detail.html": ["cart.html", "products.html"],
    "cart.html": ["checkout.html", "index.html"],
    "checkout.html": ["cart.html"],
    "register.html": ["index.html"],
    "login.html": ["profile.html", "index.html"],
    "profile.html": ["index.html"],
    "help.html": ["help2.html"],
    "help2.html": ["help.html"],
    "promo.html": [],
}

# Oracle unit-test constants (not a holdout-tuning input).
H2_INITIAL_QTY = 1
H2_CLICKS_TO_VIOLATE = 2

SHOP_HOME_LABELS = (
    "商品列表", "购物车", "注册", "登录", "个人中心", "活动专区", "搜索",
)
SHOP_DETAIL_LABELS = (
    "加入购物车", "收藏", "立即购买", "返回列表",
)


def html_string_literals(path: str) -> set:
    """Deterministic quoted-string harvest. Does not execute JS."""
    text = open(path, encoding="utf-8").read()
    return set(re.findall(r'["\']([^"\'\n]+)["\']', text))


def page_depths(pages: dict, start: str) -> dict:
    dist = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in pages.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def static_shop_descriptors() -> dict:
    pages = SOURCE_MODELED_SHOP_PAGES
    depths = page_depths(pages, "index.html")
    fanouts = [len(v) for v in pages.values()]
    n = len(pages)
    return {
        "n_pages": n,
        "mean_fanout": round(sum(fanouts) / n, 3) if n else 0,
        "max_fanout": max(fanouts) if fanouts else 0,
        "mean_shortest_path_depth": round(
            sum(depths.values()) / len(depths), 3) if depths else 0,
        "max_shortest_path_depth": max(depths.values()) if depths else 0,
        "shallow_leaf_pages": sorted(
            p for p, d in depths.items() if d <= 1 and len(pages.get(p, [])) <= 1),
        "page_depths": depths,
        "home_is_hub": is_hub(shop_home_state()),
        "home_branch_eids": [
            a.target_eid for a in branch_clicks(shop_home_state())],
    }


def graph_descriptors(nodes: list, edges: list, sequence_events: list = None) -> dict:
    """Descriptors from an observed StateGraph dump. Not used by policy."""
    n = len(nodes)
    urls = {nd.get("url", "") for nd in nodes}
    clusters = {nd.get("cluster_id", "") for nd in nodes}
    start = ""
    for nd in nodes:
        if nd.get("first_seen_step") == 1 or not start:
            start = nd.get("sig", "")
            if nd.get("first_seen_step") == 1:
                break
    adj = defaultdict(list)
    for e in edges:
        adj[e.get("src")].append(e.get("dst"))
    dist = {}
    if start:
        dist[start] = 0
        q = deque([start])
        while q:
            u = q.popleft()
            for v in adj.get(u, []):
                if v not in dist:
                    dist[v] = dist[u] + 1
                    q.append(v)
    depths = list(dist.values()) or [0]
    fanouts = [len(adj[nd["sig"]]) for nd in nodes] or [0]
    ev = sequence_events or []
    hub_seen = sum(1 for x in ev if x.get("event") == "hub_seen")
    branch_start = [x for x in ev if x.get("event") == "branch_start"]
    returned = sum(1 for x in ev if x.get("event") == "sequence_terminal"
                   and x.get("outcome") == "returned")
    return {
        "n_states": n,
        "n_clusters": len(clusters),
        "n_urls": len(urls),
        "semantic_variant_churn": round(n / max(len(urls), 1), 3),
        "mean_observed_fanout": round(sum(fanouts) / len(fanouts), 3),
        "mean_reached_depth": round(sum(depths) / len(depths), 3),
        "max_reached_depth": max(depths),
        "hub_seen_events": hub_seen,
        "unique_branches_started": len({x.get("branch_key") for x in branch_start}),
        "branch_start_events": len(branch_start),
        "return_to_hub_events": returned,
        "return_to_hub_reuse_ratio": round(
            returned / len(branch_start), 3) if branch_start else None,
        "urls": sorted(urls),
    }


def first_hub_event(events: list) -> dict | None:
    for e in events:
        if e.get("kind") == "step" and e.get("is_hub"):
            return e
        if e.get("event") == "hub_seen":
            return e
    return None


def url_of(ev: dict) -> str:
    src = ev.get("src") or {}
    return src.get("url") or ev.get("url") or ""


def action_text(ev: dict) -> str:
    act = ev.get("action") or {}
    return f"{act.get('type', '')}:{act.get('target_eid', '')}:{act.get('text', '')}"
