"""Deterministic generator for v0.3.11 preregistered fresh targets.

Inputs: app identity, frozen seed, topology family, vocabulary.
Does not import policies, explorers, oracles, or web runners.
Does not score or reject topology based on exploration results.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from benchmark.multitarget_js import JS_BY_APP
from benchmark.multitarget_vocab import APP_NAMES, resolve_seed, vocab_for

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 1.5rem 2rem; color: #1f2933; }}
a {{ margin-right: .7rem; }} button {{ margin: .2rem .3rem .2rem 0; padding: .3rem .8rem; }}
input, textarea {{ padding: .3rem; margin-right: .4rem; }} [role=alert] {{ color: #b42318; margin-top: .5rem; }}
.muted {{ color: #5b6770; font-size: .9rem; }} nav {{ margin-bottom: 1rem; }}
.card {{ border: 1px solid #d8dee4; padding: .8rem 1rem; margin: .6rem 0; border-radius: 4px; }}
h1 {{ font-size: 1.35rem; }}
</style></head>
<body data-page="{page}"><div id="root"></div><script src="app.js"></script></body>
</html>
"""

SERVER = '''"""{title} local server: static files + a seeded 500.

Fully offline, deterministic. Usage:
    python server.py [port]        (default {default_port})
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
FAIL_PATH = "{fail_path}"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, *args):
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == FAIL_PATH:
            self._json(500, {{"error": "{fail_error}"}})
        elif self.path == "/api/echo":
            length = int(self.headers.get("Content-Length", 0))
            self._json(200, {{"echo": self.rfile.read(length).decode("utf-8", "ignore")}})
        else:
            self._json(404, {{"error": "not found"}})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else {default_port}
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("{title} listening on http://127.0.0.1:" + str(port))
    server.serve_forever()


if __name__ == "__main__":
    main()
'''

FAMILIES = {
    "buggy-crm": {
        "title": "BuggyCRM",
        "family": "fanout_hub_nested_entity",
        "default_port": 3942,
        "fail_path": "/api/export",
        "fail_error": "export dispatch failed: NullPointerException",
        "storage_key": "bc_state",
        "pages": [
            ("index.html", "home", "工作台"),
            ("accounts.html", "accounts", "客户"),
            ("account.html", "account", "客户详情"),
            ("contacts.html", "contacts", "联系人"),
            ("contact.html", "contact", "联系人详情"),
            ("opportunities.html", "opportunities", "商机"),
            ("opportunity.html", "opportunity", "商机详情"),
            ("activity.html", "activity", "活动"),
            ("pipeline.html", "pipeline", "管道"),
            ("team.html", "team", "团队"),
            ("settings.html", "settings", "设置"),
            ("compose.html", "compose", "新建商机"),
            ("help.html", "help", "使用说明"),
            ("handbook.html", "handbook", "现场手册"),
        ],
        "prefix": "BUG-C",
    },
    "buggy-wiki": {
        "title": "BuggyWiki",
        "family": "cross_linked_content_graph",
        "default_port": 3943,
        "fail_path": "/api/preview",
        "fail_error": "preview dispatch failed: NullPointerException",
        "storage_key": "bw_state",
        "pages": [
            ("index.html", "home", "首页"),
            ("spaces.html", "spaces", "空间"),
            ("space.html", "space", "空间详情"),
            ("pages.html", "pages", "页面"),
            ("page.html", "page", "文稿"),
            ("history.html", "history", "历史"),
            ("revision.html", "revision", "修订"),
            ("tags.html", "tags", "标签"),
            ("backlinks.html", "backlinks", "反向链接"),
            ("editor.html", "editor", "编辑器"),
            ("search.html", "search", "检索"),
            ("settings.html", "settings", "设置"),
            ("help.html", "help", "快捷说明"),
            ("shortcuts.html", "shortcuts", "快捷键"),
        ],
        "prefix": "BUG-W",
    },
    "buggy-ops": {
        "title": "BuggyOps",
        "family": "deep_nested_multi_parent",
        "default_port": 3944,
        "fail_path": "/api/page",
        "fail_error": "pager dispatch failed: NullPointerException",
        "storage_key": "bo_state",
        "pages": [
            ("index.html", "home", "工作台"),
            ("services.html", "services", "服务"),
            ("service.html", "service", "服务详情"),
            ("incidents.html", "incidents", "事件"),
            ("incident.html", "incident", "事件详情"),
            ("alerts.html", "alerts", "告警"),
            ("alert.html", "alert", "告警详情"),
            ("runbooks.html", "runbooks", "手册"),
            ("runbook.html", "runbook", "手册详情"),
            ("deploys.html", "deploys", "发布历史"),
            ("deploy.html", "deploy", "发布详情"),
            ("teams.html", "teams", "团队"),
            ("settings.html", "settings", "设置"),
            ("compose.html", "compose", "新建事件"),
            ("help.html", "help", "值班说明"),
            ("playbook.html", "playbook", "应急手册"),
        ],
        "prefix": "BUG-O",
    },
}


