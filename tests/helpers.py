"""Shared test fixtures. Tests must not import other test modules."""
from ghostqa.executor.sim import SimApp
from ghostqa.state.models import GUIState, UIElement


def make_seq_el(eid, text, kind="click"):
    return UIElement(eid, "button", text, kind=kind)


def make_hub_state():
    return GUIState(
        app="t", url="/hub", title="Hub",
        elements=(
            make_seq_el("go_a", "分支A"),
            make_seq_el("go_b", "分支B"),
            make_seq_el("go_c", "分支C"),
            make_seq_el("submit", "提交"),
        ), obs={})


def make_seq_app():
    pages = {
        "hub": {"url": "/hub", "title": "Hub",
                "elements": [
                    {"eid": "go_a", "role": "button", "text": "分支A",
                     "effect": {"op": "goto", "to": "a"}},
                    {"eid": "go_b", "role": "button", "text": "分支B",
                     "effect": {"op": "goto", "to": "b"}},
                    {"eid": "go_c", "role": "button", "text": "分支C",
                     "effect": {"op": "goto", "to": "c"}},
                ]},
        "a": {"url": "/a", "title": "A",
              "elements": [
                  {"eid": "mutate", "role": "button", "text": "变更",
                   "effect": {"op": "goto", "to": "a2"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
        "a2": {"url": "/a2", "title": "A2",
               "elements": [
                   {"eid": "follow", "role": "button", "text": "后续",
                    "effect": {"op": "goto", "to": "hub"}},
                   {"eid": "backh", "role": "button", "text": "返回",
                    "effect": {"op": "goto", "to": "hub"}},
               ]},
        "b": {"url": "/b", "title": "B",
              "elements": [
                  {"eid": "leaf_b", "role": "button", "text": "叶子B",
                   "effect": {"op": "noop"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
        "c": {"url": "/c", "title": "C",
              "elements": [
                  {"eid": "leaf_c", "role": "button", "text": "叶子C",
                   "effect": {"op": "noop"}},
                  {"eid": "backh", "role": "button", "text": "返回",
                   "effect": {"op": "goto", "to": "hub"}},
              ]},
    }
    return SimApp("seq", "hub", pages, {}, lambda i, p: {})


def make_mini_crash_app():
    """Tiny app with an easily reachable crash for loop-level tests."""
    pages = {
        "home": {"url": "/home", "title": "首页",
                 "elements": [
                     {"eid": "nav_a", "role": "link", "text": "页面A",
                      "effect": {"op": "goto", "to": "a"}},
                 ]},
        "a": {"url": "/a", "title": "页面A",
              "elements": [
                  {"eid": "btn_boom", "role": "button", "text": "危险操作",
                   "effect": {"op": "crash"}},
              ]},
    }
    return SimApp("mini-crash", "home", pages, {}, lambda i, p: {})
