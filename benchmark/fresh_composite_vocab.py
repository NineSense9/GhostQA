"""Frozen vocabulary for the v0.3.20 fresh composite targets.

Names, seeds, and the visible-label fragments that are not branch clicks.
No exploration, policy, or result imports. The token list is duplicated data
so generated hubs match the frozen UI vocabulary without importing it.
"""
from __future__ import annotations

import hashlib
import random

SEED_PREFIX = "ghostqa-v0.3.20:"

UI_NON_BRANCH_TOKENS = (
    "返回", "return", "back", "previous", "parent", "上一级",
    "帮助", "关于", "文档", "设置", "历史", "报表", "日志",
    "help", "about", "docs", "settings", "history", "report",
    "下一步", "继续", "登录", "提交", "创建", "确认", "完成", "保存",
    "进入", "演示登录", "新建", "打开项目", "结算", "支付", "注册",
    "next", "continue", "login", "submit", "create", "confirm",
    "finish", "save", "enter", "sign in", "signup", "register",
    "checkout", "pay",
)

APP_NAMES = (
    "buggy-campus",
    "buggy-warehouse",
    "buggy-studio",
    "buggy-booking",
    "buggy-catalog",
    "buggy-kiosk",
)
POSITIVE = APP_NAMES[:4]
NEGATIVE = APP_NAMES[4:]

FAMILIES = {
    "buggy-campus": {
        "family": "hierarchical_learning_assessment_review",
        "control_class": "positive",
        "port": 3951,
        "prefix": "BUG-CP",
        "bug_count": 12,
        "brand_pool": ("澄课书院", "望溪学堂", "拾页教室"),
        "storage_key": "campus_v0320",
        "fail_error": "campus export dispatch failed",
        "search_error": "campus search query too long",
        "sync_error": "campus sync handshake failed",
    },
    "buggy-warehouse": {
        "family": "inventory_batch_transfer_audit",
        "control_class": "positive",
        "port": 3952,
        "prefix": "BUG-WH",
        "bug_count": 12,
        "brand_pool": ("澄仓台", "北垛库存", "拾箱库房"),
        "storage_key": "warehouse_v0320",
        "fail_error": "warehouse export dispatch failed",
        "search_error": "warehouse search query too long",
        "sync_error": "warehouse sync handshake failed",
    },
    "buggy-studio": {
        "family": "project_scene_asset_render_review",
        "control_class": "positive",
        "port": 3953,
        "prefix": "BUG-ST",
        "bug_count": 12,
        "brand_pool": ("澄帧工坊", "夜场制片", "拾镜棚"),
        "storage_key": "studio_v0320",
        "fail_error": "studio export dispatch failed",
        "search_error": "studio search query too long",
        "sync_error": "studio sync handshake failed",
    },
    "buggy-booking": {
        "family": "venue_calendar_reservation_guest_workflow",
        "control_class": "positive",
        "port": 3954,
        "prefix": "BUG-BK",
        "bug_count": 12,
        "brand_pool": ("澄席预订", "临江会场", "拾间日历"),
        "storage_key": "booking_v0320",
        "fail_error": "booking export dispatch failed",
        "search_error": "booking search query too long",
        "sync_error": "booking sync handshake failed",
    },
    "buggy-catalog": {
        "family": "shallow_catalog_fanout_control",
        "control_class": "negative",
        "port": 3955,
        "prefix": "BUG-CT",
        "bug_count": 8,
        "brand_pool": ("平录图册", "廊间样本", "值品目录"),
        "storage_key": "catalog_v0320",
        "fail_error": "catalog export dispatch failed",
        "search_error": "catalog search query too long",
        "sync_error": "catalog sync handshake failed",
    },
    "buggy-kiosk": {
        "family": "shallow_finding_heavy_button_control",
        "control_class": "negative",
        "port": 3956,
        "prefix": "BUG-KS",
        "bug_count": 8,
        "brand_pool": ("澄台自助", "门厅柜台", "拾号面板"),
        "storage_key": "kiosk_v0320",
        "fail_error": "kiosk export dispatch failed",
        "search_error": "kiosk search query too long",
        "sync_error": "kiosk sync handshake failed",
    },
}

NAME_POOLS = {
    "course": ("晨读课", "水彩课", "声乐课", "园艺课"),
    "module": ("第一单元", "第二单元", "第三单元"),
    "lesson": ("识谱", "对唱", "合奏", "复习"),
    "warehouse": ("东库", "西库", "南库", "北库"),
    "zone": ("常温区", "冷藏区", "拣选区"),
    "item": ("纸箱", "托盘", "胶带", "标签"),
    "project": ("晨雾短片", "港湾纪录", "夜市动画"),
    "scene": ("开场", "街巷", "收束", "空镜"),
    "asset": ("台词本", "布景图", "音轨", "字幕"),
    "venue": ("临江厅", "北楼厅", "花园厅"),
    "room": ("梅花间", "竹叶间", "听雨间", "望湖间"),
    "guest": ("周宁", "林夏", "许昭"),
    "product": ("陶杯", "麻布袋", "木梳", "纸灯"),
    "task": ("取号", "补打", "问询"),
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
