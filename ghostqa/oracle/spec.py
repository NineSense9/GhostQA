"""Semantic spec DSL (JSON) + expression registry.

Spec file format (JSON list):
[
  {
    "id": "cart_total_consistent",
    "severity": "high",
    "when": {"url_contains": "/cart"},          # or "always" / {"action_key_contains": "..."}
    "assert": {"op": "eq",
               "left":  {"obs": "cart_total_display_num"},
               "right": {"expr": "cart_total"}}
  }
]

Operand forms: {"obs": key} | {"gt": key} | {"const": value} | {"expr": name}
Expression names are registered callables: fn(ground_truth: dict) -> value.
Supported ops: eq, ne, ge, gt, le, lt, contains, not_contains, implies
"""
from __future__ import annotations

import json


class ExprRegistry:
    def __init__(self):
        self._fns = {}

    def register(self, name: str, fn):
        self._fns[name] = fn

    def eval(self, name: str, ground_truth: dict):
        if name not in self._fns:
            raise KeyError(f"expr '{name}' not registered")
        return self._fns[name](ground_truth)


DEFAULT_REGISTRY = ExprRegistry()
DEFAULT_REGISTRY.register("cart_total",
                          lambda gt: sum(i["price"] * i["qty"] for i in gt.get("cart", [])))
DEFAULT_REGISTRY.register("cart_count", lambda gt: len(gt.get("cart", [])))


def load_spec(path: str) -> list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _operand(val: dict, obs: dict, gt: dict, registry: ExprRegistry):
    if "obs" in val:
        return obs.get(val["obs"])
    if "gt" in val:
        return gt.get(val["gt"])
    if "const" in val:
        return val["const"]
    if "expr" in val:
        return registry.eval(val["expr"], gt)
    raise ValueError(f"bad operand {val}")


def eval_pred(node: dict, obs: dict, gt: dict, registry: ExprRegistry):
    """Returns True (pass) / False (violation) / None (not applicable here)."""
    op = node["op"]
    if op == "implies":
        cond = eval_pred(node["cond"], obs, gt, registry)
        if cond is not True:
            return None                        # cond unknown or false -> not applicable
        return eval_pred(node["then"], obs, gt, registry)
    left = _operand(node["left"], obs, gt, registry)
    right = _operand(node["right"], obs, gt, registry)
    if left is None or right is None:
        return None                            # page does not expose these values
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if op == "ge":
        return left >= right
    if op == "gt":
        return left > right
    if op == "le":
        return left <= right
    if op == "lt":
        return left < right
    if op == "contains":
        return str(right) in str(left)
    if op == "not_contains":
        return str(right) not in str(left)
    raise ValueError(f"bad op {op}")


def when_matches(when, url: str, action_key: str) -> bool:
    if when is None or when == "always":
        return True
    if isinstance(when, dict):
        if "url_contains" in when:
            return when["url_contains"] in url
        if "action_key_contains" in when:
            return when["action_key_contains"] in action_key
    return False
