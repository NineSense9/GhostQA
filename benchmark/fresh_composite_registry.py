"""Additive app registry for the v0.3.20 fresh targets.

benchmark/web_runner.py is covered by the v0.3.9 candidate freeze, so this
module does not edit that map. Historical ids still resolve to the same
directories. The six v0.3.20 ids are added beside them.
"""
from __future__ import annotations

import os

from benchmark.web_runner import APPS as HISTORICAL_APP_DIRS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HISTORICAL_KEYS = (
    "buggy-shop",
    "buggy-flow",
    "buggy-desk",
    "buggy-crm",
    "buggy-wiki",
    "buggy-ops",
)

FRESH = {
    "buggy-campus": {"dir": "apps/buggy-campus", "port": 3951},
    "buggy-warehouse": {"dir": "apps/buggy-warehouse", "port": 3952},
    "buggy-studio": {"dir": "apps/buggy-studio", "port": 3953},
    "buggy-booking": {"dir": "apps/buggy-booking", "port": 3954},
    "buggy-catalog": {"dir": "apps/buggy-catalog", "port": 3955},
    "buggy-kiosk": {"dir": "apps/buggy-kiosk", "port": 3956},
}


def resolve(app_id: str) -> str:
    if app_id in FRESH:
        return os.path.join(ROOT, FRESH[app_id]["dir"].replace("/", os.sep))
    if app_id in HISTORICAL_APP_DIRS:
        return HISTORICAL_APP_DIRS[app_id]
    raise KeyError(app_id)


def fresh_port(app_id: str) -> int:
    return int(FRESH[app_id]["port"])
