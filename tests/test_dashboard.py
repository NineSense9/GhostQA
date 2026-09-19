"""Dashboard presentation-layer helpers. Does not start a server."""
import os

from dashboard.server import (
    _public_event, STATIC_DIR, shot_basename, is_safe_shot_name,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.explorer import RunResult
from ghostqa.state.models import Action, Finding, Step


def test_public_event_rewrites_screenshot_to_servable_url():
    ev = _public_event("abc123", {
        "src": {"screenshot": r"C:\tmp\shot-1.png", "url": "/a"},
        "dst": {"screenshot": "/abs/shot-2.png"},
    })
    assert ev["src"]["screenshot"] == "/api/runs/abc123/shot/shot-1.png"
    assert ev["dst"]["screenshot"] == "/api/runs/abc123/shot/shot-2.png"
    assert ev["src"]["url"] == "/a"


def test_shot_basename_is_os_agnostic():
    assert shot_basename(r"C:\tmp\shot-1.png") == "shot-1.png"
    assert shot_basename("C:/foo/bar.png") == "bar.png"
    assert shot_basename("/foo/bar.png") == "bar.png"
    assert shot_basename("bar.png") == "bar.png"
    assert shot_basename("") == ""


def test_shot_name_rejects_traversal():
    assert is_safe_shot_name("shot-1.png")
    assert not is_safe_shot_name("../shot-1.png")
    assert not is_safe_shot_name("a/shot-1.png")
    assert not is_safe_shot_name("a\\shot-1.png")
    assert not is_safe_shot_name("shot-1.jpg")
    assert not is_safe_shot_name("")


def test_hidden_css_beats_display_block():
    css = open(os.path.join(STATIC_DIR, "styles", "base.css"), encoding="utf-8").read()
    assert "[hidden] { display: none !important; }" in css


def test_dashboard_confirmed_uses_episode_local_length():
    result = RunResult(app="t", policy="p")
    result.reset_events = [{"before_step": 0, "reason": "initial", "episode_id": 0},
                           {"before_step": 2, "reason": "relocate", "episode_id": 1}]
    a = Action("click", "nav_a")
    b = Action("click", "nav_b")
    c = Action("click", "btn_bug")
    result.steps = [
        Step(0, "s0", a, "s1", episode_id=0),
        Step(1, "s1", b, "s2", episode_id=1),
        Step(2, "s2", c, "s3", episode_id=1,
             findings=[Finding("js_error", "high", "x", 2)]),
    ]
    finding = result.steps[2].findings[0]
    repro = result.reproduction_actions(finding)
    bug = result.make_confirmed(finding, repro)
    assert bug.original_length == 2
    assert bug.episode_local_reproduction_length == 2
    assert bug.original_global_step == 2
    assert bug.source_episode_id == 1
    assert finding.step_index + 1 == 3  # the old dashboard bug


def test_product_ghost_default_has_frontier_off():
    assert GhostPolicy().use_frontier is False
    assert GhostPolicy(use_frontier=True).use_frontier is True
