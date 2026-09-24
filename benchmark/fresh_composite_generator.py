"""Deterministic v0.3.20 target generator.

One graph per frozen app identity. Inputs are the app name, the frozen seed,
the frozen topology family, and the vocabulary tables. No exploration,
runner, analysis, or result imports.
"""
from __future__ import annotations

import argparse
import json
import os

from benchmark.fresh_composite_js import HTML, JS, SERVER
from benchmark.fresh_composite_vocab import (
    APP_NAMES, FAMILIES, SEED_PREFIX, assign_names, contains_non_branch, resolve_seed,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAIL_PATH = "/api/export"
EDGE_FIELDS = (
    "parent_return", "returns_to", "alternate_child_completion", "family",
    "child_workflow_role", "child_local", "follow_up", "guarantees_finding",
    "guarantees_no_finding", "path_id", "path_index", "opportunity_class",
    "state_variant_return",
)


def _link(testid, text, href, dst, **extra):
    row = {"kind": "link", "testid": testid, "text": text, "href": href, "dst": dst, "effect": "goto"}
    row.update(extra)
    return row


def _button(testid, text, effect="dead", **extra):
    row = {"kind": "button", "testid": testid, "text": text, "effect": effect, "dst": ""}
    row.update(extra)
    return row


def _input(testid, text):
    return {"kind": "input", "testid": testid, "text": text, "effect": "", "dst": ""}


def _back(testid, text, href, dst, **extra):
    return _link(testid, text, href, dst, parent_return=True, returns_to=dst, **extra)


def _mutate(testid, text, patch, role, reveal=""):
    row = _button(
        testid, text, "mutate",
        patch=[{"key": key, "value": value} for key, value in patch],
        child_local=True, child_workflow_role=role, family=role,
    )
    if reveal:
        row["reveal"] = reveal
    return row


def _public_control(ctl):
    keep = (
        "kind", "testid", "text", "href", "effect", "message", "input", "obs_key",
        "patch", "reveal", "reveal_after", "when_entity", "when_no_entity",
    )
    return {key: ctl[key] for key in keep if key in ctl and ctl[key] not in ("", None, False, [])}


class Builder:
    def __init__(self, app_name: str):
        if app_name not in FAMILIES:
            raise ValueError(app_name)
        self.app = app_name
        self.fam = FAMILIES[app_name]
        self.seed, self.seed_hex = resolve_seed(app_name)
        self.nodes = []
        self.control_map = {}
        self.files = []

    def add(self, node_id, page, data_page, title, controls, *, hub_role,
            entity="", entity_source="", obs=None, blank=False, variant_of=""):
        self.nodes.append({
            "id": node_id,
            "page": page,
            "data_page": data_page,
            "title": title,
            "hub_role": hub_role,
            "entity": entity,
            "entity_source": entity_source,
            "obs": list(obs or []),
            "blank": blank,
            "variant_of": variant_of,
        })
        self.control_map[node_id] = list(controls)
        if page not in self.files:
            self.files.append(page)

    def _visible(self, controls, entity):
        out = []
        for ctl in controls:
            if ctl.get("reveal_after"):
                continue
            if ctl.get("when_entity") and ctl["when_entity"] != entity:
                continue
            out.append(ctl)
        return out

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
            visible = self._visible(controls, node.get("entity") or "")
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
            hub = len(branch_actions) >= 3
            first = branch_actions[0]["testid"] if branch_actions else ""
            topo_nodes.append({
                "id": node["id"],
                "page": node["page"],
                "hub": hub,
                "hub_role": node["hub_role"],
                "entity": node.get("entity") or "",
                "variant_of": node.get("variant_of") or "",
                "first_branch_action": first,
                "blank": node["blank"],
                "eligible_buttons": eligible,
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
                    "src": node["id"],
                    "dst": dst,
                    "action": ctl["testid"],
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
            obs = []
            obs_by_entity = {}
            controls = []
            entity_source = ""
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


def _names(seed, pool, ids):
    mapping = assign_names(seed, pool, ids)
    return [{"id": item_id, "name": mapping[item_id]} for item_id in ids]


def _by_id(rows):
    return {row["id"]: row["name"] for row in rows}


def _child_controls(role, back_href, back_dst):
    return [
        _mutate("btn_mark", "登记处理", [("handled", "是"), ("handled_label", "未登记")], role, reveal="btn_follow"),
        _button(
            "btn_follow", "补充说明", "mutate",
            patch=[{"key": "handled_note", "value": "已补充"}],
            reveal_after="btn_mark", follow_up=True, child_local=True,
            child_workflow_role=role, family=role,
        ),
        _back("nav_up_child", "返回上页", back_href, back_dst),
    ]


def _status_buttons():
    return [
        _button("btn_close", "关闭条目", "mutate", patch=[{"key": "status_label", "value": "已关闭"}]),
        _button("btn_reopen", "重新打开", "mutate", patch=[{"key": "reopened", "value": "是"}]),
    ]


def _finding_controls(back_links):
    rows = [
        _button("btn_note_a", "记一笔", "mutate", patch=[{"key": "scratch_a", "value": "已记"}]),
        _button("btn_note_b", "标重点", "mutate", patch=[{"key": "scratch_b", "value": "已标"}]),
    ]
    rows.extend(back_links)
    return rows


def _search(controls, message):
    controls.extend([
        _input("search_box", "检索词"),
        _button("btn_query_submit", "提交查询", "search", input="search_box", message=message, obs_key="search_state"),
    ])
    return controls


def _positive_initial():
    return {
        "score_shown": "8", "score_live": "6",
        "shown_qty": "8", "live_qty": "8",
        "status_label": "跟进中", "reopened": "否",
        "note_kind": "", "note_visible": "",
        "handled": "", "handled_label": "", "handled_note": "",
        "form_msg": "", "search_state": "", "variant_note": "原稿",
        "scratch_a": "", "scratch_b": "", "hold_mark": "", "tag_mark": "",
    }


def _spec(prefix, form_url, qty_url, seq_url, cross_url, finding_url):
    def implies(cond_obs, cond_val, then_op, then_obs, then_val):
        return {
            "op": "implies",
            "cond": {"op": "eq", "left": {"obs": cond_obs}, "right": {"const": cond_val}},
            "then": {"op": then_op, "left": {"obs": then_obs}, "right": {"const": then_val}},
        }
    return [
        {
            "id": f"{prefix}_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": form_url},
            "assert": implies("input_topic_title", "", "not_contains", "form_msg", "已创建"),
        },
        {
            "id": f"{prefix}_qty_matches",
            "severity": "medium",
            "desc": "展示数量应与剩余数量一致",
            "when": {"url_contains": qty_url},
            "assert": {"op": "eq", "left": {"obs": "shown_qty"}, "right": {"obs": "live_qty"}},
        },
        {
            "id": f"{prefix}_reopen_clears",
            "severity": "high",
            "desc": "重新打开后不应仍显示已关闭",
            "when": {"url_contains": seq_url},
            "assert": implies("reopened", "是", "ne", "status_label", "已关闭"),
        },
        {
            "id": f"{prefix}_note_visibility",
            "severity": "high",
            "desc": "内部摘记不应显示为公开",
            "when": {"url_contains": cross_url},
            "assert": implies("note_kind", "内部", "eq", "note_visible", "内部"),
        },
        {
            "id": f"{prefix}_handled_label",
            "severity": "high",
            "desc": "登记之后标记不应仍是未登记",
            "when": {"url_contains": seq_url},
            "assert": implies("handled", "是", "eq", "handled_label", "已登记"),
        },
        {
            "id": f"{prefix}_score_matches",
            "severity": "high",
            "desc": "展示分数应与记录分数一致",
            "when": {"url_contains": finding_url},
            "assert": {"op": "eq", "left": {"obs": "score_shown"}, "right": {"obs": "score_live"}},
        },
    ]


def _bug(bid, category, kind, depth, desc, match, steps, severity="medium"):
    return {
        "id": bid, "category": category, "severity": severity, "desc": desc,
        "kind": kind, "trigger_depth": depth, "prerequisites": [],
        "match": match, "min_reproduction": steps,
    }


def _positive_bugs(prefix, fam, cfg):
    p = prefix
    home = "index.html"
    ent = cfg["entity_file"]
    mid = cfg["mid_file"]
    child = cfg["child_file"]
    side = cfg["side_file"]
    side_ent = cfg["side_entity_file"]
    mid_b = cfg["mid_b_file"]
    finding = cfg["finding_file"]
    blank = cfg["blank_file"]
    return [
        _bug(f"{p}1", "blank page", "blank", 2, "列表架渲染后完全空白",
             {"url_contains": "/" + blank},
             [f"{home}: {cfg['blank_id']}"], "high"),
        _bug(f"{p}2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": fam["search_error"]},
             [f"{home}: search_box=25 chars", f"{home}: btn_query_submit"]),
        _bug(f"{p}3", "navigation loop", "nav_loop", 2, "说明页与相邻页互相链接",
             {"cycle_urls_contains": "help.html"},
             list(cfg["loop_steps"])),
        _bug(f"{p}4", "form validation", "semantic", 3, "标题为空时仍提示已创建",
             {"assert_id": f"{cfg['assert_prefix']}_title_required"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: nav_prefs", "settings.html: btn_submit"], "high"),
        _bug(f"{p}5", "dead action", "dead_action", 3, "明细页收藏点击无效果",
             {"eid": "btn_pin"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: btn_pin"]),
        _bug(f"{p}6", "js error", "js_error", 4, "偏好页测试同步抛出未捕获异常",
             {"error_contains": fam["sync_error"]},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: nav_prefs", "settings.html: btn_probe"]),
        _bug(f"{p}7", "http 5xx", "http_error", 4, "导出请求返回 500",
             {"error_contains": "/api/export"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: nav_prefs", "settings.html: btn_export"], "high"),
        _bug(f"{p}8", "state inconsistency", "semantic", 4, "下调数量后展示值未更新",
             {"assert_id": f"{cfg['assert_prefix']}_qty_matches"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: btn_cool"]),
        _bug(f"{p}9", "cross-page consistency", "semantic", 5, "内部摘记在相邻页显示为公开",
             {"assert_id": f"{cfg['assert_prefix']}_note_visibility"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: open_side", f"{side}: open_side_{cfg['side_ids'][0]}",
              f"{side_ent}: btn_staff_note", f"{side_ent}: open_mid_b"], "high"),
        _bug(f"{p}10", "sequence-dependent", "semantic", 6, "关闭后再打开仍显示已关闭",
             {"assert_id": f"{cfg['assert_prefix']}_reopen_clears"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: open_mid", f"{mid}: btn_close", f"{mid}: btn_reopen",
              f"{mid}: open_child_a"], "high"),
        _bug(f"{p}11", "local action return", "semantic", 5, "登记后的本地标记仍写着未登记",
             {"assert_id": f"{cfg['assert_prefix']}_handled_label"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_row_{cfg['list_ids'][0]}",
              f"{ent}: open_mid", f"{mid}: open_child_a", f"{child}: btn_mark"], "high"),
        _bug(f"{p}12", "state inconsistency", "semantic", 4, "分数展示与记录不一致",
             {"assert_id": f"{cfg['assert_prefix']}_score_matches"},
             [f"{home}: {cfg['primary_id']}", f"{cfg['list_file']}: open_finding"], "high"),
    ]


def _settings(back_href, back_dst, fam, loop_text, loop_href, loop_dst):
    return [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _button("btn_probe", "测试同步", "throw", message=fam["sync_error"]),
        _button("btn_export", "导出", "post"),
        _link("open_loop_from_prefs", loop_text, loop_href, loop_dst) if loop_href else _back(
            "nav_up_from_prefs", "返回上页", back_href, back_dst),
        _back("nav_up_from_prefs", "返回上页", back_href, back_dst),
    ]


def _help_controls(loop_text, loop_href, loop_dst, extra=None):
    rows = [_link("open_loop", loop_text, loop_href, loop_dst)]
    if extra:
        rows.append(extra)
    return rows


def build_positive(app_name: str):
    cfg = POSITIVE_CFG[app_name]
    fam = FAMILIES[app_name]
    b = Builder(app_name)
    seed = b.seed
    list_rows = _names(seed, cfg["list_pool"], cfg["list_ids"])
    side_rows = _names(seed + 1, cfg["side_pool"], cfg["side_ids"])
    list_name = _by_id(list_rows)
    side_name = _by_id(side_rows)
    role_a = cfg["role_a"]
    role_b = cfg["role_b"]
    home = [
        _link(cfg["primary_id"], cfg["primary_text"], cfg["list_file"], "list_hub"),
        _link(cfg["blank_id"], cfg["blank_text"], cfg["blank_file"], "blank"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("blank", cfg["blank_file"], cfg["blank_page"], cfg["blank_text"], [], hub_role="blank", blank=True)
    list_controls = []
    for item_id in cfg["list_ids"]:
        list_controls.append(_link(
            f"open_row_{item_id}", list_name[item_id],
            f"{cfg['entity_file']}?id={item_id}", f"row_{item_id}",
        ))
    list_controls.append(_link(
        "open_finding", cfg["finding_text"], cfg["finding_file"], "finding",
        opportunity_class="finding_return_entry_opportunity",
        guarantees_finding=True, path_id="finding-main", path_index=0,
    ))
    list_controls.append(_back("nav_up_home", "返回首页", "index.html", "home"))
    b.add("list_hub", cfg["list_file"], cfg["list_page"], cfg["list_title"], list_controls,
          hub_role=cfg["list_role"])
    for item_id in cfg["list_ids"]:
        b.add(
            f"row_{item_id}", cfg["entity_file"], cfg["entity_page"], cfg["entity_title"], [
                _link("open_mid", cfg["mid_text"], cfg["mid_file"], "mid"),
                _link("open_side", cfg["side_text"], cfg["side_file"], "side_hub"),
                _link("nav_prefs", "偏好", "settings.html", "settings"),
                _button("btn_pin", "收藏", "dead"),
                _button("btn_cool", "下调数量", "mutate", patch=[{"key": "live_qty", "value": "6"}]),
                _back("nav_up_list", "返回上页", cfg["list_file"], "list_hub"),
            ],
            hub_role=cfg["entity_role"], entity=item_id, entity_source="list_rows",
            obs=["shown_qty", "live_qty"],
        )
    child_href = cfg["child_file"]
    mid_controls = []
    for suffix in ("a", "b", "c"):
        mid_controls.append(_link(
            f"open_child_{suffix}", cfg["child_text"],
            f"{child_href}?id={suffix}", f"child_{suffix}",
            family=role_a,
        ))
    mid_controls.extend(_status_buttons())
    mid_controls.append(_back("nav_up_row", "返回上页", f"{cfg['entity_file']}?id={cfg['list_ids'][0]}", f"row_{cfg['list_ids'][0]}"))
    b.add("mid", cfg["mid_file"], cfg["mid_page"], cfg["mid_title"], mid_controls, hub_role=cfg["mid_role"])
    for suffix in ("a", "b", "c"):
        b.add(
            f"child_{suffix}", cfg["child_file"], cfg["child_page"], cfg["child_title"],
            _child_controls(role_a, cfg["mid_file"], "mid"),
            hub_role=cfg["child_role"], entity=suffix, obs=["status_label", "reopened", "handled", "handled_label", "handled_note"],
        )
    side_controls = []
    for item_id in cfg["side_ids"]:
        side_controls.append(_link(
            f"open_side_{item_id}", side_name[item_id],
            f"{cfg['side_entity_file']}?id={item_id}", f"side_{item_id}",
        ))
    side_controls.append(_back("nav_up_home_side", "返回首页", "index.html", "home"))
    b.add("side_hub", cfg["side_file"], cfg["side_page"], cfg["side_title"], side_controls,
          hub_role=cfg["side_role"], obs=["note_kind", "note_visible", "variant_note"])
    for index, item_id in enumerate(cfg["side_ids"]):
        back_flags = {"state_variant_return": True} if index == 1 else {}
        b.add(
            f"side_{item_id}", cfg["side_entity_file"], cfg["side_entity_page"], cfg["side_entity_title"], [
                _link("open_mid_b", cfg["mid_b_text"], cfg["mid_b_file"], "mid_b"),
                _link("open_cross", cfg["cross_text"], cfg["anchor_file"], "anchor"),
                _button("btn_variant", "改注记", "mutate", patch=[{"key": "variant_note", "value": "已改"}]),
                _button("btn_staff_note", "内部摘记", "mutate", patch=[
                    {"key": "note_kind", "value": "内部"},
                    {"key": "note_visible", "value": "公开"},
                ]),
                _back("nav_up_side", "返回上页", cfg["side_file"], "side_hub", **back_flags),
            ],
            hub_role=cfg["side_entity_role"], entity=item_id, entity_source="side_rows",
            variant_of="" if index == 0 else f"side_{cfg['side_ids'][0]}",
            obs=["variant_note", "note_kind", "note_visible"],
        )
    mid_b_controls = []
    for suffix in ("a", "b", "c"):
        mid_b_controls.append(_link(
            f"open_child_b_{suffix}", cfg["child_b_text"],
            f"{cfg['child_b_file']}?id={suffix}", f"child_b_{suffix}",
            family=role_b,
        ))
    mid_b_controls.extend(_status_buttons())
    mid_b_controls.append(_back(
        "nav_up_side_row", "返回上页",
        f"{cfg['side_entity_file']}?id={cfg['side_ids'][0]}", f"side_{cfg['side_ids'][0]}",
    ))
    b.add("mid_b", cfg["mid_b_file"], cfg["mid_b_page"], cfg["mid_b_title"], mid_b_controls,
          hub_role=cfg["mid_b_role"], obs=["note_kind", "note_visible"])
    for suffix in ("a", "b", "c"):
        b.add(
            f"child_b_{suffix}", cfg["child_b_file"], cfg["child_b_page"], cfg["child_b_title"],
            _child_controls(role_b, cfg["mid_b_file"], "mid_b"),
            hub_role=cfg["child_b_role"], entity=suffix,
            obs=["status_label", "reopened", "handled", "handled_label", "handled_note"],
        )
    b.add("finding", cfg["finding_file"], cfg["finding_page"], cfg["finding_title"], _finding_controls([
        _back("nav_up_finding", "返回上页", cfg["list_file"], "list_hub"),
        _back("nav_up_anchor", "返回名册", cfg["anchor_file"], "anchor"),
    ]), hub_role=cfg["finding_role"], obs=["score_shown", "score_live", "scratch_a", "scratch_b"])
    b.add("anchor", cfg["anchor_file"], cfg["anchor_page"], cfg["anchor_title"], [
        _link(
            "open_lane_a", cfg["lane_text"], f"{cfg['lane_file']}?id=s1", "lane_a",
            path_id="horizon-main", path_index=0,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _link(
            "open_finding_b", cfg["finding_text"], cfg["finding_file"], "finding",
            opportunity_class="finding_return_entry_opportunity",
            guarantees_finding=True, path_id="finding-anchor", path_index=0,
        ),
        _link("open_leaf", cfg["leaf_text"], cfg["leaf_file"], cfg["leaf_node"]),
        _back("nav_up_home_anchor", "返回首页", "index.html", "home"),
    ], hub_role=cfg["anchor_role"])
    b.add("lane_a", cfg["lane_file"], cfg["lane_page"], cfg["lane_title"], [
        _link(
            "open_lane_b", "下一段", f"{cfg['lane_file']}?id=s2", "lane_b",
            path_id="horizon-main", path_index=1,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _back("nav_up_anchor_a", "返回上页", cfg["anchor_file"], "anchor"),
    ], hub_role="horizon_lane", entity="s1")
    b.add("lane_b", cfg["lane_file"], cfg["lane_page"], cfg["lane_title"], [
        _link(
            "open_dest", cfg["dest_text"], f"{cfg['lane_file']}?id=dest", "lane_dest",
            path_id="horizon-main", path_index=2,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _back("nav_up_lane", "返回上页", f"{cfg['lane_file']}?id=s1", "lane_a"),
    ], hub_role="horizon_lane", entity="s2")
    b.add("lane_dest", cfg["lane_file"], cfg["lane_page"], cfg["dest_title"], [
        _button("btn_hold", "记下", "mutate", patch=[{"key": "hold_mark", "value": "是"}]),
        _button("btn_tag", "加标记", "mutate", patch=[{"key": "tag_mark", "value": "是"}]),
        _back("nav_up_lane_b", "返回上页", f"{cfg['lane_file']}?id=s2", "lane_b"),
    ], hub_role="horizon_destination", entity="dest", obs=["hold_mark", "tag_mark"])
    if cfg["loop_file"] == "handbook.html":
        b.add("handbook", "handbook.html", "handbook", "手册", [
            _back("nav_up_help", "返回说明", "help.html", "help"),
        ], hub_role="handbook")
    help_extra = None
    if cfg["extras"]:
        first = cfg["extras"][0]
        help_extra = _link("open_extra_0", first["text"], first["file"], "extra_0")
    b.add("help", "help.html", "help", "说明", _help_controls(
        cfg["loop_link_text"], cfg["loop_file"], cfg["loop_node"], help_extra,
    ), hub_role="help")
    prev = "help"
    prev_href = "help.html"
    for index, extra in enumerate(cfg["extras"]):
        nxt = cfg["extras"][index + 1] if index + 1 < len(cfg["extras"]) else None
        controls = []
        if nxt:
            controls.append(_link(f"open_extra_{index + 1}", nxt["text"], nxt["file"], f"extra_{index + 1}"))
        controls.append(_back(f"nav_up_extra_{index}", "返回上页", prev_href, prev if index == 0 else f"extra_{index - 1}"))
        b.add(f"extra_{index}", extra["file"], extra["page"], extra["text"], controls, hub_role="extra")
        prev = f"extra_{index}"
        prev_href = extra["file"]
    pref_back_href = f"{cfg['entity_file']}?id={cfg['list_ids'][0]}"
    settings_controls = [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _button("btn_probe", "提交同步", "throw", message=fam["sync_error"]),
        _button("btn_export", "提交导出", "post"),
        _back("nav_up_from_prefs", "返回上页", pref_back_href, f"row_{cfg['list_ids'][0]}"),
    ]
    if cfg["loop_file"] == "settings.html":
        settings_controls.insert(4, _link("open_loop", "说明页", "help.html", "help"))
    b.add("settings", "settings.html", "settings", "偏好", settings_controls, hub_role="settings", obs=["form_msg"])
    entities = {"list_rows": list_rows, "side_rows": side_rows}
    topology, model = b.materialize(entities, _positive_initial())
    topology["expected_control_class"] = "positive"
    spec = _spec(
        cfg["assert_prefix"], "/settings.html", "/" + cfg["entity_file"],
        "/" + cfg["child_file"], "/" + cfg["mid_b_file"], "/" + cfg["finding_file"],
    )
    bugs = _positive_bugs(fam["prefix"], fam, cfg)
    return b, topology, model, bugs, spec


def build_catalog(seed: int):
    del seed
    fam = FAMILIES["buggy-catalog"]
    b = Builder("buggy-catalog")
    products = _names(b.seed, "product", ["p1", "p2", "p3"])
    pname = _by_id(products)
    home = [
        _link("nav_categories", "分类", "categories.html", "categories"),
        _link("nav_search", "查找", "search.html", "search"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("categories", "categories.html", "categories", "分类", [
        _link("open_p1", pname["p1"], "product.html?id=p1", "product_p1"),
        _link("open_p2", pname["p2"], "product.html?id=p2", "product_p2"),
        _link("open_p3", pname["p3"], "product.html?id=p3", "product_p3"),
        _link("nav_products", "全部样品", "products.html", "products"),
        _link("open_compare", "并排页", "compare.html", "compare"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], hub_role="category_list")
    b.add("products", "products.html", "products", "样品", [
        _back("nav_up_categories", "返回分类", "categories.html", "categories"),
    ], hub_role="product_list")
    for item_id in ("p1", "p2", "p3"):
        b.add(f"product_{item_id}", "product.html", "product", "样品明细", [
            _back("nav_up_products", "返回样品", "products.html", "products"),
        ], hub_role="product", entity=item_id, entity_source="products", obs=["shown_qty", "live_qty"])
    b.add("compare", "compare.html", "compare", "并排", [], hub_role="compare", blank=True)
    b.add("search", "search.html", "search", "查找", [
        _back("nav_up_home_search", "返回首页", "index.html", "home"),
    ], hub_role="search")
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
    topology, model = b.materialize(
        {"products": products},
        {
            "shown_qty": "8", "live_qty": "6", "form_msg": "", "search_state": "",
            "score_shown": "", "score_live": "",
        },
    )
    topology["expected_control_class"] = "catalog"
    spec = [
        {
            "id": "catalog_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": "/settings.html"},
            "assert": {
                "op": "implies",
                "cond": {"op": "eq", "left": {"obs": "input_topic_title"}, "right": {"const": ""}},
                "then": {"op": "not_contains", "left": {"obs": "form_msg"}, "right": {"const": "已创建"}},
            },
        },
        {
            "id": "catalog_qty_matches",
            "severity": "medium",
            "desc": "展示数量应与剩余数量一致",
            "when": {"url_contains": "/product.html"},
            "assert": {"op": "eq", "left": {"obs": "shown_qty"}, "right": {"obs": "live_qty"}},
        },
    ]
    bugs = [
        _bug("BUG-CT1", "blank page", "blank", 2, "并排页渲染后完全空白",
             {"url_contains": "/compare.html"},
             ["index.html: nav_categories", "categories.html: open_compare"], "high"),
        _bug("BUG-CT2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": fam["search_error"]},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-CT3", "navigation loop", "nav_loop", 2, "说明与偏好互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: open_loop",
              "help.html: open_loop", "settings.html: open_loop"]),
        _bug("BUG-CT4", "form validation", "semantic", 2, "标题为空时仍提示已创建",
             {"assert_id": "catalog_title_required"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_submit"], "high"),
        _bug("BUG-CT5", "dead action", "dead_action", 2, "保存草稿点击无效果",
             {"eid": "btn_pin"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_pin"]),
        _bug("BUG-CT6", "js error", "js_error", 2, "偏好页同步抛出未捕获异常",
             {"error_contains": fam["sync_error"]},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_probe"]),
        _bug("BUG-CT7", "http 5xx", "http_error", 2, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_export"], "high"),
        _bug("BUG-CT8", "state inconsistency", "semantic", 3, "样品展示数量与剩余数量不一致",
             {"assert_id": "catalog_qty_matches"},
             ["index.html: nav_categories", "categories.html: open_p1"], "high"),
    ]
    return b, topology, model, bugs, spec


def build_kiosk(seed: int):
    del seed
    fam = FAMILIES["buggy-kiosk"]
    b = Builder("buggy-kiosk")
    home = [
        _link("nav_kiosk", "柜台", "kiosk.html", "kiosk"),
        _link("open_aid", "帮助", "help.html", "help"),
    ]
    _search(home, fam["search_error"])
    b.add("home", "index.html", "home", "首页", home, hub_role="entry", obs=["search_state"])
    b.add("kiosk", "kiosk.html", "kiosk", "柜台", [
        _link(
            "open_task_t1", "取号", "task.html?id=t1", "task_t1",
            opportunity_class="finding_return_entry_opportunity",
            guarantees_finding=True, path_id="finding-t1", path_index=0,
        ),
        _link(
            "open_task_t2", "补打", "task.html?id=t2", "task_t2",
            opportunity_class="finding_return_entry_opportunity",
            guarantees_finding=True, path_id="finding-t2", path_index=0,
        ),
        _link(
            "open_lane_a", "问询单", "receipt.html?id=s1", "lane_a",
            path_id="horizon-main", path_index=0,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], hub_role="kiosk_panel")
    for item_id, title in (("t1", "取号"), ("t2", "补打")):
        b.add(f"task_{item_id}", "task.html", "task", title, [
            _button("btn_note_a", "记一笔", "mutate", patch=[{"key": "scratch_a", "value": "已记"}]),
            _button("btn_note_b", "标重点", "mutate", patch=[{"key": "scratch_b", "value": "已标"}]),
            _back("nav_up_kiosk", "返回柜台", "kiosk.html", "kiosk"),
        ], hub_role="task_panel", entity=item_id,
              obs=["score_shown", "score_live", "scratch_a", "scratch_b"])
    b.add("lane_a", "receipt.html", "receipt", "问询", [
        _link(
            "open_lane_b", "下一页", "receipt.html?id=s2", "lane_b",
            path_id="horizon-main", path_index=1,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _back("nav_up_kiosk_a", "返回柜台", "kiosk.html", "kiosk"),
    ], hub_role="horizon_lane", entity="s1")
    b.add("lane_b", "receipt.html", "receipt", "问询", [
        _link(
            "open_dest", "小票", "receipt.html?id=dest", "lane_dest",
            path_id="horizon-main", path_index=2,
            opportunity_class="horizon_only_return_entry_control",
            guarantees_no_finding=True,
        ),
        _back("nav_up_lane", "返回上页", "receipt.html?id=s1", "lane_a"),
    ], hub_role="horizon_lane", entity="s2")
    b.add("lane_dest", "receipt.html", "receipt", "小票", [
        _button("btn_hold", "记下", "mutate", patch=[{"key": "hold_mark", "value": "是"}]),
        _button("btn_tag", "加标记", "mutate", patch=[{"key": "tag_mark", "value": "是"}]),
        _back("nav_up_lane_b", "返回上页", "receipt.html?id=s2", "lane_b"),
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
        "score_shown": "8", "score_live": "6",
        "form_msg": "", "search_state": "",
        "scratch_a": "", "scratch_b": "空", "hold_mark": "", "tag_mark": "",
    })
    topology["expected_control_class"] = "kiosk"
    spec = [
        {
            "id": "kiosk_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": "/settings.html"},
            "assert": {
                "op": "implies",
                "cond": {"op": "eq", "left": {"obs": "input_topic_title"}, "right": {"const": ""}},
                "then": {"op": "not_contains", "left": {"obs": "form_msg"}, "right": {"const": "已创建"}},
            },
        },
        {
            "id": "kiosk_score_matches",
            "severity": "high",
            "desc": "展示分数应与记录分数一致",
            "when": {"url_contains": "/task.html"},
            "assert": {"op": "eq", "left": {"obs": "score_shown"}, "right": {"obs": "score_live"}},
        },
        {
            "id": "kiosk_note_label",
            "severity": "medium",
            "desc": "记一笔后摘记不应为空",
            "when": {"url_contains": "/task.html"},
            "assert": {
                "op": "implies",
                "cond": {"op": "eq", "left": {"obs": "scratch_a"}, "right": {"const": "已记"}},
                "then": {"op": "eq", "left": {"obs": "scratch_b"}, "right": {"const": "已记"}},
            },
        },
    ]
    bugs = [
        _bug("BUG-KS1", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": fam["search_error"]},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-KS2", "navigation loop", "nav_loop", 2, "说明与偏好互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: open_loop",
              "help.html: open_loop", "settings.html: open_loop"]),
        _bug("BUG-KS3", "form validation", "semantic", 2, "标题为空时仍提示已创建",
             {"assert_id": "kiosk_title_required"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_submit"], "high"),
        _bug("BUG-KS4", "dead action", "dead_action", 2, "保存草稿点击无效果",
             {"eid": "btn_pin"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_pin"]),
        _bug("BUG-KS5", "js error", "js_error", 2, "偏好页同步抛出未捕获异常",
             {"error_contains": fam["sync_error"]},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_probe"]),
        _bug("BUG-KS6", "http 5xx", "http_error", 3, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: open_aid", "help.html: open_loop", "settings.html: btn_export"], "high"),
        _bug("BUG-KS7", "state inconsistency", "semantic", 2, "任务分数展示与记录不一致",
             {"assert_id": "kiosk_score_matches"},
             ["index.html: nav_kiosk", "kiosk.html: open_task_t1"], "high"),
        _bug("BUG-KS8", "local mutation", "semantic", 3, "只记一笔时另一标记被要求相同",
             {"assert_id": "kiosk_note_label"},
             ["index.html: nav_kiosk", "kiosk.html: open_task_t2", "task.html: btn_note_a"], "high"),
    ]
    return b, topology, model, bugs, spec


def _cfg(**kwargs):
    return kwargs


POSITIVE_CFG = {
    "buggy-campus": _cfg(
        list_pool="course", side_pool="lesson", list_ids=["c1", "c2", "c3"], side_ids=["l1", "l2", "l3"],
        role_a="assessment_record", role_b="feedback_note", assert_prefix="campus",
        primary_id="nav_courses", primary_text="课程", list_file="courses.html", list_page="courses", list_title="课程", list_role="course_hub",
        blank_id="nav_shelf", blank_text="模块架", blank_file="modules.html", blank_page="modules",
        entity_file="course.html", entity_page="course", entity_title="课程明细", entity_role="course",
        mid_text="单元", mid_file="module.html", mid_page="module", mid_title="单元", mid_role="module",
        child_text="测验单", child_file="quiz.html", child_page="quiz", child_title="测验", child_role="quiz_child",
        side_text="课节", side_file="lessons.html", side_page="lessons", side_title="课节", side_role="lesson_hub",
        side_entity_file="lesson.html", side_entity_page="lesson", side_entity_title="课节明细", side_entity_role="lesson",
        mid_b_text="讲评", mid_b_file="review.html", mid_b_page="review", mid_b_title="讲评", mid_b_role="review",
        child_b_text="反馈单", child_b_file="feedback.html", child_b_page="feedback", child_b_title="反馈", child_b_role="feedback_child",
        finding_text="成绩页", finding_file="gradebook.html", finding_page="gradebook", finding_title="成绩", finding_role="gradebook",
        anchor_file="student.html", anchor_page="student", anchor_title="学员", anchor_role="student",
        lane_text="答卷", lane_file="submission.html", lane_page="submission", lane_title="答卷", dest_text="答卷页", dest_title="答卷整理",
        leaf_text="手册页", leaf_file="handbook.html", leaf_node="handbook",
        loop_file="handbook.html", loop_node="handbook", loop_link_text="打开手册",
        loop_steps=(
            "index.html: open_aid", "help.html: open_loop", "handbook.html: nav_up_help",
            "help.html: open_loop", "handbook.html: nav_up_help",
        ),
        extras=[],
        cross_text="学员页",
    ),
    "buggy-warehouse": _cfg(
        list_pool="warehouse", side_pool="item", list_ids=["w1", "w2", "w3"], side_ids=["i1", "i2", "i3"],
        role_a="transfer_capture", role_b="audit_count", assert_prefix="warehouse",
        primary_id="nav_warehouses", primary_text="仓库", list_file="warehouses.html", list_page="warehouses", list_title="仓库", list_role="warehouse_hub",
        blank_id="nav_rollup", blank_text="汇总", blank_file="reports.html", blank_page="reports",
        entity_file="warehouse.html", entity_page="warehouse", entity_title="仓库明细", entity_role="warehouse",
        mid_text="库区", mid_file="zone.html", mid_page="zone", mid_title="库区", mid_role="zone",
        child_text="调拨单", child_file="transfer.html", child_page="transfer", child_title="调拨", child_role="transfer_child",
        side_text="货品", side_file="items.html", side_page="items", side_title="货品", side_role="item_hub",
        side_entity_file="item.html", side_entity_page="item", side_entity_title="货品明细", side_entity_role="item",
        mid_b_text="批次", mid_b_file="batch.html", mid_b_page="batch", mid_b_title="批次", mid_b_role="batch",
        child_b_text="盘点单", child_b_file="audit.html", child_b_page="audit", child_b_title="盘点", child_b_role="audit_child",
        finding_text="抽检页", finding_file="inspection.html", finding_page="inspection", finding_title="抽检", finding_role="inspection",
        anchor_file="supplier.html", anchor_page="supplier", anchor_title="供方", anchor_role="supplier",
        lane_text="调整单", lane_file="adjustment.html", lane_page="adjustment", lane_title="调整", dest_text="调整页", dest_title="调整整理",
        leaf_text="库区一览", leaf_file="zones.html", leaf_node="extra_0",
        loop_file="settings.html", loop_node="settings", loop_link_text="偏好页",
        loop_steps=(
            "index.html: open_aid", "help.html: open_loop", "settings.html: open_loop",
            "help.html: open_loop", "settings.html: open_loop",
        ),
        extras=[
            {"file": "zones.html", "page": "zones", "text": "库区一览"},
            {"file": "batches.html", "page": "batches", "text": "批次一览"},
        ],
        cross_text="供方页",
    ),
    "buggy-studio": _cfg(
        list_pool="project", side_pool="asset", list_ids=["p1", "p2", "p3"], side_ids=["a1", "a2", "a3"],
        role_a="render_take", role_b="publish_note", assert_prefix="studio",
        primary_id="nav_projects", primary_text="项目", list_file="projects.html", list_page="projects", list_title="项目", list_role="project_hub",
        blank_id="nav_compare_blank", blank_text="对照页", blank_file="compare.html", blank_page="compare",
        entity_file="project.html", entity_page="project", entity_title="项目明细", entity_role="project",
        mid_text="场次", mid_file="scene.html", mid_page="scene", mid_title="场次", mid_role="scene",
        child_text="成片", child_file="render.html", child_page="render", child_title="成片", child_role="render_child",
        side_text="素材", side_file="assets.html", side_page="assets", side_title="素材", side_role="asset_hub",
        side_entity_file="asset.html", side_entity_page="asset", side_entity_title="素材明细", side_entity_role="asset",
        mid_b_text="版本", mid_b_file="versions.html", mid_b_page="versions", mid_b_title="版本", mid_b_role="versions",
        child_b_text="发布单", child_b_file="publish.html", child_b_page="publish", child_b_title="发布", child_b_role="publish_child",
        finding_text="批注页", finding_file="comments.html", finding_page="comments", finding_title="批注", finding_role="comments",
        anchor_file="review.html", anchor_page="review", anchor_title="审片", anchor_role="review",
        lane_text="渲染列", lane_file="renders.html", lane_page="renders", lane_title="渲染列", dest_text="渲染页", dest_title="渲染整理",
        leaf_text="手册页", leaf_file="handbook.html", leaf_node="handbook",
        loop_file="handbook.html", loop_node="handbook", loop_link_text="打开手册",
        loop_steps=(
            "index.html: open_aid", "help.html: open_loop", "handbook.html: nav_up_help",
            "help.html: open_loop", "handbook.html: nav_up_help",
        ),
        extras=[{"file": "scenes.html", "page": "scenes", "text": "场次一览"}],
        cross_text="审片页",
    ),
    "buggy-booking": _cfg(
        list_pool="venue", side_pool="room", list_ids=["v1", "v2", "v3"], side_ids=["r1", "r2", "r3"],
        role_a="guest_checkin", role_b="modification_slip", assert_prefix="booking",
        primary_id="nav_venues", primary_text="场馆", list_file="venues.html", list_page="venues", list_title="场馆", list_role="venue_hub",
        blank_id="nav_rollup", blank_text="汇总", blank_file="reports.html", blank_page="reports",
        entity_file="venue.html", entity_page="venue", entity_title="场馆明细", entity_role="venue",
        mid_text="房间", mid_file="room.html", mid_page="room", mid_title="房间", mid_role="room",
        child_text="客人单", child_file="guest.html", child_page="guest", child_title="客人", child_role="guest_child",
        side_text="日历", side_file="calendar.html", side_page="calendar", side_title="日历", side_role="calendar",
        side_entity_file="reservation.html", side_entity_page="reservation", side_entity_title="预订明细", side_entity_role="reservation",
        mid_b_text="改期", mid_b_file="modify.html", mid_b_page="modify", mid_b_title="改期", mid_b_role="modify",
        child_b_text="回执", child_b_file="confirmation.html", child_b_page="confirmation", child_b_title="回执", child_b_role="slip_child",
        finding_text="备注页", finding_file="notes.html", finding_page="notes", finding_title="备注", finding_role="notes",
        anchor_file="guests.html", anchor_page="guests", anchor_title="客人名册", anchor_role="guest_list",
        lane_text="取消单", lane_file="cancellation.html", lane_page="cancellation", lane_title="取消单", dest_text="取消页", dest_title="取消整理",
        leaf_text="房间一览", leaf_file="rooms.html", leaf_node="extra_0",
        loop_file="settings.html", loop_node="settings", loop_link_text="偏好页",
        loop_steps=(
            "index.html: open_aid", "help.html: open_loop", "settings.html: open_loop",
            "help.html: open_loop", "settings.html: open_loop",
        ),
        extras=[
            {"file": "rooms.html", "page": "rooms", "text": "房间一览"},
            {"file": "reservations.html", "page": "reservations", "text": "预订一览"},
        ],
        cross_text="名册页",
    ),
}


BUILDERS = {
    "buggy-campus": build_positive,
    "buggy-warehouse": build_positive,
    "buggy-studio": build_positive,
    "buggy-booking": build_positive,
    "buggy-catalog": build_catalog,
    "buggy-kiosk": build_kiosk,
}


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _write_json(path, obj):
    _write(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def generated_relpaths(app_name: str) -> list[str]:
    builder, _, _, _, _ = BUILDERS[app_name](app_name if app_name in POSITIVE_CFG else resolve_seed(app_name)[0])
    rels = [
        f"apps/{app_name}/server.py",
        f"apps/{app_name}/README.md",
        f"apps/{app_name}/spec.json",
        f"apps/{app_name}/topology.json",
        f"apps/{app_name}/mechanism-opportunities.json",
        f"apps/{app_name}/bugs.manifest.json",
        f"apps/{app_name}/generation.json",
        f"apps/{app_name}/static/app.js",
    ]
    for page in builder.files:
        rels.append(f"apps/{app_name}/static/{page}")
    return rels


def generate_app(app_name: str, *, root: str = ROOT) -> dict:
    seed, _hex = resolve_seed(app_name)
    if app_name in POSITIVE_CFG:
        builder, topology, model, bugs, spec = build_positive(app_name)
    elif app_name == "buggy-catalog":
        builder, topology, model, bugs, spec = build_catalog(seed)
    else:
        builder, topology, model, bugs, spec = build_kiosk(seed)
    dest = os.path.join(root, "apps", app_name)
    static = os.path.join(dest, "static")
    os.makedirs(static, exist_ok=True)
    fam = FAMILIES[app_name]
    brand = fam["brand_pool"][seed % len(fam["brand_pool"])]
    data_pages = {}
    for node in builder.nodes:
        data_pages[node["page"]] = node["data_page"]
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
    _write_json(os.path.join(dest, "spec.json"), {
        "app": app_name,
        "note": "Specification-driven semantic oracle. Uses ONLY page-presented values.",
        "assertions": spec,
    })
    _write_json(os.path.join(dest, "topology.json"), topology)
    from benchmark.fresh_composite_qualify import mechanism_from_qualification, qualify_topology
    row = qualify_topology(topology)
    _write_json(os.path.join(dest, "mechanism-opportunities.json"), mechanism_from_qualification(row))
    _write_json(os.path.join(dest, "generation.json"), {
        "round": "v0.3.20",
        "app": app_name,
        "seed": seed,
        "seed_hex": builder.seed_hex,
        "seed_rule": 'uint32(first 8 hex digits of SHA256("' + SEED_PREFIX + '" + app_name))',
        "topology_family": fam["family"],
        "expected_control_class": topology["expected_control_class"],
        "policy_blind": True,
        "generator": "benchmark/fresh_composite_generator.py",
    })
    _write(os.path.join(dest, "README.md"), (
        f"# {brand}\n\n"
        f"Preregistered v0.3.20 fresh target `{app_name}`.\n"
        f"Topology family: `{fam['family']}`.\n"
        f"Seed `{builder.seed_hex}` = {seed}.\n"
        f"Class: {fam['control_class']}.\n\n"
        "The bug manifest, topology, and mechanism opportunity file are judge-only and are not served.\n"
        "Static qualification is not empirical transfer.\n"
    ))
    return {
        "app": app_name,
        "seed": seed,
        "seed_hex": builder.seed_hex,
        "n_bugs": len(bugs),
        "qualified": row["qualified"],
        "summary": {
            "nested": row["nested_handoff_opportunity_count"],
            "finding": row["finding_return_entry_opportunity_count"],
            "horizon": row["horizon_only_return_entry_control_count"],
            "depth": row["max_nested_branch_depth"],
            "handoff_edges": row["handoff_edge_count"],
            "variant": row["state_variant_return_count"],
        },
        "files": generated_relpaths(app_name),
    }


def generate_all(*, root: str = ROOT) -> list:
    return [generate_app(name, root=root) for name in APP_NAMES]


def lf_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["write", "seeds"])
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args(argv)
    if args.cmd == "seeds":
        for name in APP_NAMES:
            seed, hex8 = resolve_seed(name)
            print(f"{name} {hex8} {seed}")
        return 0
    for rec in generate_all(root=args.root):
        print(
            f"wrote {rec['app']} seed={rec['seed_hex']} bugs={rec['n_bugs']} "
            f"qualified={rec['qualified']} {rec['summary']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
