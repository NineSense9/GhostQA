"""GhostBench v0 - simulated benchmark apps with seeded bugs.

Each app returns (SimApp, spec, bug_manifest).
bug_manifest entries: {"id", "kind", "severity", "desc", "match"}
  match: evidence keys that must equal for a finding to count as this bug.
"""
from __future__ import annotations

from ghostqa.executor.sim import SimApp


# ---------------------------------------------------------------- sim-shop
def _shop_obs(internal: dict, page: str) -> dict:
    obs = {}
    if page == "cart":
        obs["cart_total_display_num"] = internal.get("cart_total_display", 0)
        obs["cart_count"] = len(internal.get("cart", []))
    if page == "detail":
        obs["stock_num"] = internal.get("stock", 0)
    if page == "register":
        obs["form_msg"] = internal.get("form_msg", "")
    return obs


def make_sim_shop() -> tuple:
    pages = {
        "home": {
            "url": "/home", "title": "幽灵商城·首页",
            "elements": [
                {"eid": "nav_products", "role": "link", "text": "商品列表",
                 "effect": {"op": "goto", "to": "products"}},
                {"eid": "nav_cart", "role": "link", "text": "购物车",
                 "effect": {"op": "goto", "to": "cart"}},
                {"eid": "nav_profile", "role": "link", "text": "个人中心",
                 "effect": {"op": "goto", "to": "profile",
                            "guard": {"if_not": "logged_in", "goto": "login"}}},
                {"eid": "nav_register", "role": "link", "text": "注册",
                 "effect": {"op": "goto", "to": "register"}},
                {"eid": "search_box", "role": "input", "text": "搜索商品", "kind": "input"},
            ],
            "input_rules": {"search_box": {
                "max_len": 20,
                "on_violate": {"op": "js_error",
                               "message": "Uncaught RangeError: Maximum call stack size exceeded"}}},
        },
        "products": {
            "url": "/products", "title": "商品列表",
            "elements": [
                {"eid": "item_apple", "role": "link", "text": "红富士苹果 ¥5",
                 "effect": {"op": "goto", "to": "detail"}},
                {"eid": "nav_help", "role": "link", "text": "帮助中心",
                 "effect": {"op": "goto", "to": "help"}},
            ],
        },
        "detail": {
            "url": "/detail", "title": "商品详情·苹果",
            "elements": [
                {"eid": "btn_add", "role": "button", "text": "加入购物车",
                 "effect": {"op": "mutate",
                            "mutations": [["cart_add", {"name": "苹果", "price": 5, "qty": 1}]],
                            "then": {"op": "goto", "to": "cart"}}},
                {"eid": "btn_fav", "role": "button", "text": "收藏",
                 "effect": {"op": "noop"}},                       # BUG-03 dead action
                {"eid": "btn_buy", "role": "button", "text": "立即购买",
                 "effect": {"op": "mutate", "mutations": [["purchase", None]]}},
            ],
        },
        "cart": {
            "url": "/cart", "title": "购物车",
            "elements": [
                {"eid": "btn_remove", "role": "button", "text": "删除首个商品",
                 "effect": {"op": "mutate", "mutations": [["cart_remove", None]]}},  # BUG-02
                {"eid": "btn_checkout", "role": "button", "text": "去结算",
                 "effect": {"op": "goto", "to": "checkout"}},
            ],
        },
        "checkout": {
            "url": "/checkout", "title": "订单结算",
            "elements": [
                {"eid": "btn_pay", "role": "button", "text": "立即支付",
                 "effect": {"op": "crash",                         # BUG-01 pay on EMPTY cart crashes
                            "when": {"empty": "cart"},
                            "else": {"op": "goto", "to": "profile"}}},
            ],
        },
        "profile": {
            "url": "/profile", "title": "个人中心",
            "elements": [
                {"eid": "btn_settings", "role": "button", "text": "设置",
                 "effect": {"op": "goto", "to": "settings"}},
            ],
        },
        "login": {
            "url": "/login", "title": "登录",
            "elements": [
                {"eid": "input_user", "role": "input", "text": "用户名", "kind": "input"},
                {"eid": "btn_login", "role": "button", "text": "登录",
                 "effect": {"op": "mutate", "mutations": [["login", None]],
                            "then": {"op": "goto", "to": "profile"}}},
            ],
        },
        "settings": {
            "url": "/settings", "title": "设置",
            "elements": [
                {"eid": "btn_more", "role": "link", "text": "更多帮助",
                 "effect": {"op": "goto", "to": "help2"}},
            ],
        },
        "help": {
            "url": "/help", "title": "帮助中心",
            "elements": [
                {"eid": "btn_more", "role": "link", "text": "更多帮助",
                 "effect": {"op": "goto", "to": "help2"}},
            ],
        },
        "help2": {
            "url": "/help2", "title": "更多帮助",
            "elements": [
                {"eid": "btn_back_help", "role": "link", "text": "返回帮助",
                 "effect": {"op": "goto", "to": "help"}},          # BUG-04 help<->help2 loop
            ],
        },
        "register": {
            "url": "/register", "title": "注册",
            "elements": [
                {"eid": "reg_user", "role": "input", "text": "用户名", "kind": "input"},
                {"eid": "btn_reg", "role": "button", "text": "提交注册",
                 "effect": {"op": "mutate",
                            "mutations": [["set_msg", "注册成功"],
                                          ["submit_form", None]]}},  # BUG-06 always success
            ],
        },
    }
    initial = {"logged_in": False,
               "cart": [{"name": "苹果", "price": 5, "qty": 1}],
               "cart_total_display": 5,
               "stock": 2, "fields": {}, "form_submitted": False}
    app = SimApp("sim-shop", "home", pages, initial, _shop_obs)

    spec = [
        {"id": "cart_total_consistent", "severity": "high",
         "desc": "购物车显示总价应与实际商品合计一致（删除商品后总价未更新）",
         "when": {"url_contains": "/cart"},
         "assert": {"op": "eq", "left": {"obs": "cart_total_display_num"},
                    "right": {"expr": "cart_total"}}},
        {"id": "stock_non_negative", "severity": "medium",
         "desc": "库存不应为负数",
         "when": "always",
         "assert": {"op": "ge", "left": {"obs": "stock_num"}, "right": {"const": 0}}},
        {"id": "register_requires_username", "severity": "high",
         "desc": "用户名为空时不应提示注册成功",
         "when": {"url_contains": "/register"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"gt": "fields"},
                             "right": {"const": {"reg_user": ""}}},
                    "then": {"op": "not_contains", "left": {"obs": "form_msg"},
                             "right": {"const": "成功"}}}},
    ]

    manifest = [
        {"id": "BUG-01", "kind": "crash", "desc": "购物车为空时点击立即支付导致崩溃",
         "match": {"page": "checkout"}},
        {"id": "BUG-02", "kind": "semantic", "desc": "删除商品后总价未更新",
         "match": {"assert_id": "cart_total_consistent"}},
        {"id": "BUG-03", "kind": "dead_action", "desc": "收藏按钮点击无响应",
         "match": {"eid": "btn_fav"}},
        {"id": "BUG-04", "kind": "nav_loop", "desc": "帮助中心↔更多帮助死循环",
         "match": {"cycle_urls": ["sim://sim-shop/help", "sim://sim-shop/help2"]}},
        {"id": "BUG-05", "kind": "js_error", "desc": "搜索框超长输入触发 JS 错误",
         "match": {"error": "Uncaught RangeError: Maximum call stack size exceeded"}},
        {"id": "BUG-06", "kind": "semantic", "desc": "注册表单空用户名也提示成功",
         "match": {"assert_id": "register_requires_username"}},
        {"id": "BUG-07", "kind": "semantic", "desc": "库存可被扣为负数",
         "match": {"assert_id": "stock_non_negative"}},
    ]
    return app, spec, manifest


