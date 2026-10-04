"""Dashboard presentation-layer helpers. Does not start a server."""
import json
import os

from dashboard.server import (
    _public_event, STATIC_DIR, shot_basename, is_safe_shot_name,
    RunHandle, replay_until_stop,
)
from ghostqa.exploration.policy import GhostPolicy
from ghostqa.exploration.explorer import RunResult
from ghostqa.state.models import Action, Finding, Step


def _v0338_publication():
    root = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "experiments", "published", "fresh-transfer-v0.3.38")
    with open(os.path.join(root, "metrics", "mechanism.json"), encoding="utf-8") as handle:
        mechanism = json.load(handle)
    with open(os.path.join(root, "metrics", "safety.json"), encoding="utf-8") as handle:
        safety = json.load(handle)
    facts = safety["facts"]
    controls = mechanism["controls"]
    return {
        "outcome": mechanism["derived"]["outcome"],
        "evaluable_positives": facts["evaluable_positives"],
        "structured_positives": facts["structured_positives"],
        "fresh_guard_loss": facts["fresh_guard_loss"],
        "historical_guard_loss": facts["historical_guard_loss"],
        "saddle_handoff": controls["buggy-saddle"]["handoff"],
        "timber_handoff": controls["buggy-timber"]["handoff"],
    }


def test_public_event_rewrites_screenshot_to_servable_url():
    ev = _public_event("abc123", {
        "src": {"screenshot": r"C:\tmp\shot-1.png", "url": "/a"},
        "dst": {"screenshot": "/abs/shot-2.png"},
    })
    assert ev["src"]["screenshot"] == "/api/runs/abc123/shot/shot-1.png"
    assert ev["dst"]["screenshot"] == "/api/runs/abc123/shot/shot-2.png"
    assert ev["src"]["url"] == "/a"


def test_public_event_exposes_phase_and_ai_observability():
    ev = _public_event("abc123", {
        "type": "step", "phase": "exploration",
        "decision": {"mode": "model_gate", "model_used": True,
                      "top_k": [{"label": "刷新合计", "score": 0.86}]},
        "src": {}, "dst": {},
    })
    assert ev["phase"] == "exploration"
    assert ev["decision"]["model_used"] is True
    assert ev["decision"]["top_k"][0]["label"] == "刷新合计"


def test_replay_until_stop_keeps_unfinished_candidates_and_continues():
    unfinished = []
    confirmed = []

    def validate(finding):
        if finding == "timeout":
            raise TimeoutError("navigation timeout")
        return True

    replay_until_stop(
        ["timeout", "ok"], lambda: False, validate,
        lambda finding: [finding],
        lambda finding, repro: confirmed.append(finding),
        lambda finding, exc: unfinished.append((finding, str(exc))),
    )
    assert unfinished == [("timeout", "navigation timeout")]
    assert confirmed == ["ok"]


def test_live_console_has_product_flow_and_ai_panel():
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    js = open(os.path.join(STATIC_DIR, "scripts", "main.js"), encoding="utf-8").read()
    assert 'id="run-stage"' in html
    assert 'id="ai-readout"' in html
    assert "配置" in html and "最小化" in html and "报告" in html
    assert "decision" in js
    assert "partial" in js


def test_ghost_decision_is_observable_without_changing_selection():
    from ghostqa.exploration.observation import select_observed
    from ghostqa.agent.gateway import MockLLM
    from ghostqa.state.graph import StateGraph
    from ghostqa.state.models import GUIState
    policy = GhostPolicy(MockLLM())
    policy._program_score = lambda *args: 1.0
    policy._gate_reasons = lambda *args: ["near_tie"]
    actions = [Action("click", "pay"), Action("back")]
    ctx = {"sig": "exact:1", "step": 0}
    state = GUIState(app="test", url="/cart", title="购物车")
    chosen = select_observed(policy, StateGraph(), state, actions, ctx)
    assert ctx["last_decision"]["model_used"] is True
    assert ctx["last_decision"]["cache_hit"] is False
    assert ctx["last_decision"]["chosen_key"] == chosen.key()
    json.dumps(ctx["last_decision"])
    select_observed(policy, StateGraph(), state, actions, ctx)
    assert ctx["last_decision"]["cache_hit"] is True


