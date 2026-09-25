"""New-application generator for the v0.3.25 fresh transfer.

Does not edit the frozen v0.3.20 generator or the v0.3.24 candidate.
Positives are a single spine plus one board workflow.
"""
from __future__ import annotations

import hashlib
import json
import os
import random

from benchmark.fresh_composite_generator import (
    EDGE_FIELDS, FAIL_PATH, _back, _bug, _button, _finding_controls, _input,
    _link, _mutate, _public_control, _search, _status_buttons,
)
from benchmark.fresh_composite_js import HTML, JS, SERVER
from benchmark.fresh_composite_qualify import qualify_topology
from benchmark.fresh_composite_vocab import contains_non_branch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED_PREFIX = "ghostqa-v0.3.25:"

FAMILIES = {
    "buggy-clinic": {
        "family": "roster_chart_order_spine", "control_class": "positive", "port": 3961,
        "prefix": "BUG-CL", "brand_pool": ("澄诊台", "北街门诊", "拾页病历"),
        "storage_key": "clinic_v0325", "fail_error": "clinic export dispatch failed",
        "search_error": "clinic search query too long", "sync_error": "clinic sync handshake failed",
        "assert_prefix": "clinic",
    },
    "buggy-dispatch": {
        "family": "roster_chart_order_spine", "control_class": "positive", "port": 3962,
        "prefix": "BUG-DP", "brand_pool": ("澄调度", "北埠派单", "拾班台"),
        "storage_key": "dispatch_v0325", "fail_error": "dispatch export dispatch failed",
        "search_error": "dispatch search query too long", "sync_error": "dispatch sync handshake failed",
        "assert_prefix": "dispatch",
    },
    "buggy-archive": {
        "family": "roster_chart_order_spine", "control_class": "positive", "port": 3963,
        "prefix": "BUG-AR", "brand_pool": ("澄档室", "北库卷宗", "拾匣档案"),
        "storage_key": "archive_v0325", "fail_error": "archive export dispatch failed",
        "search_error": "archive search query too long", "sync_error": "archive sync handshake failed",
        "assert_prefix": "archive",
    },
    "buggy-fleet": {
        "family": "roster_chart_order_spine", "control_class": "positive", "port": 3964,
        "prefix": "BUG-FL", "brand_pool": ("澄车队", "北线调度", "拾辆台"),
        "storage_key": "fleet_v0325", "fail_error": "fleet export dispatch failed",
        "search_error": "fleet search query too long", "sync_error": "fleet sync handshake failed",
        "assert_prefix": "fleet",
    },
    "buggy-shelf": {
        "family": "shallow_shelf", "control_class": "catalog", "port": 3965,
        "prefix": "BUG-SH", "brand_pool": ("澄架", "北柜样品", "拾格"),
        "storage_key": "shelf_v0325", "fail_error": "shelf export dispatch failed",
        "search_error": "shelf search query too long", "sync_error": "shelf sync handshake failed",
        "assert_prefix": "shelf",
    },
    "buggy-counter": {
        "family": "shallow_counter", "control_class": "kiosk", "port": 3966,
        "prefix": "BUG-CN", "brand_pool": ("澄柜台", "北窗受理", "拾号"),
        "storage_key": "counter_v0325", "fail_error": "counter export dispatch failed",
        "search_error": "counter search query too long", "sync_error": "counter sync handshake failed",
        "assert_prefix": "counter",
    },
}

POSITIVE = ("buggy-clinic", "buggy-dispatch", "buggy-archive", "buggy-fleet")
NEGATIVE = ("buggy-shelf", "buggy-counter")
NAMES = {
    "record": ("甲卷", "乙卷", "丙卷", "丁卷"),
    "board": ("早班", "午班", "晚班"),
}


def resolve_seed(app_name: str) -> tuple[int, str]:
    digest = hashlib.sha256((SEED_PREFIX + app_name).encode("utf-8")).hexdigest()
    return int(digest[:8], 16), digest[:8]


def _names(seed: int, pool: str, ids: list[str]) -> list[dict]:
    rows = list(NAMES[pool])
    rng = random.Random(seed)
    rng.shuffle(rows)
    return [{"id": item_id, "name": rows[index]} for index, item_id in enumerate(ids)]


