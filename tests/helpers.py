"""Shared test fixtures. Tests must not import other test modules."""
from ghostqa.executor.sim import SimApp


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