def test_partial_report_distinguishes_failed_and_unfinished():
    from ghostqa.report.generator import report_for_saved_run, render_html
    report = report_for_saved_run({}, {}, [], "partial")
    assert report is not None
    page = render_html(report, [
        {"kind": "dead_action", "description": "未复现", "replay_status": "failed"},
        {"kind": "nav_loop", "description": "入口未完成", "replay_status": "unfinished",
         "replay_error_type": "navigation_timeout", "replay_error": "navigation timeout"},
    ])
    assert "未通过重放" in page and "重放未完成" in page
    assert "导航超时" in page


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
    policy = GhostPolicy()
    assert policy.sequence_mode == "off"
    assert policy.use_frontier is False
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
                       v0312_root="/tmp/missing-v0312", v0313_root="/tmp/missing-v0313",
                       v0314_root="/tmp/missing-v0314", v0315_root="/tmp/missing-v0315",
                       v0316_root="/tmp/missing-v0316",
                       v0317_root="/tmp/missing-v0317",
                       v0318_root="/tmp/missing-v0318",
                       v0319_root="/tmp/missing-v0319",
                       v0320_root="/tmp/missing-v0320",
                       v0321_root="/tmp/missing-v0321",
                       v0322_root="/tmp/missing-v0322",
                       v0323_root="/tmp/missing-v0323",
                       v0324_root="/tmp/missing-v0324",
                       v0325_root="/tmp/missing-v0325",
                       v0326_root="/tmp/missing-v0326",
                       v0327_root="/tmp/missing-v0327",
                       v0330_root="/tmp/missing-v0330",
                       v0331_root="/tmp/missing-v0331",
                       v0332_root="/tmp/missing-v0332",
                       v0333_root="/tmp/missing-v0333",
                       v0334_root="/tmp/missing-v0334",
                       v0335_root="/tmp/missing-v0335",
                       v0336_root="/tmp/missing-v0336",
                       v0337_root="/tmp/missing-v0337",
                       v0338_root="/tmp/missing-v0338")
    assert s["return_cycle"]["available"] is False
    assert s["application_shape"]["available"] is False
    assert s["fresh_transfer"]["available"] is False
    assert s["multi_target"]["available"] is False
    assert s["nested_hub"]["available"] is False
    assert s["nested_stack"]["available"] is False
    assert s["horizon_handoff"]["available"] is False
    assert s["fresh_handoff"]["available"] is False
    assert s["reentry_frontier"]["available"] is False
    assert s["local_action_drain"]["available"] is False
    assert s["return_entry_drain"]["available"] is False
    assert s["finding_return_entry"]["available"] is False
    assert s["fresh_composite"]["available"] is False
    assert s["return_waypoint"]["available"] is False
    assert s["post_escape_sink"]["available"] is False
    assert s["residual_frontier_debt"]["available"] is False
    assert s["episode_drain"]["available"] is False
    assert s["fresh_transfer_v0325"]["available"] is False
    assert s["fresh_transfer_v0326"]["available"] is False
    assert s["fresh_transfer_v0327"]["available"] is False
    assert s["fresh_transfer_v0330"]["available"] is False
    assert s["fresh_transfer_v0331"]["available"] is False
    assert s["fresh_transfer_v0332"]["available"] is False
    assert s["fresh_transfer_v0333"]["available"] is False
    assert s["fresh_transfer_v0334"]["available"] is False
    assert s["fresh_transfer_v0335"]["available"] is False
    assert s["fresh_transfer_v0336"]["available"] is False
    assert s["fresh_transfer_v0337"]["available"] is False
    assert s["fresh_transfer_v0338"]["available"] is False
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
    ns = body.get("nested_stack") or {}
    hh = body.get("horizon_handoff") or {}
    fh = body.get("fresh_handoff") or {}
    rf = body.get("reentry_frontier") or {}
    la = body.get("local_action_drain") or {}
    re = body.get("return_entry_drain") or {}
    fr = body.get("finding_return_entry") or {}
    fc = body.get("fresh_composite") or {}
    rw = body.get("return_waypoint") or {}
    sink = body.get("post_escape_sink") or {}
    debt = body.get("residual_frontier_debt") or {}
    episode = body.get("episode_drain") or {}
    fresh25 = body.get("fresh_transfer_v0325") or {}
    fresh26 = body.get("fresh_transfer_v0326") or {}
    fresh27 = body.get("fresh_transfer_v0327") or {}
    fresh30 = body.get("fresh_transfer_v0330") or {}
    fresh31 = body.get("fresh_transfer_v0331") or {}
    fresh32 = body.get("fresh_transfer_v0332") or {}
    fresh33 = body.get("fresh_transfer_v0333") or {}
    fresh34 = body.get("fresh_transfer_v0334") or {}
    fresh35 = body.get("fresh_transfer_v0335") or {}
    fresh36 = body.get("fresh_transfer_v0336") or {}
    fresh37 = body.get("fresh_transfer_v0337") or {}
    fresh38 = body.get("fresh_transfer_v0338") or {}
    if fresh38.get("available"):
        assert body["latest"]["round"] == "v0.3.38"
        assert body["project"]["latest_research"] == "v0.3.38"
        assert body["latest"]["outcome"] == "A"
        assert fresh38["outcome"] == "A"
        assert fresh38["product_default_changed"] is False
        assert fresh38["promotion_readiness"] == "not_ready"
        assert fresh38["evaluable_positives"] == 4
        assert fresh38["structured_positives"] == 4
        assert fresh38["fresh_guard_loss"] == []
        assert fresh38["historical_guard_loss"] == []
        assert fresh38["saddle_handoff"] == 0
        assert fresh38["timber_handoff"] == 0
        published = _v0338_publication()
        assert fresh38["outcome"] == published["outcome"]
        assert fresh38["evaluable_positives"] == published["evaluable_positives"]
        assert fresh38["structured_positives"] == published["structured_positives"]
        assert fresh38["fresh_guard_loss"] == published["fresh_guard_loss"]
        assert fresh38["historical_guard_loss"] == published["historical_guard_loss"]
        assert fresh38["saddle_handoff"] == published["saddle_handoff"]
        assert fresh38["timber_handoff"] == published["timber_handoff"]
        assert fresh37["outcome"] == "C"
        assert fresh36["outcome"] == "C"
        assert fresh35["outcome"] == "A"
        assert GhostPolicy().sequence_mode == "off"
        assert GhostPolicy().use_frontier is False
        assert episode["outcome"] == "A"
    elif fresh37.get("available"):
        assert body["latest"]["round"] == "v0.3.37"
        assert body["project"]["latest_research"] == "v0.3.37"
        assert body["latest"]["outcome"] == "C"
        assert fresh37["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh37["product_default_changed"] is False
        assert fresh37["promotion_readiness"] == "not_ready"
        assert fresh37["evaluable_positives"] == 4
        assert fresh37["structured_positives"] == 0
        assert [row["bugs"] for row in fresh37["fresh_guard_loss"]] == [
            ["BUG-FD10"], ["BUG-GD10"], ["BUG-HL10"], ["BUG-IT10"]]
        assert fresh37["historical_guard_loss"] == [
            {"app": "buggy-directory", "bugs": ["BUG-DIR5"]}]
        assert fresh37["junction_handoff"] == 0
        assert fresh37["karst_handoff"] == 0
        assert fresh36["outcome"] == "C"
        assert fresh35["outcome"] == "A"
        assert GhostPolicy().sequence_mode == "off"
        assert GhostPolicy().use_frontier is False
        assert episode["outcome"] == "A"
    elif fresh36.get("available"):
        assert body["latest"]["round"] == "v0.3.36"
        assert body["project"]["latest_research"] == "v0.3.36"
        assert body["latest"]["outcome"] == "C"
        assert fresh36["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh36["evaluable_positives"] == 4
        assert fresh36["structured_positives"] == 0
        assert [row["bugs"] for row in fresh36["fresh_guard_loss"]] == [
            ["BUG-WI10"], ["BUG-YA10"], ["BUG-ZE10"], ["BUG-AB10"]]
        assert fresh36["historical_guard_loss"] == [
            {"app": "buggy-directory", "bugs": ["BUG-DIR5"]}]
        assert fresh36["basin_handoff"] == 0
        assert fresh36["cleft_handoff"] == 0
        assert fresh35["outcome"] == "A"
        assert fresh34["outcome"] == "A"
        assert episode["outcome"] == "A"
    elif fresh35.get("available"):
        assert body["latest"]["round"] == "v0.3.35"
        assert body["project"]["latest_research"] == "v0.3.35"
        assert body["latest"]["outcome"] == "A"
        assert fresh35["outcome"] == "A"
        assert body["latest"]["product_default_changed"] is False
        assert fresh35["evaluable_positives"] == 4
        assert fresh35["structured_positives"] == 4
        assert fresh35["fresh_guard_loss"] == []
        assert fresh35["historical_guard_loss"] == []
        assert fresh35["umber_handoff"] == 0
        assert fresh35["verge_handoff"] == 0
        assert fresh34["outcome"] == "A"
        assert fresh33["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh34.get("available"):
        assert body["latest"]["round"] == "v0.3.34"
        assert body["project"]["latest_research"] == "v0.3.34"
        assert body["latest"]["outcome"] == "A"
        assert fresh34["outcome"] == "A"
        assert body["latest"]["product_default_changed"] is False
        assert fresh34["evaluable_positives"] == 4
        assert fresh34["structured_positives"] == 4
        assert fresh34["fresh_guard_loss"] == []
        assert fresh34["historical_guard_loss"] == []
        assert fresh34["oxbow_handoff"] == 0
        assert fresh34["pond_handoff"] == 0
        assert fresh33["outcome"] == "C"
        assert fresh32["outcome"] == "A"
        assert episode["outcome"] == "A"
    elif fresh33.get("available"):
        assert body["latest"]["round"] == "v0.3.33"
        assert body["project"]["latest_research"] == "v0.3.33"
        assert body["latest"]["outcome"] == "C"
        assert fresh33["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh33["evaluable_positives"] == 4
        assert fresh33["structured_positives"] == 4
        assert fresh33["fresh_guard_loss"] == []
        assert fresh33["historical_guard_loss"] == [
            {"app": "buggy-wiki", "bugs": ["BUG-W2"]}]
        assert fresh33["ledge_handoff"] == 0
        assert fresh33["notch_handoff"] == 0
        assert fresh32["outcome"] == "A"
        assert fresh31["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh32.get("available"):
        assert body["latest"]["round"] == "v0.3.32"
        assert body["project"]["latest_research"] == "v0.3.32"
        assert body["latest"]["outcome"] == "A"
        assert fresh32["outcome"] == "A"
        assert body["latest"]["product_default_changed"] is False
        assert fresh32["product_default_changed"] is False
        assert fresh32["evaluable_positives"] == 4
        assert fresh32["structured_positives"] == 4
        assert fresh32["fresh_guard_loss"] == []
        assert fresh32["historical_guard_loss"] == []
        assert fresh32["loft_handoff"] == 0
        assert fresh32["mesa_handoff"] == 0
        assert fresh31["outcome"] == "C"
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh31.get("available"):
        assert body["latest"]["round"] == "v0.3.31"
        assert body["project"]["latest_research"] == "v0.3.31"
        assert body["latest"]["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh31["evaluable_positives"] == 4
        assert fresh31["structured_positives"] == 0
        assert fresh31["crate_handoff"] == 0
        assert fresh31["stand_handoff"] == 0
        assert [row["bugs"] for row in fresh31["fresh_guard_loss"]] == [
            ["BUG-MH4"], ["BUG-CV4"], ["BUG-GN4"], ["BUG-FG4"]]
        assert fresh31["historical_guard_loss"] == []
        assert fresh30["outcome"] == "C"
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh30.get("available"):
        assert body["latest"]["round"] == "v0.3.30"
        assert body["project"]["latest_research"] == "v0.3.30"
        assert body["latest"]["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh30["evaluable_positives"] == 4
        assert fresh30["structured_positives"] == 0
        assert fresh30["tray_handoff"] == 0
        assert fresh30["booth_handoff"] == 0
        assert [row["bugs"] for row in fresh30["fresh_guard_loss"]] == [
            ["BUG-CR4"], ["BUG-RG4"], ["BUG-WF4"], ["BUG-KN4"]]
        assert fresh30["historical_guard_loss"] == [
            {"app": "buggy-desk", "bugs": ["BUG-K10"]},
            {"app": "buggy-shop", "bugs": ["BUG-W6"]},
        ]
        assert fresh30["inspected_settings"] == {"buggy-campus": [], "buggy-studio": []}
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh27.get("available"):
        assert body["latest"]["round"] == "v0.3.27"
        assert body["project"]["latest_research"] == "v0.3.27"
        assert body["latest"]["outcome"] == "B"
        assert body["latest"]["product_default_changed"] is False
        assert fresh27["outcome"] == "B"
        assert fresh27["evaluable_positives"] == 4
        assert fresh27["structured_positives"] == 0
        assert fresh27["sibling_selections"] == 0
        assert fresh27["bin_handoff"] == 0
        assert fresh27["gate_handoff"] == 0
        assert fresh27["historical_guard_loss"] == []
        assert fresh27["inspected_score_bugs"] == ["BUG-WD12", "BUG-HB12", "BUG-GL12", "BUG-SG12"]
        assert fresh26["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh26.get("available"):
        assert body["latest"]["round"] == "v0.3.26"
        assert body["project"]["latest_research"] == "v0.3.26"
        assert body["latest"]["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh26["outcome"] == "C"
        assert fresh26["evaluable_positives"] == 4
        assert fresh26["structured_positives"] == 4
        assert fresh26["rack_handoff"] == 0
        assert fresh26["window_handoff"] == 0
        assert fresh26["historical_guard_loss"][0]["app"] == "buggy-desk"
        assert fresh26["inspected_score_bugs"] == ["BUG-CL12", "BUG-DP12", "BUG-AR12", "BUG-FL12"]
        assert fresh25["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh25.get("available"):
        assert body["latest"]["round"] == "v0.3.25"
        assert body["project"]["latest_research"] == "v0.3.25"
        assert body["latest"]["outcome"] == "C"
        assert body["latest"]["product_default_changed"] is False
        assert fresh25["outcome"] == "C"
        assert fresh25["fresh_validation"] is True
        assert fresh25["v0324_outcome"] == "A"
        assert fresh25["evaluable_positives"] == 4
        assert fresh25["structured_positives"] == 0
        assert fresh25["shelf_handoff"] == 0
        assert fresh25["counter_handoff"] == 0
        assert fresh25["historical_guard_loss"] == []
        assert episode["outcome"] == "A"
        assert episode["product_default_changed"] is False
    elif episode.get("available"):
        assert body["latest"]["round"] == "v0.3.24"
        assert body["project"]["latest_research"] == "v0.3.24"
        assert body["latest"]["outcome"] == "A"
        assert body["latest"]["product_default_changed"] is False
        assert episode["outcome"] == "A"
        assert episode["product_default_changed"] is False
        assert episode["fresh_validation"] is False
        assert episode["v0323_outcome"] == "B"
        assert episode["v0322_diagnosis"] == "persistent_post_terminal_sink"
        assert episode["v0321_outcome"] == "C"
        assert episode["campus"]["episode_advances"] == 1
        assert episode["studio"]["episode_advances"] == 1
        assert episode["campus"]["revalidated"] >= 1
        assert episode["studio"]["revalidated"] >= 1
        assert episode["campus"]["template_589"] is True
        assert episode["studio"]["template_589"] is True
        assert episode["warehouse"]["episode_advances"] == 0
        assert episode["booking"]["episode_advances"] == 0
        assert episode["catalog_episode_advances"] == 0
        assert episode["kiosk_episode_advances"] == 0
        assert episode["safety_violations"] == 0
        assert debt["outcome"] == "B"
        assert debt["product_default_changed"] is False
    elif debt.get("available"):
        assert body["latest"]["round"] == "v0.3.23"
        assert body["project"]["latest_research"] == "v0.3.23"
        assert body["latest"]["outcome"] == "B"
        assert body["latest"]["product_default_changed"] is False
        assert debt["outcome"] == "B"
        assert debt["product_default_changed"] is False
        assert debt["fresh_validation"] is False
        assert debt["v0322_diagnosis"] == "persistent_post_terminal_sink"
        assert debt["v0321_outcome"] == "C"
        assert debt["campus"]["relocations"] == 1
        assert debt["studio"]["relocations"] == 1
        assert debt["catalog_relocations"] == 0
        assert debt["kiosk_relocations"] == 0
        assert debt["safety_violations"] == 0
        assert sink["diagnosis"] == "persistent_post_terminal_sink"
        assert sink["v0321_outcome"] == "C"
        assert rw["outcome"] == "C"
        assert sink["product_default_changed"] is False
        assert sink["fresh_validation"] is False
        assert rw["product_default_changed"] is False
        assert rw["fresh_validation"] is False
        assert rw["engaged"] == 4
        assert fc.get("outcome") == "C"
        assert fr.get("outcome") == "A"
    elif sink.get("available"):
        assert body["latest"]["round"] == "v0.3.22"
        assert body["project"]["latest_research"] == "v0.3.22"
        assert body["latest"].get("diagnosis")
        assert body["latest"].get("outcome") is None
        assert rw["outcome"] == "C"
        assert sink["product_default_changed"] is False
        assert sink["fresh_validation"] is False
        assert sink["v0321_outcome"] == "C"
        assert rw["product_default_changed"] is False
        assert rw["fresh_validation"] is False
        assert rw["engaged"] == 4
        assert fc.get("outcome") == "C"
        assert fr.get("outcome") == "A"
    elif rw.get("available"):
        assert body["latest"]["round"] == "v0.3.21"
        assert body["project"]["latest_research"] == "v0.3.21"
        assert rw["outcome"] == "C"
        assert rw["product_default_changed"] is False
        assert rw["fresh_validation"] is False
        assert rw["engaged"] == 4
        assert rw["catalog_escapes"] == 0
        assert rw["kiosk_escapes"] == 0
        assert fc.get("outcome") == "C"
        assert fr.get("outcome") == "A"
        assert re.get("outcome") == "C"
        assert la.get("outcome") == "B"
        assert rf.get("outcome") == "B"
        assert fh.get("outcome") == "C"
        assert hh.get("outcome") == "A"
    elif fc.get("available"):
        assert body["latest"]["round"] == "v0.3.20"
        assert body["project"]["latest_research"] == "v0.3.20"
        assert fc["outcome"] == "C"
        assert fc["product_default_changed"] is False
        assert fc["composite_evaluable"] == 4
        assert fc["full_transfer"] == 0
        assert fc["guard_loss_count"] == 4
        assert fc["catalog_events"] == 0
        assert fc["kiosk_handoffs"] == 0
        assert fc["horizon_drains"] == 0
        assert fr.get("outcome") == "A"
        assert re.get("outcome") == "C"
        assert la.get("outcome") == "B"
        assert rf.get("outcome") == "B"
        assert fh.get("outcome") == "C"
        assert hh.get("outcome") == "A"
    elif fr.get("available"):
        assert body["latest"]["round"] == "v0.3.19"
        assert body["project"]["latest_research"] == "v0.3.19"
        assert fr["outcome"] == "A"
        assert fr["product_default_changed"] is False
        assert fr["lab_lost"] == []
        assert fr["deep_lost"] == []
        assert fr["directory_handoffs"] == 0
        assert fr["forum_full_transfer"] is True
        assert fr["billing_full_transfer"] is True
        assert fr["historical_regression_loss_count"] == 0
        assert fr["finding_drains"] == 3
        assert fr["horizon_bypasses"] == 13
        assert fr["deep_horizon_drains"] == 0
        assert re.get("outcome") == "C"
        assert la.get("outcome") == "B"
        assert rf.get("outcome") == "B"
        assert fh.get("outcome") == "C"
        assert hh.get("outcome") == "A"
    elif re.get("available"):
        assert body["latest"]["round"] == "v0.3.18"
        assert body["project"]["latest_research"] == "v0.3.18"
        assert re["outcome"] == "C"
        assert re["lab_l9_before"] == "lost"
        assert re["lab_l9_after"] == "retained"
        assert re["directory_handoffs"] == 0
        assert re["product_default_changed"] is False
        assert re["return_entry_drains"] >= 1
        assert "btn_close" in (re.get("result_buttons_drained") or [])
        assert "btn_reopen" in (re.get("result_buttons_drained") or [])
        assert re["historical_regression_loss_count"] > 0
        assert la.get("outcome") == "B"
        assert rf.get("outcome") == "B"
        assert fh.get("outcome") == "C"
        assert hh.get("outcome") == "A"
    elif la.get("available"):
        assert body["latest"]["round"] == "v0.3.17"
        assert body["project"]["latest_research"] == "v0.3.17"
        assert la["outcome"] == "B"
        assert la["directory_handoffs"] == 0
        assert la["historical_regression_loss"] == 0
        assert la["product_default_changed"] is False
        assert la["buttons_drained"] >= 1
        assert la["promoted_children"] == 0
        assert "BUG-L9" in (la.get("lab_lost") or [])
        assert "BUG-L1" not in (la.get("lab_lost") or [])
        assert "BUG-L10" not in (la.get("lab_lost") or [])
        assert rf.get("outcome") == "B"
        assert fh.get("outcome") == "C"
        assert hh.get("outcome") == "A"
        assert ns.get("outcome") == "C"
        assert mt.get("outcome") == "D"
    elif rf.get("available"):
        assert body["latest"]["round"] == "v0.3.16"
        assert body["project"]["latest_research"] == "v0.3.16"
        assert rf["outcome"] == "B"
        assert rf["directory_handoffs"] == 0
        assert rf["directory_handoffs_before"] == 2
        assert rf["lab_leases"] >= 1
        assert "BUG-L8" not in (rf.get("lab_lost") or [])
        assert rf["historical_regression_loss"] == 0
        assert rf["product_default_changed"] is False
        assert fh.get("outcome") == "C"
        assert fh["evaluable_targets"] == 3
        assert fh["transfer_targets"] == 2
        assert fh["negative_control_handoffs"] == 2
        assert hh.get("outcome") == "A"
        assert ns.get("outcome") == "C"
        assert mt.get("outcome") == "D"
    elif fh.get("available"):
        assert body["latest"]["round"] == "v0.3.15"
        assert body["project"]["latest_research"] == "v0.3.15"
        assert fh["outcome"] == "C"
        assert fh["evaluable_targets"] == 3
        assert fh["transfer_targets"] == 2
        assert fh["negative_control_handoffs"] == 2
        assert fh["bug_loss_count"] == 1
        assert fh["product_default_changed"] is False
        assert fh["promotion_readiness"] == "not_ready"
        assert hh.get("outcome") == "A"
        assert ns.get("outcome") == "C"
        assert mt.get("outcome") == "D"
    elif hh.get("available"):
        assert body["latest"]["round"] == "v0.3.14"
        assert body["project"]["latest_research"] == "v0.3.14"
        assert hh["product_default_changed"] is False
        assert hh["outcome"] == "A"
        assert hh.get("generalization_claim") is False
        assert ns.get("outcome") == "C"
    elif ns.get("available"):
        assert body["latest"]["round"] == "v0.3.13"
        assert body["project"]["latest_research"] == "v0.3.13"
        assert ns["product_default_changed"] is False
        assert ns["outcome"] == "C"
        assert ns.get("generalization_claim") is False
        assert nh.get("outcome") == "C"
    elif nh.get("available"):
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
    ns = s["nested_stack"]
    assert ns["available"] is True
    hh = s["horizon_handoff"]
    assert hh["available"] is True
    fh = s["fresh_handoff"]
    assert fh["available"] is True
    assert fh["outcome"] == "C"
    rf = s["reentry_frontier"]
    assert rf["available"] is True
    assert rf["outcome"] == "B"
    assert rf["product_default_changed"] is False
    la = s["local_action_drain"]
    assert la["available"] is True
    assert la["outcome"] == "B"
    assert la["product_default_changed"] is False
    assert la["directory_handoffs"] == 0
    re = s["return_entry_drain"]
    assert re["available"] is True
    assert re["outcome"] == "C"
    assert re["product_default_changed"] is False
    assert re["directory_handoffs"] == 0
    assert re["lab_l9_before"] == "lost"
    assert re["lab_l9_after"] == "retained"
    fr = s["finding_return_entry"]
    assert fr["available"] is True
    assert fr["outcome"] == "A"
    assert fr["product_default_changed"] is False
    assert fr["lab_lost"] == []
    assert fr["deep_lost"] == []
    assert fr["directory_handoffs"] == 0
    fc = s["fresh_composite"]
    assert fc["available"] is True
    assert fc["outcome"] == "C"
    assert fc["product_default_changed"] is False
    assert fc["promotion_readiness"] == "not_ready"
    assert fc["guard_loss_count"] == 4
    assert fc["catalog_events"] == 0
    assert fc["kiosk_handoffs"] == 0
    rw = s["return_waypoint"]
    assert rw["available"] is True
    assert rw["outcome"] == "C"
    assert rw["product_default_changed"] is False
    assert rw["fresh_validation"] is False
    assert rw["engaged"] == 4
    assert rw["catalog_escapes"] == 0
    assert rw["kiosk_escapes"] == 0
    sink = s.get("post_escape_sink") or {}
    debt = s.get("residual_frontier_debt") or {}
    episode = s.get("episode_drain") or {}
    fresh25 = s.get("fresh_transfer_v0325") or {}
    fresh26 = s.get("fresh_transfer_v0326") or {}
    fresh27 = s.get("fresh_transfer_v0327") or {}
    fresh30 = s.get("fresh_transfer_v0330") or {}
    fresh31 = s.get("fresh_transfer_v0331") or {}
    fresh32 = s.get("fresh_transfer_v0332") or {}
    fresh33 = s.get("fresh_transfer_v0333") or {}
    fresh34 = s.get("fresh_transfer_v0334") or {}
    fresh35 = s.get("fresh_transfer_v0335") or {}
    fresh36 = s.get("fresh_transfer_v0336") or {}
    fresh37 = s.get("fresh_transfer_v0337") or {}
    fresh38 = s.get("fresh_transfer_v0338") or {}
    if fresh38.get("available"):
        assert s["latest"]["round"] == "v0.3.38"
        assert s["latest"]["outcome"] == "A"
        assert fresh38["outcome"] == "A"
        assert s["project"]["latest_research"] == "v0.3.38"
        assert s["latest"]["product_default_changed"] is False
        assert fresh38["promotion_readiness"] == "not_ready"
        assert fresh38["evaluable_positives"] == 4
        assert fresh38["structured_positives"] == 4
        assert fresh38["fresh_guard_loss"] == []
        assert fresh38["historical_guard_loss"] == []
        assert fresh38["saddle_handoff"] == 0
        assert fresh38["timber_handoff"] == 0
        published = _v0338_publication()
        assert fresh38["outcome"] == published["outcome"]
        assert fresh38["evaluable_positives"] == published["evaluable_positives"]
        assert fresh38["structured_positives"] == published["structured_positives"]
        assert fresh38["fresh_guard_loss"] == published["fresh_guard_loss"]
        assert fresh38["historical_guard_loss"] == published["historical_guard_loss"]
        assert fresh38["saddle_handoff"] == published["saddle_handoff"]
        assert fresh38["timber_handoff"] == published["timber_handoff"]
        assert fresh37["outcome"] == "C"
        assert fresh36["outcome"] == "C"
        assert fresh35["outcome"] == "A"
        assert GhostPolicy().sequence_mode == "off"
        assert GhostPolicy().use_frontier is False
        assert episode["outcome"] == "A"
    elif fresh37.get("available"):
        assert s["latest"]["round"] == "v0.3.37"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.37"
        assert s["latest"]["product_default_changed"] is False
        assert fresh37["promotion_readiness"] == "not_ready"
        assert fresh37["evaluable_positives"] == 4
        assert fresh37["structured_positives"] == 0
        assert [row["bugs"] for row in fresh37["fresh_guard_loss"]] == [
            ["BUG-FD10"], ["BUG-GD10"], ["BUG-HL10"], ["BUG-IT10"]]
        assert fresh37["historical_guard_loss"] == [
            {"app": "buggy-directory", "bugs": ["BUG-DIR5"]}]
        assert fresh37["junction_handoff"] == 0
        assert fresh37["karst_handoff"] == 0
        assert fresh36["outcome"] == "C"
        assert fresh35["outcome"] == "A"
        assert GhostPolicy().sequence_mode == "off"
        assert GhostPolicy().use_frontier is False
        assert episode["outcome"] == "A"
    elif fresh36.get("available"):
        assert s["latest"]["round"] == "v0.3.36"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.36"
        assert fresh36["evaluable_positives"] == 4
        assert fresh36["structured_positives"] == 0
        assert [row["bugs"] for row in fresh36["fresh_guard_loss"]] == [
            ["BUG-WI10"], ["BUG-YA10"], ["BUG-ZE10"], ["BUG-AB10"]]
        assert fresh36["historical_guard_loss"] == [
            {"app": "buggy-directory", "bugs": ["BUG-DIR5"]}]
        assert fresh36["basin_handoff"] == 0
        assert fresh36["cleft_handoff"] == 0
        assert fresh35["outcome"] == "A"
        assert fresh34["outcome"] == "A"
        assert episode["outcome"] == "A"
    elif fresh35.get("available"):
        assert s["latest"]["round"] == "v0.3.35"
        assert s["latest"]["outcome"] == "A"
        assert s["project"]["latest_research"] == "v0.3.35"
        assert fresh35["evaluable_positives"] == 4
        assert fresh35["structured_positives"] == 4
        assert fresh35["fresh_guard_loss"] == []
        assert fresh35["historical_guard_loss"] == []
        assert fresh35["umber_handoff"] == 0
        assert fresh35["verge_handoff"] == 0
        assert fresh34["outcome"] == "A"
        assert fresh33["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh34.get("available"):
        assert s["latest"]["round"] == "v0.3.34"
        assert s["latest"]["outcome"] == "A"
        assert s["project"]["latest_research"] == "v0.3.34"
        assert fresh34["evaluable_positives"] == 4
        assert fresh34["structured_positives"] == 4
        assert fresh34["fresh_guard_loss"] == []
        assert fresh34["historical_guard_loss"] == []
        assert fresh34["oxbow_handoff"] == 0
        assert fresh34["pond_handoff"] == 0
        assert fresh33["outcome"] == "C"
        assert fresh32["outcome"] == "A"
        assert episode["outcome"] == "A"
    elif fresh33.get("available"):
        assert s["latest"]["round"] == "v0.3.33"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.33"
        assert fresh33["evaluable_positives"] == 4
        assert fresh33["structured_positives"] == 4
        assert fresh33["fresh_guard_loss"] == []
        assert fresh33["historical_guard_loss"] == [
            {"app": "buggy-wiki", "bugs": ["BUG-W2"]}]
        assert fresh33["ledge_handoff"] == 0
        assert fresh33["notch_handoff"] == 0
        assert fresh32["outcome"] == "A"
        assert fresh31["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh32.get("available"):
        assert s["latest"]["round"] == "v0.3.32"
        assert s["latest"]["outcome"] == "A"
        assert fresh32["outcome"] == "A"
        assert s["project"]["latest_research"] == "v0.3.32"
        assert fresh32["evaluable_positives"] == 4
        assert fresh32["structured_positives"] == 4
        assert fresh32["fresh_guard_loss"] == []
        assert fresh32["historical_guard_loss"] == []
        assert fresh32["loft_handoff"] == 0
        assert fresh32["mesa_handoff"] == 0
        assert fresh32["product_default_changed"] is False
        assert fresh31["outcome"] == "C"
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh31.get("available"):
        assert s["latest"]["round"] == "v0.3.31"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.31"
        assert fresh31["evaluable_positives"] == 4
        assert fresh31["structured_positives"] == 0
        assert fresh31["crate_handoff"] == 0
        assert fresh31["stand_handoff"] == 0
        assert fresh31["historical_guard_loss"] == []
        assert fresh30["outcome"] == "C"
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh30.get("available"):
        assert s["latest"]["round"] == "v0.3.30"
        assert s["latest"]["outcome"] == "C"
        assert fresh27["outcome"] == "B"
        assert episode["outcome"] == "A"
    elif fresh27.get("available"):
        assert s["latest"]["round"] == "v0.3.27"
        assert s["latest"]["outcome"] == "B"
        assert s["project"]["latest_research"] == "v0.3.27"
        assert fresh26["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh26.get("available"):
        assert s["latest"]["round"] == "v0.3.26"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.26"
        assert fresh25["outcome"] == "C"
        assert episode["outcome"] == "A"
    elif fresh25.get("available"):
        assert s["latest"]["round"] == "v0.3.25"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.25"
        assert episode["outcome"] == "A"
    elif episode.get("available"):
        assert s["latest"]["round"] == "v0.3.24"
        assert s["latest"]["outcome"] == "A"
        assert s["latest"]["product_default_changed"] is False
        assert s["project"]["latest_research"] == "v0.3.24"
        assert episode["campus"]["template_589"] is True
        assert episode["studio"]["template_589"] is True
        assert episode["warehouse"]["episode_advances"] == 0
        assert episode["booking"]["episode_advances"] == 0
        assert debt["outcome"] == "B"
    elif debt.get("available"):
        assert s["latest"]["round"] == "v0.3.23"
        assert s["latest"]["outcome"] == "B"
        assert s["latest"]["product_default_changed"] is False
        assert s["project"]["latest_research"] == "v0.3.23"
        assert debt["fresh_validation"] is False
        assert debt["v0322_diagnosis"] == "persistent_post_terminal_sink"
        assert debt["v0321_outcome"] == "C"
        assert debt["campus"]["relocations"] == 1
        assert debt["studio"]["relocations"] == 1
        assert debt["catalog_relocations"] == 0
        assert debt["kiosk_relocations"] == 0
        assert debt["safety_violations"] == 0
        assert sink["diagnosis"] == "persistent_post_terminal_sink"
    elif sink.get("available"):
        assert s["latest"]["round"] == "v0.3.22"
        assert s["latest"].get("diagnosis")
        assert s["project"]["latest_research"] == "v0.3.22"
        assert sink["v0321_outcome"] == "C"
    else:
        assert s["latest"]["round"] == "v0.3.21"
        assert s["latest"]["outcome"] == "C"
        assert s["project"]["latest_research"] == "v0.3.21"
    assert hh["outcome"] == "A"
    assert hh["product_default_changed"] is False
    assert hh["generalization_claim"] is False
    assert hh["crm_repair"] is True
    assert hh["ops_repair"] is True
    assert hh["lost_count"] == 0
    assert hh["witness_violations"] == 0
    assert hh["reaudit"]["published_outcome"] == "C"
    assert hh["reaudit"]["counterfactual_outcome"] == "C"
    assert hh["reaudit"]["desk_old_bad"] == 1
    assert hh["reaudit"]["desk_residual"] == 0
    assert hh["reaudit"]["deep_old_bad"] == 33
    assert hh["reaudit"]["deep_residual"] == 0
    crm_h = {t["name"]: t for t in hh["targets"]}["buggy-crm"]
    assert crm_h["guard_states"] == 5
    assert crm_h["states"] > 5
    assert ns["outcome"] == "C"
    assert ns["product_default_changed"] is False
    assert ns["generalization_claim"] is False
    assert ns["crm_repair"] is False
    assert ns["ops_repair"] is False
    assert "BUG-K1" in (ns["lost"].get("buggy-desk") or [])
    assert "BUG-W2" in (ns["lost"].get("wiki") or [])
    crm = {t["name"]: t for t in ns["targets"]}["buggy-crm"]
    assert crm["guard_states"] == 5
    assert crm["stack_states"] == 5
    assert crm["stack_pushes"] == 80
    assert crm["stack_resumes"] == 0
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
        'id="run-form"', 'id="run-history"', 'id="shot"', 'id="graph"', 'id="btn-run"',
        'data-testid="return-cycle"', 'data-testid="fresh-transfer"',
        'data-testid="multi-target"', 'data-testid="evidence-v0311"',
        'data-testid="nested-hub"', 'data-testid="evidence-v0312"',
        'data-testid="horizon-handoff"', 'data-testid="evidence-v0314"',
        'data-testid="residual-debt"', 'data-testid="evidence-v0323"',
        'data-testid="post-escape-sink"', 'data-testid="evidence-v0322"',
        'id="proof-metric-1"', 'id="tl-v0311"', 'id="tl-v0312"', 'id="tl-v0314"', 'id="tl-v0338"',
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
    from ghostqa.__main__ import POLICIES
    research_names = (
        "ghost-structural-horizon-handoff-guard",
        "ghost-structural-reentry-frontier-guard",
        "ghost-structural-local-action-drain-guard",
        "ghost-structural-return-entry-drain-guard",
        "ghost-structural-finding-return-entry-drain-guard",
        "ghost-structural-return-waypoint-frontier-guard",
        "ghost-structural-residual-frontier-debt-guard",
        "ghost-structural-episode-drain-epoch-guard",
        "ghost-structural-untried-sibling-guard",
        "ghost-structural-parent-hub-sibling-guard",
        "ghost-structural-repeat-click-guard",
        "ghost-structural-alternate-payload-guard",
        "ghost-structural-payload-button-guard",
        "ghost-structural-page-buttons-guard",
        "ghost-structural-seen-button-guard",
        "ghost-structural-search-submit-guard",
        "ghost-structural-hub-distractor-guard",
        "ghost-structural-loop-exit-guard",
        "ghost-structural-side-back-guard",
    )
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    assert 'value="ghost" selected' in html
    for name in research_names:
        policy = _make_policy(name, None, 0)
        assert name in POLICIES
        assert policy.name == name
        assert policy.use_frontier is False
        assert policy is not d
        assert f'value="{name}"' in html
    assert d.sequence_mode == "off"
    assert d.use_frontier is False
    assert d.postreach_mode == "off"
    variants = (
        ("ghost-branch", "branch", "off"),
        ("ghost-followup", "followup", "off"),
        ("ghost-sequence", "sequence", "off"),
        ("ghost-deferred", "off", "deferred"),
        ("ghost-exploit", "off", "exploit"),
        ("ghost-postreach", "off", "postreach"),
    )
    for name, sequence_mode, postreach_mode in variants:
        policy = _make_policy(name, None, 0)
        assert name in POLICIES
        assert isinstance(policy, GhostPolicy)
        assert policy.name == "ghost"
        assert policy.sequence_mode == sequence_mode
        assert policy.postreach_mode == postreach_mode
        assert policy.use_frontier is False
        assert f'value="{name}"' in html
    assert 'id="h-tl">v0.3.6 → v0.3.38' in html
    assert 'id="tl-v0338"' in html
    assert "Outcome A。四个新正例保住全部 Guard 缺陷" in html
    assert 'id="run-history"' in html
    import pytest
    with pytest.raises(ValueError):
        _make_policy("not-a-real-policy", None, 0)


def test_reopen_restores_last_frame_and_run_config():
    js = open(os.path.join(STATIC_DIR, "scripts", "main.js"), encoding="utf-8").read()
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    assert "function latestFrame" in js
    assert "function applyRunConfig" in js
    assert "selectEvent(latestFrame(S.events))" in js
    assert "function eventForBug" in js
    assert "S.epoch" in js
    assert "main.js?v=20260930c" in html
    assert "const showErrorReport" in js
    assert "function unconfirmedCandidates" in js
    assert "candidate.replay_status !== 'failed'" in js
    assert "重放未完成" in js
    assert "st.status === 'done' || st.status === 'error' || st.status === 'stopped'" in js
    assert "function visibleErrorLine" in js
    assert "停止重放" in js
    assert "function withVisibleLabel" in js
    assert "function runSteps" in js
    assert "summary.actions" in js
    assert "停止探索" in js
    assert "/cancel" in js
    assert "fmtAction(a).join" not in js
    assert "function runWhen" in js
    assert "a.label" in js
    assert "run.id" in js
    assert "components.css?v=20260930b" in html
    assert "runs.slice(0, 12)" not in js
    css = open(os.path.join(STATIC_DIR, "styles", "components.css"), encoding="utf-8").read()
    assert "max-height: 320px" in css
    assert ".bug-desc" in css
    assert "flex: 1 1 100%" in css
    assert "overflow-wrap: anywhere" in css
    assert ".bug.is-unconfirmed" in css
    assert "未通过重放" in js


def test_rendered_report_uses_stored_json_not_stale_html(tmp_path, monkeypatch):
    import dashboard.server as srv
    run_id = "rpttest1"
    run_dir = tmp_path / run_id
    run_dir.mkdir()
    report = {
        "app": "shop",
        "policy": "ghost",
        "summary": {
            "actions_executed": 2,
            "states_discovered": 3,
            "candidate_findings": 1,
            "confirmed_bugs": 1,
            "llm_calls": 0,
            "pseudo_tokens": 0,
            "wall_seconds": 1.0,
        },
        "bugs": [{
            "finding": {
                "kind": "semantic",
                "severity": "high",
                "description": "用户名为空时不应提示注册成功",
                "step_index": 1,
                "evidence": {
                    "url": "http://127.0.0.1:3939/register.html",
                    "obs": {"form_msg": "注册成功", "input_reg_user": ""},
                },
            },
            "reproduction": [
                {"type": "click", "target_eid": "252de9b8e3"},
                {"type": "click", "target_eid": "btn_reg"},
            ],
            "original_length": 2,
            "source_episode_id": 0,
            "original_global_step": 1,
        }],
    }
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (run_dir / "report.html").write_text("<html>stale</html>", encoding="utf-8")
    (run_dir / "events.jsonl").write_text(
        json.dumps({
            "type": "step",
            "action": {"type": "click", "target_eid": "252de9b8e3",
                       "text": None, "label": "link:注册"},
        }, ensure_ascii=False) + "\n",
        encoding="utf-8")
    monkeypatch.setattr(srv, "_run_dir", lambda rid: str(tmp_path / rid))
    handle = srv.RunHandle(run_id, {"policy": "ghost"})
    handle.report_html = str(run_dir / "report.html")
    handle.status = "done"
    srv.RUNS[run_id] = handle
    try:
        page = srv.rendered_report_html(str(run_dir))
        assert "register.html" in page
        assert "form_msg" in page
        assert "click[link:注册]" in page
        assert 'title="252de9b8e3"' in page
        assert "click[btn_reg]" in page
        assert "stale" not in page
        resp = srv.run_report(run_id)
        body = resp.body.decode("utf-8")
        assert "register.html" in body
        assert "click[link:注册]" in body
        assert "stale" not in body
        assert resp.headers.get("cache-control") == "no-store"
        assert "未通过重放" not in body
    finally:
        srv.RUNS.pop(run_id, None)
    assert srv.rendered_report_html(str(tmp_path / "missing")) is None


def test_rendered_report_lists_replay_failures(tmp_path):
    """The header already counts every candidate. List the ones replay rejected."""
    import dashboard.server as srv
    from ghostqa.report.generator import render_html

    run_dir = tmp_path / "rptfail1"
    run_dir.mkdir()
    semantic = "用户名为空时不应提示注册成功"
    report = {
        "app": "shop",
        "policy": "ghost",
        "summary": {
            "actions_executed": 3,
            "states_discovered": 2,
            "candidate_findings": 2,
            "confirmed_bugs": 1,
            "llm_calls": 0,
            "pseudo_tokens": 0,
            "wall_seconds": 1.0,
        },
        "bugs": [{
            "finding": {
                "kind": "semantic",
                "severity": "high",
                "description": semantic,
                "step_index": 1,
                "evidence": {"url": "http://127.0.0.1:3939/register.html"},
            },
            "reproduction": [{"type": "click", "target_eid": "btn_reg"}],
            "original_length": 2,
            "source_episode_id": 0,
            "original_global_step": 1,
        }],
    }
    dead = {
        "kind": "dead_action",
        "severity": "medium",
        "description": "点击无响应：元素 btn_reg 点击后界面无任何变化",
        "step_index": 2,
        "evidence": {
            "eid": "btn_reg",
            "url": "http://127.0.0.1:3939/register.html",
            "action": "click[btn_reg]",
        },
    }
    (run_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")
    (run_dir / "candidates.json").write_text(json.dumps([
        {
            "kind": "semantic",
            "severity": "high",
            "description": semantic,
            "step_index": 1,
            "evidence": {"url": "http://127.0.0.1:3939/register.html"},
        },
        dead,
    ], ensure_ascii=False), encoding="utf-8")
    page = srv.rendered_report_html(str(run_dir))
    assert page.count(semantic) == 1
    assert "未通过重放" in page
    assert "点击无响应：元素 btn_reg 点击后界面无任何变化" in page
    assert "click[btn_reg]" in page
    pending = page.split("未通过重放", 1)[1]
    assert "最小复现路径" not in pending
    direct = render_html(report, [dead])
    assert "未通过重放" in direct
    assert "最小复现路径" not in direct.split("未通过重放", 1)[1]


def test_stopped_report_does_not_call_unfinished_candidates_failed():
    """A user stop did not replay the remaining candidates."""
    from ghostqa.report.generator import render_html

    dead = {
        "kind": "dead_action",
        "severity": "medium",
        "description": "点击无响应：元素 btn_reg 点击后界面无任何变化",
        "step_index": 2,
        "evidence": {"eid": "btn_reg", "url": "http://127.0.0.1:8798/cases/register.html"},
    }
    confirmed = {
        "finding": {
            "kind": "semantic",
            "severity": "high",
            "description": "用户名为空时不应提示注册成功",
            "step_index": 1,
            "evidence": {"url": "http://127.0.0.1:8798/cases/register.html"},
        },
        "reproduction": [{"type": "click", "target_eid": "btn_reg", "label": "button:提交注册"}],
        "original_length": 2,
        "source_episode_id": 0,
        "original_global_step": 1,
    }
    summary = {
        "actions_executed": 13,
        "states_discovered": 6,
        "candidate_findings": 2,
        "confirmed_bugs": 1,
        "llm_calls": 0,
        "pseudo_tokens": 0,
        "wall_seconds": 8.0,
    }
    stopped = render_html({
        "app": "cases",
        "policy": "ghost",
        "summary": summary,
        "bugs": [confirmed],
        "replay_state": "stopped",
    }, [dead])
    assert "重放没有跑完，这些候选还不能当成已确认缺陷。" in stopped
    assert "重放未完成" in stopped
    assert "未通过重放" not in stopped
    assert "已重放确认" in stopped
    assert "click[button:提交注册]" in stopped
    pending = stopped.split("重放未完成", 1)[1]
    assert "最小复现路径" not in pending
    finished = render_html({
        "app": "cases",
        "policy": "ghost",
        "summary": summary,
        "bugs": [confirmed],
    }, [dead])
    assert "未通过重放" in finished
    assert "重放未完成" not in finished


def test_report_html_includes_page_and_observation():
    from ghostqa.report.generator import render_html
    report = {
        "app": "shop",
        "policy": "ghost",
        "summary": {
            "actions_executed": 2,
            "states_discovered": 3,
            "candidate_findings": 1,
            "confirmed_bugs": 1,
            "llm_calls": 0,
            "pseudo_tokens": 0,
            "wall_seconds": 1.0,
        },
        "bugs": [{
            "finding": {
                "kind": "semantic",
                "severity": "high",
                "description": "用户名为空时不应提示注册成功",
                "step_index": 1,
                "evidence": {
                    "url": "http://127.0.0.1:3939/register.html",
                    "obs": {"form_msg": "注册成功", "input_reg_user": ""},
                },
            },
            "reproduction": [{"type": "click", "target_eid": "btn_reg"}],
            "original_length": 2,
            "source_episode_id": 0,
            "original_global_step": 1,
        }],
    }
    page = render_html(report)
    assert "register.html" in page
    assert "form_msg" in page
    assert "注册成功" in page
    assert "（空）" in page
    report["bugs"][0]["finding"]["evidence"] = {}
    assert "最小复现路径" in render_html(report)
    report["bugs"][0]["reproduction"] = [{
        "type": "input",
        "target_eid": "search_box",
        "text": "测试输入",
        "label": "input:搜索商品",
    }]
    typed = render_html(report)
    assert "input[input:搜索商品]=测试输入" in typed
    assert 'title="search_box"' in typed


def test_hydrate_restores_saved_error(tmp_path, monkeypatch):
    """A failed run stores its traceback in meta.json. Restart must keep it."""
    import dashboard.server as srv

    failed = tmp_path / "errkeep1"
    failed.mkdir()
    (failed / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "bfs"},
        "created": 1,
        "status": "error",
        "error": "TimeoutError: waiting until domcontentloaded\n"
                 "navigating to http://127.0.0.1:3939/index.html",
    }), encoding="utf-8")
    interrupted = tmp_path / "runint1"
    interrupted.mkdir()
    (interrupted / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "ghost"},
        "created": 2,
        "status": "running",
    }), encoding="utf-8")
    monkeypatch.setattr(srv, "RUNS_DIR", str(tmp_path))
    for run_id in ("errkeep1", "runint1"):
        srv.RUNS.pop(run_id, None)
    try:
        srv._hydrate_runs()
        restored = srv.RUNS["errkeep1"]
        assert restored.status == "error"
        assert restored.error.endswith("navigating to http://127.0.0.1:3939/index.html")
        stopped = srv.RUNS["runint1"]
        assert stopped.status == "error"
        assert stopped.error == "interrupted (server restarted)"
    finally:
        srv.RUNS.pop("errkeep1", None)
        srv.RUNS.pop("runint1", None)


def test_hydrate_recovers_candidates_after_validation_crash(tmp_path, monkeypatch):
    """A ddmin timeout used to leave the finished exploration with no candidates."""
    import dashboard.server as srv

    run = tmp_path / "ddminerr"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "bfs", "budget": 40},
        "created": 3,
        "status": "error",
        "error": "playwright._impl._errors.TimeoutError: Page.goto: Timeout 15000ms exceeded.\n",
    }), encoding="utf-8")
    semantic = {
        "kind": "semantic",
        "severity": "high",
        "description": "用户名为空时不应提示注册成功",
        "step_index": 27,
        "evidence": {
            "assert_id": "register_requires_username",
            "url": "http://127.0.0.1:3939/register.html",
        },
    }
    dead = {
        "kind": "dead_action",
        "severity": "medium",
        "description": "点击无响应：元素 btn_reg 点击后界面无任何变化",
        "step_index": 2,
        "evidence": {
            "eid": "btn_reg",
            "page": "http://127.0.0.1:3939/register.html",
            "url": "http://127.0.0.1:3939/register.html",
        },
    }
    lines = []
    for index, findings in ((2, [dead]), (27, [semantic]), (28, [dict(semantic, step_index=28)])):
        lines.append(json.dumps({
            "type": "step", "seq": index, "index": index, "episode_id": 1,
            "findings": findings,
        }, ensure_ascii=False))
    (run / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run / "graph.json").write_text(
        json.dumps({"nodes": [{"id": "a"}, {"id": "b"}], "edges": []}),
        encoding="utf-8")
    monkeypatch.setattr(srv, "RUNS_DIR", str(tmp_path))
    srv.RUNS.pop("ddminerr", None)
    try:
        srv._hydrate_runs()
        restored = srv.RUNS["ddminerr"]
        assert restored.status == "error"
        assert "TimeoutError" in restored.error
        assert [item["kind"] for item in restored.candidates] == ["dead_action", "semantic"]
        assert restored.candidates[1]["step_index"] == 27
        assert restored.candidates[1]["episode_id"] == 1
        assert restored.summary["actions"] == 3
        assert restored.summary["states"] == 2
        assert restored.summary["candidates"] == 2
        assert restored.summary["confirmed"] == 0
    finally:
        srv.RUNS.pop("ddminerr", None)


def test_crashed_run_without_report_file_lists_unfinished_candidates(tmp_path, monkeypatch):
    """A ddmin crash kept the findings in step events and never wrote report.json."""
    import pytest
    from fastapi import HTTPException
    import dashboard.server as srv
    from ghostqa.report.generator import report_for_saved_run

    assert report_for_saved_run({}, {}, [], "done") is None
    run = tmp_path / "crashrpt"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "bfs", "budget": 40},
        "created": 4,
        "status": "error",
        "error": "playwright._impl._errors.TimeoutError: Page.goto: Timeout 15000ms exceeded.\n",
        "summary": {
            "actions": 40, "states": 20, "candidates": 1, "confirmed": 0,
            "llm_calls": 0, "wall_seconds": 12.5,
        },
    }), encoding="utf-8")
    dead = {
        "kind": "dead_action",
        "severity": "medium",
        "description": "点击无响应：元素 btn_reg 点击后界面无任何变化",
        "step_index": 2,
        "evidence": {
            "eid": "btn_reg",
            "url": "http://127.0.0.1:3939/register.html",
            "action": "click[btn_reg]",
        },
    }
    (run / "events.jsonl").write_text(json.dumps({
        "type": "step", "seq": 2, "index": 2, "findings": [dead],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    empty = tmp_path / "emptyerr"
    empty.mkdir()
    (empty / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "ghost"},
        "created": 5,
        "status": "error",
        "error": "interrupted (server restarted)",
    }), encoding="utf-8")
    monkeypatch.setattr(srv, "RUNS_DIR", str(tmp_path))
    for run_id in ("crashrpt", "emptyerr"):
        srv.RUNS.pop(run_id, None)
    try:
        srv._hydrate_runs()
        resp = srv.run_report("crashrpt")
        body = resp.body.decode("utf-8")
        assert "重放没有跑完，这些候选还不能当成已确认缺陷。" in body
        assert "重放未完成" in body
        assert "未通过重放" not in body
        assert "最小复现路径" not in body
        assert "点击无响应：元素 btn_reg 点击后界面无任何变化" in body
        assert "click[btn_reg]" in body
        assert "web:127.0.0.1:3939" in body
        assert resp.headers.get("cache-control") == "no-store"
        with pytest.raises(HTTPException) as raised:
            srv.run_report("emptyerr")
        assert raised.value.status_code == 404
    finally:
        srv.RUNS.pop("crashrpt", None)
        srv.RUNS.pop("emptyerr", None)