class SpineBuilder:
    def __init__(self, app_name: str):
        self.app = app_name
        self.fam = FAMILIES[app_name]
        self.seed, self.seed_hex = resolve_seed(app_name)
        self.nodes = []
        self.control_map = {}
        self.files = []

    def add(self, node_id, page, data_page, title, controls, *, hub_role,
            entity="", entity_source="", obs=None, blank=False, variant_of=""):
        self.nodes.append({
            "id": node_id, "page": page, "data_page": data_page, "title": title,
            "hub_role": hub_role, "entity": entity, "entity_source": entity_source,
            "obs": list(obs or []), "blank": blank, "variant_of": variant_of,
        })
        self.control_map[node_id] = list(controls)
        if page not in self.files:
            self.files.append(page)

    def materialize(self, entities, initial_obs):
        grouped = {}
        for node in self.nodes:
            grouped.setdefault(node["data_page"], []).append(node)
        pages = {}
        topo_nodes = []
        topo_edges = []
        for node in self.nodes:
            siblings = grouped[node["data_page"]]
            has_entity = any(item.get("entity") for item in siblings)
            controls = []
            for ctl in self.control_map[node["id"]]:
                item = dict(ctl)
                if has_entity:
                    if node.get("entity"):
                        item["when_entity"] = node["entity"]
                    else:
                        item["when_no_entity"] = True
                controls.append(item)
            self.control_map[node["id"]] = controls
            visible = []
            for ctl in controls:
                if ctl.get("reveal_after"):
                    continue
                if ctl.get("when_entity") and ctl["when_entity"] != (node.get("entity") or ""):
                    continue
                visible.append(ctl)
            branch_actions = []
            eligible = []
            for ctl in visible:
                if ctl["kind"] not in ("link", "button"):
                    continue
                if contains_non_branch(ctl.get("text") or "", ctl.get("testid") or ""):
                    continue
                if ctl.get("parent_return"):
                    continue
                navigates = ctl["kind"] == "link" and bool(ctl.get("href"))
                branch_actions.append({
                    "testid": ctl["testid"],
                    "dst": ctl.get("dst") or node["id"] if navigates else node["id"],
                    "navigates": bool(navigates),
                })
                if ctl["kind"] == "button":
                    eligible.append(ctl["testid"])
            topo_nodes.append({
                "id": node["id"], "page": node["page"], "hub": len(branch_actions) >= 3,
                "hub_role": node["hub_role"], "entity": node.get("entity") or "",
                "variant_of": node.get("variant_of") or "",
                "first_branch_action": branch_actions[0]["testid"] if branch_actions else "",
                "blank": node["blank"], "eligible_buttons": eligible,
                "branch_actions": branch_actions,
            })
            for ctl in controls:
                branch_like = (
                    ctl["kind"] in ("link", "button")
                    and not contains_non_branch(ctl.get("text") or "", ctl.get("testid") or "")
                    and not ctl.get("parent_return")
                )
                navigates = ctl["kind"] == "link" and bool(ctl.get("href")) and not ctl.get("parent_return")
                flagged = any(ctl.get(key) for key in (
                    "child_local", "follow_up", "parent_return", "opportunity_class", "path_id",
                    "guarantees_finding", "state_variant_return", "alternate_child_completion",
                ))
                if not (navigates or flagged):
                    continue
                dst = ctl.get("dst") or node["id"]
                if not navigates and not ctl.get("parent_return"):
                    dst = node["id"]
                edge = {
                    "id": f"{node['id']}:{ctl['testid']}",
                    "src": node["id"], "dst": dst, "action": ctl["testid"],
                    "branch_like": bool(branch_like and (navigates or ctl.get("child_local") or ctl.get("follow_up"))),
                    "navigates": bool(navigates),
                    "follow_up": bool(ctl.get("follow_up")),
                    "child_local": bool(ctl.get("child_local")),
                    "parent_return": bool(ctl.get("parent_return")),
                    "returns_to": ctl.get("returns_to") or "",
                    "alternate_child_completion": bool(ctl.get("alternate_child_completion")),
                    "family": ctl.get("family") or "",
                    "child_workflow_role": ctl.get("child_workflow_role") or "",
                }
                for key in EDGE_FIELDS:
                    if key in ("child_local", "follow_up", "parent_return", "family", "child_workflow_role"):
                        continue
                    if ctl.get(key) not in (None, "", False):
                        edge[key] = ctl.get(key)
                topo_edges.append(edge)
        for data_page, nodes in grouped.items():
            has_entity = any(item.get("entity") for item in nodes)
            obs, obs_by_entity, controls, entity_source = [], {}, [], ""
            for node in nodes:
                entity_source = node.get("entity_source") or entity_source
                for key in node.get("obs") or []:
                    if node.get("entity"):
                        bucket = obs_by_entity.setdefault(node["entity"], [])
                        if key not in bucket:
                            bucket.append(key)
                    elif key not in obs:
                        obs.append(key)
                controls.extend(self.control_map[node["id"]])
            pages[data_page] = {
                "title": nodes[0]["title"],
                "blank": bool(nodes[0]["blank"] and len(nodes) == 1),
                "entity_param": "id" if has_entity else "",
                "entity_source": entity_source,
                "obs": obs,
                "obs_by_entity": obs_by_entity,
                "controls": [_public_control(ctl) for ctl in controls],
            }
        topology = {
            "app": self.app,
            "note": "Judge and qualification topology. Not served. Exploration must not read this file.",
            "topology_family": self.fam["family"],
            "seed": self.seed,
            "seed_hex": self.seed_hex,
            "expected_control_class": self.fam["control_class"],
            "branch_horizon": 3,
            "nodes": topo_nodes,
            "edges": topo_edges,
        }
        model = {
            "storage_key": self.fam["storage_key"],
            "fail_path": FAIL_PATH,
            "initial": {"obs": initial_obs, "revealed": {}},
            "entities": entities,
            "pages": pages,
        }
        return topology, model