def _crm_bugs():
    return [
        {"id": "BUG-C1", "category": "js error", "severity": "medium",
         "desc": "设置页测试同步抛出未捕获异常",
         "kind": "js_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "crm sync handshake"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_test_sync"]},
        {"id": "BUG-C2", "category": "blank page", "severity": "medium",
         "desc": "管道页渲染后完全空白",
         "kind": "blank", "trigger_depth": 1, "prerequisites": [],
         "match": {"url_contains": "/pipeline.html"},
         "min_reproduction": ["index.html: nav_pipeline"]},
        {"id": "BUG-C3", "category": "dead action", "severity": "medium",
         "desc": "客户关注按钮点击无任何效果",
         "kind": "dead_action", "trigger_depth": 3, "prerequisites": [],
         "match": {"eid": "btn_watch"},
         "min_reproduction": ["index.html: nav_accounts", "accounts.html: account_a1",
                              "account.html: btn_watch"]},
        {"id": "BUG-C4", "category": "navigation loop", "severity": "medium",
         "desc": "使用说明与现场手册互相链接，无法退出",
         "kind": "nav_loop", "trigger_depth": 2, "prerequisites": [],
         "match": {"cycle_urls_contains": "help.html"},
         "min_reproduction": ["index.html: nav_help", "help.html: btn_handbook",
                              "handbook.html: btn_help", "help.html: btn_handbook",
                              "handbook.html: btn_help"]},
        {"id": "BUG-C5", "category": "form validation", "severity": "high",
         "desc": "标题为空时仍提示已创建",
         "kind": "semantic", "trigger_depth": 2, "prerequisites": [],
         "match": {"assert_id": "opp_title_required"},
         "min_reproduction": ["index.html: nav_compose", "compose.html: btn_create"]},
        {"id": "BUG-C6", "category": "state inconsistency", "severity": "medium",
         "desc": "下调预测后展示值未更新",
         "kind": "semantic", "trigger_depth": 3, "prerequisites": ["open-account"],
         "match": {"assert_id": "forecast_display_matches_remaining"},
         "min_reproduction": ["index.html: nav_accounts", "accounts.html: account_a1",
                              "account.html: btn_pause_forecast"]},
        {"id": "BUG-C7", "category": "boundary js error", "severity": "medium",
         "desc": "工作台搜索词超过 24 字抛出未捕获 RangeError",
         "kind": "js_error", "trigger_depth": 1, "prerequisites": [],
         "match": {"error_contains": "crm search query too long"},
         "min_reproduction": ["index.html: search_box=25 chars", "index.html: search_btn"]},
        {"id": "BUG-C8", "category": "http 5xx", "severity": "high",
         "desc": "导出请求 /api/export 始终返回 500",
         "kind": "http_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "/api/export"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_export"]},
        {"id": "BUG-C9", "category": "sequence-dependent", "severity": "high",
         "desc": "关闭后再重开，状态仍显示已关闭",
         "kind": "semantic", "trigger_depth": 4, "prerequisites": ["open-account", "close"],
         "match": {"assert_id": "reopen_clears_closed"},
         "min_reproduction": ["index.html: nav_accounts", "accounts.html: account_a1",
                              "account.html: btn_close", "account.html: btn_reopen"]},
        {"id": "BUG-C10", "category": "cross-page consistency", "severity": "high",
         "desc": "内部备注在活动中显示为客户可见",
         "kind": "semantic", "trigger_depth": 5, "prerequisites": ["open-account", "internal-note"],
         "match": {"assert_id": "internal_note_not_customer_visible"},
         "min_reproduction": ["index.html: nav_accounts", "accounts.html: account_a1",
                              "account.html: btn_internal_note", "account.html: nav_activity"]},
    ]