# ---------------------------------------------------------------- sim-todo
def _todo_obs(internal: dict, page: str) -> dict:
    obs = {}
    if page == "list":
        obs["count_display"] = internal.get("count_display", 0)
        obs["real_count"] = len(internal.get("todos", []))
    if page == "settings":
        obs["form_msg"] = internal.get("fields", {}).get("form_msg", "")
    return obs


def make_sim_todo() -> tuple:
    pages = {
        "list": {
            "url": "/list", "title": "待办清单",
            "elements": [
                {"eid": "input_todo", "role": "input", "text": "新待办", "kind": "input"},
                {"eid": "btn_del", "role": "button", "text": "删除首条",
                 "effect": {"op": "mutate", "mutations": [["cart_remove_todo", None]]}},
                {"eid": "btn_top", "role": "button", "text": "置顶首条",
                 "effect": {"op": "noop"}},                        # dead action
                {"eid": "btn_clear", "role": "button", "text": "清空全部",
                 "effect": {"op": "crash"}},                        # crash
                {"eid": "nav_settings", "role": "link", "text": "设置",
                 "effect": {"op": "goto", "to": "settings"}},
            ],
        },
        "settings": {
            "url": "/settings", "title": "设置",
            "elements": [
                {"eid": "btn_theme", "role": "button", "text": "切换主题",
                 "effect": {"op": "mutate",
                            "mutations": [["set_field", ["form_msg", "主题已切换"]]]}},
            ],
        },
    }
    initial = {"todos": [{"name": "写作业"}, {"name": "买牛奶"}],
               "count_display": 2, "fields": {}}
    app = SimApp("sim-todo", "list", pages, initial, _todo_obs)

    # monkey-patch mutation name: reuse cart_remove semantics for todos
    orig_apply = None  # handled in runner via executor subclass (see below)

    spec = [
        {"id": "todo_count_consistent", "severity": "high",
         "desc": "待办条数显示应与实际一致",
         "when": {"url_contains": "/list"},
         "assert": {"op": "eq", "left": {"obs": "count_display"},
                    "right": {"obs": "real_count"}}},
    ]
    manifest = [
        {"id": "BUG-T1", "kind": "crash", "desc": "清空全部导致崩溃",
         "match": {"page": "list"}},
        {"id": "BUG-T2", "kind": "semantic", "desc": "删除待办后计数未更新",
         "match": {"assert_id": "todo_count_consistent"}},
        {"id": "BUG-T3", "kind": "dead_action", "desc": "置顶按钮无响应",
         "match": {"eid": "btn_top"}},
    ]
    return app, spec, manifest