def _initial():
    return {
        "score_shown": "8", "score_live": "6",
        "shown_qty": "8", "live_qty": "8",
        "status_label": "跟进中", "reopened": "否",
        "note_kind": "", "note_visible": "",
        "handled": "", "handled_label": "", "handled_note": "",
        "form_msg": "", "search_state": "",
        "scratch_a": "", "scratch_b": "", "hold_mark": "", "tag_mark": "",
    }


def _spec(prefix):
    def implies(cond_obs, cond_val, then_op, then_obs, then_val):
        return {
            "op": "implies",
            "cond": {"op": "eq", "left": {"obs": cond_obs}, "right": {"const": cond_val}},
            "then": {"op": then_op, "left": {"obs": then_obs}, "right": {"const": then_val}},
        }
    return [
        {"id": f"{prefix}_title_required", "severity": "high", "desc": "标题为空时不应提示已创建",
         "when": {"url_contains": "/settings.html"},
         "assert": implies("input_topic_title", "", "not_contains", "form_msg", "已创建")},
        {"id": f"{prefix}_qty_matches", "severity": "medium", "desc": "展示数量应与剩余数量一致",
         "when": {"url_contains": "/chart.html"},
         "assert": {"op": "eq", "left": {"obs": "shown_qty"}, "right": {"obs": "live_qty"}}},
        {"id": f"{prefix}_reopen_clears", "severity": "high", "desc": "重新打开后不应仍显示已关闭",
         "when": {"url_contains": "/order.html"},
         "assert": implies("reopened", "是", "ne", "status_label", "已关闭")},
        {"id": f"{prefix}_note_visibility", "severity": "high", "desc": "内部标注不应显示为公开",
         "when": {"url_contains": "/notice.html"},
         "assert": implies("note_kind", "内部", "eq", "note_visible", "内部")},
        {"id": f"{prefix}_handled_label", "severity": "high", "desc": "登记之后标记不应仍是未登记",
         "when": {"url_contains": "/slip.html"},
         "assert": implies("handled", "是", "eq", "handled_label", "已登记")},
        {"id": f"{prefix}_score_matches", "severity": "high", "desc": "展示分数应与记录分数一致",
         "when": {"url_contains": "/finding.html"},
         "assert": {"op": "eq", "left": {"obs": "score_shown"}, "right": {"obs": "score_live"}}},
    ]


