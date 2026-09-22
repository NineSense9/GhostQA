"""Deterministic seed derivation and display vocabulary for v0.3.11 targets.

Topology families and bug mechanics are family-fixed. The seed only fills
display names. No policy, explorer, or oracle imports.
"""
from __future__ import annotations

import hashlib
import random

SEED_PREFIX = "ghostqa-v0.3.11:"

APP_NAMES = ("buggy-crm", "buggy-wiki", "buggy-ops")

BRANDS = {
    "buggy-crm": ["星澜客户", "北衡客户", "青渚客户", "临川客户"],
    "buggy-wiki": ["青简知识库", "石渠文库", "墨池空间", "竹简文库"],
    "buggy-ops": ["云津运维", "朔风值守", "江左观测", "长淮值班"],
}
ACCOUNT_NAMES = ["星河科技", "青木贸易", "临江制造", "南港物流", "北原能源", "东洲设计"]
PERSON_NAMES = ["陈可", "林夏", "周宁", "苏晚", "韩澈", "沈予"]
OPP_TITLES = ["续约扩容", "新品试点", "年度框架", "渠道共建", "服务升级"]
PAGE_TITLES = ["值班手册", "发布清单", "权限模型", "备份策略", "故障分级"]
SPACE_NAMES = ["产品", "工程", "支持", "运营"]
SERVICE_NAMES = ["结算网关", "消息总线", "登录中枢", "对象存储"]
INCIDENT_TITLES = ["延迟升高", "错误突增", "证书将过期", "队列堆积"]
RUNBOOK_TITLES = ["回滚步骤", "扩容手册", "证书轮换", "限流开关"]


def resolve_seed(app_name: str) -> tuple[int, str]:
    digest = hashlib.sha256((SEED_PREFIX + app_name).encode("utf-8")).hexdigest()
    hex8 = digest[:8]
    return int(hex8, 16), hex8


def _pick(rng: random.Random, items: list, n: int) -> list:
    pool = list(items)
    rng.shuffle(pool)
    return pool[:n]


def vocab_for(app_name: str) -> dict:
    if app_name not in APP_NAMES:
        raise ValueError(app_name)
    seed, hex8 = resolve_seed(app_name)
    rng = random.Random(seed)
    brand = rng.choice(BRANDS[app_name])
    people = _pick(rng, PERSON_NAMES, 3)
    if app_name == "buggy-crm":
        acc = _pick(rng, ACCOUNT_NAMES, 3)
        opps = _pick(rng, OPP_TITLES, 3)
        return {
            "app": app_name,
            "seed": seed,
            "seed_hex": hex8,
            "brand": brand,
            "accounts": [
                {"id": "a1", "name": acc[0], "related": ["a2", "a3"]},
                {"id": "a2", "name": acc[1], "related": ["a1", "a3"]},
                {"id": "a3", "name": acc[2], "related": ["a1"]},
            ],
            "contacts": [
                {"id": "c1", "name": people[0], "account": "a1"},
                {"id": "c2", "name": people[1], "account": "a1"},
                {"id": "c3", "name": people[2], "account": "a2"},
            ],
            "opps": [
                {"id": "o1", "title": opps[0], "account": "a1", "related": ["o2", "o3"]},
                {"id": "o2", "title": opps[1], "account": "a1", "related": ["o1"]},
                {"id": "o3", "title": opps[2], "account": "a2", "related": ["o1"]},
            ],
            "team": [{"id": "u1", "name": people[0]},
                     {"id": "u2", "name": people[1]},
                     {"id": "u3", "name": people[2]}],
        }
    if app_name == "buggy-wiki":
        spaces = _pick(rng, SPACE_NAMES, 3)
        pages = _pick(rng, PAGE_TITLES, 3)
        return {
            "app": app_name,
            "seed": seed,
            "seed_hex": hex8,
            "brand": brand,
            "spaces": [
                {"id": "s1", "name": spaces[0]},
                {"id": "s2", "name": spaces[1]},
                {"id": "s3", "name": spaces[2]},
            ],
            "pages": [
                {"id": "p1", "title": pages[0], "space": "s1",
                 "backlinks": ["p2", "p3"], "tags": ["t1"]},
                {"id": "p2", "title": pages[1], "space": "s1",
                 "backlinks": ["p1"], "tags": ["t1", "t2"]},
                {"id": "p3", "title": pages[2], "space": "s2",
                 "backlinks": ["p1"], "tags": ["t2"]},
            ],
            "tags": [{"id": "t1", "name": "流程"}, {"id": "t2", "name": "规范"}],
            "revisions": [
                {"id": "r1", "page": "p1", "n": "3"},
                {"id": "r2", "page": "p1", "n": "2"},
                {"id": "r3", "page": "p2", "n": "1"},
            ],
        }
    services = _pick(rng, SERVICE_NAMES, 3)
    incs = _pick(rng, INCIDENT_TITLES, 3)
    books = _pick(rng, RUNBOOK_TITLES, 3)
    return {
        "app": app_name,
        "seed": seed,
        "seed_hex": hex8,
        "brand": brand,
        "services": [
            {"id": "svc1", "name": services[0]},
            {"id": "svc2", "name": services[1]},
            {"id": "svc3", "name": services[2]},
        ],
        "incidents": [
            {"id": "i1", "title": incs[0], "service": "svc1", "related": ["i2", "i3"]},
            {"id": "i2", "title": incs[1], "service": "svc1", "related": ["i1"]},
            {"id": "i3", "title": incs[2], "service": "svc2", "related": ["i1"]},
        ],
        "alerts": [
            {"id": "al1", "title": "P2 " + incs[0], "service": "svc1", "remaining": 6,
             "remainingDisplay": 6},
            {"id": "al2", "title": "P3 " + incs[1], "service": "svc2", "remaining": 4,
             "remainingDisplay": 4},
        ],
        "runbooks": [
            {"id": "rb1", "title": books[0]},
            {"id": "rb2", "title": books[1]},
            {"id": "rb3", "title": books[2]},
        ],
        "deploys": [
            {"id": "d1", "service": "svc1", "version": "1.4.2"},
            {"id": "d2", "service": "svc1", "version": "1.4.1"},
            {"id": "d3", "service": "svc2", "version": "2.0.0"},
        ],
        "team": [{"id": "u1", "name": people[0]},
                 {"id": "u2", "name": people[1]}],
    }
