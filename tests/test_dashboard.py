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


def test_showcase_reads_v039_published_metrics():
    from dashboard.showcase import build_showcase
    s = build_showcase()
    assert s["latest"]["round"] == "v0.3.9"
    assert s["latest"]["outcome"] == "A"
    assert s["latest"]["product_default_changed"] is False
    rc = s["return_cycle"]
    assert rc["available"] is True
    assert rc["baseline"]["states"] == 6
    assert rc["baseline"]["urls"] == 4
    assert rc["baseline"]["return_attempts"] == 116
    assert rc["candidate"]["states"] == 22
    assert rc["candidate"]["urls"] == 8
    assert rc["candidate"]["return_attempts"] == 15
    assert rc["candidate"]["cycle_escapes"] == 4
    assert rc["deepbench120"]["lost_from_baseline"] == []
    assert rc["deepbench120"]["guard_escapes"] == 0
    assert rc["reproduction"]["clean_clone_verified"] is True


def test_showcase_reads_v038_shop_collapse():
    from dashboard.showcase import build_showcase
    s = build_showcase()
    a = s["application_shape"]
    assert a["available"] is True
    assert a["c1"]["return_attempts"] == 116
    assert a["c1"]["successful_return"] == 0
    assert a["reproduction"]["match"] is True


def test_showcase_missing_artifacts_do_not_crash():
    from dashboard.showcase import build_showcase
    s = build_showcase(v039_root="/tmp/missing-v039", v038_root="/tmp/missing-v038")
    assert s["return_cycle"]["available"] is False
    assert s["application_shape"]["available"] is False
    assert s["latest"]["available"] is False


def test_showcase_has_no_path_query():
    import inspect
    from dashboard import server
    src = inspect.getsource(server.showcase)
    assert "Query" not in src
    assert "path" not in inspect.signature(server.showcase).parameters


def test_showcase_endpoint_function_returns_payload():
    from dashboard.server import showcase
    body = showcase()
    assert body["latest"]["round"] == "v0.3.9"
    assert body["latest"]["outcome"] == "A"
    assert body["return_cycle"]["baseline"]["states"] == 6
    assert body["return_cycle"]["candidate"]["cycle_escapes"] == 4


def test_showcase_evidence_file_counts():
    from dashboard.showcase import build_showcase
    s = build_showcase()
    assert s["return_cycle"]["reproduction"]["evidence_files"] == 8
    assert s["return_cycle"]["reproduction"]["evidence_manifest_verified"] is True
    assert s["application_shape"]["reproduction"]["evidence_files"] == 27
    assert s["application_shape"]["reproduction"]["evidence_manifest_verified"] is True


def test_index_has_three_views_and_live_ids():
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    for token in (
        'id="view-overview"', 'id="view-live"', 'id="view-evidence"',
        'id="run-form"', 'id="shot"', 'id="graph"', 'id="btn-run"',
        'data-testid="return-cycle"', 'data-testid="live-viewport"',
    ):
        assert token in html
    assert "view-overview" in html
    assert "进入实时探索" in html


def test_showcase_assets_exist():
    assert os.path.isfile(os.path.join(STATIC_DIR, "styles", "showcase.css"))
    assert os.path.isfile(os.path.join(STATIC_DIR, "scripts", "showcase.js"))
    css = open(os.path.join(STATIC_DIR, "styles", "base.css"), encoding="utf-8").read()
    assert "body.view-overview" in css


def test_make_policy_exposes_return_guard_without_changing_default():
    from ghostqa.__main__ import _make_policy
    from ghostqa.exploration.return_cycle_guard import ReturnCycleGuardGhostPolicy
    from ghostqa.exploration.policy import GhostPolicy
    g = _make_policy("ghost-structural-return-guard", None, 0)
    assert isinstance(g, ReturnCycleGuardGhostPolicy)
    d = _make_policy("ghost", None, 0)
    assert isinstance(d, GhostPolicy)
    assert d.name == "ghost"
    assert getattr(d, "sequence_mode", "off") in (False, "off", "", None)