def _positive_bugs(prefix, fam):
    home = "index.html"
    return [
        _bug(f"{prefix}1", "blank page", "blank", 2, "空白页完全空白",
             {"url_contains": "/blank.html"}, [f"{home}: nav_blank"], "high"),
        _bug(f"{prefix}2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": fam["search_error"]},
             [f"{home}: search_box=25 chars", f"{home}: btn_query_submit"]),
        _bug(f"{prefix}3", "navigation loop", "nav_loop", 2, "说明页与偏好页互相链接",
             {"cycle_urls_contains": "help.html"},
             [f"{home}: open_aid", "help.html: open_loop", "settings.html: open_loop",
              "help.html: open_loop", "settings.html: open_loop"]),
        _bug(f"{prefix}4", "form validation", "semantic", 3, "标题为空时仍提示已创建",
             {"assert_id": f"{fam['assert_prefix']}_title_required"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_desk",
              "settings.html: btn_submit"], "high"),
        _bug(f"{prefix}5", "dead action", "dead_action", 3, "图表页收藏点击无效果",
             {"eid": "btn_pin"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: btn_pin"]),
        _bug(f"{prefix}6", "js error", "js_error", 4, "偏好页测试同步抛出未捕获异常",
             {"error_contains": fam["sync_error"]},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_desk",
              "settings.html: btn_probe"]),
        _bug(f"{prefix}7", "http 5xx", "http_error", 4, "导出请求返回 500",
             {"error_contains": "/api/export"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_desk",
              "settings.html: btn_export"], "high"),
        _bug(f"{prefix}8", "state inconsistency", "semantic", 4, "下调数量后展示值未更新",
             {"assert_id": f"{fam['assert_prefix']}_qty_matches"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: btn_cool"]),
        _bug(f"{prefix}9", "cross-page consistency", "semantic", 5, "内部标注在通知页显示为公开",
             {"assert_id": f"{fam['assert_prefix']}_note_visibility"},
             [f"{home}: nav_board", "board.html: open_s1", "slot.html: btn_internal",
              "slot.html: open_notice"], "high"),
        _bug(f"{prefix}10", "sequence-dependent", "semantic", 5, "关闭后再打开仍显示已关闭",
             {"assert_id": f"{fam['assert_prefix']}_reopen_clears"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_order",
              "order.html: btn_close", "order.html: btn_reopen"], "high"),
        _bug(f"{prefix}11", "local action return", "semantic", 6, "登记后的本地标记仍写着未登记",
             {"assert_id": f"{fam['assert_prefix']}_handled_label"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_order",
              "order.html: open_slip", "slip.html: btn_mark"], "high"),
        _bug(f"{prefix}12", "state inconsistency", "semantic", 4, "分数展示与记录不一致",
             {"assert_id": f"{fam['assert_prefix']}_score_matches"},
             [f"{home}: nav_roster", "roster.html: open_r1", "chart.html: open_desk",
              "desk.html: open_finding"], "high"),
    ]


def build_spine(app_name: str):
    fam = FAMILIES[app_name]
    b = SpineBuilder(app_name)
    records = _names(b.seed, "record", ["r1", "r2", "r3"])
    shifts = _names(b.seed + 3, "board", ["s1", "s2", "s3"])
    record_name = {row["id"]: row["name"] for row in records}
    shift_name = {row["id"]: row["name"] for row in shifts}
    home = [
        _link("nav_roster", "名册", "roster.html", "roster"),
        _link("nav_board", "看板", "board.html", "board"),
        _link("nav_blank", "空白页", "blank.html", "blank"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("blank", "blank.html", "blank", "空白页", [], hub_role="blank", blank=True)
    roster = [
        _link(f"open_{item_id}", record_name[item_id], f"chart.html?id={item_id}", f"chart_{item_id}")
        for item_id in ("r1", "r2", "r3")
    ]
    roster.append(_back("nav_up_home", "返回首页", "index.html", "home"))
    b.add("roster", "roster.html", "roster", "名册", roster, hub_role="roster")
    for index, item_id in enumerate(("r1", "r2", "r3")):
        back_flags = {"state_variant_return": True} if index == 1 else {}
        b.add(
            f"chart_{item_id}", "chart.html", "chart", "图表", [
                _link("open_order", "医嘱", "order.html", "order"),
                _link("open_desk", "台面", "desk.html", "desk"),
                _button("btn_pin", "收藏", "dead"),
                _button("btn_cool", "下调数量", "mutate", patch=[{"key": "live_qty", "value": "6"}]),
                _back("nav_up_roster", "返回名册", "roster.html", "roster", **back_flags),
            ],
            hub_role="chart", entity=item_id, entity_source="records",
            variant_of="" if index == 0 else "chart_r1",
            obs=["shown_qty", "live_qty"],
        )
    b.add("order", "order.html", "order", "医嘱", [
        _link("open_slip", "单据", "slip.html", "slip"),
        *_status_buttons(),
        _back("nav_up_chart", "返回图表", "chart.html?id=r1", "chart_r1"),
    ], hub_role="order", obs=["status_label", "reopened"])
    b.add("slip", "slip.html", "slip", "单据", [
        *_child_controls_role("chart_order"),
        _back("nav_up_order", "返回医嘱", "order.html", "order"),
    ], hub_role="slip", obs=["handled", "handled_label", "handled_note"])
    board = [
        _link(f"open_{item_id}", shift_name[item_id], f"slot.html?id={item_id}", f"slot_{item_id}")
        for item_id in ("s1", "s2", "s3")
    ]
    board.append(_back("nav_up_home_board", "返回首页", "index.html", "home"))
    b.add("board", "board.html", "board", "看板", board, hub_role="board",
          obs=["note_kind", "note_visible"])
    for item_id in ("s1", "s2", "s3"):
        b.add(
            f"slot_{item_id}", "slot.html", "slot", "班次", [
                _link("open_notice", "通知", "notice.html", "notice"),
                _button("btn_internal", "内部标注", "mutate", patch=[
                    {"key": "note_kind", "value": "内部"},
                    {"key": "note_visible", "value": "公开"},
                ]),
                _mutate("btn_mark", "登记处理", [("handled", "是"), ("handled_label", "未登记")], "notice_slip"),
                _back("nav_up_board", "返回看板", "board.html", "board"),
            ],
            hub_role="slot", entity=item_id, entity_source="shifts",
            obs=["note_kind", "note_visible", "handled", "handled_label"],
        )
    b.add("notice", "notice.html", "notice", "通知", [
        _back("nav_up_slot", "返回班次", "slot.html?id=s1", "slot_s1"),
    ], hub_role="notice", obs=["note_kind", "note_visible"])
    b.add("desk", "desk.html", "desk", "台面", [
        _link("open_lane", "问询单", "lane.html?id=s1", "lane_a",
              path_id="horizon-main", path_index=0,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _link("open_finding", "记分页", "finding.html", "finding",
              opportunity_class="finding_return_entry_opportunity",
              guarantees_finding=True, path_id="finding-desk", path_index=0),
        _link("open_leaf", "附页", "leaf.html", "leaf"),
        _back("nav_up_chart_desk", "返回图表", "chart.html?id=r1", "chart_r1"),
    ], hub_role="desk")
    b.add("lane_a", "lane.html", "lane", "问询", [
        _link("open_lane_b", "下一段", "lane.html?id=s2", "lane_b",
              path_id="horizon-main", path_index=1,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _back("nav_up_desk", "返回台面", "desk.html", "desk"),
    ], hub_role="horizon_lane", entity="s1")
    b.add("lane_b", "lane.html", "lane", "问询", [
        _link("open_dest", "尾页", "lane.html?id=dest", "lane_dest",
              path_id="horizon-main", path_index=2,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _back("nav_up_lane", "返回上页", "lane.html?id=s1", "lane_a"),
    ], hub_role="horizon_lane", entity="s2")
    b.add("lane_dest", "lane.html", "lane", "尾页", [
        _button("btn_hold", "记下", "mutate", patch=[{"key": "hold_mark", "value": "是"}]),
        _button("btn_tag", "加标记", "mutate", patch=[{"key": "tag_mark", "value": "是"}]),
        _back("nav_up_lane_b", "返回上页", "lane.html?id=s2", "lane_b"),
    ], hub_role="horizon_destination", entity="dest", obs=["hold_mark", "tag_mark"])
    b.add("finding", "finding.html", "finding", "记分", _finding_controls([
        _back("nav_up_desk_finding", "返回台面", "desk.html", "desk"),
    ]), hub_role="finding", obs=["score_shown", "score_live", "scratch_a", "scratch_b"])
    b.add("leaf", "leaf.html", "leaf", "附页", [
        _back("nav_up_desk_leaf", "返回台面", "desk.html", "desk"),
    ], hub_role="leaf")
    b.add("help", "help.html", "help", "说明", [
        _link("open_loop", "偏好页", "settings.html", "settings"),
    ], hub_role="help")
    b.add("settings", "settings.html", "settings", "偏好", [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _button("btn_probe", "提交同步", "throw", message=fam["sync_error"]),
        _button("btn_export", "提交导出", "post"),
        _link("open_loop", "说明页", "help.html", "help"),
        _back("nav_up_chart_prefs", "返回图表", "chart.html?id=r1", "chart_r1"),
    ], hub_role="settings", obs=["form_msg"])
    topology, model = b.materialize(
        {"records": records, "shifts": shifts}, _initial())
    spec = _spec(fam["assert_prefix"])
    bugs = _positive_bugs(fam["prefix"], fam)
    return b, topology, model, bugs, spec


def _child_controls_role(role: str):
    return [
        _mutate("btn_mark", "登记处理", [("handled", "是"), ("handled_label", "未登记")], role, reveal="btn_follow"),
        _button(
            "btn_follow", "补充说明", "mutate",
            patch=[{"key": "handled_note", "value": "已补充"}],
            reveal_after="btn_mark", follow_up=True, child_local=True,
            child_workflow_role=role, family=role,
        ),
    ]


def build_shelf(app_name: str = "buggy-shelf"):
    fam = FAMILIES[app_name]
    b = SpineBuilder(app_name)
    home = [
        _link("nav_shelf", "架位", "shelf.html", "shelf"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("shelf", "shelf.html", "shelf", "架位", [
        _link("open_a", "甲格", "item.html?id=a", "item_a"),
        _link("open_b", "乙格", "item.html?id=b", "item_b"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], hub_role="shelf")
    for item_id, title in (("a", "甲格"), ("b", "乙格")):
        b.add(f"item_{item_id}", "item.html", "item", title, [
            _back("nav_up_shelf", "返回架位", "shelf.html", "shelf"),
        ], hub_role="item", entity=item_id, obs=["shown_qty", "live_qty"])
    b.add("help", "help.html", "help", "说明", [
        _link("open_loop", "偏好页", "settings.html", "settings"),
    ], hub_role="help")
    b.add("settings", "settings.html", "settings", "偏好", [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _button("btn_pin", "保存草稿", "dead"),
        _button("btn_probe", "提交同步", "throw", message=fam["sync_error"]),
        _button("btn_export", "提交导出", "post"),
        _link("open_loop", "说明页", "help.html", "help"),
        _back("nav_up_home_prefs", "返回首页", "index.html", "home"),
    ], hub_role="settings", obs=["form_msg"])
    topology, model = b.materialize({}, {
        "shown_qty": "8", "live_qty": "6", "form_msg": "", "search_state": "",
        "score_shown": "", "score_live": "",
    })
    spec = _spec("shelf")[:1]
    bugs = [
        _bug("BUG-SH1", "boundary js error", "js_error", 1, "检索词过长",
             {"error_contains": fam["search_error"]},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-SH2", "form validation", "semantic", 2, "空标题仍提示已创建",
             {"assert_id": "shelf_title_required"},
             ["index.html: nav_shelf", "shelf.html: open_a", "settings.html: btn_submit"], "high"),
        _bug("BUG-SH3", "navigation loop", "nav_loop", 2, "说明与偏好互链",
             {"cycle_urls_contains": "help.html"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: open_loop"]),
        _bug("BUG-SH4", "dead action", "dead_action", 2, "草稿点击无效果",
             {"eid": "btn_pin"}, ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_pin"]),
        _bug("BUG-SH5", "js error", "js_error", 2, "同步异常",
             {"error_contains": fam["sync_error"]},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_probe"]),
        _bug("BUG-SH6", "http 5xx", "http_error", 2, "导出 500",
             {"error_contains": "/api/export"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_export"], "high"),
        _bug("BUG-SH7", "state inconsistency", "semantic", 2, "数量不一致",
             {"assert_id": "shelf_qty_matches"},
             ["index.html: nav_shelf", "shelf.html: open_a"]),
        _bug("BUG-SH8", "state inconsistency", "semantic", 2, "分数不一致",
             {"assert_id": "shelf_score_matches"},
             ["index.html: nav_shelf"]),
    ]
    return b, topology, model, bugs, spec


def build_counter(app_name: str = "buggy-counter"):
    fam = FAMILIES[app_name]
    b = SpineBuilder(app_name)
    home = [
        _link("nav_counter", "柜台", "counter.html", "counter"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("counter", "counter.html", "counter", "柜台", [
        _link("open_t1", "取号", "ticket.html?id=t1", "ticket_t1",
              opportunity_class="finding_return_entry_opportunity",
              guarantees_finding=True, path_id="finding-t1", path_index=0),
        _link("open_t2", "补打", "ticket.html?id=t2", "ticket_t2",
              opportunity_class="finding_return_entry_opportunity",
              guarantees_finding=True, path_id="finding-t2", path_index=0),
        _link("open_lane", "问询单", "slip.html?id=s1", "lane_a",
              path_id="horizon-main", path_index=0,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], hub_role="counter")
    for item_id, title in (("t1", "取号"), ("t2", "补打")):
        b.add(f"ticket_{item_id}", "ticket.html", "ticket", title, [
            _button("btn_note_a", "记一笔", "mutate", patch=[{"key": "scratch_a", "value": "已记"}]),
            _button("btn_note_b", "标重点", "mutate", patch=[{"key": "scratch_b", "value": "已标"}]),
            _back("nav_up_counter", "返回柜台", "counter.html", "counter"),
        ], hub_role="ticket", entity=item_id, obs=["score_shown", "score_live", "scratch_a", "scratch_b"])
    b.add("lane_a", "slip.html", "slip", "问询", [
        _link("open_lane_b", "下一页", "slip.html?id=s2", "lane_b",
              path_id="horizon-main", path_index=1,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _back("nav_up_counter_a", "返回柜台", "counter.html", "counter"),
    ], hub_role="horizon_lane", entity="s1")
    b.add("lane_b", "slip.html", "slip", "问询", [
        _link("open_dest", "回执", "slip.html?id=dest", "lane_dest",
              path_id="horizon-main", path_index=2,
              opportunity_class="horizon_only_return_entry_control",
              guarantees_no_finding=True),
        _back("nav_up_lane", "返回上页", "slip.html?id=s1", "lane_a"),
    ], hub_role="horizon_lane", entity="s2")
    b.add("lane_dest", "slip.html", "slip", "回执", [
        _button("btn_hold", "记下", "mutate", patch=[{"key": "hold_mark", "value": "是"}]),
        _button("btn_tag", "加标记", "mutate", patch=[{"key": "tag_mark", "value": "是"}]),
        _back("nav_up_lane_b", "返回上页", "slip.html?id=s2", "lane_b"),
    ], hub_role="receipt", entity="dest", obs=["hold_mark", "tag_mark"])
    b.add("help", "help.html", "help", "说明", [
        _link("open_loop", "偏好页", "settings.html", "settings"),
    ], hub_role="help")
    b.add("settings", "settings.html", "settings", "偏好", [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _button("btn_pin", "保存草稿", "dead"),
        _button("btn_probe", "提交同步", "throw", message=fam["sync_error"]),
        _button("btn_export", "提交导出", "post"),
        _link("open_loop", "说明页", "help.html", "help"),
        _back("nav_up_home_prefs", "返回首页", "index.html", "home"),
    ], hub_role="settings", obs=["form_msg"])
    topology, model = b.materialize({}, {
        "score_shown": "8", "score_live": "6", "form_msg": "", "search_state": "",
        "scratch_a": "", "scratch_b": "空", "hold_mark": "", "tag_mark": "",
    })
    spec = [
        {"id": "counter_title_required", "severity": "high", "desc": "标题为空时不应提示已创建",
         "when": {"url_contains": "/settings.html"},
         "assert": {
             "op": "implies",
             "cond": {"op": "eq", "left": {"obs": "input_topic_title"}, "right": {"const": ""}},
             "then": {"op": "not_contains", "left": {"obs": "form_msg"}, "right": {"const": "已创建"}},
         }},
        {"id": "counter_score_matches", "severity": "high", "desc": "展示分数应与记录分数一致",
         "when": {"url_contains": "/ticket.html"},
         "assert": {"op": "eq", "left": {"obs": "score_shown"}, "right": {"obs": "score_live"}}},
    ]
    bugs = [
        _bug("BUG-CN1", "boundary js error", "js_error", 1, "检索词过长",
             {"error_contains": fam["search_error"]},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-CN2", "form validation", "semantic", 2, "空标题仍提示已创建",
             {"assert_id": "counter_title_required"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_submit"], "high"),
        _bug("BUG-CN3", "navigation loop", "nav_loop", 2, "说明与偏好互链",
             {"cycle_urls_contains": "help.html"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: open_loop"]),
        _bug("BUG-CN4", "dead action", "dead_action", 2, "草稿点击无效果",
             {"eid": "btn_pin"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_pin"]),
        _bug("BUG-CN5", "js error", "js_error", 2, "同步异常",
             {"error_contains": fam["sync_error"]},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_probe"]),
        _bug("BUG-CN6", "http 5xx", "http_error", 2, "导出 500",
             {"error_contains": "/api/export"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_export"], "high"),
        _bug("BUG-CN7", "state inconsistency", "semantic", 3, "分数不一致",
             {"assert_id": "counter_score_matches"},
             ["index.html: nav_counter", "counter.html: open_t1"], "high"),
        _bug("BUG-CN8", "local action", "semantic", 3, "标注不一致",
             {"assert_id": "counter_note_label"},
             ["index.html: nav_counter", "counter.html: open_t2", "ticket.html: btn_note_a"], "high"),
    ]
    return b, topology, model, bugs, spec


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_json(path, obj):
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def generate_app(app_name: str, root: str = ROOT) -> dict:
    if app_name in POSITIVE:
        builder, topology, model, bugs, spec = build_spine(app_name)
    elif app_name == "buggy-shelf":
        builder, topology, model, bugs, spec = build_shelf(app_name)
    else:
        builder, topology, model, bugs, spec = build_counter(app_name)
    fam = FAMILIES[app_name]
    seed = builder.seed
    brand = fam["brand_pool"][seed % len(fam["brand_pool"])]
    dest = os.path.join(root, "apps", app_name)
    static = os.path.join(dest, "static")
    os.makedirs(static, exist_ok=True)
    data_pages = {node["page"]: node["data_page"] for node in builder.nodes}
    for page in builder.files:
        _write(os.path.join(static, page), HTML.format(title=f"{brand}·{page}", page=data_pages[page]))
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    _write(os.path.join(static, "app.js"), JS.replace("__MODEL__", payload))
    _write(os.path.join(dest, "server.py"), SERVER.format(
        title=brand, default_port=fam["port"], fail_path=FAIL_PATH, fail_error=fam["fail_error"]))
    _write_json(os.path.join(dest, "bugs.manifest.json"), {
        "app": app_name,
        "note": "BENCHMARK JUDGE ONLY. GhostQA exploration must never read this file.",
        "bugs": bugs,
    })
    _write_json(os.path.join(dest, "spec.json"), {"app": app_name, "assertions": spec})
    _write_json(os.path.join(dest, "topology.json"), topology)
    qual = qualify_topology(topology)
    _write_json(os.path.join(dest, "mechanism-opportunities.json"), {
        "app": app_name,
        "note": "Judge qualification. Not served. Exploration must not read this file.",
        "qualified": qual["qualified"],
        "summary": {
            key: qual[key] for key in (
                "qualified", "hub_count", "max_nested_branch_depth",
                "nested_handoff_opportunity_count", "handoff_edge_count",
                "finding_return_entry_opportunity_count",
                "horizon_only_return_entry_control_count",
                "state_variant_return_count", "distinct_child_workflows",
            ) if key in qual
        },
    })
    _write_json(os.path.join(dest, "generation.json"), {
        "app": app_name, "seed": builder.seed, "seed_hex": builder.seed_hex,
        "family": fam["family"], "port": fam["port"],
    })
    _write(os.path.join(dest, "README.md"), f"# {app_name}\n\nGenerated for v0.3.25. Judge files are not served.\n")
    return qual


def main() -> int:
    bad = []
    for app in POSITIVE + NEGATIVE:
        qual = generate_app(app)
        print(app, "qualified", qual["qualified"],
              "nested", qual["nested_handoff_opportunity_count"],
              "handoff", qual["handoff_edge_count"],
              "finding", qual["finding_return_entry_opportunity_count"],
              "horizon", qual["horizon_only_return_entry_control_count"],
              "roles", qual.get("distinct_child_workflows"))
        if not qual["qualified"]:
            bad.append(app)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