def _wiki_bugs():
    return [
        {"id": "BUG-W1", "category": "js error", "severity": "medium",
         "desc": "设置页测试插件抛出未捕获异常",
         "kind": "js_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "wiki plugin handshake"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_test_plugin"]},
        {"id": "BUG-W2", "category": "blank page", "severity": "medium",
         "desc": "检索页渲染后完全空白",
         "kind": "blank", "trigger_depth": 1, "prerequisites": [],
         "match": {"url_contains": "/search.html"},
         "min_reproduction": ["index.html: nav_search"]},
        {"id": "BUG-W3", "category": "dead action", "severity": "medium",
         "desc": "页面关注按钮点击无任何效果",
         "kind": "dead_action", "trigger_depth": 3, "prerequisites": [],
         "match": {"eid": "btn_watch"},
         "min_reproduction": ["index.html: nav_pages", "pages.html: wiki_page_p1",
                              "page.html: btn_watch"]},
        {"id": "BUG-W4", "category": "navigation loop", "severity": "medium",
         "desc": "快捷说明与快捷键互相链接，无法退出",
         "kind": "nav_loop", "trigger_depth": 2, "prerequisites": [],
         "match": {"cycle_urls_contains": "help.html"},
         "min_reproduction": ["index.html: nav_help", "help.html: btn_shortcuts",
                              "shortcuts.html: btn_help", "help.html: btn_shortcuts",
                              "shortcuts.html: btn_help"]},
        {"id": "BUG-W5", "category": "form validation", "severity": "high",
         "desc": "标题为空时仍提示已发布",
         "kind": "semantic", "trigger_depth": 2, "prerequisites": [],
         "match": {"assert_id": "page_title_required"},
         "min_reproduction": ["index.html: nav_editor", "editor.html: btn_publish"]},
        {"id": "BUG-W6", "category": "state inconsistency", "severity": "medium",
         "desc": "恢复修订后展示修订号未更新",
         "kind": "semantic", "trigger_depth": 4, "prerequisites": ["open-page", "history"],
         "match": {"assert_id": "display_rev_matches_restored"},
         "min_reproduction": ["index.html: nav_pages", "pages.html: wiki_page_p1",
                              "page.html: nav_history", "history.html: rev_r1",
                              "revision.html: btn_restore_rev"]},
        {"id": "BUG-W7", "category": "boundary js error", "severity": "medium",
         "desc": "首页搜索词超过 24 字抛出未捕获 RangeError",
         "kind": "js_error", "trigger_depth": 1, "prerequisites": [],
         "match": {"error_contains": "wiki search query too long"},
         "min_reproduction": ["index.html: search_box=25 chars", "index.html: search_btn"]},
        {"id": "BUG-W8", "category": "http 5xx", "severity": "high",
         "desc": "远程预览 /api/preview 始终返回 500",
         "kind": "http_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "/api/preview"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_api_preview"]},
        {"id": "BUG-W9", "category": "sequence-dependent", "severity": "high",
         "desc": "取消发布后仍显示已发布",
         "kind": "semantic", "trigger_depth": 4, "prerequisites": ["open-page"],
         "match": {"assert_id": "unpublish_clears_published"},
         "min_reproduction": ["index.html: nav_pages", "pages.html: wiki_page_p1",
                              "page.html: btn_unpublish"]},
    ]