# ---------------------------------------------------------------- sim-deep (frontier / depth)
def _deep_obs(internal: dict, page: str) -> dict:
    obs = {"phase": internal.get("phase", "start"), "depth": page}
    if page == "s5":
        obs["ready_to_crash"] = "1"
    return obs


def make_sim_deep() -> tuple:
    """Deep chain + distractor bush. Bug sits at the end of the main chain.

    Home branching: three distractor entries then the valuable '进入主流程'.
    BFS walks distractors first. Frontier restore should jump back to the
    unused main-chain action instead of only backing up one level.
    """
    def leaf(url, title, nxt=None):
        els = []
        if nxt:
            els.append({"eid": f"next_{nxt}", "role": "link", "text": "下一页",
                        "effect": {"op": "goto", "to": nxt}})
        return {"url": url, "title": title, "elements": els}

    pages = {
        "home": {
            "url": "/home", "title": "首页",
            "elements": [
                {"eid": "nav_help", "role": "link", "text": "帮助",
                 "effect": {"op": "goto", "to": "h1"}},
                {"eid": "nav_about", "role": "link", "text": "关于",
                 "effect": {"op": "goto", "to": "a1"}},
                {"eid": "nav_docs", "role": "link", "text": "文档",
                 "effect": {"op": "goto", "to": "d1"}},
                {"eid": "nav_main", "role": "link", "text": "进入主流程",
                 "effect": {"op": "goto", "to": "s1"}},
            ],
        },
        "h1": leaf("/help/1", "帮助1", "h2"),
        "h2": leaf("/help/2", "帮助2", "h3"),
        "h3": leaf("/help/3", "帮助3", "h4"),
        "h4": leaf("/help/4", "帮助4"),
        "a1": leaf("/about/1", "关于1", "a2"),
        "a2": leaf("/about/2", "关于2"),
        "d1": leaf("/docs/1", "文档1", "d2"),
        "d2": leaf("/docs/2", "文档2"),
        "s1": {
            "url": "/flow/1", "title": "流程1",
            "elements": [{"eid": "next_s2", "role": "button", "text": "继续流程",
                          "effect": {"op": "goto", "to": "s2"}}],
        },
        "s2": {
            "url": "/flow/2", "title": "流程2",
            "elements": [{"eid": "next_s3", "role": "button", "text": "继续流程",
                          "effect": {"op": "goto", "to": "s3"}}],
        },
        "s3": {
            "url": "/flow/3", "title": "流程3",
            "elements": [{"eid": "next_s4", "role": "button", "text": "继续流程",
                          "effect": {"op": "goto", "to": "s4"}}],
        },
        "s4": {
            "url": "/flow/4", "title": "流程4",
            "elements": [{"eid": "next_s5", "role": "button", "text": "提交支付",
                          "effect": {"op": "goto", "to": "s5"}}],
        },
        "s5": {
            "url": "/flow/5", "title": "流程5",
            "elements": [{"eid": "btn_boom", "role": "button", "text": "确认支付",
                          "effect": {"op": "crash"}}],
        },
    }
    app = SimApp("sim-deep", "home", pages, {"phase": "start"}, _deep_obs)
    spec = []
    manifest = [
        {"id": "BUG-DEEP-1", "kind": "crash", "severity": "high",
         "desc": "主流程末端支付崩溃（depth 6）",
         "match": {"page": "s5"},
         "trigger_depth": 6},
    ]
    return app, spec, manifest


APPS = {
    "sim-shop": make_sim_shop,
    "sim-todo": make_sim_todo,
    "sim-deep": make_sim_deep,
}
