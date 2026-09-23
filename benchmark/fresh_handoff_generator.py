"""Deterministic v0.3.15 target generator.

One graph per frozen app identity. Inputs are the app name, the frozen seed,
the frozen topology family, and the vocabulary tables. No exploration,
runner, analysis, or result imports.
"""
from __future__ import annotations

import argparse
import json
import os

from benchmark.fresh_handoff_js import HTML, JS, SERVER
from benchmark.fresh_handoff_vocab import FAMILIES, SEED_PREFIX, assign_names, contains_non_branch, resolve_seed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_NAMES = ("buggy-forum", "buggy-billing", "buggy-lab", "buggy-directory")
FAIL_PATH = "/api/export"


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


def _back(testid, text, href, dst):
    return _link(testid, text, href, dst, parent_return=True, returns_to=dst)


def _mutate(testid, text, patch, role, reveal="", follow=False):
    row = _button(
        testid, text, "mutate",
        patch=[{"key": key, "value": value} for key, value in patch],
        child_local=True, child_workflow_role=role,
    )
    if reveal:
        row["reveal"] = reveal
    if follow:
        row["follow_up"] = True
        row["reveal_after"] = reveal if False else row.get("reveal_after", "")
    return row


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

    def add(self, node_id, page, data_page, title, controls, *, expect_hub, hub_role,
            entity="", entity_source="", obs=None, blank=False):
        self.nodes.append({
            "id": node_id,
            "page": page,
            "data_page": data_page,
            "title": title,
            "expect_hub": expect_hub,
            "hub_role": hub_role,
            "entity": entity,
            "entity_source": entity_source,
            "obs": list(obs or []),
            "blank": blank,
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

    def _branch_count(self, controls, entity):
        count = 0
        first = ""
        for ctl in self._visible(controls, entity):
            if ctl["kind"] not in ("link", "button"):
                continue
            if contains_non_branch(ctl.get("text") or "", ctl.get("testid") or ""):
                continue
            count += 1
            if not first:
                first = ctl["testid"]
        return count, first

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
            count, first = self._branch_count(controls, node.get("entity") or "")
            hub = count >= 3
            if hub != node["expect_hub"]:
                raise RuntimeError(
                    f"{self.app} {node['id']} hub={hub} count={count} expected={node['expect_hub']} first={first}"
                )
            node["hub"] = hub
            node["first_branch_action"] = first
            topo_nodes.append({
                "id": node["id"],
                "page": node["page"],
                "hub": hub,
                "hub_role": node["hub_role"],
                "entity": node.get("entity") or "",
                "first_branch_action": first,
                "blank": node["blank"],
            })
            for ctl in controls:
                branch_like = (
                    ctl["kind"] in ("link", "button")
                    and not contains_non_branch(ctl.get("text") or "", ctl.get("testid") or "")
                    and not ctl.get("parent_return")
                )
                navigates = ctl["kind"] == "link" and bool(ctl.get("href")) and not ctl.get("parent_return")
                useful = navigates or ctl.get("child_local") or ctl.get("follow_up") or ctl.get("parent_return")
                if not useful:
                    continue
                dst = ctl.get("dst") or node["id"]
                if not navigates and not ctl.get("parent_return"):
                    dst = node["id"]
                topo_edges.append({
                    "id": f"{node['id']}:{ctl['testid']}",
                    "src": node["id"],
                    "dst": dst,
                    "action": ctl["testid"],
                    "branch_like": bool(branch_like and navigates) or bool(
                        branch_like and (ctl.get("child_local") or ctl.get("follow_up"))
                    ),
                    "navigates": bool(navigates),
                    "follow_up": bool(ctl.get("follow_up")),
                    "child_local": bool(ctl.get("child_local")),
                    "parent_return": bool(ctl.get("parent_return")),
                    "returns_to": ctl.get("returns_to") or "",
                    "alternate_child_completion": bool(ctl.get("alternate_child_completion")),
                    "family": ctl.get("family") or "",
                    "child_workflow_role": ctl.get("child_workflow_role") or "",
                })
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
            "note": "Judge/authoring topology. Not served. Exploration must not read this file.",
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


def _public_control(ctl):
    keep = (
        "kind", "testid", "text", "href", "effect", "message", "input", "obs_key",
        "patch", "reveal", "reveal_after", "when_entity", "when_no_entity",
    )
    return {key: ctl[key] for key in keep if key in ctl and ctl[key] not in ("", None, [])}


def _names(seed, pool, ids):
    mapping = assign_names(seed, pool, ids)
    return [{"id": item_id, "name": mapping[item_id]} for item_id in ids]


def _by_id(rows):
    return {row["id"]: row["name"] for row in rows}


def _search_and_help(home):
    home.extend([
        _link("nav_help", "帮助", "help.html", "help"),
        _input("search_box", "检索词"),
        _button(
            "btn_query_submit", "提交查询", "search",
            input="search_box", message="", obs_key="search_state",
        ),
    ])
    return home


def _tail_pages(builder, settings_back_href, settings_back_dst, settings_back_text):
    builder.add("compose", "compose.html", "compose", "撰写", [
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="compose", obs=["form_msg"])
    builder.add("settings", "settings.html", "settings", "偏好", [
        _button("btn_probe", "测试同步", "throw", message=builder.fam["sync_error"]),
        _button("btn_export", "导出", "post"),
        _back("nav_up_from_prefs", settings_back_text, settings_back_href, settings_back_dst),
    ], expect_hub=False, hub_role="settings")
    builder.add("search", "search.html", "search", "检索", [
        _back("nav_up_home_search", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="search")
    builder.add("help", "help.html", "help", "说明", [
        _link("open_handbook", "打开手册", "handbook.html", "handbook"),
    ], expect_hub=False, hub_role="help")
    builder.add("handbook", "handbook.html", "handbook", "手册", [
        _back("nav_up_help", "返回说明", "help.html", "help"),
    ], expect_hub=False, hub_role="handbook")


def _role(role, family):
    return {"child_workflow_role": role, "family": family}


def build_forum(seed: int):
    b = Builder("buggy-forum")
    zones = _names(seed, "zone", ["c1", "c2", "c3"])
    topics = _names(seed + 1, "topic", ["t1", "t2", "t3"])
    people = _names(seed + 2, "person", ["p1"])
    z, t = _by_id(zones), _by_id(topics)
    role, family = "moderation_resolution", "discussion_moderation"
    role2, family2 = "report_triage", "author_report"
    home = [
        _link("nav_zones", "分类", "categories.html", "categories"),
        _link("nav_threads", "讨论串", "threads.html", "threads"),
    ]
    _search_and_help(home)
    home[-1]["message"] = b.fam["search_error"]
    b.add("home", "index.html", "home", "首页", home, expect_hub=False, hub_role="entry",
          obs=["search_state"])
    b.add("categories", "categories.html", "categories", "分类", [
        _link("open_zone_c1", z["c1"], "category.html?id=c1", "category"),
        _link("open_zone_c2", z["c2"], "category.html?id=c2", "category"),
        _link("open_zone_c3", z["c3"], "category.html?id=c3", "category"),
        _link("nav_compose", "写讨论", "compose.html", "compose"),
        _link("nav_drafts", "草稿", "drafts.html", "drafts"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], expect_hub=True, hub_role="category_hub")
    b.add("category", "category.html", "category", "分区", [
        _link("open_topic_t1", t["t1"], "thread.html?id=t1", "thread_t1"),
        _link("open_topic_t2", t["t2"], "thread.html?id=t2", "thread_t2"),
        _link("open_topic_t3", t["t3"], "thread.html?id=t3", "thread_t3"),
        _button("btn_pin", "收藏", "dead"),
        _link("nav_prefs", "偏好", "settings.html", "settings"),
        _back("nav_up_zones", "返回分类", "categories.html", "categories"),
    ], expect_hub=True, hub_role="category", entity_source="zones", obs=[])
    b.add("threads", "threads.html", "threads", "讨论串", [
        _link("open_thread_t2", t["t2"], "thread.html?id=t2", "thread_t2"),
        _link("open_thread_t1", t["t1"], "thread.html?id=t1", "thread_t1"),
        _link("open_thread_t3", t["t3"], "thread.html?id=t3", "thread_t3"),
        _back("nav_up_home_threads", "返回首页", "index.html", "home"),
    ], expect_hub=True, hub_role="thread_hub")
    b.add("thread_t1", "thread.html", "thread", "讨论", [
        _link("open_triage", "处理队列", "moderation.html?id=t1", "moderation", **_role(role, family)),
        _link("open_response", "查看回复", "reply.html?id=r1", "reply"),
        _link("open_author", "查看作者", "profile.html?id=p1", "profile"),
        _link("nav_replies", "全部回复", "replies.html?id=t1", "replies"),
        _button("btn_cool", "下调热度", "mutate", patch=[{"key": "heat_remaining", "value": "6"}]),
        _button("btn_staff_note", "内部记录", "mutate", patch=[
            {"key": "note_kind", "value": "内部"},
            {"key": "note_visibility", "value": "公开"},
        ]),
        _back("nav_up_zone", "返回分区", "category.html?id=c1", "category"),
    ], expect_hub=True, hub_role="thread", entity="t1", entity_source="topics",
          obs=["heat_display", "heat_remaining", "note_kind", "note_visibility"])
    b.add("thread_t2", "thread.html", "thread", "讨论", [
        _link("open_author", "查看作者", "profile.html?id=p1", "profile", **_role(role2, family2)),
        _link("open_triage", "处理队列", "moderation.html?id=t2", "moderation"),
        _link("open_response", "查看回复", "reply.html?id=r2", "reply"),
        _back("nav_up_threads", "返回讨论串", "threads.html", "threads"),
    ], expect_hub=True, hub_role="thread", entity="t2", entity_source="topics")
    b.add("thread_t3", "thread.html", "thread", "讨论", [
        _link("open_response", "查看回复", "reply.html?id=r3", "reply"),
        _link("open_author", "查看作者", "profile.html?id=p1", "profile"),
        _link("nav_replies", "全部回复", "replies.html?id=t3", "replies"),
        _back("nav_up_threads_t3", "返回讨论串", "threads.html", "threads"),
    ], expect_hub=True, hub_role="thread", entity="t3", entity_source="topics")
    b.add("reply", "reply.html", "reply", "回复", [
        _link("open_author_reply", "查看作者", "profile.html?id=p1", "profile"),
        _link("open_topic_peer", t["t2"], "thread.html?id=t2", "thread_t2"),
        _link("open_triage_reply", "处理队列", "moderation.html?id=t1", "moderation"),
        _button("btn_close", "关闭", "mutate", patch=[{"key": "topic_status", "value": "已关闭"}]),
        _button("btn_reopen", "重新打开", "mutate", patch=[{"key": "reopened", "value": "是"}]),
        _back("nav_up_topic", "返回讨论", "thread.html?id=t1", "thread_t1"),
    ], expect_hub=True, hub_role="reply", obs=["topic_status", "reopened"])
    b.add("replies", "replies.html", "replies", "回复列表", [
        _link("open_response_r1", "首条", "reply.html?id=r1", "reply"),
        _link("open_response_r2", "下一条", "reply.html?id=r2", "reply"),
        _link("open_author_list", "查看作者", "profile.html?id=p1", "profile"),
        _back("nav_up_topic_list", "返回讨论", "thread.html?id=t1", "thread_t1"),
    ], expect_hub=True, hub_role="reply_hub", obs=["note_kind", "note_visibility"])
    b.add("profile", "profile.html", "profile", "作者", [
        _link("open_case", "受理举报", "report.html?id=p1", "report", **_role(role2, family2)),
        _link("open_author_topic", t["t2"], "thread.html?id=t2", "thread_t2"),
        _link("open_author_replies", "作者回复", "replies.html?id=p1", "replies"),
        _back("nav_up_threads_author", "返回讨论串", "threads.html", "threads"),
    ], expect_hub=True, hub_role="profile", entity_source="people")
    b.add("moderation", "moderation.html", "moderation", "处理", [
        _mutate("btn_mark", "登记处理", [("handled", "是")], role, reveal="btn_follow"),
        _button(
            "btn_follow", "补充说明", "mutate",
            patch=[{"key": "handled_note", "value": "已补充"}],
            reveal_after="btn_mark", follow_up=True, child_local=True, child_workflow_role=role,
        ),
        _back("nav_up_topic_mod", "返回讨论", "thread.html?id=t1", "thread_t1"),
    ], expect_hub=False, hub_role="moderation_child")
    b.add("report", "report.html", "report", "举报", [
        _mutate("btn_accept", "受理登记", [("accepted", "是")], role2, reveal="btn_reason"),
        _button(
            "btn_reason", "填写理由", "mutate",
            patch=[{"key": "reason_note", "value": "已填写"}],
            reveal_after="btn_accept", follow_up=True, child_local=True, child_workflow_role=role2,
        ),
        _back("nav_up_author", "返回作者", "profile.html?id=p1", "profile"),
    ], expect_hub=False, hub_role="report_child")
    b.add("drafts", "drafts.html", "drafts", "草稿", [], expect_hub=False, hub_role="drafts", blank=True)
    _tail_pages(b, "category.html?id=c1", "category", "返回分区")
    entities = {"zones": zones, "topics": topics, "people": people}
    initial = {
        "heat_display": "8", "heat_remaining": "8", "topic_status": "跟进中", "reopened": "否",
        "note_kind": "", "note_visibility": "", "form_msg": "", "search_state": "",
        "handled": "", "handled_note": "", "accepted": "", "reason_note": "",
    }
    topology, model = b.materialize(entities, initial)
    bugs = _forum_bugs()
    spec = _semantic_spec("buggy-forum", "forum", "/thread.html", "/reply.html", "/replies.html")
    return b, topology, model, bugs, spec


def build_billing(seed: int):
    b = Builder("buggy-billing")
    accounts = _names(seed, "account", ["a1", "a2", "a3"])
    invoices = _names(seed + 1, "invoice", ["i1", "i2", "i3"])
    a, inv = _by_id(accounts), _by_id(invoices)
    role, family = "payment_capture", "invoice_payment"
    role2, family2 = "refund_escape", "dispute_refund"
    home = [
        _link("nav_accounts", "账户", "accounts.html", "accounts"),
        _link("nav_invoices", "发票", "invoices.html", "invoices"),
    ]
    _search_and_help(home)
    home[-1]["message"] = b.fam["search_error"]
    b.add("home", "index.html", "home", "首页", home, expect_hub=False, hub_role="entry", obs=["search_state"])
    b.add("accounts", "accounts.html", "accounts", "账户", [
        _link("open_acct_a1", a["a1"], "account.html?id=a1", "account"),
        _link("open_acct_a2", a["a2"], "account.html?id=a2", "account"),
        _link("open_acct_a3", a["a3"], "account.html?id=a3", "account"),
        _link("nav_compose", "写单据", "compose.html", "compose"),
        _link("nav_payments", "收款列表", "payments.html", "payments"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], expect_hub=True, hub_role="account_hub")
    b.add("account", "account.html", "account", "账户明细", [
        _link("open_bill_i1", inv["i1"], "invoice.html?id=i1", "invoice_i1"),
        _link("open_bill_i2", inv["i2"], "invoice.html?id=i2", "invoice_i2"),
        _link("nav_credits", "抵扣", "credits.html", "credits"),
        _link("nav_prefs", "偏好", "settings.html", "settings"),
        _button("btn_pin", "收藏", "dead"),
        _back("nav_up_accounts", "返回账户", "accounts.html", "accounts"),
    ], expect_hub=True, hub_role="account", entity_source="accounts")
    b.add("invoices", "invoices.html", "invoices", "发票", [
        _link("open_inv_i2", inv["i2"], "invoice.html?id=i2", "invoice_i2"),
        _link("open_inv_i1", inv["i1"], "invoice.html?id=i1", "invoice_i1"),
        _link("open_inv_i3", "另一张发票", "invoice.html?id=i1", "invoice_i1"),
        _back("nav_up_home_inv", "返回首页", "index.html", "home"),
    ], expect_hub=True, hub_role="invoice_hub")
    b.add("invoice_i1", "invoice.html", "invoice", "发票明细", [
        _link("open_receipt", "收款单", "payment.html?id=i1", "payment", **_role(role, family)),
        _link("open_refund", "退回单", "refund.html?id=i1", "refund"),
        _link("open_dispute", "争议单", "disputes.html?id=i1", "dispute"),
        _link("open_credit", "抵扣单", "credits.html?id=i1", "credits"),
        _button("btn_adjust", "下调费用", "mutate", patch=[{"key": "fee_remaining", "value": "6"}]),
        _button("btn_staff_note", "内部记录", "mutate", patch=[
            {"key": "note_kind", "value": "内部"},
            {"key": "note_visibility", "value": "公开"},
        ]),
        _back("nav_up_acct", "返回账户", "account.html?id=a1", "account"),
    ], expect_hub=True, hub_role="invoice", entity="i1", entity_source="invoices",
          obs=["fee_display", "fee_remaining", "invoice_book", "note_kind", "note_visibility"])
    b.add("invoice_i2", "invoice.html", "invoice", "发票明细", [
        _link("open_dispute", "争议单", "disputes.html?id=i2", "dispute", **_role(role2, family2)),
        _link("open_receipt", "收款单", "payment.html?id=i2", "payment"),
        _link("open_refund", "退回单", "refund.html?id=i2", "refund"),
        _link("open_credit", "抵扣单", "credits.html?id=i2", "credits"),
        _back("nav_up_invoices", "返回发票", "invoices.html", "invoices"),
    ], expect_hub=True, hub_role="invoice", entity="i2", entity_source="invoices",
          obs=["invoice_book"])
    b.add("payment", "payment.html", "payment", "收款", [
        _mutate("btn_post", "登记到账", [("invoice_book", "80")], role, reveal="btn_slip"),
        _button(
            "btn_slip", "追加回单", "mutate",
            patch=[{"key": "slip_note", "value": "已追加"}],
            reveal_after="btn_post", follow_up=True, child_local=True, child_workflow_role=role,
        ),
        _back("nav_up_bill", "返回发票", "invoice.html?id=i1", "invoice_i1"),
    ], expect_hub=False, hub_role="payment_child")
    b.add("dispute", "disputes.html", "dispute", "争议", [
        _link("open_refund_case", "退回单", "refund.html?id=i2", "refund", **_role(role2, family2)),
        _link("open_inv_case", inv["i2"], "invoice.html?id=i2", "invoice_i2"),
        _link("open_credit_case", "抵扣单", "credits.html?id=i2", "credits"),
        _back("nav_up_bill_dispute", "返回发票", "invoice.html?id=i2", "invoice_i2"),
    ], expect_hub=True, hub_role="dispute")
    b.add("refund", "refund.html", "refund", "退回", [
        _mutate("btn_mark", "登记退回", [("refund_mark", "是")], role2, reveal="btn_note"),
        _button(
            "btn_note", "补充说明", "mutate",
            patch=[{"key": "refund_note", "value": "已补充"}],
            reveal_after="btn_mark", follow_up=True, child_local=True, child_workflow_role=role2,
        ),
        _back("nav_up_credit", "返回抵扣", "credits.html?id=i2", "credits"),
        _back("nav_up_dispute", "返回争议", "disputes.html?id=i2", "dispute"),
    ], expect_hub=False, hub_role="refund_child")
    b.add("credits", "credits.html", "credits", "抵扣", [
        _button("btn_close", "关闭", "mutate", patch=[{"key": "topic_status", "value": "已关闭"}]),
        _button("btn_reopen", "重新打开", "mutate", patch=[{"key": "reopened", "value": "是"}]),
        _back("nav_up_refund", "返回退款", "refund.html?id=i2", "refund"),
    ], expect_hub=False, hub_role="credits", obs=["topic_status", "reopened", "note_kind", "note_visibility"])
    b.add("payments", "payments.html", "payments", "收款列表", [], expect_hub=False,
          hub_role="payments", blank=True)
    b.add("refunds", "refunds.html", "refunds", "退回列表", [
        _link("open_refund_a", "一笔退回", "refund.html?id=i1", "refund"),
        _link("open_refund_b", "另一笔退回", "refund.html?id=i2", "refund"),
        _back("nav_up_home_refunds", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="refund_list")
    b.add("reports", "reports.html", "reports", "账期汇总", [
        _back("nav_up_home_period", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="period")
    _tail_pages(b, "account.html?id=a1", "account", "返回账户")
    entities = {"accounts": accounts, "invoices": invoices}
    initial = {
        "fee_display": "8", "fee_remaining": "8", "invoice_book": "120",
        "topic_status": "跟进中", "reopened": "否", "note_kind": "", "note_visibility": "",
        "form_msg": "", "search_state": "", "slip_note": "", "refund_mark": "", "refund_note": "",
    }
    topology, model = b.materialize(entities, initial)
    return b, topology, model, _billing_bugs(), _semantic_spec(
        "buggy-billing", "billing", "/invoice.html", "/credits.html", "/credits.html")


def build_lab(seed: int):
    b = Builder("buggy-lab")
    projects = _names(seed, "project", ["p1", "p2"])
    experiments = _names(seed + 1, "experiment", ["e1", "e2", "e3"])
    runs = _names(seed + 2, "run", ["u1"])
    samples = _names(seed + 3, "sample", ["s1", "s2"])
    results = _names(seed + 4, "result", ["q1"])
    p, e, u = _by_id(projects), _by_id(experiments), _by_id(runs)
    s, q = _by_id(samples), _by_id(results)
    role, family = "sample_observation", "run_sample"
    role2, family2 = "comparison_notebook", "result_compare"
    home = [
        _link("nav_projects", "项目", "projects.html", "projects"),
        _link("nav_experiments", "实验", "experiments.html", "experiments"),
    ]
    _search_and_help(home)
    home[-1]["message"] = b.fam["search_error"]
    b.add("home", "index.html", "home", "首页", home, expect_hub=False, hub_role="entry", obs=["search_state"])
    b.add("projects", "projects.html", "projects", "项目", [
        _link("open_proj_p1", p["p1"], "project.html?id=p1", "project"),
        _link("open_proj_p2", p["p2"], "project.html?id=p2", "project"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="project_list")
    b.add("project", "project.html", "project", "项目明细", [
        _link("open_exp_e1", e["e1"], "experiment.html?id=e1", "experiment_e1"),
        _link("open_exp_e3", e["e3"], "experiment.html?id=e3", "experiment_e1"),
        _link("nav_runs", "批次列表", "runs.html", "runs"),
        _link("nav_prefs", "偏好", "settings.html", "settings"),
        _link("nav_compose", "写记录", "compose.html", "compose"),
        _button("btn_pin", "收藏", "dead"),
        _back("nav_up_projects", "返回项目", "projects.html", "projects"),
    ], expect_hub=True, hub_role="project", entity_source="projects")
    b.add("experiments", "experiments.html", "experiments", "实验", [
        _link("open_exp_e2", e["e2"], "experiment.html?id=e2", "experiment_e2"),
        _link("open_exp_e1b", e["e1"], "experiment.html?id=e1", "experiment_e1"),
        _link("open_exp_e3b", e["e3"], "experiment.html?id=e3", "experiment_e1"),
        _link("nav_samples", "样品架", "samples.html", "samples"),
        _back("nav_up_home_exp", "返回首页", "index.html", "home"),
    ], expect_hub=True, hub_role="experiment_hub")
    b.add("experiment_e1", "experiment.html", "experiment", "实验明细", [
        _link("open_run_u1", u["u1"], "run.html?id=u1", "run"),
        _link("open_result_side", q["q1"], "result.html?id=q1", "result"),
        _link("nav_results", "结果列表", "results.html", "results"),
        _back("nav_up_project", "返回项目", "project.html?id=p1", "project"),
    ], expect_hub=True, hub_role="experiment", entity="e1", entity_source="experiments")
    b.add("experiment_e2", "experiment.html", "experiment", "实验明细", [
        _link("open_result_q1", q["q1"], "result.html?id=q1", "result", **_role(role2, family2)),
        _link("open_run_side", u["u1"], "run.html?id=u1", "run"),
        _link("nav_notebook_side", "记录本", "notebook.html?id=q1", "notebook"),
        _back("nav_up_experiments", "返回实验", "experiments.html", "experiments"),
    ], expect_hub=True, hub_role="experiment", entity="e2", entity_source="experiments")
    b.add("run", "run.html", "run", "批次", [
        _link("open_sample_s1", s["s1"], "sample.html?id=s1", "sample", **_role(role, family)),
        _link("open_result_from_run", q["q1"], "result.html?id=q1", "result"),
        _link("open_sample_s2", s["s2"], "sample.html?id=s2", "sample"),
        _button("btn_staff_note", "内部记录", "mutate", patch=[
            {"key": "note_kind", "value": "内部"},
            {"key": "note_visibility", "value": "公开"},
        ]),
        _back("nav_up_exp", "返回实验", "experiment.html?id=e1", "experiment_e1"),
    ], expect_hub=True, hub_role="run", entity_source="runs",
          obs=["run_note", "heat_display", "heat_remaining"])
    b.add("sample", "sample.html", "sample", "样品", [
        _mutate("btn_obs", "记录观测", [("run_note", "已观测")], role, reveal="btn_batch"),
        _button(
            "btn_batch", "补充批次", "mutate",
            patch=[{"key": "batch_note", "value": "已补充"}],
            reveal_after="btn_obs", follow_up=True, child_local=True, child_workflow_role=role,
        ),
        _back("nav_up_run", "返回批次", "run.html?id=u1", "run"),
    ], expect_hub=False, hub_role="sample_child", entity_source="samples")
    b.add("result", "result.html", "result", "结果", [
        _link("open_compare", "对照", "compare.html?id=q1", "compare", **_role(role2, family2)),
        _link("open_notebook", "记录本", "notebook.html?id=q1", "notebook"),
        _link("open_run_again", u["u1"], "run.html?id=u1", "run"),
        _button("btn_close", "关闭", "mutate", patch=[{"key": "topic_status", "value": "已关闭"}]),
        _button("btn_reopen", "重新打开", "mutate", patch=[{"key": "reopened", "value": "是"}]),
        _back("nav_up_exp_result", "返回实验", "experiment.html?id=e2", "experiment_e2"),
    ], expect_hub=True, hub_role="result", entity_source="results",
          obs=["topic_status", "reopened", "note_kind", "note_visibility"])
    b.add("compare", "compare.html", "compare", "对照", [
        _mutate("btn_pin_base", "固定基线", [("baseline", "是")], role2, reveal="btn_compare_note"),
        _button(
            "btn_compare_note", "补充对照", "mutate",
            patch=[{"key": "compare_note", "value": "已补充"}],
            reveal_after="btn_pin_base", follow_up=True, child_local=True, child_workflow_role=role2,
        ),
        _back("nav_up_result", "返回结果", "result.html?id=q1", "result"),
    ], expect_hub=False, hub_role="compare_child")
    b.add("notebook", "notebook.html", "notebook", "记录本", [
        _link("open_compare_from_note", "查看对照", "compare.html?id=q1", "compare"),
        _back("nav_up_result_note", "返回结果", "result.html?id=q1", "result"),
    ], expect_hub=False, hub_role="notebook")
    b.add("runs", "runs.html", "runs", "批次列表", [
        _link("open_run_list", u["u1"], "run.html?id=u1", "run"),
        _back("nav_up_project_runs", "返回项目", "project.html?id=p1", "project"),
    ], expect_hub=False, hub_role="run_list")
    b.add("samples", "samples.html", "samples", "样品架", [], expect_hub=False, hub_role="samples", blank=True)
    b.add("results", "results.html", "results", "结果列表", [
        _link("open_result_list", q["q1"], "result.html?id=q1", "result"),
        _back("nav_up_home_results", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="result_list")
    # State bug lives on the run page; the run node already has heat obs.
    b.control_map["run"].insert(4, _button(
        "btn_cool", "下调读数", "mutate", patch=[{"key": "heat_remaining", "value": "6"}]))
    _tail_pages(b, "project.html?id=p1", "project", "返回项目")
    entities = {
        "projects": projects, "experiments": experiments, "runs": runs,
        "samples": samples, "results": results,
    }
    initial = {
        "heat_display": "8", "heat_remaining": "8", "run_note": "待观测",
        "topic_status": "跟进中", "reopened": "否", "note_kind": "", "note_visibility": "",
        "form_msg": "", "search_state": "", "batch_note": "", "baseline": "", "compare_note": "",
    }
    topology, model = b.materialize(entities, initial)
    return b, topology, model, _lab_bugs(), _semantic_spec(
        "buggy-lab", "lab", "/run.html", "/result.html", "/result.html")


def build_directory(seed: int):
    b = Builder("buggy-directory")
    people = _names(seed, "person", ["h1", "h2"])
    teams = _names(seed + 1, "team", ["m1"])
    offices = _names(seed + 2, "office", ["o1"])
    roles = _names(seed + 3, "role", ["r1"])
    person, team = _by_id(people), _by_id(teams)
    home = [
        _link("nav_people", "人员", "people.html", "people"),
        _link("nav_teams", "班组", "teams.html", "teams"),
        _link("nav_offices", "办公点", "offices.html", "offices"),
        _link("nav_roles", "职责", "roles.html", "roles"),
        _link("nav_lookup", "检索", "search.html", "search"),
        _link("nav_help", "帮助", "help.html", "help"),
        _link("nav_prefs_word", "设置", "settings.html", "settings"),
        _input("search_box", "检索词"),
        _button("btn_query_submit", "提交查询", "search", input="search_box",
                message=b.fam["search_error"], obs_key="search_state"),
    ]
    b.add("home", "index.html", "home", "首页", home, expect_hub=True, hub_role="entry", obs=["search_state"])
    b.add("people", "people.html", "people", "人员", [
        _link("open_highlight", person["h1"], "people.html?id=h1", "person_detail"),
        _button("btn_pin", "收藏", "dead"),
        _back("nav_up_home", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="people")
    b.add("person_detail", "people.html", "people", "人员", [
        _button("btn_adjust", "下调班次", "mutate", patch=[{"key": "heat_remaining", "value": "6"}]),
        _back("nav_up_people", "返回人员", "people.html", "people"),
    ], expect_hub=False, hub_role="person_detail", entity="h1", entity_source="people",
          obs=["heat_display", "heat_remaining"])
    b.add("teams", "teams.html", "teams", "班组", [
        _link("open_team", team["m1"], "teams.html?id=m1", "team_detail"),
        _back("nav_up_home_teams", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="teams")
    b.add("team_detail", "teams.html", "teams", "班组", [
        _back("nav_up_teams", "返回班组", "teams.html", "teams"),
    ], expect_hub=False, hub_role="team_detail", entity="m1", entity_source="teams")
    b.add("offices", "offices.html", "offices", "办公点", [], expect_hub=False, hub_role="offices", blank=True)
    b.add("roles", "roles.html", "roles", "职责", [
        _back("nav_up_home_roles", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="roles", entity_source="roles")
    b.add("search", "search.html", "search", "检索", [
        _back("nav_up_home_search", "返回首页", "index.html", "home"),
    ], expect_hub=False, hub_role="search")
    b.add("settings", "settings.html", "settings", "偏好", [
        _button("btn_probe", "测试同步", "throw", message=b.fam["sync_error"]),
        _button("btn_export", "导出", "post"),
        _input("topic_title", "标题"),
        _button("btn_submit", "提交", "form"),
        _back("nav_up_help", "返回说明", "help.html", "help"),
    ], expect_hub=False, hub_role="settings", obs=["form_msg"])
    b.add("help", "help.html", "help", "说明", [
        _link("open_handbook", "查阅规程", "settings.html", "settings"),
    ], expect_hub=False, hub_role="help")
    entities = {"people": people, "teams": teams, "offices": offices, "roles": roles}
    initial = {
        "heat_display": "8", "heat_remaining": "8", "form_msg": "", "search_state": "",
    }
    topology, model = b.materialize(entities, initial)
    return b, topology, model, _directory_bugs(), _directory_spec()


def _implies(cond_obs, cond_val, then_op, then_obs, then_val):
    return {
        "op": "implies",
        "cond": {"op": "eq", "left": {"obs": cond_obs}, "right": {"const": cond_val}},
        "then": {"op": then_op, "left": {"obs": then_obs}, "right": {"const": then_val}},
    }


def _semantic_spec(app, prefix, state_url, seq_url, cross_url):
    return [
        {
            "id": f"{prefix}_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": "/compose.html"},
            "assert": _implies("input_topic_title", "", "not_contains", "form_msg", "已创建"),
        },
        {
            "id": f"{prefix}_heat_matches",
            "severity": "medium",
            "desc": "展示读数应与剩余读数一致",
            "when": {"url_contains": state_url},
            "assert": {
                "op": "eq",
                "left": {"obs": "heat_display"},
                "right": {"obs": "heat_remaining"},
            },
        },
        {
            "id": f"{prefix}_reopen_clears",
            "severity": "high",
            "desc": "重新打开后不应仍显示已关闭",
            "when": {"url_contains": seq_url},
            "assert": _implies("reopened", "是", "ne", "topic_status", "已关闭"),
        },
        {
            "id": f"{prefix}_note_visibility",
            "severity": "high",
            "desc": "内部记录不应显示为公开",
            "when": {"url_contains": cross_url},
            "assert": _implies("note_kind", "内部", "eq", "note_visibility", "内部"),
        },
    ] if prefix != "billing" else [
        {
            "id": "billing_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": "/compose.html"},
            "assert": _implies("input_topic_title", "", "not_contains", "form_msg", "已创建"),
        },
        {
            "id": "billing_fee_matches",
            "severity": "medium",
            "desc": "展示费用应与剩余费用一致",
            "when": {"url_contains": "/invoice.html"},
            "assert": {"op": "eq", "left": {"obs": "fee_display"}, "right": {"obs": "fee_remaining"}},
        },
        {
            "id": "billing_reopen_clears",
            "severity": "high",
            "desc": "重新打开后不应仍显示已关闭",
            "when": {"url_contains": "/credits.html"},
            "assert": _implies("reopened", "是", "ne", "topic_status", "已关闭"),
        },
        {
            "id": "billing_note_visibility",
            "severity": "high",
            "desc": "内部记录不应显示为公开",
            "when": {"url_contains": "/credits.html"},
            "assert": _implies("note_kind", "内部", "eq", "note_visibility", "内部"),
        },
    ]


def _directory_spec():
    return [
        {
            "id": "directory_title_required",
            "severity": "high",
            "desc": "标题为空时不应提示已创建",
            "when": {"url_contains": "/settings.html"},
            "assert": _implies("input_topic_title", "", "not_contains", "form_msg", "已创建"),
        },
        {
            "id": "directory_shift_matches",
            "severity": "medium",
            "desc": "展示班次应与剩余班次一致",
            "when": {"url_contains": "/people.html"},
            "assert": {"op": "eq", "left": {"obs": "heat_display"}, "right": {"obs": "heat_remaining"}},
        },
    ]


def _bug(bid, category, kind, depth, desc, match, steps, severity="medium"):
    return {
        "id": bid, "category": category, "severity": severity, "desc": desc,
        "kind": kind, "trigger_depth": depth, "prerequisites": [],
        "match": match, "min_reproduction": steps,
    }


def _forum_bugs():
    return [
        _bug("BUG-F1", "blank page", "blank", 2, "草稿页渲染后完全空白",
             {"url_contains": "/drafts.html"}, ["index.html: nav_zones", "categories.html: nav_drafts"], "high"),
        _bug("BUG-F2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": "forum search query too long"},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-F3", "navigation loop", "nav_loop", 2, "说明与手册互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: nav_help", "help.html: open_handbook", "handbook.html: nav_up_help",
              "help.html: open_handbook", "handbook.html: nav_up_help"]),
        _bug("BUG-F4", "form validation", "semantic", 3, "标题为空时仍提示已创建",
             {"assert_id": "forum_title_required"},
             ["index.html: nav_zones", "categories.html: nav_compose", "compose.html: btn_submit"], "high"),
        _bug("BUG-F5", "dead action", "dead_action", 3, "分区收藏点击无效果",
             {"eid": "btn_pin"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: btn_pin"]),
        _bug("BUG-F6", "js error", "js_error", 4, "偏好页测试同步抛出未捕获异常",
             {"error_contains": "forum sync handshake failed"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: nav_prefs",
              "settings.html: btn_probe"]),
        _bug("BUG-F7", "http 5xx", "http_error", 4, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: nav_prefs",
              "settings.html: btn_export"], "high"),
        _bug("BUG-F8", "state inconsistency", "semantic", 4, "下调热度后展示值未更新",
             {"assert_id": "forum_heat_matches"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: open_topic_t1",
              "thread.html: btn_cool"]),
        _bug("BUG-F9", "sequence-dependent", "semantic", 6, "关闭后再打开仍显示已关闭",
             {"assert_id": "forum_reopen_clears"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: open_topic_t1",
              "thread.html: open_response", "reply.html: btn_close", "reply.html: btn_reopen"], "high"),
        _bug("BUG-F10", "cross-page consistency", "semantic", 5, "内部记录在回复列表显示为公开",
             {"assert_id": "forum_note_visibility"},
             ["index.html: nav_zones", "categories.html: open_zone_c1", "category.html: open_topic_t1",
              "thread.html: btn_staff_note", "thread.html: nav_replies"], "high"),
    ]


def _billing_bugs():
    return [
        _bug("BUG-B1", "blank page", "blank", 2, "收款列表渲染后完全空白",
             {"url_contains": "/payments.html"},
             ["index.html: nav_accounts", "accounts.html: nav_payments"], "high"),
        _bug("BUG-B2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": "billing search query too long"},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-B3", "navigation loop", "nav_loop", 2, "说明与手册互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: nav_help", "help.html: open_handbook", "handbook.html: nav_up_help",
              "help.html: open_handbook", "handbook.html: nav_up_help"]),
        _bug("BUG-B4", "form validation", "semantic", 3, "标题为空时仍提示已创建",
             {"assert_id": "billing_title_required"},
             ["index.html: nav_accounts", "accounts.html: nav_compose", "compose.html: btn_submit"], "high"),
        _bug("BUG-B5", "dead action", "dead_action", 3, "账户收藏点击无效果",
             {"eid": "btn_pin"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: btn_pin"]),
        _bug("BUG-B6", "js error", "js_error", 4, "偏好页测试同步抛出未捕获异常",
             {"error_contains": "billing sync handshake failed"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: nav_prefs",
              "settings.html: btn_probe"]),
        _bug("BUG-B7", "http 5xx", "http_error", 4, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: nav_prefs",
              "settings.html: btn_export"], "high"),
        _bug("BUG-B8", "state inconsistency", "semantic", 4, "下调费用后展示值未更新",
             {"assert_id": "billing_fee_matches"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: open_bill_i1",
              "invoice.html: btn_adjust"]),
        _bug("BUG-B9", "sequence-dependent", "semantic", 6, "关闭后再打开仍显示已关闭",
             {"assert_id": "billing_reopen_clears"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: open_bill_i1",
              "invoice.html: open_credit", "credits.html: btn_close", "credits.html: btn_reopen"], "high"),
        _bug("BUG-B10", "cross-page consistency", "semantic", 5, "内部记录在抵扣页显示为公开",
             {"assert_id": "billing_note_visibility"},
             ["index.html: nav_accounts", "accounts.html: open_acct_a1", "account.html: open_bill_i1",
              "invoice.html: btn_staff_note", "invoice.html: open_credit"], "high"),
    ]


def _lab_bugs():
    return [
        _bug("BUG-L1", "blank page", "blank", 2, "样品架渲染后完全空白",
             {"url_contains": "/samples.html"},
             ["index.html: nav_experiments", "experiments.html: nav_samples"], "high"),
        _bug("BUG-L2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": "lab search query too long"},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-L3", "navigation loop", "nav_loop", 2, "说明与手册互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: nav_help", "help.html: open_handbook", "handbook.html: nav_up_help",
              "help.html: open_handbook", "handbook.html: nav_up_help"]),
        _bug("BUG-L4", "form validation", "semantic", 4, "标题为空时仍提示已创建",
             {"assert_id": "lab_title_required"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: nav_compose",
              "compose.html: btn_submit"],
             "high"),
        _bug("BUG-L5", "dead action", "dead_action", 3, "项目页收藏点击无效果",
             {"eid": "btn_pin"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: btn_pin"]),
        _bug("BUG-L6", "js error", "js_error", 4, "偏好页测试同步抛出未捕获异常",
             {"error_contains": "lab sync handshake failed"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: nav_prefs",
              "settings.html: btn_probe"]),
        _bug("BUG-L7", "http 5xx", "http_error", 4, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: nav_prefs",
              "settings.html: btn_export"], "high"),
        _bug("BUG-L8", "state inconsistency", "semantic", 5, "下调读数后展示值未更新",
             {"assert_id": "lab_heat_matches"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: open_exp_e1",
              "experiment.html: open_run_u1", "run.html: btn_cool"]),
        _bug("BUG-L9", "sequence-dependent", "semantic", 5, "关闭后再打开仍显示已关闭",
             {"assert_id": "lab_reopen_clears"},
             ["index.html: nav_experiments", "experiments.html: open_exp_e2", "experiment.html: open_result_q1",
              "result.html: btn_close", "result.html: btn_reopen"], "high"),
        _bug("BUG-L10", "cross-page consistency", "semantic", 6, "内部记录在结果页显示为公开",
             {"assert_id": "lab_note_visibility"},
             ["index.html: nav_projects", "projects.html: open_proj_p1", "project.html: open_exp_e1",
              "experiment.html: open_run_u1", "run.html: btn_staff_note", "run.html: open_result_from_run"],
             "high"),
    ]


def _directory_bugs():
    return [
        _bug("BUG-DIR1", "blank page", "blank", 1, "办公点页渲染后完全空白",
             {"url_contains": "/offices.html"}, ["index.html: nav_offices"], "high"),
        _bug("BUG-DIR2", "boundary js error", "js_error", 1, "首页检索词超过 24 字抛出未捕获异常",
             {"error_contains": "directory search query too long"},
             ["index.html: search_box=25 chars", "index.html: btn_query_submit"]),
        _bug("BUG-DIR3", "navigation loop", "nav_loop", 2, "说明与偏好互相链接",
             {"cycle_urls_contains": "help.html"},
             ["index.html: nav_help", "help.html: open_handbook", "settings.html: nav_up_help",
              "help.html: open_handbook", "settings.html: nav_up_help"]),
        _bug("BUG-DIR4", "form validation", "semantic", 2, "标题为空时仍提示已创建",
             {"assert_id": "directory_title_required"},
             ["index.html: nav_prefs_word", "settings.html: btn_submit"], "high"),
        _bug("BUG-DIR5", "dead action", "dead_action", 2, "人员收藏点击无效果",
             {"eid": "btn_pin"}, ["index.html: nav_people", "people.html: btn_pin"]),
        _bug("BUG-DIR6", "js error", "js_error", 2, "偏好页测试同步抛出未捕获异常",
             {"error_contains": "directory sync handshake failed"},
             ["index.html: nav_prefs_word", "settings.html: btn_probe"]),
        _bug("BUG-DIR7", "http 5xx", "http_error", 2, "导出请求返回 500",
             {"error_contains": "/api/export"},
             ["index.html: nav_prefs_word", "settings.html: btn_export"], "high"),
        _bug("BUG-DIR8", "state inconsistency", "semantic", 3, "下调班次后展示值未更新",
             {"assert_id": "directory_shift_matches"},
             ["index.html: nav_people", "people.html: open_highlight", "people.html: btn_adjust"]),
    ]


BUILDERS = {
    "buggy-forum": build_forum,
    "buggy-billing": build_billing,
    "buggy-lab": build_lab,
    "buggy-directory": build_directory,
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
    builder, _, _, _, _ = BUILDERS[app_name](resolve_seed(app_name)[0])
    rels = [
        f"apps/{app_name}/server.py",
        f"apps/{app_name}/README.md",
        f"apps/{app_name}/spec.json",
        f"apps/{app_name}/topology.json",
        f"apps/{app_name}/bugs.manifest.json",
        f"apps/{app_name}/generation.json",
        f"apps/{app_name}/static/app.js",
    ]
    for page in builder.files:
        rels.append(f"apps/{app_name}/static/{page}")
    return rels


def generate_app(app_name: str, *, root: str = ROOT) -> dict:
    seed, _hex = resolve_seed(app_name)
    builder, topology, model, bugs, spec = BUILDERS[app_name](seed)
    dest = os.path.join(root, "apps", app_name)
    static = os.path.join(dest, "static")
    os.makedirs(static, exist_ok=True)
    fam = FAMILIES[app_name]
    brand = fam["brand_pool"][seed % len(fam["brand_pool"])]
    data_pages = {node["page"]: node["data_page"] for node in builder.nodes}
    for page in builder.files:
        _write(os.path.join(static, page), HTML.format(
            title=f"{brand}·{page}", page=data_pages[page]))
    payload = json.dumps(model, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    _write(os.path.join(static, "app.js"), JS.replace("__MODEL__", payload))
    _write(os.path.join(dest, "server.py"), SERVER.format(
        title=brand, default_port=fam["port"], fail_path=FAIL_PATH, fail_error=fam["fail_error"]))
    _write_json(os.path.join(dest, "bugs.manifest.json"), {
        "app": app_name,
        "note": "BENCHMARK JUDGE ONLY. GhostQA exploration/oracle must never read this file.",
        "bugs": bugs,
    })
    _write_json(os.path.join(dest, "spec.json"), {
        "app": app_name,
        "note": "Specification-driven semantic oracle. Uses ONLY page-presented values.",
        "assertions": spec,
    })
    _write_json(os.path.join(dest, "topology.json"), topology)
    _write_json(os.path.join(dest, "generation.json"), {
        "round": "v0.3.15",
        "app": app_name,
        "seed": seed,
        "seed_hex": builder.seed_hex,
        "seed_rule": 'uint32(first 8 hex digits of SHA256("' + SEED_PREFIX + '" + app_name))',
        "topology_family": fam["family"],
        "expected_control_class": fam["control_class"],
        "policy_blind": True,
        "generator": "benchmark/fresh_handoff_generator.py",
    })
    _write(os.path.join(dest, "README.md"), (
        f"# {brand}\n\n"
        f"Preregistered v0.3.15 fresh target `{app_name}`.\n"
        f"Topology family: `{fam['family']}`.\n"
        f"Seed `{builder.seed_hex}` = {seed}.\n"
        f"Class: {fam['control_class']}.\n\n"
        "The bug manifest and topology are judge-only and are not served.\n"
        "Static qualification is not empirical transfer.\n"
    ))
    return {
        "app": app_name,
        "seed": seed,
        "seed_hex": builder.seed_hex,
        "n_bugs": len(bugs),
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
        print(f"wrote {rec['app']} seed={rec['seed_hex']} bugs={rec['n_bugs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