def _ops_bugs():
    return [
        {"id": "BUG-O1", "category": "js error", "severity": "medium",
         "desc": "设置页测试呼叫抛出未捕获异常",
         "kind": "js_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "ops pager handshake"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_test_pager"]},
        {"id": "BUG-O2", "category": "blank page", "severity": "medium",
         "desc": "团队页渲染后完全空白",
         "kind": "blank", "trigger_depth": 1, "prerequisites": [],
         "match": {"url_contains": "/teams.html"},
         "min_reproduction": ["index.html: nav_teams"]},
        {"id": "BUG-O3", "category": "dead action", "severity": "medium",
         "desc": "事件钉住按钮点击无任何效果",
         "kind": "dead_action", "trigger_depth": 4, "prerequisites": [],
         "match": {"eid": "btn_pin"},
         "min_reproduction": ["index.html: nav_services", "services.html: service_svc1",
                              "service.html: nav_service_incidents",
                              "incidents.html: incident_i1", "incident.html: btn_pin"]},
        {"id": "BUG-O4", "category": "navigation loop", "severity": "medium",
         "desc": "值班说明与应急手册互相链接，无法退出",
         "kind": "nav_loop", "trigger_depth": 2, "prerequisites": [],
         "match": {"cycle_urls_contains": "help.html"},
         "min_reproduction": ["index.html: nav_help", "help.html: btn_playbook",
                              "playbook.html: btn_help", "help.html: btn_playbook",
                              "playbook.html: btn_help"]},
        {"id": "BUG-O5", "category": "form validation", "severity": "high",
         "desc": "标题为空时仍提示已创建",
         "kind": "semantic", "trigger_depth": 2, "prerequisites": [],
         "match": {"assert_id": "inc_title_required"},
         "min_reproduction": ["index.html: nav_compose", "compose.html: btn_create"]},
        {"id": "BUG-O6", "category": "state inconsistency", "severity": "medium",
         "desc": "静默告警后展示剩余时间未更新",
         "kind": "semantic", "trigger_depth": 3, "prerequisites": ["open-alert"],
         "match": {"assert_id": "silence_display_matches_remaining"},
         "min_reproduction": ["index.html: nav_alerts", "alerts.html: alert_al1",
                              "alert.html: btn_silence"]},
        {"id": "BUG-O7", "category": "boundary js error", "severity": "medium",
         "desc": "工作台搜索词超过 24 字抛出未捕获 RangeError",
         "kind": "js_error", "trigger_depth": 1, "prerequisites": [],
         "match": {"error_contains": "ops search query too long"},
         "min_reproduction": ["index.html: search_box=25 chars", "index.html: search_btn"]},
        {"id": "BUG-O8", "category": "http 5xx", "severity": "high",
         "desc": "寻呼请求 /api/page 始终返回 500",
         "kind": "http_error", "trigger_depth": 2, "prerequisites": [],
         "match": {"error_contains": "/api/page"},
         "min_reproduction": ["index.html: nav_settings", "settings.html: btn_page"]},
        {"id": "BUG-O9", "category": "sequence-dependent", "severity": "high",
         "desc": "确认后再重开，状态仍显示已关闭",
         "kind": "semantic", "trigger_depth": 4, "prerequisites": ["open-incident", "ack"],
         "match": {"assert_id": "reopen_clears_closed"},
         "min_reproduction": ["index.html: nav_incidents", "incidents.html: incident_i1",
                              "incident.html: btn_ack", "incident.html: btn_reopen"]},
    ]


