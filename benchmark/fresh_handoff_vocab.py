"""Frozen vocabulary for the v0.3.15 fresh handoff targets.

Names and seeds only. No exploration, policy, or result imports.
"""
from __future__ import annotations

import hashlib
import random

SEED_PREFIX = "ghostqa-v0.3.15:"

# Visible-label fragments that commit, return, or leave the primary nav list.
# Used so generated controls match their declared branch flags.
UI_NON_BRANCH_TOKENS = (
    "返回", "return", "back", "previous", "parent", "上一级",
    "帮助", "关于", "文档", "设置", "历史", "报表", "日志",
    "help", "about", "docs", "settings", "history", "report",
    "下一步", "继续", "登录", "提交", "创建", "确认", "完成", "保存",
    "进入", "新建", "结算", "支付", "注册",
    "next", "continue", "login", "submit", "create", "confirm",
    "finish", "save", "enter", "signup", "register", "checkout", "pay",
)

APPS = ("buggy-forum", "buggy-billing", "buggy-lab", "buggy-directory")

FAMILIES = {
    "buggy-forum": {
        "family": "cross_linked_discussion_with_nested_moderation",
        "control_class": "positive",
        "port": 3945,
        "prefix": "BUG-F",
        "bug_count": 10,
        "brand_pool": ("澄谈社区", "望潮论坛", "拾句部落"),
        "storage_key": "forum_v0315",
        "fail_error": "forum export dispatch failed",
        "search_error": "forum search query too long",
        "sync_error": "forum sync handshake failed",
    },
    "buggy-billing": {
        "family": "transactional_nested_account_invoice_payment",
        "control_class": "positive",
        "port": 3946,
        "prefix": "BUG-B",
        "bug_count": 10,
        "brand_pool": ("析账台", "衡票簿", "澄算屋"),
        "storage_key": "billing_v0315",
        "fail_error": "billing export dispatch failed",
        "search_error": "billing search query too long",
        "sync_error": "billing sync handshake failed",
    },
    "buggy-lab": {
        "family": "deep_experiment_run_sample_result_graph",
        "control_class": "positive",
        "port": 3947,
        "prefix": "BUG-L",
        "bug_count": 10,
        "brand_pool": ("砚衡实验", "澄测记录", "拾样台"),
        "storage_key": "lab_v0315",
        "fail_error": "lab export dispatch failed",
        "search_error": "lab search query too long",
        "sync_error": "lab sync handshake failed",
    },
    "buggy-directory": {
        "family": "shallow_flat_fanout_control",
        "control_class": "negative",
        "port": 3948,
        "prefix": "BUG-DIR",
        "bug_count": 8,
        "brand_pool": ("平录名册", "廊录", "值名簿"),
        "storage_key": "directory_v0315",
        "fail_error": "directory export dispatch failed",
        "search_error": "directory search query too long",
        "sync_error": "directory sync handshake failed",
    },
}

NAME_POOLS = {
    "zone": ("城事", "书评", "科谈", "夜读", "市集"),
    "topic": ("周末市集", "旧书店", "望远镜", "雨天菜单", "码头钟"),
    "person": ("周宁", "林夏", "许昭", "陈汐", "宋晚"),
    "account": ("临江制造", "北原能源", "星河科技", "青石物流", "南风食品"),
    "invoice": ("三月服务费", "四月托管", "五月备件", "六月维保"),
    "project": ("澄水样本", "东岸对照", "夜航观测"),
    "experiment": ("温度曲线", "溶剂对照", "光照批次", "振荡复核"),
    "run": ("清晨批次", "午后批次", "夜间批次"),
    "sample": ("瓶A", "瓶B", "瓶C"),
    "result": ("峰面积", "回收率", "空白漂移"),
    "team": ("前台", "档案", "值班"),
    "office": ("一号楼", "二号楼", "仓库"),
    "role": ("接待", "归档", "巡查"),
}


def resolve_seed(app_name: str) -> tuple[int, str]:
    digest = hashlib.sha256((SEED_PREFIX + app_name).encode("utf-8")).hexdigest()
    hex8 = digest[:8]
    return int(hex8, 16), hex8


def assign_names(seed: int, pool_key: str, ids: list[str]) -> dict[str, str]:
    pool = list(NAME_POOLS[pool_key])
    if len(pool) < len(ids):
        raise ValueError(pool_key)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return {item_id: pool[index] for index, item_id in enumerate(ids)}


def contains_non_branch(text: str, testid: str = "") -> bool:
    blob = f"{text} {testid}".lower()
    return any(token.lower() in blob for token in UI_NON_BRANCH_TOKENS)