def test_hydrate_keeps_saved_candidates_when_replay_was_interrupted(tmp_path, monkeypatch):
    import dashboard.server as srv

    run = tmp_path / "valint1"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:3939", "policy": "ghost", "budget": 8},
        "created": 4,
        "status": "validating",
        "summary": {"actions": 8, "states": 3, "candidates": 1, "confirmed": 0},
    }), encoding="utf-8")
    (run / "candidates.json").write_text(json.dumps([{
        "kind": "semantic",
        "description": "stored-candidate",
        "step_index": 1,
        "evidence": {"assert_id": "stored", "url": "http://127.0.0.1:3939/"},
    }]), encoding="utf-8")
    (run / "events.jsonl").write_text(json.dumps({
        "type": "step", "index": 4, "episode_id": 0,
        "findings": [{
            "kind": "dead_action",
            "description": "other-candidate",
            "step_index": 4,
            "evidence": {"eid": "btn_x", "page": "/x"},
        }],
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(srv, "RUNS_DIR", str(tmp_path))
    srv.RUNS.pop("valint1", None)
    try:
        srv._hydrate_runs()
        restored = srv.RUNS["valint1"]
        assert restored.status == "error"
        assert restored.error == "interrupted (server restarted)"
        assert restored.summary["actions"] == 8
        assert [item["description"] for item in restored.candidates] == ["stored-candidate"]
    finally:
        srv.RUNS.pop("valint1", None)


def test_entry_url_keeps_origin_index_and_opens_a_named_page():
    from ghostqa.executor.playwright_web import entry_url
    assert entry_url("http://127.0.0.1:3939") == "http://127.0.0.1:3939/index.html"
    assert entry_url("http://127.0.0.1:3939/") == "http://127.0.0.1:3939/"
    assert entry_url("http://127.0.0.1:8787/cases/register.html") == (
        "http://127.0.0.1:8787/cases/register.html")
    assert entry_url("http://127.0.0.1:5173/app/") == "http://127.0.0.1:5173/app/"


def test_builtin_cases_are_on_the_form_and_served():
    import dashboard.server as srv
    html = open(os.path.join(STATIC_DIR, "index.html"), encoding="utf-8").read()
    js = open(os.path.join(STATIC_DIR, "scripts", "main.js"), encoding="utf-8").read()
    assert 'id="f-case"' in html
    assert "我的项目" in html
    assert "空用户名注册" in html
    assert "apps/builtin-cases/spec.json" in html
    assert "function applyCase" in js
    assert "function dashboardLoopback" in js
    assert "$('f-policy').value = 'ghost-nollm'" not in js
    assert "$('f-mock').checked = true" not in js
    assert any(getattr(route, "path", None) == "/cases" for route in srv.app.routes)
    for name in (
        "index.html", "register.html", "dead.html", "script.html",
        "blank-link.html", "blank.html", "help.html", "help2.html",
        "stock.html", "cart.html", "profile.html",
    ):
        text = open(os.path.join(srv.CASES_DIR, name), encoding="utf-8").read()
        assert text.strip()
        assert "BUG-" not in text


def test_builtin_spec_resolves_from_repo_root(tmp_path, monkeypatch):
    import dashboard.server as srv
    from ghostqa.oracle.spec import load_spec
    monkeypatch.chdir(tmp_path)
    path = srv.resolve_spec_path("apps/builtin-cases/spec.json")
    loaded = load_spec(path)
    assert {item["id"] for item in loaded} >= {
        "case_register_requires_username",
        "case_stock_non_negative",
        "case_cart_total_consistent",
        "case_login_gate",
    }
    assert srv.reject_unreadable_spec("") == ""
    assert srv.reject_unreadable_spec("apps/builtin-cases/spec.json") == path


def test_missing_or_invalid_spec_is_rejected_before_a_run(tmp_path):
    from fastapi import HTTPException
    import dashboard.server as srv
    before = set(srv.RUNS)
    try:
        srv.start_run({
            "url": "http://127.0.0.1:9/index.html",
            "spec": "apps/does-not-exist.json",
            "policy": "ghost",
            "budget": 1,
        })
        assert False, "missing spec should not start a run"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "规格文件不存在" in exc.detail
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    try:
        srv.start_run({
            "url": "http://127.0.0.1:9/index.html",
            "spec": str(bad),
            "policy": "ghost",
            "budget": 1,
        })
        assert False, "invalid JSON should not start a run"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "不是合法 JSON" in exc.detail
    number = tmp_path / "num.json"
    number.write_text("123", encoding="utf-8")
    try:
        srv.reject_unreadable_spec(str(number))
        assert False, "a JSON number is not an assertion list"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "断言列表" in exc.detail
    assert set(srv.RUNS) == before


def test_replay_stop_keeps_confirms_and_skips_the_rest():
    import dashboard.server as srv
    from ghostqa.minimizer.ddmin import ReplayStopped, minimize_reproduction

    class Finding:
        def fingerprint(self):
            return "fp"

    try:
        minimize_reproduction(lambda: None, ["click"], Finding(), None,
                              should_stop=lambda: True)
        assert False, "stop must not look like a failed replay"
    except ReplayStopped:
        pass

    saved = []

    def minimize(finding):
        if finding == "later":
            raise ReplayStopped()
        return [finding]

    stopped = srv.replay_until_stop(
        ["kept", "skip", "later", "never"],
        lambda: False,
        lambda finding: finding != "skip",
        minimize,
        lambda finding, repro: saved.append((finding, repro)))
    assert stopped is True
    assert saved == [("kept", ["kept"])]

    calls = []
    stopped = srv.replay_until_stop(
        ["a", "b"],
        lambda: True,
        lambda finding: calls.append(finding) or True,
        lambda finding: ["x"],
        lambda finding, repro: None)
    assert stopped is True
    assert calls == []


def test_replay_marks_failed_candidates_and_continues():
    import dashboard.server as srv

    failed = []
    confirmed = []
    stopped = srv.replay_until_stop(
        ["bad", "good", "later"],
        lambda: False,
        lambda finding: finding == "good",
        lambda finding: [finding],
        lambda finding, repro: confirmed.append((finding, repro)),
        on_failed=failed.append,
    )
    assert stopped is False
    assert failed == ["bad", "later"]
    assert confirmed == [("good", ["good"])]


def test_visible_error_line_prefers_the_exception():
    import subprocess
    script = r"""
const fs = require('fs');
const js = fs.readFileSync('dashboard/static/scripts/main.js', 'utf8');
const start = js.indexOf('function visibleErrorLine');
const end = js.indexOf('function renderBugs');
eval(js.slice(start, end));
const raw = [
  'Traceback (most recent call last):',
  'playwright._impl._errors.TimeoutError: Page.goto: Timeout 15000ms exceeded.',
  'Call log:',
  '  - navigating to "http://127.0.0.1:3939/index.html", waiting until "domcontentloaded"'
].join('\n');
const line = visibleErrorLine(raw);
if (!line.includes('TimeoutError')) {
  console.error(line);
  process.exit(1);
}
if (visibleErrorLine('') !== '未知错误') process.exit(2);
"""
    subprocess.check_call(["node", "-e", script], cwd=os.path.dirname(os.path.dirname(__file__)))


def test_hydrate_keeps_a_stopped_replay(tmp_path, monkeypatch):
    import dashboard.server as srv
    run = tmp_path / "stop1"
    run.mkdir()
    (run / "meta.json").write_text(json.dumps({
        "cfg": {"url": "http://127.0.0.1:8798/cases/dead.html", "policy": "ghost"},
        "created": 5,
        "status": "stopped",
        "error": "",
        "summary": {"actions": 4, "states": 2, "candidates": 2, "confirmed": 1},
    }), encoding="utf-8")
    (run / "bugs.json").write_text(json.dumps([{"finding": {"kind": "dead_action"}}]),
                                   encoding="utf-8")
    (run / "candidates.json").write_text(json.dumps([
        {"kind": "dead_action"}, {"kind": "semantic"},
    ]), encoding="utf-8")
    monkeypatch.setattr(srv, "RUNS_DIR", str(tmp_path))
    srv.RUNS.pop("stop1", None)
    try:
        srv._hydrate_runs()
        restored = srv.RUNS["stop1"]
        assert restored.status == "stopped"
        assert restored.error == ""
        assert restored.summary["confirmed"] == 1
        assert len(restored.candidates) == 2
        assert len(restored.bugs) == 1
    finally:
        srv.RUNS.pop("stop1", None)