def _crm_spec():
    return [
        {"id": "opp_title_required", "severity": "high",
         "desc": "标题为空时不应提示已创建",
         "when": {"url_contains": "/compose"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "input_opp_title"}, "right": {"const": ""}},
                    "then": {"op": "not_contains", "left": {"obs": "form_msg"},
                             "right": {"const": "已创建"}}}},
        {"id": "forecast_display_matches_remaining", "severity": "medium",
         "desc": "客户页展示的预测应与剩余预测值一致",
         "when": {"url_contains": "/account.html"},
         "assert": {"op": "eq", "left": {"obs": "forecast_display"},
                    "right": {"obs": "forecast_remaining"}}},
        {"id": "reopen_clears_closed", "severity": "high",
         "desc": "已重开的客户不应仍显示为已关闭",
         "when": {"url_contains": "/account.html"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "reopen_state"}, "right": {"const": "是"}},
                    "then": {"op": "ne", "left": {"obs": "account_status"},
                             "right": {"const": "已关闭"}}}},
        {"id": "internal_note_not_customer_visible", "severity": "high",
         "desc": "内部备注在活动中不应显示为客户可见",
         "when": {"url_contains": "/activity"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "note_kind"}, "right": {"const": "内部"}},
                    "then": {"op": "eq", "left": {"obs": "note_visibility"},
                             "right": {"const": "内部"}}}},
    ]


def _wiki_spec():
    return [
        {"id": "page_title_required", "severity": "high",
         "desc": "标题为空时不应提示已发布",
         "when": {"url_contains": "/editor"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "input_page_title"}, "right": {"const": ""}},
                    "then": {"op": "not_contains", "left": {"obs": "form_msg"},
                             "right": {"const": "已发布"}}}},
        {"id": "display_rev_matches_restored", "severity": "medium",
         "desc": "修订页展示的修订号应与已恢复修订一致",
         "when": {"url_contains": "/revision.html"},
         "assert": {"op": "eq", "left": {"obs": "display_rev"},
                    "right": {"obs": "restored_rev"}}},
        {"id": "unpublish_clears_published", "severity": "high",
         "desc": "已取消发布的页面不应仍显示已发布",
         "when": {"url_contains": "/page.html"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "unpublish_flag"}, "right": {"const": "是"}},
                    "then": {"op": "ne", "left": {"obs": "publish_state"},
                             "right": {"const": "已发布"}}}},
    ]


def _ops_spec():
    return [
        {"id": "inc_title_required", "severity": "high",
         "desc": "标题为空时不应提示已创建",
         "when": {"url_contains": "/compose"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "input_inc_title"}, "right": {"const": ""}},
                    "then": {"op": "not_contains", "left": {"obs": "form_msg"},
                             "right": {"const": "已创建"}}}},
        {"id": "silence_display_matches_remaining", "severity": "medium",
         "desc": "告警页展示的剩余时间应与剩余值一致",
         "when": {"url_contains": "/alert.html"},
         "assert": {"op": "eq", "left": {"obs": "silence_display"},
                    "right": {"obs": "silence_remaining"}}},
        {"id": "reopen_clears_closed", "severity": "high",
         "desc": "已重开的事件不应仍显示为已关闭",
         "when": {"url_contains": "/incident.html"},
         "assert": {"op": "implies",
                    "cond": {"op": "eq", "left": {"obs": "reopen_state"}, "right": {"const": "是"}},
                    "then": {"op": "ne", "left": {"obs": "incident_status"},
                             "right": {"const": "已关闭"}}}},
    ]


BUGS = {"buggy-crm": _crm_bugs, "buggy-wiki": _wiki_bugs, "buggy-ops": _ops_bugs}
SPECS = {"buggy-crm": _crm_spec, "buggy-wiki": _wiki_spec, "buggy-ops": _ops_spec}


def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text if text.endswith("\n") else text + "\n")


def _write_json(path: str, obj) -> None:
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def app_dir(app_name: str, root: str = ROOT) -> str:
    return os.path.join(root, "apps", app_name)


