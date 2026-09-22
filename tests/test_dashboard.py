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
    s = build_showcase(v039_root="/tmp/missing-v039", v038_root="/tmp/missing-v038",
                       v0310_root="/tmp/missing-v0310", v0311_root="/tmp/missing-v0311",
                       v0312_root="/tmp/missing-v0312")
    assert s["return_cycle"]["available"] is False
    assert s["application_shape"]["available"] is False
    assert s["fresh_transfer"]["available"] is False
    assert s["multi_target"]["available"] is False
    assert s["nested_hub"]["available"] is False
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
    assert body["return_cycle"]["baseline"]["states"] == 6
    assert body["return_cycle"]["candidate"]["cycle_escapes"] == 4
    assert body["fresh_transfer"]["available"] is True
    assert body["fresh_transfer"]["outcome"] == "A"
    assert body["fresh_transfer"]["product_default_changed"] is False
    assert body["latest"]["product_default_changed"] is False
    mt = body.get("multi_target") or {}
    nh = body.get("nested_hub") or {}
    if nh.get("available"):
        assert body["latest"]["round"] == "v0.3.12"
        assert body["project"]["latest_research"] == "v0.3.12"
        assert nh["product_default_changed"] is False
        assert nh["outcome"] == "C"
        assert nh.get("generalization_claim") is False
    elif mt.get("available"):
        assert body["latest"]["round"] == "v0.3.11"
        assert body["project"]["latest_research"] == "v0.3.11"
        assert mt["product_default_changed"] is False
        assert mt["outcome"] == "D"
        assert mt.get("generalization_claim") is False
        assert mt.get("promotion_readiness") == "not_ready"
        assert mt.get("evaluable_targets") == 1
        assert mt.get("transfer_targets") == 1
    else:
        assert body["latest"]["round"] == "v0.3.10"
        assert body["latest"]["outcome"] == "A"


def test_showcase_reads_v0311_published_metrics():
    from dashboard.showcase import build_showcase
    s = build_showcase()
    mt = s["multi_target"]
    assert mt["available"] is True
    assert mt["outcome"] == "D"
    nh = s["nested_hub"]
    assert nh["available"] is True
    assert s["latest"]["round"] == "v0.3.12"
    assert s["project"]["latest_research"] == "v0.3.12"
    assert nh["outcome"] == "C"
    assert nh["product_default_changed"] is False
    assert nh["generalization_claim"] is False
    assert nh["crm_repair"] is True
    assert nh["ops_repair"] is True
    assert "buggy-desk" in nh["lost_confirmed_cases"]
    assert "deepbench" in nh["lost_confirmed_cases"]
    assert mt["product_default_changed"] is False
    assert mt["generalization_claim"] is False
    assert mt["evaluable_targets"] == 1
    assert mt["transfer_targets"] == 1
    names = [t["name"] for t in mt["targets"]]
    assert names == ["buggy-crm", "buggy-wiki", "buggy-ops"]
    by = {t["name"]: t for t in mt["targets"]}
    assert by["buggy-wiki"]["transfer_demonstrated"] is True
    assert by["buggy-crm"]["transfer_demonstrated"] is False
    assert by["buggy-ops"]["transfer_demonstrated"] is False
    assert s["fresh_transfer"]["outcome"] == "A"
    assert s["latest"]["product_default_changed"] is False
    assert mt["reproduction"]["clean_clone_verified"] is True


def test_showcase_evidence_file_counts():
    from dashboard.showcase import build_showcase
    s = build_showcase()
    assert s["return_cycle"]["reproduction"]["evidence_files"] == 8
    assert s["return_cycle"]["reproduction"]["evidence_manifest_verified"] is True
    assert s["application_shape"]["reproduction"]["evidence_files"] == 27
    assert s["application_shape"]["reproduction"]["evidence_manifest_verified"] is True
    assert s["fresh_transfer"]["reproduction"]["evidence_files"] >= 1
    assert s["fresh_transfer"]["baseline"]["states"] == 6
    assert s["fresh_transfer"]["candidate_run"]["cycle_escapes"] == 7
    assert s["fresh_transfer"]["candidate_run"]["states"] == 35


def test_index_has_three_views_and_live_ids():
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    for token in (
        'id="view-overview"', 'id="view-live"', 'id="view-evidence"',
        'id="run-form"', 'id="shot"', 'id="graph"', 'id="btn-run"',
        'data-testid="return-cycle"', 'data-testid="fresh-transfer"',
        'data-testid="multi-target"', 'data-testid="evidence-v0311"',
        'data-testid="nested-hub"', 'data-testid="evidence-v0312"',
        'id="proof-metric-1"', 'id="tl-v0311"', 'id="tl-v0312"',
        'data-testid="live-viewport"',
        'id="theme-toggle"', 'data-testid="theme-toggle"',
    ):
        assert token in html
    assert "view-overview" in html
    assert "运行一次探索" in html
    assert "进入实时探索" not in html


def test_theme_tokens_and_init_script():
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    tokens = open(os.path.join(STATIC_DIR, "styles", "tokens.css"), encoding="utf-8").read()
    js = open(os.path.join(STATIC_DIR, "scripts", "main.js"), encoding="utf-8").read()
    assert "ghostqa-theme" in html
    assert "prefers-color-scheme" in html
    assert 'data-theme' in html
    assert '[data-theme="light"]' in tokens
    assert '[data-theme="dark"]' in tokens
    assert "--graph-node" in tokens
    assert "--graph-new" in tokens
    assert "Chakra Petch" not in html
    assert "Chakra Petch" not in tokens
    assert "scanlines" not in html
    assert "THEME_KEY" in js
    assert "applyGraphTheme" in js
    assert "#171a1f" not in js
    assert "#3ddad7" not in js
    assert "#a78bfa" not in js


def test_copy_guardrails_and_v038_claim():
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    js = (
        open(os.path.join(STATIC_DIR, "scripts", "main.js"), encoding="utf-8").read()
        + open(os.path.join(STATIC_DIR, "scripts", "showcase.js"), encoding="utf-8").read()
    )
    blob = html + "\n" + js
    assert "没有证据表明 fingerprint" in html
    assert "C0/C1 都记录到 116 次 return attempt" in html
    assert "主要不是 fingerprint 爆炸" not in html
    assert "我们不只" not in blob
    assert "让测试代理自己走完整条路径" not in html
    assert "协议、freeze、manifest、clean clone" not in html
    for phrase in (
        "赋能", "智能化", "革命", "下一代", "一站式", "全链路",
        "领先", "强大", "精准", "高效", "AI-powered", "cutting-edge",
        "重新定义", "一站式智能", "不仅",
    ):
        assert phrase not in blob
    assert "BuggyShop 是机制分析用例" in html or "已分析用例" in html


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
    from ghostqa.exploration.nested_hub_guard import NestedHubReturnGuardGhostPolicy
    n = _make_policy("ghost-structural-nested-return-guard", None, 0)
    assert isinstance(n, NestedHubReturnGuardGhostPolicy)
    assert n.name == "ghost-structural-nested-return-guard"
    assert n is not d