def generated_relpaths(app_name: str) -> list:
    fam = FAMILIES[app_name]
    rels = [
        f"apps/{app_name}/server.py",
        f"apps/{app_name}/spec.json",
        f"apps/{app_name}/bugs.manifest.json",
        f"apps/{app_name}/topology.manifest.json",
        f"apps/{app_name}/README.md",
        f"apps/{app_name}/static/app.js",
    ]
    for fname, _page, _title in fam["pages"]:
        rels.append(f"apps/{app_name}/static/{fname}")
    return rels


def generate_app(app_name: str, *, root: str = ROOT) -> dict:
    if app_name not in FAMILIES:
        raise ValueError(app_name)
    fam = FAMILIES[app_name]
    vocab = vocab_for(app_name)
    dest = app_dir(app_name, root)
    static = os.path.join(dest, "static")
    os.makedirs(static, exist_ok=True)
    brand = vocab["brand"]
    for fname, page, title in fam["pages"]:
        _write(os.path.join(static, fname), HTML.format(
            title=f"{brand}·{title}", page=page))
    js = JS_BY_APP[app_name].replace(
        "__VOCAB__", json.dumps(vocab, ensure_ascii=False, separators=(",", ":")))
    _write(os.path.join(static, "app.js"), js)
    _write(os.path.join(dest, "server.py"), SERVER.format(
        title=fam["title"], default_port=fam["default_port"],
        fail_path=fam["fail_path"], fail_error=fam["fail_error"]))
    bugs = BUGS[app_name]()
    _write_json(os.path.join(dest, "bugs.manifest.json"), {
        "app": app_name,
        "note": "BENCHMARK JUDGE ONLY. GhostQA exploration/oracle must never read this file.",
        "bugs": bugs,
    })
    _write_json(os.path.join(dest, "spec.json"), {
        "app": app_name,
        "note": "Specification-driven semantic oracle. Uses ONLY page-presented values (data-obs / input values) - never internal app state.",
        "assertions": SPECS[app_name](),
    })
    _write_json(os.path.join(dest, "topology.manifest.json"), {
        "app": app_name,
        "note": "Judge/authoring topology metadata. Not served to the browser. Policy/Explorer/Oracle must not read this file.",
        "topology_family": fam["family"],
        "seed": vocab["seed"],
        "seed_hex": vocab["seed_hex"],
        "pages": [p[0] for p in fam["pages"]],
        "cycle_prone": {
            "buggy-crm": "account related-entity clique",
            "buggy-wiki": "page backlinks clique plus editor exact variants",
            "buggy-ops": "incident related clique",
        }[app_name],
        "successful_return": {
            "buggy-crm": "account.html nav_back_accounts -> accounts.html",
            "buggy-wiki": "revision.html -> history.html -> page.html",
            "buggy-ops": "incident.html -> incidents.html -> service.html",
        }[app_name],
    })
    _write(os.path.join(dest, "README.md"), (
        f"# {fam['title']}\n\n"
        f"Preregistered v0.3.11 fresh target. Topology family: `{fam['family']}`.\n"
        f"Seed `{vocab['seed_hex']}` = {vocab['seed']}.\n\n"
        "Manifest and topology are judge-only and are not served.\n"
    ))
    return {
        "app": app_name,
        "dir": dest,
        "seed": vocab["seed"],
        "seed_hex": vocab["seed_hex"],
        "n_pages": len(fam["pages"]),
        "n_bugs": len(bugs),
        "files": generated_relpaths(app_name),
    }


def generate_all(*, root: str = ROOT) -> list:
    return [generate_app(name, root=root) for name in APP_NAMES]


def lf_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["write", "seeds", "list"])
    ap.add_argument("--root", default=ROOT)
    args = ap.parse_args(argv)
    if args.cmd == "seeds":
        for name in APP_NAMES:
            seed, hex8 = resolve_seed(name)
            print(f"{name} {hex8} {seed}")
        return 0
    if args.cmd == "list":
        for name in APP_NAMES:
            for rel in generated_relpaths(name):
                print(rel)
        return 0
    for rec in generate_all(root=args.root):
        print(f"wrote {rec['app']} seed={rec['seed_hex']} pages={rec['n_pages']} bugs={rec['n_bugs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
